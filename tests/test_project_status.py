"""project_status.py — 프로젝트 단계 지도 파생 출력 검증.

실 roadmap SPEC 트리(파일)를 읽어 렌더 (LLM/API 무관, 순수 파싱).
세션마다 /resume·/wrap-up 이 의존하므로 조용한 회귀 방지.
"""
from __future__ import annotations

from scripts.project_status import build_status_report


def test_report_has_core_sections():
    rpt = build_status_report()
    assert "프로젝트 단계 지도" in rpt
    assert "현재 ACTIVE 작업" in rpt
    assert "roadmap 미연결 미완 SPEC" in rpt


def test_master_roadmap_is_root_and_nests_left_brain():
    rpt = build_status_report()
    # 마스터가 뿌리로 렌더되고 그 아래 왼쪽 뇌 roadmap 이 들여쓰기되어 매달림
    assert "PROJECT-NORTH-STAR-001" in rpt
    i_master = rpt.index("PROJECT-NORTH-STAR-001")
    i_left = rpt.index("LEFT-BRAIN-COMPLETION-001")
    assert i_master < i_left  # 마스터가 먼저(뿌리)


def test_active_lists_only_governed_implementing():
    rpt = build_status_report()
    active_block = rpt.split("현재 ACTIVE 작업")[1].split("roadmap 미연결")[0]
    # ANSWER-FIDELITY-001 은 roadmap 자식 + implementing → ACTIVE
    assert "ANSWER-FIDELITY-001" in active_block
    # legacy stale-implementing(미연결)은 ACTIVE 에서 제외
    assert "BRIEFING-ON-DEMAND-001" not in active_block
