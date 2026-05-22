"""INFRA-SNAPSHOT-EXTEND-001 — sector_rs collector 4 케이스.

1. rs_score 정규화 (excess +/- 0 → 5점, +10% → 10점, -10% → 0점, clamp)
2. 벤치마크 KOSPI chart 부재 시 빈 list 반환
3. partial ETF chart 부재 시 해당 섹터 skip (회귀 없이 나머지만 반환)
4. 결과 rs_score 내림차순 정렬
"""
from __future__ import annotations

from datetime import date as _date
from datetime import timedelta

import pytest

from collectors import sector_rs as sr
from collectors.charts import persist_ohlcv_to_db
from collectors.sector_rs import (
    SectorRS,
    _rs_score_from_excess,
    compute_sector_rs,
)
from core.db.connection import Database, reset_db


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    db = Database(tmp_path / "test_sector_rs.sqlite")
    from collectors import charts as ch_mod
    monkeypatch.setattr(ch_mod, "get_db", lambda: db)
    return db


def _bars_with_return(ticker_close_start: float, return_pct_60d: float, days: int = 80) -> list[dict]:
    """선형 합성. 60일 후 수익률이 return_pct_60d 가 되도록.

    days >= 60 보장. 65 일이면 -65 위치가 start, -1 위치가 end.
    """
    end_close = ticker_close_start * (1 + return_pct_60d / 100)
    bars = []
    d = _date(2025, 1, 2)
    for i in range(days):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        # i=0 → ticker_close_start, i=days-1 → end_close 도달 (선형 보간)
        # 단 RS 계산은 close[-60] 기준 — close[-60] 이 정확히 ticker_close_start 가 되도록 처음 (days-60) 봉을 평탄하게.
        if i < days - 60:
            close = ticker_close_start
        else:
            j = i - (days - 60)
            close = ticker_close_start + (end_close - ticker_close_start) * (j / 59)
        bars.append({
            "date": d.strftime("%Y-%m-%d"),
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1_000_000,
            "value": int(close * 1_000_000),
            "change_rate": 0.0,
        })
        d += timedelta(days=1)
    return bars


# ---------------------------------------------------------------------------
# 1. rs_score 정규화 공식
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "excess,expected",
    [
        (0.0, 5.0),
        (10.0, 10.0),
        (-10.0, 0.0),
        (20.0, 10.0),     # clamp
        (-20.0, 0.0),     # clamp
        (5.0, 7.5),
    ],
)
def test_rs_score_from_excess(excess: float, expected: float) -> None:
    assert _rs_score_from_excess(excess) == expected


# ---------------------------------------------------------------------------
# 2. 벤치마크 (KOSPI) chart 부재 → 빈 list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_benchmark_missing_returns_empty(isolated_db: Database) -> None:
    # KOSPI(0001) chart 적재 X. ETF 만 있어도 빈 list.
    persist_ohlcv_to_db("091160", _bars_with_return(10_000, 5.0), adjusted=True)
    result = await compute_sector_rs([("091160", "KODEX 반도체")])
    assert result == []


# ---------------------------------------------------------------------------
# 3. Partial ETF chart 부재 → 해당 섹터 skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_etf_missing_skips(isolated_db: Database) -> None:
    # 벤치마크 + 1 ETF 만 적재, 다른 ETF 는 부재
    persist_ohlcv_to_db("0001", _bars_with_return(2500.0, 0.0), adjusted=True)
    persist_ohlcv_to_db("091160", _bars_with_return(10_000, 10.0), adjusted=True)

    result = await compute_sector_rs([
        ("091160", "KODEX 반도체"),
        ("999999", "(없는 ETF)"),
    ])
    assert len(result) == 1
    assert result[0].sector == "KODEX 반도체"
    # excess = 10% - 0% = 10 → rs_score 10
    assert result[0].rs_score == 10.0


# ---------------------------------------------------------------------------
# 4. 내림차순 정렬 + rs_ratio 정합
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_results_sorted_desc(isolated_db: Database) -> None:
    persist_ohlcv_to_db("0001", _bars_with_return(2500.0, 0.0), adjusted=True)        # KOSPI 0%
    persist_ohlcv_to_db("A", _bars_with_return(10_000, 5.0), adjusted=True)            # +5% excess
    persist_ohlcv_to_db("B", _bars_with_return(10_000, -5.0), adjusted=True)           # -5%
    persist_ohlcv_to_db("C", _bars_with_return(10_000, 15.0), adjusted=True)           # +15%

    result = await compute_sector_rs([
        ("A", "AlphaSector"),
        ("B", "BetaSector"),
        ("C", "GammaSector"),
    ])
    assert len(result) == 3
    # 내림차순 = C(+15) > A(+5) > B(-5)
    assert result[0].sector == "GammaSector"
    assert result[1].sector == "AlphaSector"
    assert result[2].sector == "BetaSector"
    # rs_score 가 내림차순
    scores = [r.rs_score for r in result]
    assert scores == sorted(scores, reverse=True)
    # rs_ratio 정합 (excess return)
    assert abs(result[0].rs_ratio - 15.0) < 0.1
    assert abs(result[2].rs_ratio - (-5.0)) < 0.1
