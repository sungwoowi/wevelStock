"""Scaffolder — create new teams, MCP servers, or SPEC files.

Usage:
    uv run python -m scripts.scaffold team <id> [--runtime rule|llm|hybrid]
    uv run python -m scripts.scaffold mcp <id>
    uv run python -m scripts.scaffold spec <team_id> "<title>"
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TEAMS_DIR = REPO_ROOT / "teams"
MCP_DIR = REPO_ROOT / "mcp-servers"
TEAM_TEMPLATE = TEAMS_DIR / "_template"
MCP_TEMPLATE = MCP_DIR / "_template"


def _slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\-_\s]", "", text)
    text = re.sub(r"\s+", "-", text).strip("-")
    return text.lower()


def _render_template_tree(src: Path, dst: Path, subst: dict[str, str]) -> None:
    """Copy src → dst, replacing {VAR} tokens in text files."""
    if dst.exists():
        raise FileExistsError(f"Target exists: {dst}")
    shutil.copytree(src, dst)
    for p in dst.rglob("*"):
        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            new_text = text
            for k, v in subst.items():
                new_text = new_text.replace("{" + k + "}", v)
            if new_text != text:
                p.write_text(new_text, encoding="utf-8")


def scaffold_team(team_id: str, runtime: str = "rule") -> None:
    target = TEAMS_DIR / team_id
    subst = {
        "TEAM_ID": team_id,
        "TEAM_NAME": team_id.replace("-", " ").title(),
    }
    _render_template_tree(TEAM_TEMPLATE, target, subst)

    # Fix manifest.yaml runtime
    mf = target / "manifest.yaml"
    text = mf.read_text(encoding="utf-8")
    text = re.sub(r"^runtime:.*$", f"runtime: {runtime}", text, count=1, flags=re.MULTILINE)
    mf.write_text(text, encoding="utf-8")

    # Rename template SPEC file prefix
    prefix = team_id.upper().replace("-", "_")
    template_spec = target / "specs" / "TEMPLATE-000-bootstrap.md"
    if template_spec.exists():
        new_name = template_spec.parent / f"{prefix}-000-bootstrap.md"
        template_spec.rename(new_name)
        # Update frontmatter spec_id and PREFIX inside
        content = new_name.read_text(encoding="utf-8")
        content = content.replace("TEMPLATE-000", f"{prefix}-000")
        content = content.replace("{PREFIX}", prefix)
        new_name.write_text(content, encoding="utf-8")

    print(f"✓ Scaffolded teams/{team_id} (runtime={runtime})")


def scaffold_mcp(mcp_id: str) -> None:
    target = MCP_DIR / mcp_id
    subst = {"MCP_ID": mcp_id, "MCP_NAME": mcp_id.replace("-", " ").title()}
    _render_template_tree(MCP_TEMPLATE, target, subst)
    print(f"✓ Scaffolded mcp-servers/{mcp_id}")


def scaffold_spec(team_id: str, title: str) -> None:
    team_dir = TEAMS_DIR / team_id
    if not team_dir.exists():
        raise SystemExit(f"Team not found: {team_id}")
    specs_dir = team_dir / "specs"
    specs_dir.mkdir(exist_ok=True)
    prefix = team_id.upper().replace("-", "_")
    existing = sorted(specs_dir.glob(f"{prefix}-*.md"))
    numbers = []
    for p in existing:
        m = re.match(rf"{prefix}-(\d+)-.*\.md", p.name)
        if m:
            numbers.append(int(m.group(1)))
    next_num = max(numbers + [0]) + 1
    slug = _slugify(title)
    spec_id = f"{prefix}-{next_num:03d}"
    filename = specs_dir / f"{spec_id}-{slug}.md"
    content = f"""---
spec_id: {spec_id}
title: {title}
team: {team_id}
type: feature
status: draft
generates: []
modifies: []
depends_on: []
contracts:
  - contract: team-output-v1
---

# {spec_id}: {title}

## 목적
(무엇을, 왜)

## 입력
- (데이터 소스)

## 출력
- `team_outputs` 테이블 (StandardOutput)

## 판단 로직
<!-- SPEC:INTERVIEW-SLOT role="judgment-logic" -->
(이 영역은 /spec-interview 로 채워집니다)

## 엣지 케이스
<!-- SPEC:INTERVIEW-SLOT role="edge-cases" -->

## 완료 기준
- [ ] 테스트 통과
- [ ] `just validate` 통과
- [ ] 도메인 문서 생성
"""
    filename.write_text(content, encoding="utf-8")
    print(f"✓ Created {filename}")


def main() -> None:
    parser = argparse.ArgumentParser(description="wevelStock scaffolder")
    sub = parser.add_subparsers(dest="kind", required=True)

    p_team = sub.add_parser("team", help="Create a new team")
    p_team.add_argument("id")
    p_team.add_argument("--runtime", default="rule", choices=["rule", "llm", "hybrid"])

    p_mcp = sub.add_parser("mcp", help="Create a new MCP server")
    p_mcp.add_argument("id")

    p_spec = sub.add_parser("spec", help="Create a new SPEC file")
    p_spec.add_argument("team_id")
    p_spec.add_argument("title")

    args = parser.parse_args()
    if args.kind == "team":
        scaffold_team(args.id, args.runtime)
    elif args.kind == "mcp":
        scaffold_mcp(args.id)
    elif args.kind == "spec":
        scaffold_spec(args.team_id, args.title)


if __name__ == "__main__":
    main()
