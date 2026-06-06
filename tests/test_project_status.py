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
    # 거버넌스 불변식을 *실 SPEC 데이터* 기준으로 검증 (특정 SPEC 의 transient status 하드코딩 금지 —
    # 그 SPEC 이 verified 로 넘어가면 깨지는 stale 테스트가 됨. 2026-06-06 stale 발견 후 구조화).
    from scripts.project_status import _INPROGRESS, _load_specs

    rpt = build_status_report()
    active_block = rpt.split("현재 ACTIVE 작업")[1].split("roadmap 미연결")[0]
    listed = {
        ln.replace("🔨", "").strip()
        for ln in active_block.splitlines()
        if "🔨" in ln
    }

    specs = _load_specs()
    roadmap_children: set[str] = set()
    for p in specs.values():
        if p.meta.level == "roadmap":
            roadmap_children.update(p.meta.children)

    expected = {
        sid for sid, p in specs.items()
        if p.meta.level == "implementation"
        and p.meta.status in _INPROGRESS
        and (sid in roadmap_children or bool(p.meta.parent))
    }
    # ACTIVE = roadmap 연결 + implementing 인 implementation 만 (legacy stale-implementing 제외)
    assert listed == expected
    # 핵심 불변식: legacy stale-implementing(미연결)은 어떤 경우에도 ACTIVE 아님
    assert "BRIEFING-ON-DEMAND-001" not in listed
