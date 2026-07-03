"""NEWS-SOURCE-001 — 뉴스부 자료층 (MS-A 데이터 백본).

자료원 어댑터(NewsSource) + news_items / news_digest_snapshot DB 영속.

설계 (SPEC 결단):
  - M1: 기존 RSS(fetch_news) 를 RssNewsSource 어댑터 첫 구현체로 흡수 (중복 X, 승격).
        자료원에 코드 비종속 → 교체 자유. ManualNewsSource = 본문·유튜브 요약 직접 입력.
        PerplexityNewsSource = 인터페이스만 (이 환경 MCP 미연결 — drop-in SLOT).
  - M2: DB=사실(news_source_items 시계열) / canon=분류룰 (얕게 — knowledge/canon/news/).
  - M4: 개별 뉴스 *판단*=LLM (classify_news_items) / *집계*=결정론 (build_news_digest).
        정밀 점수(0~10) 폐기 → 거친 tone 5단 tilt + raw 라벨 내러티브 (정직성).
  - MS-A: 어댑터 + DB 영속(url 멱등).
  - MS-B (본 모듈 하단): classify_news_items (LLM 라벨, anchors.py mirror) +
        build_news_digest (결정론 집계) + render_news_digest_md ([8] 주입 블록).
  - MS-C: 소비 배선 (market_view · buy_score N · news_curator) — 별 작업.

크로스플랫폼: pathlib 전용. 멱등: url PK (news_source_items) / (scope, date) PK (digest).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml

from collectors.news_rss import NewsItem, fetch_news_items
from core.db.connection import get_db
from core.llm.client import call_llm, parse_json_response
from core.logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
NEWS_SOURCE_CONFIG_PATH = REPO_ROOT / "config" / "news_source.yaml"

_CONFIG_CACHE: dict[str, Any] | None = None

_EMPTY_CONFIG: dict[str, Any] = {
    "categories": [],
    "time_axes": [],
    "directions": ["up", "neutral", "down"],
    "magnitudes": [1, 2, 3],
    "sources": {},
}


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------
def load_news_source_config() -> dict[str, Any]:
    """config/news_source.yaml 로드 (캐시). 부재·파싱 실패 시 빈 dict fallback.

    score_inputs_config 로더 패턴 mirror (모듈 캐시 + reload). watchdog hot reload 호환.
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        if not NEWS_SOURCE_CONFIG_PATH.exists():
            log.warning("news_source_config_missing", path=str(NEWS_SOURCE_CONFIG_PATH))
            _CONFIG_CACHE = dict(_EMPTY_CONFIG)
        else:
            try:
                _CONFIG_CACHE = (
                    yaml.safe_load(NEWS_SOURCE_CONFIG_PATH.read_text(encoding="utf-8"))
                    or dict(_EMPTY_CONFIG)
                )
            except Exception as e:  # noqa: BLE001
                log.warning("news_source_config_load_failed", error=str(e))
                _CONFIG_CACHE = dict(_EMPTY_CONFIG)
    return _CONFIG_CACHE


def reload_news_source_config() -> None:
    """테스트/hot reload — 캐시 클리어."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# NewsSource 어댑터 (M1)
# ---------------------------------------------------------------------------
@runtime_checkable
class NewsSource(Protocol):
    """뉴스 자료원 추상. 구현체는 fetch() 로 라벨 미부여 NewsItem 목록을 낸다."""

    name: str

    async def fetch(self) -> list[NewsItem]:
        ...


class RssNewsSource:
    """기존 RSS(fetch_news_items) 흡수 — 자동수집 1차 라이브 구현체.

    제목·URL·게시일만 (본문 X). labeled_by='rss_raw' (분류 전).
    """

    name = "rss"

    def __init__(
        self,
        *,
        queries: list[str] | None = None,
        limit_per_source: int | None = None,
    ) -> None:
        cfg = (load_news_source_config().get("sources") or {}).get("rss") or {}
        self.queries = queries if queries is not None else cfg.get("queries")
        self.limit_per_source = (
            limit_per_source
            if limit_per_source is not None
            else int(cfg.get("limit_per_source", 15))
        )

    async def fetch(self) -> list[NewsItem]:
        items = await fetch_news_items(
            queries=self.queries, limit_per_source=self.limit_per_source
        )
        collected = _now_utc_iso()
        for it in items:
            it.labeled_by = "rss_raw"
            it.collected_at = collected
        return items


class ManualNewsSource:
    """수동 입력 — 본문·유튜브 요약 직접 주입 (사람이 가진 자료).

    records: [{title, url, source?, published_at?, body?, affected_scope?, affected_refs?}, ...]
    labeled_by='manual'. body(요약) 가 있어 MS-B 분류 시 grounding 근거가 된다.
    """

    name = "manual"

    def __init__(self, records: list[dict] | None = None) -> None:
        self.records = records or []

    async def fetch(self) -> list[NewsItem]:
        collected = _now_utc_iso()
        items: list[NewsItem] = []
        for r in self.records:
            url = (r.get("url") or "").strip()
            title = (r.get("title") or "").strip()
            if not title or not url:
                log.warning("manual_news_skip_missing_field", record=r)
                continue
            items.append(
                NewsItem(
                    title=title,
                    url=url,
                    source=r.get("source") or "manual",
                    published_at=r.get("published_at"),
                    body=r.get("body"),
                    affected_scope=r.get("affected_scope"),
                    affected_refs=list(r.get("affected_refs") or []),
                    labeled_by="manual",
                    collected_at=collected,
                )
            )
        return items


class PerplexityNewsSource:
    """drop-in SLOT — 이 환경 Perplexity MCP 미연결 (capability gap).

    MCP 연결 시 fetch() 를 구현해 자료원 토글만으로 합류. 현재는 명시적 미지원.
    """

    name = "perplexity"

    async def fetch(self) -> list[NewsItem]:
        raise NotImplementedError(
            "PerplexityNewsSource — 이 환경 Perplexity MCP 미연결. "
            "config sources.perplexity.enabled 는 drop-in SLOT (capability gap)."
        )


async def collect_from_sources(sources: list[NewsSource]) -> list[NewsItem]:
    """여러 자료원에서 수집 → URL dedup (먼저 온 소스 우선). 어댑터 단위 graceful."""
    seen: set[str] = set()
    merged: list[NewsItem] = []
    for src in sources:
        try:
            items = await src.fetch()
        except NotImplementedError:
            log.info("news_source_not_implemented", source=getattr(src, "name", "?"))
            continue
        except Exception as e:  # noqa: BLE001 — 한 소스 실패가 전체를 막지 않음
            log.warning("news_source_fetch_failed", source=getattr(src, "name", "?"), error=str(e))
            continue
        for it in items:
            if it.url in seen:
                continue
            seen.add(it.url)
            merged.append(it)
    return merged


# ---------------------------------------------------------------------------
# DB — news_items (url 멱등)
# ---------------------------------------------------------------------------
def upsert_news_items(items: list[NewsItem]) -> int:
    """news_source_items ON CONFLICT(url) REPLACE 멱등 upsert. 적재 건수 반환.

    분류 라벨(MS-B)이 재적재 시 갱신되도록 라벨 컬럼도 REPLACE.
    (테이블명 = news_source_items — 레거시 run-scoped news_items 와 구분.)
    """
    if not items:
        return 0
    db = get_db()
    with db.connect() as conn:
        for it in items:
            conn.execute(
                "INSERT INTO news_source_items "
                "(url, title, source, published_at, body, category, time_axis, "
                " direction, magnitude, confidence, affected_scope, affected_refs_json, "
                " labeled_by, collected_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(url) DO UPDATE SET "
                " title=excluded.title, source=excluded.source, "
                " published_at=excluded.published_at, body=excluded.body, "
                " category=excluded.category, time_axis=excluded.time_axis, "
                " direction=excluded.direction, magnitude=excluded.magnitude, "
                " confidence=excluded.confidence, affected_scope=excluded.affected_scope, "
                " affected_refs_json=excluded.affected_refs_json, "
                " labeled_by=excluded.labeled_by, collected_at=excluded.collected_at",
                (
                    it.url,
                    it.title,
                    it.source,
                    it.published_at,
                    it.body,
                    it.category,
                    it.time_axis,
                    it.direction,
                    it.magnitude,
                    it.confidence,
                    it.affected_scope,
                    json.dumps(it.affected_refs, ensure_ascii=False),
                    it.labeled_by,
                    it.collected_at,
                ),
            )
    log.info("news_items_upserted", count=len(items))
    return len(items)


def _row_to_news_item(row: Any) -> NewsItem:
    return NewsItem(
        title=row["title"],
        url=row["url"],
        source=row["source"] or "",
        published_at=row["published_at"],
        body=row["body"],
        category=row["category"],
        time_axis=row["time_axis"],
        direction=row["direction"],
        magnitude=row["magnitude"],
        confidence=row["confidence"],
        affected_scope=row["affected_scope"],
        affected_refs=json.loads(row["affected_refs_json"]) if row["affected_refs_json"] else [],
        labeled_by=row["labeled_by"],
        collected_at=row["collected_at"],
    )


def get_news_items(
    *,
    since: str | None = None,
    category: str | None = None,
    limit: int = 200,
) -> list[NewsItem]:
    """news_items 조회 (collected_at 최신순). since = ISO8601 하한(포함)."""
    db = get_db()
    clauses: list[str] = []
    params: list[Any] = []
    if since:
        clauses.append("collected_at >= ?")
        params.append(since)
    if category:
        clauses.append("category = ?")
        params.append(category)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(int(limit))
    rows = db.fetch_all(
        f"SELECT * FROM news_source_items{where} ORDER BY collected_at DESC LIMIT ?",
        tuple(params),
    )
    return [_row_to_news_item(r) for r in rows]


# ---------------------------------------------------------------------------
# DB — news_digest_snapshot ((scope, date) 멱등)
#   집계 로직(build_news_digest)은 MS-B. 여기선 영속 헬퍼만 (round-trip).
# ---------------------------------------------------------------------------
@dataclass
class NewsDigest:
    """build_news_digest 산출물 (MS-B 에서 집계 채움). MS-A 는 round-trip 골격만."""

    date: str
    scope: str  # "market" | "ticker:005930" | "sector:반도체"
    tone: str = "neutral"  # bearish|lean_bearish|neutral|lean_bullish|bullish
    category_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    top_themes: list[dict] = field(default_factory=list)
    catalyst_tilt: dict[str, str] = field(default_factory=dict)  # {direction, strength}
    raw_labels: str = ""
    source: str = "empty"  # db | computed | empty


def upsert_news_digest(digest: NewsDigest) -> None:
    """news_digest_snapshot ON CONFLICT(scope, date) REPLACE 멱등 upsert."""
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO news_digest_snapshot "
            "(scope, date, tone, category_counts_json, top_themes_json, "
            " catalyst_tilt_json, raw_labels, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(scope, date) DO UPDATE SET "
            " tone=excluded.tone, category_counts_json=excluded.category_counts_json, "
            " top_themes_json=excluded.top_themes_json, "
            " catalyst_tilt_json=excluded.catalyst_tilt_json, "
            " raw_labels=excluded.raw_labels, source=excluded.source",
            (
                digest.scope,
                digest.date,
                digest.tone,
                json.dumps(digest.category_counts, ensure_ascii=False),
                json.dumps(digest.top_themes, ensure_ascii=False),
                json.dumps(digest.catalyst_tilt, ensure_ascii=False),
                digest.raw_labels,
                # source 정직 저장 — 빈 집계는 'empty' 그대로 (미수집/neutral 구분).
                # get_news_digest 는 캐시 출처 마커로 'db' 를 반환하므로 소비자 분기 무영향.
                digest.source,
            ),
        )


def get_news_digest(scope: str, date: str) -> NewsDigest | None:
    """오늘 news_digest_snapshot row → NewsDigest(source='db'). 없으면 None."""
    db = get_db()
    row = db.fetch_one(
        "SELECT * FROM news_digest_snapshot WHERE scope = ? AND date = ?",
        (scope, date),
    )
    if row is None:
        return None
    return NewsDigest(
        date=row["date"],
        scope=row["scope"],
        tone=row["tone"] or "neutral",
        category_counts=json.loads(row["category_counts_json"]) if row["category_counts_json"] else {},
        top_themes=json.loads(row["top_themes_json"]) if row["top_themes_json"] else [],
        catalyst_tilt=json.loads(row["catalyst_tilt_json"]) if row["catalyst_tilt_json"] else {},
        raw_labels=row["raw_labels"] or "",
        source="db",
    )


def digest_to_dict(digest: NewsDigest) -> dict:
    """JSON round-trip helper (probe / 테스트)."""
    return asdict(digest)


# ===========================================================================
# MS-B — classify_news_items (개별 뉴스 LLM 라벨)
#   anchors.py::select_anchors_via_llm mirror: llm_call_cache 멱등 + thinking_budget=0
#   + JSON parse + 유효성 검증 + graceful 실패. provider=gemini 명시(Anthropic 미결제).
# ===========================================================================

_CLASSIFY_CONTRACT_VERSION = "1.0"
_CLASSIFY_CACHE_TYPE = "news_classify"

_VALID_DIRECTIONS = {"up", "neutral", "down"}
_VALID_SCOPES = {"market", "sector", "ticker"}


def _classify_cfg() -> dict[str, Any]:
    return (load_news_source_config().get("classify") or {})


def _classify_cache_key(url: str, title: str, model: str) -> str:
    """라벨 멱등 키 — url + 제목 + 모델 + 계약버전. 라벨은 불변이라 사실상 영속."""
    return f"{url}|{title}|{model}|{_CLASSIFY_CONTRACT_VERSION}"


def _get_cached_classification(input_hash: str, *, ttl_days: int) -> dict | None:
    """llm_call_cache type='news_classify' 조회 (anchors _get_cached_anchor mirror)."""
    db = get_db()
    row = db.fetch_one(
        "SELECT response_json, created_at FROM llm_call_cache "
        "WHERE input_hash = ? AND type = ?",
        (input_hash, _CLASSIFY_CACHE_TYPE),
    )
    if row is None:
        return None
    try:
        created = datetime.fromisoformat(row["created_at"])
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created > timedelta(days=ttl_days):
            return None
        return json.loads(row["response_json"])
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _store_cached_classification(
    input_hash: str,
    response: dict,
    *,
    model: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
    ttl_days: int = 365,
) -> None:
    """llm_call_cache 에 type='news_classify' 저장 (anchors _store_cached_anchor mirror)."""
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO llm_call_cache
                (input_hash, model, response_json, tokens_in, tokens_out, cost_usd, ttl_days, created_at, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(input_hash) DO UPDATE SET
                response_json = excluded.response_json,
                tokens_in     = excluded.tokens_in,
                tokens_out    = excluded.tokens_out,
                cost_usd      = excluded.cost_usd,
                created_at    = excluded.created_at,
                type          = excluded.type
            """,
            (
                input_hash,
                model,
                json.dumps(response, ensure_ascii=False),
                tokens_in,
                tokens_out,
                cost_usd,
                ttl_days,
                datetime.now(timezone.utc).isoformat(),
                _CLASSIFY_CACHE_TYPE,
            ),
        )


def _build_classify_prompt(item: NewsItem) -> str:
    """단일 뉴스 1건 분류 프롬프트. 본문 grounding 강제 (학습데이터 환각 차단)."""
    cfg = load_news_source_config()
    categories = ", ".join(cfg.get("categories") or [])
    time_axes = ", ".join(cfg.get("time_axes") or [])
    body = (item.body or "").strip()
    body_block = f"\n본문/요약:\n{body[:2000]}\n" if body else "\n(본문 없음 — 제목만으로 판단)\n"
    return f"""당신은 경제·증시 뉴스 분류자입니다. 아래 뉴스 1건을 분류하세요.
제목·본문에 실제로 담긴 내용으로만 판단하고, 학습 데이터의 추측을 더하지 마세요.

제목: {item.title}
출처: {item.source}{body_block}
분류 기준:
- category (택1): {categories}
- time_axis (택1): {time_axes}
  · ephemeral_shock = 당일~수일 단발 충격 / short_theme = ~1~2주 단기 테마 / structural_trend = 분기+ 지속 흐름
- direction: up | neutral | down (증시·해당 자산에 호재/중립/악재)
- magnitude: 1(약) | 2(중) | 3(강) — 시장 영향 크기
- confidence: 0~100 (이 분류에 대한 확신도)
- affected_scope: market(시장 전반) | sector(특정 섹터) | ticker(특정 종목)
- affected_refs: 영향받는 종목코드/섹터명 배열 (없으면 [])

JSON 형식으로만 응답 (다른 텍스트 금지):
{{
  "category": "<위 6개 중 1>",
  "time_axis": "<위 3개 중 1>",
  "direction": "up|neutral|down",
  "magnitude": <1|2|3>,
  "confidence": <0~100>,
  "affected_scope": "market|sector|ticker",
  "affected_refs": ["..."]
}}"""


def _validate_classification(result: Any) -> dict | None:
    """LLM 분류 응답 유효성 검증. 실패 시 None (graceful — item 미변경)."""
    if not isinstance(result, dict):
        return None
    cfg = load_news_source_config()
    categories = set(cfg.get("categories") or [])
    time_axes = set(cfg.get("time_axes") or [])
    category = result.get("category")
    time_axis = result.get("time_axis")
    direction = result.get("direction")
    if category not in categories or time_axis not in time_axes:
        return None
    if direction not in _VALID_DIRECTIONS:
        return None
    try:
        magnitude = int(result.get("magnitude"))
        confidence = int(result.get("confidence"))
    except (TypeError, ValueError):
        return None
    if magnitude not in (1, 2, 3):
        return None
    confidence = max(0, min(100, confidence))
    scope = result.get("affected_scope")
    if scope not in _VALID_SCOPES:
        scope = None
    refs = result.get("affected_refs")
    refs = [str(r) for r in refs] if isinstance(refs, list) else []
    return {
        "category": category,
        "time_axis": time_axis,
        "direction": direction,
        "magnitude": magnitude,
        "confidence": confidence,
        "affected_scope": scope,
        "affected_refs": refs,
    }


# ---------------------------------------------------------------------------
# affected_refs 정규화 (classify 시 캐노니컬화 — 조용한 누락 방지)
#   LLM 자유 텍스트 refs("삼성전자") ↔ universe ticker(6자리 "005930") 불일치 →
#   `"005930" in ["삼성전자"]` = False 로 종목 scope·on-demand buy_score N 누락.
#   classify 시 종목명→6자리 코드 / 섹터 표현→캐노니컬 풀네임 으로 박아 필터를 매칭.
#   미매칭 ref 는 원본 보존(drop 아님) — 재현/감사성 + 마스터 테이블 도입 시 재분류 안전판.
# ---------------------------------------------------------------------------
_TICKER_CODE_RE = re.compile(r"^\d{6}$")
_SECTOR_BRAND_TOKENS = {"KODEX", "TIGER", "ACE", "200"}


def _norm_key(s: str) -> str:
    """정규화 매칭 키 — 공백 제거 + 소문자 (영문 대소문자·공백 차이 흡수)."""
    return "".join(str(s).split()).lower()


def _build_sector_map() -> dict[str, str]:
    """DEFAULT_TRACKED_ETFS → {정규화키: 캐노니컬 풀네임}. 항상 결정론.

    키 = 풀네임("KODEX 반도체") + 브랜드 접두 제거 stem("반도체") + ETF ticker.
    값 = 캐노니컬 섹터명(풀네임) — sector_rs_snapshot.sector 저장값과 정합.
    같은 collectors 레이어 import (파이프라인 간 import 아님).
    """
    from collectors.kr_sectors import DEFAULT_TRACKED_ETFS

    mapping: dict[str, str] = {}
    for ticker, name in DEFAULT_TRACKED_ETFS:
        mapping.setdefault(_norm_key(name), name)
        mapping.setdefault(ticker.lower(), name)
        stem = " ".join(tok for tok in name.split() if tok not in _SECTOR_BRAND_TOKENS)
        if stem:
            mapping.setdefault(_norm_key(stem), name)
    return mapping


def _normalize_ticker_ref(ref: str, name_code_map: dict[str, str] | None) -> str | None:
    """종목 ref → 6자리 KRX 코드. 6자리 숫자는 통과, 종목명은 map 조회. 미스 None."""
    s = str(ref).strip()
    if _TICKER_CODE_RE.match(s):
        return s
    if name_code_map:
        return name_code_map.get(_norm_key(s))
    return None


def _normalize_sector_ref(ref: str, sector_map: dict[str, str]) -> str | None:
    """섹터 ref → 캐노니컬 풀네임. 미스 None."""
    return sector_map.get(_norm_key(ref))


def _normalize_affected_refs(
    refs: list[str],
    scope: str | None,
    *,
    name_code_map: dict[str, str] | None,
    sector_map: dict[str, str],
) -> list[str]:
    """affected_refs 캐노니컬화 — scope 힌트로 종목/섹터 해소, 미스는 원본 보존.

    종목 → 6자리 코드, 섹터 → 풀네임. dedup(순서 보존, name+code 는 code 로 수렴).
    scope=None/market 은 종목 우선 후 섹터 시도. 결정론(백테스팅 재현).
    """
    out: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        if scope == "sector":
            canon = _normalize_sector_ref(ref, sector_map)
        elif scope == "ticker":
            canon = _normalize_ticker_ref(ref, name_code_map)
        else:  # market / None — 종목 먼저, 실패 시 섹터
            canon = _normalize_ticker_ref(ref, name_code_map) or _normalize_sector_ref(ref, sector_map)
        final = canon if canon is not None else str(ref).strip()
        if final and final not in seen:
            seen.add(final)
            out.append(final)
    return out


def _apply_classification(
    item: NewsItem,
    labels: dict,
    *,
    name_code_map: dict[str, str] | None = None,
    sector_map: dict[str, str] | None = None,
) -> None:
    """검증된 라벨을 NewsItem 에 적용. 수동 입력 affected_* 는 보존 (LLM 미덮어쓰기).

    LLM 가 추정한 affected_refs 는 캐노니컬화(종목명→코드/섹터→풀네임)하여 적용 —
    수동 refs 는 보존 가드 안에서만 변환하므로 사람 입력은 미변경.
    """
    item.category = labels["category"]
    item.time_axis = labels["time_axis"]
    item.direction = labels["direction"]
    item.magnitude = labels["magnitude"]
    item.confidence = labels["confidence"]
    # 수동 자료원이 이미 박은 영향 범위는 보존 (사람 입력 우선)
    if not item.affected_scope:
        item.affected_scope = labels["affected_scope"]
    if not item.affected_refs:
        smap = sector_map if sector_map is not None else _build_sector_map()
        item.affected_refs = _normalize_affected_refs(
            labels["affected_refs"],
            labels["affected_scope"],
            name_code_map=name_code_map,
            sector_map=smap,
        )
    item.labeled_by = "llm"


async def _classify_one(
    item: NewsItem, *, model: str, provider: str | None, max_tokens: int,
    ttl_days: int, skip_cache: bool,
    name_code_map: dict[str, str] | None = None,
    sector_map: dict[str, str] | None = None,
) -> NewsItem:
    """단일 뉴스 분류 — 캐시 → LLM → 검증 → 적용. 실패 시 item 미변경 (graceful).

    name_code_map/sector_map 는 affected_refs 캐노니컬화에 쓰임 (캐시·LLM 양 경로 동일 적용).
    """
    input_hash = hashlib.sha256(
        _classify_cache_key(item.url, item.title, model).encode("utf-8")
    ).hexdigest()

    if not skip_cache:
        cached = _get_cached_classification(input_hash, ttl_days=ttl_days)
        if cached is not None:
            labels = _validate_classification(cached)
            if labels is not None:
                _apply_classification(
                    item, labels, name_code_map=name_code_map, sector_map=sector_map
                )
            return item

    try:
        resp = await call_llm(
            call_type="news_classify",
            system="You are a deterministic news classifier. Output only valid JSON.",
            messages=[{"role": "user", "content": _build_classify_prompt(item)}],
            model=model,
            provider=provider,
            max_tokens=max_tokens,
            temperature=0.0,
            # Gemini-2.5 thinking 비활성 — thinking 토큰이 max_output 예산을 잠식해
            # JSON 이 잘리던 결함 방지 ([[feedback_gemini_thinking_budget_json]]).
            thinking_budget=0,
        )
        labels = _validate_classification(parse_json_response(resp.get("content", "")))
    except Exception as e:  # noqa: BLE001 — 한 건 실패가 전체를 막지 않음
        log.warning("news_classify_failed", url=item.url, error_type=type(e).__name__, error=str(e))
        return item

    if labels is None:
        log.info("news_classify_invalid", url=item.url)
        return item

    _apply_classification(item, labels, name_code_map=name_code_map, sector_map=sector_map)
    if not skip_cache:
        _store_cached_classification(
            input_hash,
            labels,
            model=resp.get("model", model),
            tokens_in=int(resp.get("tokens_in", 0)),
            tokens_out=int(resp.get("tokens_out", 0)),
            cost_usd=float(resp.get("cost_usd", 0.0)),
            ttl_days=ttl_days,
        )
    return item


async def classify_news_items(
    items: list[NewsItem],
    *,
    model: str | None = None,
    provider: str | None = None,
    skip_cache: bool = False,
    name_code_map: dict[str, str] | None = None,
    sector_map: dict[str, str] | None = None,
) -> list[NewsItem]:
    """개별 뉴스에 LLM 분류 라벨 부여 (in-place + 반환). M4: 판단=LLM.

    각 item 을 category/time_axis/direction/magnitude/confidence/affected 로 라벨링하고
    `labeled_by='llm'` 표시. 실패 item 은 기존 라벨(rss_raw/manual) 유지 (graceful).
    캐시: llm_call_cache type='news_classify' url 멱등 (라벨 불변 → 영속 TTL).

    Args:
        items: 라벨 미부여(또는 재분류) NewsItem 목록.
        model: LLM 모델. None 시 config classify.model → call_llm 기본.
        provider: LLM 백엔드. None 시 config classify.provider (기본 gemini).
        skip_cache: True 면 캐시 bypass (테스트용).
        name_code_map: {종목명: 6자리코드} — affected_refs 캐노니컬화용 (키는 내부 정규화).
            None 이면 6자리 숫자 ref 만 통과(종목명 미해소). 보통 news_ingest 가 주입.
        sector_map: 섹터 정규화 맵. None 이면 DEFAULT_TRACKED_ETFS 로 자동 구성.

    Returns:
        라벨이 채워진 같은 NewsItem 목록 (분류 성공분만 labeled_by='llm').
    """
    if not items:
        return items
    cfg = _classify_cfg()
    model = model or cfg.get("model") or "gemini-2.5-flash"
    provider = provider if provider is not None else cfg.get("provider")
    max_tokens = int(cfg.get("max_tokens", 512))
    ttl_days = int(cfg.get("cache_ttl_days", 365))

    # 맵은 묶음당 1회 구성 (per-item 재구성 회피). 주입 name_code_map 키는 정규화.
    if sector_map is None:
        sector_map = _build_sector_map()
    norm_name_code_map = (
        {_norm_key(k): v for k, v in name_code_map.items()} if name_code_map else None
    )

    results = await asyncio.gather(
        *[
            _classify_one(
                it, model=model, provider=provider, max_tokens=max_tokens,
                ttl_days=ttl_days, skip_cache=skip_cache,
                name_code_map=norm_name_code_map, sector_map=sector_map,
            )
            for it in items
        ]
    )
    labeled = sum(1 for it in results if it.labeled_by == "llm")
    log.info("news_classified", total=len(results), labeled=labeled)
    return list(results)


# ===========================================================================
# MS-B — build_news_digest (결정론 집계)
#   M4: 집계=결정론. 정밀 점수 폐기 → tone 5단 tilt + category_counts + top_themes
#   + catalyst_tilt + raw_labels. 같은 라벨 묶음 → 같은 산출 (백테스팅 재현).
# ===========================================================================

def _digest_cfg() -> dict[str, Any]:
    return (load_news_source_config().get("digest") or {})


def digest_scope_universe_limit() -> int:
    """종목 scope 다일 누적 상한 (거래대금 상위 N). 부재 시 50."""
    try:
        return int(_digest_cfg().get("scope_universe_limit", 50))
    except (TypeError, ValueError):
        return 50


def digest_persist_empty_scopes() -> bool:
    """빈 종목/섹터 scope 도 영속할지 (기본 True — '미수집' vs 'neutral' 구분)."""
    return bool(_digest_cfg().get("persist_empty_scopes", True))


def _item_signed_weight(item: NewsItem) -> tuple[float, float]:
    """(signed, weight) — weight = magnitude × confidence/100, 부호 = direction."""
    mag = item.magnitude if item.magnitude in (1, 2, 3) else 1
    conf = item.confidence if isinstance(item.confidence, int) else 50
    weight = mag * (max(0, min(100, conf)) / 100.0)
    sign = {"up": 1.0, "down": -1.0}.get(item.direction or "neutral", 0.0)
    return sign * weight, weight


def _net_tilt(items: list[NewsItem]) -> float:
    """Σ(signed weight) / Σ(weight) → [-1, 1]. 라벨 없는 항목은 weight≈0 영향."""
    total_signed = 0.0
    total_weight = 0.0
    for it in items:
        signed, weight = _item_signed_weight(it)
        total_signed += signed
        total_weight += weight
    if total_weight <= 0:
        return 0.0
    return max(-1.0, min(1.0, total_signed / total_weight))


def _tone_from_net(net: float) -> str:
    """net tilt [-1,1] → 5단 tone (config 임계)."""
    bands = _digest_cfg().get("tone_bands") or {}
    bearish = float(bands.get("bearish", -0.50))
    lean_bearish = float(bands.get("lean_bearish", -0.15))
    lean_bullish = float(bands.get("lean_bullish", 0.15))
    bullish = float(bands.get("bullish", 0.50))
    if net <= bearish:
        return "bearish"
    if net <= lean_bearish:
        return "lean_bearish"
    if net < lean_bullish:
        return "neutral"
    if net < bullish:
        return "lean_bullish"
    return "bullish"


def _catalyst_strength(net: float) -> str:
    """|net tilt| → weak/mid/strong (config 임계)."""
    cs = _digest_cfg().get("catalyst_strength") or {}
    mid = float(cs.get("mid", 0.30))
    strong = float(cs.get("strong", 0.60))
    a = abs(net)
    if a >= strong:
        return "strong"
    if a >= mid:
        return "mid"
    return "weak"


def _category_counts(items: list[NewsItem]) -> dict[str, dict[str, int]]:
    """{category: {up, neutral, down}} — 방향별 카운트 (라벨 있는 항목만)."""
    counts: dict[str, dict[str, int]] = {}
    for it in items:
        if not it.category:
            continue
        direction = it.direction if it.direction in _VALID_DIRECTIONS else "neutral"
        bucket = counts.setdefault(it.category, {"up": 0, "neutral": 0, "down": 0})
        bucket[direction] += 1
    return counts


def _theme_key(item: NewsItem) -> str | None:
    """테마 클러스터 키 = 첫 affected_ref (종목/섹터) 우선, 없으면 category."""
    if item.affected_refs:
        return str(item.affected_refs[0])
    return item.category


def _top_themes(items: list[NewsItem], *, n: int, titles_n: int) -> list[dict]:
    """동일 테마(affected_ref/category) 클러스터 상위 N. time_axis = 최빈값."""
    groups: dict[str, list[NewsItem]] = defaultdict(list)
    for it in items:
        key = _theme_key(it)
        if key:
            groups[key].append(it)
    # 큰 클러스터 우선, 동률은 키 이름 (결정론 — 백테스팅 재현)
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    themes: list[dict] = []
    for key, members in ordered[:n]:
        axis_counts: dict[str, int] = defaultdict(int)
        for m in members:
            if m.time_axis:
                axis_counts[m.time_axis] += 1
        time_axis = (
            max(sorted(axis_counts.items()), key=lambda kv: kv[1])[0]
            if axis_counts else None
        )
        themes.append({
            "theme": key,
            "time_axis": time_axis,
            "trigger_titles": [m.title for m in members[:titles_n]],
        })
    return themes


def _raw_labels(items: list[NewsItem]) -> str:
    """LLM 주입용 분류 텍스트 묶음 — 한 줄/뉴스. 라벨 없으면 (미분류) 표시."""
    lines: list[str] = []
    for it in items:
        if it.category:
            tag = f"[{it.category}/{it.time_axis}] {it.direction}(강도{it.magnitude},확신{it.confidence}%)"
        else:
            tag = "[미분류]"
        lines.append(f"- {tag} {it.title}")
    return "\n".join(lines)


def _filter_items_for_scope(
    items: list[NewsItem], *, ticker: str | None, sector: str | None
) -> list[NewsItem]:
    """scope 별 필터 — ticker/sector 는 affected_refs 멤버십. market 은 전체."""
    if ticker:
        return [it for it in items if ticker in (it.affected_refs or [])]
    if sector:
        return [it for it in items if sector in (it.affected_refs or [])]
    return items


def build_news_digest(
    date: str,
    *,
    ticker: str | None = None,
    sector: str | None = None,
    persist: bool = True,
) -> NewsDigest:
    """date(KST 'YYYY-MM-DD') 의 뉴스 거친 종합 — 단일 산출물 (M5).

    scope: ticker 주면 'ticker:<code>'(해당 종목 뉴스), sector 주면 'sector:<name>',
    둘 다 없으면 'market'(전체). 결정론 집계 (M4): tone 5단 + category_counts +
    top_themes + catalyst_tilt + raw_labels. 빈 입력 → source='empty', tone='neutral'.

    Args:
        date: 집계 대상 날짜 (collected_at 또는 published_at 의 날짜부 일치).
        ticker / sector: scope 좁히기 (affected_refs 멤버십).
        persist: True 면 news_digest_snapshot 멱등 upsert.

    Returns:
        NewsDigest. 소비자(market_view·buy_score·news_curator)는 이 단일 산출물 read.
    """
    if ticker:
        scope = f"ticker:{ticker}"
    elif sector:
        scope = f"sector:{sector}"
    else:
        scope = "market"

    cfg = _digest_cfg()
    lookback = int(cfg.get("lookback_limit", 500))
    # 날짜부 일치로 필터 (collected_at 우선, 없으면 published_at)
    candidates = get_news_items(limit=lookback)
    on_date = [
        it for it in candidates
        if (it.collected_at or "")[:10] == date or (it.published_at or "")[:10] == date
    ]
    scoped = _filter_items_for_scope(on_date, ticker=ticker, sector=sector)

    if not scoped:
        digest = NewsDigest(date=date, scope=scope, tone="neutral", source="empty")
        if persist:
            upsert_news_digest(digest)
        return digest

    net = _net_tilt(scoped)
    digest = NewsDigest(
        date=date,
        scope=scope,
        tone=_tone_from_net(net),
        category_counts=_category_counts(scoped),
        top_themes=_top_themes(
            scoped,
            n=int(cfg.get("top_themes_n", 3)),
            titles_n=int(cfg.get("trigger_titles_n", 3)),
        ),
        catalyst_tilt={
            "direction": "up" if net > 0 else "down" if net < 0 else "neutral",
            "strength": _catalyst_strength(net),
        },
        raw_labels=_raw_labels(scoped),
        source="computed",
    )
    if persist:
        upsert_news_digest(digest)
    return digest


# ===========================================================================
# MS-B — render_news_digest_md ([8] 주입 블록)
#   render_market_view_md house style mirror. news_curator system prompt 주입용.
# ===========================================================================

_TONE_KR = {
    "bearish": "약세 (악재 우세)",
    "lean_bearish": "약세 기울기",
    "neutral": "중립",
    "lean_bullish": "강세 기울기",
    "bullish": "강세 (호재 우세)",
}
_CATEGORY_KR = {
    "macro_policy": "거시·통화·재정",
    "industry_trend": "산업 흐름",
    "geopolitics": "지정학",
    "policy_political": "정치·정책",
    "corporate_events": "기업 이벤트",
    "market_sentiment": "시장심리",
}
_TIME_AXIS_KR = {
    "ephemeral_shock": "단발 충격",
    "short_theme": "단기 테마",
    "structural_trend": "지속 흐름",
}
_STRENGTH_KR = {"weak": "약", "mid": "중", "strong": "강"}


def render_news_digest_md(digest: NewsDigest) -> str:
    """`[8] 뉴스 종합` 블록 — news_curator system prompt 주입.

    M4 정합: tone 은 거친 5단 tilt (정밀 점수 아님) — 본문에 명시.
    환각 가드: source 항상 노출 (computed / db / empty).
    """
    lines: list[str] = []
    lines.append("## [8] 뉴스 종합 (NEWS-SOURCE-001)")
    lines.append("")
    tone_kr = _TONE_KR.get(digest.tone, digest.tone)
    lines.append(
        f"**날짜**: {digest.date} | **범위(scope)**: {digest.scope} | "
        f"**톤(tone)**: {tone_kr} (`{digest.tone}`) | **출처**: `{digest.source}`"
    )

    if digest.source == "empty":
        lines.append("")
        lines.append("_해당 날짜·범위에 분류된 뉴스 없음 — 톤 중립._")
        return "\n".join(lines)

    if digest.category_counts:
        lines.append("")
        lines.append("**카테고리별 방향 카운트** (호재/중립/악재):")
        lines.append("| 카테고리 | 호재 | 중립 | 악재 |")
        lines.append("|---|---|---|---|")
        for cat, c in digest.category_counts.items():
            cat_kr = _CATEGORY_KR.get(cat, cat)
            lines.append(f"| {cat_kr} | {c.get('up', 0)} | {c.get('neutral', 0)} | {c.get('down', 0)} |")

    if digest.top_themes:
        lines.append("")
        lines.append("**주요 테마**:")
        for t in digest.top_themes:
            axis_kr = _TIME_AXIS_KR.get(t.get("time_axis"), t.get("time_axis") or "?")
            titles = " / ".join(t.get("trigger_titles") or [])
            lines.append(f"- {t.get('theme')} ({axis_kr}): {titles}")

    if digest.catalyst_tilt:
        d = digest.catalyst_tilt.get("direction", "neutral")
        s = _STRENGTH_KR.get(digest.catalyst_tilt.get("strength"), digest.catalyst_tilt.get("strength", "?"))
        lines.append("")
        lines.append(f"**촉매 기울기(catalyst tilt)**: {d} (강도 {s})")

    if digest.raw_labels:
        lines.append("")
        lines.append("**분류된 뉴스 (raw)**:")
        lines.append(digest.raw_labels)

    lines.append("")
    lines.append(
        "_tone·catalyst_tilt 는 **거친 5단 tilt** (정밀 점수 아님 — 뉴스는 상황의존·비선형이라 "
        "단일 점수로 누르지 않음). 방향·강도 라벨은 개별 뉴스 LLM 판단의 결정론 집계._"
    )
    return "\n".join(lines)


def news_digest_metadata(digest: NewsDigest) -> dict[str, Any]:
    """run_analyst metadata 노출용 (MS-C hook 에서 사용)."""
    return {
        "news_digest": {
            "date": digest.date,
            "scope": digest.scope,
            "tone": digest.tone,
            "catalyst_tilt": digest.catalyst_tilt,
            "top_themes": [t.get("theme") for t in digest.top_themes],
            "source": digest.source,
        }
    }
