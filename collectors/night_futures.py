"""KOSPI200 야간선물 등락 — 세션 인식 + 올바른 기준 (ADVISOR-CORE-001 F1).

## 왜 별도 모듈인가

2026-08-12 사고: 판세가 *"야간선물 +4.31% → 내일 갭상승 우위"* 라고 발행했는데, 그 값은
KIS 선물 `change_pct` 즉 **전일 종가 대비 누적**이었다. 그날 주간에 이미 +4.26% 오른 것이
통째로 들어가 있었고, 야간에 실제 움직인 건 +0.34% 수준이었다.
**오늘 이미 일어난 상승을 내일 갭 예고로 착각한 것.**

게다가 세션 구분이 없어 주간 14:30 에 호출해도 "야간선물"이라 불렀다.

## 올바른 정의

    야간 등락 = (야간 선물가 − **그날 주간 선물 종가**) / 주간 선물 종가

KIS 선물 일봉은 하루 1행이라 주간·야간이 합쳐져 주간 종가를 못 뽑는다(실측 확인).
그래서 **주간 마감 시점에 우리가 저장**해야 정확해진다.

기준은 **저장된 주간 선물 종가 하나뿐**이다. 없으면 None.

현물(KOSPI200) 등락 대비 근사도 시도했으나 두 번 연속 조용히 틀린 값을 냈다 —
장 마감 후 지수 피드가 `value` 는 주면서 `change_pct=0` 을 주는 바람에
선물의 전일대비 누적(+4.6%)이 그대로 "야간 이동"으로 둔갑했다. 오늘 하루 반복된
바로 그 실패 패턴(빈 값을 0 으로 착각)이라 **근사 자체를 버렸다.**
기준선이 없으면 모른다고 한다 — 판세는 그 축만 빼고 나간다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

_KST = ZoneInfo("Asia/Seoul")

# KOSPI200 야간선물 정규 세션 (KST). 주간은 09:00~15:45.
NIGHT_START_HOUR = 18
NIGHT_END_HOUR = 5           # 05:00 종료 (05:00 이후는 closed)
DAY_START_HOUR = 9
DAY_END_HOUR = 16            # 15:45 마감 → 16시 이전을 주간으로 본다

# 갭 판정 임계 (%). 야간 **순수 이동** 기준이라 기존 0.5 를 그대로 쓴다.
GAP_THRESHOLD = 0.5


@dataclass
class NightChange:
    """야간선물 등락 산출 결과."""

    pct: float | None = None
    basis: str = "unavailable"   # day_close | day_session | closed | unavailable


def session_of(now: datetime | None = None) -> str:
    """지금이 어느 세션인가 — day | night | closed."""
    now = now or datetime.now(_KST)
    h = now.astimezone(_KST).hour
    if h >= NIGHT_START_HOUR or h < NIGHT_END_HOUR:
        return "night"
    if DAY_START_HOUR <= h < DAY_END_HOUR:
        return "day"
    return "closed"


def compute_night_change(
    *,
    futures_price: float | None,
    day_close: float | None,
    now: datetime | None = None,
    allow_closed_session: bool = False,
) -> NightChange:
    """야간선물 순수 이동률. 기준이 없으면 None (근거 없는 값을 만들지 않는다).

    Args:
        futures_price: 현재 선물가
        day_close: 그날 주간 선물 종가 — **유일한 기준선**. 없으면 None 을 낸다.
        allow_closed_session: 07:05 아침 판세처럼 세션 밖에서도 직전 야간 결과를 쓸 때
    """
    sess = session_of(now)
    if sess == "day":
        # 주간에는 "야간선물"이라는 값이 존재하지 않는다.
        return NightChange(pct=None, basis="day_session")
    if sess == "closed" and not allow_closed_session:
        return NightChange(pct=None, basis="closed")
    if futures_price is None:
        return NightChange(pct=None, basis="unavailable")

    if day_close:
        return NightChange(
            pct=round((futures_price - day_close) / day_close * 100.0, 2),
            basis="day_close",
        )
    return NightChange(pct=None, basis="unavailable")


def gap_call_from(pct: float | None) -> str:
    """야간 순수 이동 → 내일 시초 판정."""
    if pct is None:
        return "unknown"
    if pct <= -GAP_THRESHOLD:
        return "gap_down"
    if pct >= GAP_THRESHOLD:
        return "gap_up"
    return "flat"
