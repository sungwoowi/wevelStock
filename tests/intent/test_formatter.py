"""PRODUCTION-UX-001 — formatter (자연어 1~3줄 압축) 단위 검증.

핵심 assertion:
  - call_llm stub 호출 시 system prompt 에 label_dictionary 사전 블록 주입됨
  - format_answer 가 호출 실패 시 안내 fallback text 반환 (raise X)
  - 빈 입력 케이스 안전
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest

os.environ.setdefault("TESTING", "1")

from core.intent.formatter import (
    FormatterResult,
    _build_label_block,
    _compose_user_message,
    format_answer,
    reload_label_dictionary,
)


@pytest.fixture(autouse=True)
def _reload_dict_each():
    reload_label_dictionary()
    yield
    reload_label_dictionary()


class TestLabelBlock:
    """label_dictionary.yaml 로드 + system block 빌드."""

    def test_label_block_has_seed_labels(self) -> None:
        block = _build_label_block()
        assert "α" in block
        assert "S-Score" in block
        assert "F-Score" in block
        assert "verdict" in block
        # 자연어 변환 매핑 포함
        assert "주도주" in block
        assert "수급" in block
        assert "가속" in block

    def test_label_block_lists_evidence_categories(self) -> None:
        block = _build_label_block()
        assert "수급" in block
        assert "차트" in block
        assert "실적" in block


class TestComposeUserMessage:
    """formatter 입력 = 사용자 발화 + 분석가 + 전략가 raw."""

    def test_compose_includes_all_sections(self) -> None:
        msg = _compose_user_message(
            user_input="삼성전자 살까?",
            analyst_outputs=[
                {"id": "stock_picker", "text": "S-Score: 8, 주도주 강함"},
                {"id": "flow_analyzer", "text": "F-Score: 7, 외국인 매수"},
            ],
            strategist_outputs=[
                {"agent_id": "track_a", "text": "verdict: hold, target: 88,000"},
            ],
        )
        assert "삼성전자 살까?" in msg
        assert "stock_picker" in msg
        assert "flow_analyzer" in msg
        assert "track_a" in msg
        assert "주도주 강함" in msg

    def test_compose_truncates_long_analyst_text(self) -> None:
        long_text = "x" * 5000
        msg = _compose_user_message(
            user_input="?",
            analyst_outputs=[{"id": "a1", "text": long_text}],
            strategist_outputs=[],
        )
        # 2000 chars max + truncated 표시
        assert "truncated" in msg
        assert len(msg) < 5000 + 1000

    def test_compose_handles_error_entries(self) -> None:
        msg = _compose_user_message(
            user_input="?",
            analyst_outputs=[{"id": "a1", "error": "boom"}],
            strategist_outputs=[{"agent_id": "track_a", "error": "boom"}],
        )
        assert "호출 실패" in msg
        assert "boom" in msg


class TestFormatAnswerFallback:
    """format_answer 의 LLM 호출 stub + fallback 경로."""

    def test_format_answer_returns_text_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}

        async def _stub_llm(*args: Any, **kwargs: Any) -> dict:
            captured.update(kwargs)
            return {
                "content": "지금은 보류 권고예요.\n\n근거:\n- 수급: 외국인 매수 강함\n- 차트: 추세 가속도 정상\n- 실적: EPS 상승세",
                "tokens_in": 100,
                "tokens_out": 30,
                "model": "gemini-2.5-flash-lite",
                "cost_usd": 0.0001,
                "raw": {},
            }

        monkeypatch.setattr("core.intent.formatter.call_llm", _stub_llm)
        result = asyncio.run(
            format_answer(
                user_input="삼성전자 살까?",
                analyst_outputs=[{"id": "stock_picker", "text": "..."}],
                strategist_outputs=[{"agent_id": "track_a", "text": "..."}],
            )
        )
        assert isinstance(result, FormatterResult)
        assert "보류 권고" in result.text
        assert "근거:" in result.text
        assert result.upstream_error is None
        # system 블록에 label dictionary 가 포함되었는지
        system_blocks = captured.get("system") or []
        assert isinstance(system_blocks, list)
        joined = " ".join(b.get("text", "") for b in system_blocks)
        assert "S-Score" in joined or "α" in joined

    def test_format_answer_handles_llm_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _raises(*args: Any, **kwargs: Any) -> dict:
            raise RuntimeError("llm boom")

        monkeypatch.setattr("core.intent.formatter.call_llm", _raises)
        result = asyncio.run(
            format_answer(
                user_input="x",
                analyst_outputs=[],
                strategist_outputs=[],
            )
        )
        # raise X — text 에 안내 + upstream_error 채워짐
        assert "응답 정리에 실패" in result.text or "raw" in result.text.lower()
        assert result.upstream_error is not None
        assert "llm boom" in result.upstream_error


class TestCodeLabelGrep:
    """formatter 응답에 코드 라벨이 노출되지 않아야 (assertion 양식 검증)."""

    FORBIDDEN_CODE_LABELS = [
        "S-Score",
        "F-Score",
        "T-Score",
        "buy_score",
        "verdict",
        "regime",
        "cited",
        "RS Score",
        "Distribution Day",
    ]

    def test_grep_assertion_helper_works(self) -> None:
        """본 테스트는 grep helper 자체를 검증 — 실제 LLM 응답 검증은 e2e 에서."""
        good_text = "지금은 보류 권고예요.\n근거: 주도주 점수 8, 수급 강함, 추세 정상."
        bad_text = "S-Score=8, F-Score=7, verdict=hold"
        # good_text 에 금지 라벨 없음
        for label in self.FORBIDDEN_CODE_LABELS:
            assert label not in good_text
        # bad_text 에 일부 라벨 있음
        assert any(label in bad_text for label in self.FORBIDDEN_CODE_LABELS)
