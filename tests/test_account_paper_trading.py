"""PAPER-TRADING-001 (RB-MS2) M2 — 가상 체결 엔진 테스트.

지정가 사다리(entry→stop 보간, stop 아래 불가) + 도달 판정 + 멱등 매수 체결 +
account_positions/account_state 파생 갱신.
"""
from __future__ import annotations

import pytest

from core.account import paper_trading, portfolio
from core.account.paper_trading import (
    SellIntent,
    compute_tranche_ladder,
    plan_exits,
    record_buy_fill,
    record_sell_fill,
    tranches_reaching,
)
from core.account.sizing import reload_accounts_config
from core.db.connection import Database, reset_db


# ---------------------------------------------------------------------------
# compute_tranche_ladder — 순수 (entry→stop 보간, 무지성 물타기 차단)
# ---------------------------------------------------------------------------


def test_ladder_three_tranches_interpolates_between_entry_and_stop():
    # 기본 분율 [0.4, 0.7]: 1차=entry / 2차=entry-0.4*(e-s) / 3차=entry-0.7*(e-s)
    ladder = compute_tranche_ladder(100.0, 90.0, 3)
    assert ladder == pytest.approx([100.0, 96.0, 93.0])


def test_ladder_single_tranche_is_entry_only():
    assert compute_tranche_ladder(100.0, 90.0, 1) == pytest.approx([100.0])


def test_ladder_never_below_stop_even_with_deep_fractions():
    # 분율 < 1 이면 가장 깊은 차수도 stop 위 — 손절선 아래 추가매수 원천 차단
    ladder = compute_tranche_ladder(100.0, 90.0, 3, fractions=[0.9, 0.99])
    assert all(p > 90.0 for p in ladder)


# ---------------------------------------------------------------------------
# tranches_reaching — 순수 (당일 저가 ≤ 지정가)
# ---------------------------------------------------------------------------


def test_tranches_reaching_returns_indices_at_or_below_low():
    ladder = [100.0, 96.0, 93.0]
    # 당일 저가 95 → 1차(100)·2차(96) 도달, 3차(93) 미도달
    assert tranches_reaching(ladder, 95.0) == [1, 2]


def test_tranches_reaching_none_when_low_above_entry():
    assert tranches_reaching([100.0, 96.0], 101.0) == []


# ---------------------------------------------------------------------------
# record_buy_fill — DB (멱등, 포지션·상태 파생)
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    reload_accounts_config()
    db = Database(tmp_path / "test_paper.sqlite")
    monkeypatch.setattr(paper_trading, "get_db", lambda: db)
    monkeypatch.setattr(portfolio, "get_db", lambda: db)
    return db


def _buy(**over):
    base = dict(
        recommendation_id="REC-20260609-005930-A",
        account_id="kr_long",
        ticker="005930",
        track="A",
        leg=1,
        limit_price=100.0,
        fill_price=100.0,
        value_krw=1_000_000.0,
        filled_date="2026-06-09",
        reason="entry",
    )
    base.update(over)
    return record_buy_fill(**base)


def test_record_buy_fill_creates_position(isolated_db):
    fill = _buy()
    assert fill.shares == pytest.approx(10_000.0)  # 1,000,000 / 100
    pos = paper_trading.get_position("kr_long", "005930")
    assert pos is not None
    assert pos["shares"] == pytest.approx(10_000.0)
    assert pos["avg_price"] == pytest.approx(100.0)
    assert pos["weight"] == pytest.approx(0.01)  # 1M / 1억 seed (2026-06-10 상향)
    assert pos["tranche_count"] == 1


def test_record_buy_fill_idempotent_same_leg(isolated_db):
    _buy()
    _buy()  # 같은 (rec, account, side, leg) 재실행 → 누적 X
    pos = paper_trading.get_position("kr_long", "005930")
    assert pos["shares"] == pytest.approx(10_000.0)
    assert pos["tranche_count"] == 1


def test_second_tranche_accumulates_and_averages(isolated_db):
    _buy(leg=1, fill_price=100.0, value_krw=1_000_000.0)  # 10,000 주
    _buy(leg=2, limit_price=96.0, fill_price=96.0, value_krw=1_000_000.0)  # 10,416.67 주
    pos = paper_trading.get_position("kr_long", "005930")
    assert pos["tranche_count"] == 2
    assert pos["shares"] == pytest.approx(10_000.0 + 1_000_000.0 / 96.0)
    # 평단 = 총매수금액 / 총주수
    expected_avg = 2_000_000.0 / (10_000.0 + 1_000_000.0 / 96.0)
    assert pos["avg_price"] == pytest.approx(expected_avg)
    assert pos["weight"] == pytest.approx(0.02)  # 2M 투입 / 1억 seed


def test_account_state_deployed_weight_reflects_fills(isolated_db):
    _buy(value_krw=1_500_000.0)  # 1.5M / 1억 = 0.015 비중
    state = portfolio.get_account_state("kr_long")
    assert state.deployed_weight == pytest.approx(0.015)
    # Track A 매수는 trading_deployed_weight 에 잡히지 않음
    assert state.trading_deployed_weight == pytest.approx(0.0)


def test_track_b_fill_counts_toward_trading_deployed(isolated_db):
    _buy(account_id="kr_swing", track="B", recommendation_id="REC-20260609-005930-B",
         value_krw=1_000_000.0)
    state = portfolio.get_account_state("kr_swing")
    assert state.deployed_weight == pytest.approx(0.01)
    assert state.trading_deployed_weight == pytest.approx(0.01)


# ---------------------------------------------------------------------------
# plan_exits — 순수 (손절 우선 + 목표가 부분익절)
# ---------------------------------------------------------------------------


def test_plan_exits_stop_sells_all_remaining():
    exits = plan_exits(
        target_prices=[130.0], stop_loss=90.0,
        net_shares=10_000.0, total_buy_shares=10_000.0,
        daily_high=95.0, daily_low=88.0,  # 저가 88 ≤ stop 90
    )
    assert exits == [SellIntent(leg=0, fill_price=90.0, shares=10_000.0, reason="stop")]


def test_plan_exits_stop_takes_priority_over_target_same_day():
    # 같은 날 stop·목표 동시 도달(갭) → 손절만 (물타기·익절 아님)
    exits = plan_exits(
        target_prices=[130.0], stop_loss=90.0,
        net_shares=10_000.0, total_buy_shares=10_000.0,
        daily_high=135.0, daily_low=88.0,
    )
    assert len(exits) == 1
    assert exits[0].reason == "stop"


def test_plan_exits_single_target_partial():
    exits = plan_exits(
        target_prices=[130.0], stop_loss=90.0,
        net_shares=10_000.0, total_buy_shares=10_000.0,
        daily_high=131.0, daily_low=120.0,
    )
    assert exits == [SellIntent(leg=1, fill_price=130.0, shares=10_000.0, reason="target_1")]


def test_plan_exits_track_a_three_targets_fires_reached_levels():
    # 당일 고가 95 → 목표 80·92 도달, 105 미도달 (각 1/3 익절)
    exits = plan_exits(
        target_prices=[80.0, 92.0, 105.0], stop_loss=60.0,
        net_shares=30_000.0, total_buy_shares=30_000.0,
        daily_high=95.0, daily_low=85.0,
    )
    assert [e.leg for e in exits] == [1, 2]
    assert all(e.shares == pytest.approx(10_000.0) for e in exits)  # 30,000 / 3


def test_plan_exits_none_when_no_level_reached():
    assert plan_exits(
        target_prices=[130.0], stop_loss=90.0,
        net_shares=10_000.0, total_buy_shares=10_000.0,
        daily_high=120.0, daily_low=100.0,
    ) == []


def test_plan_exits_empty_when_no_position():
    assert plan_exits(
        target_prices=[130.0], stop_loss=90.0,
        net_shares=0.0, total_buy_shares=10_000.0,
        daily_high=200.0, daily_low=50.0,
    ) == []


# ---------------------------------------------------------------------------
# record_sell_fill — DB (실현손익, 포지션 감소/청산)
# ---------------------------------------------------------------------------


def test_record_sell_fill_partial_realizes_pnl_and_reduces(isolated_db):
    _buy(value_krw=1_000_000.0, fill_price=100.0)  # 10,000 주 @ 평단 100
    fill = record_sell_fill(
        recommendation_id="REC-20260609-005930-A", account_id="kr_long", ticker="005930",
        track="A", leg=1, fill_price=130.0, shares=5_000.0, filled_date="2026-06-15",
        reason="target_1",
    )
    assert fill.realized_pnl_krw == pytest.approx((130.0 - 100.0) * 5_000.0)  # 150,000
    pos = paper_trading.get_position("kr_long", "005930")
    assert pos["shares"] == pytest.approx(5_000.0)


def test_record_sell_fill_full_exit_closes_position(isolated_db):
    _buy(value_krw=1_000_000.0, fill_price=100.0)  # 10,000 주
    record_sell_fill(
        recommendation_id="REC-20260609-005930-A", account_id="kr_long", ticker="005930",
        track="A", leg=0, fill_price=90.0, shares=10_000.0, filled_date="2026-06-15", reason="stop",
    )
    assert paper_trading.get_position("kr_long", "005930") is None
    assert portfolio.get_account_state("kr_long").deployed_weight == pytest.approx(0.0)
