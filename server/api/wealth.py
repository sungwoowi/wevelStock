"""Wealth API — 자산 곡선 + 성장 목표 진척 (WEALTH-COMPOUND-TRACKER-001 RB-MS4).

워딩 주의: "복리" 는 지식부 자산복리부(박종훈 거시 frame) 용어 — 본 API 는 성과 측정이라
"자산 곡선/자산 성장" 으로 표기한다 (2026-06-10 정체성 분리).

Endpoints:
  GET /api/wealth/curve?account_id=     — 자산 곡선 시계열 (4계좌 통합 또는 계좌별)
  GET /api/wealth/progress              — 성장 목표(연 18%) 대비 진척 + MDD + 벤치마크

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
    """성장 목표 진척 (목표곡선 vs 실제 + MDD + 벤치마크 알파)."""
    return get_compound_progress()
