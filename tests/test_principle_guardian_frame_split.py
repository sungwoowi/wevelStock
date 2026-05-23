"""principle_guardian frame_mode (advisory vs execution) 분리 검증.

PRODUCTION-UX-001 후속 fix: 사용자 발화 "삼성전자 살까?" 같은 일반 의견 단계
(advisory frame) 에서 OS1~OS6 정량 룰이 silent blocking violation 으로 발동되어
Track A 종합 verdict 가 wait 강제 도미노로 떨어지는 문제 차단.

검증:
  - sub-task prompt 가 advisory frame 명시 + advisory_warning 라벨 강제
  - persona.md 의 verdict doctrine 에 frame_mode 분기 명시
  - manifest.yaml response_rules 의 verdict 표에 advisory_warning 라벨
  - Track A/B persona 가 advisory_warning verdict 를 wait 강제 도미노 X 명시
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("TESTING", "1")

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestSubtaskPromptAdvisoryFrame:
    """config/analyst_subtasks.yaml 의 principle_guardian sub-task prompt 검증."""

    def setup_method(self) -> None:
        from core.intent.router import _build_subtask_prompt, reload_subtasks_and_routing

        reload_subtasks_and_routing()
        self._build = _build_subtask_prompt

    def test_prompt_declares_advisory_frame(self) -> None:
        prompt = self._build(
            "principle_guardian",
            ticker="005930",
            ticker_display="삼성전자",
            original_input="삼성전자 살까?",
            scenario_id=2,
        )
        # advisory frame 명시
        assert "advisory frame" in prompt
        # 사용자 입력 결측이 정상이라는 명시
        assert "정상" in prompt
        # advisory_warning 라벨
        assert "advisory_warning" in prompt
        # violation 라벨 사용 금지 명시
        assert "violation" in prompt and "강제 X" in prompt

    def test_prompt_states_track_no_domino(self) -> None:
        """Track A/B 가 advisory_warning 을 wait 강제로 받지 않는다는 명시."""
        prompt = self._build(
            "principle_guardian",
            ticker="005930",
            ticker_display="삼성전자",
            original_input="삼성전자 살까?",
            scenario_id=2,
        )
        # Track A/B 정합 명시
        assert ("Track A" in prompt and "wait" in prompt) or "도미노" in prompt


class TestPrinciplePersonaFrameDoctrine:
    """agents/analysts/principle_guardian/persona.md 의 frame_mode 분기 명시."""

    @pytest.fixture(scope="class")
    def persona_text(self) -> str:
        return (
            REPO_ROOT / "agents" / "analysts" / "principle_guardian" / "persona.md"
        ).read_text(encoding="utf-8")

    def test_persona_declares_frame_mode_table(self, persona_text: str) -> None:
        # frame_mode 표 헤더
        assert "frame_mode" in persona_text
        assert "advisory" in persona_text
        assert "execution" in persona_text
        # advisory_warning 라벨 정의
        assert "advisory_warning" in persona_text

    def test_persona_verdict_algorithm_has_frame_branch(self, persona_text: str) -> None:
        """issue_verdict 알고리즘이 frame_mode 분기 포함."""
        # 알고리즘에 frame_mode 인자 + 분기 명시
        assert "frame_mode" in persona_text
        # advisory 에서 advisory_warning 반환 라인
        assert "advisory_warning" in persona_text
        # execution 에서 violation blocking 명시
        assert "blocking" in persona_text or "차단" in persona_text

    def test_persona_lists_advisory_warning_in_korean_table(self, persona_text: str) -> None:
        """한국어 친화 verdict 표에 advisory_warning 라벨."""
        # 한국어 친화 + 코드 라벨 병기
        assert "advisory_warning" in persona_text
        assert "사전 검토" in persona_text or "advisory frame" in persona_text


class TestPrincipleManifestFrameRules:
    """agents/analysts/principle_guardian/manifest.yaml response_rules 검증."""

    @pytest.fixture(scope="class")
    def manifest_text(self) -> str:
        return (
            REPO_ROOT / "agents" / "analysts" / "principle_guardian" / "manifest.yaml"
        ).read_text(encoding="utf-8")

    def test_manifest_declares_frame_mode(self, manifest_text: str) -> None:
        assert "frame_mode" in manifest_text or "advisory frame" in manifest_text
        assert "execution frame" in manifest_text
        assert "advisory_warning" in manifest_text

    def test_manifest_verdict_table_lists_advisory_warning(self, manifest_text: str) -> None:
        """verdict 분기 표에 advisory_warning 라벨 + violation 은 execution 전용 명시."""
        assert "advisory_warning" in manifest_text
        # violation 이 execution frame 전용 명시
        assert "execution frame" in manifest_text


class TestTrackPersonaAdvisoryWarningHandling:
    """Track A/B persona 가 advisory_warning verdict 를 wait 강제 도미노로 받지 않는다."""

    @pytest.fixture(scope="class")
    def track_a_text(self) -> str:
        return (
            REPO_ROOT / "agents" / "strategists" / "track_a" / "persona.md"
        ).read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def track_b_text(self) -> str:
        return (
            REPO_ROOT / "agents" / "strategists" / "track_b" / "persona.md"
        ).read_text(encoding="utf-8")

    def test_track_a_acknowledges_advisory_warning(self, track_a_text: str) -> None:
        # 진입 조건 표 또는 가중치 표에 advisory_warning 처리 명시
        assert "advisory_warning" in track_a_text

    def test_track_b_acknowledges_advisory_warning(self, track_b_text: str) -> None:
        assert "advisory_warning" in track_b_text
