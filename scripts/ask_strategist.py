"""전략가에 일회성 단발 질문 (CLI).

Usage:
    uv run python -m scripts.ask_strategist <strategist_id> "<질문>" [--target <ticker>] [--provider gemini|claude_code]
    just ask-strategist <strategist_id> "<질문>" [--target 005930] [--provider claude_code]

chat_strategist 의 단일 턴 wrap. JSONL 1 turn 저장 + stdout 응답 + metadata.

전략가는 분석가와 달리 `--target` 인자 받음 (종목별 권고). 기본 = "global".
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from core.strategist import StrategistNotFoundError, run_strategist

PROVIDER_CHOICES = ["gemini", "claude_code", "anthropic", "mock"]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


REPO_ROOT = Path(__file__).resolve().parents[1]
QUERIES_DIR = REPO_ROOT / "data" / "strategist_queries"


def _format_metadata(meta: dict) -> str:
    cache_read = meta.get("cache_read_tokens", 0)
    cache_creation = meta.get("cache_creation_tokens", 0)
    cache_label = "miss"
    if cache_read > 0:
        cache_label = f"hit (read {cache_read:,})"
    elif cache_creation > 0:
        cache_label = f"created ({cache_creation:,})"
    provider_used = meta.get("provider_used") or "auto"
    provider_requested = meta.get("provider_requested")
    provider_label = f"[{provider_used}]"
    if provider_requested and provider_requested != provider_used:
        provider_label = f"[{provider_used} ← req:{provider_requested}]"

    published = meta.get("analyst_published_count", 0)
    missing = meta.get("analyst_missing_count", 0)
    total = published + missing
    scores_label = f"scores {published}/{total}"
    if missing > 0:
        missing_ids = meta.get("analyst_missing_ids") or []
        scores_label += f" (missing: {','.join(missing_ids)})"

    line = (
        f"  [meta] {provider_label} · "
        f"track {meta.get('track','?')} · "
        f"target {meta.get('target','global')} · "
        f"{scores_label} · "
        f"prompt {meta['system_prompt_chars']:,} chars · "
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


async def _ask(
    strategist_id: str,
    query: str,
    *,
    target: str = "global",
    provider: str | None = None,
) -> int:
    started_at = datetime.now()
    folder = QUERIES_DIR / strategist_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{started_at.strftime('%Y%m%d-%H%M%S')}.jsonl"

    try:
        resp = await run_strategist(
            strategist_id,
            [{"role": "user", "content": query}],
            target=target,
            provider=provider,
        )
    except StrategistNotFoundError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"[error] LLM 호출 실패 (provider={provider or 'auto'}): {e}", file=sys.stderr)
        return 1

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
                    "target": target,
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
    parser = argparse.ArgumentParser(
        prog="ask_strategist",
        description="전략가에 일회성 단발 질문",
    )
    parser.add_argument("strategist_id", help="agents/strategists/<id>/ 디렉토리명 (예: track_a)")
    parser.add_argument("query", nargs="+", help="질문 본문")
    parser.add_argument(
        "--target",
        default="global",
        help="team_outputs target. 종목 ticker (예: 005930) 또는 'global'. 기본=global",
    )
    parser.add_argument(
        "--provider",
        choices=PROVIDER_CHOICES,
        default=None,
        help="LLM backend 강제 지정 (auto fallback X). None=runtime.yaml 기본 + 자동 폴백",
    )
    args = parser.parse_args()
    query = " ".join(args.query)
    return asyncio.run(
        _ask(args.strategist_id, query, target=args.target, provider=args.provider)
    )


if __name__ == "__main__":
    raise SystemExit(main())
