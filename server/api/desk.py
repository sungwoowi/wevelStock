"""Desk API — 가상매매 데스크 하단 피드 (PAPER-DESK-UX-001 RB-MS5).

Endpoints:
  GET /api/desk/feed — 지금 지켜보는 권고(활성) + 매매 일지(최근 체결·청산)

기존 테이블(team_outputs·account_fills) read 조립 — `core/account/desk_view.py` 위임(api 얇게).
가상(페이퍼) 전용. webapp `/desk` 하단 2칼럼이 소비.
"""
from __future__ import annotations

from fastapi import APIRouter

from core.account.desk_view import active_recommendations_view, recent_fills
from core.logging import get_logger

log = get_logger(__name__)

router = APIRouter()


@router.get("/desk/feed")
async def desk_feed(within_days: int = 30, fills_limit: int = 12) -> dict:
    """활성 권고 + 최근 체결 일지 (데스크 하단 2칼럼)."""
    return {
        "active_recommendations": active_recommendations_view(within_days=within_days),
        "recent_fills": recent_fills(limit=fills_limit),
    }
