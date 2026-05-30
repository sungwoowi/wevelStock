"""결정론 채점 (S-Score / T-Score / α / buy_score / F-Score).

ANALYST-PERSONAS-001 v2 옵션 b — 채점은 코드 stage, canon md 는 원리 인용 권위.
모든 함수는 순수 (LLM 호출 X, 같은 입력 → 같은 출력 ±0).
모든 점수 출력 = 0~10 범위, 0.5 단위 (재현성 ±0.5 강제).

발행 분석가 / canon 인용:
    s_score:   stock_picker      / principles/stock_selection
    t_score:   trader            / trading/entry_exit (α 오버라이드 적용)
    alpha:     stock_analyst     / stock-analysis/fractal_wave (WA·WF·WL·WE·WX 21 명제, WAVE-ALPHA-001)
    buy_score: stock_picker (B)  / stock_selection/momentum_leaders (CAN SLIM 7축)
    f_score:   flow_analyzer     / flow_analysis/sector_flow + stock_flow

공식 SLOT:
    s_score / t_score / buy_score 의 합산 공식 = SPEC S7 SLOT,
        분석가 manifest 작성 시 정식 가중치 확정. 현재 = 균등 가중 평균 placeholder.
    alpha 공식 = WAVE-ALPHA-001 SPEC 정식 = 시간 정규화 기울기 비율
        (k₁=ln(B/A)/days(A→B), k₂=ln(current/C)/days(C→current), α=k₂/k₁).
    f_score 공식 = SPEC v2 명시 (4 축 가중 합) — 그대로 구현.
    α 오버라이드 = STRATEGY-TRACK-001 명시 — 그대로 구현.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Literal


# ============================================================
# WAVE-ALPHA-001 상수 (canon WL1 + WA5 정합)
# ============================================================

THRESHOLDS: dict[str, dict[str, float]] = {
    "daily":   {"low": 0.5, "sweet_lo": 1.0, "sweet_hi": 4.0},
    "weekly":  {"low": 0.7, "sweet_lo": 1.0, "sweet_hi": 3.0},
    "monthly": {"low": 0.8, "sweet_lo": 1.0, "sweet_hi": 2.5},
}

TIMEFRAME_LIMITS: dict[str, dict[str, int]] = {
    "daily":   {"min_gap_days": 5,   "min_bars": 250, "max_history_years": 3},
    "weekly":  {"min_gap_days": 35,  "min_bars": 156, "max_history_years": 5},
    "monthly": {"min_gap_days": 180, "min_bars": 60,  "max_history_years": 15},
}

AlphaLabel = Literal["trend_broken", "weak", "modest", "sweet", "overheated"]
Anchor = tuple[date, float]  # (date, price)


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


# ============================================================
# raw 지표 → 0~10 축 매핑 (INFRA-SCORE-INPUTS-001 — advisory collapse 입력용)
# ============================================================


def map_to_axis(
    value: float | None,
    breakpoints: list[tuple[float, float]],
) -> float | None:
    """raw 지표값 → 0~10 축 점수. 구간 선형보간 + [0,10] clamp + 0.5 단위.

    모든 판단(임계·곡선 모양)은 breakpoints(config, SLOT S2)에 위임 — 함수는 보간만.
    breakpoints 의 y(점수)는 비단조 허용 → V자(적정 이격 최고, 양극단 저점) 표현 가능.
    advisory collapse 점수(t_score/f_score)의 축 입력 용도 — 권위 X (LLM override).

    Args:
        value: raw 지표값 (예: 이격도 % / 거래량 배율 / R/R). None 이면 None 전파.
        breakpoints: (raw_x, score_y) 쌍 리스트. raw_x 오름차순 가정.

    Returns:
        0~10, 0.5 단위 float. value None → None.

    Raises:
        ValueError: breakpoints 빈 리스트.
    """
    if not breakpoints:
        raise ValueError("breakpoints must be non-empty")
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None

    pts = sorted(breakpoints, key=lambda p: p[0])
    x = float(value)
    # 범위 밖 → 끝점 clamp
    if x <= pts[0][0]:
        return _clamp(_round_to_half(pts[0][1]))
    if x >= pts[-1][0]:
        return _clamp(_round_to_half(pts[-1][1]))
    # 구간 선형보간
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return _clamp(_round_to_half(y1))
            frac = (x - x0) / (x1 - x0)
            interp = y0 + frac * (y1 - y0)
            return _clamp(_round_to_half(interp))
    # 도달 불가 (위 clamp 가 커버)
    return _clamp(_round_to_half(pts[-1][1]))


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
    """타점 점수 (advisory 참고선) — trading/entry_exit framework.

    ⚠️ INFRA-SCORE-INPUTS-001 정련 (메모리 feedback_score_collapse_advisory):
    이 고정 가중 collapse 점수는 **advisory 베이스라인**으로 강등됨 — 게이트키핑 X.
    권위는 원시 지표(이격도·MACD·거래량비·R/R) + trader LLM 의 고차원 종합이며, trader 는
    이 값을 override 할 수 있다. 백테스팅·일관성 비교용 결정론 base 로만 유지.

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


def _validate_anchor(name: str, value: Anchor) -> tuple[date, float]:
    """Anchor tuple (date, price) 유효성 검증. (date, float) 반환."""
    if not isinstance(value, tuple) or len(value) != 2:
        raise TypeError(f"{name} must be tuple (date, price), got {type(value).__name__}")
    d, p = value
    if not isinstance(d, date):
        raise TypeError(f"{name}.date must be datetime.date, got {type(d).__name__}")
    if not isinstance(p, (int, float)) or isinstance(p, bool):
        raise TypeError(f"{name}.price must be int or float, got {type(p).__name__}")
    if p <= 0:
        raise ValueError(f"{name}.price must be > 0, got {p}")
    return d, float(p)


def alpha(
    anchor_a: Anchor,
    anchor_b: Anchor,
    anchor_c: Anchor,
    current: Anchor,
) -> float | None:
    """가속계수 (시간 정규화 기울기 비율) — stock_analyst 발행, WAVE-ALPHA-001 정식.

    canon: WF1 (k₁) + WF2 (k₂) + WF3 (α=k₂/k₁) + WE2 (k1_flat) + WE3 (trend_broken).

    공식:
        k₁ = ln(B.price / A.price) / (B.date - A.date).days
        k₂ = ln(current.price / C.price) / (current.date - C.date).days
        α  = k₂ / k₁

    Args:
        anchor_a: (date, price) — 1차 발산 시작점 (장기 바닥 후 첫 상승 진입)
        anchor_b: (date, price) — 1차 발산 정점
        anchor_c: (date, price) — 1차 되돌림 저점 = 2차 발산 시작점
        current:  (date, price) — 현재가 (외삽 검증용)

    Returns:
        α (무차원) 또는 None (WE2 k1_flat 시).
        - α > 0 = 2차 발산 진행 (정상)
        - α ≤ 0 = trend_broken (current ≤ C, canon WE3)

    Raises:
        TypeError: 인자 타입 위반
        ValueError: 가격 ≤ 0, 시간 역행 (days ≤ 0).
    """
    a_date, a_price = _validate_anchor("anchor_a", anchor_a)
    b_date, b_price = _validate_anchor("anchor_b", anchor_b)
    c_date, c_price = _validate_anchor("anchor_c", anchor_c)
    cur_date, cur_price = _validate_anchor("current", current)

    days_ab = (b_date - a_date).days
    days_c_cur = (cur_date - c_date).days
    if days_ab <= 0:
        raise ValueError(f"B.date must be after A.date, got A={a_date}, B={b_date}")
    if days_c_cur <= 0:
        raise ValueError(f"current.date must be after C.date, got C={c_date}, current={cur_date}")

    k1 = math.log(b_price / a_price) / days_ab
    if abs(k1) < 1e-6:
        return None  # canon WE2 — 1차 발산 평탄, α 무의미
    k2 = math.log(cur_price / c_price) / days_c_cur
    return k2 / k1


def interpret_alpha(value: float | None, timeframe: str) -> AlphaLabel | None:
    """α → 5 단계 label (canon WL1). timeframe 별 차등 임계.

    Args:
        value: alpha() 산출값 또는 None
        timeframe: "daily" | "weekly" | "monthly"

    Returns:
        "trend_broken" | "weak" | "modest" | "sweet" | "overheated" 또는 None
        (value is None 또는 NaN).

    Raises:
        ValueError: timeframe 미지정.
    """
    if timeframe not in THRESHOLDS:
        raise ValueError(f"timeframe must be one of {list(THRESHOLDS)}, got {timeframe!r}")
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    t = THRESHOLDS[timeframe]
    if value <= 0:
        return "trend_broken"
    if value < t["low"]:
        return "weak"
    if value < t["sweet_lo"]:
        return "modest"
    if value < t["sweet_hi"]:
        return "sweet"
    return "overheated"


def progress_to_b(current_price: float, b_price: float) -> float:
    """1차 정점 대비 현재가 비율 (canon WF4).

    ≥ 1.0 = B 돌파, 0.7~1.0 = B 근접 (sweet 근접), < 0.7 = 잠재력 큼.
    """
    if not isinstance(current_price, (int, float)) or isinstance(current_price, bool):
        raise TypeError(f"current_price must be number, got {type(current_price).__name__}")
    if not isinstance(b_price, (int, float)) or isinstance(b_price, bool):
        raise TypeError(f"b_price must be number, got {type(b_price).__name__}")
    if b_price <= 0:
        raise ValueError(f"b_price must be > 0, got {b_price}")
    return current_price / b_price


def duration_ratio(a_date: date, b_date: date, c_date: date, current_date: date) -> float:
    """1차 발산 시간 대비 2차 진행 시간 비율 (canon WF4).

    < 0.3 = 2차 너무 초기 (외삽 신뢰도 낮음)
    0.3~1.0 = 진행 중
    > 1.0 = 2차가 1차보다 길게 진행
    """
    for name, d in (("a_date", a_date), ("b_date", b_date), ("c_date", c_date), ("current_date", current_date)):
        if not isinstance(d, date):
            raise TypeError(f"{name} must be datetime.date, got {type(d).__name__}")
    days_ab = (b_date - a_date).days
    days_c_cur = (current_date - c_date).days
    if days_ab <= 0:
        raise ValueError(f"B.date must be after A.date, got A={a_date}, B={b_date}")
    return days_c_cur / days_ab


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
    """수급 점수 (advisory 참고선) — flow_analysis/sector_flow + stock_flow framework.

    ⚠️ INFRA-SCORE-INPUTS-001 정련 (메모리 feedback_score_collapse_advisory):
    이 고정 가중 collapse 점수는 **advisory 베이스라인**으로 강등됨 — 게이트키핑 X.
    권위는 원시 수급 지표(60일 모멘텀·자금 속도·5주체 일치도) + flow_analyzer LLM 의 종합이며,
    flow_analyzer 는 override 할 수 있다. theme_match 직관축은 SLOT S1 (2-Stage) 까지 중립.

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
