"""INFRA-CHART-DATA-001 — chart_ohlcv DB 멱등성 + schema_version 5 적재 검증."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from collectors import charts as ch_mod
from collectors.charts import (
    get_db_last_fetched_at,
    load_ohlcv_from_db,
    persist_ohlcv_to_db,
    reset_cache,
)
from core.db.connection import Database, reset_db


def _bars(start: date, days: int) -> list[dict[str, Any]]:
    out = []
    d = start
    for i in range(days):
        out.append({
            "date": d.strftime("%Y-%m-%d"),
            "open": 100 + i,
            "high": 102 + i,
            "low": 99 + i,
            "close": 101 + i,
            "volume": 1_000_000,
            "value": 100_000_000,
            "change_rate": 1.0,
        })
        d += timedelta(days=1)
    return out


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    reset_cache()
    db = Database(tmp_path / "test_chart_db.sqlite")
    monkeypatch.setattr(ch_mod, "get_db", lambda: db)
    return db


# ---------------------------------------------------------------------------
# 1. ON CONFLICT REPLACE 멱등성
# ---------------------------------------------------------------------------


def test_upsert_idempotent_replace(isolated_db: Database) -> None:
    bars = _bars(date(2025, 1, 6), 10)
    persist_ohlcv_to_db("005930", bars, adjusted=True)
    n1 = isolated_db.fetch_one(
        "SELECT COUNT(*) AS n FROM chart_ohlcv WHERE ticker = ?", ("005930",)
    )["n"]
    assert n1 == 10

    # 같은 (ticker, date) 다른 close → REPLACE
    bars2 = _bars(date(2025, 1, 6), 10)
    bars2[0]["close"] = 999.0
    persist_ohlcv_to_db("005930", bars2, adjusted=True)
    n2 = isolated_db.fetch_one(
        "SELECT COUNT(*) AS n FROM chart_ohlcv WHERE ticker = ?", ("005930",)
    )["n"]
    assert n2 == 10  # 행 수 그대로
    row = isolated_db.fetch_one(
        "SELECT close FROM chart_ohlcv WHERE ticker = ? AND date = ?",
        ("005930", "2025-01-06"),
    )
    assert row["close"] == 999.0  # 덮어쓰기


# ---------------------------------------------------------------------------
# 2. schema_version 5 적재 확인 (신규 DB)
# ---------------------------------------------------------------------------


def test_schema_version_5_present(isolated_db: Database) -> None:
    rows = isolated_db.fetch_all("SELECT version FROM schema_version ORDER BY version")
    versions = [r["version"] for r in rows]
    assert 5 in versions
    # chart_ohlcv 테이블 존재 확인
    rows = isolated_db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chart_ohlcv'"
    )
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# 3. load_ohlcv_from_db 정순 정렬 + get_db_last_fetched_at 정합
# ---------------------------------------------------------------------------


def test_load_orders_ascending_and_last_fetched(isolated_db: Database) -> None:
    bars = _bars(date(2025, 1, 6), 30)
    persist_ohlcv_to_db("005930", bars, adjusted=True)

    df = load_ohlcv_from_db("005930", limit=1825)
    # 정순 (오름차순) 정렬
    assert df.index.is_monotonic_increasing
    assert len(df) == 30
    assert df["close"].iloc[0] == 101.0
    assert df["close"].iloc[-1] == 130.0

    # last fetched_at 메타
    last_date, hours_ago = get_db_last_fetched_at("005930")
    assert last_date == bars[-1]["date"]
    assert hours_ago is not None
    assert hours_ago < 1  # 방금 적재
