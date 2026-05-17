"""결정론 채점 (S-Score / T-Score / α / buy_score / F-Score).

ANALYST-PERSONAS-001 v2 옵션 b — 채점은 코드 stage, canon md 는 원리 인용 권위.
모든 함수는 순수 (LLM 호출 X, 같은 입력 → 같은 출력 ±0).
모든 점수 출력 = 0~10 범위, 0.5 단위 (재현성 ±0.5 강제).

발행 분석가 / canon 인용:
    s_score:   stock_picker      / principles/stock_selection
    t_score:   trader            / trading/entry_exit (α 오버라이드 적용)
    alpha:     stock_analyst     / stock-analysis/fractal_wave (W1 등)
    buy_score: stock_picker (B)  / stock_selection/momentum_leaders (CAN SLIM 7축)
    f_score:   flow_analyzer     / flow_analysis/sector_flow + stock_flow

공식 SLOT:
    s_score / t_score / buy_score 의 합산 공식 = SPEC S7 SLOT,
        분석가 manifest 작성 시 정식 가중치 확정. 현재 = 균등 가중 평균 placeholder.
    alpha 공식 = WAVE-ALPHA-001 백로그.
        현재 = ln(C/B) / ln(B/A) placeholder (current 인자는 정식 외삽 검증용).
    f_score 공식 = SPEC v2 명시 (4 축 가중 합) — 그대로 구현.
    α 오버라이드 = STRATEGY-TRACK-001 명시 — 그대로 구현.
"""

from __future__ import annotations

import math


def _clamp(value: float, *, low: float = 0.0, high: float = 10.0) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


def _round_to_half(value: float) -> float:
    return round(value * 2) / 2


def _validate_unit_score(name: str, value: float) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{name} must be int or float, got {type(value).__name__}")
    if value < 0 or value > 10:
        raise ValueError(f"{name} must be in [0, 10], got {value}")


def s_score(rs: float, supply_chain: float, alignment: float) -> float:
    """주도주 점수 — stock_picker 발행, principles/stock_selection framework 권위.

    placeholder = 균등 3축 평균 → 0.5 단위 (SPEC S7 SLOT).

    Args:
        rs: Relative Strength (0-10) — 시장·섹터 대비 상대강도.
        supply_chain: 공급망 위계 (0-10) — 산업 트렌드 중심도.
        alignment: 정배열 (0-10) — 월·주·일봉 위계.

    Returns:
        0~10, 0.5 단위 float.
    """
    for name, val in (("rs", rs), ("supply_chain", supply_chain), ("alignment", alignment)):
        _validate_unit_score(name, val)
    raw = (rs + supply_chain + alignment) / 3
    return _clamp(_round_to_half(raw))


def t_score(
    divergence: float,
    macd: float,
    volume: float,
    rr: float,
    alpha: float,
) -> float:
    """타점 점수 — trader 발행, trading/entry_exit framework 권위.

    α 가속계수 오버라이드 (STRATEGY-TRACK-001):
        α  < 1.3       → 기본 (4축 균등 평균)
        1.3 ≤ α < 1.5  → max(기본, 5.0)  발산 시작
        1.5 ≤ α < 2.0  → max(기본, 7.0)  강발산 ⭐
        α  ≥ 2.0       → min(기본, 3.0)  폭주, 부분 청산

    Args:
        divergence: 이격도 점수 (0-10).
        macd: MACD 점수 (0-10).
        volume: 거래량 점수 (0-10).
        rr: R/R 점수 (0-10).
        alpha: 가속계수 (≥ 0.0, 로그 발산 비).

    Returns:
        0~10, 0.5 단위 float.
    """
    for name, val in (
        ("divergence", divergence),
        ("macd", macd),
        ("volume", volume),
        ("rr", rr),
    ):
        _validate_unit_score(name, val)
    if not isinstance(alpha, (int, float)) or isinstance(alpha, bool):
        raise TypeError(f"alpha must be int or float, got {type(alpha).__name__}")
    if alpha < 0:
        raise ValueError(f"alpha must be >= 0, got {alpha}")

    base = _round_to_half((divergence + macd + volume + rr) / 4)
    if alpha < 1.3:
        adjusted = base
    elif alpha < 1.5:
        adjusted = max(base, 5.0)
    elif alpha < 2.0:
        adjusted = max(base, 7.0)
    else:
        adjusted = min(base, 3.0)
    return _clamp(_round_to_half(adjusted))


def alpha(anchor_a: float, anchor_b: float, anchor_c: float, current: float) -> float:
    """가속계수 — stock_analyst 발행, stock-analysis/fractal_wave (W1 등) framework 권위.

    placeholder = ln(C/B) / ln(B/A) (B→C 추세 vs A→B 추세 비).
    정식 공식 = WAVE-ALPHA-001 SPEC (백로그). current 인자는 외삽 검증용 (현재 미사용).

    Args:
        anchor_a, anchor_b, anchor_c: 1·2·3차 앵커 가격 (> 0, 단조 증가).
        current: 현재 가격 (> 0). 정식 공식에서 외삽 검증용.

    Returns:
        α ≥ 0 (정상 추세 ≈ 1.0, 발산 시작 ≥ 1.3, 강발산 ≥ 1.5, 폭주 ≥ 2.0).

    Raises:
        ValueError: 가격 ≤ 0 또는 앵커 비단조 (A < B < C 강제).
    """
    for name, val in (
        ("anchor_a", anchor_a),
        ("anchor_b", anchor_b),
        ("anchor_c", anchor_c),
        ("current", current),
    ):
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            raise TypeError(f"{name} must be int or float, got {type(val).__name__}")
        if val <= 0:
            raise ValueError(f"{name} must be > 0, got {val}")
    if not (anchor_a < anchor_b < anchor_c):
        raise ValueError(
            f"앵커 단조 증가 위배 — A < B < C 강제 "
            f"(got A={anchor_a}, B={anchor_b}, C={anchor_c})"
        )
    base_slope = math.log(anchor_b / anchor_a)
    next_slope = math.log(anchor_c / anchor_b)
    return next_slope / base_slope


def buy_score(
    c: float,
    a: float,
    n: float,
    s: float,
    l: float,
    i: float,
    m: float,
) -> float:
    """매수 점수 (CAN SLIM 7축) — stock_picker (Track B) 발행, stock_selection/momentum_leaders.

    placeholder = 균등 7축 평균 → 0.5 단위 (SPEC S7 SLOT).

    Args:
        c: Current quarterly earnings (0-10).
        a: Annual earnings (0-10).
        n: New products / management (0-10).
        s: Supply & demand (0-10).
        l: Leader or laggard (0-10).
        i: Institutional sponsorship (0-10).
        m: Market direction (0-10).

    Returns:
        0~10, 0.5 단위 float.
    """
    components = {"c": c, "a": a, "n": n, "s": s, "l": l, "i": i, "m": m}
    for name, val in components.items():
        _validate_unit_score(name, val)
    raw = sum(components.values()) / 7
    return _clamp(_round_to_half(raw))


def f_score(
    theme_match: float,
    momentum: float,
    inflow_speed: float,
    agreement: float,
) -> float:
    """수급 점수 — flow_analyzer 발행, flow_analysis/sector_flow + stock_flow framework.

    SPEC v2 명시 공식:
        F = round(2 × (0.4·theme + 0.3·momentum + 0.2·inflow + 0.1·agreement)) / 2

    Args:
        theme_match: 테마-주체 매칭 (0-10) — 종목 테마와 권위 주체 매수 일치도.
        momentum: 60일 수급 모멘텀 (0-10) — 외인·기관 누적 부호 turnaround.
        inflow_speed: 시총 정규화 자금 유입 속도 (0-10).
        agreement: 5주체 부호 일치도 (0-10).

    Returns:
        0~10, 0.5 단위 float.
    """
    for name, val in (
        ("theme_match", theme_match),
        ("momentum", momentum),
        ("inflow_speed", inflow_speed),
        ("agreement", agreement),
    ):
        _validate_unit_score(name, val)
    raw = 0.4 * theme_match + 0.3 * momentum + 0.2 * inflow_speed + 0.1 * agreement
    return _clamp(_round_to_half(raw))
