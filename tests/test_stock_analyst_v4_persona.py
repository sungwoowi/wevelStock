"""INFRA-FUNDAMENTAL-DATA-001 — stock_analyst v4 페르소나 정정 자동 검증.

cycle 10 (2026-05-21) 의 v4 마이크로 정정 = F2·F5 의 unknown 가드 해제 +
fundamental_data_md `[5]` 블록 출처 명시 강제. 정정 3 위치:
  (a) § Outputs 격자 [1] Quality Grid 의 F2/F5 출처 표기
  (b) § Reasoning Doctrine F1~F5 정의 표 F2/F5 row 본문 정량 임계
  (c) manifest response_rules F2/F5 본문 정정 + reads_fundamental_data: true

회귀 보장: 8 섹션 portable + cited 풀이 v3.1 + Track A read 정합 + v3 흔적 (chart_data_md, [4]) 모두 보존.
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
# 1. manifest reads_fundamental_data: true (Step 12 핵심)
# ---------------------------------------------------------------------------


def test_manifest_reads_fundamental_data_true(manifest_raw: dict) -> None:
    assert manifest_raw.get("reads_fundamental_data") is True
    # v3 의 reads_chart_data 도 그대로 유지 (회귀 보장)
    assert manifest_raw.get("reads_chart_data") is True


# ---------------------------------------------------------------------------
# 2. persona § Outputs 격자 [1] Quality Grid F2·F5 unknown 강제 해제
# ---------------------------------------------------------------------------


def test_persona_quality_grid_f2_f5_unknown_lifted(persona_text: str) -> None:
    # v3 의 "INFRA-FUNDAMENTAL-DATA-001 후속 (현재 unknown)" 표기 제거
    assert "INFRA-FUNDAMENTAL-DATA-001 후속 (현재 unknown)" not in persona_text
    # v4 의 fundamental_data_md [5] 출처 표기로 대체
    assert "fundamental_data_md [5]" in persona_text
    # F2 의 5 ratio 어휘
    assert "EPS TTM·PE·ROE·Op.Margin·Debt/Eq" in persona_text
    # v4 단계 라벨
    assert "v4 단계" in persona_text


# ---------------------------------------------------------------------------
# 3. persona § Reasoning Doctrine F2/F5 정의 표 의 fundamental_data_md 출처
# ---------------------------------------------------------------------------


def test_persona_reasoning_doctrine_f2_f5_v4(persona_text: str) -> None:
    # F2 정의 표의 정량 임계
    assert "PE < 업종 평균" in persona_text
    assert "ROE > 15%" in persona_text
    assert "Op.Margin > 10%" in persona_text
    assert "Debt/Eq < 100%" in persona_text
    # F5 정의 표의 분기 4분기 QoQ·YoY
    assert "분기 매출·영업이익·EPS QoQ·YoY" in persona_text
    # v4 단계 라벨 전환
    assert "v4 단계 (2026-05-21" in persona_text


# ---------------------------------------------------------------------------
# 4. manifest response_rules F2/F5 가드 본문 정정 + v4 정정 라벨
# ---------------------------------------------------------------------------


def test_manifest_response_rules_v4_correction(manifest_raw: dict) -> None:
    rr = manifest_raw.get("response_rules") or ""
    # v3 의 "INFRA-FUNDAMENTAL-DATA-001 후속" 표현 제거
    assert "F2 (펀더멘털) — PER·PBR·매출 성장·ROE 의 분기 변화" not in rr
    assert "F5 (실적 모멘텀) — 분기 실적 QoQ·YoY 2 분기 연속 둔화 시 청산. INFRA-FUNDAMENTAL-DATA-001 후속" not in rr
    # v4 의 fundamental_data_md [5] 출처 표기
    assert "fundamental_data_md [5]" in rr
    # v4 정정 라벨
    assert "v4 정정" in rr


# ---------------------------------------------------------------------------
# 5. v4 정정 트레이스 § 존재 + 8 섹션 + Track A 회귀 보장
# ---------------------------------------------------------------------------


def test_v4_trace_section_and_compat_unchanged(persona_text: str) -> None:
    # v4 정정 트레이스 §
    assert "### v4 정정 트레이스 (2026-05-21" in persona_text
    assert "MS3 완전 도달" in persona_text
    # v3 트레이스 § 도 보존 (deprecation X)
    assert "### v3 정정 트레이스" in persona_text
    # 8 섹션 portable (회귀 보장)
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
    # v3 의 chart_data_md 출처 명시도 보존 (회귀 보장)
    assert "chart_data_md" in persona_text
    assert "[4]" in persona_text
