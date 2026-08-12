"""코스닥 섹터 RS (ADVISOR-CORE-001 M1-c).

지금까지 섹터 RS 는 **항상 KOSPI 벤치마크**로만 계산됐다. 코스닥이 더 강한 국면
(2026-08-10: 코스닥 상승종목 86% vs 코스피 79%)에서 코스닥 섹터를 못 보던 결함.

외부 호출 0 — OHLCV 는 DB fixture 로 주입.
"""
from __future__ import annotations

import pytest

from collectors import sector_rs as srs
from core.db.connection import Database, reset_db


@pytest.fixture()
def db(tmp_path, monkeypatch):
    reset_db()
    d = Database(tmp_path / "srs.sqlite")
    monkeypatch.setattr(srs, "get_db", lambda: d)
    return d


def _ohlcv(db, ticker: str, start: float, end: float, bars: int = 60) -> None:
    """선형 보간 종가 시계열. **정확히 60봉** — RS 창(60)과 일치시켜야
    60일 수익률이 (end/start - 1)*100 으로 딱 떨어진다."""
    step = (end - start) / (bars - 1)
    rows = []
    for i in range(bars):
        day = f"2026-{(5 + i // 30):02d}-{(i % 30) + 1:02d}"
        px = start + step * i
        rows.append((ticker, day, px, px, px, px, 1000, "2026-08-10T18:00:00"))
    db.executemany(
        "INSERT OR REPLACE INTO chart_ohlcv "
        "(ticker, date, open, high, low, close, volume, fetched_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )


@pytest.fixture(autouse=True)
def _chart_from_db(db, monkeypatch):
    """load_ohlcv_from_db 가 테스트 DB 를 보도록."""
    import pandas as pd

    def _load(ticker: str, limit: int = 100):
        rows = db.fetch_all(
            "SELECT date, close FROM chart_ohlcv WHERE ticker = ? ORDER BY date DESC LIMIT ?",
            (ticker, limit),
        )
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([{"date": r["date"], "close": r["close"]} for r in rows])
        return df.iloc[::-1].reset_index(drop=True)

    monkeypatch.setattr(srs, "load_ohlcv_from_db", _load)


# --- 1. 벤치마크가 시장별로 갈린다 ------------------------------------------


def test_benchmark_map_covers_both_markets() -> None:
    assert srs.BENCHMARK_BY_MARKET["KOSPI"] == "0001"
    assert srs.BENCHMARK_BY_MARKET["KOSDAQ"] == "1001"


async def test_kosdaq_rs_uses_kosdaq_benchmark(db) -> None:
    """같은 ETF 라도 코스피 대비와 코스닥 대비 초과수익이 다르게 나온다."""
    _ohlcv(db, "0001", 100.0, 80.0)     # 코스피 -20%
    _ohlcv(db, "1001", 100.0, 110.0)    # 코스닥 +10%
    _ohlcv(db, "TESTETF", 100.0, 100.0)  # ETF 0%

    kospi = await srs.compute_sector_rs([("TESTETF", "테스트")], market="KOSPI")
    kosdaq = await srs.compute_sector_rs([("TESTETF", "테스트")], market="KOSDAQ")

    assert kospi[0].rs_ratio == pytest.approx(20.0, abs=0.5)    # 0 - (-20)
    assert kosdaq[0].rs_ratio == pytest.approx(-10.0, abs=0.5)  # 0 - (+10)
    assert kospi[0].rs_score > kosdaq[0].rs_score


async def test_unknown_market_falls_back_to_kospi(db) -> None:
    _ohlcv(db, "0001", 100.0, 80.0)
    _ohlcv(db, "TESTETF", 100.0, 100.0)
    rows = await srs.compute_sector_rs([("TESTETF", "테스트")], market="NASDAQ")
    assert rows and rows[0].rs_ratio == pytest.approx(20.0, abs=0.5)


async def test_missing_benchmark_returns_empty(db) -> None:
    _ohlcv(db, "TESTETF", 100.0, 100.0)
    assert await srs.compute_sector_rs([("TESTETF", "테스트")], market="KOSDAQ") == []


# --- 2. 코스닥 ETF 목록 -------------------------------------------------------


def test_kosdaq_etfs_defined_and_disjoint_from_kospi() -> None:
    from collectors.kr_sectors import DEFAULT_TRACKED_ETFS, KOSDAQ_TRACKED_ETFS

    assert len(KOSDAQ_TRACKED_ETFS) >= 4
    kospi_codes = {t for t, _ in DEFAULT_TRACKED_ETFS}
    new_codes = {t for t, _ in KOSDAQ_TRACKED_ETFS}
    assert new_codes - kospi_codes, "코스닥 전용 ETF 가 하나도 없다"


def test_chart_universe_includes_kosdaq_etfs() -> None:
    """OHLCV 갱신 대상에 들어가야 RS 가 계산된다."""
    from collectors.charts import chart_refresh_universe
    from collectors.kr_sectors import KOSDAQ_TRACKED_ETFS

    universe = set(chart_refresh_universe())
    assert "1001" in universe                     # 코스닥 벤치마크
    for ticker, _ in KOSDAQ_TRACKED_ETFS:
        assert ticker in universe, f"{ticker} 미포함"


# --- 3. 양 시장 동시 갱신 -----------------------------------------------------


async def test_refresh_persists_both_markets(db) -> None:
    _ohlcv(db, "0001", 100.0, 90.0)
    _ohlcv(db, "1001", 100.0, 110.0)
    _ohlcv(db, "E1", 100.0, 130.0)

    n = await srs.refresh_sector_rs_all_markets(
        "2026-08-10", etfs=[("E1", "테마1")],
    )
    assert n == 2
    for market, expected in (("KOSPI", 40.0), ("KOSDAQ", 20.0)):
        rows = db.fetch_all(
            "SELECT sector, rs_ratio FROM sector_rs_snapshot WHERE date=? AND market=?",
            ("2026-08-10", market),
        )
        assert len(rows) == 1
        assert rows[0]["rs_ratio"] == pytest.approx(expected, abs=0.5)


async def test_refresh_is_graceful_when_one_market_missing(db) -> None:
    """코스닥 벤치마크가 없어도 코스피는 적재된다."""
    _ohlcv(db, "0001", 100.0, 90.0)
    _ohlcv(db, "E1", 100.0, 130.0)
    n = await srs.refresh_sector_rs_all_markets("2026-08-10", etfs=[("E1", "테마1")])
    assert n == 1
    assert db.fetch_all(
        "SELECT 1 FROM sector_rs_snapshot WHERE market='KOSPI'"
    )


async def test_refresh_is_idempotent(db) -> None:
    _ohlcv(db, "0001", 100.0, 90.0)
    _ohlcv(db, "1001", 100.0, 110.0)
    _ohlcv(db, "E1", 100.0, 130.0)
    await srs.refresh_sector_rs_all_markets("2026-08-10", etfs=[("E1", "테마1")])
    await srs.refresh_sector_rs_all_markets("2026-08-10", etfs=[("E1", "테마1")])
    rows = db.fetch_all("SELECT * FROM sector_rs_snapshot WHERE date='2026-08-10'")
    assert len(rows) == 2   # KOSPI 1 + KOSDAQ 1


# --- 4. 판세가 시장별 섹터를 읽는다 -------------------------------------------


def test_stance_sectors_are_not_duplicated_across_markets(db, monkeypatch) -> None:
    """양 시장이 적재돼도 판세 섹터는 한 벤치마크만 읽는다 (중복·모순 차단)."""
    from core.signal import market_stance as ms

    monkeypatch.setattr(ms, "get_db", lambda: db)
    db.execute(
        "INSERT OR REPLACE INTO market_macro_snapshot (date, market, index_close) "
        "VALUES ('2026-08-10','KOSPI',100)"
    )
    # 같은 테마가 시장별로 다른 초과수익을 갖는 실제 상황 (반도체: 코스피 -12 / 코스닥 +1)
    for market, ratio in (("KOSPI", -12.0), ("KOSDAQ", 1.3)):
        db.execute(
            "INSERT OR REPLACE INTO sector_rs_snapshot "
            "(date, market, sector, etf_ticker, rs_score, return_60d, kospi_return_60d, rs_ratio) "
            "VALUES (?,?,?,?,?,?,?,?)",
            ("2026-08-10", market, "반도체", "000000", 5.0, 0.0, 0.0, ratio),
        )
    b = ms.build_stance_facts("2026-08-10", "postclose").sectors
    names = [e.sector for e in b.strong + b.neutral + b.avoid]
    assert names.count("반도체") == 1, "섹터가 시장별로 중복됐다"
    assert b.avoid and b.avoid[0].rs_ratio == pytest.approx(-12.0)   # KOSPI 기준


def test_stance_sectors_fall_back_when_benchmark_market_absent(db, monkeypatch) -> None:
    """기준 시장 행이 없으면 있는 것으로 폴백 (구 데이터 호환)."""
    from core.signal import market_stance as ms

    monkeypatch.setattr(ms, "get_db", lambda: db)
    db.execute(
        "INSERT OR REPLACE INTO market_macro_snapshot (date, market, index_close) "
        "VALUES ('2026-08-10','KOSPI',100)"
    )
    db.execute(
        "INSERT OR REPLACE INTO sector_rs_snapshot "
        "(date, market, sector, etf_ticker, rs_score, return_60d, kospi_return_60d, rs_ratio) "
        "VALUES ('2026-08-10','KOSDAQ','게임','000000',9.0,0.0,0.0,18.0)"
    )
    b = ms.build_stance_facts("2026-08-10", "postclose").sectors
    assert [e.sector for e in b.strong] == ["게임"]
