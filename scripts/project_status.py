"""프로젝트 단계 지도 — roadmap SPEC 트리에서 진행도·ACTIVE·drift 후보를 파생 출력.

2층 SPEC 구조(docs/STRUCTURE.md § SPEC 2-tier)를 단일 진실원으로 읽는다:
  roadmap(level=roadmap, children=[...]) → implementation(level=implementation, parent=...).

세션마다 `/resume`(시작)·`/wrap-up`(끝) 이 이 출력을 읽어
"지금 전체 단계 중 어디인가 / 딴 데로 새는가" 를 점검한다. 손으로 적는 % 가 아닌 파생값.

drift 판정 자체는 사람/LLM 추론 영역 — 이 스크립트는 지도와 후보만 제공(게이트 아님).

usage: uv run python scripts/project_status.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.contracts.spec_frontmatter import (  # noqa: E402
    ParsedSpec,
    SpecParseError,
    find_all_specs,
    parse_spec,
)

# status 분류
_DONE = {"implemented", "verified", "done"}
_INPROGRESS = {"implementing"}
_TODO = {"draft", "approved"}


def _load_specs() -> dict[str, ParsedSpec]:
    out: dict[str, ParsedSpec] = {}
    for path in find_all_specs(REPO_ROOT):
        try:
            parsed = parse_spec(path)
        except SpecParseError:
            continue
        out[parsed.meta.spec_id] = parsed
    return out


def _status_mark(status: str) -> str:
    if status in _DONE:
        return "✅"
    if status in _INPROGRESS:
        return "🔨"
    if status in _TODO:
        return "□"
    return "·"


def _roadmap_progress(parsed: ParsedSpec, specs: dict[str, ParsedSpec]) -> tuple[int, int, int, int]:
    """roadmap 의 자식 implementation 기준 (done, inprogress, total, missing)."""
    done = inprog = total = missing = 0
    for child_id in parsed.meta.children:
        total += 1
        child = specs.get(child_id)
        if child is None:
            missing += 1
            continue
        st = child.meta.status
        if st in _DONE:
            done += 1
        elif st in _INPROGRESS:
            inprog += 1
    return done, inprog, total, missing


def _render_roadmap(
    rid: str, specs: dict[str, ParsedSpec], lines: list[str], depth: int, seen: set[str]
) -> None:
    if rid in seen:
        return
    seen.add(rid)
    parsed = specs.get(rid)
    indent = "    " * depth
    if parsed is None:
        lines.append(f"{indent}- {rid} [미작성]")
        return
    done, inprog, total, missing = _roadmap_progress(parsed, specs)
    pct = round(done / total * 100) if total else 0
    head = f"{indent}🗺  {rid} — {parsed.meta.title.split('—')[0].strip()} [roadmap]"
    prog = f"완료 {done}/{total} ({pct}%)" + (f" · 진행중 {inprog}" if inprog else "")
    if missing:
        prog += f" · 미작성 {missing}"
    lines.append(f"{head}  {prog}")
    for child_id in parsed.meta.children:
        child = specs.get(child_id)
        if child is not None and child.meta.level == "roadmap":
            _render_roadmap(child_id, specs, lines, depth + 1, seen)
        else:
            cindent = "    " * (depth + 1)
            if child is None:
                lines.append(f"{cindent}{_status_mark('')} {child_id} [미작성]")
            else:
                active = "  ◀ 현재 작업" if child.meta.status in _INPROGRESS else ""
                lines.append(
                    f"{cindent}{_status_mark(child.meta.status)} {child_id} "
                    f"[{child.meta.status}]{active}"
                )


def build_status_report() -> str:
    specs = _load_specs()
    roadmaps = {sid: p for sid, p in specs.items() if p.meta.level == "roadmap"}

    # 뿌리 roadmap = 다른 roadmap 의 child 로 참조되지 않은 roadmap
    referenced: set[str] = set()
    for p in roadmaps.values():
        referenced.update(p.meta.children)
    roots = [sid for sid in roadmaps if sid not in referenced]

    lines: list[str] = ["=== wevelStock 프로젝트 단계 지도 (roadmap SPEC 파생) ===", ""]
    if not roots:
        lines.append("(roadmap SPEC 없음 — docs/STRUCTURE.md § SPEC 2-tier 참조)")
    seen: set[str] = set()
    for rid in sorted(roots):
        _render_roadmap(rid, specs, lines, 0, seen)
        lines.append("")

    roadmap_children: set[str] = set()
    for p in roadmaps.values():
        roadmap_children.update(p.meta.children)

    def _governed(sid: str, p: ParsedSpec) -> bool:
        """roadmap 에 연결된 작업 (자식이거나 parent 명시) — 신 거버넌스 하의 작업."""
        return sid in roadmap_children or bool(p.meta.parent)

    # ACTIVE = roadmap 연결 + implementing 인 implementation 만 (legacy stale-implementing 제외)
    active = sorted(
        sid for sid, p in specs.items()
        if p.meta.level == "implementation" and p.meta.status in _INPROGRESS and _governed(sid, p)
    )
    lines.append("── 현재 ACTIVE 작업 (roadmap 연결 + implementing) ──")
    lines.extend(f"  🔨 {sid}" for sid in active) if active else lines.append("  (없음)")
    lines.append("")

    # drift 후보 = roadmap 미연결 *미완* implementation SPEC (대부분 거버넌스 이전 legacy 백로그).
    # 세션 단위 drift 판정 = 이 목록이 *지난 세션 대비 늘었나* — 사람/LLM 추론.
    orphans_open = sorted(
        sid for sid, p in specs.items()
        if p.meta.level == "implementation"
        and p.meta.status in (_TODO | _INPROGRESS)
        and not _governed(sid, p)
    )
    lines.append(
        f"── roadmap 미연결 미완 SPEC {len(orphans_open)}개 "
        "(legacy 백로그 + 신규 drift — 새 항목 생기면 roadmap 에 연결) ──"
    )
    lines.extend(f"  · {sid}" for sid in orphans_open) if orphans_open else lines.append("  (없음)")
    lines.append("")

    legacy_done = sum(
        1 for sid, p in specs.items()
        if p.meta.level == "implementation" and p.meta.status in _DONE and not _governed(sid, p)
    )
    lines.append(f"(roadmap 밖 완료 legacy SPEC: {legacy_done}개 — 거버넌스 이전, 정상)")
    return "\n".join(lines)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows cp949 가드
    except Exception:  # noqa: BLE001
        pass
    print(build_status_report())


if __name__ == "__main__":
    main()
