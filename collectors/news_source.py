"""NEWS-SOURCE-001 — 뉴스부 자료층 (MS-A 데이터 백본).

자료원 어댑터(NewsSource) + news_items / news_digest_snapshot DB 영속.

설계 (SPEC 결단):
  - M1: 기존 RSS(fetch_news) 를 RssNewsSource 어댑터 첫 구현체로 흡수 (중복 X, 승격).
        자료원에 코드 비종속 → 교체 자유. ManualNewsSource = 본문·유튜브 요약 직접 입력.
        PerplexityNewsSource = 인터페이스만 (이 환경 MCP 미연결 — drop-in SLOT).
  - M2: DB=사실(news_items 시계열) / canon=분류룰 (얕게, MS-B).
  - MVP(MS-A): 어댑터 + DB 영속(url 멱등) 까지. 분류(classify_news_items) · 집계
        (build_news_digest) · 소비 배선은 MS-B/MS-C.

크로스플랫폼: pathlib 전용. 멱등: url PK (news_items) / (scope, date) PK (digest).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml

from collectors.news_rss import NewsItem, fetch_news_items
from core.db.connection import get_db
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
                "computed" if digest.source == "empty" else digest.source,
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
