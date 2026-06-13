"""Accounts API — 가상 4계좌 상태 + 보유현황 조회 (PAPER-TRADING-001 RB-MS2).

Endpoints:
  GET /api/accounts                     — 4계좌 정의 + 현 비중·여력
  GET /api/accounts/{account_id}/holdings — 계좌 보유·평가손익·보유기간 + 요약

가상(페이퍼) 전용 — 실 KIS 잔고 아님. webapp `/계좌` · 텔레그램 `/계좌` 가 동일 소비.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.account.desk_view import (
    get_account_closed,
    get_account_pending,
    get_position_tranches,
)
from core.account.holdings import get_holdings
from core.account.portfolio import get_account, get_account_state, load_accounts
from core.logging import get_logger

log = get_logger(__name__)

router = APIRouter()


@router.get("/accounts")
async def list_accounts() -> dict:
    """4계좌 정의 + 현 누적 비중·잔여 여력 (가상)."""
    items = []
    for a in load_accounts():
        st = get_account_state(a.account_id)
        items.append({
            "account_id": a.account_id,
            "label": a.label,
            "market": a.market,
            "track": a.track,
            "horizon": a.horizon,
            "seed_krw": a.seed_krw,
            "deployed_weight": st.deployed_weight,
            "trading_deployed_weight": st.trading_deployed_weight,
            "available_weight": max(0.0, 1.0 - st.deployed_weight),
            "deployed_krw": st.deployed_weight * a.seed_krw,
        })
    return {"items": items}


@router.get("/accounts/{account_id}/holdings")
async def account_holdings(account_id: str) -> dict:
    """계좌 보유현황 + 평가/실현손익 요약 + 회차내역·매수대기·청산 (계좌 상세 화면).

    holdings[*].tranches = 회차별 체결(filled)+미체결 사다리(pending). pending = 매수대기.
    closed = 이익실현(청산). 전부 기존 테이블 read (PAPER-DESK-UX-001).
    """
    account = get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"account '{account_id}' 없음")
    holdings = get_holdings(account_id)
    for h in holdings:
        h["tranches"] = get_position_tranches(account_id, h["ticker"], account=account)
    unrealized = sum(h["unrealized_pnl_krw"] for h in holdings)
    realized = sum(h["realized_pnl_krw"] for h in holdings)
    return {
        "account_id": account_id,
        "holdings": holdings,
        "pending": get_account_pending(account_id),
        "closed": get_account_closed(account_id),
        "summary": {
            "position_count": len(holdings),
            "unrealized_pnl_krw": unrealized,
            "realized_pnl_krw": realized,
            "total_pnl_krw": unrealized + realized,
            "any_unpriced": any(not h["priced"] for h in holdings),
        },
    }
