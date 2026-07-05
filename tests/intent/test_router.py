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
from core.intent.router import (
    RouteResponse,
    _build_subtask_prompt,
    _resolve_analyst_ids_for_scenario,
    reload_subtasks_and_routing,
    route_intent,
)


@pytest.fixture(autouse=True)
def _reload_subtasks_each():
    """yaml hot-reload 안전 — 매 테스트마다 캐시 클리어."""
    reload_subtasks_and_routing()
    yield
    reload_subtasks_and_routing()


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
    """옵션 A 적용 — track_a 호출 시 prefetch 분석가 N명 + 전략가 1."""

    def test_track_a_calls_strategist_with_prefetch(self, stub_strategist, stub_analyst) -> None:
        c = _make_classification(agent_route="track_a", ticker="005930")
        result = asyncio.run(
            route_intent(c, [{"role": "user", "content": "삼성전자 어때"}])
        )
        # 전략가 1번 호출
        assert len(stub_strategist) == 1
        assert stub_strategist[0]["strategist_id"] == "track_a"
        assert stub_strategist[0]["target"] == "005930"
        # 분석가 prefetch — track_a 의 reads_analysts (manifest 정의) 만큼 동시 호출
        assert len(stub_analyst) >= 1
        # 전략가에 prefetched_analyst_outputs 가 전달됨
        prefetched = stub_strategist[0].get("prefetched_analyst_outputs")
        assert prefetched is not None
        assert len(prefetched) == len(stub_analyst)
        # agent_responses 에 analyst_prefetch + strategist 양쪽 포함
        kinds = [r["kind"] for r in result.agent_responses]
        assert "strategist" in kinds
        assert kinds.count("analyst_prefetch") == len(stub_analyst)

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
        # 두 전략가 모두 같은 prefetched 자료 받음 (dedupe + 단일 prefetch)
        pa = stub_strategist[0].get("prefetched_analyst_outputs")
        pb = stub_strategist[1].get("prefetched_analyst_outputs")
        assert pa is not None and pb is not None
        assert pa == pb  # 동일 객체 reference (dedupe + single prefetch)
        # agent_responses = analyst_prefetch N + strategist 2
        kinds = [r["kind"] for r in result.agent_responses]
        assert kinds.count("strategist") == 2
        assert kinds.count("analyst_prefetch") >= 1


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


class TestMockFallbackForwarded:
    """router 의 wrap 함수들이 mock_fallback_allowed=False 를 항상 forward 하는지.

    production-chat 사용자 경로 = silent mock 노출 차단. wrap 함수가 이 flag 를
    forward 안 하면 silent fallback 이 재발한다.
    """

    def test_track_a_forwards_mock_fallback_disabled(
        self, stub_strategist, stub_analyst
    ) -> None:
        c = _make_classification(agent_route="track_a", ticker="005930")
        asyncio.run(route_intent(c, [{"role": "user", "content": "x"}]))
        # 전략가 호출 kwargs 에 mock_fallback_allowed=False
        assert stub_strategist[0].get("mock_fallback_allowed") is False
        # 분석가 prefetch 호출 kwargs 에도 동일
        for call in stub_analyst:
            assert call.get("mock_fallback_allowed") is False

    def test_both_forwards_mock_fallback_disabled(
        self, stub_strategist, stub_analyst
    ) -> None:
        c = _make_classification(agent_route="both", ticker="005930")
        asyncio.run(route_intent(c, [{"role": "user", "content": "x"}]))
        for call in stub_strategist:
            assert call.get("mock_fallback_allowed") is False
        for call in stub_analyst:
            assert call.get("mock_fallback_allowed") is False

    def test_analyst_direct_forwards_mock_fallback_disabled(
        self, stub_strategist, stub_analyst
    ) -> None:
        c = _make_classification(
            scenario_id=3,
            agent_route="analyst_direct",
            analyst_ids=["market_state_analyzer"],
            ticker=None,
        )
        asyncio.run(route_intent(c, [{"role": "user", "content": "x"}]))
        assert stub_analyst[0].get("mock_fallback_allowed") is False


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


class TestSubtaskDecomposition:
    """sub-task prompt 가 사용자 발화 forward 대신 분야별 prompt 로 변환되는지 검증."""

    def test_subtask_prompt_substitutes_ticker(self) -> None:
        prompt = _build_subtask_prompt(
            "stock_analyst",
            ticker="005930",
            ticker_display="삼성전자",
            original_input="삼성전자 살까?",
            scenario_id=2,
        )
        # ticker / display 치환 확인
        assert "005930" in prompt
        assert "삼성전자" in prompt
        # 영역 명시
        assert "종목분석가" in prompt or "stock_analyst" in prompt
        # 회피 차단 룰 (common_directives)
        assert "회피" in prompt or "산출" in prompt

    def test_subtask_prompt_includes_scenario_name(self) -> None:
        prompt = _build_subtask_prompt(
            "principle_guardian",
            ticker="005930",
            ticker_display="삼성전자",
            original_input="삼성전자 살까?",
            scenario_id=2,
        )
        # 시나리오 2 = "신규 진입"
        assert "신규 진입" in prompt

    def test_subtask_prompt_falls_back_when_no_template(self) -> None:
        """알 수 없는 분석가 id → fallback = original_input 그대로."""
        prompt = _build_subtask_prompt(
            "nonexistent_analyst",
            ticker=None,
            ticker_display=None,
            original_input="raw user input",
            scenario_id=2,
        )
        assert prompt == "raw user input"

    def test_stub_analyst_receives_subtask_not_original(
        self, stub_strategist, stub_analyst
    ) -> None:
        """라우터가 분석가에 던지는 messages 의 마지막 user content = sub-task prompt."""
        c = _make_classification(
            scenario_id=2, agent_route="track_a", ticker="005930"
        )
        asyncio.run(route_intent(c, [{"role": "user", "content": "삼성전자 살까?"}]))
        assert len(stub_analyst) >= 1
        for call in stub_analyst:
            last_msg = call["messages"][-1]
            assert last_msg["role"] == "user"
            # 사용자 원본 발화 그대로 forward 가 아니라 sub-task prompt 인지
            content = last_msg["content"]
            # sub-task prompt 가 본 영역 명시 (예: "주도주" / "수급" / "α" / "종목" 등) 포함
            assert len(content) > len("삼성전자 살까?") + 50, (
                f"sub-task prompt 가 너무 짧음 (forward 의심): {content[:200]}"
            )


class TestScenarioRouting:
    """시나리오별 분석가 축약 매핑 검증."""

    def test_scenario_1_uses_3_analysts(self, stub_strategist, stub_analyst) -> None:
        """시나리오 1 (보유 결정) = stock_analyst + principle_guardian + flow_analyzer 3명."""
        c = _make_classification(
            scenario_id=1, agent_route="track_a", ticker="005930"
        )
        asyncio.run(route_intent(c, [{"role": "user", "content": "삼성전자 들고 있어"}]))
        # 축약 매핑이 적용되어 3명만 호출
        called = {call["analyst_id"] for call in stub_analyst}
        assert called == {"stock_analyst", "principle_guardian", "flow_analyzer"}

    def test_scenario_2_uses_5_analysts(self, stub_strategist, stub_analyst) -> None:
        """시나리오 2 (신규 진입) = 5명."""
        c = _make_classification(
            scenario_id=2, agent_route="track_a", ticker="005930"
        )
        asyncio.run(route_intent(c, [{"role": "user", "content": "삼성전자 살까?"}]))
        called = {call["analyst_id"] for call in stub_analyst}
        # config 매핑 = stock_picker + stock_analyst + market_state_analyzer +
        # principle_guardian + flow_analyzer
        assert "stock_picker" in called
        assert "stock_analyst" in called
        assert "market_state_analyzer" in called
        assert "principle_guardian" in called
        assert "flow_analyzer" in called

    def test_scenario_7_uses_2_analysts_only(
        self, stub_strategist, stub_analyst
    ) -> None:
        """시나리오 7 (손절) = principle_guardian + market_state_analyzer 2명."""
        c = _make_classification(
            scenario_id=7, agent_route="track_a", ticker="005930"
        )
        asyncio.run(route_intent(c, [{"role": "user", "content": "손절선 깼다"}]))
        called = {call["analyst_id"] for call in stub_analyst}
        assert called == {"principle_guardian", "market_state_analyzer"}

    def test_unknown_scenario_falls_back_to_reads_analysts(
        self, stub_strategist, stub_analyst
    ) -> None:
        """scenario_id=999 (매핑 없음) → track_a reads_analysts 풀세트 fallback."""
        c = _make_classification(
            scenario_id=999, agent_route="track_a", ticker="005930"
        )
        asyncio.run(route_intent(c, [{"role": "user", "content": "x"}]))
        # track_a reads_analysts = 7명 (6명 + news_curator, NEWS-EVENT-INTERPRETATION-001 M1-c)
        assert len(stub_analyst) == 7

    def test_resolve_analyst_ids_helper(self) -> None:
        # 직접 helper 호출 검증
        ids1 = _resolve_analyst_ids_for_scenario(1, ["track_a"])
        assert set(ids1) == {"stock_analyst", "principle_guardian", "flow_analyzer"}
        ids_fallback = _resolve_analyst_ids_for_scenario(999, ["track_a"])
        assert len(ids_fallback) == 7  # 6명 + news_curator (M1-c 합류)


class TestTrackRequiredAugmentation:
    """track_required — Track B 경로 시 시나리오 축약이 떨어뜨린 권위 분석가(trader) 보강.

    2026-06-01 시연 발견: 시나리오 2(신규 진입)가 Track A 기준이라 trader 누락 →
    swing(Track B) 라우팅 시 cited_scores.t_score 항상 null. track 인지 보강으로 복구.
    """

    def test_track_b_appends_trader_for_scenario_2(self) -> None:
        """시나리오 2(5명) + Track B → trader 보강 = 6명, trader 포함."""
        ids = _resolve_analyst_ids_for_scenario(2, ["track_b"])
        assert "trader" in ids
        # 기존 5명 보존 + trader = 6
        assert len(ids) == 6
        assert {
            "stock_picker",
            "stock_analyst",
            "market_state_analyzer",
            "principle_guardian",
            "flow_analyzer",
        }.issubset(set(ids))

    def test_track_b_no_duplicate_when_trader_present(self) -> None:
        """시나리오 5는 이미 trader 포함 → 중복 추가 없이 5명 유지."""
        ids = _resolve_analyst_ids_for_scenario(5, ["track_b"])
        assert ids.count("trader") == 1
        assert len(ids) == 5

    def test_both_route_includes_trader(self) -> None:
        """both(track_a+track_b) → trader 보강."""
        ids = _resolve_analyst_ids_for_scenario(2, ["track_a", "track_b"])
        assert "trader" in ids

    def test_track_a_alone_does_not_add_trader(self) -> None:
        """Track A 단독 경로는 trader 미추가 (축약 의미 보존, 회귀 0)."""
        ids = _resolve_analyst_ids_for_scenario(2, ["track_a"])
        assert "trader" not in ids
        assert len(ids) == 5

    def test_route_intent_track_b_prefetches_trader(
        self, stub_strategist, stub_analyst
    ) -> None:
        """route_intent track_b 경로 → prefetch 분석가 호출에 trader 포함."""
        c = _make_classification(
            scenario_id=2, agent_route="track_b", ticker="005930"
        )
        asyncio.run(route_intent(c, [{"role": "user", "content": "삼성전자 단타 살까"}]))
        called = {call["analyst_id"] for call in stub_analyst}
        assert "trader" in called


class TestErrorHandling:
    def test_strategist_exception_is_captured(
        self, monkeypatch: pytest.MonkeyPatch, stub_analyst
    ) -> None:
        async def _raises(*args, **kwargs):
            raise RuntimeError("strategist boom")

        monkeypatch.setattr("core.intent.router.run_strategist", _raises)
        c = _make_classification(agent_route="track_a", ticker="005930")
        result = asyncio.run(route_intent(c, [{"role": "user", "content": "x"}]))
        # prefetch 분석가는 정상 호출 + strategist 만 error
        strategist_responses = [r for r in result.agent_responses if r.get("kind") == "strategist"]
        assert len(strategist_responses) == 1
        assert "strategist boom" in (strategist_responses[0].get("error") or "")

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
