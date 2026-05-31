"""INFRA-SNAPSHOT-EXTEND-001 — market_macro collector 5 케이스.

1. DB hit (오늘 row 박혀 있으면 compute 가 즉시 반환, KIS/KRX 호출 X)
2. position 분기 (above_both / between / below_both)
3. trend 분기 (uptrend / sideways / downtrend)
4. Distribution Day 25 일 윈도우 카운트
5. refresh_market_macro_all 양 시장 처리 + upsert 멱등성
"""
from __future__ import annotations

from datetime import date as _date
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from collectors import market_macro as mm
from collectors.charts import persist_ohlcv_to_db
from collectors.market_macro import (
    INDEX_TICKER_MAP,
    MarketMacro,
    _position_from_close,
    _trend_from_slopes,
    compute_distribution_days,
    compute_index_hierarchy,
    compute_ma_trend,
    compute_market_macro,
    refresh_market_macro_all,
    upsert_market_macro,
)
from core.db.connection import Database, reset_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    """temp DB + market_macro / charts module 의 get_db 패치 + KRX 호출 mock."""
    reset_db()
    db = Database(tmp_path / "test_market_macro.sqlite")
    monkeypatch.setattr(mm, "get_db", lambda: db)
    # charts.load_ohlcv_from_db 가 본인 get_db 를 호출하므로 별도 패치
    from collectors import charts as ch_mod
    monkeypatch.setattr(ch_mod, "get_db", lambda: db)

    # KRX breadth 항상 빈 dict (테스트는 chart 기반 4축만 검증)
    async def _empty_breadth(market: str) -> dict:
        return {}
    monkeypatch.setattr(mm, "_fetch_breadth", _empty_breadth)
    return db


def _synthetic_daily_bars(
    days: int,
    *,
    start: _date = _date(2021, 1, 4),
    base_close: float = 2500.0,
    drift_per_day: float = 0.0,
    volume_base: int = 1_000_000,
) -> list[dict]:
    """합성 일봉 — close 가 base + drift*i 로 선형. change_rate 동시 산출."""
    out = []
    prev_close = base_close
    d = start
    for i in range(days):
        # 주말 건너뜀
        while d.weekday() >= 5:
            d += timedelta(days=1)
        close = base_close + drift_per_day * i
        change_pct = (close - prev_close) / prev_close * 100 if prev_close > 0 else 0.0
        out.append({
            "date": d.strftime("%Y-%m-%d"),
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.98,
            "close": close,
            "volume": volume_base,
            "value": int(close * volume_base),
            "change_rate": round(change_pct, 4),
        })
        prev_close = close
        d += timedelta(days=1)
    return out


# ---------------------------------------------------------------------------
# 1. DB hit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_db_hit_returns_cached_row(isolated_db: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    today = mm._today_kst_str()
    # 오늘 row 박음
    cached = MarketMacro(
        date=today,
        market="KOSPI",
        index_close=2700.0,
        ma_36m=2500.0, ma_60m=2400.0, position="above_both",
        ma_20d=2680.0, ma_60d=2650.0,
        ma20_slope_pct_5d=1.2, ma60_slope_pct_20d=0.8, trend="uptrend",
        advancing=500, declining=350, unchanged=100, breadth_ratio=0.588,
        is_distribution_day=False, change_pct=0.5, volume_change_pct=2.0,
        distribution_count_25d=2,
    )
    upsert_market_macro(cached)

    # load_ohlcv_from_db 가 호출되면 안 됨 → guard
    def _fail_load(*a, **kw):
        raise AssertionError("DB hit 시 chart_ohlcv read 호출되면 안 됨")
    monkeypatch.setattr(mm, "load_ohlcv_from_db", _fail_load)

    result = await compute_market_macro("KOSPI")
    assert result.source == "db"
    assert result.position == "above_both"
    assert result.trend == "uptrend"
    assert result.advancing == 500
    assert result.market == "KOSPI"


# ---------------------------------------------------------------------------
# 2. Position 3 분기
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "close,ma36,ma60,expected",
    [
        (2700.0, 2500.0, 2400.0, "above_both"),    # 양쪽 위
        (2500.0, 2520.0, 2480.0, "between"),       # 사이
        (2300.0, 2500.0, 2400.0, "below_both"),    # 양쪽 아래
        (2700.0, None, None, "between"),           # 데이터 부족
    ],
)
def test_position_branches(close: float, ma36, ma60, expected: str) -> None:
    assert _position_from_close(close, ma36, ma60) == expected


# ---------------------------------------------------------------------------
# 3. Trend 3 분기
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "slope5,slope20,expected",
    [
        (1.2, 0.8, "uptrend"),       # 둘 다 양수
        (-1.5, -0.7, "downtrend"),   # 둘 다 음수
        (1.2, -0.5, "sideways"),     # 부호 mix
        (None, 0.8, "sideways"),     # 데이터 부족
    ],
)
def test_trend_branches(slope5, slope20, expected: str) -> None:
    assert _trend_from_slopes(slope5, slope20) == expected


# ---------------------------------------------------------------------------
# 4. Distribution Day 25 일 윈도우 카운트
# ---------------------------------------------------------------------------


def test_distribution_day_count_in_25d_window() -> None:
    # 30 일 합성 (앞 5일 평범, 뒤 25일 중 3일은 DD 조건 충족)
    bars = _synthetic_daily_bars(30, drift_per_day=0.0, base_close=2500.0)
    # 뒤 25일 중 3 일은 -0.5% 등락 + 전일 대비 거래량 증가 (DD)
    for dd_idx in (-3, -8, -15):
        bars[dd_idx]["change_rate"] = -0.5
        bars[dd_idx]["volume"] = bars[dd_idx - 1]["volume"] + 500_000  # > 전일

    df = pd.DataFrame(bars)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")

    result = compute_distribution_days(df, window=25)
    assert result["distribution_count_25d"] == 3
    assert len(result["recent_distribution_days"]) == 3
    # 마지막 봉이 DD 아닌지 (테스트 합성은 -3 부터 시작)
    assert result["is_distribution_day"] is False


# ---------------------------------------------------------------------------
# 5. refresh_market_macro_all 양 시장 처리
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_all_orchestrates_both_markets(
    isolated_db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    # KOSPI(0001) / KOSDAQ(1001) 양쪽에 충분한 일봉 적재 (1500 일 ≈ 75 개월 → 60월 MA 가능)
    kospi_bars = _synthetic_daily_bars(1500, base_close=2500.0, drift_per_day=0.05)
    kosdaq_bars = _synthetic_daily_bars(1500, base_close=850.0, drift_per_day=0.02)
    persist_ohlcv_to_db("0001", kospi_bars, adjusted=True)
    persist_ohlcv_to_db("1001", kosdaq_bars, adjusted=True)

    result = await refresh_market_macro_all()
    assert result["refreshed"] == ["KOSPI", "KOSDAQ"]
    assert result["failures"] == []

    # DB 양 시장 row 적재 확인
    rows = isolated_db.fetch_all(
        "SELECT market, position, trend, index_close FROM market_macro_snapshot "
        "WHERE date = ? ORDER BY market",
        (mm._today_kst_str(),),
    )
    assert len(rows) == 2
    markets = {r["market"] for r in rows}
    assert markets == {"KOSPI", "KOSDAQ"}
    # drift 양수 → 추세 uptrend 또는 sideways. position above_both 또는 between.
    for r in rows:
        assert r["position"] in ("above_both", "between", "below_both")
        assert r["trend"] in ("uptrend", "sideways", "downtrend")
        assert r["index_close"] > 0

    # 멱등성: 한 번 더 refresh 호출 → 같은 결과
    result2 = await refresh_market_macro_all()
    assert result2["refreshed"] == ["KOSPI", "KOSDAQ"]
    rows2 = isolated_db.fetch_all(
        "SELECT COUNT(*) AS n FROM market_macro_snapshot WHERE date = ?",
        (mm._today_kst_str(),),
    )
    assert rows2[0]["n"] == 2  # 행 수 그대로 (ON CONFLICT REPLACE)


# ---------------------------------------------------------------------------
# 6. market_breadth — KIS 업종지수 등락종목수 (KRX STAT Akamai 폐기 대체, 2026-05-31)
# ---------------------------------------------------------------------------


class _FakeKIS:
    """async with KISClient() as kis 대체 — market_breadth 고정 반환."""

    def __init__(self, breadth: dict) -> None:
        self._b = breadth

    async def __aenter__(self) -> "_FakeKIS":
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def market_breadth(self, market: str) -> dict:
        return self._b


@pytest.mark.asyncio
@pytest.mark.parametrize("market,iscd", [("KOSPI", "0001"), ("KOSDAQ", "1001")])
async def test_kis_market_breadth_parses_issu_cnt(
    market: str, iscd: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """inquire-index-price 의 *_issu_cnt → 전체 시장 등락 종목수 파싱 + 시장→index_code."""
    from connectors.kis.client import KISClient

    kis = KISClient()

    async def _fake_get(path: str, *, tr_id: str, params: dict) -> dict:
        assert tr_id == "FHPUP02100000"
        assert params["FID_INPUT_ISCD"] == iscd
        return {"rt_cd": "0", "output": {
            "ascn_issu_cnt": "206", "down_issu_cnt": "688", "stnr_issu_cnt": "28",
            "uplm_issu_cnt": "4", "lslm_issu_cnt": "0",
        }}

    monkeypatch.setattr(kis, "_get", _fake_get)
    r = await kis.market_breadth(market)
    assert r["advancing"] == 206 and r["declining"] == 688 and r["unchanged"] == 28
    assert r["limit_up"] == 4 and r["limit_down"] == 0
    assert r["breadth_ratio"] == round(206 / 894, 4)
    assert r["source"] == "kis_index"


@pytest.mark.asyncio
async def test_kis_market_breadth_error_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from connectors.kis.client import KISClient

    kis = KISClient()

    async def _fake_get(path: str, *, tr_id: str, params: dict) -> dict:
        return {"rt_cd": "1", "msg1": "조회 실패"}

    monkeypatch.setattr(kis, "_get", _fake_get)
    r = await kis.market_breadth("KOSPI")
    assert r["source"] == "unavailable" and r["advancing"] is None


@pytest.mark.asyncio
async def test_fetch_breadth_uses_kis_index(monkeypatch: pytest.MonkeyPatch) -> None:
    """_fetch_breadth 1순위 = KIS 업종지수 (정확값)."""
    breadth = {"market": "KOSPI", "advancing": 206, "declining": 688,
               "unchanged": 28, "breadth_ratio": 0.2304, "source": "kis_index"}
    monkeypatch.setattr(mm, "KISClient", lambda: _FakeKIS(breadth))
    r = await mm._fetch_breadth("KOSPI")
    assert r["source"] == "kis_index" and r["advancing"] == 206


@pytest.mark.asyncio
async def test_fetch_breadth_falls_back_to_volrank_when_empty(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """KIS 업종지수가 0 카운트 → volume_rank top30 대용으로 강등."""
    monkeypatch.setattr(mm, "KISClient", lambda: _FakeKIS({"advancing": 0, "declining": 0}))
    called = {}

    async def _fake_fallback(market: str) -> dict:
        called["hit"] = True
        return {"source": "kis_volrank_top30", "advancing": 5, "declining": 3}

    monkeypatch.setattr(mm, "_fetch_breadth_kis_fallback", _fake_fallback)
    r = await mm._fetch_breadth("KOSPI")
    assert called.get("hit") and r["source"] == "kis_volrank_top30"


# ---------------------------------------------------------------------------
# classify_market_regime — 6단계 결정론 분류 (예측 X, 현재 상태 라벨링)
# ---------------------------------------------------------------------------


def _macro(**kw) -> dict:
    base = {
        "position": "above_both", "trend": "uptrend",
        "ma20_slope_pct_5d": 1.0, "breadth_ratio": 0.50,
        "distribution_count_25d": 0,
    }
    base.update(kw)
    return base


class TestClassifyMarketRegime:
    def test_strong_bull(self) -> None:
        # above_both + uptrend + breadth 양호 + 분산일 적음, 기울기 완만 → strong_bull
        assert mm.classify_market_regime(_macro(ma20_slope_pct_5d=1.0)) == "strong_bull"

    def test_parabolic(self) -> None:
        # 가파른 기울기(≥3.0) + breadth 강함(≥0.55) + 분산일 적음 → parabolic
        assert mm.classify_market_regime(
            _macro(ma20_slope_pct_5d=4.0, breadth_ratio=0.60)
        ) == "parabolic"

    def test_parabolic_suppressed_by_distribution(self) -> None:
        # 가파르나 분산일 천장(≥5) → parabolic 억제 → strong_bull
        assert mm.classify_market_regime(
            _macro(ma20_slope_pct_5d=4.0, breadth_ratio=0.60, distribution_count_25d=6)
        ) == "strong_bull"

    def test_narrow_breadth_downgrades_to_moderate_bull(self) -> None:
        # 시총 상위 쏠림 = 지수 상승(above_both+uptrend)인데 breadth 좁음(<0.40) → moderate_bull
        assert mm.classify_market_regime(
            _macro(breadth_ratio=0.30, ma20_slope_pct_5d=4.0)
        ) == "moderate_bull"

    def test_recovery_uptrend_below_long_ma_is_moderate(self) -> None:
        # uptrend 이나 장기선 회복 중(between) → moderate_bull
        assert mm.classify_market_regime(_macro(position="between")) == "moderate_bull"

    def test_sideways(self) -> None:
        assert mm.classify_market_regime(_macro(trend="sideways")) == "sideways"

    def test_moderate_bear(self) -> None:
        # downtrend 이나 장기선 위/중간 → moderate_bear
        assert mm.classify_market_regime(_macro(trend="downtrend", position="between")) == "moderate_bear"

    def test_strong_bear(self) -> None:
        assert mm.classify_market_regime(
            _macro(trend="downtrend", position="below_both")
        ) == "strong_bear"

    def test_missing_data_sideways_fallback(self) -> None:
        assert mm.classify_market_regime(_macro(position=None)) == "sideways"
        assert mm.classify_market_regime(_macro(trend=None)) == "sideways"

    def test_accepts_dataclass(self) -> None:
        # MarketMacro dataclass 도 수용
        macro = MarketMacro(
            date="2026-06-01", market="KOSPI", index_close=2500.0,
            ma_36m=2400.0, ma_60m=2300.0, position="above_both",
            ma_20d=2480.0, ma_60d=2450.0, ma20_slope_pct_5d=1.0, ma60_slope_pct_20d=0.5,
            trend="uptrend", advancing=500, declining=400, unchanged=50, breadth_ratio=0.55,
            is_distribution_day=False, change_pct=0.5, volume_change_pct=2.0,
            distribution_count_25d=0,
        )
        assert mm.classify_market_regime(macro) == "strong_bull"

    def test_thresholds_di(self) -> None:
        # 임계 DI: parabolic 기울기 임계를 5.0 으로 올리면 기울기 4.0 은 strong_bull
        assert mm.classify_market_regime(
            _macro(ma20_slope_pct_5d=4.0, breadth_ratio=0.60),
            thresholds={"parabolic_slope_pct": 5.0},
        ) == "strong_bull"

    def test_determinism(self) -> None:
        m = _macro(ma20_slope_pct_5d=4.0, breadth_ratio=0.60)
        assert mm.classify_market_regime(m) == mm.classify_market_regime(m)


class TestRegimeToScore:
    def test_bull_high(self) -> None:
        assert mm.regime_to_score("parabolic") == 10.0
        assert mm.regime_to_score("strong_bull") == 10.0
        assert mm.regime_to_score("moderate_bull") == 7.0

    def test_neutral_bear(self) -> None:
        assert mm.regime_to_score("sideways") == 4.0
        assert mm.regime_to_score("moderate_bear") == 2.0
        assert mm.regime_to_score("strong_bear") == 0.0

    def test_unknown_neutral(self) -> None:
        assert mm.regime_to_score(None) == 4.0
        assert mm.regime_to_score("??") == 4.0
