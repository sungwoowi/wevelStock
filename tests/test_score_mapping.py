"""raw 지표 → 0~10 축 매핑 helper 단위 테스트 (INFRA-SCORE-INPUTS-001).

map_to_axis = advisory collapse 점수 입력용 순수 함수.
모든 판단(breakpoints)은 config(SLOT S2) 외부화, 함수는 구간 선형보간만.
같은 입력 → 같은 출력 ±0.
"""

from __future__ import annotations

import pytest

from collectors.scoring import map_to_axis


class TestMapToAxis:
    def test_exact_breakpoint(self) -> None:
        bps = [(0.0, 2.0), (10.0, 8.0)]
        assert map_to_axis(0.0, bps) == 2.0
        assert map_to_axis(10.0, bps) == 8.0

    def test_linear_midpoint(self) -> None:
        # (0→2, 10→8): value 5 → 5.0
        assert map_to_axis(5.0, [(0.0, 2.0), (10.0, 8.0)]) == 5.0

    def test_below_first_clamps_to_first_y(self) -> None:
        assert map_to_axis(-100.0, [(0.0, 3.0), (10.0, 8.0)]) == 3.0

    def test_above_last_clamps_to_last_y(self) -> None:
        assert map_to_axis(100.0, [(0.0, 3.0), (10.0, 8.0)]) == 8.0

    def test_v_shape_non_monotonic(self) -> None:
        # 적정 이격(0) 최고, 양극단 저점 — V자(역). breakpoints y 비단조 허용.
        bps = [(-15.0, 2.0), (0.0, 9.0), (15.0, 2.0)]
        assert map_to_axis(0.0, bps) == 9.0
        assert map_to_axis(-15.0, bps) == 2.0
        assert map_to_axis(15.0, bps) == 2.0
        # -7.5 → 중점 → (2+9)/2 = 5.5
        assert map_to_axis(-7.5, bps) == 5.5

    def test_round_to_half(self) -> None:
        # 0→0, 10→10, value 1 → 1.0 → 1.0 (0.5 단위)
        assert map_to_axis(1.0, [(0.0, 0.0), (10.0, 10.0)]) == 1.0
        # value 3.3 → 3.3 → round 0.5 → 3.5
        assert map_to_axis(3.3, [(0.0, 0.0), (10.0, 10.0)]) == 3.5

    def test_clamp_to_0_10(self) -> None:
        # breakpoint y 가 범위 밖이어도 [0,10] clamp
        assert map_to_axis(5.0, [(0.0, -5.0), (10.0, 15.0)]) == 5.0
        assert map_to_axis(0.0, [(0.0, -5.0), (10.0, 15.0)]) == 0.0
        assert map_to_axis(10.0, [(0.0, -5.0), (10.0, 15.0)]) == 10.0

    def test_single_breakpoint(self) -> None:
        # 1개면 항상 그 y (clamp/round)
        assert map_to_axis(123.0, [(5.0, 7.0)]) == 7.0

    def test_empty_breakpoints_raises(self) -> None:
        with pytest.raises(ValueError):
            map_to_axis(1.0, [])

    def test_none_value_returns_none(self) -> None:
        # 지표 결측(이격도 None 등) → None 전파 (advisory 제외)
        assert map_to_axis(None, [(0.0, 2.0), (10.0, 8.0)]) is None
