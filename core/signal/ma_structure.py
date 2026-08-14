"""다중 시간축 이평 구조 해석 (ADVISOR-CORE-001 M1-F3).

**사용자 정의 체계** (2026-08-13 인터뷰 — `docs/a_wanted/user_want_spec.md` 의
"인터뷰 대기" 항목 해소):

> 일봉 **7·13·20·60·120** / 주봉 **5·10·20** / 월봉 **종가기준 7월선 지지력**.
> 단기–중기–장기 이평 간 **변곡 여부 탐지**와 **이평 이격도의 미적분적 포착**(수렴/발산·가속).
> **주도 종목뿐 아니라 지수 차트에도 해당하는 구조적 차트해석법.**

그래서 이 모듈은 종목 전용이 아니라 **지수·종목 공용 렌즈**다. 같은 함수에 코스피 일봉을
넣으면 지수 구조가, 삼성전자 일봉을 넣으면 종목 구조가 나온다.

**미적분적 포착이 핵심**이다. 이격도의 *현재값*만 보면 "20일선 위 3%" 같은 정지 사진이라
국면 전환을 못 본다. 그래서 이격도 시계열의
  - **1차 미분(velocity)** = 벌어지는 중인가 좁혀지는 중인가 → `motion`
  - **2차 미분(acceleration)** = 그 속도가 붙는가 죽는가 → `accel`
를 같이 산출한다. *"20일선 아래지만 3봉째 빠르게 좁혀지며 가속"* = 상향 돌파 시도이고,
이건 이격도 한 숫자로는 절대 안 보인다.

**순수** — LLM 0 · I/O 0 · DB 0. 입력은 DatetimeIndex 를 가진 OHLCV DataFrame.
데이터가 모자란 축은 **None + 사유**로 남긴다 (근사·추정 금지 — [[feedback_no_false_certainty]]).
판단·해석은 LLM 몫이고, 이 모듈은 **코드가 먼저 감지해 이름을 붙이는** 층이다 (F2 와 같은 결).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from collectors.anchors import resample_ohlcv

# ---------------------------------------------------------------------------
# 이평 세트 — 사용자 정의 (2026-08-13). 변경은 본질 문서 동기화 필요.
# ---------------------------------------------------------------------------

DAILY_MAS: tuple[int, ...] = (7, 13, 20, 60, 120)
WEEKLY_MAS: tuple[int, ...] = (5, 10, 20)
MONTHLY_MAS: tuple[int, ...] = (7,)

MA_SETS: dict[str, tuple[int, ...]] = {
    "daily": DAILY_MAS,
    "weekly": WEEKLY_MAS,
    "monthly": MONTHLY_MAS,
}

# 미분 관측창 (봉 단위). 시간축마다 1봉의 무게가 달라 같은 창을 쓰면 주/월봉이 과민해진다.
_DERIV_WINDOW: dict[str, int] = {"daily": 5, "weekly": 3, "monthly": 2}

# 판정 임계 — 실측 분포가 쌓이면 config 외부화 대상(SLOT). 지금은 보수적 기본값 + 근거.
_FLAT_VELOCITY = 0.05      # %/봉. 이보다 느린 이격도 변화는 잡음으로 본다.
_FLAT_ACCEL = 0.03         # %/봉². 가속 판정 하한.
_NEAR_MA_PCT = 3.0         # 이평 ±3% 안 = "접점" — 돌파/이탈 시도를 말할 수 있는 거리.
_CROSS_LOOKBACK = 5        # 최근 N봉 안의 스프레드 부호 전환 = 실제 크로스 발생.
_CROSS_IMMINENT_PCT = 1.5  # 스프레드가 이 안이고 좁혀지는 중 = 크로스 임박.
_MAX_BARS_TO_CROSS = 20    # 선형 외삽은 이 이상 나가면 의미 없다 → None.

# 스프레드로 볼 이평 쌍 (단기–중기, 중기–장기).
_SPREAD_PAIRS: dict[str, tuple[tuple[int, int], ...]] = {
    "daily": ((7, 20), (20, 60), (60, 120)),
    "weekly": ((5, 10), (10, 20)),
    "monthly": (),
}


# ---------------------------------------------------------------------------
# 자료구조
# ---------------------------------------------------------------------------


@dataclass
class MADeviation:
    """한 이평선에 대한 이격도와 그 1차·2차 미분."""

    period: int
    ma: float | None = None
    deviation_pct: float | None = None   # (close - ma) / ma * 100
    velocity: float | None = None        # 1차 — %/봉
    acceleration: float | None = None    # 2차 — %/봉²
    phase: str | None = None             # above | below
    motion: str | None = None            # diverging | converging | flat
    accel: str | None = None             # accelerating | decelerating | steady


@dataclass
class MASpread:
    """이평 간 간격 — 단기가 장기를 향해 좁히는지 벌리는지."""

    fast: int
    slow: int
    spread_pct: float | None = None      # (fast_ma - slow_ma) / slow_ma * 100
    velocity: float | None = None
    state: str | None = None             # widening|narrowing|cross_imminent|golden_cross|dead_cross
    bars_to_cross: int | None = None     # 선형 외삽 (근사라 상한 밖은 None)


@dataclass
class MonthlySupport:
    """월봉 7선 지지력 — 사용자가 명시적으로 요구한 축 (종가 기준)."""

    ma7: float | None = None
    close: float | None = None
    above: bool | None = None
    deviation_pct: float | None = None
    months_held: int | None = None       # 현재 상태(위/아래)를 유지한 연속 개월
    event: str | None = None             # regained | lost | holding | below


@dataclass
class TimeframeStructure:
    """한 시간축의 구조 판정."""

    timeframe: str
    bars: int = 0
    close: float | None = None
    order: str | None = None             # bullish_stack | bearish_stack | mixed
    deviations: list[MADeviation] = field(default_factory=list)
    spreads: list[MASpread] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def dev(self, period: int) -> MADeviation | None:
        return next((d for d in self.deviations if d.period == period), None)


@dataclass
class MAStructure:
    """지수 또는 종목 하나의 다중 시간축 구조."""

    name: str
    daily: TimeframeStructure | None = None
    weekly: TimeframeStructure | None = None
    monthly: TimeframeStructure | None = None
    monthly_support: MonthlySupport | None = None
    labels: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict

        return asdict(self)


# ---------------------------------------------------------------------------
# 순수 계산
# ---------------------------------------------------------------------------


def _finite(v: Any) -> float | None:
    """NaN·inf·None 을 전부 None 으로 (0 과 구분 — 빈 값을 0 으로 읽는 사고 차단)."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _slope(series: pd.Series, window: int) -> float | None:
    """최근 `window` 봉의 평균 변화율 (단위: 값/봉).

    최소제곱 대신 양 끝 차분 — 이격도는 노이즈가 크고, 여기서 필요한 건 정밀한 기울기가
    아니라 **방향과 대략의 속도**다. 봉이 모자라면 None (짧은 창으로 억지 추정하지 않는다).
    """
    s = series.dropna()
    if len(s) < window + 1:
        return None
    a, b = _finite(s.iloc[-1 - window]), _finite(s.iloc[-1])
    if a is None or b is None:
        return None
    return (b - a) / window


def _classify_motion(deviation: float | None, velocity: float | None) -> tuple[str | None, str | None]:
    """(phase, motion) — 이평 위/아래 × 벌어짐/좁혀짐.

    부호 조합의 의미가 직관과 어긋나기 쉬워 명시한다:
      이평 **위**에서 이격 ↑ = diverging(위로 벌어짐, 과열 방향)
      이평 **위**에서 이격 ↓ = converging(이평으로 회귀, 눌림)
      이평 **아래**에서 이격 ↑ = converging(밑에서 회복, 돌파 시도)
      이평 **아래**에서 이격 ↓ = diverging(아래로 벌어짐, 이탈 심화)
    """
    if deviation is None:
        return None, None
    phase = "above" if deviation >= 0 else "below"
    if velocity is None:
        return phase, None
    if abs(velocity) < _FLAT_VELOCITY:
        return phase, "flat"
    if phase == "above":
        return phase, "diverging" if velocity > 0 else "converging"
    return phase, "converging" if velocity > 0 else "diverging"


def _classify_accel(velocity: float | None, acceleration: float | None) -> str | None:
    """2차 미분 — 진행 방향으로 힘이 붙는가 죽는가.

    가속도의 부호 자체가 아니라 **속도와 같은 방향인지**를 본다. 하락 이격이 더 빨리
    떨어지는 것도 '가속'이다.
    """
    if velocity is None or acceleration is None:
        return None
    if abs(acceleration) < _FLAT_ACCEL:
        return "steady"
    return "accelerating" if (acceleration > 0) == (velocity > 0) else "decelerating"


def _deviation_series(close: pd.Series, period: int) -> pd.Series | None:
    """이격도 시계열 — 미분의 입력. 봉 부족 시 None."""
    if len(close) < period:
        return None
    ma = close.rolling(window=period).mean()
    dev = (close - ma) / ma * 100
    return dev.dropna()


def _build_deviation(close: pd.Series, period: int, window: int) -> MADeviation:
    d = MADeviation(period=period)
    if len(close) < period:
        return d
    ma_series = close.rolling(window=period).mean()
    d.ma = _finite(ma_series.iloc[-1])
    dev_series = _deviation_series(close, period)
    if dev_series is None or len(dev_series) == 0:
        return d
    d.deviation_pct = _finite(dev_series.iloc[-1])
    d.velocity = _slope(dev_series, window)
    # 2차 = 직전 창의 속도와 비교. 두 창을 담을 봉이 있어야 한다.
    prev_velocity = _slope(dev_series.iloc[:-window], window) if len(dev_series) > 2 * window else None
    if d.velocity is not None and prev_velocity is not None:
        d.acceleration = (d.velocity - prev_velocity) / window
    d.phase, d.motion = _classify_motion(d.deviation_pct, d.velocity)
    d.accel = _classify_accel(d.velocity, d.acceleration)
    return d


def _classify_order(devs: list[MADeviation]) -> str | None:
    """정배열 / 역배열 / 혼조 — 짧은 이평이 긴 이평 위에 순서대로 있는가."""
    vals = [(d.period, d.ma) for d in devs if d.ma is not None]
    if len(vals) < 2:
        return None
    vals.sort(key=lambda x: x[0])
    mas = [m for _, m in vals]
    if all(a > b for a, b in zip(mas, mas[1:])):
        return "bullish_stack"
    if all(a < b for a, b in zip(mas, mas[1:])):
        return "bearish_stack"
    return "mixed"


def _build_spread(close: pd.Series, fast: int, slow: int, window: int) -> MASpread:
    sp = MASpread(fast=fast, slow=slow)
    if len(close) < slow:
        return sp
    fast_ma = close.rolling(window=fast).mean()
    slow_ma = close.rolling(window=slow).mean()
    series = ((fast_ma - slow_ma) / slow_ma * 100).dropna()
    if len(series) == 0:
        return sp
    sp.spread_pct = _finite(series.iloc[-1])
    sp.velocity = _slope(series, window)
    if sp.spread_pct is None:
        return sp

    # ① 최근 실제 크로스 — lookback 안에서 부호가 뒤집혔나.
    recent = series.tail(_CROSS_LOOKBACK + 1)
    if len(recent) >= 2:
        first, last = _finite(recent.iloc[0]), _finite(recent.iloc[-1])
        if first is not None and last is not None and (first >= 0) != (last >= 0):
            sp.state = "golden_cross" if last >= 0 else "dead_cross"
            return sp

    # ② 임박 — 간격이 좁고 0 을 향해 움직이는 중.
    approaching = (
        sp.velocity is not None
        and abs(sp.velocity) >= _FLAT_VELOCITY
        and (sp.spread_pct > 0) != (sp.velocity > 0)
    )
    if approaching:
        bars = abs(sp.spread_pct / sp.velocity) if sp.velocity else None
        if bars is not None and bars <= _MAX_BARS_TO_CROSS:
            sp.bars_to_cross = int(round(bars))
        if abs(sp.spread_pct) <= _CROSS_IMMINENT_PCT:
            sp.state = "cross_imminent"
            return sp
        sp.state = "narrowing"
        return sp
    if sp.velocity is None or abs(sp.velocity) < _FLAT_VELOCITY:
        sp.state = "flat"
    else:
        sp.state = "widening"
    return sp


# ---------------------------------------------------------------------------
# 라벨 — 코드가 먼저 감지해 이름을 붙인다 (F2 와 같은 결)
# ---------------------------------------------------------------------------

_TF_KR = {"daily": "일봉", "weekly": "주봉", "monthly": "월봉"}
_ORDER_KR = {"bullish_stack": "정배열", "bearish_stack": "역배열", "mixed": "혼조"}


def _ma_label(timeframe: str, period: int) -> str:
    unit = {"daily": "일", "weekly": "주", "monthly": "월"}[timeframe]
    return f"{period}{unit}선"


def _timeframe_labels(tf: TimeframeStructure) -> list[str]:
    """이 시간축에서 사람이 알아야 할 사건만 문장으로. 나열이 아니라 선별이다."""
    out: list[str] = []
    if tf.order in _ORDER_KR and tf.order != "mixed":
        out.append(f"{_TF_KR[tf.timeframe]} {_ORDER_KR[tf.order]}")

    # 같은 사건이 이평마다 반복되면(7·13·20선이 나란히 "이격 확대 가속") 한 가지 사실이
    # 라벨 슬롯을 다 먹는다 → 사건별로 묶어 "7·13·20일선 이격 확대 가속" 한 줄로.
    unit = {"daily": "일", "weekly": "주", "monthly": "월"}[tf.timeframe]
    events: list[tuple[int, str]] = []
    for d in tf.deviations:
        if d.deviation_pct is None or d.motion is None:
            continue
        near = abs(d.deviation_pct) <= _NEAR_MA_PCT
        accel_kr = {"accelerating": " 가속", "decelerating": " 감속"}.get(d.accel or "", "")
        if near and d.phase == "below" and d.motion == "converging":
            events.append((d.period, f"상향 돌파 시도{accel_kr}"))
        elif near and d.phase == "above" and d.motion == "converging":
            events.append((d.period, f"지지 시험{accel_kr}"))
        elif d.phase == "below" and d.motion == "diverging" and d.accel == "accelerating":
            events.append((d.period, "이탈 심화"))
        elif d.phase == "above" and d.motion == "diverging" and d.accel == "accelerating":
            events.append((d.period, "이격 확대 가속"))

    grouped: dict[str, list[int]] = {}
    for period, event in events:
        grouped.setdefault(event, []).append(period)
    for event, periods in grouped.items():
        names = "·".join(str(p) for p in periods)
        out.append(f"{names}{unit}선 {event}")

    for sp in tf.spreads:
        fast, slow = _ma_label(tf.timeframe, sp.fast), _ma_label(tf.timeframe, sp.slow)
        if sp.state == "golden_cross":
            out.append(f"{fast}·{slow} 골든크로스 발생")
        elif sp.state == "dead_cross":
            out.append(f"{fast}·{slow} 데드크로스 발생")
        elif sp.state == "cross_imminent":
            tail = f" (약 {sp.bars_to_cross}봉)" if sp.bars_to_cross else ""
            out.append(f"{fast}·{slow} 교차 임박{tail}")
    return out


def _build_monthly_support(monthly_close: pd.Series) -> MonthlySupport:
    """월봉 7선 지지력 — **종가 기준**(사용자 명시). 꼬리로 판단하지 않는다."""
    ms = MonthlySupport()
    if len(monthly_close) < 7:
        return ms
    ma = monthly_close.rolling(window=7).mean()
    ms.ma7 = _finite(ma.iloc[-1])
    ms.close = _finite(monthly_close.iloc[-1])
    if ms.ma7 is None or ms.close is None or ms.ma7 == 0:
        return ms
    ms.above = ms.close >= ms.ma7
    ms.deviation_pct = (ms.close - ms.ma7) / ms.ma7 * 100

    # 현재 상태를 며칠(개월) 유지했나 — 뒤에서부터 같은 부호가 이어지는 구간.
    pairs = [
        (c, m) for c, m in zip(monthly_close, ma)
        if _finite(c) is not None and _finite(m) is not None
    ]
    held = 0
    for c, m in reversed(pairs):
        if (c >= m) == ms.above:
            held += 1
        else:
            break
    ms.months_held = held
    if held == 1 and len(pairs) >= 2:
        ms.event = "regained" if ms.above else "lost"
    else:
        ms.event = "holding" if ms.above else "below"
    return ms


def _monthly_support_label(ms: MonthlySupport) -> str | None:
    if ms.above is None:
        return None
    if ms.event == "regained":
        return "월봉 7선 지지 회복"
    if ms.event == "lost":
        return "월봉 7선 이탈"
    if ms.above:
        return f"월봉 7선 지지 유지 ({ms.months_held}개월)"
    return f"월봉 7선 아래 ({ms.months_held}개월)"


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------


def build_timeframe_structure(ohlcv: pd.DataFrame, timeframe: str) -> TimeframeStructure:
    """한 시간축 구조 판정. 입력은 **일봉** DataFrame — 주/월 변환은 내부에서 한다."""
    tf = TimeframeStructure(timeframe=timeframe)
    periods = MA_SETS.get(timeframe)
    if periods is None:
        raise ValueError(f"timeframe must be daily/weekly/monthly, got {timeframe!r}")
    if ohlcv is None or len(ohlcv) == 0 or "close" not in ohlcv.columns:
        tf.reasons.append("OHLCV 부재")
        return tf

    try:
        frame = resample_ohlcv(ohlcv, timeframe)
    except Exception as e:  # noqa: BLE001 — 한 시간축 실패가 나머지를 막지 않는다
        tf.reasons.append(f"{_TF_KR[timeframe]} 변환 실패: {e}")
        return tf

    close = frame["close"].dropna()
    tf.bars = len(close)
    tf.close = _finite(close.iloc[-1]) if len(close) else None
    if tf.bars == 0:
        tf.reasons.append(f"{_TF_KR[timeframe]} 봉 0")
        return tf

    window = _DERIV_WINDOW[timeframe]
    tf.deviations = [_build_deviation(close, p, window) for p in periods]
    for d in tf.deviations:
        if d.ma is None:
            tf.reasons.append(f"{_ma_label(timeframe, d.period)} 봉 부족 ({tf.bars}봉)")
    tf.order = _classify_order(tf.deviations)
    tf.spreads = [
        _build_spread(close, f, s, window)
        for f, s in _SPREAD_PAIRS.get(timeframe, ())
        if tf.bars >= s
    ]
    tf.labels = _timeframe_labels(tf)
    return tf


def build_ma_structure(
    ohlcv: pd.DataFrame,
    *,
    name: str = "",
    timeframes: tuple[str, ...] = ("daily", "weekly", "monthly"),
) -> MAStructure:
    """지수·종목 공용 진입점 — 일봉 OHLCV 하나로 3 시간축 구조를 낸다.

    Args:
        ohlcv: DatetimeIndex + close 컬럼을 가진 **일봉** DataFrame
               (`collectors.charts.load_ohlcv_from_db` 출력 형태).
        name: 노출용 이름. 종목코드가 아니라 **종목명**을 넣는다
              ([[feedback_no_stock_code_in_display]]).
    """
    st = MAStructure(name=name)
    if ohlcv is None or len(ohlcv) == 0:
        st.reasons.append("OHLCV 부재")
        return st

    for tf_name in timeframes:
        tf = build_timeframe_structure(ohlcv, tf_name)
        setattr(st, tf_name, tf)

    if st.monthly is not None and st.monthly.bars:
        try:
            monthly_close = resample_ohlcv(ohlcv, "monthly")["close"].dropna()
            st.monthly_support = _build_monthly_support(monthly_close)
        except Exception as e:  # noqa: BLE001
            st.reasons.append(f"월봉 7선 지지력 산출 실패: {e}")

    # 통합 라벨 — 큰 시간축부터 (월봉 지지력이 가장 무거운 맥락).
    if st.monthly_support is not None:
        lbl = _monthly_support_label(st.monthly_support)
        if lbl:
            st.labels.append(lbl)
    for tf in (st.weekly, st.daily):
        if tf is not None:
            st.labels.extend(tf.labels)
    for tf in (st.daily, st.weekly, st.monthly):
        if tf is not None:
            st.reasons.extend(tf.reasons)
    return st
