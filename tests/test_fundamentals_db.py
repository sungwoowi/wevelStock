"""INFRA-FUNDAMENTAL-DATA-001 — fundamentals DB 멱등성 + schema_version 6 검증."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from collectors import fundamentals as fm_mod
from collectors.fundamentals import (
    Fundamentals,
    load_fundamentals_from_db,
    persist_fundamentals_to_db,
    reset_cache,
)
from core.db.connection import Database, reset_db


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    reset_cache()
    db = Database(tmp_path / "test_fundamentals_db.sqlite")
    monkeypatch.setattr(fm_mod, "get_db", lambda: db)
    return db


def _make_fundamentals(
    ticker: str = "005930", eps_ttm: float = 9512.0
) -> Fundamentals:
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return Fundamentals(
        ticker=ticker, market="KS",
        fetched_at=0.0, fetched_at_iso=now_iso,
        eps_ttm=eps_ttm, pe_ratio=12.4, roe=0.142,
        operating_margin=0.187, debt_to_equity=45.3,
        quarterly_revenue=[79.8e12, 75.2e12, 72.5e12, 67.4e12, 67.5e12],
        quarterly_operating_income=[6.7e12, 6.4e12, 5.9e12, 5.2e12, 5.2e12],
        quarterly_eps=[998.0, 935.0, 873.0, 781.0, 781.0],
        quarter_labels=["2026Q1", "2025Q4", "2025Q3", "2025Q2", "2025Q1"],
        source="yfinance", fetched_db_iso=now_iso, stale_hours=0.0,
    )


# ---------------------------------------------------------------------------
# 1. schema_version 6 적재 + fundamentals 테이블 존재
# ---------------------------------------------------------------------------


def test_schema_version_6_present(isolated_db: Database) -> None:
    rows = isolated_db.fetch_all(
        "SELECT version FROM schema_version ORDER BY version"
    )
    versions = [r["version"] for r in rows]
    assert 6 in versions
    # fundamentals 테이블 존재 확인
    rows = isolated_db.fetch_all(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='fundamentals'"
    )
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# 2. ON CONFLICT REPLACE 멱등 upsert
# ---------------------------------------------------------------------------


def test_upsert_idempotent_replace(isolated_db: Database) -> None:
    f1 = _make_fundamentals(eps_ttm=9512.0)
    persist_fundamentals_to_db(f1)
    n1 = isolated_db.fetch_one(
        "SELECT COUNT(*) AS n FROM fundamentals WHERE ticker = ?",
        ("005930",),
    )["n"]
    assert n1 == 1

    # 같은 ticker 다른 값 → REPLACE
    f2 = _make_fundamentals(eps_ttm=10000.0)
    persist_fundamentals_to_db(f2)
    n2 = isolated_db.fetch_one(
        "SELECT COUNT(*) AS n FROM fundamentals WHERE ticker = ?",
        ("005930",),
    )["n"]
    assert n2 == 1  # 행 수 그대로
    row = isolated_db.fetch_one(
        "SELECT eps_ttm FROM fundamentals WHERE ticker = ?",
        ("005930",),
    )
    assert row["eps_ttm"] == 10000.0  # 덮어쓰기


# ---------------------------------------------------------------------------
# 3. quarterly_data JSON round-trip + load_fundamentals_from_db
# ---------------------------------------------------------------------------


def test_quarterly_data_json_roundtrip(isolated_db: Database) -> None:
    f = _make_fundamentals()
    persist_fundamentals_to_db(f)

    loaded = load_fundamentals_from_db("005930")
    assert loaded is not None
    assert loaded.quarter_labels == [
        "2026Q1", "2025Q4", "2025Q3", "2025Q2", "2025Q1",
    ]
    assert loaded.quarterly_revenue == [
        79.8e12, 75.2e12, 72.5e12, 67.4e12, 67.5e12,
    ]
    assert loaded.quarterly_eps == [
        998.0, 935.0, 873.0, 781.0, 781.0,
    ]
    # raw JSON column 직접 확인
    row = isolated_db.fetch_one(
        "SELECT quarterly_data FROM fundamentals WHERE ticker = ?",
        ("005930",),
    )
    qd = json.loads(row["quarterly_data"])
    assert qd["quarter_labels"] == [
        "2026Q1", "2025Q4", "2025Q3", "2025Q2", "2025Q1",
    ]
