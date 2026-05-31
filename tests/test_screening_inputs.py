"""collectors/screening_inputs.py 단위 테스트 (INFRA-SCORE-INPUTS-001 v2 / S-Score 원시 지표).

compute_alignment 는 합성 indicators dict 로 (DB 의존 X). build_s_score_inputs 는 graceful
fallback (빈 풀 → rs 중립 / OHLCV 부재 → alignment None) + DB 백킹 rs 산출.
원시 지표가 권위, advisory S-Score = 참고선.
"""
from __future__ import annotations

from datetime import date as _date
from datetime import timedelta

import pytest

from collectors.screening_inputs import (
    ScreeningInputs,
    build_s_score_inputs,
    compute_alignment,
    render_s_score_inputs_md,
)


# ============================================================
# compute_alignment (순수)
# ============================================================


def _ind(*, close, m7=None, w10=None, w20=None, w60=None, d20=None, d60=None):
    return {
        "current_close": close,
        "monthly_ma": {"ma7": m7},
        "weekly_ma": {"ma10": w10, "ma20": w20, "ma60": w60},
        "daily_ma": {"ma20": d20, "ma60": d60},
    }


class TestComputeAlignment:
    def test_full_stack_max(self) -> None:
        # 월봉 위(4) + 주봉 정배열(3) + 일봉 정배열(3) = 10
        ind = _ind(close=100, m7=90, w10=95, w20=90, w60=85, d20=92, d60=88)
        score, detail = compute_alignment(ind)
        assert score == 10.0
        assert detail == {"monthly_7ma": True, "weekly_stack": True, "daily_stack": True}

    def test_full_reverse_zero(self) -> None:
        # 모두 역배열 = 0
        ind = _ind(close=80, m7=90, w10=85, w20=90, w60=95, d20=92, d60=95)
        score, detail = compute_alignment(ind)
        assert score == 0.0
        assert detail["monthly_7ma"] is False

    def test_partial_components(self) -> None:
        # 월봉만 위 = 4점 (주/일봉 데이터 부족)
        ind = _ind(close=100, m7=90)
        score, detail = compute_alignment(ind)
        assert score == 4.0
        assert detail["weekly_stack"] is None and detail["daily_stack"] is None

    def test_all_missing_returns_none(self) -> None:
        ind = _ind(close=100)
        score, detail = compute_alignment(ind)
        assert score is None

    def test_no_close_returns_none(self) -> None:
        score, _ = compute_alignment(_ind(close=None, m7=90))
        assert score is None

    def test_determinism(self) -> None:
        ind = _ind(close=100, m7=90, d20=92, d60=88)
        assert compute_alignment(ind)[0] == compute_alignment(ind)[0]


# ============================================================
# build_s_score_inputs (graceful fallback)
# ============================================================


@pytest.mark.asyncio
async def test_empty_pool_rs_neutral() -> None:
    # 풀 없고 OHLCV 도 없음 → rs 중립 5.0, alignment None, advisory 산출됨
    si = await build_s_score_inputs(ticker="999999", pool_tickers=[])
    assert isinstance(si, ScreeningInputs)
    assert si.rs_score == 5.0
    assert si.rs_source == "neutral_fallback"
    assert si.alignment_score is None
    assert si.advisory_s_score is not None  # 크래시 X
    assert si.supply_chain_source == "neutral_fallback"


@pytest.mark.asyncio
async def test_blank_ticker_graceful() -> None:
    si = await build_s_score_inputs(ticker="", pool_tickers=[])
    assert si.rs_score == 5.0
    assert si.advisory_s_score is not None


# ============================================================
# build_s_score_inputs (DB 백킹 rs)
# ============================================================


def _bars(close_start: float, return_pct_60d: float, days: int = 80, *, spread: float = 0.02) -> list[dict]:
    end_close = close_start * (1 + return_pct_60d / 100)
    bars = []
    d = _date(2025, 1, 2)
    for i in range(days):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        if i < days - 60:
            close = close_start
        else:
            j = i - (days - 60)
            close = close_start + (end_close - close_start) * (j / 59)
        bars.append({
            "date": d.strftime("%Y-%m-%d"),
            "open": close, "high": close * (1 + spread), "low": close * (1 - spread),
            "close": close, "volume": 1_000_000, "value": int(close * 1_000_000),
            "change_rate": 0.0,
        })
        d += timedelta(days=1)
    return bars


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from core.db.connection import Database, reset_db

    reset_db()
    db = Database(tmp_path / "test_screening_inputs.sqlite")
    from collectors import charts as ch_mod

    monkeypatch.setattr(ch_mod, "get_db", lambda: db)
    from collectors import screening as sc_mod

    sc_mod.reload_screening_config()
    return db


@pytest.mark.asyncio
async def test_rs_from_pool_db(isolated_db) -> None:
    from collectors.charts import persist_ohlcv_to_db

    # A 강함(+15%), B 약함(-5%) 풀. A 의 rs 가 풀 최상위.
    persist_ohlcv_to_db("A", _bars(10_000, 15.0), adjusted=True)
    persist_ohlcv_to_db("B", _bars(10_000, -5.0), adjusted=True)

    si_a = await build_s_score_inputs(ticker="A", pool_tickers=["A", "B"])
    si_b = await build_s_score_inputs(ticker="B", pool_tickers=["A", "B"])
    assert si_a.rs_source == "screening"
    assert si_a.rs_score is not None and si_b.rs_score is not None
    assert si_a.rs_score > si_b.rs_score  # A 가 풀 내 더 강함
    assert si_a.pool_size == 2


@pytest.mark.asyncio
async def test_cutoff_reproducible(isolated_db) -> None:
    from collectors.charts import persist_ohlcv_to_db

    persist_ohlcv_to_db("A", _bars(10_000, 15.0, days=120), adjusted=True)
    persist_ohlcv_to_db("B", _bars(10_000, -5.0, days=120), adjusted=True)
    r1 = await build_s_score_inputs(ticker="A", pool_tickers=["A", "B"], cutoff_date="2025-04-01")
    r2 = await build_s_score_inputs(ticker="A", pool_tickers=["A", "B"], cutoff_date="2025-04-01")
    assert r1.rs_score == r2.rs_score and r1.advisory_s_score == r2.advisory_s_score


# ============================================================
# render
# ============================================================


@pytest.mark.asyncio
async def test_render_contains_advisory_and_axes() -> None:
    si = await build_s_score_inputs(ticker="999999", pool_tickers=[])
    md = render_s_score_inputs_md(si, name="테스트")
    assert "[5d] 주도주 입력 지표" in md
    assert "advisory S-Score" in md
    assert "rs (상대강도" in md
    assert "정배열 위계" in md
