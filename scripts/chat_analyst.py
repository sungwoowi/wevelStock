"""분석가와 멀티턴 대화 (REPL).

Usage:
    uv run python -m scripts.chat_analyst <analyst_id> [--provider gemini|claude_code]
    just chat <analyst_id> [--provider claude_code]

명령:
    /exit  또는 Ctrl+D  종료 (대화가 비어있지 않으면 JSONL 자동 저장)
    /clear              messages 배열 비움 (system canon/persona/RAG 는 유지)
    /save               즉시 강제 저장 (종료 안 함)

provider 는 conversation 단위 락. 다른 backend 비교하려면 새 chat 세션 시작.
JSONL 보관 위치: data/analyst_queries/<analyst_id>/<YYYYMMDD-HHMMSS>.jsonl
한 파일 = 한 conversation, 한 줄 = 한 turn (user + assistant + metadata).

INFRA-RUNTIME-EFFICIENCY-001 (a) 후: in-process `run_analyst` 가 아니라
`WEVELSTOCK_SERVER_URL` (default `http://127.0.0.1:8000`) 의
`POST /api/analysts/{id}/chat` 으로 HTTP 호출. 서버 안 BGE-m3 1 회 로딩 재사용.
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
REQUEST_TIMEOUT_SECONDS = 180.0


def _server_base_url() -> str:
    return os.environ.get("WEVELSTOCK_SERVER_URL", "http://127.0.0.1:8000").rstrip("/")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


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
    provider_used = meta.get("provider_used") or "auto"
    provider_requested = meta.get("provider_requested")
    provider_label = f"[{provider_used}]"
    if provider_requested and provider_requested != provider_used:
        provider_label = f"[{provider_used} ← req:{provider_requested}]"
    line = (
        f"  [meta] {provider_label} · "
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
    """공백 줄·EOF 구분. 사용자가 빈 줄만 누르면 다시 prompt."""
    try:
        line = input("> ")
    except EOFError:
        return None
    return _strip_surrogates(line)


async def _post_chat(
    client: httpx.AsyncClient,
    analyst_id: str,
    messages: list[dict],
    *,
    provider: str | None,
) -> tuple[int, dict]:
    """server 호출. 반환 = (status_code, body_dict)."""
    base_url = _server_base_url()
    url = f"{base_url}/api/analysts/{analyst_id}/chat"
    payload: dict = {"messages": messages, "include_memory": True}
    if provider:
        payload["provider"] = provider
    resp = await client.post(url, json=payload)
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        body = {"raw": resp.text}
    return resp.status_code, body


async def _chat_loop(analyst_id: str, *, provider: str | None = None) -> int:
    started_at = datetime.now()
    path = _conv_path(analyst_id, started_at)
    base_url = _server_base_url()

    print(f"=== chat with {analyst_id} (provider={provider or 'auto'}, server={base_url}) ===")
    print(f"saving to: {_display_path(path)}")
    print("commands: /exit, /clear, /save\n")

    messages: list[dict] = []
    turn = 0
    cumulative_in = 0
    cumulative_out = 0

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
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
                print(f"(현재까지 {turn} turn 저장됨: {_display_path(path)})")
                continue

            messages.append({"role": "user", "content": stripped})

            try:
                status, body = await _post_chat(
                    client, analyst_id, messages, provider=provider
                )
            except httpx.ConnectError:
                print(
                    f"[error] WevelStock 서버에 연결할 수 없습니다 ({base_url}).\n"
                    f"        다른 터미널에서 'just server' 실행 후 다시 시도하세요."
                )
                messages.pop()
                return 3
            except httpx.ReadTimeout:
                print(
                    f"[error] 응답 대기 시간 초과 ({REQUEST_TIMEOUT_SECONDS:.0f}s). "
                    f"서버가 BGE-m3 로딩 중일 수 있습니다."
                )
                messages.pop()
                continue

            if status == 404:
                detail = body.get("detail", str(body))
                print(f"[error] {detail}")
                messages.pop()
                return 2
            if status != 200:
                detail = body.get("detail", str(body))
                print(f"[error] LLM 호출 실패 (status {status}, provider={provider or 'auto'}): {detail}")
                messages.pop()
                continue

            assistant_text = body.get("text", "") or "(empty response)"
            metadata = body.get("metadata", {})
            messages.append({"role": "assistant", "content": assistant_text})
            turn += 1
            cumulative_in += int(metadata.get("tokens_in", 0))
            cumulative_out += int(metadata.get("tokens_out", 0))

            print()
            print(assistant_text)
            print()
            print(_format_metadata(metadata, cumulative_in, cumulative_out))
            print()

            _save_turn(
                path,
                {
                    "turn": turn,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "user": stripped,
                    "assistant": assistant_text,
                    "metadata": metadata,
                },
            )

    if turn == 0 and path.exists() and path.stat().st_size == 0:
        path.unlink()
        print("(빈 대화 — 파일 삭제)")
    elif turn > 0:
        print(
            f"\nsaved: {_display_path(path)} ({turn} turn{'s' if turn != 1 else ''}, "
            f"cumulative {cumulative_in + cumulative_out:,} tokens)"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="chat_analyst",
        description="분석가와 멀티턴 REPL 대화 (server 경유). provider 는 conversation 단위 락.",
    )
    parser.add_argument("analyst_id", help="agents/analysts/<id>/ 디렉토리명")
    parser.add_argument(
        "--provider",
        choices=PROVIDER_CHOICES,
        default=None,
        help="LLM backend 강제 지정 (auto fallback X). None=runtime.yaml 기본 + 자동 폴백",
    )
    args = parser.parse_args()
    try:
        return asyncio.run(_chat_loop(args.analyst_id, provider=args.provider))
    except KeyboardInterrupt:
        print("\n(KeyboardInterrupt — 종료)")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
