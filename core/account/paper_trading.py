"""가상 체결 엔진 — PAPER-TRADING-001 (RB-MS2) M2.

전략가 권고(구조화) → 비중 지시(size_position) → **지정가 도달 판정** → 가상 체결 기록.
체결 모델(spec-interview 2026-06-09 확정):
  - 차수 지정가 = entry→stop **보간 사다리** (1차=entry, i차=entry−frac·(entry−stop)).
    분율 < 1 → 가장 깊은 차수도 stop 위 = 무지성 물타기 원천 차단(thesis-valid 구간만 추가매수).
  - 도달 판정 = 당일 저가 ≤ 차수 지정가 → 그 지정가에 체결(보수적).
  - 멱등 = (recommendation_id, account_id, side, leg). account_positions/account_state 는 fills 에서 파생.

가상(페이퍼) 전용 — 실 KIS 주문 X. 수치(분율)는 다일 튜닝 SLOT([[feedback_backtest_essence]]).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.account.portfolio import get_account, upsert_account_state
from core.account.sizing import AccountState
from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)

# 2·3차 분율 — entry−frac·(entry−stop). 보수적 기본(<1 보장 → stop 위). config split_ladder 로 override.
_DEFAULT_LADDER_FRACTIONS: list[float] = [0.4, 0.7]


@dataclass
class PaperFill:
    """가상 체결 1 leg — paper-fill-v1."""

    recommendation_id: str
    account_id: str
    ticker: str
    track: str
    side: str               # "buy" | "sell"
    leg: int                # buy: 차수 1-3 / sell: 목표단 1-3·손절 0
    limit_price: float | None
    fill_price: float
    shares: float
    value_krw: float
    reason: str
    realized_pnl_krw: float
    filled_date: str


def compute_tranche_ladder(
    entry: float, stop: float, n_tranches: int, *, fractions: list[float] | None = None
) -> list[float]:
    """차수별 지정가 = entry→stop 보간 사다리. 1차=entry, i차=entry−frac[i-2]·(entry−stop).

    분율 < 1 → 모든 차수 > stop (손절선 아래 추가매수 차단). entry≤stop 이면 빈 사다리 아님(1차=entry).
    """
    fracs = fractions or _DEFAULT_LADDER_FRACTIONS
    span = entry - stop
    ladder = [float(entry)]
    for i in range(1, max(1, n_tranches)):
        f = fracs[i - 1] if (i - 1) < len(fracs) else fracs[-1]
        ladder.append(entry - f * span)
    return ladder[:n_tranches]


def tranches_reaching(ladder: list[float], daily_low: float) -> list[int]:
    """당일 저가 ≤ 지정가인 차수 인덱스(1-based). 도달 = 그 지정가에 매수 체결 가능."""
    return [i + 1 for i, lp in enumerate(ladder) if daily_low <= lp]


def record_buy_fill(
    *,
    recommendation_id: str,
    account_id: str,
    ticker: str,
    track: str,
    leg: int,
    limit_price: float | None,
    fill_price: float,
    value_krw: float,
    filled_date: str,
    reason: str = "entry",
) -> PaperFill:
    """가상 매수 체결 1 leg 기록 (멱등) + 포지션·계좌상태 파생 갱신.

    shares = value_krw / fill_price (배포 자본 고정 → 저가 체결 시 주수 증가, 비중은 자본 기준 유지).
    """
    shares = value_krw / fill_price if fill_price else 0.0
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO account_fills
                (recommendation_id, account_id, ticker, track, side, leg,
                 limit_price, fill_price, shares, value_krw, reason, realized_pnl_krw, filled_date)
            VALUES (?, ?, ?, ?, 'buy', ?, ?, ?, ?, ?, ?, 0, ?)
            ON CONFLICT(recommendation_id, account_id, side, leg) DO UPDATE SET
                ticker=excluded.ticker, track=excluded.track,
                limit_price=excluded.limit_price, fill_price=excluded.fill_price,
                shares=excluded.shares, value_krw=excluded.value_krw,
                reason=excluded.reason, filled_date=excluded.filled_date
            """,
            (recommendation_id, account_id, ticker, track, leg,
             limit_price, fill_price, shares, value_krw, reason, filled_date),
        )
    _recompute_position(account_id, ticker, track)
    _recompute_account_state(account_id)
    return PaperFill(
        recommendation_id=recommendation_id, account_id=account_id, ticker=ticker, track=track,
        side="buy", leg=leg, limit_price=limit_price, fill_price=fill_price, shares=shares,
        value_krw=value_krw, reason=reason, realized_pnl_krw=0.0, filled_date=filled_date,
    )


@dataclass
class SellIntent:
    """매도 1 leg 의도 — plan_exits 산출 (desk 가 record_sell_fill 로 기록)."""

    leg: int            # 목표단 1-3 / 손절 0
    fill_price: float
    shares: float
    reason: str


def plan_exits(
    *,
    target_prices: list[float],
    stop_loss: float | None,
    net_shares: float,
    total_buy_shares: float,
    daily_high: float,
    daily_low: float,
) -> list[SellIntent]:
    """당일 시세 → 매도 의도. **손절 우선** (같은 날 stop·목표 동시 도달 시 손절만).

    - stop 도달(당일 저가 ≤ stop): 보유 전량 청산 (leg=0, reason=stop).
    - 목표가단 도달(당일 고가 ≥ 목표): 각 단 total_buy_shares/n 부분익절 (leg=i, reason=target_i).
    - 보유 없음(net≤0): 빈 리스트.
    """
    if net_shares <= 1e-9:
        return []
    if stop_loss is not None and daily_low <= stop_loss:
        return [SellIntent(leg=0, fill_price=float(stop_loss), shares=net_shares, reason="stop")]
    intents: list[SellIntent] = []
    n = len(target_prices)
    if n:
        per = total_buy_shares / n
        remaining = net_shares
        for i, t in enumerate(target_prices, start=1):
            if remaining <= 1e-9:
                break
            if daily_high >= t:
                s = min(per, remaining)  # 잔여 초과 매도 방지 (오버셀 차단)
                intents.append(SellIntent(leg=i, fill_price=float(t), shares=s, reason=f"target_{i}"))
                remaining -= s
    return intents


def _cost_basis(account_id: str, ticker: str) -> float:
    """현 보유의 cost-basis 평단 (매수 fills 가중)."""
    rows = get_db().fetch_all(
        "SELECT shares, value_krw FROM account_fills "
        "WHERE account_id = ? AND ticker = ? AND side = 'buy'",
        (account_id, ticker),
    )
    buy_shares = sum(r["shares"] for r in rows)
    buy_value = sum(r["value_krw"] for r in rows)
    return (buy_value / buy_shares) if buy_shares else 0.0


def record_sell_fill(
    *,
    recommendation_id: str,
    account_id: str,
    ticker: str,
    track: str,
    leg: int,
    fill_price: float,
    shares: float,
    filled_date: str,
    reason: str,
) -> PaperFill:
    """가상 매도 체결 1 leg 기록 (멱등) + 실현손익 + 포지션·계좌상태 파생 갱신.

    realized_pnl = (체결가 − cost-basis 평단) × 매도수량.
    """
    avg = _cost_basis(account_id, ticker)
    realized = (fill_price - avg) * shares
    value = fill_price * shares
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO account_fills
                (recommendation_id, account_id, ticker, track, side, leg,
                 limit_price, fill_price, shares, value_krw, reason, realized_pnl_krw, filled_date)
            VALUES (?, ?, ?, ?, 'sell', ?, NULL, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(recommendation_id, account_id, side, leg) DO UPDATE SET
                ticker=excluded.ticker, track=excluded.track, fill_price=excluded.fill_price,
                shares=excluded.shares, value_krw=excluded.value_krw, reason=excluded.reason,
                realized_pnl_krw=excluded.realized_pnl_krw, filled_date=excluded.filled_date
            """,
            (recommendation_id, account_id, ticker, track, leg,
             fill_price, shares, value, reason, realized, filled_date),
        )
    _recompute_position(account_id, ticker, track)
    _recompute_account_state(account_id)
    return PaperFill(
        recommendation_id=recommendation_id, account_id=account_id, ticker=ticker, track=track,
        side="sell", leg=leg, limit_price=None, fill_price=fill_price, shares=shares,
        value_krw=value, reason=reason, realized_pnl_krw=realized, filled_date=filled_date,
    )


def get_position(account_id: str, ticker: str) -> dict[str, Any] | None:
    """account_positions 1행 (보유 없으면 None)."""
    row = get_db().fetch_one(
        "SELECT * FROM account_positions WHERE account_id = ? AND ticker = ?",
        (account_id, ticker),
    )
    return dict(row) if row is not None else None


def _seed_for(account_id: str) -> float:
    acct = get_account(account_id)
    return acct.seed_krw if acct else 10_000_000.0


def _recompute_position(account_id: str, ticker: str, track: str) -> None:
    """account_fills(매수−매도) 집계 → account_positions 파생 (cost-basis 평단·비중)."""
    db = get_db()
    fills = db.fetch_all(
        "SELECT side, leg, shares, value_krw, filled_date FROM account_fills "
        "WHERE account_id = ? AND ticker = ?",
        (account_id, ticker),
    )
    buy_shares = sum(f["shares"] for f in fills if f["side"] == "buy")
    buy_value = sum(f["value_krw"] for f in fills if f["side"] == "buy")
    sell_shares = sum(f["shares"] for f in fills if f["side"] == "sell")
    net_shares = buy_shares - sell_shares
    tranche_count = sum(1 for f in fills if f["side"] == "buy")
    buy_dates = [f["filled_date"] for f in fills if f["side"] == "buy"]
    opened_at = min(buy_dates) if buy_dates else None
    avg_price = (buy_value / buy_shares) if buy_shares else 0.0
    seed = _seed_for(account_id)

    with db.connect() as conn:
        if net_shares <= 1e-9:
            # 전량 청산 → 활성 보유 목록에서 제거 (실현은 account_fills 에 남음)
            conn.execute(
                "DELETE FROM account_positions WHERE account_id = ? AND ticker = ?",
                (account_id, ticker),
            )
            return
        weight = (avg_price * net_shares) / seed if seed else 0.0
        conn.execute(
            """
            INSERT INTO account_positions
                (account_id, ticker, track, avg_price, shares, weight, tranche_count, opened_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(account_id, ticker) DO UPDATE SET
                track=excluded.track, avg_price=excluded.avg_price, shares=excluded.shares,
                weight=excluded.weight, tranche_count=excluded.tranche_count,
                opened_at=excluded.opened_at, updated_at=excluded.updated_at
            """,
            (account_id, ticker, track, avg_price, net_shares, weight, tranche_count, opened_at),
        )


def _recompute_account_state(account_id: str) -> None:
    """account_positions 비중 합 → account_state.deployed_weight (Track B = trading_deployed)."""
    db = get_db()
    rows = db.fetch_all(
        "SELECT track, weight FROM account_positions WHERE account_id = ?",
        (account_id,),
    )
    deployed = sum(r["weight"] or 0.0 for r in rows)
    trading = sum((r["weight"] or 0.0) for r in rows if (r["track"] or "") == "B")
    upsert_account_state(
        AccountState(account_id=account_id, deployed_weight=deployed, trading_deployed_weight=trading),
        seed_krw=_seed_for(account_id),
    )
