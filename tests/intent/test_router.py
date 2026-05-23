"""PRODUCTION-UX-001 — Intent Router 분기 단위 테스트.

각 agent_route 별로 router 가 올바른 dispatcher 를 호출하는지 검증.
run_strategist / run_analyst 는 monkeypatch 로 stub — 실 LLM 호출 없음.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest

os.environ.setdefault("TESTING", "1")

from core.intent.classifier import IntentClassification
from core.intent.router import RouteResponse, route_intent


# ---------------------------------------------------------------------------
# Fixtures — run_strategist / run_analyst stub
# ---------------------------------------------------------------------------


class _StubResponse:
    def __init__(self, text: str, metadata: dict[str, Any] | None = None):
        self.text = text
        self.metadata = metadata or {}


def _make_classification(
    *,
    scenario_id: int = 1,
    agent_route: str = "track_a",
    analyst_ids: list[str] | None = None,
    ticker: str | None = "005930",
) -> IntentClassification:
    return IntentClassification(
        scenario_id=scenario_id,
        ticker=ticker,
        ticker_display="삼성전자" if ticker == "005930" else None,
        agent_route=agent_route,
        analyst_ids=analyst_ids or [],
        confidence=0.9,
        manual_fallback_required=False,
        stage="deterministic",
        latency_ms=10,
        raw_input="test input",
        reasoning="stub",
    )


@pytest.fixture
def stub_strategist(monkeypatch: pytest.MonkeyPatch):
    """run_strategist 를 stub — 호출 추적."""
    calls: list[dict[str, Any]] = []

    async def _stub(
        strategist_id: str, messages: list[dict], *, target: str = "global", **kwargs: Any
    ) -> _StubResponse:
        calls.append(
            {"strategist_id": strategist_id, "messages": messages, "target": target, **kwargs}
        )
        return _StubResponse(
            text=f"[STUB strategist {strategist_id}] target={target}",
            metadata={"strategist_id": strategist_id, "target": target, "is_mock": False},
        )

    monkeypatch.setattr("core.intent.router.run_strategist", _stub)
    return calls


@pytest.fixture
def stub_analyst(monkeypatch: pytest.MonkeyPatch):
    """run_analyst 를 stub — 호출 추적."""
    calls: list[dict[str, Any]] = []

    async def _stub(
        analyst_id: str,
        messages: list[dict],
        *,
        target_ticker: str | None = None,
        **kwargs: Any,
    ) -> _StubResponse:
        calls.append(
            {"analyst_id": analyst_id, "messages": messages, "target_ticker": target_ticker, **kwargs}
        )
        return _StubResponse(
            text=f"[STUB analyst {analyst_id}] ticker={target_ticker}",
            metadata={"analyst_id": analyst_id, "target_ticker": target_ticker},
        )

    monkeypatch.setattr("core.intent.router.run_analyst", _stub)
    return calls


@pytest.fixture
def stub_llm_call(monkeypatch: pytest.MonkeyPatch):
    """refuse_or_guide path 용 call_llm stub."""

    async def _stub(*args: Any, **kwargs: Any) -> dict:
        return {
            "content": "안내 응답 stub: 발화를 명확히 해주세요.",
            "tokens_in": 10,
            "tokens_out": 20,
            "model": "stub-model",
            "cost_usd": 0.0,
            "raw": {"mock": True},
        }

    monkeypatch.setattr("core.intent.router.call_llm", _stub)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSingleTrack:
    def test_track_a_calls_run_strategist_once(self, stub_strategist, stub_analyst) -> None:
        c = _make_classification(agent_route="track_a", ticker="005930")
        result = asyncio.run(
            route_intent(c, [{"role": "user", "content": "삼성전자 어때"}])
        )
        assert len(stub_strategist) == 1
        assert stub_strategist[0]["strategist_id"] == "track_a"
        assert stub_strategist[0]["target"] == "005930"
        assert len(stub_analyst) == 0
        assert len(result.agent_responses) == 1
        assert result.agent_responses[0]["kind"] == "strategist"
        assert result.agent_responses[0]["agent_id"] == "track_a"

    def test_track_b_calls_strategist_track_b(self, stub_strategist, stub_analyst) -> None:
        c = _make_classification(agent_route="track_b", ticker="000660")
        asyncio.run(route_intent(c, [{"role": "user", "content": "단타"}]))
        assert len(stub_strategist) == 1
        assert stub_strategist[0]["strategist_id"] == "track_b"

    def test_global_target_when_ticker_missing(self, stub_strategist, stub_analyst) -> None:
        c = _make_classification(agent_route="track_a", ticker=None)
        asyncio.run(route_intent(c, [{"role": "user", "content": "x"}]))
        assert stub_strategist[0]["target"] == "global"


class TestBothRoute:
    def test_both_calls_track_a_and_track_b(self, stub_strategist, stub_analyst) -> None:
        c = _make_classification(agent_route="both", ticker="005930")
        result = asyncio.run(route_intent(c, [{"role": "user", "content": "삼성전자 살까"}]))
        assert len(stub_strategist) == 2
        called_ids = {call["strategist_id"] for call in stub_strategist}
        assert called_ids == {"track_a", "track_b"}
        assert len(result.agent_responses) == 2


class TestAnalystDirect:
    def test_single_analyst(self, stub_strategist, stub_analyst) -> None:
        c = _make_classification(
            scenario_id=3,
            agent_route="analyst_direct",
            analyst_ids=["market_state_analyzer"],
            ticker=None,
        )
        result = asyncio.run(route_intent(c, [{"role": "user", "content": "시장 어때"}]))
        assert len(stub_analyst) == 1
        assert stub_analyst[0]["analyst_id"] == "market_state_analyzer"
        assert len(result.agent_responses) == 1
        assert result.agent_responses[0]["kind"] == "analyst"

    def test_multi_analyst(self, stub_strategist, stub_analyst) -> None:
        c = _make_classification(
            scenario_id=4,
            agent_route="analyst_direct",
            analyst_ids=["stock_picker", "market_state_analyzer"],
            ticker=None,
        )
        result = asyncio.run(route_intent(c, [{"role": "user", "content": "어떤 섹터"}]))
        assert len(stub_analyst) == 2
        called = {call["analyst_id"] for call in stub_analyst}
        assert called == {"stock_picker", "market_state_analyzer"}
        assert len(result.agent_responses) == 2

    def test_analyst_with_ticker_passes_through(self, stub_strategist, stub_analyst) -> None:
        c = _make_classification(
            scenario_id=4,
            agent_route="analyst_direct",
            analyst_ids=["stock_picker"],
            ticker="005930",
        )
        asyncio.run(route_intent(c, [{"role": "user", "content": "x"}]))
        assert stub_analyst[0]["target_ticker"] == "005930"

    def test_analyst_direct_empty_ids_falls_back_to_guide(
        self, stub_strategist, stub_analyst, stub_llm_call
    ) -> None:
        c = _make_classification(
            scenario_id=3, agent_route="analyst_direct", analyst_ids=[], ticker=None
        )
        result = asyncio.run(route_intent(c, [{"role": "user", "content": "x"}]))
        assert len(stub_analyst) == 0
        assert len(stub_strategist) == 0
        assert result.agent_responses[0]["kind"] == "refuse_or_guide"


class TestRefuseOrGuide:
    def test_refuse_route_calls_llm_directly(
        self, stub_strategist, stub_analyst, stub_llm_call
    ) -> None:
        c = _make_classification(
            scenario_id=0, agent_route="refuse_or_guide", analyst_ids=[], ticker=None
        )
        result = asyncio.run(route_intent(c, [{"role": "user", "content": "안녕"}]))
        assert len(stub_strategist) == 0
        assert len(stub_analyst) == 0
        assert len(result.agent_responses) == 1
        assert result.agent_responses[0]["kind"] == "refuse_or_guide"
        assert "stub" in result.agent_responses[0]["text"]


class TestPendingMs5:
    def test_pending_ms5_returns_static_message(
        self, stub_strategist, stub_analyst
    ) -> None:
        c = _make_classification(
            scenario_id=11, agent_route="pending_ms5", analyst_ids=[], ticker=None
        )
        result = asyncio.run(route_intent(c, [{"role": "user", "content": "자가 진화"}]))
        # 어느 LLM/분석가도 호출되지 X
        assert len(stub_strategist) == 0
        assert len(stub_analyst) == 0
        assert result.agent_responses[0]["kind"] == "pending_ms5"
        assert "MS5" in result.agent_responses[0]["text"]


class TestErrorHandling:
    def test_strategist_exception_is_captured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _raises(*args, **kwargs):
            raise RuntimeError("strategist boom")

        monkeypatch.setattr("core.intent.router.run_strategist", _raises)
        c = _make_classification(agent_route="track_a", ticker="005930")
        result = asyncio.run(route_intent(c, [{"role": "user", "content": "x"}]))
        # error 가 raise 되지 않고 metadata 에 들어감
        assert len(result.agent_responses) == 1
        assert "strategist boom" in (result.agent_responses[0].get("error") or "")

    def test_analyst_not_found_is_captured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.inference.run_analyst import AnalystNotFoundError

        async def _raises(*args, **kwargs):
            raise AnalystNotFoundError("missing analyst")

        monkeypatch.setattr("core.intent.router.run_analyst", _raises)
        c = _make_classification(
            scenario_id=3,
            agent_route="analyst_direct",
            analyst_ids=["nonexistent"],
            ticker=None,
        )
        result = asyncio.run(route_intent(c, [{"role": "user", "content": "x"}]))
        assert "missing analyst" in (result.agent_responses[0].get("error") or "")
