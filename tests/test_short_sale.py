"""공매도·융자/대주 잔고·프로그램매매 수집 (ADVISOR-CORE-001 M1-b).

KIS 실호출 0 — 클라이언트를 stub 으로 주입. 저장은 `stock_supply_history` 컬럼 확장
(가드 #11: 종목×일자 수급 지표로 도메인 동일, 신규 테이블 0).
"""
from __future__ import annotations

import pytest

from collectors import short_sale as ss
from core.db.connection import Database, reset_db


@pytest.fixture()
def db(tmp_path, monkeypatch):
    reset_db()
    d = Database(tmp_path / "short.sqlite")
    monkeypatch.setattr(ss, "get_db", lambda: d)
    return d


class _StubKIS:
    """KIS 응답 stub — 실호출 0."""

    _UNSET = object()   # "미지정"과 "명시적 None/빈값"을 구분

    def __init__(self, short=_UNSET, credit=_UNSET, program=_UNSET, fail: set[str] | None = None):
        self._short = short if short is not _StubKIS._UNSET else [
            {"date": "2026-08-10", "short_volume": 1166600,
             "short_ratio": 7.14, "short_cum_ratio": 9.08},
            {"date": "2026-08-07", "short_volume": 2339705,
             "short_ratio": 11.39, "short_cum_ratio": 9.33},
        ]
        self._credit = credit if credit is not _StubKIS._UNSET else [
            {"date": "2026-08-10", "loan_balance_qty": 23841068, "short_balance_qty": 7886},
        ]
        self._program = program if program is not _StubKIS._UNSET else {
            "net_qty": 740940, "net_amount": 172879,
        }
        self._fail = fail or set()

    async def daily_short_sale(self, ticker, start_date, end_date):
        if "short" in self._fail:
            raise RuntimeError("boom")
        return self._short

    async def daily_credit_balance(self, ticker, base_date):
        if "credit" in self._fail:
            raise RuntimeError("boom")
        return self._credit

    async def program_trade_by_stock(self, ticker):
        if "program" in self._fail:
            raise RuntimeError("boom")
        return self._program


def _seed_supply(db, ticker="005930", date="2026-08-10"):
    """기존 5주체 행이 있는 상태 — 확장 컬럼은 그 위에 채워진다."""
    db.execute(
        "INSERT OR REPLACE INTO stock_supply_history "
        "(ticker, date, foreign_net, institution_net, individual_net, "
        " financial_inv_net, pension_net, source) VALUES (?,?,?,?,?,?,?,'kis')",
        (ticker, date, -100, 50, 50, 0, 0),
    )


# --- 1. 공매도 --------------------------------------------------------------


async def test_short_sale_rows_persisted(db) -> None:
    _seed_supply(db)
    n = await ss.collect_short_pressure("005930", as_of="2026-08-10", kis=_StubKIS())
    assert n >= 1
    row = db.fetch_one(
        "SELECT * FROM stock_supply_history WHERE ticker='005930' AND date='2026-08-10'"
    )
    assert row["short_volume"] == 1166600
    assert row["short_ratio"] == pytest.approx(7.14)
    assert row["short_cum_ratio"] == pytest.approx(9.08)


async def test_short_sale_preserves_existing_flow_columns(db) -> None:
    """확장 컬럼을 채우면서 기존 5주체 값을 덮어쓰지 않는다."""
    _seed_supply(db)
    await ss.collect_short_pressure("005930", as_of="2026-08-10", kis=_StubKIS())
    row = db.fetch_one(
        "SELECT foreign_net, institution_net FROM stock_supply_history "
        "WHERE ticker='005930' AND date='2026-08-10'"
    )
    assert row["foreign_net"] == -100 and row["institution_net"] == 50


async def test_short_sale_creates_row_when_absent(db) -> None:
    """5주체 행이 아직 없어도 공매도만으로 행이 생긴다 (NOT NULL 은 0 으로)."""
    n = await ss.collect_short_pressure("000660", as_of="2026-08-10", kis=_StubKIS())
    assert n >= 1
    row = db.fetch_one(
        "SELECT * FROM stock_supply_history WHERE ticker='000660' AND date='2026-08-10'"
    )
    assert row is not None and row["short_volume"] == 1166600
    assert row["foreign_net"] == 0     # 미수집 자리 — 5주체 collector 가 나중에 채움


# --- 2. 융자·대주 잔고 (숏커버링 재료) ---------------------------------------


async def test_credit_balance_persisted(db) -> None:
    _seed_supply(db)
    await ss.collect_short_pressure("005930", as_of="2026-08-10", kis=_StubKIS())
    row = db.fetch_one(
        "SELECT loan_balance_qty, short_balance_qty FROM stock_supply_history "
        "WHERE ticker='005930' AND date='2026-08-10'"
    )
    assert row["loan_balance_qty"] == 23841068
    assert row["short_balance_qty"] == 7886


# --- 3. 프로그램매매 ---------------------------------------------------------


async def test_program_trade_persisted(db) -> None:
    _seed_supply(db)
    await ss.collect_short_pressure("005930", as_of="2026-08-10", kis=_StubKIS())
    row = db.fetch_one(
        "SELECT program_net_qty, program_net_amount FROM stock_supply_history "
        "WHERE ticker='005930' AND date='2026-08-10'"
    )
    assert row["program_net_qty"] == 740940
    assert row["program_net_amount"] == 172879


# --- 4. graceful — 한 축이 죽어도 나머지는 적재 ------------------------------


@pytest.mark.parametrize("broken", ["short", "credit", "program"])
async def test_one_axis_failure_does_not_block_others(db, broken) -> None:
    _seed_supply(db)
    n = await ss.collect_short_pressure(
        "005930", as_of="2026-08-10", kis=_StubKIS(fail={broken})
    )
    row = db.fetch_one(
        "SELECT * FROM stock_supply_history WHERE ticker='005930' AND date='2026-08-10'"
    )
    assert row is not None
    if broken != "short":
        assert row["short_volume"] is not None
    if broken != "credit":
        assert row["short_balance_qty"] is not None
    if broken != "program":
        assert row["program_net_qty"] is not None


async def test_all_axes_failing_returns_zero_not_crash(db) -> None:
    n = await ss.collect_short_pressure(
        "005930", as_of="2026-08-10", kis=_StubKIS(fail={"short", "credit", "program"})
    )
    assert n == 0


async def test_empty_responses_are_graceful(db) -> None:
    n = await ss.collect_short_pressure(
        "005930", as_of="2026-08-10",
        kis=_StubKIS(short=[], credit=[], program=None),
    )
    assert n == 0


# --- 5. 멱등 ----------------------------------------------------------------


async def test_collect_is_idempotent(db) -> None:
    _seed_supply(db)
    await ss.collect_short_pressure("005930", as_of="2026-08-10", kis=_StubKIS())
    await ss.collect_short_pressure("005930", as_of="2026-08-10", kis=_StubKIS())
    rows = db.fetch_all("SELECT * FROM stock_supply_history WHERE ticker='005930'")
    assert len(rows) == 2   # 08-10, 08-07 (공매도 시계열 2행) — 중복 없음


# --- 6. 시장 집계 (판세 입력) ------------------------------------------------


def test_market_short_summary_aggregates(db) -> None:
    """판세는 종목별이 아니라 시장 집계를 읽는다."""
    for t, ratio, sbal in [("005930", 7.14, 7886), ("000660", 12.0, 50000),
                           ("035420", 3.0, 1000)]:
        db.execute(
            "INSERT OR REPLACE INTO stock_supply_history "
            "(ticker, date, foreign_net, institution_net, individual_net, "
            " financial_inv_net, pension_net, source, short_ratio, short_balance_qty, "
            " program_net_amount) VALUES (?,?,0,0,0,0,0,'kis',?,?,?)",
            (t, "2026-08-10", ratio, sbal, 1000),
        )
    s = ss.summarize_short_pressure("2026-08-10")
    assert s.covered_tickers == 3
    assert s.avg_short_ratio == pytest.approx((7.14 + 12.0 + 3.0) / 3, abs=0.01)
    assert s.max_short_ratio == pytest.approx(12.0)
    assert s.total_program_net_amount == 3000


def test_market_short_summary_empty_day(db) -> None:
    s = ss.summarize_short_pressure("2026-08-10")
    assert s.covered_tickers == 0
    assert s.avg_short_ratio is None
