"""WAVE-ALPHA-001 sub-cycle 14.3 — alpha() 시간 정규화 통합·시나리오 검증.

본 파일 = test_scoring.py::TestAlpha (14.1 단위) 보완 — 통합 시나리오 + interpret_alpha
timeframe 차등 + 외삽 메타 (WF4) + 엣지 케이스 7 (WE1~WE7) 정합.

canon (knowledge/canon/stock-analysis/fractal_wave/01-anchor-and-alpha-formula.md):
    WA1·WA2·WA3 anchor 정의, WF1·WF2·WF3 시간 정규화 공식, WF4 외삽 메타,
    WL1 5단계 label, WE1~WE7 엣지 케이스.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from collectors.scoring import (
    THRESHOLDS,
    TIMEFRAME_LIMITS,
    alpha,
    duration_ratio,
    interpret_alpha,
    progress_to_b,
)


# ---------------------------------------------------------------------------
# 1. WF1·WF2·WF3 시간 정규화 시나리오 (수동 검증 가능 케이스)
# ---------------------------------------------------------------------------


class TestTimeNormalization:
    """canon WF1 (k₁) + WF2 (k₂) + WF3 (α = k₂/k₁) 시간 정규화 본질."""

    def test_same_speed_2x_time_gives_half_alpha(self) -> None:
        """1차 6개월 100→200 (k₁=ln(2)/180) + 2차 12개월 150→300 (k₂=ln(2)/360)
        → α = 0.5 (2차가 동일 비율이지만 시간 2배 → 절반 속도)."""
        a = (date(2024, 1, 1), 100.0)
        b = (date(2024, 7, 1), 200.0)  # +181 days
        c = (date(2024, 10, 1), 150.0)
        cur = (date(2025, 9, 26), 300.0)  # +360 days from C
        result = alpha(a, b, c, cur)
        assert result is not None
        # k₁ = ln(2)/182, k₂ = ln(2)/360, α ≈ 182/360 ≈ 0.506
        assert 0.48 < result < 0.52

    def test_2x_speed_gives_alpha_2(self) -> None:
        """1차 360일 100→200 + 2차 180일 150→300 → α = 2.0 (2차 2배 속도)."""
        a = (date(2023, 1, 1), 100.0)
        b = (date(2023, 12, 27), 200.0)  # ~360 days
        c = (date(2024, 3, 1), 150.0)
        cur = (date(2024, 8, 27), 300.0)  # ~180 days
        result = alpha(a, b, c, cur)
        assert result is not None
        assert 1.9 < result < 2.1

    def test_equal_speed_gives_alpha_1(self) -> None:
        """1차·2차 동일 일별 속도 → α = 1.0."""
        a = (date(2024, 1, 1), 100.0)
        b = (date(2024, 4, 1), 200.0)  # 91 days
        c = (date(2024, 7, 1), 100.0)
        cur = (date(2024, 9, 30), 200.0)  # 91 days
        result = alpha(a, b, c, cur)
        assert result is not None
        assert 0.98 < result < 1.02


# ---------------------------------------------------------------------------
# 2. interpret_alpha 5단계 label timeframe 차등 (canon WL1)
# ---------------------------------------------------------------------------


class TestInterpretAlphaTimeframeDiff:
    """canon WL1 + THRESHOLDS dict — daily/weekly/monthly 차등 임계."""

    @pytest.mark.parametrize("tf,expected_low", [
        ("daily", 0.5), ("weekly", 0.7), ("monthly", 0.8),
    ])
    def test_low_boundary(self, tf: str, expected_low: float) -> None:
        # low 미만 = weak / 정확히 low = modest
        assert interpret_alpha(expected_low - 0.01, tf) == "weak"
        assert interpret_alpha(expected_low, tf) == "modest"

    @pytest.mark.parametrize("tf,sweet_hi", [
        ("daily", 4.0), ("weekly", 3.0), ("monthly", 2.5),
    ])
    def test_sweet_to_overheated_boundary(self, tf: str, sweet_hi: float) -> None:
        assert interpret_alpha(sweet_hi - 0.01, tf) == "sweet"
        assert interpret_alpha(sweet_hi, tf) == "overheated"

    def test_trend_broken_negative(self) -> None:
        for tf in ("daily", "weekly", "monthly"):
            assert interpret_alpha(-0.5, tf) == "trend_broken"
            assert interpret_alpha(0.0, tf) == "trend_broken"

    def test_null_passthrough(self) -> None:
        for tf in ("daily", "weekly", "monthly"):
            assert interpret_alpha(None, tf) is None
            assert interpret_alpha(float("nan"), tf) is None

    def test_overheated_extreme(self) -> None:
        for tf in ("daily", "weekly", "monthly"):
            assert interpret_alpha(100.0, tf) == "overheated"

    def test_invalid_timeframe_raises(self) -> None:
        with pytest.raises(ValueError, match="timeframe"):
            interpret_alpha(1.0, "hourly")

    def test_modest_to_sweet_boundary(self) -> None:
        for tf in ("daily", "weekly", "monthly"):
            assert interpret_alpha(0.99, tf) == "modest"
            assert interpret_alpha(1.0, tf) == "sweet"


# ---------------------------------------------------------------------------
# 3. WE2 / WE3 / WE4 엣지 케이스
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """canon WE2 k1_flat / WE3 trend_broken / 입력 검증."""

    def test_we2_k1_flat_returns_none(self) -> None:
        """B.price ≈ A.price → |k₁| < 1e-6 → α = None."""
        a = (date(2024, 1, 1), 100.0)
        b = (date(2024, 6, 1), 100.0001)  # 거의 동일
        c = (date(2024, 7, 1), 95.0)
        cur = (date(2024, 12, 1), 120.0)
        assert alpha(a, b, c, cur) is None

    def test_we3_trend_broken_current_below_c(self) -> None:
        """current < C → k₂ 음수 → α ≤ 0 → trend_broken label."""
        a = (date(2024, 1, 1), 100.0)
        b = (date(2024, 6, 1), 200.0)
        c = (date(2024, 7, 1), 150.0)
        cur = (date(2024, 12, 1), 120.0)  # C 아래
        result = alpha(a, b, c, cur)
        assert result is not None and result < 0
        assert interpret_alpha(result, "weekly") == "trend_broken"

    def test_we3_current_equals_c(self) -> None:
        """current == C → k₂ = 0 → α = 0 → trend_broken."""
        a = (date(2024, 1, 1), 100.0)
        b = (date(2024, 6, 1), 200.0)
        c = (date(2024, 7, 1), 150.0)
        cur = (date(2024, 12, 1), 150.0)
        result = alpha(a, b, c, cur)
        assert result is not None and result == 0.0
        assert interpret_alpha(result, "daily") == "trend_broken"

    def test_time_reverse_raises(self) -> None:
        """B.date <= A.date → ValueError."""
        a = (date(2024, 6, 1), 100.0)
        b = (date(2024, 1, 1), 200.0)
        c = (date(2024, 7, 1), 150.0)
        cur = (date(2024, 12, 1), 200.0)
        with pytest.raises(ValueError, match="after A.date"):
            alpha(a, b, c, cur)

    def test_current_before_c_raises(self) -> None:
        a = (date(2024, 1, 1), 100.0)
        b = (date(2024, 6, 1), 200.0)
        c = (date(2024, 12, 1), 150.0)
        cur = (date(2024, 7, 1), 180.0)  # current 가 C 보다 과거
        with pytest.raises(ValueError, match="after C.date"):
            alpha(a, b, c, cur)

    def test_price_zero_raises(self) -> None:
        with pytest.raises(ValueError):
            alpha((date(2024, 1, 1), 0.0), (date(2024, 6, 1), 200.0),
                  (date(2024, 7, 1), 150.0), (date(2024, 12, 1), 200.0))

    def test_price_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            alpha((date(2024, 1, 1), -10.0), (date(2024, 6, 1), 200.0),
                  (date(2024, 7, 1), 150.0), (date(2024, 12, 1), 200.0))


# ---------------------------------------------------------------------------
# 4. WF4 외삽 메타 (progress_to_b, duration_ratio)
# ---------------------------------------------------------------------------


class TestExtrapolationMeta:
    """canon WF4 — progress_to_b + duration_ratio."""

    def test_progress_at_b(self) -> None:
        assert progress_to_b(200.0, 200.0) == 1.0

    def test_progress_above_b(self) -> None:
        assert progress_to_b(220.0, 200.0) == 1.1

    def test_progress_below_b(self) -> None:
        assert progress_to_b(180.0, 200.0) == 0.9

    def test_duration_ratio_half(self) -> None:
        """2차 시간이 1차의 절반 → 0.5."""
        a = date(2024, 1, 1)
        b = date(2024, 7, 1)  # 182 days
        c = date(2024, 8, 1)
        cur = date(2024, 11, 1)  # 92 days from C
        r = duration_ratio(a, b, c, cur)
        assert 0.5 < r < 0.52

    def test_duration_ratio_over_one(self) -> None:
        a = date(2024, 1, 1)
        b = date(2024, 4, 1)  # 91 days
        c = date(2024, 5, 1)
        cur = date(2025, 5, 1)  # 365 days from C
        r = duration_ratio(a, b, c, cur)
        assert r > 4.0

    def test_progress_b_zero_raises(self) -> None:
        with pytest.raises(ValueError):
            progress_to_b(100.0, 0.0)


# ---------------------------------------------------------------------------
# 5. TIMEFRAME_LIMITS 정합 (canon WA5 min_bars + min_gap_days)
# ---------------------------------------------------------------------------


class TestTimeframeLimits:
    """TIMEFRAME_LIMITS dict 정합 — canon WA5 timeframe 차등."""

    def test_min_gap_days_ordering(self) -> None:
        """daily < weekly < monthly 순서."""
        assert TIMEFRAME_LIMITS["daily"]["min_gap_days"] < TIMEFRAME_LIMITS["weekly"]["min_gap_days"]
        assert TIMEFRAME_LIMITS["weekly"]["min_gap_days"] < TIMEFRAME_LIMITS["monthly"]["min_gap_days"]

    def test_min_bars_ordering(self) -> None:
        """daily > weekly > monthly (bar 수 = 시간 깊이)."""
        assert TIMEFRAME_LIMITS["daily"]["min_bars"] > TIMEFRAME_LIMITS["weekly"]["min_bars"]
        assert TIMEFRAME_LIMITS["weekly"]["min_bars"] > TIMEFRAME_LIMITS["monthly"]["min_bars"]

    def test_max_history_years_ordering(self) -> None:
        """monthly 가 가장 깊은 history 요구."""
        assert TIMEFRAME_LIMITS["monthly"]["max_history_years"] > TIMEFRAME_LIMITS["weekly"]["max_history_years"]
        assert TIMEFRAME_LIMITS["weekly"]["max_history_years"] > TIMEFRAME_LIMITS["daily"]["max_history_years"]

    def test_thresholds_dict_complete(self) -> None:
        for tf in ("daily", "weekly", "monthly"):
            assert tf in THRESHOLDS
            assert "low" in THRESHOLDS[tf]
            assert "sweet_lo" in THRESHOLDS[tf]
            assert "sweet_hi" in THRESHOLDS[tf]
            # sweet_lo == 1.0 강제 (canon WL1)
            assert THRESHOLDS[tf]["sweet_lo"] == 1.0
