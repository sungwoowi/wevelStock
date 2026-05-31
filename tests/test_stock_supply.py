"""collectors/stock_supply.py 단위 테스트 (INFRA-STOCK-SUPPLY-001).

종목 레벨 5주체 수급 — upsert 멱등 / load 정순 / fetch(KRX mock) / ensure 백필·당일 재-fetch /
cutoff_date 결정론(live fetch X) / get_stock_supply_60d + market_cap(KIS mock) / agreement 재사용.
**KRX/KIS mock 필수 (실 API 금지), TESTING=1.**
"""
from __future__ import annotations

import pytest

from collectors.stock_supply import (
    StockSupplyRow,
    ensure_stock_supply_series,
    fetch_stock_supply,
    get_stock_market_cap,
    get_stock_supply_60d,
    load_stock_supply_window,
    sum_stock_supply,
    upsert_stock_supply_row,
)
from collectors.supply_demand_history import agreement_score
from core.db import get_db, reset_db


@pytest.fixture
def fresh_db(tmp_path):
    db_path = tmp_path / "test.db"
    reset_db()
    db = get_db(db_path)
    yield db
    reset_db()


def _row(ticker: str, date: str, f=0, i=0, ind=0, fin=0, p=0) -> StockSupplyRow:
    return StockSupplyRow(
        ticker=ticker, date=date, foreign_net=f, institution_net=i,
        individual_net=ind, financial_inv_net=fin, pension_net=p,
    )


class _FakeKIS:
    """KIS mock — stock_investor_history(3주체 시계열) + stock_price(시총) 동시 제공."""

    def __init__(self, history_rows: list[dict] | None = None,
                 market_cap_eok: int | None = None) -> None:
        self._rows = history_rows or []
        self._cap = market_cap_eok
        self.history_calls = 0

    async def stock_investor_history(self, ticker):
        self.history_calls += 1
        return self._rows

    async def stock_price(self, ticker):
        if self._cap is None:
            return {"error": "no_data", "ticker": ticker}
        return {"ticker": ticker, "market_cap": self._cap}


def _kis_rows(dates: list[str]) -> list[dict]:
    # KIS 3주체 (financial_inv/pension 은 collector 가 0 으로 채움)
    return [
        {"date": d, "foreign_net": 100, "institution_net": 50, "individual_net": -120}
        for d in dates
    ]


# ---------------------------------------------------------------------------
# 1. 순수 — sum / agreement 재사용
# ---------------------------------------------------------------------------


class TestPure:
    def test_sum_aggregates(self) -> None:
        rows = [_row("X", "2026-05-01", f=100, i=50), _row("X", "2026-05-02", f=200, i=-50)]
        sums = sum_stock_supply(rows)
        assert sums["foreign_net"] == 300
        assert sums["institution_net"] == 0

    def test_agreement_reused(self) -> None:
        sums = {"foreign_net": 100, "institution_net": 50, "individual_net": -10,
                "financial_inv_net": 30, "pension_net": 20}
        # 4/5 동일 부호(+) → 8.0
        assert agreement_score(sums) == 8.0


# ---------------------------------------------------------------------------
# 2. DB layer — upsert 멱등 / load 정순
# ---------------------------------------------------------------------------


class TestDB:
    def test_upsert_idempotent(self, fresh_db) -> None:
        upsert_stock_supply_row(_row("005930", "2026-05-31", f=100))
        upsert_stock_supply_row(_row("005930", "2026-05-31", f=999))  # REPLACE
        rows = load_stock_supply_window("005930")
        assert len(rows) == 1
        assert rows[0].foreign_net == 999

    def test_load_window_ascending(self, fresh_db) -> None:
        upsert_stock_supply_row(_row("X", "2026-05-03"))
        upsert_stock_supply_row(_row("X", "2026-05-01"))
        upsert_stock_supply_row(_row("X", "2026-05-02"))
        rows = load_stock_supply_window("X")
        assert [r.date for r in rows] == ["2026-05-01", "2026-05-02", "2026-05-03"]

    def test_load_window_ticker_isolated(self, fresh_db) -> None:
        upsert_stock_supply_row(_row("A", "2026-05-01"))
        upsert_stock_supply_row(_row("B", "2026-05-01"))
        assert len(load_stock_supply_window("A")) == 1


# ---------------------------------------------------------------------------
# 3. fetch_stock_supply — KRX mock
# ---------------------------------------------------------------------------


class TestFetch:
    @pytest.mark.asyncio
    async def test_fetch_upserts(self, fresh_db) -> None:
        kis = _FakeKIS(history_rows=_kis_rows(["2026-05-01", "2026-05-02"]))
        n = await fetch_stock_supply("005930", kis=kis)
        assert n == 2
        rows = load_stock_supply_window("005930")
        assert len(rows) == 2
        assert kis.history_calls == 1
        assert rows[0].financial_inv_net == 0 and rows[0].pension_net == 0  # KIS 3주체

    @pytest.mark.asyncio
    async def test_fetch_cutoff_excludes_future(self, fresh_db) -> None:
        kis = _FakeKIS(history_rows=_kis_rows(["2026-05-01", "2026-05-31"]))
        n = await fetch_stock_supply("X", cutoff_date="2026-05-15", kis=kis)
        assert n == 1  # 05-31 제외
        assert [r.date for r in load_stock_supply_window("X")] == ["2026-05-01"]

    @pytest.mark.asyncio
    async def test_fetch_empty_on_error(self, fresh_db) -> None:
        class _Boom:
            async def stock_investor_history(self, *a, **k):
                raise RuntimeError("kis down")
        n = await fetch_stock_supply("X", kis=_Boom())
        assert n == 0


# ---------------------------------------------------------------------------
# 4. ensure_stock_supply_series — 백필 / 당일 재-fetch / cutoff
# ---------------------------------------------------------------------------


class TestEnsure:
    @pytest.mark.asyncio
    async def test_fetch_populates(self, fresh_db) -> None:
        kis = _FakeKIS(history_rows=_kis_rows([f"2026-05-{d:02d}" for d in range(1, 21)]))
        rows = await ensure_stock_supply_series("X", days=60, kis=kis)
        assert kis.history_calls == 1
        assert len(rows) == 20

    @pytest.mark.asyncio
    async def test_cutoff_no_live_fetch(self, fresh_db) -> None:
        upsert_stock_supply_row(_row("X", "2026-05-01", f=1))
        upsert_stock_supply_row(_row("X", "2026-05-20", f=2))  # cutoff 이후
        kis = _FakeKIS(history_rows=[])
        rows = await ensure_stock_supply_series("X", cutoff_date="2026-05-10", kis=kis)
        assert kis.history_calls == 0  # 백테스팅 = live fetch 금지
        assert [r.date for r in rows] == ["2026-05-01"]

    @pytest.mark.asyncio
    async def test_empty_ticker(self, fresh_db) -> None:
        assert await ensure_stock_supply_series("  ", kis=_FakeKIS()) == []


# ---------------------------------------------------------------------------
# 5. get_stock_supply_60d + market_cap
# ---------------------------------------------------------------------------


class TestGet60d:
    @pytest.mark.asyncio
    async def test_stock_source_and_market_cap(self, fresh_db) -> None:
        kis = _FakeKIS(history_rows=_kis_rows(["2026-05-01", "2026-05-02"]), market_cap_eok=4000)
        res = await get_stock_supply_60d("005930", kis=kis)
        assert res["source"] == "stock_kis"
        assert res["actual_days"] == 2
        assert res["foreign_net_60d"] == 200
        assert res["market_cap"] == 400000.0  # 4000억 → 400,000 백만원

    @pytest.mark.asyncio
    async def test_unavailable_when_empty(self, fresh_db) -> None:
        res = await get_stock_supply_60d("X", kis=_FakeKIS(history_rows=[], market_cap_eok=None))
        assert res["source"] == "unavailable"
        assert res["actual_days"] == 0

    @pytest.mark.asyncio
    async def test_market_cap_eok_to_million(self, fresh_db) -> None:
        assert await get_stock_market_cap("X", kis=_FakeKIS(market_cap_eok=123)) == 12300.0

    @pytest.mark.asyncio
    async def test_market_cap_none_on_error(self, fresh_db) -> None:
        assert await get_stock_market_cap("X", kis=_FakeKIS(market_cap_eok=None)) is None
