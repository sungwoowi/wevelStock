"""Market snapshot API — 시황 집계 read + 시점 히스토리 (PAPER-DESK-UX-001 RB-MS5).

Endpoints:
  GET /api/market/snapshot[?run_id=&pipeline_id=]
      — run_id 없으면 현재(라이브 DB-first) 집계 / 있으면 그 시점 스냅샷 재조립
  GET /api/market/history[?limit=8]
      — 최근 시점(브리핑 런) 목록 (장전/장개시/장중/장마감) — LNB 히스토리용

결정론 read 전용 — LLM 호출 0. 라이브는 `build_market_snapshot()`(DB-first),
과거 시점은 `briefing_parts`(run_id별) + date-keyed getter 로 point-in-time 재조립.
섹션별 partial 허용 — 미수집은 null/빈값, 크래시 0 (graceful empty).
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter

from collectors.market_macro import _get_today_macro
from collectors.market_view import get_today_view
from collectors.sector_rs import load_sector_rs_snapshot
from collectors.snapshot import (
    _adapt_kr_indices_from_part,
    _adapt_kr_leading_from_part,
    _adapt_kr_supply_sectors_from_part,
    _adapt_overnight_from_part,
    _find_part_data,
    _macro_to_dict,
    _sector_rs_to_dict,
    build_market_snapshot,
)
from collectors.us_macro import get_today_us_macro
from core.briefing import parts_store
from core.logging import get_logger

log = get_logger(__name__)

router = APIRouter()

_KST = ZoneInfo("Asia/Seoul")
_WD_KR = ["월", "화", "수", "목", "금", "토", "일"]
# 시황 히스토리 대상 파이프라인 (시점들)
_BRIEFING_PIPELINES = ("market_briefing_pre", "market_briefing_now")


# ── 공통 helper ──────────────────────────────────────────────────────────────
def _market_view_block(date_str: str) -> dict | None:
    """그 날짜 KOSPI MarketView (regime·entry_posture·one_liner). 없으면 None."""
    try:
        mv = get_today_view(date_str, "KOSPI")
    except Exception as exc:  # pragma: no cover — DB read 안전망
        log.warning("market_view_read_failed", error=str(exc))
        return None
    return mv.to_dict() if mv is not None else None


def _us_macro_block(date_str: str) -> dict | None:
    """그 날짜 us_macro 스냅샷 (야간자산 WTI·브렌트·NQ·ES 포함). 없으면 None."""
    try:
        um = get_today_us_macro(date_str)
    except Exception as exc:  # pragma: no cover
        log.warning("us_macro_read_failed", error=str(exc))
        return None
    return asdict(um) if um is not None else None


def _night_futures_from_parts(parts: list) -> dict | None:
    """overnight 파트의 night_futures (KOSPI200 야간선물). 없으면 None."""
    ov = _find_part_data(parts, "overnight")
    if isinstance(ov, dict):
        nf = ov.get("night_futures")
        if nf:
            return nf
    return None


def _latest_night_futures() -> dict | None:
    """최신 market_briefing_pre 의 night_futures (라이브용 DB-first)."""
    try:
        res = parts_store.get_latest_parts_with_age("market_briefing_pre")
        if not res:
            return None
        _, parts, _ = res
        return _night_futures_from_parts(parts)
    except Exception as exc:  # pragma: no cover
        log.warning("night_futures_read_failed", error=str(exc))
    return None


def _parse_run_dt(run_id: str) -> datetime | None:
    """run_id 의 ISO 타임스탬프 prefix → KST datetime. 파싱 실패 시 None."""
    iso = run_id.split("#", 1)[0]
    try:
        return datetime.fromisoformat(iso).astimezone(_KST)
    except (ValueError, TypeError):
        return None


def _run_label(pipeline_id: str, dt_kst: datetime | None) -> str:
    """시점 라벨 (장전/장개시/장중/장마감)."""
    if pipeline_id == "market_briefing_pre":
        return "장전(간밤)"
    if dt_kst is None:
        return "시황"
    h = dt_kst.hour
    if h < 11:
        return "장개시"
    if h < 14:
        return "장중"
    if h < 16:
        return "장마감"
    return "마감후"


def _run_time_label(dt_kst: datetime | None, label: str) -> str:
    """'6/13 (금) 09:30 · 장개시' 형태."""
    if dt_kst is None:
        return label
    wd = _WD_KR[dt_kst.weekday()]
    return f"{dt_kst.month}/{dt_kst.day} ({wd}) {dt_kst.hour:02d}:{dt_kst.minute:02d} · {label}"


# ── 파트 → 버킷 어댑터 (라이브 어댑터 재사용) ───────────────────────────────
def _apply_now_parts(parts: list, bucket: dict) -> None:
    mo = _find_part_data(parts, "market_overview")
    if mo is not None:
        bucket["kr_indices"] = _adapt_kr_indices_from_part(mo)
    ss = _find_part_data(parts, "supply_sectors")
    if ss is not None:
        sup, fut, sec = _adapt_kr_supply_sectors_from_part(ss)
        bucket["kr_supply"] = sup
        bucket["kr_futures_supply"] = fut
        bucket["kr_sectors"] = sec
    ls = _find_part_data(parts, "leading_stocks")
    if ls is not None:
        bucket["kr_leading"] = _adapt_kr_leading_from_part(ls)


def _apply_pre_parts(parts: list, bucket: dict) -> None:
    ov = _find_part_data(parts, "overnight")
    if ov is not None:
        overnight, fear_greed = _adapt_overnight_from_part(ov)
        bucket["overnight"] = overnight
        bucket["fear_greed"] = fear_greed
        nf = _night_futures_from_parts(parts)
        if nf:
            bucket["night_futures"] = nf


def _build_historical(pipeline_id: str, run_id: str) -> dict | None:
    """특정 브리핑 런 → point-in-time 시황 dict (라이브 응답과 동일 키). 없으면 None.

    그 런의 파트(자기 시장) + 직전 반대 파이프라인 런(상대 시장) + 그 날짜 date-keyed
    (market_macro breadth·sector_rs·us_macro·market_view) 로 재조립. fetch 없음·DB-only.
    """
    parts = parts_store.get_parts_by_run(pipeline_id, run_id)
    if not parts:
        return None
    dt_kst = _parse_run_dt(run_id)
    date_str = dt_kst.date().isoformat() if dt_kst else datetime.now(_KST).date().isoformat()
    cutoff = run_id.split("#", 1)[0]

    bucket: dict[str, Any] = {
        "kr_indices": {}, "overnight": {}, "fear_greed": {}, "kr_supply": {},
        "kr_futures_supply": {}, "kr_sectors": {}, "kr_leading": {}, "night_futures": None,
    }

    if pipeline_id == "market_briefing_now":
        _apply_now_parts(parts, bucket)
        pre = parts_store.get_last_run_before("market_briefing_pre", cutoff)
        if pre is not None:
            _apply_pre_parts(pre[1], bucket)
    elif pipeline_id == "market_briefing_pre":
        _apply_pre_parts(parts, bucket)
        now = parts_store.get_last_run_before("market_briefing_now", cutoff)
        if now is not None:
            _apply_now_parts(now[1], bucket)

    # date-keyed (breadth·sector RS)
    market_macro: dict[str, Any] = {}
    for market in ("KOSPI", "KOSDAQ"):
        try:
            mm = _get_today_macro(date_str, market)
        except Exception:  # pragma: no cover
            mm = None
        if mm is not None:
            market_macro[market] = _macro_to_dict(mm)
    try:
        sector_rs = [_sector_rs_to_dict(r) for r in load_sector_rs_snapshot(date_str, "KOSPI")]
    except Exception:  # pragma: no cover
        sector_rs = []

    return {
        "fetched_at_iso": dt_kst.isoformat(timespec="seconds") if dt_kst else None,
        "cache_hit": False,
        "run_id": run_id,
        "pipeline_id": pipeline_id,
        "is_historical": True,
        "source_map": {"historical": pipeline_id},
        "db_age_seconds": {},
        "kr_indices": bucket["kr_indices"],
        "overnight": bucket["overnight"],
        "fear_greed": bucket["fear_greed"],
        "market_macro": market_macro,
        "kr_supply": bucket["kr_supply"],
        "kr_supply_60d": {},
        "kr_futures_supply": bucket["kr_futures_supply"],
        "kr_sectors": bucket["kr_sectors"],
        "sector_rs": sector_rs,
        "kr_leading": bucket["kr_leading"],
        "us_macro": _us_macro_block(date_str),
        "night_futures": bucket["night_futures"],
        "market_view": _market_view_block(date_str),
        "failures": [],
        "snapshot_extend_failures": [],
    }


# ── 엔드포인트 ───────────────────────────────────────────────────────────────
@router.get("/market/snapshot")
async def market_snapshot(run_id: str | None = None, pipeline_id: str | None = None) -> dict:
    """시황 집계 (market-snapshot-v1).

    run_id 없으면 현재(라이브 DB-first) — LLM 0.
    run_id 있으면 그 시점(브리핑 런) point-in-time 재조립.
    """
    if run_id:
        pid = pipeline_id or "market_briefing_now"
        hist = _build_historical(pid, run_id)
        if hist is not None:
            return hist
        # 파트 없음 → 라이브로 폴백 (graceful)

    today = datetime.now(_KST).date().isoformat()
    snap, cache_hit = await build_market_snapshot()

    return {
        "fetched_at_iso": snap.fetched_at_iso,
        "cache_hit": cache_hit,
        "is_historical": False,
        "source_map": snap.source_map,
        "db_age_seconds": snap.db_age_seconds,
        "kr_indices": snap.kr_indices,
        "overnight": snap.overnight,
        "fear_greed": snap.fear_greed,
        "market_macro": snap.market_macro,
        "kr_supply": snap.kr_supply,
        "kr_supply_60d": snap.kr_supply_60d,
        "kr_futures_supply": snap.kr_futures_supply,
        "kr_sectors": snap.kr_sectors,
        "sector_rs": snap.sector_rs,
        "kr_leading": snap.kr_leading,
        "us_macro": _us_macro_block(today),
        "night_futures": _latest_night_futures(),
        "market_view": _market_view_block(today),
        "failures": snap.failures,
        "snapshot_extend_failures": snap.snapshot_extend_failures,
    }


def _run_summary(pipeline_id: str, parts: list) -> str:
    """시점 카드 2번째 줄 요약 (그 런의 핵심 한 줄)."""
    if pipeline_id == "market_briefing_now":
        mo = _find_part_data(parts, "market_overview")
        idx = (mo or {}).get("indices") or {}
        kospi = idx.get("kospi") if isinstance(idx, dict) else None
        if isinstance(kospi, dict) and isinstance(kospi.get("change_pct"), (int, float)):
            chg = kospi["change_pct"]
            return f"코스피 {chg:+.2f}%"
        return "한국 정규장 시황"
    ov = _find_part_data(parts, "overnight")
    if isinstance(ov, dict):
        us = ov.get("overnight_us") or {}
        nas = us.get("nasdaq") if isinstance(us, dict) else None
        if isinstance(nas, dict) and isinstance(nas.get("change_pct"), (int, float)):
            return f"간밤 나스닥 {nas['change_pct']:+.2f}%"
    return "간밤 미국 시황"


@router.get("/market/history")
async def market_history(limit: int = 8) -> dict:
    """최근 시점(브리핑 런) 목록 — LNB 히스토리. 최신 DESC."""
    per = max(2, min(limit, 12))
    rows: list[dict[str, Any]] = []
    for pid in _BRIEFING_PIPELINES:
        try:
            runs = parts_store.get_recent_runs(pid, per)
        except Exception as exc:  # pragma: no cover
            log.warning("history_runs_failed", pipeline=pid, error=str(exc))
            continue
        for run_id, _ts, parts in runs:
            dt = _parse_run_dt(run_id)
            label = _run_label(pid, dt)
            rows.append({
                "run_id": run_id,
                "pipeline_id": pid,
                "kst_iso": dt.isoformat(timespec="minutes") if dt else None,
                "sort_key": dt.timestamp() if dt else 0.0,
                "label": label,
                "time_label": _run_time_label(dt, label),
                "summary": _run_summary(pid, parts),
            })
    rows.sort(key=lambda r: r["sort_key"], reverse=True)
    items = [{k: v for k, v in r.items() if k != "sort_key"} for r in rows[:limit]]
    return {"items": items}
