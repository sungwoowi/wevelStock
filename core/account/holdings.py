"""계좌 보유·평가손익·보유기간 조회 — PAPER-TRADING-001 (RB-MS2) M3.

account_positions(가상 체결 파생) + DB-first 시세(chart_ohlcv 최신 종가)로 평가손익 산출.
시세 부재 시 평단 폴백(추정 X, priced=False 노출). 보유기간 = opened_at→as_of.
채점(RB-MS3)·복리(RB-MS4)·`/계좌` 보유현황(M4)의 조회 단일 진입점.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Callable

from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)


def latest_close(ticker: str) -> float | None:
    """chart_ohlcv 최신 종가 (DB-first). 부재 시 None (graceful)."""
    try:
        row = get_db().fetch_one(
            "SELECT close FROM chart_ohlcv WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            (ticker,),
        )
    except Exception:  # noqa: BLE001
        return None
    return float(row["close"]) if row is not None and row["close"] is not None else None


def _days_between(opened_at: str | None, as_of: str | None) -> int:
    """opened_at → as_of(기본 오늘) 보유 일수. 파싱 실패 시 0."""
    if not opened_at:
        return 0
    end = as_of or date.today().isoformat()
    try:
        return max(0, (date.fromisoformat(end[:10]) - date.fromisoformat(opened_at[:10])).days)
    except ValueError:
        return 0


def _realized_to_date(account_id: str, ticker: str) -> float:
    rows = get_db().fetch_all(
        "SELECT realized_pnl_krw FROM account_fills "
        "WHERE account_id = ? AND ticker = ? AND side = 'sell'",
        (account_id, ticker),
    )
    return sum(r["realized_pnl_krw"] or 0.0 for r in rows)


def get_holdings(
    account_id: str,
    *,
    as_of: str | None = None,
    price_lookup: Callable[[str], float | None] | None = None,
) -> list[dict[str, Any]]:
    """계좌 활성 보유 + 평가손익·보유기간·실현손익(누적).

    price_lookup: ticker→평가 시세 (기본 chart_ohlcv 최신 종가). 부재 시 평단 폴백(priced=False).
    """
    pl = price_lookup or latest_close
    rows = get_db().fetch_all(
        "SELECT * FROM account_positions WHERE account_id = ? ORDER BY ticker",
        (account_id,),
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        avg = float(r["avg_price"] or 0.0)
        shares = float(r["shares"] or 0.0)
        raw_price = pl(r["ticker"])
        priced = raw_price is not None
        eval_price = float(raw_price) if priced else avg
        unrealized = (eval_price - avg) * shares
        unrealized_pct = ((eval_price / avg) - 1.0) * 100.0 if avg else 0.0
        out.append({
            "account_id": account_id,
            "ticker": r["ticker"],
            "track": r["track"],
            "shares": shares,
            "avg_price": avg,
            "weight": float(r["weight"] or 0.0),
            "tranche_count": int(r["tranche_count"] or 0),
            "eval_price": eval_price,
            "priced": priced,
            "unrealized_pnl_krw": unrealized,
            "unrealized_pct": unrealized_pct,
            "realized_pnl_krw": _realized_to_date(account_id, r["ticker"]),
            "opened_at": r["opened_at"],
            "holding_days": _days_between(r["opened_at"], as_of),
        })
    return out
