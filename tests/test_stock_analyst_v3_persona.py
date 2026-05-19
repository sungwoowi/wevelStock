"""INFRA-CHART-DATA-001 — stock_analyst v3 페르소나 정정 자동 검증.

cycle 5 (2026-05-20) 의 v3 마이크로 정정 = 환각 가드 2 해제 + chart_data_md `[4]` 블록
출처 명시 강제. 정정 3 위치:
  (a) § Anti-patterns 의 가드 2 본문 (persona.md)
  (b) § Outputs 격자 [1] Quality Grid 의 α·F1 unknown 강제 해제 (persona.md)
  (c) manifest response_rules + reads_chart_data: true (manifest.yaml)

회귀 보장: 8 섹션 portable 양식 + cited 풀이 v3.1 양식 + Track A read 정합 + 권위 한정 모두 불변.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


REPO = Path(__file__).resolve().parents[1]
PERSONA = REPO / "agents/analysts/stock_analyst/persona.md"
MANIFEST = REPO / "agents/analysts/stock_analyst/manifest.yaml"


@pytest.fixture(scope="module")
def persona_text() -> str:
    return PERSONA.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def manifest_raw() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}


# ---------------------------------------------------------------------------
# 1. manifest 의 reads_chart_data: true (Step 10 핵심 정정)
# ---------------------------------------------------------------------------


def test_manifest_reads_chart_data_true(manifest_raw: dict) -> None:
    assert manifest_raw.get("reads_chart_data") is True


# ---------------------------------------------------------------------------
# 2. v2 의 verdict=unknown 강제 표현 제거 (manifest)
# ---------------------------------------------------------------------------


def test_manifest_unknown_force_removed(manifest_raw: dict) -> None:
    rr = manifest_raw.get("response_rules") or ""
    # v2 의 "verdict=`unknown` 강제" 패턴이 사라졌어야 함
    assert "verdict=`unknown` 강제" not in rr
    # 대신 chart_data_md 부재 시 inconclusive 사용 안내
    assert "chart_data_md" in rr
    assert "inconclusive" in rr


# ---------------------------------------------------------------------------
# 3. persona § Anti-patterns 의 환각 가드 2 본문 정정 — chart_data_md [4] 출처 명시 강제
# ---------------------------------------------------------------------------


def test_persona_chart_citation_rule_v3(persona_text: str) -> None:
    # v3 의 핵심 표현: chart_data_md [4] 블록 출처 명시 강제
    assert "chart_data_md" in persona_text
    assert "[4]" in persona_text
    # 출처 명시 강제 키워드
    assert "출처 명시" in persona_text or "출처만 인용" in persona_text


# ---------------------------------------------------------------------------
# 4. persona § Outputs 격자 [1] Quality Grid 의 α·F1 unknown 강제 해제
# ---------------------------------------------------------------------------


def test_persona_quality_grid_alpha_f1_unknown_lifted(persona_text: str) -> None:
    # v2 의 "INFRA-CHART-DATA-001 (미비 시 unknown)" 패턴이 사라졌어야 함
    assert "INFRA-CHART-DATA-001 (미비 시 unknown)" not in persona_text
    # v3 의 chart_data_md [4] 출처 표기로 대체
    assert "chart_data_md [4]" in persona_text


# ---------------------------------------------------------------------------
# 5. 8 섹션 portable 양식 + cited 풀이 v3.1 양식 + Track A read 정합 (회귀 보장)
# ---------------------------------------------------------------------------


def test_persona_eight_sections_and_track_a_compat_unchanged(persona_text: str) -> None:
    # 8 섹션 portable (ANALYST-PERSONAS-001 v2)
    for section in (
        "## Identity",
        "## Domain Frame",
        "## Inputs",
        "## Outputs",
        "## Reasoning Doctrine",
        "## Knowledge Categories",
        "## Anti-patterns",
        "## Cross-Agent Boundaries",
    ):
        assert section in persona_text, f"섹션 누락: {section}"
    # cited 풀이 v3.1 양식
    assert "cited: []" in persona_text
    assert "근거 명제 풀이:" in persona_text
    # 권위 한정 4 가지 발행물 불변
    assert "α (가속계수)" in persona_text
    assert "Module A 목표가 3 단" in persona_text
    assert "F1~F5" in persona_text
    assert "holding_period_estimate_days" in persona_text
    # Track A read 정합
    assert "Track A" in persona_text
    # 박종훈 framework 직접 인용 금지 가드 유지
    assert "박종훈 framework 직접 인용 금지" in persona_text or "박종훈 framework" in persona_text
