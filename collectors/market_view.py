"""시장관 종합 collector — MARKET-VIEW-SYNTHESIS-001 (LB-MS2).

왼쪽 뇌의 비어 있던 "시장 종합 판단" 한 겹. 섹터 RS·regime·매크로를 결정론으로
종합해 **순환매 방향 + 진입 자세**를 한 산출물(MarketView)로 묶는다.

흐름:
  1. `build_market_view(market)` — DB-first hybrid (market_view_snapshot 오늘 row 즉시 반환).
  2. 없으면:
     a. `compute_market_macro` → `classify_market_regime` (결정론 6단계).
     b. `load_sector_rs_snapshot(today)` 또는 `compute_sector_rs` + persist (섹터 RS).
     c. `load_prev_sector_rs(window_days)` — 순환매 다일 비교 기준.
     d. `synthesize_market_view(...)` — 결정론 종합 (leading/fading/rotation Stage1/entry_posture/one_liner).
     e. (M2) rotation Stage 2 LLM 크로스체크 — `cross_check_rotation_via_llm` 으로 검증·보정.
     f. `market_view_snapshot` upsert.
  3. formatter 가 `one_liner` 를 모든 답변 머리에 prepend (M2 토글).
  4. market_state_analyzer 가 `render_market_view_md` 를 read 해서 해석.

순환매 본질: *이동*. 어제 대비가 아니라 **N일 윈도우 변화**로 single-day overfitting 회피
([[feedback_backtest_essence]]). 결정론 후보 + LLM 크로스체크로 환각·하루치오해 양쪽 차단
([[feedback_llm_intuition_distribution]], WAVE-ALPHA anchor 패턴 mirror).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from collectors.market_macro import classify_market_regime, compute_market_macro
from collectors.sector_rs import (
    SectorRS,
    compute_sector_rs,
    load_prev_sector_rs,
    load_sector_rs_snapshot,
    persist_sector_rs,
)
from core.db import get_db
from core.llm.client import call_llm, parse_json_response
from core.logging import get_logger

log = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")
REPO_ROOT = Path(__file__).resolve().parents[1]
MARKET_VIEW_PATH = REPO_ROOT / "config" / "market_view.yaml"

# regime → 한국어 (one_liner / md). market_state_analyzer 톤 정합.
_REGIME_KR: dict[str, str] = {
    "parabolic": "과열(폭주)",
    "strong_bull": "강한 강세",
    "moderate_bull": "완만한 강세",
    "sideways": "횡보",
    "moderate_bear": "약세",
    "strong_bear": "강한 약세",
}
_POSTURE_KR: dict[str, str] = {
    "aggressive": "공격",
    "neutral": "중립",
    "defensive": "방어",
}

_DEFAULT_CONFIG: dict[str, Any] = {
    "rotation": {
        "window_days": 5,
        "leading_top_n": 3,
        "in_threshold": 0.5,
        "out_threshold": 0.5,
        "strong_change": 1.5,
    },
    "entry_posture": {
        "kill_switch_dd": 4,
        "ceiling_dd": 5,
        "breadth_strong": 0.55,
    },
    "cross_check": {"enabled": True, "provider": "gemini", "model": "gemini-2.5-flash-lite", "ttl_days": 1},
    "prepend": {"enabled": True},
    "sector_labels": {},
}

_CONFIG_CACHE: dict[str, Any] | None = None


def load_market_view_config() -> dict[str, Any]:
    """config/market_view.yaml 로드 (캐시). 부재·파싱 실패 시 default 병합."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        cfg = dict(_DEFAULT_CONFIG)
        if MARKET_VIEW_PATH.exists():
            try:
                loaded = yaml.safe_load(MARKET_VIEW_PATH.read_text(encoding="utf-8")) or {}
                for key, default_block in _DEFAULT_CONFIG.items():
                    if isinstance(default_block, dict):
                        cfg[key] = {**default_block, **(loaded.get(key) or {})}
                    else:
                        cfg[key] = loaded.get(key, default_block)
            except Exception as e:  # noqa: BLE001
                log.warning("market_view_config_load_failed", error=str(e))
        else:
            log.warning("market_view_config_missing", path=str(MARKET_VIEW_PATH))
        _CONFIG_CACHE = cfg
    return _CONFIG_CACHE


def reload_market_view_config() -> None:
    """테스트/hot reload — 캐시 클리어."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None


# ---------------------------------------------------------------------------
# DataClass
# ---------------------------------------------------------------------------


@dataclass
class Rotation:
    """순환매 판단 (결정론 다일 후보 ⨯ LLM 크로스체크)."""

    direction: str                       # "2차전지→방산" | "반도체 유입" | "—"
    from_sectors: list[str] = field(default_factory=list)
    to_sectors: list[str] = field(default_factory=list)
    strength: str = "none"               # "strong" | "mild" | "none"
    method: str = "deterministic"        # "deterministic" | "hybrid"
    agreement: str = "n/a"               # "agree" | "disagree" | "n/a"


@dataclass
class MarketView:
    """시장관 종합 산출물 — market-view-v1 계약."""

    date: str
    market: str
    regime: str
    leading_sectors: list[dict[str, Any]]
    fading_sectors: list[dict[str, Any]]
    rotation: Rotation
    entry_posture: str                   # "aggressive" | "neutral" | "defensive"
    one_liner: str
    confidence: int
    reasons: list[str] = field(default_factory=list)
    source: str = "computed"             # "db" | "computed" | "stale"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Pure helpers — 결정론, 단위 테스트 가능
# ---------------------------------------------------------------------------


def _mget(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _sector_label(etf_ticker: str, fallback: str, config: dict[str, Any]) -> str:
    """ETF ticker → 사용자 친화 섹터명. 미매칭 시 ETF 원명(fallback).

    SectorRS.sector 는 "TIGER 200 금융" 같은 브랜드명이라 답변엔 "금융" 이 자연스럽다.
    """
    labels = config.get("sector_labels") or {}
    return str(labels.get(etf_ticker) or fallback)


def entry_posture(
    regime: str,
    breadth_ratio: float | None,
    distribution_count: int | None,
    *,
    config: dict[str, Any] | None = None,
) -> str:
    """진입 자세 결정론 — "지금 들어갈 때냐".

    우선순위:
      1. 분산일(DD) kill switch ≥ → defensive 강제 (market_state_analyzer 정합).
      2. 천장/하락 체제(parabolic, *_bear) → defensive.
      3. 강세 체제 + 폭 강함 + 분산일 적음 → aggressive.
      4. 그 외(sideways/폭 약한 강세) → neutral.
    """
    cfg = (config or load_market_view_config()).get("entry_posture", {})
    kill = int(cfg.get("kill_switch_dd", 4))
    ceiling = int(cfg.get("ceiling_dd", 5))
    breadth_strong = float(cfg.get("breadth_strong", 0.55))
    dd = int(distribution_count or 0)

    if dd >= kill:
        return "defensive"
    if regime in ("parabolic", "moderate_bear", "strong_bear"):
        return "defensive"
    if regime in ("strong_bull", "moderate_bull"):
        if breadth_ratio is not None and breadth_ratio >= breadth_strong and dd < ceiling:
            return "aggressive"
        return "neutral"
    return "neutral"  # sideways / unknown


def _base_confidence(regime: str) -> int:
    """체제 결정성 기반 base confidence (rotation 크로스체크 전)."""
    if regime in ("parabolic", "strong_bull", "strong_bear"):
        return 70
    if regime in ("moderate_bull", "moderate_bear"):
        return 60
    return 50  # sideways = 모호


def build_rotation_stage1(
    today_rs: list[SectorRS],
    prev_rs: list[SectorRS] | None,
    *,
    config: dict[str, Any] | None = None,
) -> tuple[Rotation, dict[str, float | None]]:
    """Stage 1 결정론 순환매 후보 (다일 RS 변화 기반).

    Returns:
        (Rotation, {sector → rs_change_nd or None}) — change map 은 leading/fading 표기용.
    """
    cfg = (config or load_market_view_config()).get("rotation", {})
    in_th = float(cfg.get("in_threshold", 0.5))
    out_th = float(cfg.get("out_threshold", 0.5))
    strong = float(cfg.get("strong_change", 1.5))
    top_n = int(cfg.get("leading_top_n", 3))

    if not prev_rs:
        # 첫날/이력 부족 — 추정 금지 (graceful).
        return Rotation(direction="—", strength="none", method="deterministic", agreement="n/a"), {}

    cfg_full = config or load_market_view_config()
    # 매칭 = etf_ticker(섹터 정체성). 라벨도 ticker 기준 → 매칭·표기 완전 일관.
    prev_map = {r.etf_ticker: r.rs_score for r in prev_rs}
    changes: list[tuple[str, float]] = []  # (clean_label, delta)
    change_map: dict[str, float | None] = {}  # clean_label → delta (사용자·LLM 표기 일관)
    for r in today_rs:
        label = _sector_label(r.etf_ticker, r.sector, cfg_full)
        if r.etf_ticker in prev_map:
            delta = round(r.rs_score - prev_map[r.etf_ticker], 2)
            changes.append((label, delta))
            change_map[label] = delta
        else:
            change_map[label] = None

    if not changes:
        return Rotation(direction="—", strength="none", method="deterministic", agreement="n/a"), change_map

    to_list = [s for s, d in sorted(changes, key=lambda c: c[1], reverse=True) if d >= in_th][:top_n]
    from_list = [s for s, d in sorted(changes, key=lambda c: c[1]) if d <= -out_th][:top_n]
    max_abs = max(abs(d) for _, d in changes)

    if to_list and from_list:
        direction = f"{from_list[0]}→{to_list[0]}"
    elif to_list:
        direction = f"{to_list[0]} 유입"
    elif from_list:
        direction = f"{from_list[0]} 유출"
    else:
        direction = "—"

    if direction == "—":
        strength = "none"
    elif max_abs >= strong:
        strength = "strong"
    else:
        strength = "mild"

    return (
        Rotation(
            direction=direction,
            from_sectors=from_list,
            to_sectors=to_list,
            strength=strength,
            method="deterministic",
            agreement="n/a",
        ),
        change_map,
    )


def _sector_entries(
    rs_list: list[SectorRS],
    change_map: dict[str, float | None],
    *,
    top_n: int,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """leading_sectors 표기 — rs_score 상위 top_n (섹터명 = 친화 라벨)."""
    out: list[dict[str, Any]] = []
    for r in rs_list[:top_n]:
        label = _sector_label(r.etf_ticker, r.sector, config)
        out.append({
            "sector": label,
            "rs_score": r.rs_score,
            "rs_change_nd": change_map.get(label),
        })
    return out


def _fading_entries(
    rs_list: list[SectorRS],
    change_map: dict[str, float | None],
    *,
    top_n: int,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """fading_sectors — rs_change_nd < 0 인 섹터를 가장 많이 떨어진 순으로."""
    labeled = [(r, _sector_label(r.etf_ticker, r.sector, config)) for r in rs_list]
    falling = [
        (r, label) for r, label in labeled
        if change_map.get(label) is not None and change_map[label] < 0  # type: ignore[operator]
    ]
    falling.sort(key=lambda rl: change_map[rl[1]])  # type: ignore[index]
    return [
        {"sector": label, "rs_score": r.rs_score, "rs_change_nd": change_map.get(label)}
        for r, label in falling[:top_n]
    ]


def build_one_liner(
    regime: str,
    leading_sectors: list[dict[str, Any]],
    rotation: Rotation,
    posture: str,
) -> str:
    """formatter prepend용 결정론 한 줄. 빈 축 생략 (ANSWER-FIDELITY F2 정신)."""
    parts = [f"오늘 시장: {_REGIME_KR.get(regime, regime)}"]
    if leading_sectors:
        parts.append(f"주도 {leading_sectors[0]['sector']}")
    if rotation.strength != "none" and rotation.direction != "—":
        parts.append(f"순환 {rotation.direction}")
    parts.append(f"진입 {_POSTURE_KR.get(posture, posture)}")
    return " · ".join(parts)


# NEWS-SOURCE-001 MS-C C2 — 시장 전반 뉴스 톤 한국어 (one_liner / reason 흡수)
_NEWS_TONE_KR = {
    "bearish": "악재 우세",
    "lean_bearish": "약세 기울기",
    "neutral": "중립",
    "lean_bullish": "강세 기울기",
    "bullish": "호재 우세",
}


def synthesize_market_view(
    macro: Any,
    today_rs: list[SectorRS],
    prev_rs: list[SectorRS] | None,
    *,
    market: str,
    date_str: str,
    config: dict[str, Any] | None = None,
    news_digest: Any = None,
) -> MarketView:
    """결정론 종합 (Stage 1) — LLM 없음. M2 크로스체크 전 baseline.

    Args:
        macro: MarketMacro 또는 dict (regime 분류 입력).
        today_rs: 오늘 섹터 RS (rs_score 내림차순 가정).
        prev_rs: N일 전 섹터 RS (순환매 비교 기준). None = 첫날 graceful.
        news_digest: 시장 scope NewsDigest (NEWS-SOURCE-001 M5). None/empty 면 흡수 생략.
    """
    cfg = config or load_market_view_config()
    top_n = int(cfg.get("rotation", {}).get("leading_top_n", 3))

    regime = classify_market_regime(macro)
    breadth = _mget(macro, "breadth_ratio")
    dd = _mget(macro, "distribution_count_25d")

    rotation, change_map = build_rotation_stage1(today_rs, prev_rs, config=cfg)
    leading = _sector_entries(today_rs, change_map, top_n=top_n, config=cfg)
    fading = _fading_entries(today_rs, change_map, top_n=top_n, config=cfg)
    posture = entry_posture(regime, breadth, dd, config=cfg)
    one_liner = build_one_liner(regime, leading, rotation, posture)

    reasons: list[str] = [
        f"체제 {_REGIME_KR.get(regime, regime)}(regime={regime}) → 진입 {_POSTURE_KR.get(posture, posture)}",
    ]
    if rotation.strength != "none":
        reasons.append(f"순환매 {rotation.direction} (강도={rotation.strength}, 검증={rotation.method})")
    else:
        reasons.append("순환매 판단 보류 (다일 누적 부족 또는 유의미한 이동 없음)")
    if dd is not None:
        reasons.append(f"분산일(25일) {int(dd)}건" + (" — kill switch 발동" if int(dd or 0) >= int(cfg.get("entry_posture", {}).get("kill_switch_dd", 4)) else ""))

    # C2 — 시장 전반 뉴스 톤 흡수 (NEWS-SOURCE-001 M5: 시장 뉴스 → 시장관 내러티브).
    if news_digest is not None and getattr(news_digest, "source", "empty") != "empty":
        tone = getattr(news_digest, "tone", "neutral")
        tone_kr = _NEWS_TONE_KR.get(tone, tone)
        themes = getattr(news_digest, "top_themes", None) or []
        theme_part = (
            " · 테마 " + ", ".join(str(t.get("theme")) for t in themes[:2]) if themes else ""
        )
        reasons.append(f"뉴스 톤 {tone_kr}(tone={tone}){theme_part}")
        if tone in ("bullish", "bearish", "lean_bullish", "lean_bearish"):
            one_liner = f"{one_liner} · 뉴스 {tone_kr}"

    return MarketView(
        date=date_str,
        market=market,
        regime=regime,
        leading_sectors=leading,
        fading_sectors=fading,
        rotation=rotation,
        entry_posture=posture,
        one_liner=one_liner,
        confidence=_base_confidence(regime),
        reasons=reasons,
        source="computed",
    )


# ---------------------------------------------------------------------------
# DB layer — market_view_snapshot
# ---------------------------------------------------------------------------


def _row_to_view(row: Any) -> MarketView:
    rot_raw = json.loads(row["rotation_json"]) if row["rotation_json"] else {}
    rotation = Rotation(
        direction=rot_raw.get("direction", "—"),
        from_sectors=rot_raw.get("from_sectors", []),
        to_sectors=rot_raw.get("to_sectors", []),
        strength=rot_raw.get("strength", "none"),
        method=rot_raw.get("method", "deterministic"),
        agreement=rot_raw.get("agreement", "n/a"),
    )
    return MarketView(
        date=row["date"],
        market=row["market"],
        regime=row["regime"] or "sideways",
        leading_sectors=json.loads(row["leading_json"]) if row["leading_json"] else [],
        fading_sectors=json.loads(row["fading_json"]) if row["fading_json"] else [],
        rotation=rotation,
        entry_posture=row["entry_posture"] or "neutral",
        one_liner=row["one_liner"] or "",
        confidence=int(row["confidence"]) if row["confidence"] is not None else 50,
        reasons=json.loads(row["reasons_json"]) if row["reasons_json"] else [],
        source="db",
    )


def get_cached_one_liner(market: str = "KOSPI", date_str: str | None = None) -> str | None:
    """formatter prepend용 — 오늘 시장관 한 줄 (DB 캐시 read only, LLM·계산 0).

    답변 시점 비용 0 보장: 빌드(build_market_view)를 트리거하지 않고 적재된 스냅샷만 읽는다.
    prepend 비활성 / 오늘 스냅샷 부재 시 None (답변 막지 않음 — 일1회 refresh 가 적재).
    """
    if not load_market_view_config().get("prepend", {}).get("enabled", True):
        return None
    date_str = date_str or _today_kst_str()
    try:
        view = get_today_view(date_str, market.upper())
    except Exception:  # noqa: BLE001 — DB 부재 환경에서도 답변 막지 않음
        return None
    return view.one_liner if view and view.one_liner else None


def get_today_view(date_str: str, market: str) -> MarketView | None:
    """오늘 market_view_snapshot row → MarketView(source='db'). 없으면 None."""
    db = get_db()
    row = db.fetch_one(
        "SELECT * FROM market_view_snapshot WHERE date = ? AND market = ?",
        (date_str, market),
    )
    return _row_to_view(row) if row is not None else None


def upsert_market_view(view: MarketView) -> None:
    """market_view_snapshot ON CONFLICT REPLACE 멱등 upsert."""
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO market_view_snapshot "
            "(date, market, regime, leading_json, fading_json, rotation_json, "
            " entry_posture, one_liner, confidence, reasons_json, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(date, market) DO UPDATE SET "
            " regime=excluded.regime, leading_json=excluded.leading_json, "
            " fading_json=excluded.fading_json, rotation_json=excluded.rotation_json, "
            " entry_posture=excluded.entry_posture, one_liner=excluded.one_liner, "
            " confidence=excluded.confidence, reasons_json=excluded.reasons_json, "
            " source=excluded.source",
            (
                view.date,
                view.market,
                view.regime,
                json.dumps(view.leading_sectors, ensure_ascii=False),
                json.dumps(view.fading_sectors, ensure_ascii=False),
                json.dumps(asdict(view.rotation), ensure_ascii=False),
                view.entry_posture,
                view.one_liner,
                view.confidence,
                json.dumps(view.reasons, ensure_ascii=False),
                "computed",
            ),
        )


def _today_kst_str() -> str:
    return datetime.now(_KST).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Async public API
# ---------------------------------------------------------------------------


async def build_market_view(
    market: str = "KOSPI",
    *,
    force_refresh: bool = False,
    cross_check: bool = True,
) -> MarketView:
    """시장관 종합 — DB-first hybrid.

    Args:
        market: 현재 KOSPI 만 (KOSDAQ 확장 SLOT).
        force_refresh: True 면 DB hit 무시 재계산.
        cross_check: rotation Stage 2 LLM 크로스체크 수행 여부 (M2). 기본 True.

    Returns:
        MarketView. 섹터 RS / regime 부재 시도 부분 발행.
    """
    market = market.upper()
    today = _today_kst_str()

    if not force_refresh:
        cached = get_today_view(today, market)
        if cached is not None:
            return cached

    macro = await compute_market_macro(market)

    today_rs = load_sector_rs_snapshot(today, market)
    if not today_rs:
        today_rs = await compute_sector_rs()
        if today_rs:
            try:
                persist_sector_rs(today, market, today_rs)
            except Exception as e:  # pragma: no cover
                log.warning("sector_rs_persist_failed", market=market, error=str(e))

    cfg = load_market_view_config()
    window = int(cfg.get("rotation", {}).get("window_days", 5))
    prev = load_prev_sector_rs(today, market, window_days=window)
    prev_rs = prev[1] if prev else None

    # C2 — 시장 전반 뉴스 digest (graceful, persist=False — 소비 read 용. 영속은 뉴스 파이프라인 책임).
    news_digest = None
    try:
        from collectors.news_source import build_news_digest as _build_news_digest

        news_digest = _build_news_digest(today, persist=False)
    except Exception as e:  # noqa: BLE001
        log.warning("market_view_news_digest_failed", market=market, error=str(e))

    view = synthesize_market_view(
        macro, today_rs, prev_rs, market=market, date_str=today, config=cfg,
        news_digest=news_digest,
    )

    # M2 seam — rotation Stage 2 LLM 크로스체크 (cross_check_rotation_via_llm).
    if cross_check and cfg.get("cross_check", {}).get("enabled", True):
        try:
            view = await _apply_rotation_cross_check(view, prev_rs, today_rs, config=cfg)
        except Exception as e:  # noqa: BLE001 — 크로스체크 실패는 결정론 baseline 유지
            log.warning("rotation_cross_check_failed", market=market, error=str(e))

    try:
        upsert_market_view(view)
    except Exception as e:  # pragma: no cover
        log.warning("market_view_upsert_failed", market=market, error=str(e))

    return view


_CROSS_CHECK_MODEL_DEFAULT = "gemini-2.5-flash-lite"   # FAST tier (Anthropic 미결제 — Gemini 고정)
_CROSS_CHECK_PROVIDER_DEFAULT = "gemini"


def _rotation_cache_key(market: str, date_str: str, direction: str) -> str:
    """크로스체크 cache_key — market|date|direction (det 후보 바뀌면 캐시 무효)."""
    return f"{market}|{date_str}|{direction}"


def _get_cached_rotation(input_hash: str, *, ttl_days: int) -> dict | None:
    """llm_call_cache type='market_rotation' 조회 (anchor 캐싱 mirror). TTL 만료 시 None."""
    db = get_db()
    row = db.fetch_one(
        "SELECT response_json, created_at FROM llm_call_cache "
        "WHERE input_hash = ? AND type = 'market_rotation'",
        (input_hash,),
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


def _store_cached_rotation(
    input_hash: str, response: dict, *, model: str, ttl_days: int,
    tokens_in: int = 0, tokens_out: int = 0, cost_usd: float = 0.0,
) -> None:
    """llm_call_cache 에 type='market_rotation' 저장 (anchor 캐싱 mirror)."""
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO llm_call_cache "
            "(input_hash, model, response_json, tokens_in, tokens_out, cost_usd, ttl_days, created_at, type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'market_rotation') "
            "ON CONFLICT(input_hash) DO UPDATE SET "
            " response_json=excluded.response_json, model=excluded.model, "
            " tokens_in=excluded.tokens_in, tokens_out=excluded.tokens_out, "
            " cost_usd=excluded.cost_usd, created_at=excluded.created_at, type='market_rotation'",
            (
                input_hash, model, json.dumps(response, ensure_ascii=False),
                tokens_in, tokens_out, cost_usd, ttl_days,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def _format_rotation_prompt(
    rotation: Rotation, change_map: dict[str, float | None], window_days: int
) -> str:
    """LLM 입력 — 결정론 순환매 후보 + 다일 RS 변화 표. LLM 은 검증(agree/disagree)만."""
    rows = ["sector | rs_change_Nd", "-------|-------------"]
    for sector, change in sorted(
        ((s, c) for s, c in change_map.items() if c is not None),
        key=lambda x: x[1], reverse=True,
    ):
        rows.append(f"{sector} | {'+' if change >= 0 else ''}{change}")
    table = "\n".join(rows)
    return f"""당신은 국내 증시 순환매(sector rotation) 검증자입니다.
아래는 결정론 알고리즘이 최근 {window_days}거래일 섹터 상대강도(RS) 변화로 판정한 순환매 후보입니다.
이 판정이 데이터와 부합하는지 **검증만** 하세요. 새 섹터를 지어내지 마세요(표에 없는 섹터 금지).

결정론 후보:
- 방향: {rotation.direction}
- 자금 유입(to): {', '.join(rotation.to_sectors) or '없음'}
- 자금 유출(from): {', '.join(rotation.from_sectors) or '없음'}
- 강도: {rotation.strength}

{window_days}거래일 RS 변화:
```
{table}
```

판단 기준: 유입 섹터가 실제로 RS 가 오르고 유출 섹터가 내렸는가? 변화가 노이즈 수준은 아닌가?
JSON 으로만 응답 (다른 텍스트 금지):
{{
  "agree": <true|false>,
  "reasoning": "<한 문장 근거>"
}}"""


async def cross_check_rotation_via_llm(
    market: str,
    date_str: str,
    rotation: Rotation,
    change_map: dict[str, float | None],
    *,
    window_days: int,
    model: str = _CROSS_CHECK_MODEL_DEFAULT,
    provider: str | None = _CROSS_CHECK_PROVIDER_DEFAULT,
    ttl_days: int = 1,
    skip_cache: bool = False,
) -> dict | None:
    """Stage 2 — LLM 이 결정론 순환매 후보를 검증 (agree/disagree). 캐싱 일 1회.

    LLM 은 후보를 **생성하지 않고 검증만** 한다 (결정론 후보가 앵커 → 환각 차단).
    provider 명시(기본 gemini) — Anthropic 미결제 환경에서 폴백 차단.

    Returns:
        {"agree": bool, "reasoning": str} 또는 None (LLM 실패/무효 → 결정론 유지).
    """
    cache_key = _rotation_cache_key(market, date_str, rotation.direction)
    input_hash = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()

    if not skip_cache:
        cached = _get_cached_rotation(input_hash, ttl_days=ttl_days)
        if cached is not None:
            log.debug("rotation_cache_hit", market=market, date=date_str)
            return cached

    prompt = _format_rotation_prompt(rotation, change_map, window_days)
    try:
        resp = await call_llm(
            system="You are a deterministic sector-rotation verifier. Output only valid JSON.",
            messages=[{"role": "user", "content": prompt}],
            model=model,
            provider=provider,   # gemini 고정 (Anthropic 미결제 폴백 차단)
            max_tokens=512,
            temperature=0.0,
            thinking_budget=0,   # Gemini-2.5 thinking 예산 잠식 → JSON 잘림 방지 ([[feedback_gemini_thinking_budget_json]])
        )
        result = parse_json_response(resp.get("content", ""))
    except Exception as e:  # noqa: BLE001
        log.warning("rotation_llm_failed", market=market, error_type=type(e).__name__, error=str(e))
        return None

    if not isinstance(result, dict) or "agree" not in result:
        return None
    validated = {"agree": bool(result["agree"]), "reasoning": str(result.get("reasoning", ""))[:300]}

    if not skip_cache:
        _store_cached_rotation(
            input_hash, validated, model=model, ttl_days=ttl_days,
            tokens_in=int(resp.get("tokens_in", 0)), tokens_out=int(resp.get("tokens_out", 0)),
            cost_usd=float(resp.get("cost_usd", 0.0)),
        )
    return validated


async def _apply_rotation_cross_check(
    view: MarketView,
    prev_rs: list[SectorRS] | None,
    today_rs: list[SectorRS],
    *,
    config: dict[str, Any],
    skip_cache: bool = False,
) -> MarketView:
    """Stage 2 LLM 크로스체크를 결정론 baseline 에 적용.

    - 순환매 없음(strength=none) → skip (검증 대상 없음).
    - LLM 실패 → 결정론 유지 (method=deterministic, agreement=n/a).
    - agree → method=hybrid, agreement=agree, confidence +10.
    - disagree → method=hybrid, agreement=disagree, confidence -15, 근거에 LLM 이견 병기.
      (방향은 결정론 앵커 유지 — 은폐 X, agreement 로 노출.)
    """
    if view.rotation.strength == "none" or view.rotation.direction == "—":
        return view

    rot_cfg = config.get("rotation", {})
    cc_cfg = config.get("cross_check", {})
    window = int(rot_cfg.get("window_days", 5))
    model = str(cc_cfg.get("model", _CROSS_CHECK_MODEL_DEFAULT))
    provider = cc_cfg.get("provider", _CROSS_CHECK_PROVIDER_DEFAULT)
    ttl = int(cc_cfg.get("ttl_days", 1))

    # change_map 재구성 (synthesize 와 동일 — prev 대비 today 변화)
    _, change_map = build_rotation_stage1(today_rs, prev_rs, config=config)

    result = await cross_check_rotation_via_llm(
        view.market, view.date, view.rotation, change_map,
        window_days=window, model=model, provider=provider, ttl_days=ttl, skip_cache=skip_cache,
    )
    if result is None:
        return view  # LLM 불가 — 결정론 유지

    rotation = view.rotation
    rotation.method = "hybrid"
    reasons = list(view.reasons)
    confidence = view.confidence
    if result["agree"]:
        rotation.agreement = "agree"
        confidence = min(100, confidence + 10)
        reasons.append(f"순환매 LLM 크로스체크 일치 (신뢰도 +10): {result['reasoning']}")
    else:
        rotation.agreement = "disagree"
        confidence = max(0, confidence - 15)
        reasons.append(f"⚠ 순환매 결정론·LLM 이견 (신뢰도 -15): {result['reasoning']}")

    return MarketView(
        date=view.date, market=view.market, regime=view.regime,
        leading_sectors=view.leading_sectors, fading_sectors=view.fading_sectors,
        rotation=rotation, entry_posture=view.entry_posture, one_liner=view.one_liner,
        confidence=confidence, reasons=reasons, source="computed",
    )


# ---------------------------------------------------------------------------
# Render — [7] 시장관 블록 + metadata
# ---------------------------------------------------------------------------


def render_market_view_md(view: MarketView) -> str:
    """`[7] 시장관 종합` 블록 — market_state_analyzer system prompt 주입."""
    lines: list[str] = []
    lines.append("## [7] 시장관 종합 (MARKET-VIEW-SYNTHESIS-001)")
    lines.append("")
    lines.append(f"**시장**: {view.market} | **날짜**: {view.date} | **체제(regime)**: {_REGIME_KR.get(view.regime, view.regime)} (`{view.regime}`)")
    lines.append(f"**진입 자세**: {_POSTURE_KR.get(view.entry_posture, view.entry_posture)} (`{view.entry_posture}`) | **신뢰도**: {view.confidence}")
    if view.leading_sectors:
        lead = ", ".join(
            f"{s['sector']}(rs {s['rs_score']}{_fmt_change(s.get('rs_change_nd'))})"
            for s in view.leading_sectors
        )
        lines.append(f"**주도 섹터**: {lead}")
    if view.fading_sectors:
        fade = ", ".join(
            f"{s['sector']}(rs {s['rs_score']}{_fmt_change(s.get('rs_change_nd'))})"
            for s in view.fading_sectors
        )
        lines.append(f"**약화 섹터**: {fade}")
    r = view.rotation
    lines.append(
        f"**순환매**: {r.direction} (강도={r.strength}, 검증={r.method}/{r.agreement})"
    )
    if view.reasons:
        lines.append("")
        lines.append("**근거**:")
        for reason in view.reasons:
            lines.append(f"- {reason}")
    lines.append("")
    lines.append(f"_한 줄: {view.one_liner}_")
    lines.append(
        "_순환매 검증 = `deterministic`(다일 RS 변화) / `hybrid`(결정론⨯LLM 크로스체크). "
        "agreement=`disagree` 면 결정론·LLM 판단이 갈린 것 — 신뢰도 하향._"
    )
    return "\n".join(lines)


def _fmt_change(change: float | None) -> str:
    if change is None:
        return ""
    sign = "+" if change >= 0 else ""
    return f", {sign}{change}"


def market_view_metadata(view: MarketView) -> dict[str, Any]:
    """run_analyst metadata 노출용 시장관 풀세트."""
    return {
        "market_view": {
            "date": view.date,
            "market": view.market,
            "regime": view.regime,
            "entry_posture": view.entry_posture,
            "rotation_direction": view.rotation.direction,
            "rotation_strength": view.rotation.strength,
            "rotation_method": view.rotation.method,
            "rotation_agreement": view.rotation.agreement,
            "leading_sectors": [s["sector"] for s in view.leading_sectors],
            "one_liner": view.one_liner,
            "confidence": view.confidence,
            "source": view.source,
        }
    }
