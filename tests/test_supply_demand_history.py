"""INFRA-SNAPSHOT-EXTEND-001 — supply_demand_history collector 4 케이스.

1. refresh_supply_demand_today upsert (mock KIS → 양 시장 row 적재 + 멱등성)
2. get_supply_60d 60일 sum 정확도
3. agreement_score 부호 일치 5/5, 4/5, 3/5 시나리오
4. 시장 분리 (KOSPI / KOSDAQ 독립)
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from collectors import supply_demand_history as sdh
from collectors.supply_demand_history import (
    SupplyRow,
    agreement_score,
    get_supply_60d,
    refresh_supply_demand_today,
    upsert_supply_row,
)
from core.db.connection import Database, reset_db


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    db = Database(tmp_path / "test_supply_demand_history.sqlite")
    monkeypatch.setattr(sdh, "get_db", lambda: db)
    return db


class _FakeKIS:
    """KIS market_investor_total mock — pre-set 응답."""

    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    async def __aenter__(self) -> "_FakeKIS":
        return self

    async def __aexit__(self, *a) -> None:
        pass

    async def market_investor_total(self, market: str) -> dict:
        self.calls.append(market)
        return self.responses[market]


# ---------------------------------------------------------------------------
# 1. refresh upsert (mock KIS) + 멱등성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_upserts_both_markets(isolated_db: Database) -> None:
    fake = _FakeKIS({
        "kospi": {
            "market": "kospi",
            "individual_net_amount_m": -1_000,
            "foreign_net_amount_m": 5_000,
            "institution_net_amount_m": -4_000,
            "fin_invest_net_amount_m": -800,
            "pension_net_amount_m": 200,
        },
        "kosdaq": {
            "market": "kosdaq",
            "individual_net_amount_m": 800,
            "foreign_net_amount_m": -300,
            "institution_net_amount_m": -500,
            "fin_invest_net_amount_m": -100,
            "pension_net_amount_m": -50,
        },
    })
    result = await refresh_supply_demand_today(kis=fake)
    assert sorted(result["refreshed"]) == ["KOSDAQ", "KOSPI"]
    assert result["failures"] == []

    rows = isolated_db.fetch_all(
        "SELECT market, foreign_net, institution_net, pension_net "
        "FROM supply_demand_history WHERE date = ? ORDER BY market",
        (sdh._today_kst_str(),),
    )
    assert len(rows) == 2
    kospi_row = next(r for r in rows if r["market"] == "KOSPI")
    assert kospi_row["foreign_net"] == 5_000
    assert kospi_row["pension_net"] == 200
    kosdaq_row = next(r for r in rows if r["market"] == "KOSDAQ")
    assert kosdaq_row["foreign_net"] == -300

    # 멱등성: 다시 호출 시 행 수 그대로
    await refresh_supply_demand_today(kis=fake)
    n = isolated_db.fetch_one(
        "SELECT COUNT(*) AS n FROM supply_demand_history WHERE date = ?",
        (sdh._today_kst_str(),),
    )["n"]
    assert n == 2


# ---------------------------------------------------------------------------
# 2. get_supply_60d 60일 sum 정확도
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_supply_60d_sums_correctly(isolated_db: Database) -> None:
    # 60 영업일 적재. 각 row 동일 net → 60 sum = row * 60
    base = datetime(2026, 3, 1).date()
    for i in range(60):
        d = base + timedelta(days=i)
        # 평일 매핑 X (테스트는 단순 날짜 기반)
        upsert_supply_row(SupplyRow(
            date=d.strftime("%Y-%m-%d"),
            market="KOSPI",
            foreign_net=100,
            institution_net=-50,
            individual_net=-40,
            financial_inv_net=-10,
            pension_net=0,
        ))

    result = await get_supply_60d("KOSPI")
    assert result["market"] == "KOSPI"
    assert result["actual_days"] == 60
    assert result["foreign_net_60d"] == 100 * 60
    assert result["institution_net_60d"] == -50 * 60
    assert result["individual_net_60d"] == -40 * 60
    assert result["pension_net_60d"] == 0


# ---------------------------------------------------------------------------
# 3. agreement_score 부호 일치 분기
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nets,expected",
    [
        ([10, 20, 30, 40, 50], 10.0),    # 5/5 동일 부호 (+)
        ([-10, -20, -30, -40, -50], 10.0),  # 5/5 동일 부호 (-)
        ([10, 20, 30, 40, -50], 8.0),    # 4/5 (+) + 1 (-)
        ([10, 20, 30, -40, -50], 6.0),   # 3/5 (+) + 2 (-)
        ([10, 20, -30, -40, -50], 6.0),  # 3/5 (-) + 2 (+) → still 3/5 majority
        ([0, 0, 0, 0, 0], 10.0),         # 모두 0 (특이 케이스)
    ],
)
def test_agreement_score_branches(nets: list[int], expected: float) -> None:
    assert agreement_score(nets) == expected


# ---------------------------------------------------------------------------
# 4. KOSPI / KOSDAQ 독립 적재 + 조회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_markets_isolated(isolated_db: Database) -> None:
    upsert_supply_row(SupplyRow(
        date="2026-05-15", market="KOSPI",
        foreign_net=1000, institution_net=-500, individual_net=-400,
        financial_inv_net=-100, pension_net=0,
    ))
    upsert_supply_row(SupplyRow(
        date="2026-05-15", market="KOSDAQ",
        foreign_net=-200, institution_net=100, individual_net=120,
        financial_inv_net=-20, pension_net=0,
    ))

    kospi = await get_supply_60d("KOSPI")
    kosdaq = await get_supply_60d("KOSDAQ")
    assert kospi["foreign_net_60d"] == 1000
    assert kosdaq["foreign_net_60d"] == -200
    # 시장 분리 — 절대 섞이지 않음
    assert kospi["actual_days"] == 1
    assert kosdaq["actual_days"] == 1
