"""Wealth API — 복리 자산 곡선 + 목표 진척 (WEALTH-COMPOUND-TRACKER-001 RB-MS4).

Endpoints:
  GET /api/wealth/curve?account_id=     — 자산 곡선 시계열 (4계좌 통합 또는 계좌별)
  GET /api/wealth/progress              — 복리 목표(연 18%) 대비 진척 + MDD + 벤치마크

가상매매 스냅샷 기반. webapp `/자산` · 텔레그램 `/wealth` 동일 소비.
"""
from __future__ import annotations

from fastapi import APIRouter

from core.account.compounding import get_compound_progress, get_equity_curve
from core.logging import get_logger

log = get_logger(__name__)

router = APIRouter()


@router.get("/wealth/curve")
async def wealth_curve(account_id: str | None = None) -> dict:
    """자산 곡선 (account_equity_snapshot 시계열)."""
    return get_equity_curve(account_id=account_id)


@router.get("/wealth/progress")
async def wealth_progress() -> dict:
    """복리 목표 진척 (목표곡선 vs 실제 + MDD + 벤치마크 알파)."""
    return get_compound_progress()
