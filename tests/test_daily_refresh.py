"""일일 적재 통합 entrypoint 테스트 (dev cron 미작동 부채 해소).

run_daily_refresh 오케스트레이션 검증:
  - run_snapshot_macro_refresh + run_news_ingest 둘 다 호출.
  - 반환 dict 에 snapshot_macro / news / elapsed_s 키.
  - 한 서브잡 실패가 다른 서브잡을 막지 않고 격리된다 (graceful).

두 서브잡을 mock (함수 내부 import 라 원 잡 모듈을 패치).
"""
from __future__ import annotations

import asyncio

import pytest

from server.schedulers.jobs import daily_refresh as dr
from server.schedulers.jobs import news_ingest as ni
from server.schedulers.jobs import snapshot_macro as sm
from server.schedulers.jobs.daily_refresh import run_daily_refresh


@pytest.fixture
def patched_subjobs(monkeypatch: pytest.MonkeyPatch) -> dict:
    calls: dict = {"macro": 0, "news": 0}

    async def fake_macro():
        calls["macro"] += 1
        return {"supply": {"refreshed": ["KOSPI"]}, "market_view": {"regime": "moderate_bull"}}

    async def fake_news():
        calls["news"] += 1
        return {"date": "2026-06-08", "collected": 5, "classified": 4, "failures": []}

    monkeypatch.setattr(sm, "run_snapshot_macro_refresh", fake_macro)
    monkeypatch.setattr(ni, "run_news_ingest", fake_news)
    return calls


def test_both_subjobs_invoked(patched_subjobs: dict) -> None:
    """macro + news 두 서브잡 모두 호출, 집계 dict 구조."""
    result = asyncio.run(run_daily_refresh())

    assert patched_subjobs["macro"] == 1
    assert patched_subjobs["news"] == 1
    assert set(result) >= {"snapshot_macro", "news", "elapsed_s"}
    assert result["snapshot_macro"]["market_view"]["regime"] == "moderate_bull"
    assert result["news"]["collected"] == 5


def test_macro_failure_does_not_block_news(
    monkeypatch: pytest.MonkeyPatch, patched_subjobs: dict
) -> None:
    """macro 서브잡 예외 → news 는 여전히 실행, macro 만 error 격리."""

    async def boom():
        raise RuntimeError("kis timeout")

    monkeypatch.setattr(sm, "run_snapshot_macro_refresh", boom)

    result = asyncio.run(run_daily_refresh())

    assert "error" in result["snapshot_macro"]
    assert "kis timeout" in result["snapshot_macro"]["error"]
    # news 는 정상 실행
    assert patched_subjobs["news"] == 1
    assert result["news"]["collected"] == 5


def test_news_failure_isolated(
    monkeypatch: pytest.MonkeyPatch, patched_subjobs: dict
) -> None:
    """news 서브잡 예외 → macro 는 정상, news 만 error 격리."""

    async def boom():
        raise RuntimeError("rss down")

    monkeypatch.setattr(ni, "run_news_ingest", boom)

    result = asyncio.run(run_daily_refresh())

    assert result["snapshot_macro"]["supply"]["refreshed"] == ["KOSPI"]
    assert "error" in result["news"]
    assert "rss down" in result["news"]["error"]
