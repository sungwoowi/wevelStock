"""데스크 UI read view 조립 — PAPER-DESK-UX-001 (RB-MS5).

가상매매 데스크(`/desk`)·계좌 상세(`/desk/[id]`) 화면이 소비하는 **read-only** 뷰.
기존 테이블(`account_fills`·`account_positions`·`team_outputs`)만 read·계산 — 신규 테이블 0
(CLAUDE.md 절대원칙 #11, [[feedback_reuse_first_guard]]). LLM·네트워크 0(시세는 holdings DB-first 재사용).

- 회차 내역: `account_fills` buy leg(체결) + 원안 사다리(`size_position` 재산출) 미체결 = pending.
- 매수 대기: 보유 포지션 미체결 사다리 + 활성 권고 중 관망(verdict≠buy).
- 체결 일지: `account_fills` 최신 N행.
산정·체결은 데스크 엔진(`desk.py`)이 소유 — 본 모듈은 그 결과를 *읽어 보여줄* 뿐(복사 0).
"""
from __future__ import annotations

from datetime import date
from typing import Any

from core.account.desk import _default_market_context
from core.account.holdings import get_holdings
from core.account.paper_trading import compute_tranche_ladder
from core.account.portfolio import get_account
from core.account.sizing import AccountState, size_position
from core.db import get_db
from core.logging import get_logger
from core.strategist.recommendation import (
    StrategistRecommendation,
    load_active_recommendations,
    load_recommendation,
)

log = get_logger(__name__)


def _market_of(ticker: str) -> str:
    """6자리 숫자 = 국장(KR), 그 외 = 미장(US)."""
    return "KR" if ticker.isdigit() and len(ticker) == 6 else "US"


def _planned_ladder(rec: StrategistRecommendation, account: Any) -> list[dict[str, Any]]:
    """권고 원안 분할 사다리(신규 진입 가정 = state 0) → leg별 지정가·배분·자본.

    state 0 으로 산출 → 이미 열린 포지션 비중이 deployment_cap 을 잠식하지 않게(원안 = 무엇이 계획됐나).
    blocked·미actionable → 빈 리스트(graceful).
    """
    if not rec.is_actionable or account is None:
        return []
    posture, extreme = _default_market_context(date.today().isoformat())
    sizing = size_position(
        recommendation=rec.to_recommendation_dict(),
        account=account,
        state=AccountState(account_id=account.account_id),
        entry_posture=posture,
        extension=None,  # 종목별 과열도 주입은 후속 SLOT (중립 분할)
        extreme=extreme,
    )
    if sizing.blocked or not sizing.tranches:
        return []
    ladder = compute_tranche_ladder(rec.entry_price, rec.stop_loss, len(sizing.tranches))
    return [
        {"leg": t.index, "limit_price": ladder[t.index - 1], "value_krw": t.value_krw, "ratio": t.ratio}
        for t in sizing.tranches
    ]


def _buy_fills(account_id: str, ticker: str) -> list[dict[str, Any]]:
    rows = get_db().fetch_all(
        "SELECT leg, fill_price, shares, value_krw, reason, filled_date, recommendation_id "
        "FROM account_fills WHERE account_id = ? AND ticker = ? AND side = 'buy' ORDER BY leg",
        (account_id, ticker),
    )
    return [dict(r) for r in rows]


def get_position_tranches(account_id: str, ticker: str, *, account: Any = None) -> dict[str, Any]:
    """한 포지션의 회차별 체결(filled) + 미체결 사다리(pending) + 손절선.

    filled = `account_fills` buy leg. pending = 원안 사다리(`_planned_ladder`) 중 미체결 leg.
    """
    account = account or get_account(account_id)
    buys = _buy_fills(account_id, ticker)
    filled_legs = {b["leg"] for b in buys}
    filled = [
        {
            "leg": b["leg"], "fill_price": b["fill_price"], "shares": b["shares"],
            "value_krw": b["value_krw"], "filled_date": b["filled_date"], "reason": b["reason"],
        }
        for b in buys
    ]
    rec_id = buys[0]["recommendation_id"] if buys else None
    rec = load_recommendation(rec_id) if rec_id else None
    stop_loss = rec.stop_loss if rec is not None else None
    pending = [p for p in _planned_ladder(rec, account) if p["leg"] not in filled_legs] if rec else []
    return {
        "ticker": ticker,
        "recommendation_id": rec_id,
        "stop_loss": stop_loss,
        "filled": filled,
        "pending": pending,
    }


def get_account_pending(account_id: str) -> dict[str, Any]:
    """매수 대기 — 보유 포지션 미체결 사다리(ladder_waiting) + 활성 권고 관망(watching).

    ladder_waiting: 보유 종목 미체결 차수 + 미보유 actionable 권고의 원안 전 차수.
    watching: 활성 권고 중 verdict≠buy(관망/기다림), 계좌 시장·트랙, 미보유.
    """
    account = get_account(account_id)
    if account is None:
        return {"ladder_waiting": [], "watching": []}

    holdings = get_holdings(account_id)
    held = {h["ticker"] for h in holdings}
    ladder_waiting: list[dict[str, Any]] = []
    for h in holdings:
        tr = get_position_tranches(account_id, h["ticker"], account=account)
        for p in tr["pending"]:
            ladder_waiting.append({"ticker": h["ticker"], "display_name": "", **p})

    watching: list[dict[str, Any]] = []
    for rec in load_active_recommendations():
        if rec.track != account.track or _market_of(rec.ticker) != account.market or rec.ticker in held:
            continue
        if rec.is_actionable:  # 미보유 진입 대기 → 원안 사다리 노출
            for p in _planned_ladder(rec, account):
                ladder_waiting.append({"ticker": rec.ticker, "display_name": rec.display_name, **p})
        else:  # 관망/기다림
            watching.append({
                "ticker": rec.ticker, "display_name": rec.display_name,
                "verdict": rec.verdict, "reason": (rec.reasons[0] if rec.reasons else ""),
            })
    return {"ladder_waiting": ladder_waiting, "watching": watching}


def get_account_closed(account_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """이익실현(청산 내역) — `account_fills` sell 행 최신순 (이 계좌)."""
    rows = get_db().fetch_all(
        "SELECT ticker, leg, fill_price, shares, value_krw, reason, realized_pnl_krw, filled_date "
        "FROM account_fills WHERE account_id = ? AND side = 'sell' "
        "ORDER BY filled_date DESC, created_at DESC LIMIT ?",
        (account_id, limit),
    )
    return [dict(r) for r in rows]


def recent_fills(*, limit: int = 12) -> list[dict[str, Any]]:
    """매매 일지 — 전 계좌 `account_fills` 최신 N행 (체결·청산)."""
    rows = get_db().fetch_all(
        "SELECT recommendation_id, account_id, ticker, track, side, leg, fill_price, shares, "
        "value_krw, reason, realized_pnl_krw, filled_date "
        "FROM account_fills ORDER BY filled_date DESC, created_at DESC LIMIT ?",
        (limit,),
    )
    return [dict(r) for r in rows]


def active_recommendations_view(*, within_days: int = 30) -> list[dict[str, Any]]:
    """지금 지켜보는 권고 — 활성 권고(`team_outputs` track_a/b) 표시용 dict 목록."""
    out: list[dict[str, Any]] = []
    for rec in load_active_recommendations(within_days=within_days):
        out.append({
            "recommendation_id": rec.recommendation_id,
            "ticker": rec.ticker,
            "display_name": rec.display_name,
            "track": rec.track,
            "verdict": rec.verdict,
            "entry_price": rec.entry_price,
            "stop_loss": rec.stop_loss,
            "target_prices": rec.target_prices,
            "risk_reward": rec.risk_reward,
            "confidence": rec.confidence,
            "date": rec.date,
            "reason": (rec.reasons[0] if rec.reasons else ""),
        })
    return out
