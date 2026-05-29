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
    scrub_code_labels,
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
        """error 가 있는 entry 는 본문에서 제외되고 '응답 누락' 섹션에 ID만 표시.

        과거 양식은 본문에 error 메시지를 박았으나, mock fallback 차단 + 환각
        억제 본질에 따라 LLM 입력에서 완전히 제외.
        """
        msg = _compose_user_message(
            user_input="?",
            analyst_outputs=[{"id": "a1", "error": "boom"}],
            strategist_outputs=[{"agent_id": "track_a", "error": "boom"}],
        )
        assert "응답 누락" in msg
        assert "a1" in msg
        assert "track_a" in msg
        # 에러 본문은 노출 안 함
        assert "boom" not in msg

    def test_compose_excludes_mock_entries(self) -> None:
        """metadata.is_mock=True 또는 upstream_error 가 있는 entry 는 입력에서 제외."""
        msg = _compose_user_message(
            user_input="?",
            analyst_outputs=[
                {"id": "real", "text": "정상 응답", "metadata": {}},
                {"id": "mocked", "text": "가짜 응답", "metadata": {"is_mock": True}},
                {"id": "errored", "text": "에러 응답", "metadata": {"upstream_error": "boom"}},
            ],
            strategist_outputs=[],
        )
        # 정상 응답만 본문 포함
        assert "real" in msg
        assert "정상 응답" in msg
        # mock/error 본문은 제외
        assert "가짜 응답" not in msg
        assert "에러 응답" not in msg
        # 누락 섹션에는 ID 표시
        assert "응답 누락" in msg
        assert "mocked" in msg
        assert "errored" in msg


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
        # 빈 입력은 LLM 호출 자체를 skip 하니 실 응답 1건 이상 주입.
        result = asyncio.run(
            format_answer(
                user_input="x",
                analyst_outputs=[{"id": "a1", "text": "정상 raw"}],
                strategist_outputs=[],
            )
        )
        # raise X — text 에 안내 + upstream_error 채워짐
        assert "응답 정리에 실패" in result.text or "raw" in result.text.lower()
        assert result.upstream_error is not None
        assert "llm boom" in result.upstream_error

    def test_format_answer_skips_llm_when_all_responses_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """모든 분석가/전략가 응답이 mock/error/빈 응답 = LLM 호출 자체 skip + 안내 return.

        mock fallback 차단 본질: 자연어 답변에 가짜 narrative 가 섞이는 것 차단.
        """
        called = {"count": 0}

        async def _stub_llm(*args: Any, **kwargs: Any) -> dict:
            called["count"] += 1
            return {"content": "should not be called", "tokens_in": 0, "tokens_out": 0,
                    "model": "x", "cost_usd": 0.0, "raw": {}}

        monkeypatch.setattr("core.intent.formatter.call_llm", _stub_llm)
        result = asyncio.run(
            format_answer(
                user_input="삼성전자 살까?",
                analyst_outputs=[
                    {"id": "a1", "error": "boom"},
                    {"id": "a2", "metadata": {"is_mock": True}, "text": "fake"},
                    {"id": "a3", "text": ""},
                ],
                strategist_outputs=[
                    {"agent_id": "track_a", "metadata": {"upstream_error": "rate_limit"}, "text": "fake"},
                ],
            )
        )
        # LLM 호출 안 됨
        assert called["count"] == 0
        # 명시 안내 + upstream_error 라벨
        assert "응답을 받지 못했습니다" in result.text or "잠시 후 다시 시도" in result.text
        assert result.upstream_error == "all_upstream_responses_missing"
        assert result.is_mock is False


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


class TestScrubCodeLabels:
    """결정론 스크러버 — Flash 누출 코드 라벨 자연어 역치환 (모델 무관 production-clean)."""

    LEAKY_LABELS = [
        "S-Score", "s_score", "F-Score", "f_score", "T-Score", "buy_score",
        "verdict", "regime", "confidence", "cited", "RS Score", "RS",
        "Distribution Day", "holding_period", "progress_to_b",
        "sweet", "overheated", "trend_broken", "modest",
    ]

    def test_scrub_removes_score_labels(self) -> None:
        text = "주봉 S-Score=8 이고 buy_score 높음, F-Score 7."
        out = scrub_code_labels(text)
        assert "S-Score" not in out
        assert "buy_score" not in out
        assert "F-Score" not in out
        # 자연어 short 로 치환됨
        assert "주도주 점수" in out
        assert "매수 점수" in out
        assert "수급 점수" in out

    def test_scrub_removes_alpha_stage_labels(self) -> None:
        """α 5 단계 라벨 (sweet/overheated 등) = Flash 가 실제 누출한 토큰."""
        text = "주봉은 sweet 구간, 월봉은 overheated, 일봉은 weak."
        out = scrub_code_labels(text)
        assert "sweet" not in out
        assert "overheated" not in out
        assert "적정 가속 구간" in out
        assert "과열 구간" in out

    def test_scrub_skips_pure_korean_keys(self) -> None:
        """순수 한국어 key (분배일) 는 이미 자연어라 이중 wrap 하지 않음."""
        text = "오늘 분배일 신호 발생."
        out = scrub_code_labels(text)
        # 분배일 은 그대로 (괄호 설명으로 부풀지 않음)
        assert out == text

    def test_scrub_does_not_touch_english_word_internals(self) -> None:
        """짧은 ASCII 토큰 (RS) 이 영단어 내부에서 오치환되지 않아야."""
        text = "the first course covers diverse topics"
        out = scrub_code_labels(text)
        # 'first'(RS 포함), 'course', 'diverse'(RS 포함) 내부 미치환
        assert out == text

    def test_scrub_replaces_rs_score_before_rs(self) -> None:
        """길이 내림차순 — 'RS Score' 가 'RS' 보다 먼저 매칭."""
        out = scrub_code_labels("RS Score 가 높다")
        assert "RS" not in out
        assert "상대강도" in out

    def test_scrub_empty_and_clean_text(self) -> None:
        assert scrub_code_labels("") == ""
        clean = "지금은 보류예요. 외국인 매수가 강합니다."
        assert scrub_code_labels(clean) == clean

    def test_scrub_output_has_no_forbidden_labels(self) -> None:
        text = " ".join(f"{lbl}=x" for lbl in self.LEAKY_LABELS)
        out = scrub_code_labels(text)
        for label in TestCodeLabelGrep.FORBIDDEN_CODE_LABELS:
            assert label not in out

    def test_format_answer_applies_scrubber(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """format_answer 가 LLM 누출 라벨을 반환 직전 스크러빙."""
        async def _stub_llm(*args: Any, **kwargs: Any) -> dict:
            return {
                "content": "보류예요. 근거: S-Score=8, sweet 구간, verdict=hold.",
                "tokens_in": 10, "tokens_out": 5,
                "model": "gemini-2.5-flash", "cost_usd": 0.0, "raw": {},
            }

        monkeypatch.setattr("core.intent.formatter.call_llm", _stub_llm)
        result = asyncio.run(
            format_answer(
                user_input="삼성전자 살까?",
                analyst_outputs=[{"id": "a1", "text": "정상 raw"}],
                strategist_outputs=[],
            )
        )
        assert "S-Score" not in result.text
        assert "sweet" not in result.text
        assert "verdict" not in result.text
        assert "주도주 점수" in result.text
