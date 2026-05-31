"""collectors/buy_score_inputs.py 단위 테스트 (INFRA-SCORE-INPUTS-001 v3 / buy_score CAN SLIM 7축).

순수 함수(compute_eps_yoy / compute_institution_ratio)는 DB 의존 X.
build_buy_score_inputs 는 graceful fallback(데이터 공백 축 → 중립) + advisory 산출.
원시 지표가 권위, advisory buy_score = 참고선.
"""
from __future__ import annotations

import pytest

from collectors.buy_score_inputs import (
    BuyScoreInputs,
    compute_eps_yoy,
    compute_institution_ratio,
    render_buy_score_inputs_md,
)


# ============================================================
# compute_eps_yoy (순수)
# ============================================================


class TestComputeEpsYoy:
    def test_positive_yoy(self) -> None:
        # 최근 분기 125, 전년 동기 100 → +25%
        assert compute_eps_yoy([125, 80, 70, 60, 100]) == pytest.approx(25.0)

    def test_negative_yoy(self) -> None:
        assert compute_eps_yoy([50, 60, 70, 80, 100]) == pytest.approx(-50.0)

    def test_base_negative_abs(self) -> None:
        # 적자→흑자: base 음수 abs 정규화. (10 - (-10))/10 = +200%
        assert compute_eps_yoy([10, 0, -5, -8, -10]) == pytest.approx(200.0)

    def test_too_few_quarters(self) -> None:
        assert compute_eps_yoy([125, 80, 70]) is None

    def test_base_zero(self) -> None:
        assert compute_eps_yoy([125, 80, 70, 60, 0]) is None

    def test_none_value(self) -> None:
        assert compute_eps_yoy([None, 80, 70, 60, 100]) is None

    def test_empty(self) -> None:
        assert compute_eps_yoy(None) is None


class TestComputeInstitutionRatio:
    def test_institution_buy(self) -> None:
        # 기관 +800, 외인 -200 → 800/(200+800+1) ≈ 0.799
        r = compute_institution_ratio({"institution_net": 800, "foreign_net": -200})
        assert r == pytest.approx(800 / 1001, abs=1e-3)

    def test_institution_sell(self) -> None:
        r = compute_institution_ratio({"institution_net": -500, "foreign_net": 100})
        assert r < 0

    def test_clamped(self) -> None:
        r = compute_institution_ratio({"institution_net": 10000, "foreign_net": 0})
        assert -1.0 <= r <= 1.0

    def test_empty(self) -> None:
        assert compute_institution_ratio(None) is None
        assert compute_institution_ratio({}) is None


# ============================================================
# build_buy_score_inputs (graceful fallback)
# ============================================================


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from core.db.connection import Database, reset_db

    reset_db()
    db = Database(tmp_path / "test_buy_score_inputs.sqlite")
    from collectors import charts as ch_mod

    monkeypatch.setattr(ch_mod, "get_db", lambda: db)
    from collectors import screening as sc_mod

    sc_mod.reload_screening_config()
    return db


@pytest.mark.asyncio
async def test_all_gaps_neutral(isolated_db, monkeypatch: pytest.MonkeyPatch) -> None:
    # fundamentals/flow/charts 전부 부재 종목 + market_macro 없음 → 모든 축 중립, advisory 산출(크래시 X)
    from collectors import buy_score_inputs as bsi
    from collectors.fundamentals import Fundamentals

    async def _fake_fund(ticker: str, *a, **kw):
        return Fundamentals(
            ticker=ticker, market="KS", fetched_at=0.0, fetched_at_iso="",
            eps_ttm=None, pe_ratio=None, roe=None, operating_margin=None, debt_to_equity=None,
            quarterly_revenue=[], quarterly_operating_income=[], quarterly_eps=[],
            quarter_labels=[], source="unknown", fetched_db_iso=None, stale_hours=0.0,
        )

    async def _fake_flow(**kw):
        from collectors.flow_inputs import FlowInputs
        return FlowInputs(
            ticker="", market="KOSPI", actual_days=0, net_sums={},
            momentum_raw=None, inflow_speed_raw=None, agreement=0.0,
            momentum_score=None, inflow_score=None, theme_match_score=None, advisory_f_score=None,
        )

    monkeypatch.setattr("collectors.fundamentals.get_fundamentals", _fake_fund)
    monkeypatch.setattr("collectors.flow_inputs.build_flow_inputs", _fake_flow)

    bi = await bsi.build_buy_score_inputs(ticker="999999", pool_tickers=[], market_macro=None)
    assert isinstance(bi, BuyScoreInputs)
    assert bi.a == 5.0  # 연간 EPS 공백 중립
    assert bi.m == 4.0  # market_macro 없음 → sideways 중립
    assert bi.advisory_buy_score is not None  # 크래시 X
    assert bi.axis_source["a"] == "neutral_fallback"


@pytest.mark.asyncio
async def test_eps_and_regime_live(isolated_db, monkeypatch: pytest.MonkeyPatch) -> None:
    # EPS YoY 강함 + 강세 regime → C/M 실측 점수
    from collectors import buy_score_inputs as bsi
    from collectors.fundamentals import Fundamentals

    async def _fake_fund(ticker: str, *a, **kw):
        return Fundamentals(
            ticker=ticker, market="KS", fetched_at=0.0, fetched_at_iso="",
            eps_ttm=1000.0, pe_ratio=10.0, roe=15.0, operating_margin=20.0, debt_to_equity=0.5,
            quarterly_revenue=[], quarterly_operating_income=[],
            quarterly_eps=[130, 110, 100, 95, 100],  # YoY = +30%
            quarter_labels=[], source="yfinance", fetched_db_iso=None, stale_hours=0.0,
        )

    async def _fake_flow(**kw):
        from collectors.flow_inputs import FlowInputs
        return FlowInputs(
            ticker="A", market="KOSPI", actual_days=60,
            net_sums={"institution_net": 800, "foreign_net": -200,
                      "individual_net": 0, "financial_inv_net": 0, "pension_net": 0},
            momentum_raw=0.5, inflow_speed_raw=80.0, agreement=6.0,
            momentum_score=7.0, inflow_score=9.0, theme_match_score=5.0, advisory_f_score=7.0,
        )

    monkeypatch.setattr("collectors.fundamentals.get_fundamentals", _fake_fund)
    monkeypatch.setattr("collectors.flow_inputs.build_flow_inputs", _fake_flow)

    macro = {
        "position": "above_both", "trend": "uptrend",
        "ma20_slope_pct_5d": 1.0, "breadth_ratio": 0.55, "distribution_count_25d": 0,
    }
    bi = await bsi.build_buy_score_inputs(ticker="A", pool_tickers=["A"], market_macro=macro)
    assert bi.eps_yoy_pct == pytest.approx(30.0)
    assert bi.c >= 9.0  # +30% YoY → 높은 C
    assert bi.regime == "strong_bull" and bi.m == 10.0
    assert bi.s == 9.0  # flow inflow_score
    assert bi.i > 5.0   # 기관 매수 우위
    assert bi.axis_source["c"].startswith("fundamentals")


@pytest.mark.asyncio
async def test_narrow_breadth_regime_moderate(isolated_db, monkeypatch: pytest.MonkeyPatch) -> None:
    # 시총 상위 쏠림: 지수 강세지만 breadth 좁음 → M = moderate_bull(7), breadth 노출
    from collectors import buy_score_inputs as bsi

    macro = {
        "position": "above_both", "trend": "uptrend",
        "ma20_slope_pct_5d": 4.0, "breadth_ratio": 0.30, "distribution_count_25d": 3,
    }
    bi = await bsi.build_buy_score_inputs(ticker="999999", pool_tickers=[], market_macro=macro)
    assert bi.regime == "moderate_bull" and bi.m == 7.0
    assert bi.breadth_ratio == 0.30 and bi.distribution_count == 3
    md = render_buy_score_inputs_md(bi)
    assert "천장 디버전스" in md and "0.30" in md


@pytest.mark.asyncio
async def test_render_block(isolated_db) -> None:
    from collectors import buy_score_inputs as bsi

    bi = await bsi.build_buy_score_inputs(ticker="999999", pool_tickers=[], market_macro=None)
    md = render_buy_score_inputs_md(bi, name="테스트")
    assert "[5e] 매수 입력 지표" in md
    assert "CAN SLIM" in md
    assert "advisory buy_score" in md
