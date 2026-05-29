"""ARCHITECTURE-HYBRID-EXECUTIVE-001 — 투자 총괄 임원 종합 모듈 단위 검증.

결정론 부분만 검증 (LLM 통찰 품질은 smoke + 사용자 평가):
  - system block = persona doctrine + canon + label 사전 주입
  - _compose_user_message = 분석가/전략가 raw 종합, mock/error 제외 + 누락 명시
  - synthesize_executive = 성공 stub / 예외 fallback / 전부 누락 시 LLM skip
  - persona.md 핵심 가드 (박종훈 변곡점 스코프 / 시나리오 3 / 전략가 verdict 맹종 금지)
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault("TESTING", "1")

from core.executive.synthesize import (
    ExecutiveResult,
    PERSONA_PATH,
    _build_system_blocks,
    _compose_user_message,
    reload_executive_config,
    synthesize_executive,
)


@pytest.fixture(autouse=True)
def _reload_each():
    reload_executive_config()
    yield
    reload_executive_config()


class TestSystemBlocks:
    def test_blocks_include_persona_and_labels(self) -> None:
        blocks = _build_system_blocks()
        joined = "\n".join(b.get("text", "") for b in blocks)
        # 임원 persona doctrine
        assert "투자 총괄 임원" in joined
        assert "시나리오 3" in joined
        # label 사전 (코드 라벨 → 자연어)
        assert "S-Score" in joined or "α" in joined
        # canon 주입 헤더
        assert "Investment Knowledge (Canon)" in joined

    def test_persona_has_park_jonghoon_inflection_guard(self) -> None:
        """박종훈 거시 framework = 변곡점 전용 (평상시 트레이딩 비인용) 가드 존재."""
        text = PERSONA_PATH.read_text(encoding="utf-8")
        assert "변곡점" in text
        assert "박종훈" in text
        # 기본 트레이딩 렌즈와 변곡점 렌즈 구분 명시
        assert "기본 트레이딩 렌즈" in text

    def test_persona_forbids_strategist_verdict_blind_follow(self) -> None:
        text = PERSONA_PATH.read_text(encoding="utf-8")
        assert "verdict" in text
        # 전략가 기계적 결론에 갇히지 말 것
        assert "재통합" in text


class TestComposeUserMessage:
    def test_includes_all_sections(self) -> None:
        msg = _compose_user_message(
            user_input="삼성전자 살까?",
            analyst_outputs=[
                {"id": "stock_analyst", "text": "주봉 sweet spot, 실적 가속"},
                {"id": "flow_analyzer", "text": "외국인 매도, 기관 매수"},
            ],
            strategist_outputs=[{"agent_id": "track_a", "text": "verdict wait, 목표가 미발행"}],
        )
        assert "삼성전자 살까?" in msg
        assert "stock_analyst" in msg
        assert "flow_analyzer" in msg
        assert "track_a" in msg
        assert "주봉 sweet spot" in msg

    def test_injects_snapshot_when_given(self) -> None:
        msg = _compose_user_message(
            user_input="?",
            analyst_outputs=[{"id": "a1", "text": "ok"}],
            strategist_outputs=[],
            market_snapshot_md="KOSPI 2,650 (+0.5%)",
        )
        assert "실시간 시장 스냅샷" in msg
        assert "KOSPI 2,650" in msg

    def test_excludes_mock_and_error_lists_missing(self) -> None:
        msg = _compose_user_message(
            user_input="?",
            analyst_outputs=[
                {"id": "real", "text": "정상", "metadata": {}},
                {"id": "mocked", "text": "가짜", "metadata": {"is_mock": True}},
                {"id": "errored", "error": "boom"},
            ],
            strategist_outputs=[],
        )
        assert "정상" in msg
        assert "가짜" not in msg
        assert "boom" not in msg
        assert "응답 누락" in msg
        assert "mocked" in msg
        assert "errored" in msg


class TestSynthesizeExecutive:
    def test_success_returns_text(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}

        async def _stub_llm(*args: Any, **kwargs: Any) -> dict:
            captured.update(kwargs)
            return {
                "content": "지금은 분할로 접근할 자리예요. 주봉 추세가 막 가속...",
                "tokens_in": 200,
                "tokens_out": 400,
                "model": "gemini-2.5-pro",
                "cost_usd": 0.01,
                "raw": {},
            }

        monkeypatch.setattr("core.executive.synthesize.call_llm", _stub_llm)
        result = asyncio.run(
            synthesize_executive(
                user_input="삼성전자 살까?",
                analyst_outputs=[{"id": "stock_analyst", "text": "주봉 sweet"}],
                strategist_outputs=[{"agent_id": "track_a", "text": "verdict wait"}],
            )
        )
        assert isinstance(result, ExecutiveResult)
        assert "분할로 접근" in result.text
        assert result.upstream_error is None
        # mock_fallback_allowed=False 강제 (production 경로 silent mock 차단)
        assert captured.get("mock_fallback_allowed") is False
        # max_tokens = manifest 8000 (Gemini 2.5 Pro thinking 토큰이 예산 잠식 → 잘림 방지)
        assert captured.get("max_tokens") == 8000

    def test_model_override_passed_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """tier A/B 비교용 model override 가 call_llm 으로 전달."""
        captured: dict[str, Any] = {}

        async def _stub_llm(*args: Any, **kwargs: Any) -> dict:
            captured.update(kwargs)
            return {"content": "ok", "tokens_in": 1, "tokens_out": 1,
                    "model": kwargs.get("model"), "cost_usd": 0.0, "raw": {}}

        monkeypatch.setattr("core.executive.synthesize.call_llm", _stub_llm)
        asyncio.run(
            synthesize_executive(
                user_input="?",
                analyst_outputs=[{"id": "a1", "text": "raw"}],
                strategist_outputs=[],
                model="gemini-2.5-flash",
            )
        )
        assert captured.get("model") == "gemini-2.5-flash"

    def test_handles_llm_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _raises(*args: Any, **kwargs: Any) -> dict:
            raise RuntimeError("gemini boom")

        monkeypatch.setattr("core.executive.synthesize.call_llm", _raises)
        result = asyncio.run(
            synthesize_executive(
                user_input="x",
                analyst_outputs=[{"id": "a1", "text": "정상 raw"}],
                strategist_outputs=[],
            )
        )
        assert result.upstream_error is not None
        assert "gemini boom" in result.upstream_error
        assert "실패" in result.text or "확인" in result.text

    def test_skips_llm_when_all_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called = {"count": 0}

        async def _stub_llm(*args: Any, **kwargs: Any) -> dict:
            called["count"] += 1
            return {"content": "x", "tokens_in": 0, "tokens_out": 0, "model": "x", "cost_usd": 0.0, "raw": {}}

        monkeypatch.setattr("core.executive.synthesize.call_llm", _stub_llm)
        result = asyncio.run(
            synthesize_executive(
                user_input="삼성전자 살까?",
                analyst_outputs=[
                    {"id": "a1", "error": "boom"},
                    {"id": "a2", "metadata": {"is_mock": True}, "text": "fake"},
                ],
                strategist_outputs=[
                    {"agent_id": "track_a", "metadata": {"upstream_error": "rate"}, "text": "fake"},
                ],
            )
        )
        assert called["count"] == 0
        assert result.upstream_error == "all_upstream_responses_missing"
        assert result.is_mock is False
