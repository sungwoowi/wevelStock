"""야간선물 등락 계산 (ADVISOR-CORE-001 F1).

2026-08-12 사고: 판세가 "야간선물 +4.31% → 내일 갭상승 우위"라고 했는데, 그 값은
KIS 선물 `change_pct`(**전일 종가 대비**)라 그날 주간 상승분(+4.26%)이 통째로 들어가
있었다. 야간에 실제 움직인 건 +0.34% 수준. 오늘 이미 일어난 상승을 내일 갭으로 착각.

게다가 세션 무구분이라 주간(14:30)에 호출해도 "야간선물"이라 불렀다.

올바른 정의: **야간 등락 = (야간 선물가 − 그날 주간 선물 종가) / 주간 선물 종가**
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from collectors import night_futures as nf

_KST = ZoneInfo("Asia/Seoul")


def _at(h: int, m: int = 0, day: int = 12):
    return datetime(2026, 8, day, h, m, tzinfo=_KST)


# --- 1. 세션 판정 -------------------------------------------------------------


@pytest.mark.parametrize("hour,expected", [
    (9, "day"), (14, "day"), (15, "day"),
    (18, "night"), (21, "night"), (23, "night"),
    (2, "night"), (4, "night"),
    (6, "closed"), (8, "closed"),
])
def test_session_of(hour, expected) -> None:
    assert nf.session_of(_at(hour)) == expected


# --- 2. 주간 세션에서는 야간선물을 쓰지 않는다 --------------------------------


def test_day_session_returns_none() -> None:
    """주간에 부르면 '야간선물'이 아니다 — 값 자체를 내지 않는다."""
    out = nf.compute_night_change(
        futures_price=1035.3, day_close=None, now=_at(14, 30),
    )
    assert out.pct is None
    assert out.basis == "day_session"


# --- 3. 주간 종가가 있으면 정확 계산 ------------------------------------------


def test_exact_from_stored_day_close() -> None:
    out = nf.compute_night_change(
        futures_price=1035.3, day_close=1031.0, now=_at(21),
    )
    assert out.pct == pytest.approx((1035.3 - 1031.0) / 1031.0 * 100, abs=0.01)
    assert out.basis == "day_close"


def test_exact_calculation_is_small_not_cumulative() -> None:
    """핵심 회귀 — 전일 대비 누적(+4.6%)이 아니라 야간 순수 이동만."""
    out = nf.compute_night_change(
        futures_price=1035.3, day_close=1031.0, now=_at(21),
    )
    assert abs(out.pct) < 1.0, f"{out.pct} — 주간 상승분이 섞였다"


# --- 4. 기준선이 없으면 None (근사 없음) --------------------------------------


def test_no_day_close_yields_none() -> None:
    """근사 경로를 버렸다 — 기준선 없으면 모른다고 한다.

    현물 대비 근사는 두 번 연속 조용히 틀렸다(장 마감 후 지수 피드가 change_pct=0 을
    주는 바람에 선물 전일대비 누적 +4.6% 가 야간 이동으로 둔갑).
    """
    out = nf.compute_night_change(futures_price=1035.3, day_close=None, now=_at(21))
    assert out.pct is None and out.basis == "unavailable"


def test_missing_futures_price_returns_none() -> None:
    out = nf.compute_night_change(futures_price=None, day_close=1031.0, now=_at(21))
    assert out.pct is None


# --- 5. 아침(장 시작 전) 세션도 야간 결과를 쓴다 ------------------------------


def test_premarket_uses_prev_day_close() -> None:
    """07:05 아침 판세 — 밤새 움직임을 그대로 읽는다."""
    out = nf.compute_night_change(
        futures_price=1040.0, day_close=1031.0, now=_at(7, 5, day=13),
        allow_closed_session=True,
    )
    assert out.pct == pytest.approx((1040.0 - 1031.0) / 1031.0 * 100, abs=0.01)
    assert out.basis == "day_close"


def test_closed_session_without_allow_is_none() -> None:
    out = nf.compute_night_change(
        futures_price=1040.0, day_close=1031.0, now=_at(7, 5),
    )
    assert out.pct is None and out.basis == "closed"


# --- 6. 갭 판정은 야간 순수 이동 기준 -----------------------------------------


@pytest.mark.parametrize("pct,expected", [
    (0.9, "gap_up"), (0.2, "flat"), (-0.1, "flat"), (-0.8, "gap_down"), (None, "unknown"),
])
def test_gap_call_from_night_move(pct, expected) -> None:
    assert nf.gap_call_from(pct) == expected


def test_old_bug_would_have_called_gap_up_wrongly() -> None:
    """회귀 방지 — 옛 값(+4.6% 누적)이면 갭상승, 실제 야간(+0.42%)이면 보합."""
    assert nf.gap_call_from(4.6) == "gap_up"
    assert nf.gap_call_from(0.42) == "flat"

