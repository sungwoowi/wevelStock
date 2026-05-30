"""collectors/technicals.py 단위 테스트 (INFRA-SCORE-INPUTS-001 M3 / T-Score 원시 지표).

순수 compute 는 합성 indicators dict 로 테스트 (charts/DB 의존 없음).
같은 입력 → 같은 출력 ±0. 원시 지표 = 권위(LLM 주입), advisory t_score = 참고선.
"""

from __future__ import annotations

import pytest

from collectors.technicals import compute_technical_inputs, render_technicals_md

# T-Score 매핑 breakpoints (테스트용 명시 — DI)
_BPS = {
    "divergence": [(-20.0, 2.0), (-2.0, 9.0), (3.0, 8.0), (25.0, 1.0)],
    "macd": [(-3.0, 2.0), (0.0, 5.0), (3.0, 9.0)],
    "volume": [(0.5, 3.0), (1.0, 5.0), (1.8, 8.0), (6.0, 4.0)],
    "rr": [(0.5, 1.0), (1.5, 6.0), (3.0, 9.0)],
}


def _indicators(*, ma20=100.0, hist=0.0, spike=1.0, close=100.0):
    return {
        "current_close": close,
        "daily_ma": {"ma20": ma20},
        "macd": {"macd": 1.0, "signal": 0.5, "histogram": hist},
        "volume": {"today": 1000, "ma20": 1000, "spike_ratio": spike},
    }


class TestComputeTechnicalInputs:
    def test_divergence_pct_from_ma20(self) -> None:
        # price 110, ma20 100 → 이격도 +10%
        ti = compute_technical_inputs(
            _indicators(ma20=100.0, close=110.0), 110.0, breakpoints=_BPS
        )
        assert ti.divergence_pct == pytest.approx(10.0, abs=0.01)

    def test_volume_ratio_passthrough(self) -> None:
        ti = compute_technical_inputs(
            _indicators(spike=1.8), 100.0, breakpoints=_BPS
        )
        assert ti.volume_ratio == pytest.approx(1.8)
        assert ti.volume_score == 8.0  # breakpoint 정확

    def test_axes_mapped_to_0_10(self) -> None:
        ti = compute_technical_inputs(
            _indicators(ma20=100.0, close=98.0, spike=1.8, hist=0.0),
            98.0, rr=1.5, breakpoints=_BPS,
        )
        for sc in (ti.divergence_score, ti.macd_score, ti.volume_score, ti.rr_score):
            assert sc is None or (0.0 <= sc <= 10.0 and (sc * 2) % 1 == 0)

    def test_advisory_t_score_present_when_all_axes(self) -> None:
        ti = compute_technical_inputs(
            _indicators(ma20=100.0, close=99.0, spike=1.8),
            99.0, rr=2.0, alpha=0.0, breakpoints=_BPS,
        )
        assert ti.advisory_t_score is not None
        assert 0.0 <= ti.advisory_t_score <= 10.0

    def test_alpha_override_lifts_advisory(self) -> None:
        # α 1.6 (강발산) → t_score max(base, 7.0) (STRATEGY-TRACK-001)
        ti = compute_technical_inputs(
            _indicators(ma20=100.0, close=99.0, spike=1.0, hist=0.0),
            99.0, rr=1.5, alpha=1.6, breakpoints=_BPS,
        )
        assert ti.advisory_t_score >= 7.0

    def test_missing_ma20_divergence_none(self) -> None:
        ind = _indicators()
        ind["daily_ma"]["ma20"] = None
        ti = compute_technical_inputs(ind, 100.0, breakpoints=_BPS)
        assert ti.divergence_pct is None
        assert ti.divergence_score is None
        assert any("이격도" in r or "ma20" in r.lower() for r in ti.reasons)

    def test_deterministic(self) -> None:
        a = compute_technical_inputs(_indicators(spike=1.8), 105.0, rr=2.0, breakpoints=_BPS)
        b = compute_technical_inputs(_indicators(spike=1.8), 105.0, rr=2.0, breakpoints=_BPS)
        assert a.advisory_t_score == b.advisory_t_score
        assert a.divergence_pct == b.divergence_pct


class TestRenderTechnicalsMd:
    def test_md_contains_raw_and_advisory(self) -> None:
        ti = compute_technical_inputs(
            _indicators(ma20=100.0, close=110.0, spike=1.8),
            110.0, rr=2.0, alpha=0.0, breakpoints=_BPS, ticker="005930",
        )
        md = render_technicals_md(ti)
        assert "005930" in md
        assert "이격도" in md
        # advisory 라벨 + override 가능 명시 (게이트키핑 아님)
        assert "advisory" in md.lower() or "참고선" in md
        # 원시 지표 값 노출
        assert "+10" in md or "10.0" in md

    def test_md_handles_none(self) -> None:
        ind = _indicators()
        ind["daily_ma"]["ma20"] = None
        ti = compute_technical_inputs(ind, 100.0, breakpoints=_BPS, ticker="000660")
        md = render_technicals_md(ti)
        assert isinstance(md, str)
        assert "000660" in md
