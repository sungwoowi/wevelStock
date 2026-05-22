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
from collectors.kr_sectors import DEFAULT_TRACKED_ETFS
from core.logging import get_logger

log = get_logger(__name__)

_BENCHMARK_TICKER = "0001"          # KOSPI
_WINDOW_BARS = 60                   # 60 거래일


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
    benchmark_ticker: str = _BENCHMARK_TICKER,
    window_bars: int = _WINDOW_BARS,
) -> list[SectorRS]:
    """14 섹터 ETF + KOSPI(0001) 60일 RS 계산. rs_score 내림차순 정렬.

    Args:
        etfs: (ticker, name) tuple list. None 이면 DEFAULT_TRACKED_ETFS (14).
        benchmark_ticker: 기준 지수. 기본 KOSPI(0001).
        window_bars: RS 윈도우. 기본 60 거래일.

    Returns:
        SectorRS list. ETF chart 부재 시 해당 섹터 skip + log.warning.
        벤치마크 (KOSPI) chart 부재 또는 return 산출 불가 시 빈 list.
    """
    etf_list = etfs if etfs is not None else DEFAULT_TRACKED_ETFS

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
