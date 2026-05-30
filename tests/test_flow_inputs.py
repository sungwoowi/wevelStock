"""collectors/flow_inputs.py 단위 테스트 (INFRA-SCORE-INPUTS-001 M4 / F-Score 원시 지표).

순수 compute 는 합성 supply rows 로 테스트 (DB 의존 없음).
MVP = 시장 레벨 5주체 60일 수급 프록시 (momentum / inflow_speed / agreement).
theme_match 직관축 = SLOT S1 → MVP 중립. advisory f_score = 참고선.
"""

from __future__ import annotations

import pytest

from collectors.flow_inputs import compute_flow_inputs, render_flow_inputs_md

_BPS = {
    "momentum": [(-1.0, 1.0), (0.0, 5.0), (1.0, 9.0)],
    "inflow_speed": [(-50.0, 1.0), (0.0, 5.0), (150.0, 10.0)],
}


def _row(f, i, *, ind=0, fin=0, pen=0):
    return {
        "foreign_net": f, "institution_net": i, "individual_net": ind,
        "financial_inv_net": fin, "pension_net": pen,
    }


def _rows_buy_turnaround(n=60):
    # 앞 절반 매도(외인·기관 음), 뒤 절반 매수(양) → momentum 강한 +turnaround
    rows = []
    for k in range(n):
        if k < n // 2:
            rows.append(_row(-1000, -800))
        else:
            rows.append(_row(2000, 1500))
    return rows


class TestComputeFlowInputs:
    def test_agreement_from_sum(self) -> None:
        # 모두 같은 부호(매수) → agreement 10
        rows = [_row(100, 200, ind=50, fin=30, pen=20) for _ in range(10)]
        fi = compute_flow_inputs(rows, breakpoints=_BPS)
        assert fi.agreement == pytest.approx(10.0)

    def test_momentum_positive_turnaround(self) -> None:
        fi = compute_flow_inputs(_rows_buy_turnaround(), breakpoints=_BPS)
        assert fi.momentum_raw > 0.5  # 강한 매수 전환
        assert fi.momentum_score is not None and fi.momentum_score > 5.0

    def test_momentum_in_range(self) -> None:
        fi = compute_flow_inputs(_rows_buy_turnaround(), breakpoints=_BPS)
        assert -1.0 <= fi.momentum_raw <= 1.0

    def test_inflow_speed_none_without_market_cap(self) -> None:
        fi = compute_flow_inputs(_rows_buy_turnaround(), breakpoints=_BPS)
        assert fi.inflow_speed_raw is None
        assert any("시총" in r or "market_cap" in r.lower() for r in fi.reasons)

    def test_inflow_speed_with_market_cap(self) -> None:
        rows = [_row(1000, 1000) for _ in range(60)]  # 외인+기관 60d = 120000 (백만원)
        fi = compute_flow_inputs(rows, market_cap=1_000_000, breakpoints=_BPS)
        assert fi.inflow_speed_raw is not None

    def test_theme_match_unresolved_neutral(self) -> None:
        # theme_match_score 미주입(None) → 중립 fallback (SLOT S1)
        fi = compute_flow_inputs(_rows_buy_turnaround(), breakpoints=_BPS, theme_match_neutral=5.0)
        assert fi.theme_match_score == 5.0
        assert fi.theme_match_source == "neutral_fallback"
        assert any("theme" in r.lower() or "테마" in r for r in fi.reasons)

    def test_theme_match_resolved_injected(self) -> None:
        # build 가 resolve_theme_match 로 채점한 score 주입 → 그대로 반영
        fi = compute_flow_inputs(
            _rows_buy_turnaround(), breakpoints=_BPS,
            theme_match_score=8.0, theme_match_theme="cosmetics", theme_match_source="llm",
        )
        assert fi.theme_match_score == 8.0
        assert fi.theme_match_theme == "cosmetics"
        assert fi.theme_match_source == "llm"
        assert any("cosmetics" in r for r in fi.reasons)

    def test_advisory_f_score_present(self) -> None:
        fi = compute_flow_inputs(_rows_buy_turnaround(), breakpoints=_BPS)
        assert fi.advisory_f_score is not None
        assert 0.0 <= fi.advisory_f_score <= 10.0

    def test_empty_rows(self) -> None:
        fi = compute_flow_inputs([], breakpoints=_BPS)
        assert fi.actual_days == 0
        assert fi.momentum_raw is None or fi.momentum_score is None

    def test_deterministic(self) -> None:
        a = compute_flow_inputs(_rows_buy_turnaround(), breakpoints=_BPS)
        b = compute_flow_inputs(_rows_buy_turnaround(), breakpoints=_BPS)
        assert a.advisory_f_score == b.advisory_f_score
        assert a.momentum_raw == b.momentum_raw


class TestRenderFlowInputsMd:
    def test_md_contains_raw_and_advisory(self) -> None:
        fi = compute_flow_inputs(
            _rows_buy_turnaround(), breakpoints=_BPS, market="KOSPI",
        )
        md = render_flow_inputs_md(fi)
        assert "수급" in md or "F-Score" in md
        assert "advisory" in md.lower() or "참고선" in md
        # 일치도 raw 노출
        assert "일치도" in md or "agreement" in md.lower()
        # theme_match 행 노출
        assert "theme_match" in md or "테마" in md

    def test_md_shows_resolved_theme(self) -> None:
        fi = compute_flow_inputs(
            _rows_buy_turnaround(), breakpoints=_BPS, market="KOSPI",
            theme_match_score=7.5, theme_match_theme="cosmetics", theme_match_source="llm",
        )
        md = render_flow_inputs_md(fi)
        assert "cosmetics" in md
        assert "llm" in md
