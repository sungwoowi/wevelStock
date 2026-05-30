"""score_inputs.yaml 로더 단위 테스트 (INFRA-SCORE-INPUTS-001 M2)."""

from __future__ import annotations

from collectors.score_inputs_config import (
    get_advisory_constant,
    get_breakpoints,
    load_score_inputs_config,
    reload_score_inputs_config,
)


def setup_function() -> None:
    reload_score_inputs_config()


def test_loads_real_config() -> None:
    cfg = load_score_inputs_config()
    assert "technicals" in cfg
    assert "flow" in cfg


def test_get_breakpoints_divergence() -> None:
    bps = get_breakpoints("technicals", "divergence")
    assert len(bps) >= 2
    # 오름차순 x, 튜플 float
    xs = [x for x, _ in bps]
    assert xs == sorted(xs)
    assert all(isinstance(x, float) and isinstance(y, float) for x, y in bps)


def test_get_breakpoints_all_axes_present() -> None:
    for axis in ("divergence", "macd", "volume", "rr"):
        assert get_breakpoints("technicals", axis), f"technicals.{axis} 누락"
    for axis in ("momentum", "inflow_speed"):
        assert get_breakpoints("flow", axis), f"flow.{axis} 누락"


def test_get_breakpoints_unknown_returns_empty() -> None:
    assert get_breakpoints("technicals", "nonexistent") == []
    assert get_breakpoints("nonexistent", "divergence") == []


def test_advisory_constant() -> None:
    assert get_advisory_constant("theme_match_neutral", 0.0) == 5.0
    assert get_advisory_constant("nonexistent_key", 7.0) == 7.0
