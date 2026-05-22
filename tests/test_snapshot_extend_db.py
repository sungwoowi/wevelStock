"""INFRA-SNAPSHOT-EXTEND-001 — v7 DB 자동 회귀 보호 4 케이스.

1. schema_version 7 적재 확인 (신규 DB)
2. 신규 2 테이블 존재 + 컬럼 정합
3. market_macro_snapshot ON CONFLICT REPLACE 멱등
4. supply_demand_history ON CONFLICT REPLACE 멱등 + 시장 분리
"""
from __future__ import annotations

import pytest

from collectors import market_macro as mm
from collectors import supply_demand_history as sdh
from collectors.market_macro import MarketMacro, upsert_market_macro
from collectors.supply_demand_history import SupplyRow, upsert_supply_row
from core.db.connection import Database, reset_db


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    db = Database(tmp_path / "test_snapshot_extend_db.sqlite")
    monkeypatch.setattr(mm, "get_db", lambda: db)
    monkeypatch.setattr(sdh, "get_db", lambda: db)
    return db


# ---------------------------------------------------------------------------
# 1. schema_version 7 적재
# ---------------------------------------------------------------------------


def test_schema_version_7_present(isolated_db: Database) -> None:
    rows = isolated_db.fetch_all("SELECT version FROM schema_version ORDER BY version")
    versions = [r["version"] for r in rows]
    assert 7 in versions
    # 7 이 최신 — 더 큰 버전이 박혀 있으면 안 됨
    assert max(versions) == 7


# ---------------------------------------------------------------------------
# 2. 신규 2 테이블 + 컬럼 정합
# ---------------------------------------------------------------------------


def test_new_tables_and_columns(isolated_db: Database) -> None:
    tables = isolated_db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name IN ('market_macro_snapshot', 'supply_demand_history') ORDER BY name"
    )
    assert [r["name"] for r in tables] == ["market_macro_snapshot", "supply_demand_history"]

    # market_macro_snapshot 18 컬럼 (SPEC 명세)
    cols_macro = isolated_db.fetch_all("PRAGMA table_info(market_macro_snapshot)")
    macro_names = {c["name"] for c in cols_macro}
    expected_macro = {
        "date", "market", "index_close", "ma_36m", "ma_60m", "position",
        "ma_20d", "ma_60d", "ma20_slope_pct_5d", "ma60_slope_pct_20d", "trend",
        "advancing", "declining", "unchanged", "breadth_ratio",
        "is_distribution_day", "change_pct", "volume_change_pct",
    }
    assert macro_names == expected_macro

    # supply_demand_history 8 컬럼
    cols_supply = isolated_db.fetch_all("PRAGMA table_info(supply_demand_history)")
    supply_names = {c["name"] for c in cols_supply}
    expected_supply = {
        "date", "market", "foreign_net", "institution_net", "individual_net",
        "financial_inv_net", "pension_net", "source",
    }
    assert supply_names == expected_supply


# ---------------------------------------------------------------------------
# 3. market_macro_snapshot ON CONFLICT REPLACE 멱등
# ---------------------------------------------------------------------------


def test_market_macro_upsert_idempotent(isolated_db: Database) -> None:
    macro_v1 = MarketMacro(
        date="2026-05-21", market="KOSPI",
        index_close=2700.0, ma_36m=2500.0, ma_60m=2400.0, position="above_both",
        ma_20d=2680.0, ma_60d=2650.0,
        ma20_slope_pct_5d=1.2, ma60_slope_pct_20d=0.8, trend="uptrend",
        advancing=500, declining=350, unchanged=100, breadth_ratio=0.588,
        is_distribution_day=False, change_pct=0.5, volume_change_pct=2.0,
        distribution_count_25d=2,
    )
    upsert_market_macro(macro_v1)
    n = isolated_db.fetch_one(
        "SELECT COUNT(*) AS n FROM market_macro_snapshot WHERE date = ? AND market = ?",
        ("2026-05-21", "KOSPI"),
    )["n"]
    assert n == 1

    # 같은 (date, market) 의 다른 값 → REPLACE
    macro_v2 = MarketMacro(
        date="2026-05-21", market="KOSPI",
        index_close=2750.0, ma_36m=2510.0, ma_60m=2410.0, position="above_both",
        ma_20d=2700.0, ma_60d=2660.0,
        ma20_slope_pct_5d=1.5, ma60_slope_pct_20d=1.0, trend="uptrend",
        advancing=600, declining=300, unchanged=80, breadth_ratio=0.667,
        is_distribution_day=True, change_pct=-0.3, volume_change_pct=8.0,
        distribution_count_25d=3,
    )
    upsert_market_macro(macro_v2)

    rows = isolated_db.fetch_all(
        "SELECT index_close, breadth_ratio, is_distribution_day "
        "FROM market_macro_snapshot WHERE date = ? AND market = ?",
        ("2026-05-21", "KOSPI"),
    )
    assert len(rows) == 1                       # 행 수 그대로
    assert rows[0]["index_close"] == 2750.0     # 덮어쓰기
    assert rows[0]["breadth_ratio"] == 0.667
    assert rows[0]["is_distribution_day"] == 1


# ---------------------------------------------------------------------------
# 4. supply_demand_history ON CONFLICT REPLACE 멱등 + 시장 분리
# ---------------------------------------------------------------------------


def test_supply_demand_upsert_and_market_isolation(isolated_db: Database) -> None:
    row_kospi_v1 = SupplyRow(
        date="2026-05-21", market="KOSPI",
        foreign_net=1_000, institution_net=-500, individual_net=-400,
        financial_inv_net=-100, pension_net=0,
    )
    row_kosdaq_v1 = SupplyRow(
        date="2026-05-21", market="KOSDAQ",
        foreign_net=-200, institution_net=100, individual_net=120,
        financial_inv_net=-20, pension_net=0,
    )
    upsert_supply_row(row_kospi_v1)
    upsert_supply_row(row_kosdaq_v1)

    # 시장 분리: 같은 날짜라도 (date, market) 복합 PK 라 2 row
    n = isolated_db.fetch_one(
        "SELECT COUNT(*) AS n FROM supply_demand_history WHERE date = ?",
        ("2026-05-21",),
    )["n"]
    assert n == 2

    # KOSPI 만 REPLACE → KOSDAQ 영향 X
    row_kospi_v2 = SupplyRow(
        date="2026-05-21", market="KOSPI",
        foreign_net=2_000, institution_net=-1_000, individual_net=-800,
        financial_inv_net=-200, pension_net=0,
    )
    upsert_supply_row(row_kospi_v2)

    rows = isolated_db.fetch_all(
        "SELECT market, foreign_net FROM supply_demand_history "
        "WHERE date = ? ORDER BY market",
        ("2026-05-21",),
    )
    by_market = {r["market"]: r["foreign_net"] for r in rows}
    assert by_market["KOSPI"] == 2_000      # 덮어쓰기
    assert by_market["KOSDAQ"] == -200      # 변경 없음
