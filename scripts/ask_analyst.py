"""분석가에 일회성 단발 질문 (CLI).

Usage:
    uv run python -m scripts.ask_analyst <analyst_id> "<질문>"
    just ask <analyst_id> "<질문>"

chat_analyst 의 단일 턴 wrap. JSONL 1 turn 저장 + stdout 응답 + metadata.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from core.inference import AnalystNotFoundError, run_analyst  # type: ignore[attr-defined]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


REPO_ROOT = Path(__file__).resolve().parents[1]
QUERIES_DIR = REPO_ROOT / "data" / "analyst_queries"


def _format_metadata(meta: dict) -> str:
    cache_read = meta.get("cache_read_tokens", 0)
    cache_creation = meta.get("cache_creation_tokens", 0)
    cache_label = "miss"
    if cache_read > 0:
        cache_label = f"hit (read {cache_read:,})"
    elif cache_creation > 0:
        cache_label = f"created ({cache_creation:,})"
    line = (
        f"  [meta] prompt {meta['system_prompt_chars']:,} chars · "
        f"RAG {meta['rag_chunks_returned']} chunks · "
        f"cache {cache_label} · "
        f"tokens {meta['tokens_in']:,}/{meta['tokens_out']:,} · "
        f"cost ${meta.get('cost_usd', 0.0):.4f} · "
        f"{meta['latency_s']:.1f}s · "
        f"{meta['model']}"
    )
    if meta.get("is_mock"):
        line += "  ⚠ MOCK"
    if meta.get("upstream_error"):
        line += f"\n  [upstream error] {meta['upstream_error']}"
    return line


async def _ask(analyst_id: str, query: str) -> int:
    started_at = datetime.now()
    folder = QUERIES_DIR / analyst_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{started_at.strftime('%Y%m%d-%H%M%S')}.jsonl"

    try:
        resp = await run_analyst(analyst_id, [{"role": "user", "content": query}])
    except AnalystNotFoundError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2

    print(resp.text or "(empty response)")
    print()
    print(_format_metadata(resp.metadata))

    with path.open("w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "turn": 1,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "user": query,
                    "assistant": resp.text,
                    "metadata": resp.metadata,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    print(f"\nsaved: {path.relative_to(REPO_ROOT)}")
    return 0


def main() -> int:
    if len(sys.argv) < 3:
        print(
            'usage: python -m scripts.ask_analyst <analyst_id> "<query>"',
            file=sys.stderr,
        )
        return 2
    analyst_id = sys.argv[1]
    query = " ".join(sys.argv[2:])
    return asyncio.run(_ask(analyst_id, query))


if __name__ == "__main__":
    raise SystemExit(main())
