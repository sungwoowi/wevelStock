"""Structural validation — runs every project convention check.

Usage:
    just validate

Exit code non-zero if any check fails.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import yaml

from core.contracts.spec_frontmatter import find_all_specs, parse_spec
from core.registry import TEAMS_DIR, list_all_teams, refresh_registry_file

REPO_ROOT = Path(__file__).resolve().parents[1]


class Issue:
    def __init__(self, severity: str, where: str, message: str) -> None:
        self.severity = severity  # error | warning
        self.where = where
        self.message = message

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.where}: {self.message}"


def check_team_layout(issues: list[Issue]) -> None:
    """Each team must have CLAUDE.md, manifest.yaml, src/agent.py, tests/test_agent.py."""
    required = {
        "CLAUDE.md": True,
        "manifest.yaml": True,
        "src/agent.py": True,
        "tests/test_agent.py": True,
        "CHANGELOG.md": False,  # warning if missing
    }
    for team in list_all_teams():
        if team.path is None:
            issues.append(Issue("error", team.id, "team path not set"))
            continue
        for rel, must in required.items():
            if not (team.path / rel).exists():
                sev = "error" if must else "warning"
                issues.append(Issue(sev, f"teams/{team.id}", f"missing {rel}"))


def check_no_cross_team_imports(issues: list[Issue]) -> None:
    """AST scan: teams/<X>/src/** must not import teams.<Y> (X != Y)."""
    for team in list_all_teams():
        if team.path is None:
            continue
        src = team.path / "src"
        if not src.exists():
            continue
        for py in src.rglob("*.py"):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"))
            except SyntaxError:
                issues.append(Issue("error", str(py), "syntax error"))
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    mod = node.module
                    if mod.startswith("teams.") and not mod.startswith(f"teams.{team.id}."):
                        # allow teams.<self>.xxx only
                        issues.append(Issue(
                            "error",
                            str(py),
                            f"forbidden cross-team import: {mod}",
                        ))
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod = alias.name
                        if mod.startswith("teams.") and not mod.startswith(f"teams.{team.id}"):
                            issues.append(Issue(
                                "error",
                                str(py),
                                f"forbidden cross-team import: {mod}",
                            ))


def check_specs(issues: list[Issue]) -> None:
    """All SPECs must parse and their `generates` files must exist when implemented."""
    for path in find_all_specs(REPO_ROOT):
        try:
            parsed = parse_spec(path)
        except Exception as e:  # noqa: BLE001
            issues.append(Issue("error", str(path), f"spec parse failed: {e}"))
            continue
        if parsed.meta.status in ("implemented", "verified"):
            for gen in parsed.meta.generates:
                p = REPO_ROOT / gen
                if not p.exists():
                    issues.append(Issue(
                        "error",
                        str(path),
                        f"status={parsed.meta.status} but generates file missing: {gen}",
                    ))


def check_registry(issues: list[Issue]) -> None:
    """teams/registry.yaml must reflect filesystem."""
    reg_path = TEAMS_DIR / "registry.yaml"
    if not reg_path.exists():
        issues.append(Issue("warning", "teams/registry.yaml", "missing (run validate to regenerate)"))
        return
    try:
        data = yaml.safe_load(reg_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        issues.append(Issue("error", "teams/registry.yaml", f"YAML error: {e}"))
        return
    declared = {t["id"] for t in (data.get("teams") or [])}
    actual = {t.id for t in list_all_teams()}
    missing = actual - declared
    extra = declared - actual
    if missing:
        issues.append(Issue("warning", "teams/registry.yaml", f"missing teams: {missing}"))
    if extra:
        issues.append(Issue("warning", "teams/registry.yaml", f"stale teams: {extra}"))


def main() -> int:
    issues: list[Issue] = []
    check_team_layout(issues)
    check_no_cross_team_imports(issues)
    check_specs(issues)
    check_registry(issues)

    # Refresh registry file (always)
    try:
        refresh_registry_file()
    except Exception as e:  # noqa: BLE001
        issues.append(Issue("warning", "registry refresh", str(e)))

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    for i in issues:
        print(i)

    print()
    print(f"✓ {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
