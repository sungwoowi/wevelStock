"""INFRA-US-MACRO-SNAPSHOT-001 MS-2 — MarketView 미장 흡수.

entry_posture 단계 강등 + vix_panic 게이트 + one_liner 토큰 + synthesize 흡수.
기존 market_view 회귀는 test_market_view.py 가 커버 (us_macro=None 하위호환).
"""
from __future__ import annotations

from collectors.market_view import (
    apply_us_macro_to_posture,
    entry_posture,
    synthesize_market_view,
)
from collectors.us_macro import USMacroSnapshot


def _us(signal: str, extreme: str = "none", source: str = "computed") -> USMacroSnapshot:
    return USMacroSnapshot(
        date="2026-06-07", nasdaq_change_pct=0.0, sp500_change_pct=0.0, sox_change_pct=0.0,
        vix=15.0, vix_change_pct=0.0, dxy=104.0, dxy_change_pct=0.0,
        us_10y=4.5, us_10y_change_bp=0.0, gold_change_pct=0.0,
        risk_signal=signal, signal_score=0.0, extreme=extreme, source=source,
    )


# ---------------------------------------------------------------------------
# apply_us_macro_to_posture (순수 — U2 단계 강등 + 게이트, 비대칭)
# ---------------------------------------------------------------------------


def test_risk_off_downgrades_one_notch():
    assert apply_us_macro_to_posture("aggressive", _us("risk_off")) == "neutral"
    assert apply_us_macro_to_posture("neutral", _us("risk_off")) == "defensive"
    assert apply_us_macro_to_posture("defensive", _us("risk_off")) == "defensive"


def test_vix_panic_forces_defensive():
    assert apply_us_macro_to_posture("aggressive", _us("risk_off", extreme="vix_panic")) == "defensive"
    # risk_signal 이 뭐든 패닉이면 방어
    assert apply_us_macro_to_posture("aggressive", _us("neutral", extreme="vix_panic")) == "defensive"


def test_asymmetric_risk_on_does_not_upgrade():
    """비대칭 — risk_on 은 자동 상향 안 함."""
    assert apply_us_macro_to_posture("neutral", _us("risk_on")) == "neutral"
    assert apply_us_macro_to_posture("defensive", _us("risk_on")) == "defensive"


def test_neutral_and_unavailable_and_none_unchanged():
    assert apply_us_macro_to_posture("aggressive", _us("neutral")) == "aggressive"
    assert apply_us_macro_to_posture("aggressive", _us("risk_off", source="unavailable")) == "aggressive"
    assert apply_us_macro_to_posture("aggressive", None) == "aggressive"


def test_disabled_config_skips_us(monkeypatch):
    cfg = {"us_macro": {"enabled": False}}
    assert apply_us_macro_to_posture("aggressive", _us("risk_off"), config=cfg) == "aggressive"


# ---------------------------------------------------------------------------
# entry_posture 통합 (KR base 후 미장 적용)
# ---------------------------------------------------------------------------


def test_entry_posture_aggressive_downgraded_by_risk_off():
    """강세+폭강함 → aggressive base, 미장 risk_off → neutral."""
    base = entry_posture("strong_bull", 0.6, 0, us_macro=None)
    assert base == "aggressive"
    with_us = entry_posture("strong_bull", 0.6, 0, us_macro=_us("risk_off"))
    assert with_us == "neutral"


def test_entry_posture_vix_panic_overrides_bull():
    assert entry_posture("strong_bull", 0.6, 0, us_macro=_us("neutral", extreme="vix_panic")) == "defensive"


# ---------------------------------------------------------------------------
# synthesize_market_view 흡수 (one_liner 토큰 + reason)
# ---------------------------------------------------------------------------


def _macro_dict(regime_inputs: dict) -> dict:
    """classify_market_regime 가 읽는 최소 dict."""
    return {
        "position": regime_inputs.get("position", "above_both"),
        "trend": regime_inputs.get("trend", "uptrend"),
        "ma20_slope_pct_5d": regime_inputs.get("slope", 1.0),
        "breadth_ratio": regime_inputs.get("breadth", 0.6),
        "distribution_count_25d": regime_inputs.get("dd", 0),
    }


def test_synthesize_absorbs_risk_off_token_and_reason():
    macro = _macro_dict({})  # strong_bull-ish
    view = synthesize_market_view(
        macro, today_rs=[], prev_rs=None, market="KOSPI", date_str="2026-06-07",
        us_macro=_us("risk_off"),
    )
    assert "미장 위험회피" in view.one_liner
    assert any("미장 야간" in r for r in view.reasons)


def test_synthesize_neutral_us_no_token():
    macro = _macro_dict({})
    view = synthesize_market_view(
        macro, today_rs=[], prev_rs=None, market="KOSPI", date_str="2026-06-07",
        us_macro=_us("neutral"),
    )
    assert "미장" not in view.one_liner


def test_synthesize_no_us_backward_compatible():
    """us_macro=None → 기존 동작 (토큰·reason 무흡수)."""
    macro = _macro_dict({})
    view = synthesize_market_view(
        macro, today_rs=[], prev_rs=None, market="KOSPI", date_str="2026-06-07",
    )
    assert "미장" not in view.one_liner
