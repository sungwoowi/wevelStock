"""전략가와 멀티턴 대화 (REPL).

Usage:
    uv run python -m scripts.chat_strategist <strategist_id> [--target <ticker>] [--provider gemini|claude_code]
    just chat-strategist <strategist_id> [--target 005930] [--provider claude_code]

명령:
    /exit  또는 Ctrl+D  종료 (대화가 비어있지 않으면 JSONL 자동 저장)
    /clear              messages 배열 비움 (system canon/persona/RAG/scores 는 유지)
    /save               즉시 강제 저장 (종료 안 함)
    /target <ticker>    대화 중 target 변경 (다음 turn 부터 분석가 점수 재조회)

provider 와 target 은 conversation 단위 락 — `/target` 명령으로만 변경. 둘 다 비교 시
새 세션 시작.

JSONL 보관 위치: data/strategist_queries/<strategist_id>/<YYYYMMDD-HHMMSS>.jsonl
한 파일 = 한 conversation, 한 줄 = 한 turn (user + assistant + metadata + target).
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
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


def _strip_surrogates(text: str) -> str:
    return text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


REPO_ROOT = Path(__file__).resolve().parents[1]
QUERIES_DIR = REPO_ROOT / "data" / "strategist_queries"
CONTEXT_LIMIT_TOKENS = 200_000


def _conv_path(strategist_id: str, started_at: datetime) -> Path:
    folder = QUERIES_DIR / strategist_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{started_at.strftime('%Y%m%d-%H%M%S')}.jsonl"


def _save_turn(path: Path, turn_record: dict) -> None:
    payload = json.dumps(turn_record, ensure_ascii=False)
    payload = _strip_surrogates(payload)
    with path.open("a", encoding="utf-8") as f:
        f.write(payload + "\n")


def _format_metadata(meta: dict, cumulative_in: int, cumulative_out: int) -> str:
    cum_total = cumulative_in + cumulative_out
    cache_read = meta.get("cache_read_tokens", 0)
    cache_creation = meta.get("cache_creation_tokens", 0)
    cache_label = "miss"
    if cache_read > 0:
        cache_label = f"hit (read {cache_read:,})"
    elif cache_creation > 0:
        cache_label = f"created ({cache_creation:,})"
    cost = meta.get("cost_usd", 0.0)
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
        f"turn tokens {meta['tokens_in']:,}/{meta['tokens_out']:,} · "
        f"cumulative {cum_total:,}/{CONTEXT_LIMIT_TOKENS:,} · "
        f"cost ${cost:.4f} · "
        f"{meta['latency_s']:.1f}s · "
        f"{meta['model']}"
    )
    if meta.get("is_mock"):
        line += "  ⚠ MOCK"
    if meta.get("upstream_error"):
        line += f"\n  [upstream error] {meta['upstream_error']}"
    return line


def _read_user_input() -> str | None:
    try:
        line = input("> ")
    except EOFError:
        return None
    return _strip_surrogates(line)


async def _chat_loop(
    strategist_id: str,
    *,
    target: str = "global",
    provider: str | None = None,
) -> int:
    started_at = datetime.now()
    path = _conv_path(strategist_id, started_at)

    print(
        f"=== chat with {strategist_id} (target={target}, provider={provider or 'auto'}) ==="
    )
    print(f"saving to: {path.relative_to(REPO_ROOT)}")
    print("commands: /exit, /clear, /save, /target <ticker>\n")

    messages: list[dict] = []
    turn = 0
    cumulative_in = 0
    cumulative_out = 0

    while True:
        line = _read_user_input()
        if line is None:
            print("\n(EOF — 종료)")
            break

        stripped = line.strip()
        if not stripped:
            continue

        if stripped == "/exit":
            print("(/exit — 종료)")
            break
        if stripped == "/clear":
            messages = []
            print(
                f"(messages 리셋. 누적 토큰은 유지: {cumulative_in:,}/{cumulative_out:,})"
            )
            continue
        if stripped == "/save":
            print(f"(현재까지 {turn} turn 저장됨: {path.relative_to(REPO_ROOT)})")
            continue
        if stripped.startswith("/target "):
            new_target = stripped.split(" ", 1)[1].strip()
            if new_target:
                target = new_target
                print(f"(target 변경 → {target}. 다음 turn 부터 분석가 점수 재조회)")
            else:
                print(f"(target 인자 부재. 현재 target={target} 유지)")
            continue

        messages.append({"role": "user", "content": stripped})
        try:
            resp = await run_strategist(
                strategist_id, messages, target=target, provider=provider
            )
        except StrategistNotFoundError as e:
            print(f"[error] {e}")
            messages.pop()
            return 2
        except Exception as e:  # noqa: BLE001
            print(f"[error] LLM 호출 실패 (provider={provider or 'auto'}): {e}")
            messages.pop()
            continue

        assistant_text = resp.text or "(empty response)"
        messages.append({"role": "assistant", "content": assistant_text})
        turn += 1
        cumulative_in += int(resp.metadata.get("tokens_in", 0))
        cumulative_out += int(resp.metadata.get("tokens_out", 0))

        print()
        print(assistant_text)
        print()
        print(_format_metadata(resp.metadata, cumulative_in, cumulative_out))
        print()

        _save_turn(
            path,
            {
                "turn": turn,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "user": stripped,
                "target": target,
                "assistant": assistant_text,
                "metadata": resp.metadata,
            },
        )

    if turn == 0 and path.exists() and path.stat().st_size == 0:
        path.unlink()
        print("(빈 대화 — 파일 삭제)")
    elif turn > 0:
        print(
            f"\nsaved: {path.relative_to(REPO_ROOT)} ({turn} turn{'s' if turn != 1 else ''}, "
            f"cumulative {cumulative_in + cumulative_out:,} tokens)"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="chat_strategist",
        description="전략가와 멀티턴 REPL 대화. provider·target 은 conversation 단위 락 (/target 명령으로 중 변경 가능).",
    )
    parser.add_argument(
        "strategist_id", help="agents/strategists/<id>/ 디렉토리명 (예: track_a)"
    )
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
    try:
        return asyncio.run(
            _chat_loop(
                args.strategist_id, target=args.target, provider=args.provider
            )
        )
    except KeyboardInterrupt:
        print("\n(KeyboardInterrupt — 종료)")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
