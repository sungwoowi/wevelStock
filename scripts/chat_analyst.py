"""분석가와 멀티턴 대화 (REPL).

Usage:
    uv run python -m scripts.chat_analyst <analyst_id>
    just chat <analyst_id>

명령:
    /exit  또는 Ctrl+D  종료 (대화가 비어있지 않으면 JSONL 자동 저장)
    /clear              messages 배열 비움 (system canon/persona/RAG 는 유지)
    /save               즉시 강제 저장 (종료 안 함)

JSONL 보관 위치: data/analyst_queries/<analyst_id>/<YYYYMMDD-HHMMSS>.jsonl
한 파일 = 한 conversation, 한 줄 = 한 turn (user + assistant + metadata).
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from core.inference import AnalystNotFoundError, run_analyst  # type: ignore[attr-defined]

# Windows 콘솔 cp949 함정 회피 — R3 의 scripts/knowledge.py 패턴 그대로.
# stdin 도 utf-8 강제 (사용자가 콘솔에서 한국어 직접 입력 시 필수).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


def _strip_surrogates(text: str) -> str:
    """Surrogate 가 남으면 utf-8 인코딩 실패. 안전하게 제거."""
    return text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


REPO_ROOT = Path(__file__).resolve().parents[1]
QUERIES_DIR = REPO_ROOT / "data" / "analyst_queries"
CONTEXT_LIMIT_TOKENS = 200_000  # Sonnet 4.6 기본. Opus 1M 모델 사용 시 사용자가 의식하면 됨.


def _conv_path(analyst_id: str, started_at: datetime) -> Path:
    folder = QUERIES_DIR / analyst_id
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
    line = (
        f"  [meta] prompt {meta['system_prompt_chars']:,} chars · "
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
    """공백 줄·EOF 구분. 사용자가 빈 줄만 누르면 다시 prompt."""
    try:
        line = input("> ")
    except EOFError:
        return None
    return _strip_surrogates(line)


async def _chat_loop(analyst_id: str) -> int:
    started_at = datetime.now()
    path = _conv_path(analyst_id, started_at)

    print(f"=== chat with {analyst_id} ===")
    print(f"saving to: {path.relative_to(REPO_ROOT)}")
    print("commands: /exit, /clear, /save\n")

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
            print(f"(messages 리셋. 누적 토큰은 유지: {cumulative_in:,}/{cumulative_out:,})")
            continue
        if stripped == "/save":
            print(f"(현재까지 {turn} turn 저장됨: {path.relative_to(REPO_ROOT)})")
            continue

        messages.append({"role": "user", "content": stripped})
        try:
            resp = await run_analyst(analyst_id, messages)
        except AnalystNotFoundError as e:
            print(f"[error] {e}")
            messages.pop()  # 실패한 user 메시지 롤백
            return 2
        except Exception as e:  # noqa: BLE001
            print(f"[error] LLM 호출 실패: {e}")
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
    if len(sys.argv) < 2:
        print("usage: python -m scripts.chat_analyst <analyst_id>", file=sys.stderr)
        return 2
    analyst_id = sys.argv[1]
    try:
        return asyncio.run(_chat_loop(analyst_id))
    except KeyboardInterrupt:
        print("\n(KeyboardInterrupt — 종료)")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
