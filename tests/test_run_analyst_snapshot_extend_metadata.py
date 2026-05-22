"""INFRA-SNAPSHOT-EXTEND-001 — run_analyst metadata 4 키 노출 4 케이스.

SPEC § 13:
- snapshot_extend_failures: list[str]
- market_macro_source: "db" | "computed" | "stale" | "unknown" | "mixed"
- sector_rs_count: int (정상 14)
- supply_60d_age_days: int | None
"""
from __future__ import annotations

import time

import pytest

from collectors.snapshot import MarketSnapshot
from collectors.supply_demand_history import SupplyRow, upsert_supply_row
from core.db.connection import Database, reset_db
from core.inference.run_analyst import _snapshot_extend_metadata


def _empty_snapshot(**overrides) -> MarketSnapshot:
    base = dict(
        fetched_at=time.time(),
        fetched_at_iso="2026-05-21T18:00:00+09:00",
        overnight={}, fear_greed={}, kr_indices={}, kr_supply={},
        kr_futures_supply={}, kr_sectors={}, kr_leading={},
    )
    base.update(overrides)
    return MarketSnapshot(**base)


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    db = Database(tmp_path / "test_run_analyst_metadata.sqlite")
    from collectors import supply_demand_history as sdh_mod
    monkeypatch.setattr(sdh_mod, "get_db", lambda: db)
    return db


# ---------------------------------------------------------------------------
# 1. 빈 snapshot → unknown / 0 / None
# ---------------------------------------------------------------------------


def test_metadata_empty_snapshot(isolated_db: Database) -> None:
    meta = _snapshot_extend_metadata(_empty_snapshot())
    assert meta["snapshot_extend_failures"] == []
    assert meta["market_macro_source"] == "unknown"
    assert meta["sector_rs_count"] == 0
    assert meta["supply_60d_age_days"] is None


# ---------------------------------------------------------------------------
# 2. 둘 다 db 소스 → "db"
# ---------------------------------------------------------------------------


def test_metadata_both_markets_db_source(isolated_db: Database) -> None:
    macro = {
        "KOSPI": {"source": "db"},
        "KOSDAQ": {"source": "db"},
    }
    meta = _snapshot_extend_metadata(_empty_snapshot(market_macro=macro))
    assert meta["market_macro_source"] == "db"


# ---------------------------------------------------------------------------
# 3. 시장 source 불일치 → "mixed"
# ---------------------------------------------------------------------------


def test_metadata_mixed_source(isolated_db: Database) -> None:
    macro = {
        "KOSPI": {"source": "db"},
        "KOSDAQ": {"source": "computed"},
    }
    meta = _snapshot_extend_metadata(_empty_snapshot(market_macro=macro))
    assert meta["market_macro_source"] == "mixed"


# ---------------------------------------------------------------------------
# 4. 14 섹터 + DB supply row 적재 → count 14 + age 0
# ---------------------------------------------------------------------------


def test_metadata_full_extend(isolated_db: Database) -> None:
    sector_rs = [{"sector": f"sec_{i}", "rs_score": 5.0} for i in range(14)]
    snapshot_extend_failures = ["sector_rs"]  # 의도된 failure 라벨 노출 검증

    # 오늘 supply row 적재 → age = 0
    from collectors.supply_demand_history import _today_kst_str
    upsert_supply_row(SupplyRow(
        date=_today_kst_str(), market="KOSPI",
        foreign_net=100, institution_net=-50, individual_net=-40,
        financial_inv_net=-10, pension_net=0,
    ))

    snap = _empty_snapshot(
        sector_rs=sector_rs,
        snapshot_extend_failures=snapshot_extend_failures,
    )
    meta = _snapshot_extend_metadata(snap)
    assert meta["sector_rs_count"] == 14
    assert meta["snapshot_extend_failures"] == ["sector_rs"]
    assert meta["supply_60d_age_days"] == 0
