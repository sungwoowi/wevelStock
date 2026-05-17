"""결정론 채점 단위 테스트 — ANALYST-PERSONAS-001 v2 옵션 b.

같은 입력 → 같은 출력 ±0 (재현성 강제).
"""

from __future__ import annotations

import math

import pytest

from collectors.scoring import alpha, buy_score, f_score, s_score, t_score


# ============================================================
# s_score — 주도주 점수 (stock_picker)
# ============================================================


class TestSScore:
    def test_uniform_mid(self) -> None:
        assert s_score(5, 5, 5) == 5.0

    def test_min(self) -> None:
        assert s_score(0, 0, 0) == 0.0

    def test_max(self) -> None:
        assert s_score(10, 10, 10) == 10.0

    def test_round_to_half(self) -> None:
        # (3 + 7 + 8) / 3 = 6.0
        assert s_score(3, 7, 8) == 6.0

    def test_round_to_half_quarter(self) -> None:
        # (4 + 5 + 6) / 3 = 5.0
        assert s_score(4, 5, 6) == 5.0

    def test_round_to_half_odd_average(self) -> None:
        # (5 + 5 + 6) / 3 = 5.333... → 5.5
        assert s_score(5, 5, 6) == 5.5

    def test_round_to_half_lower(self) -> None:
        # (5 + 5 + 4) / 3 = 4.666... → 4.5
        assert s_score(5, 5, 4) == 4.5

    def test_invalid_negative(self) -> None:
        with pytest.raises(ValueError):
            s_score(-1, 5, 5)

    def test_invalid_above_max(self) -> None:
        with pytest.raises(ValueError):
            s_score(11, 5, 5)

    def test_invalid_type_bool(self) -> None:
        with pytest.raises(TypeError):
            s_score(True, 5, 5)  # type: ignore[arg-type]

    def test_invalid_type_str(self) -> None:
        with pytest.raises(TypeError):
            s_score("5", 5, 5)  # type: ignore[arg-type]

    def test_determinism(self) -> None:
        # 같은 입력 100회 → 모두 동일
        values = [s_score(3, 7, 8) for _ in range(100)]
        assert len(set(values)) == 1
        assert values[0] == 6.0


# ============================================================
# t_score — 타점 점수 (trader, α 오버라이드)
# ============================================================


class TestTScore:
    def test_base_alpha_below_threshold(self) -> None:
        # α=1.0 정상 추세, 4축 평균만
        # (5 + 5 + 5 + 5) / 4 = 5.0
        assert t_score(5, 5, 5, 5, 1.0) == 5.0

    def test_base_alpha_zero(self) -> None:
        # α=0 정상 추세
        assert t_score(4, 4, 4, 4, 0.0) == 4.0

    def test_alpha_just_below_override(self) -> None:
        # α=1.29 그대로 base
        # (2 + 2 + 2 + 2) / 4 = 2.0
        assert t_score(2, 2, 2, 2, 1.29) == 2.0

    def test_alpha_override_divergence_start(self) -> None:
        # α=1.4 → max(base, 5.0)
        # base = (2 + 2 + 2 + 2) / 4 = 2.0 → max(2.0, 5.0) = 5.0
        assert t_score(2, 2, 2, 2, 1.4) == 5.0

    def test_alpha_override_divergence_start_high_base(self) -> None:
        # α=1.4, base 가 이미 6.0 이면 max(6, 5) = 6.0
        # (6 + 6 + 6 + 6) / 4 = 6.0
        assert t_score(6, 6, 6, 6, 1.4) == 6.0

    def test_alpha_override_strong_divergence(self) -> None:
        # α=1.7 → max(base, 7.0)
        # base = (4 + 4 + 4 + 4) / 4 = 4.0 → max(4.0, 7.0) = 7.0
        assert t_score(4, 4, 4, 4, 1.7) == 7.0

    def test_alpha_override_strong_divergence_high_base(self) -> None:
        # α=1.7, base 9.0 → max(9, 7) = 9.0
        assert t_score(9, 9, 9, 9, 1.7) == 9.0

    def test_alpha_override_runaway(self) -> None:
        # α=2.5 → min(base, 3.0) 폭주 부분 청산
        # base = (8 + 8 + 8 + 8) / 4 = 8.0 → min(8.0, 3.0) = 3.0
        assert t_score(8, 8, 8, 8, 2.5) == 3.0

    def test_alpha_override_runaway_low_base(self) -> None:
        # α=2.5, base 1.0 → min(1, 3) = 1.0
        assert t_score(1, 1, 1, 1, 2.5) == 1.0

    def test_alpha_boundary_1_3(self) -> None:
        # α=1.3 정확히 → override 시작
        # base = (3 + 3 + 3 + 3) / 4 = 3.0 → max(3, 5) = 5.0
        assert t_score(3, 3, 3, 3, 1.3) == 5.0

    def test_alpha_boundary_1_5(self) -> None:
        # α=1.5 정확히 → 강발산 max(base, 7.0)
        assert t_score(3, 3, 3, 3, 1.5) == 7.0

    def test_alpha_boundary_2_0(self) -> None:
        # α=2.0 정확히 → 폭주 min(base, 3.0)
        assert t_score(8, 8, 8, 8, 2.0) == 3.0

    def test_invalid_alpha_negative(self) -> None:
        with pytest.raises(ValueError):
            t_score(5, 5, 5, 5, -0.1)

    def test_invalid_divergence_negative(self) -> None:
        with pytest.raises(ValueError):
            t_score(-1, 5, 5, 5, 1.0)

    def test_invalid_alpha_type(self) -> None:
        with pytest.raises(TypeError):
            t_score(5, 5, 5, 5, "1.5")  # type: ignore[arg-type]

    def test_determinism(self) -> None:
        values = [t_score(4, 6, 5, 4, 1.7) for _ in range(100)]
        assert len(set(values)) == 1
        # base = (4+6+5+4)/4 = 4.75 → 4.5 → max(4.5, 7.0) = 7.0
        assert values[0] == 7.0


# ============================================================
# alpha — 가속계수 (stock_analyst, placeholder)
# ============================================================


class TestAlpha:
    def test_linear_growth(self) -> None:
        # 100 → 110 → 121 (10% 동일 비율)
        # ln(110/100) ≈ 0.0953, ln(121/110) ≈ 0.0953 → α ≈ 1.0
        assert alpha(100, 110, 121, 121) == pytest.approx(1.0, rel=1e-6)

    def test_accelerating_growth(self) -> None:
        # 100 → 120 → 150 (20% → 25% 가속)
        # ln(120/100) ≈ 0.1823, ln(150/120) ≈ 0.2231 → α ≈ 1.224
        result = alpha(100, 120, 150, 150)
        assert result > 1.0
        assert result == pytest.approx(math.log(150 / 120) / math.log(120 / 100), rel=1e-9)

    def test_strong_divergence_above_1_5(self) -> None:
        # 100 → 110 → 200 (10% → 82%) → α >> 1.5
        result = alpha(100, 110, 200, 200)
        assert result > 1.5

    def test_decelerating(self) -> None:
        # 100 → 150 → 160 (50% → 6.7%) → α < 1.0
        result = alpha(100, 150, 160, 160)
        assert result < 1.0
        assert result > 0

    def test_non_monotonic_raises(self) -> None:
        # B ≤ A 위배
        with pytest.raises(ValueError, match="단조 증가"):
            alpha(100, 100, 110, 110)

    def test_non_monotonic_c_le_b(self) -> None:
        with pytest.raises(ValueError, match="단조 증가"):
            alpha(100, 110, 110, 120)

    def test_zero_anchor_raises(self) -> None:
        with pytest.raises(ValueError, match="> 0"):
            alpha(0, 110, 121, 130)

    def test_negative_anchor_raises(self) -> None:
        with pytest.raises(ValueError, match="> 0"):
            alpha(100, -110, 121, 130)

    def test_invalid_type(self) -> None:
        with pytest.raises(TypeError):
            alpha("100", 110, 121, 130)  # type: ignore[arg-type]

    def test_determinism(self) -> None:
        values = [alpha(100, 130, 180, 180) for _ in range(100)]
        assert len(set(values)) == 1


# ============================================================
# buy_score — 매수 점수 CAN SLIM (stock_picker Track B)
# ============================================================


class TestBuyScore:
    def test_uniform(self) -> None:
        assert buy_score(7, 7, 7, 7, 7, 7, 7) == 7.0

    def test_min(self) -> None:
        assert buy_score(0, 0, 0, 0, 0, 0, 0) == 0.0

    def test_max(self) -> None:
        assert buy_score(10, 10, 10, 10, 10, 10, 10) == 10.0

    def test_round_to_half(self) -> None:
        # (7+7+7+7+7+7+8) / 7 = 7.142... → 7.0
        assert buy_score(7, 7, 7, 7, 7, 7, 8) == 7.0

    def test_round_to_half_up(self) -> None:
        # (8+8+8+8+8+8+9) / 7 = 8.142... → 8.0
        # (7+7+7+8+8+8+8) / 7 = 7.571... → 7.5
        assert buy_score(7, 7, 7, 8, 8, 8, 8) == 7.5

    def test_invalid_negative(self) -> None:
        with pytest.raises(ValueError):
            buy_score(-1, 5, 5, 5, 5, 5, 5)

    def test_invalid_above_max(self) -> None:
        with pytest.raises(ValueError):
            buy_score(5, 5, 5, 5, 5, 5, 11)

    def test_determinism(self) -> None:
        values = [buy_score(6, 7, 5, 8, 6, 7, 5) for _ in range(100)]
        assert len(set(values)) == 1


# ============================================================
# f_score — 수급 점수 (flow_analyzer)
# ============================================================


class TestFScore:
    def test_uniform_mid(self) -> None:
        # 0.4*5 + 0.3*5 + 0.2*5 + 0.1*5 = 5.0
        assert f_score(5, 5, 5, 5) == 5.0

    def test_min(self) -> None:
        assert f_score(0, 0, 0, 0) == 0.0

    def test_max(self) -> None:
        assert f_score(10, 10, 10, 10) == 10.0

    def test_theme_match_dominant(self) -> None:
        # 0.4*10 + 0.3*0 + 0.2*0 + 0.1*0 = 4.0
        assert f_score(10, 0, 0, 0) == 4.0

    def test_momentum_dominant(self) -> None:
        # 0.4*0 + 0.3*10 + 0.2*0 + 0.1*0 = 3.0
        assert f_score(0, 10, 0, 0) == 3.0

    def test_inflow_speed_dominant(self) -> None:
        # 0.4*0 + 0.3*0 + 0.2*10 + 0.1*0 = 2.0
        assert f_score(0, 0, 10, 0) == 2.0

    def test_agreement_dominant(self) -> None:
        # 0.4*0 + 0.3*0 + 0.2*0 + 0.1*10 = 1.0
        assert f_score(0, 0, 0, 10) == 1.0

    def test_round_to_half(self) -> None:
        # 0.4*8 + 0.3*6 + 0.2*4 + 0.1*2 = 3.2 + 1.8 + 0.8 + 0.2 = 6.0
        assert f_score(8, 6, 4, 2) == 6.0

    def test_round_to_half_quarter(self) -> None:
        # 0.4*7 + 0.3*7 + 0.2*7 + 0.1*8 = 2.8 + 2.1 + 1.4 + 0.8 = 7.1 → 7.0
        assert f_score(7, 7, 7, 8) == 7.0

    def test_round_to_half_up(self) -> None:
        # 0.4*7 + 0.3*8 + 0.2*7 + 0.1*8 = 2.8 + 2.4 + 1.4 + 0.8 = 7.4 → 7.5
        assert f_score(7, 8, 7, 8) == 7.5

    def test_invalid_negative(self) -> None:
        with pytest.raises(ValueError):
            f_score(-1, 5, 5, 5)

    def test_invalid_above_max(self) -> None:
        with pytest.raises(ValueError):
            f_score(5, 5, 5, 11)

    def test_determinism(self) -> None:
        values = [f_score(7, 8, 4, 6) for _ in range(100)]
        assert len(set(values)) == 1
        # 0.4*7 + 0.3*8 + 0.2*4 + 0.1*6 = 2.8 + 2.4 + 0.8 + 0.6 = 6.6 → 6.5
        assert values[0] == 6.5


# ============================================================
# 전체 결정론 회귀 — 5 함수 동시 같은 입력 → 같은 출력
# ============================================================


def test_all_functions_deterministic() -> None:
    """5 함수 모두 같은 입력 500회 → 모두 동일 (재현성 ±0 강제)."""
    s_values = {s_score(3, 7, 8) for _ in range(500)}
    t_values = {t_score(4, 6, 5, 4, 1.7) for _ in range(500)}
    alpha_values = {alpha(100, 130, 180, 180) for _ in range(500)}
    buy_values = {buy_score(6, 7, 5, 8, 6, 7, 5) for _ in range(500)}
    f_values = {f_score(7, 8, 4, 6) for _ in range(500)}

    assert len(s_values) == 1
    assert len(t_values) == 1
    assert len(alpha_values) == 1
    assert len(buy_values) == 1
    assert len(f_values) == 1
