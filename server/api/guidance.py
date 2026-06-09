"""Guidance API — 가이던스 적중도 KPI + 회고 (GUIDANCE-ACCURACY-TRACKER-001 RB-MS3).

Endpoints:
  GET /api/guidance/kpi?track=&period_days=          — guidance-kpi-v1 집계
  GET /api/guidance/retrospective?track=&period_days= — 집계 + 회고 텍스트

가상매매(account_fills) 기반. webapp `/회고` · 텔레그램 `/retro` 가 동일 소비.
"""
from __future__ import annotations

from fastapi import APIRouter

from core.guidance.kpi import get_kpi_summary
from core.guidance.retrospective import render_retrospective
from core.logging import get_logger

log = get_logger(__name__)

router = APIRouter()


@router.get("/guidance/kpi")
async def guidance_kpi(track: str | None = None, period_days: int = 90) -> dict:
    """청산된 권고 KPI 집계 (실현수익률·벤치마크 초과·적중률·R/R·트랙분리)."""
    return get_kpi_summary(track=track, period_days=period_days)


@router.get("/guidance/retrospective")
async def guidance_retrospective(track: str | None = None, period_days: int = 90) -> dict:
    """KPI 집계 + 사람 친화 회고 텍스트."""
    summary = get_kpi_summary(track=track, period_days=period_days)
    return {"summary": summary, "text": render_retrospective(summary)}
