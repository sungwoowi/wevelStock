"""PAPER-TRADING-001 (RB-MS2) M3 — 계좌 보유·평가손익·보유기간 조회 테스트."""
from __future__ import annotations

import pytest

from core.account import holdings, paper_trading, portfolio
from core.account.holdings import get_holdings
from core.account.sizing import reload_accounts_config
from core.db.connection import Database, reset_db


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    reload_accounts_config()
    db = Database(tmp_path / "test_holdings.sqlite")
    for mod in (paper_trading, portfolio, holdings):
        monkeypatch.setattr(mod, "get_db", lambda: db)
    return db


def _buy(**over):
    base = dict(
        recommendation_id="REC-20260609-005930-A", account_id="kr_long", ticker="005930",
        track="A", leg=1, limit_price=100.0, fill_price=100.0, value_krw=1_000_000.0,
        filled_date="2026-06-09", reason="entry",
    )
    base.update(over)
    return paper_trading.record_buy_fill(**base)


def test_empty_account_has_no_holdings(isolated_db):
    assert get_holdings("kr_long") == []


def test_holding_unrealized_pnl_with_price(isolated_db):
    _buy()  # 10,000 주 @ 100
    rows = get_holdings("kr_long", price_lookup=lambda t: 130.0)
    assert len(rows) == 1
    h = rows[0]
    assert h["ticker"] == "005930"
    assert h["shares"] == pytest.approx(10_000.0)
    assert h["eval_price"] == pytest.approx(130.0)
    assert h["unrealized_pnl_krw"] == pytest.approx((130.0 - 100.0) * 10_000.0)  # 300,000
    assert h["unrealized_pct"] == pytest.approx(30.0)
    assert h["priced"] is True


def test_holding_without_price_falls_back_to_avg(isolated_db):
    _buy()
    h = get_holdings("kr_long", price_lookup=lambda t: None)[0]
    assert h["eval_price"] == pytest.approx(100.0)  # 시세 부재 → 평단 (추정 X)
    assert h["unrealized_pnl_krw"] == pytest.approx(0.0)
    assert h["priced"] is False


def test_holding_days_from_opened_at(isolated_db):
    _buy(filled_date="2026-06-01")
    h = get_holdings("kr_long", as_of="2026-06-09", price_lookup=lambda t: 100.0)[0]
    assert h["holding_days"] == 8


def test_holding_includes_realized_to_date(isolated_db):
    _buy(value_krw=1_000_000.0, fill_price=100.0)  # 10,000 주
    paper_trading.record_sell_fill(
        recommendation_id="REC-20260609-005930-A", account_id="kr_long", ticker="005930",
        track="A", leg=1, fill_price=130.0, shares=5_000.0, filled_date="2026-06-15",
        reason="target_1",
    )
    h = get_holdings("kr_long", price_lookup=lambda t: 130.0)[0]
    assert h["shares"] == pytest.approx(5_000.0)
    assert h["realized_pnl_krw"] == pytest.approx((130.0 - 100.0) * 5_000.0)  # 150,000


def test_latest_close_reads_chart_ohlcv(isolated_db):
    with isolated_db.connect() as conn:
        conn.execute(
            "INSERT INTO chart_ohlcv (ticker, date, open, high, low, close, volume, fetched_at) "
            "VALUES ('005930','2026-06-08',100,110,95,105,1000,'2026-06-08T18:00:00+09:00')",
        )
        conn.execute(
            "INSERT INTO chart_ohlcv (ticker, date, open, high, low, close, volume, fetched_at) "
            "VALUES ('005930','2026-06-09',105,120,100,118,1000,'2026-06-09T18:00:00+09:00')",
        )
    assert holdings.latest_close("005930") == pytest.approx(118.0)  # 최신 date
    assert holdings.latest_close("999999") is None
