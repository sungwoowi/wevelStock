"""snapshot_macro 일일 refresh job 테스트 (INFRA-SNAPSHOT-EXTEND-001 + MARKET-VIEW-SYNTHESIS-001).

3단계 cron (supply → market_macro → market_view) 의 오케스트레이션 검증:
  - 3단계 모두 호출 + build_market_view 가 force_refresh=True 로 불린다.
  - 반환 dict 에 supply / market_macro / market_view 3키 존재.
  - 한 단계 실패가 다른 단계를 막지 않고 격리된다 (graceful).

실 API/LLM 금지 — 세 collector 를 전부 mock (함수 내부 import 라 원 소스 모듈을 패치).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from collectors import market_macro as mm
from collectors import market_view as mv
from collectors import supply_demand_history as sdh
from server.schedulers.jobs.snapshot_macro import run_snapshot_macro_refresh


# ---------------------------------------------------------------------------
# Fixtures — 세 collector mock
# ---------------------------------------------------------------------------


@dataclass
class _FakeRotation:
    direction: str = "바이오→금융"
    strength: str = "mild"


@dataclass
class _FakeView:
    market: str = "KOSPI"
    regime: str = "moderate_bull"
    rotation: _FakeRotation = None  # type: ignore[assignment]
    one_liner: str = "오늘 시장: 완만한 강세 · 주도 금융 · 진입 중립"

    def __post_init__(self) -> None:
        if self.rotation is None:
            self.rotation = _FakeRotation()


@pytest.fixture
def patched_collectors(monkeypatch: pytest.MonkeyPatch) -> dict:
    """세 collector 를 호출 추적 mock 으로 교체. 호출 인자 기록."""
    calls: dict = {"supply": 0, "macro": 0, "view": []}

    async def fake_supply():
        calls["supply"] += 1
        return {"refreshed": ["KOSPI", "KOSDAQ"], "failures": []}

    async def fake_macro():
        calls["macro"] += 1
        return {"refreshed": ["KOSPI", "KOSDAQ"], "failures": []}

    async def fake_view(market="KOSPI", *, force_refresh=False, cross_check=True):
        calls["view"].append({"market": market, "force_refresh": force_refresh})
        return _FakeView(market=market)

    monkeypatch.setattr(sdh, "refresh_supply_demand_today", fake_supply)
    monkeypatch.setattr(mm, "refresh_market_macro_all", fake_macro)
    monkeypatch.setattr(mv, "build_market_view", fake_view)
    return calls


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_three_stages_invoked(patched_collectors: dict) -> None:
    """supply → macro → market_view 3단계 모두 호출. view 는 force_refresh=True."""
    result = asyncio.run(run_snapshot_macro_refresh())

    assert patched_collectors["supply"] == 1
    assert patched_collectors["macro"] == 1
    assert patched_collectors["view"] == [{"market": "KOSPI", "force_refresh": True}]

    assert set(result) >= {"supply", "market_macro", "market_view", "elapsed_s"}
    assert result["market_view"]["regime"] == "moderate_bull"
    assert result["market_view"]["rotation"] == "바이오→금융"
    assert result["market_view"]["one_liner"]


def test_market_view_failure_isolated(
    monkeypatch: pytest.MonkeyPatch, patched_collectors: dict
) -> None:
    """build_market_view 예외 → job 크래시 X, market_view 만 error 격리. supply/macro 정상."""

    async def boom(market="KOSPI", *, force_refresh=False, cross_check=True):
        raise RuntimeError("gemini down")

    monkeypatch.setattr(mv, "build_market_view", boom)

    result = asyncio.run(run_snapshot_macro_refresh())

    # 앞 두 단계는 정상 완료
    assert result["supply"]["refreshed"] == ["KOSPI", "KOSDAQ"]
    assert result["market_macro"]["refreshed"] == ["KOSPI", "KOSDAQ"]
    # market_view 는 error 로 격리
    assert "error" in result["market_view"]
    assert "gemini down" in result["market_view"]["error"]


def test_macro_failure_does_not_block_market_view(
    monkeypatch: pytest.MonkeyPatch, patched_collectors: dict
) -> None:
    """macro 단계 실패해도 market_view 단계는 여전히 실행된다 (단계 독립)."""

    async def macro_boom():
        raise RuntimeError("kis timeout")

    monkeypatch.setattr(mm, "refresh_market_macro_all", macro_boom)

    result = asyncio.run(run_snapshot_macro_refresh())

    assert result["market_macro"]["failures"]  # macro 실패 기록
    # market_view 는 그래도 호출되어 성공
    assert patched_collectors["view"] == [{"market": "KOSPI", "force_refresh": True}]
    assert result["market_view"]["regime"] == "moderate_bull"
