"""전략가에 일회성 단발 질문 (CLI).

Usage:
    uv run python -m scripts.ask_strategist <strategist_id> "<질문>" [--target <ticker>] [--provider gemini|claude_code]
    just ask-strategist <strategist_id> "<질문>" [--target 005930] [--provider claude_code]

전략가는 분석가와 달리 `--target` 인자 받음 (종목별 권고). 기본 = "global".

INFRA-RUNTIME-EFFICIENCY-001 v3 patch (cycle 7): CLI 는 in-process
`run_strategist` 가 아니라 `WEVELSTOCK_SERVER_URL` (default `http://127.0.0.1:8000`)
의 `POST /api/strategists/{id}/chat` 으로 HTTP 호출. 서버 프로세스 안에서
BGE-m3 ~2.5GB 모델이 1 회 로딩되고 매 호출 재사용된다. 서버 부재 시 명확한 에러.
ask_analyst 패턴 (cycle 4) 1:1 미러.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx

PROVIDER_CHOICES = ["gemini", "claude_code", "anthropic", "mock"]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


REPO_ROOT = Path(__file__).resolve().parents[1]
QUERIES_DIR = REPO_ROOT / "data" / "strategist_queries"
REQUEST_TIMEOUT_SECONDS = 180.0  # BGE-m3 cold 로딩 + LLM 호출 + 분석가 점수 조회 합 여유


def _server_base_url() -> str:
    return os.environ.get("WEVELSTOCK_SERVER_URL", "http://127.0.0.1:8000").rstrip("/")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


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

    base_url = _server_base_url()
    url = f"{base_url}/api/strategists/{strategist_id}/chat"
    payload: dict = {
        "messages": [{"role": "user", "content": query}],
        "target": target,
        "include_memory": True,
    }
    if provider:
        payload["provider"] = provider

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json=payload)
    except httpx.ConnectError:
        print(
            f"[error] WevelStock 서버에 연결할 수 없습니다 ({base_url}).\n"
            f"        다른 터미널에서 'just server' 실행 후 다시 시도하세요.",
            file=sys.stderr,
        )
        return 3
    except httpx.ReadTimeout:
        print(
            f"[error] 응답 대기 시간 초과 ({REQUEST_TIMEOUT_SECONDS:.0f}s). "
            f"서버가 BGE-m3 로딩 중일 수 있습니다.",
            file=sys.stderr,
        )
        return 4

    if resp.status_code == 404:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:  # noqa: BLE001
            detail = resp.text
        print(f"[error] {detail}", file=sys.stderr)
        return 2
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:  # noqa: BLE001
            detail = resp.text
        print(
            f"[error] LLM 호출 실패 (status {resp.status_code}, provider={provider or 'auto'}): {detail}",
            file=sys.stderr,
        )
        return 1

    body = resp.json()
    text = body.get("text", "") or "(empty response)"
    metadata = body.get("metadata", {})

    print(text)
    print()
    print(_format_metadata(metadata))

    with path.open("w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "turn": 1,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "user": query,
                    "target": target,
                    "assistant": text,
                    "metadata": metadata,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    print(f"\nsaved: {_display_path(path)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="ask_strategist",
        description="전략가에 일회성 단발 질문 (server 경유)",
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
