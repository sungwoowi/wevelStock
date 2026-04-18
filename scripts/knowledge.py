"""Knowledge-base CLI: ingest / compile / status / browse.

Usage:
    just knowledge-ingest <team>
    just knowledge-compile <team>
    just knowledge-status <team>
    just knowledge-browse <team> "<query>"
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from core.knowledge.ingest import ingest_team
from core.knowledge.retrieve import retrieve
from core.registry import get_team

REPO_ROOT = Path(__file__).resolve().parents[1]


async def _status(team_id: str) -> None:
    team = get_team(team_id)
    if team is None or team.path is None:
        print(f"❌ team not found: {team_id}")
        return
    sources = team.path / "knowledge" / "sources"
    canon = team.path / "knowledge" / "compiled.md"
    index = team.path / "knowledge" / "vector-index"
    source_count = sum(1 for _ in sources.rglob("*")) if sources.exists() else 0
    print(f"Team: {team_id}")
    print(f"  sources dir  : {sources}  ({source_count} entries)")
    print(f"  canon        : {canon}  ({'present' if canon.exists() else 'absent'})")
    print(f"  index        : {index}  ({'present' if index.exists() and any(index.iterdir()) else 'empty'})")


async def _compile(team_id: str) -> None:
    """Minimal canon compile — concatenates all sources into compiled.md.

    For richer LLM-based compilation, extend this later (see FOUNDATION-PLAN).
    """
    team = get_team(team_id)
    if team is None or team.path is None:
        print(f"❌ team not found: {team_id}")
        return
    sources = team.path / "knowledge" / "sources"
    canon_path = team.path / "knowledge" / "compiled.md"
    if not sources.exists():
        print(f"❌ sources dir missing: {sources}")
        return

    parts: list[str] = [f"# {team_id} — Canon (auto-compiled)\n"]
    for p in sorted(sources.rglob("*.md")):
        parts.append(f"\n## from {p.relative_to(sources)}\n")
        parts.append(p.read_text(encoding="utf-8").strip())
    canon_path.write_text("\n".join(parts), encoding="utf-8")
    print(f"✓ Canon written: {canon_path}")


async def _browse(team_id: str, query: str) -> None:
    results = await retrieve(team_id, query, top_k=5)
    if not results:
        print("(no results — index empty or chroma unavailable)")
        return
    for i, r in enumerate(results, 1):
        print(f"\n[{i}] score={r.score:.3f}  source={r.chunk.source_title or r.chunk.source_id}")
        print(r.chunk.text[:300])


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_in = sub.add_parser("ingest"); p_in.add_argument("team")
    p_cm = sub.add_parser("compile"); p_cm.add_argument("team")
    p_st = sub.add_parser("status"); p_st.add_argument("team")
    p_br = sub.add_parser("browse"); p_br.add_argument("team"); p_br.add_argument("query")
    args = parser.parse_args()

    if args.cmd == "ingest":
        result = asyncio.run(ingest_team(args.team))
        print(result)
    elif args.cmd == "compile":
        asyncio.run(_compile(args.team))
    elif args.cmd == "status":
        asyncio.run(_status(args.team))
    elif args.cmd == "browse":
        asyncio.run(_browse(args.team, args.query))


if __name__ == "__main__":
    main()
