"""Generate a user-facing domain document from a SPEC + its generated code + tests.

Usage:
    just domain-doc PRINCIPLE-001
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
from pathlib import Path

from core.contracts.spec_frontmatter import find_all_specs, parse_spec

REPO_ROOT = Path(__file__).resolve().parents[1]
DOMAIN_DIR = REPO_ROOT / "docs" / "domain"


def _find_spec(spec_id: str):
    for path in find_all_specs(REPO_ROOT):
        parsed = parse_spec(path)
        if parsed.meta.spec_id == spec_id:
            return parsed
    raise SystemExit(f"SPEC not found: {spec_id}")


def _extract_docstrings(py_path: Path) -> list[tuple[str, str]]:
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    out: list[tuple[str, str]] = []
    mod_doc = ast.get_docstring(tree)
    if mod_doc:
        out.append((f"{py_path.name} (module)", mod_doc))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node)
            if doc:
                out.append((f"{py_path.name}::{node.name}", doc))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec_id")
    args = parser.parse_args()

    parsed = _find_spec(args.spec_id)
    meta = parsed.meta

    # Determine domain file path — group by team
    team_slug = meta.team
    topic_slug = args.spec_id.lower()
    out_path = DOMAIN_DIR / team_slug / f"{topic_slug}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append(f"# {meta.title}")
    lines.append("")
    lines.append(f"> 이 문서는 {meta.spec_id} 구현에 대한 **사용자용 설명서**입니다.")
    lines.append(f"> 자동 생성 시각: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append(f"- **팀**: `{meta.team}`")
    lines.append(f"- **상태**: `{meta.status}`")
    lines.append(f"- **타입**: `{meta.type}`")
    lines.append("")

    # SPEC body (excluding frontmatter)
    lines.append("## SPEC 요약")
    lines.append("")
    lines.append(parsed.body.strip())
    lines.append("")

    # Generated files + docstrings
    lines.append("## 구현 파일과 설명")
    for rel in meta.generates:
        p = REPO_ROOT / rel
        if not p.exists():
            lines.append(f"- ❌ `{rel}` (아직 생성되지 않음)")
            continue
        lines.append(f"### `{rel}`")
        if p.suffix == ".py":
            docs = _extract_docstrings(p)
            for where, doc in docs:
                lines.append(f"**{where}**")
                lines.append("")
                lines.append("> " + doc.strip().replace("\n", "\n> "))
                lines.append("")
        else:
            lines.append(f"(비-Python 파일, 경로만 기록)")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ Domain doc written: {out_path}")


if __name__ == "__main__":
    main()
