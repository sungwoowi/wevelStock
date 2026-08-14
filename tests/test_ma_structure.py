"""다중 시간축 이평 구조 해석 (ADVISOR-CORE-001 M1-F3).

사용자 정의 체계 (2026-08-13): 일봉 7·13·20·60·120 / 주봉 5·10·20 / 월봉 종가기준 7선.
검증의 무게중심 = **미적분 포착**(1차 수렴/발산 · 2차 가속/감속)과 **봉 부족 시 None**.
합성 가격 시계열로 의도한 국면을 만들어 판정이 그 국면을 집어내는지 본다.
"""
from __future__ import annotations

import os

os.environ.setdefault("TESTING", "1")

import numpy as np
import pandas as pd
import pytest

from core.signal import ma_structure as ms


def _frame(closes: list[float], start: str = "2020-01-01") -> pd.DataFrame:
    """영업일 인덱스 OHLCV. close 만 의미 있고 나머지는 형태 맞추기."""
    idx = pd.bdate_range(start=start, periods=len(closes))
    s = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame(
        {"open": s, "high": s * 1.01, "low": s * 0.99, "close": s, "volume": 1_000.0},
        index=idx,
    )


def _rising(n: int = 400, start: float = 100.0, rate: float = 0.004) -> list[float]:
    return [start * (1 + rate) ** i for i in range(n)]


def _falling(n: int = 400, start: float = 300.0, rate: float = 0.004) -> list[float]:
    return [start * (1 - rate) ** i for i in range(n)]


# ---------------------------------------------------------------------------
# 이평 세트 = 사용자 정의와 일치 (본질 문서 동기화 대상이라 상수로 못 박는다)
# ---------------------------------------------------------------------------


def test_ma_sets_match_user_definition():
    assert ms.DAILY_MAS == (7, 13, 20, 60, 120)
    assert ms.WEEKLY_MAS == (5, 10, 20)
    assert ms.MONTHLY_MAS == (7,)


def test_daily_structure_emits_every_defined_ma():
    st = ms.build_timeframe_structure(_frame(_rising()), "daily")
    assert [d.period for d in st.deviations] == list(ms.DAILY_MAS)
    assert all(d.ma is not None for d in st.deviations)


def test_weekly_and_monthly_resample_from_daily_input():
    """일봉 하나만 넣으면 주/월봉은 내부 변환 — 호출부가 resample 을 몰라도 된다."""
    frame = _frame(_rising(600))
    weekly = ms.build_timeframe_structure(frame, "weekly")
    monthly = ms.build_timeframe_structure(frame, "monthly")
    assert 0 < weekly.bars < len(frame)
    assert 0 < monthly.bars < weekly.bars
    assert [d.period for d in weekly.deviations] == list(ms.WEEKLY_MAS)


def test_invalid_timeframe_raises():
    with pytest.raises(ValueError):
        ms.build_timeframe_structure(_frame(_rising(50)), "hourly")


# ---------------------------------------------------------------------------
# 정배열 / 역배열
# ---------------------------------------------------------------------------


def test_sustained_rise_is_bullish_stack():
    st = ms.build_timeframe_structure(_frame(_rising()), "daily")
    assert st.order == "bullish_stack"
    assert "일봉 정배열" in st.labels


def test_sustained_fall_is_bearish_stack():
    st = ms.build_timeframe_structure(_frame(_falling()), "daily")
    assert st.order == "bearish_stack"


def test_order_none_when_only_one_ma_available():
    """7선만 겨우 나오는 길이 → 정/역배열을 말할 수 없다 (None, 추정 금지)."""
    st = ms.build_timeframe_structure(_frame(_rising(10)), "daily")
    assert st.order is None


# ---------------------------------------------------------------------------
# 1차 미분 — 수렴 / 발산
# ---------------------------------------------------------------------------


def test_above_ma_and_pulling_away_is_diverging():
    closes = _rising(300) + [300.0 * (1 + 0.03) ** i for i in range(1, 9)]  # 마지막 급등
    st = ms.build_timeframe_structure(_frame(closes), "daily")
    d = st.dev(20)
    assert d.phase == "above"
    assert d.motion == "diverging"
    assert d.velocity > 0


def test_below_ma_and_recovering_is_converging():
    """이평 **아래**에서 이격이 줄어드는 것 = 수렴(돌파 시도). 부호 직관과 어긋나는 지점."""
    base = _rising(300)
    crashed = base + [base[-1] * 0.80] * 3           # 급락으로 이평 아래
    recovering = crashed + [base[-1] * (0.82 + 0.02 * i) for i in range(6)]
    st = ms.build_timeframe_structure(_frame(recovering), "daily")
    d = st.dev(20)
    assert d.phase == "below"
    assert d.motion == "converging"


def test_flat_price_yields_flat_motion():
    st = ms.build_timeframe_structure(_frame([100.0] * 200), "daily")
    assert st.dev(20).motion == "flat"


# ---------------------------------------------------------------------------
# 2차 미분 — 가속 / 감속 (사용자 요구의 핵심)
# ---------------------------------------------------------------------------


def test_accelerating_when_move_speeds_up():
    closes = _rising(280)
    last = closes[-1]
    closes += [last * (1 + 0.01 * (i ** 1.6)) for i in range(1, 12)]   # 점점 가팔라짐
    st = ms.build_timeframe_structure(_frame(closes), "daily")
    d = st.dev(20)
    assert d.acceleration is not None
    assert d.accel == "accelerating"


def test_decelerating_when_move_loses_steam():
    """일정 속도 상승은 이격도가 포화된다 — 아직 벌어지지만 힘은 죽는 국면."""
    closes = [100.0] * 200
    for _ in range(14):
        closes.append(closes[-1] * 1.01)
    st = ms.build_timeframe_structure(_frame(closes), "daily")
    d = st.dev(20)
    assert d.motion == "diverging"
    assert d.accel == "decelerating"


def test_stalling_rally_reads_as_converging_while_above():
    """상승세가 꺾이면 이격도 층에서는 **이평으로 수렴**으로 나타난다 (= 눌림).

    이 방향 정의가 흔들리면 '20일선 위 8%' 같은 정지 사진으로 되돌아간다.
    """
    closes = _rising(280)
    last = closes[-1]
    closes += [last * (1 + 0.06 * np.log1p(i)) for i in range(1, 14)]
    d = ms.build_timeframe_structure(_frame(closes), "daily").dev(20)
    assert d.phase == "above"
    assert d.motion == "converging"


def test_acceleration_none_when_bars_insufficient_for_two_windows():
    """두 관측창을 못 담으면 2차 미분은 **None** — 억지 추정하지 않는다."""
    st = ms.build_timeframe_structure(_frame(_rising(23)), "daily")
    d = st.dev(20)
    assert d.deviation_pct is not None
    assert d.acceleration is None
    assert d.accel is None


def test_classify_accel_treats_downside_speedup_as_accelerating():
    """하락 이격이 더 빨리 벌어지는 것도 '가속' — 부호가 아니라 진행 방향 기준."""
    assert ms._classify_accel(-0.5, -0.4) == "accelerating"
    assert ms._classify_accel(-0.5, 0.4) == "decelerating"
    assert ms._classify_accel(0.5, 0.0) == "steady"


# ---------------------------------------------------------------------------
# 스프레드 · 크로스
# ---------------------------------------------------------------------------


def test_spread_pairs_cover_short_mid_long():
    st = ms.build_timeframe_structure(_frame(_rising()), "daily")
    assert [(s.fast, s.slow) for s in st.spreads] == [(7, 20), (20, 60), (60, 120)]


def test_golden_cross_detected_after_reversal():
    base = _falling(200)
    closes = base + [base[-1] * (1 + 0.02) ** i for i in range(1, 9)]
    st = ms.build_timeframe_structure(_frame(closes), "daily")
    sp = next(s for s in st.spreads if (s.fast, s.slow) == (7, 20))
    assert sp.state == "golden_cross"
    assert "7일선·20일선 골든크로스 발생" in st.labels


def test_dead_cross_labeled_when_fast_drops_below_slow():
    base = _rising(200)
    closes = base + [base[-1] * (1 - 0.02) ** i for i in range(1, 9)]
    st = ms.build_timeframe_structure(_frame(closes), "daily")
    sp = next(s for s in st.spreads if (s.fast, s.slow) == (7, 20))
    assert sp.state == "dead_cross"
    assert "7일선·20일선 데드크로스 발생" in st.labels


def test_old_cross_is_not_reported_as_fresh():
    """20봉 전에 지난 크로스는 사건이 아니다 — lookback 밖이면 상태로만 남는다."""
    base = _rising(200)
    closes = base + [base[-1] * (1 - 0.02) ** i for i in range(1, 20)]
    st = ms.build_timeframe_structure(_frame(closes), "daily")
    sp = next(s for s in st.spreads if (s.fast, s.slow) == (7, 20))
    assert sp.state != "dead_cross"
    assert sp.spread_pct < 0


def test_bars_to_cross_dropped_when_extrapolation_is_far():
    """선형 외삽이 20봉을 넘으면 None — 근사는 한 번 틀리면 제거한다는 원칙."""
    sp = ms._build_spread(pd.Series(_rising(400)), 60, 120, 5)
    assert sp.bars_to_cross is None or sp.bars_to_cross <= ms._MAX_BARS_TO_CROSS


# ---------------------------------------------------------------------------
# 월봉 7선 지지력 (사용자 명시 축, 종가 기준)
# ---------------------------------------------------------------------------


def test_monthly_support_holding_in_uptrend():
    st = ms.build_ma_structure(_frame(_rising(900)), name="테스트지수")
    sup = st.monthly_support
    assert sup.above is True
    assert sup.event == "holding"
    assert sup.months_held >= 2
    assert any("월봉 7선 지지 유지" in l for l in st.labels)


def test_monthly_support_lost_on_fresh_breakdown():
    closes = _rising(900)
    closes += [closes[-1] * 0.55] * 24     # 한 달 내 급락 → 7월선 아래로 신규 이탈
    st = ms.build_ma_structure(_frame(closes), name="테스트지수")
    sup = st.monthly_support
    assert sup.above is False
    assert sup.event in ("lost", "below")
    assert any("월봉 7선" in l for l in st.labels)


def test_monthly_support_none_when_under_seven_months():
    st = ms.build_ma_structure(_frame(_rising(60)), name="짧은종목")
    assert st.monthly_support is None or st.monthly_support.ma7 is None


# ---------------------------------------------------------------------------
# 라벨 — 코드가 먼저 감지해 이름 붙이기
# ---------------------------------------------------------------------------


def test_breakout_attempt_label_when_near_ma_from_below():
    """이평 바로 아래에서 좁혀 오는 중 = 돌파 시도. 정지 사진으로는 안 보이는 것."""
    base = _rising(300)
    closes = base + [base[-1] * x for x in ([0.90] * 3 + [0.905, 0.915, 0.925, 0.935])]
    st = ms.build_timeframe_structure(_frame(closes), "daily")
    d = st.dev(20)
    assert d.phase == "below" and d.motion == "converging"
    assert any("20일선 상향 돌파 시도" in l for l in st.labels)


def test_labels_use_korean_ma_names_per_timeframe():
    assert ms._ma_label("daily", 20) == "20일선"
    assert ms._ma_label("weekly", 5) == "5주선"
    assert ms._ma_label("monthly", 7) == "7월선"


# ---------------------------------------------------------------------------
# 지수·종목 공용 + 결측 처리
# ---------------------------------------------------------------------------


def test_same_lens_applies_to_index_and_stock():
    """사용자 명시: 주도 종목뿐 아니라 지수 차트에도 해당하는 구조적 해석법."""
    frame = _frame(_rising(900))
    index_st = ms.build_ma_structure(frame, name="코스피")
    stock_st = ms.build_ma_structure(frame, name="삼성전자")
    assert index_st.daily.order == stock_st.daily.order
    assert index_st.labels == stock_st.labels


def test_empty_ohlcv_yields_reason_not_crash():
    st = ms.build_ma_structure(pd.DataFrame(), name="빈종목")
    assert st.daily is None and st.monthly_support is None
    assert "OHLCV 부재" in st.reasons


def test_short_history_reports_missing_ma_reasons():
    st = ms.build_ma_structure(_frame(_rising(30)), name="신규상장")
    assert st.daily.dev(120).ma is None
    assert any("120일선 봉 부족" in r for r in st.daily.reasons)


def test_nan_close_does_not_become_zero():
    """빈 값과 0 을 구분한다 — 낡은/없는 값을 0 으로 읽던 사고 계열 차단."""
    closes = _rising(200)
    frame = _frame(closes)
    frame.loc[frame.index[-1], "close"] = float("nan")
    st = ms.build_timeframe_structure(frame, "daily")
    assert st.close != 0
    assert st.close is None or st.close > 0


def test_structure_is_json_serializable_for_persistence():
    """facts_json 영속 경로 — asdict 가 통째로 나가야 point-in-time 재현이 된다."""
    import json

    st = ms.build_ma_structure(_frame(_rising(900)), name="코스피")
    payload = json.dumps(st.to_dict(), ensure_ascii=False, default=str)
    assert "코스피" in payload
