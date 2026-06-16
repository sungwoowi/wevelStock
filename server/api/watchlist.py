"""관심종목 API — 체계적 종목 관리 (TRADE-PLAN-LIFECYCLE 후속).

Endpoints:
  GET /api/watchlist/funnel — 두 큐레이션 리스트(거래대금 상위 / 거래량 양봉) × 단계(관심·매수대기·진입)

기존 테이블(universe_membership ⋈ team_outputs) read 조립 — `core/watchlist_view.py` 위임(api 얇게).
가상(페이퍼) 전용. webapp `/watchlist` 페이지가 소비.
"""
from __future__ import annotations

from fastapi import APIRouter

from core.logging import get_logger
from core.watchlist_view import watchlist_funnel_view

log = get_logger(__name__)

router = APIRouter()


@router.get("/watchlist/funnel")
async def watchlist_funnel(limit: int = 50, within_days: int = 30) -> dict:
    """관심종목 funnel — 리스트별 → 단계별(진입▸매수대기▸관심) 그룹."""
    return watchlist_funnel_view(limit=limit, within_days=within_days)
