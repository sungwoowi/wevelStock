"""INFRA-CHART-DATA-001 — pandas 기본 함수로 Default 6 지표 계산 정확성 검증.

결정론 OHLCV fixture (300봉) → 각 지표가 예상 산식대로 떨어지는지 확인.
NaN/데이터 부족 케이스도 함께 검증.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from collectors.charts import compute_indicators


def _build_fixture_df(n_days: int = 300, base: float = 100.0) -> pd.DataFrame:
    """결정론 OHLCV — close = base 부터 +1 씩 단조 증가."""
    start = datetime(2024, 1, 8)  # 월요일
    dates = []
    closes = []
    d = start
    for i in range(n_days):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        dates.append(d)
        closes.append(base + i)
        d += timedelta(days=1)
    df = pd.DataFrame({
        "date": pd.to_datetime(dates),
        "open": [c - 0.5 for c in closes],
        "high": [c + 1.0 for c in closes],
        "low": [c - 1.0 for c in closes],
        "close": closes,
        "volume": [1_000_000] * n_days,
        "change_rate": [1.0] * n_days,
        "value": [100_000_000] * n_days,
    }).set_index("date")
    return df


# ---------------------------------------------------------------------------
# 1. 일봉 MA — 단조 증가 close 의 N일 평균
# ---------------------------------------------------------------------------


def test_daily_ma_arithmetic() -> None:
    df = _build_fixture_df(n_days=200, base=100.0)
    ind = compute_indicators(df)
    dma = ind["daily_ma"]

    # close = [100, 101, 102, ..., 299]
    # 마지막 4MA = (296+297+298+299)/4 = 297.5
    assert dma["ma4"] == pytest.approx(297.5, rel=1e-6)
    # 마지막 7MA = (293..299)/7 = 296.0
    assert dma["ma7"] == pytest.approx(296.0, rel=1e-6)
    # 마지막 20MA = (280..299)/20 = 289.5
    assert dma["ma20"] == pytest.approx(289.5, rel=1e-6)
    # 마지막 60MA = (240..299)/60 = 269.5
    assert dma["ma60"] == pytest.approx(269.5, rel=1e-6)
    # 마지막 120MA = (180..299)/120 = 239.5
    assert dma["ma120"] == pytest.approx(239.5, rel=1e-6)


# ---------------------------------------------------------------------------
# 2. 주봉 MA — resample('W-FRI') 후 N주 평균
# ---------------------------------------------------------------------------


def test_weekly_ma_resample_and_mean() -> None:
    df = _build_fixture_df(n_days=300, base=100.0)
    ind = compute_indicators(df)
    wma = ind["weekly_ma"]
    # 주봉이 60주 이상 확보돼야 60MA 발행
    assert wma["ma10"] is not None
    assert wma["ma20"] is not None
    assert wma["ma60"] is not None
    # close 단조 증가 → 주봉 MA 도 단조 증가. ma10 > ma20 > ma60 (최근 주가가 더 높음)
    assert wma["ma10"] > wma["ma20"] > wma["ma60"]


# ---------------------------------------------------------------------------
# 3. 월봉 MA — resample('ME') 후 N월 평균
# ---------------------------------------------------------------------------


def test_monthly_ma_resample() -> None:
    df = _build_fixture_df(n_days=300, base=100.0)  # ~14 개월
    ind = compute_indicators(df)
    mma = ind["monthly_ma"]
    assert mma["ma7"] is not None
    # 단조 증가 → 7개월 평균이 20개월 평균보다 큼
    if mma["ma20"] is not None:
        assert mma["ma7"] > mma["ma20"]


def test_monthly_ma_insufficient_data_yields_null() -> None:
    """1개월 분량만 → 월봉 20MA 산출 불가 → null + reasons."""
    df = _build_fixture_df(n_days=20, base=100.0)
    ind = compute_indicators(df)
    assert ind["monthly_ma"]["ma20"] is None
    assert any("월봉" in r and "데이터 부족" in r for r in ind["reasons"])


# ---------------------------------------------------------------------------
# 4. MACD 12-26-9
# ---------------------------------------------------------------------------


def test_macd_12_26_9_present() -> None:
    df = _build_fixture_df(n_days=100, base=100.0)
    ind = compute_indicators(df)
    macd = ind["macd"]
    # 단조 증가 close → MACD > 0 (단기 EMA > 장기 EMA)
    assert macd["macd"] is not None
    assert macd["signal"] is not None
    assert macd["histogram"] is not None
    assert macd["macd"] > 0
    # signal 도 양수 (EMA of MACD)
    assert macd["signal"] > 0


def test_macd_insufficient_data() -> None:
    """20봉 → MACD 26 EMA 부족 → null."""
    df = _build_fixture_df(n_days=20, base=100.0)
    ind = compute_indicators(df)
    assert ind["macd"]["macd"] is None
    assert any("MACD" in r for r in ind["reasons"])


# ---------------------------------------------------------------------------
# 5. 거래량 spike — volume / ma20
# ---------------------------------------------------------------------------


def test_volume_spike_uniform_returns_one() -> None:
    """volume 이 모두 동일 → ma20 = volume → spike_ratio = 1.0."""
    df = _build_fixture_df(n_days=100, base=100.0)
    ind = compute_indicators(df)
    vol = ind["volume"]
    assert vol["ma20"] == pytest.approx(1_000_000, rel=1e-6)
    assert vol["spike_ratio"] == pytest.approx(1.0, rel=1e-6)


# ---------------------------------------------------------------------------
# 6. 52주 (252 영업일) 고저 + 현재가 위치
# ---------------------------------------------------------------------------


def test_52_week_high_low_with_full_window() -> None:
    df = _build_fixture_df(n_days=300, base=100.0)
    ind = compute_indicators(df)
    ftw = ind["fifty_two_week"]
    # 마지막 252봉 = day 48 ~ 299, close = 148 ~ 399? 실제 close = 100 + i (i=0..299)
    # 마지막 252 = i=48..299, close = 148..399, high = close + 1 = 149..400
    assert ftw["high"] == pytest.approx(400.0, rel=1e-6)
    assert ftw["low"] == pytest.approx(147.0, rel=1e-6)  # close-1 at i=48 = 99+48-1=147 wait
    # current_close = 299+100=399
    # pct_from_high = (399 - 400) / 400 * 100 = -0.25
    assert ftw["pct_from_high"] == pytest.approx(-0.25, rel=1e-3)
    assert ftw["window_days"] == 252
