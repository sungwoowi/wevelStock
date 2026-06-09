"""매일 도는 데스크 한 바퀴 — PAPER-TRADING-001 (RB-MS2) M4.

"매일 도는 책임지는 데스크"의 *도는* 부분. 전구간 멱등 (어느 경로·몇 번이든 안전):
  1. 활성 권고(M1) → size_position(RB-MS1) → 지정가 도달분 가상 매수 체결(M2).
  2. 보유 포지션 → 목표가/손절 도달 매도(M3). **손절 우선.**
  3. 포지션·계좌상태는 체결에서 파생 갱신 (record_*_fill 내부).

run_daily_refresh 3-surface(cron·CLI·endpoint) 단일 호출점에 합류. 가상 전용.
시세(OHLC)·시장맥락(entry_posture/extreme)은 DB-first 기본 + 주입 가능(테스트·백테스트).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Callable

from core.account.paper_trading import (
    compute_tranche_ladder,
    plan_exits,
    record_buy_fill,
    record_sell_fill,
    get_position,
)
from core.account.portfolio import get_account_state, load_accounts
from core.account.sizing import AccountDef, size_position
from core.db import get_db
from core.logging import get_logger
from core.strategist.recommendation import StrategistRecommendation, load_active_recommendations

log = get_logger(__name__)

OHLCProvider = Callable[[str, str], dict[str, Any] | None]  # (ticker, as_of) → {high, low, close}


def _market_of(ticker: str) -> str:
    """6자리 숫자 = 국장(KR), 그 외 = 미장(US)."""
    return "KR" if ticker.isdigit() and len(ticker) == 6 else "US"


def _accounts_for(rec: StrategistRecommendation, accounts: list[AccountDef]) -> list[AccountDef]:
    """권고 트랙 × 종목 시장에 맞는 계좌 (KR 종목→국장 계좌, Track A→중장기)."""
    market = _market_of(rec.ticker)
    return [a for a in accounts if a.track == rec.track and a.market == market]


def _fill_exists(recommendation_id: str, account_id: str, side: str, leg: int) -> bool:
    row = get_db().fetch_one(
        "SELECT 1 FROM account_fills "
        "WHERE recommendation_id=? AND account_id=? AND side=? AND leg=? LIMIT 1",
        (recommendation_id, account_id, side, leg),
    )
    return row is not None


def _total_buy_shares(recommendation_id: str, account_id: str, ticker: str) -> float:
    rows = get_db().fetch_all(
        "SELECT shares FROM account_fills "
        "WHERE account_id=? AND ticker=? AND side='buy'",
        (account_id, ticker),
    )
    return sum(r["shares"] for r in rows)


def _default_market_context(as_of: str) -> tuple[str, str]:
    """DB-first 시장 맥락 — KOSPI MarketView entry_posture + 미장 매크로 extreme (graceful)."""
    posture, extreme = "neutral", "none"
    try:
        from collectors.market_view import get_today_view

        view = get_today_view(as_of, "KOSPI")
        if view is not None:
            posture = view.entry_posture or "neutral"
    except Exception:  # noqa: BLE001 — 맥락 부재가 데스크를 막지 않음
        pass
    try:
        from collectors.us_macro import get_today_us_macro

        snap = get_today_us_macro(as_of)
        if snap is not None:
            extreme = snap.extreme or "none"
    except Exception:  # noqa: BLE001
        pass
    return posture, extreme


def db_ohlc_provider(ticker: str, as_of: str) -> dict[str, Any] | None:
    """DB-first OHLC — chart_ohlcv 의 as_of 일봉. 부재 시 최신 일봉 폴백(graceful)."""
    db = get_db()
    row = db.fetch_one(
        "SELECT high, low, close FROM chart_ohlcv WHERE ticker = ? AND date = ?",
        (ticker, as_of),
    )
    if row is None:
        row = db.fetch_one(
            "SELECT high, low, close FROM chart_ohlcv WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            (ticker,),
        )
    if row is None:
        return None
    return {"high": row["high"], "low": row["low"], "close": row["close"]}


def run_desk_today(*, as_of: str | None = None) -> dict[str, Any]:
    """오늘 데스크 한 바퀴 (DB-first OHLC). run_daily_refresh 3단계 합류점."""
    return run_desk_once(as_of=as_of or date.today().isoformat(), ohlc_provider=db_ohlc_provider)


def run_desk_once(
    *,
    as_of: str,
    ohlc_provider: OHLCProvider,
    market_context: tuple[str, str] | None = None,
    within_days: int = 30,
) -> dict[str, Any]:
    """데스크 한 바퀴 (멱등). 활성 권고를 당일 시세로 굴려 가상 체결.

    ohlc_provider(ticker, as_of) → {high, low, close} (없으면 그 종목 skip).
    market_context = (entry_posture, extreme). 미주입 시 DB-first 기본.
    """
    posture, extreme = market_context or _default_market_context(as_of)
    recs = load_active_recommendations(within_days=within_days)
    accounts = load_accounts()
    buy_fills = sell_fills = 0
    touched: set[str] = set()

    for rec in recs:
        if not rec.is_actionable:
            continue
        ohlc = ohlc_provider(rec.ticker, as_of)
        if not ohlc:
            continue
        low = float(ohlc.get("low"))
        high = float(ohlc.get("high"))

        for acct in _accounts_for(rec, accounts):
            state = get_account_state(acct.account_id)
            sizing = size_position(
                recommendation=rec.to_recommendation_dict(),
                account=acct,
                state=state,
                entry_posture=posture,
                extension=None,  # 종목별 과열도 주입은 후속 SLOT (현재 중립 분할)
                extreme=extreme,
            )
            if sizing.blocked or not sizing.tranches:
                continue

            # 1) 매수 — 당일 저가 도달 차수 (미체결만), 지정가에 체결
            ladder = compute_tranche_ladder(rec.entry_price, rec.stop_loss, len(sizing.tranches))
            for i, tr in enumerate(sizing.tranches):
                leg = i + 1
                if low <= ladder[i] and not _fill_exists(rec.recommendation_id, acct.account_id, "buy", leg):
                    record_buy_fill(
                        recommendation_id=rec.recommendation_id, account_id=acct.account_id,
                        ticker=rec.ticker, track=rec.track, leg=leg, limit_price=ladder[i],
                        fill_price=ladder[i], value_krw=tr.value_krw, filled_date=as_of,
                        reason="entry" if leg == 1 else "add",
                    )
                    buy_fills += 1
                    touched.add(acct.account_id)

            # 2) 매도 — 목표가/손절 도달 (손절 우선), 발행된 leg 만 (fire-once)
            pos = get_position(acct.account_id, rec.ticker)
            if pos:
                total_buy = _total_buy_shares(rec.recommendation_id, acct.account_id, rec.ticker)
                for ex in plan_exits(
                    target_prices=rec.target_prices, stop_loss=rec.stop_loss,
                    net_shares=pos["shares"], total_buy_shares=total_buy,
                    daily_high=high, daily_low=low,
                ):
                    if not _fill_exists(rec.recommendation_id, acct.account_id, "sell", ex.leg):
                        record_sell_fill(
                            recommendation_id=rec.recommendation_id, account_id=acct.account_id,
                            ticker=rec.ticker, track=rec.track, leg=ex.leg, fill_price=ex.fill_price,
                            shares=ex.shares, filled_date=as_of, reason=ex.reason,
                        )
                        sell_fills += 1
                        touched.add(acct.account_id)

    log.info("desk_run_once", date=as_of, recs=len(recs), buy_fills=buy_fills,
             sell_fills=sell_fills, posture=posture, extreme=extreme)
    return {
        "date": as_of,
        "recommendations": len(recs),
        "buy_fills": buy_fills,
        "sell_fills": sell_fills,
        "accounts_touched": sorted(touched),
        "entry_posture": posture,
        "extreme": extreme,
    }
