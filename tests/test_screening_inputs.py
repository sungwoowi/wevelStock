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
    compute_supply_chain_score,
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

    def test_partial_components_normalized(self) -> None:
        # 월봉만 산출 가능 + 정배열 → 4/4 비례 정규화 = 10.0 (결측 위계 평가 제외, 저평가 편향 제거)
        ind = _ind(close=100, m7=90)
        score, detail = compute_alignment(ind)
        assert score == 10.0
        assert detail["weekly_stack"] is None and detail["daily_stack"] is None

    def test_partial_mixed_normalized(self) -> None:
        # 월봉 정배열(4) + 일봉 역배열(0), 주봉 결측 → available_max 7, earned 4 → 4/7×10 = 5.714 → 5.5
        ind = _ind(close=100, m7=90, d20=105, d60=110)  # close < d20 → 일봉 역배열
        score, _ = compute_alignment(ind)
        assert score == 5.5

    def test_daily_only_aligned_full(self) -> None:
        # 일봉만 산출 + 정배열 → 3/3 = 10.0 (구 구현은 max 3 으로 막혔던 저평가 편향)
        ind = _ind(close=100, d20=95, d60=90)
        score, _ = compute_alignment(ind)
        assert score == 10.0

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
# compute_supply_chain_score (순수) — theme → 섹터 RS 실측
# ============================================================


class TestComputeSupplyChain:
    _SECTORS = [
        {"sector": "KODEX AI반도체", "rs_score": 8.0},
        {"sector": "KODEX AI반도체핵심장비", "rs_score": 9.5},
        {"sector": "KODEX 바이오", "rs_score": 3.0},
    ]
    _MAP = {
        "AI_semiconductor": ["KODEX AI반도체", "KODEX AI반도체핵심장비", "KODEX AI전력핵심"],
        "bio": ["KODEX 바이오"],
        "kosdaq_theme": [],
    }

    def test_strongest_sector_chosen(self) -> None:
        # AI 테마 → 두 매핑 섹터 중 최강(9.5) 채택
        score, src = compute_supply_chain_score("AI_semiconductor", self._SECTORS, self._MAP)
        assert score == 9.5 and src == "theme_sector"

    def test_single_sector(self) -> None:
        score, src = compute_supply_chain_score("bio", self._SECTORS, self._MAP)
        assert score == 3.0 and src == "theme_sector"

    def test_empty_mapping_neutral(self) -> None:
        # kosdaq_theme = 매핑 빈 리스트 → 중립
        assert compute_supply_chain_score("kosdaq_theme", self._SECTORS, self._MAP) == (
            None, "neutral_fallback",
        )

    def test_theme_none_neutral(self) -> None:
        assert compute_supply_chain_score(None, self._SECTORS, self._MAP) == (
            None, "neutral_fallback",
        )

    def test_no_sector_rs_neutral(self) -> None:
        assert compute_supply_chain_score("bio", [], self._MAP) == (None, "neutral_fallback")

    def test_mapped_sector_absent_in_rs(self) -> None:
        # 매핑은 있으나 sector_rs 리스트에 해당 섹터 없음 → 중립
        score, src = compute_supply_chain_score(
            "AI_semiconductor", [{"sector": "KODEX 바이오", "rs_score": 3.0}], self._MAP
        )
        assert score is None and src == "neutral_fallback"

    def test_determinism(self) -> None:
        a = compute_supply_chain_score("AI_semiconductor", self._SECTORS, self._MAP)
        b = compute_supply_chain_score("AI_semiconductor", self._SECTORS, self._MAP)
        assert a == b


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
async def test_supply_chain_from_sector_rs(isolated_db, monkeypatch: pytest.MonkeyPatch) -> None:
    from collectors import theme_match as tm_mod
    from collectors.charts import persist_ohlcv_to_db
    from collectors.theme_match import ThemeResult

    persist_ohlcv_to_db("A", _bars(10_000, 15.0), adjusted=True)

    async def _fake_classify(ticker: str, **_kw):
        return ThemeResult(ticker=ticker, theme="AI_semiconductor", source="manual")

    monkeypatch.setattr(tm_mod, "classify_theme", _fake_classify)

    sectors = [
        {"sector": "KODEX AI반도체", "rs_score": 7.0},
        {"sector": "KODEX AI반도체핵심장비", "rs_score": 9.0},
    ]
    si = await build_s_score_inputs(ticker="A", pool_tickers=["A"], sector_rs=sectors)
    assert si.supply_chain_source == "theme_sector"
    assert si.supply_chain_score == 9.0  # 최강 섹터
    assert si.supply_chain_theme == "AI_semiconductor"
    assert si.supply_chain_sector == "KODEX AI반도체핵심장비"


@pytest.mark.asyncio
async def test_supply_chain_neutral_without_sector_rs(isolated_db) -> None:
    from collectors.charts import persist_ohlcv_to_db

    persist_ohlcv_to_db("A", _bars(10_000, 15.0), adjusted=True)
    # sector_rs 미전달 → supply_chain 중립 (classify_theme 호출 안 함)
    si = await build_s_score_inputs(ticker="A", pool_tickers=["A"])
    assert si.supply_chain_source == "neutral_fallback"
    assert si.supply_chain_score == 5.0


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
