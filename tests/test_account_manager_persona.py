"""ACCOUNT-MANAGER-001 (RB-MS1) — Layer 4 계좌관리자 persona/manifest 양식 검증.

8-섹션 양식 + manifest 키 + boundary 강제(종목 판단 금지·손절 누락 차단·가상 전용) 회귀 가드.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
AM_DIR = REPO_ROOT / "agents" / "account_manager"

_SECTIONS = [
    "## Identity",
    "## Domain Frame",
    "## Inputs",
    "## Outputs",
    "## Reasoning Doctrine",
    "## Knowledge Categories",
    "## Anti-patterns",
    "## Cross-Agent Boundaries",
]


def _persona() -> str:
    return (AM_DIR / "persona.md").read_text(encoding="utf-8")


def _manifest() -> dict:
    return yaml.safe_load((AM_DIR / "manifest.yaml").read_text(encoding="utf-8"))


def test_files_exist():
    assert (AM_DIR / "persona.md").exists()
    assert (AM_DIR / "manifest.yaml").exists()


def test_persona_has_eight_sections():
    body = _persona()
    for sec in _SECTIONS:
        assert sec in body, f"누락 섹션: {sec}"


def test_manifest_core_keys():
    m = _manifest()
    assert m["id"] == "account_manager"
    assert m["display_name"] == "계좌관리자"
    assert "principles" in m["reads"]
    assert m["llm"]["temperature"] == 0.3
    assert m["contract_version"] == "1.0"


def test_manifest_canon_is_principles():
    m = _manifest()
    assert all(c.startswith("principles/") for c in m["canon_categories"])
    assert "principles/philosophy_seven_commandments" in m["canon_categories"]


def test_persona_forbids_stock_judgement():
    # Layer 4 는 종목 판단 금지 — 비중만
    body = _persona()
    assert "종목 분석·매수 여부 판단 금지" in body


def test_persona_states_stop_loss_hard_block():
    # 손절 누락 = 유일한 하드 차단 명시
    body = _persona()
    assert "손절" in body and "차단" in body


def test_persona_paper_only_boundary():
    # 가상(페이퍼) 전용 — 실 KIS 주문 금지 경계
    body = _persona()
    assert "가상" in body and "KIS 주문 금지" in body


def test_persona_two_lever_doctrine():
    # 두 레버(리스크 R × regime 변조) 결정론 본질 명시
    body = _persona()
    assert "레버 1" in body and "레버 2" in body
