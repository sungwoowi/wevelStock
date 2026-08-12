"""섹터 RS (Relative Strength) collector (INFRA-SNAPSHOT-EXTEND-001 B 카테고리).

stock_picker 의 S-Score `rs` 축 + buy_score `L` (Leader) 축 base.
14 섹터 ETF (kr_sectors.DEFAULT_TRACKED_ETFS) 의 60 일 수익률을 KOSPI(0001)
60 일 수익률 대비 excess return 으로 환산 → 0~10 점수.

흐름:
  1. KOSPI(0001) chart_ohlcv 의 최근 60 봉 close 시계열 read.
  2. 14 섹터 ETF 각각 chart_ohlcv 의 최근 60 봉 close read.
  3. 각 ETF excess_return = etf_return_60d - kospi_return_60d.
  4. rs_score = clamp(5 + excess_return / 2, 0, 10).
     excess +10% = 10 점 / 0% = 5 점 / -10% = 0 점.
     (SLOT S2 — production 검증 시 정규화 공식 정정)
  5. DB 저장 X — 호출 시점 chart_ohlcv read 만으로 충분 (lazy compute).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from collectors.charts import load_ohlcv_from_db
from collectors.kr_sectors import ALL_TRACKED_ETFS
from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)

_BENCHMARK_TICKER = "0001"          # KOSPI
_WINDOW_BARS = 60                   # 60 거래일

# 시장별 RS 벤치마크 (ADVISOR-CORE-001 M1-c).
#   그전까지 섹터 RS 는 market 인자와 무관하게 **항상 KOSPI 대비**로 계산됐다. 코스닥이 더
#   강한 국면(2026-08-10: 코스닥 상승종목 86% vs 코스피 79%)에서 코스닥 섹터를 못 보던 결함.
BENCHMARK_BY_MARKET: dict[str, str] = {"KOSPI": "0001", "KOSDAQ": "1001"}


@dataclass
class SectorRS:
    """compute_sector_rs 결과 — 1 섹터 RS 풀세트."""

    sector: str          # "AI반도체"
    etf_ticker: str      # "390390"
    rs_score: float      # 0~10 (5 = KOSPI 동행)
    return_60d: float    # 섹터 ETF 60일 수익률 (%)
    kospi_return_60d: float
    rs_ratio: float      # excess return (etf_return - kospi_return)


def _return_60d_from_df(df: pd.DataFrame, window: int = _WINDOW_BARS) -> float | None:
    """최근 window 봉 close 수익률 %. 데이터 부족 시 None."""
    if df is None or df.empty or "close" not in df.columns:
        return None
    if len(df) < window:
        return None
    end = df["close"].iloc[-1]
    start = df["close"].iloc[-window]
    if start is None or start <= 0:
        return None
    return float((end - start) / start * 100)


def _rs_score_from_excess(excess_return_pct: float) -> float:
    """excess return % → 0~10 score. 선형 변환 + clamp.

    +10% → 10, 0% → 5, -10% → 0. SLOT S2 = production 검증 시 정정.
    """
    raw = 5.0 + excess_return_pct / 2.0
    return max(0.0, min(10.0, round(raw, 2)))


async def compute_sector_rs(
    etfs: list[tuple[str, str]] | None = None,
    *,
    market: str | None = None,
    benchmark_ticker: str | None = None,
    window_bars: int = _WINDOW_BARS,
) -> list[SectorRS]:
    """14 섹터 ETF + KOSPI(0001) 60일 RS 계산. rs_score 내림차순 정렬.

    Args:
        etfs: (ticker, name) tuple list. None 이면 ALL_TRACKED_ETFS.
        market: "KOSPI" | "KOSDAQ" — 벤치마크 지수를 시장에 맞춰 고른다(M1-c).
        benchmark_ticker: 벤치마크 직접 지정 (market 보다 우선).
        window_bars: RS 윈도우. 기본 60 거래일.

    Returns:
        SectorRS list. ETF chart 부재 시 해당 섹터 skip + log.warning.
        벤치마크 (KOSPI) chart 부재 또는 return 산출 불가 시 빈 list.
    """
    etf_list = etfs if etfs is not None else ALL_TRACKED_ETFS
    # market 지정 시 그 시장의 지수를 벤치마크로 (미지정·미상 시장은 KOSPI 폴백).
    if benchmark_ticker is None:
        benchmark_ticker = BENCHMARK_BY_MARKET.get(market or "", _BENCHMARK_TICKER)

    benchmark_df = load_ohlcv_from_db(benchmark_ticker, limit=window_bars + 10)
    kospi_return = _return_60d_from_df(benchmark_df, window=window_bars)
    if kospi_return is None:
        log.warning(
            "sector_rs_benchmark_unavailable",
            ticker=benchmark_ticker,
            bars=len(benchmark_df) if benchmark_df is not None else 0,
        )
        return []

    results: list[SectorRS] = []
    for ticker, name in etf_list:
        etf_df = load_ohlcv_from_db(ticker, limit=window_bars + 10)
        etf_return = _return_60d_from_df(etf_df, window=window_bars)
        if etf_return is None:
            log.warning("sector_rs_etf_unavailable", ticker=ticker, sector=name)
            continue
        excess = etf_return - kospi_return
        results.append(SectorRS(
            sector=name,
            etf_ticker=ticker,
            rs_score=_rs_score_from_excess(excess),
            return_60d=round(etf_return, 4),
            kospi_return_60d=round(kospi_return, 4),
            rs_ratio=round(excess, 4),
        ))

    results.sort(key=lambda r: r.rs_score, reverse=True)
    return results


# ---------------------------------------------------------------------------
# DB layer — sector_rs_snapshot (MARKET-VIEW-SYNTHESIS-001)
# ---------------------------------------------------------------------------
# 순환매(어제 대비 RS 이동) 판단을 위한 일자 스냅샷 누적. compute_sector_rs 는
# lazy compute(저장 X) 였으나, rotation 의 본질=*이동* 이라 다일 시계열이 선행이어야 한다.


def persist_sector_rs(date_str: str, market: str, rows: list[SectorRS]) -> None:
    """sector_rs_snapshot ON CONFLICT REPLACE 멱등 upsert (장후 1회 적재)."""
    if not rows:
        return
    db = get_db()
    with db.connect() as conn:
        conn.executemany(
            "INSERT INTO sector_rs_snapshot "
            "(date, market, sector, etf_ticker, rs_score, return_60d, kospi_return_60d, rs_ratio) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(date, market, sector) DO UPDATE SET "
            " etf_ticker=excluded.etf_ticker, rs_score=excluded.rs_score, "
            " return_60d=excluded.return_60d, kospi_return_60d=excluded.kospi_return_60d, "
            " rs_ratio=excluded.rs_ratio",
            [
                (date_str, market, r.sector, r.etf_ticker, r.rs_score,
                 r.return_60d, r.kospi_return_60d, r.rs_ratio)
                for r in rows
            ],
        )


def _row_to_sector_rs(row: Any) -> SectorRS:
    return SectorRS(
        sector=row["sector"],
        etf_ticker=row["etf_ticker"],
        rs_score=float(row["rs_score"]),
        return_60d=float(row["return_60d"]) if row["return_60d"] is not None else 0.0,
        kospi_return_60d=float(row["kospi_return_60d"]) if row["kospi_return_60d"] is not None else 0.0,
        rs_ratio=float(row["rs_ratio"]) if row["rs_ratio"] is not None else 0.0,
    )


def load_sector_rs_snapshot(date_str: str, market: str) -> list[SectorRS]:
    """특정 일자 sector_rs_snapshot read. 없으면 빈 list. rs_score 내림차순."""
    db = get_db()
    rows = db.fetch_all(
        "SELECT * FROM sector_rs_snapshot WHERE date = ? AND market = ? "
        "ORDER BY rs_score DESC",
        (date_str, market),
    )
    return [_row_to_sector_rs(r) for r in rows]


def load_prev_sector_rs(
    date_str: str, market: str, *, window_days: int
) -> tuple[str, list[SectorRS]] | None:
    """순환매 비교 기준 = `date_str` 보다 최소 window_days 이전의 *가장 최근* 스냅샷.

    정확히 window_days 전 거래일 데이터가 없을 수 있으므로(휴장 등) 그 이전 중
    가장 가까운 날짜를 채택한다. 누적이 부족하면 None (첫날 graceful).

    Returns:
        (snapshot_date, rows) 또는 None.
    """
    db = get_db()
    cutoff_row = db.fetch_one(
        "SELECT DISTINCT date FROM sector_rs_snapshot "
        "WHERE market = ? AND date <= date(?, ?) "
        "ORDER BY date DESC LIMIT 1",
        (market, date_str, f"-{int(window_days)} days"),
    )
    if cutoff_row is None:
        return None
    prev_date = cutoff_row["date"]
    return prev_date, load_sector_rs_snapshot(prev_date, market)


async def refresh_sector_rs_all_markets(
    date_str: str,
    *,
    etfs: list[tuple[str, str]] | None = None,
    markets: tuple[str, ...] = ("KOSPI", "KOSDAQ"),
) -> int:
    """양 시장 섹터 RS 계산 + 영속 (ADVISOR-CORE-001 M1-c). 적재된 시장 수 반환.

    같은 테마 ETF 라도 벤치마크가 다르면 초과수익이 달라진다 — 코스피 대비로는 회피인
    섹터가 코스닥 대비로는 강세일 수 있다. 시장별 독립 graceful (한쪽 지수 OHLCV 가
    없어도 나머지는 적재).
    """
    done = 0
    for market in markets:
        try:
            rows = await compute_sector_rs(etfs, market=market)
            if not rows:
                log.warning("sector_rs_market_empty", market=market, date=date_str)
                continue
            persist_sector_rs(date_str, market, rows)
            done += 1
            log.info("sector_rs_refreshed", market=market, date=date_str, sectors=len(rows))
        except Exception as e:  # noqa: BLE001 — 한 시장 실패가 나머지를 막지 않음
            log.warning("sector_rs_market_failed", market=market, error=str(e))
    return done
