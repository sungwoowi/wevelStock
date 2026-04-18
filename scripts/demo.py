"""E2E demo runner — runs orchestrator on a given scenario, prints result.

Usage:
    just demo over-allocation
    just demo normal
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from uuid import uuid4

# Force UTF-8 stdout on Windows (cp949 can't render emoji used by rich).
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from teams.orchestrator.src.agent import Agent as Orchestrator

console = Console(force_terminal=True, legacy_windows=False)


async def run_demo(scenario: str) -> None:
    run_id = f"{datetime.now(timezone.utc).isoformat()}#demo-{uuid4().hex[:8]}"
    console.print(Panel.fit(
        f"🚀 wevelStock Demo\nScenario: [bold]{scenario}[/bold]\nRun ID: {run_id}",
        border_style="cyan",
    ))

    orch = Orchestrator()
    output = await orch.run({"run_id": run_id, "scenario": scenario})

    console.print()
    console.print(Panel.fit(
        f"[bold]Orchestrator Verdict:[/bold] {output.verdict}  "
        f"(confidence {output.confidence})",
        border_style="green" if output.verdict in {"positive", "neutral"} else "yellow",
    ))

    console.print("\n[bold]Team results:[/bold]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Team", style="cyan")
    table.add_column("Verdict")
    table.add_column("Confidence", justify="right")
    table.add_column("Top reason")
    for team_id in output.data.get("teams_succeeded", []):
        from core.outputs import load_latest
        latest = load_latest(team_id)
        if latest:
            top = latest.reasons[0] if latest.reasons else ""
            table.add_row(team_id, latest.verdict, str(latest.confidence), top[:80])
    console.print(table)

    errors = output.data.get("teams_failed") or {}
    if errors:
        console.print("\n[bold red]Failures:[/bold red]")
        for team_id, err in errors.items():
            console.print(f"  {team_id}: {err[:200]}")

    console.print("\n[dim]Full output JSON:[/dim]")
    console.print(json.dumps(output.model_dump(), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", nargs="?", default="over-allocation")
    args = parser.parse_args()
    asyncio.run(run_demo(args.scenario))


if __name__ == "__main__":
    main()
