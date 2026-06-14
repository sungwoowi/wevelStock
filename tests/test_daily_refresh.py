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

from server.schedulers.jobs import auto_signal as asj
from server.schedulers.jobs import daily_refresh as dr
from server.schedulers.jobs import news_ingest as ni
from server.schedulers.jobs import snapshot_macro as sm
from server.schedulers.jobs.daily_refresh import run_daily_refresh


@pytest.fixture
def patched_subjobs(monkeypatch: pytest.MonkeyPatch) -> dict:
    calls: dict = {"macro": 0, "news": 0, "signal": 0, "desk": 0}

    async def fake_macro():
        calls["macro"] += 1
        return {"supply": {"refreshed": ["KOSPI"]}, "market_view": {"regime": "moderate_bull"}}

    async def fake_news():
        calls["news"] += 1
        return {"date": "2026-06-08", "collected": 5, "classified": 4, "failures": []}

    async def fake_signal(cadence="postclose"):
        calls["signal"] += 1
        return {"cadence": cadence, "screened": 3, "persisted": 4, "buys": 1}

    monkeypatch.setattr(sm, "run_snapshot_macro_refresh", fake_macro)
    monkeypatch.setattr(ni, "run_news_ingest", fake_news)
    # 자동 권고 생성(2.5단계) — 실 KIS·Gemini 호출 차단 (lazy import 라 원 모듈 패치).
    monkeypatch.setattr(asj, "run_auto_signal_job", fake_signal)
    # 데스크(3단계) — 실 DB 체결 차단 (lazy import 라 원 모듈 패치).
    import core.account.desk as desk_mod
    import core.account.compounding as comp_mod

    def fake_desk(*a, **k):
        calls["desk"] += 1
        return {"date": "2026-06-08", "buy_fills": 0, "sell_fills": 0}

    monkeypatch.setattr(desk_mod, "run_desk_today", fake_desk)
    monkeypatch.setattr(comp_mod, "snapshot_equity", lambda *a, **k: [])
    return calls


def test_both_subjobs_invoked(patched_subjobs: dict) -> None:
    """macro + news + 자동 권고 + 데스크 모두 호출, 집계 dict 구조."""
    result = asyncio.run(run_daily_refresh())

    assert patched_subjobs["macro"] == 1
    assert patched_subjobs["news"] == 1
    assert patched_subjobs["signal"] == 1
    assert set(result) >= {"snapshot_macro", "news", "auto_signal", "desk", "elapsed_s"}
    assert result["snapshot_macro"]["market_view"]["regime"] == "moderate_bull"
    assert result["news"]["collected"] == 5
    assert result["auto_signal"]["persisted"] == 4


def test_signal_runs_before_desk(
    monkeypatch: pytest.MonkeyPatch, patched_subjobs: dict
) -> None:
    """자동 권고 생성(2.5단계)이 데스크(3단계) 앞에 — 데스크가 그날 권고를 체결하도록."""
    order: list[str] = []

    async def fake_signal(cadence="postclose"):
        order.append("signal")
        return {"cadence": cadence, "persisted": 2}

    def fake_desk(*a, **k):
        order.append("desk")
        return {"buy_fills": 0}

    import core.account.desk as desk_mod

    monkeypatch.setattr(asj, "run_auto_signal_job", fake_signal)
    monkeypatch.setattr(desk_mod, "run_desk_today", fake_desk)
    asyncio.run(run_daily_refresh())
    assert order == ["signal", "desk"]


def test_signal_failure_does_not_block_desk(
    monkeypatch: pytest.MonkeyPatch, patched_subjobs: dict
) -> None:
    """자동 권고 생성 예외 → 데스크는 여전히 실행(기존 권고로), signal 만 error 격리."""

    async def boom(cadence="postclose"):
        raise RuntimeError("gemini 503")

    monkeypatch.setattr(asj, "run_auto_signal_job", boom)
    result = asyncio.run(run_daily_refresh())

    assert "error" in result["auto_signal"]
    assert "gemini 503" in result["auto_signal"]["error"]
    assert patched_subjobs["desk"] == 1  # 데스크는 정상


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
