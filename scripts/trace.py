"""Generate docs/traceability.md — bidirectional SPEC ↔ code mapping.

Usage:
    just trace
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from core.contracts.spec_frontmatter import find_all_specs, parse_spec

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "docs" / "traceability.md"


def main() -> None:
    specs = find_all_specs(REPO_ROOT)
    spec_to_files: dict[str, list[str]] = {}
    file_to_specs: dict[str, list[str]] = defaultdict(list)

    for path in specs:
        try:
            parsed = parse_spec(path)
        except Exception:
            continue
        spec_id = parsed.meta.spec_id
        files = parsed.meta.generates + parsed.meta.modifies
        spec_to_files[spec_id] = files
        for f in files:
            file_to_specs[f].append(spec_id)

    lines: list[str] = []
    lines.append("# SPEC ↔ Code Traceability")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")

    lines.append("## SPEC → Files")
    for spec_id in sorted(spec_to_files):
        files = spec_to_files[spec_id]
        lines.append(f"### {spec_id}")
        if not files:
            lines.append("- (no generates/modifies declared)")
        for f in files:
            exists = "✅" if (REPO_ROOT / f).exists() else "❌"
            lines.append(f"- {exists} `{f}`")
        lines.append("")

    lines.append("## File → SPECs")
    for f in sorted(file_to_specs):
        exists = "✅" if (REPO_ROOT / f).exists() else "❌"
        lines.append(f"- {exists} `{f}` ← " + ", ".join(file_to_specs[f]))
    lines.append("")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
