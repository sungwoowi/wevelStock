"""Claude Code CLI subprocess backend.

Spawns `claude --print --output-format json --system-prompt <...> <user prompt>`
and parses the JSON result. Uses the Claude Pro/Max subscription credentials
stored by Claude Code CLI (keychain / OS credential store), so no API key
is needed.

Trade-offs vs the direct Anthropic SDK backend:
  + Reuses Claude Pro/Max subscription (no separate billing).
  + No API key management in .env.
  - Slower first call (~1-3s subprocess startup).
  - No native prompt-cache breakpoint control (CLI manages its own caching).
  - Subject to subscription rate limits rather than token-based pricing.

Assumptions:
  - `claude` binary is on PATH.
  - User has authenticated previously via `claude setup-token` or interactive
    `/login`. (Without auth the CLI returns "Not logged in".)
"""
from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import subprocess
from typing import Any

from core.logging import get_logger

log = get_logger(__name__)


class ClaudeCodeNotInstalled(RuntimeError):
    """`claude` binary missing from PATH."""


class ClaudeCodeAuthError(RuntimeError):
    """User not logged into Claude Code CLI."""


def _blocks_to_text(system: list[dict] | str) -> str:
    """Flatten a list of system blocks into a single string for CLI use.

    Anthropic prompt-caching structure (list of blocks with cache_control) is
    meaningful only through the direct API. Here we simply concatenate.
    """
    if isinstance(system, str):
        return system
    parts: list[str] = []
    for block in system:
        text = block.get("text") if isinstance(block, dict) else None
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _messages_to_text(messages: list[dict]) -> str:
    """Collapse user/assistant turn history into a single prompt.

    Claude Code `--print` takes one prompt string. For single-turn (one user
    message) — the common case — we send the content verbatim so the LLM
    sees it as a natural question, not wrapped in a role marker.
    Multi-turn uses [ASSISTANT] / [USER] separators.
    """
    if not messages:
        return ""

    def _extract(content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                b.get("text", "") for b in content if isinstance(b, dict)
            )
        return str(content)

    if len(messages) == 1:
        return _extract(messages[0].get("content", ""))

    parts: list[str] = []
    for m in messages:
        role = m.get("role", "user").upper()
        parts.append(f"[{role}]\n{_extract(m.get('content', ''))}")
    return "\n\n".join(parts)


def _resolve_launcher(binary: str) -> list[str]:
    """Return argv prefix to spawn `binary` with asyncio.create_subprocess_exec.

    Windows npm global installs create three launchers — `claude`, `claude.cmd`,
    `claude.ps1` — and asyncio's CreateProcess cannot run `.cmd` directly.
    We resolve to the correct one and wrap .cmd/.bat with `cmd.exe /c`.
    """
    is_windows = platform.system() == "Windows"
    if is_windows:
        for suffix in (".cmd", ".exe", ".bat", ""):
            path = shutil.which(binary + suffix)
            if path:
                lower = path.lower()
                if lower.endswith((".cmd", ".bat")):
                    return ["cmd.exe", "/c", path]
                return [path]
    else:
        path = shutil.which(binary)
        if path:
            return [path]

    raise ClaudeCodeNotInstalled(
        f"`{binary}` not found in PATH. Install with "
        "`npm install -g @anthropic-ai/claude-code` or change "
        "config.llm.claude_code.binary."
    )


async def call_claude_code(
    *,
    system: list[dict] | str,
    messages: list[dict],
    model: str,
    max_tokens: int,  # noqa: ARG001  (CLI manages output length itself)
    temperature: float,  # noqa: ARG001  (not exposed by CLI)
    binary: str = "claude",
    timeout_sec: int = 90,
    extra_args: list[str] | None = None,
    json_schema: dict | None = None,
) -> dict:
    """Invoke Claude Code CLI and return the standard LLM response dict."""
    launcher = _resolve_launcher(binary)

    system_text = _blocks_to_text(system)
    user_text = _messages_to_text(messages)

    # Windows cmd.exe argv length limit is ~8,191 chars (CreateProcess is 32K).
    # Long system prompts (e.g. 5-Layer canon ≥ 19K chars) overflow argv and
    # cmd.exe rejects spawn with localized "입력이 너무 깁니다" / "command line
    # too long". We detect and fold system into the stdin payload using
    # [SYSTEM]/[USER] prefix — the model still sees the same content.
    is_windows = platform.system() == "Windows"
    cmdline_safe_limit = 7000  # conservative budget under 8191 incl. other args
    fold_system_into_stdin = is_windows and len(system_text) > cmdline_safe_limit

    args: list[str] = [
        *launcher,
        "--print",
        "--output-format", "json",
        "--input-format", "text",
        "--model", _normalize_model_alias(model),
        "--no-session-persistence",
    ]
    if system_text.strip() and not fold_system_into_stdin:
        args.extend(["--system-prompt", system_text])
    if json_schema is not None:
        args.extend(["--json-schema", json.dumps(json_schema, ensure_ascii=False)])
    if extra_args:
        args.extend(extra_args)

    if fold_system_into_stdin and system_text.strip():
        stdin_payload = f"[SYSTEM]\n{system_text}\n\n[USER]\n{user_text}"
    else:
        stdin_payload = user_text

    log.debug(
        "claude_code_spawn",
        argv_head=args[:6],
        system_chars=len(system_text),
        user_chars=len(user_text),
    )

    # Force keychain OAuth path: claude CLI prefers ANTHROPIC_API_KEY env var
    # over OAuth when both are present. Pro/Max subscription auth lives in the
    # OS keychain — strip the env var so claude falls through to it.
    # (User who genuinely wants API-key auth should use provider="anthropic".)
    sub_env = os.environ.copy()
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        sub_env.pop(key, None)

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=sub_env,
        )
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(input=stdin_payload.encode("utf-8")),
            timeout=timeout_sec,
        )
    except asyncio.TimeoutError as e:
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(f"claude_code timed out after {timeout_sec}s") from e
    except FileNotFoundError as e:
        raise ClaudeCodeNotInstalled(str(e)) from e

    stdout = stdout_b.decode("utf-8", errors="replace")
    stderr = stderr_b.decode("utf-8", errors="replace")

    if proc.returncode != 0:
        raise RuntimeError(
            f"claude_code exited {proc.returncode}: {stderr[:400] or stdout[:400]}"
        )

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"claude_code stdout is not valid JSON: {stdout[:400]}") from e

    if payload.get("is_error"):
        msg = payload.get("result") or "unknown error"
        if "not logged in" in msg.lower() or "login" in msg.lower():
            raise ClaudeCodeAuthError(
                f"Claude Code is not authenticated. Run `claude setup-token` first. Detail: {msg}"
            )
        raise RuntimeError(f"claude_code returned error: {msg}")

    content = str(payload.get("result", ""))
    usage = payload.get("usage") or {}
    total_cost = payload.get("total_cost_usd") or 0.0
    tokens_in = int(usage.get("input_tokens") or 0) + int(
        usage.get("cache_creation_input_tokens") or 0
    )
    tokens_out = int(usage.get("output_tokens") or 0)
    resolved_model = _resolve_reported_model(payload, model)

    return {
        "content": content,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "model": resolved_model,
        "cost_usd": float(total_cost),
        "raw": {
            "provider": "claude_code",
            "session_id": payload.get("session_id"),
            "stop_reason": payload.get("stop_reason"),
            "duration_ms": payload.get("duration_ms"),
            "usage": usage,
            "model_usage": payload.get("modelUsage", {}),
        },
    }


def _can_spawn_subprocess() -> bool:
    """현재 event loop 가 asyncio subprocess 를 지원하는지 사전 체크.

    Windows 의 SelectorEventLoop 는 `create_subprocess_exec` 호출 시
    NotImplementedError. ProactorEventLoop 는 지원. 사전에 알 수 있으니
    NotImplementedError 발생 자체를 회피하고 batch_thread 로 직행 → 시끄러운
    warning 도 안 띄움.
    """
    if platform.system() != "Windows":
        return True
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return True
    return "Selector" not in type(loop).__name__


async def call_claude_code_stream(
    *,
    system: list[dict] | str,
    messages: list[dict],
    model: str,
    max_tokens: int,
    temperature: float,
    binary: str = "claude",
    timeout_sec: int = 90,
    extra_args: list[str] | None = None,
):
    """Claude Code CLI streaming.

    환경별 동작:
        - ProactorEventLoop (CLI, asyncio default on Win Python 3.8+): native
          streaming. CLI 의 `--output-format stream-json --include-partial-messages`
          로 토큰 흘림.
        - SelectorEventLoop (uvicorn 의 일부 설정): subprocess 미지원이라 native
          시도 X. sync subprocess + asyncio.to_thread 의 batch_thread 로 직행 —
          응답 도착 시점에 단일 text_delta + metadata 로 emit (전체 한 번에 표시).
    """
    if _can_spawn_subprocess():
        async for ev in _claude_code_stream_native(
            system=system, messages=messages, model=model,
            max_tokens=max_tokens, temperature=temperature,
            binary=binary, timeout_sec=timeout_sec, extra_args=extra_args,
        ):
            yield ev
        return

    # SelectorEventLoop 환경 — sync subprocess + thread 로 직행.
    result = await _call_claude_code_sync_via_thread(
        system=system, messages=messages, model=model,
        max_tokens=max_tokens, temperature=temperature,
        binary=binary, timeout_sec=timeout_sec, extra_args=extra_args,
    )
    yield {"type": "text_delta", "text": result["content"]}
    raw = dict(result.get("raw") or {})
    raw["stream_fallback"] = "batch_thread"  # 진단 마커
    yield {
        "type": "metadata",
        "content": result["content"],
        "tokens_in": result["tokens_in"],
        "tokens_out": result["tokens_out"],
        "model": result["model"],
        "cost_usd": result["cost_usd"],
        "raw": raw,
    }


async def _call_claude_code_sync_via_thread(
    *,
    system: list[dict] | str,
    messages: list[dict],
    model: str,
    max_tokens: int,  # noqa: ARG001
    temperature: float,  # noqa: ARG001
    binary: str = "claude",
    timeout_sec: int = 90,
    extra_args: list[str] | None = None,
) -> dict:
    """Sync subprocess.run 을 asyncio.to_thread 로 실행 — main event loop 무관.

    SelectorEventLoop 에서 asyncio.create_subprocess_exec 가 NotImplementedError
    인 상황을 우회. 같은 인자/스킴으로 call_claude_code 와 동일 dict 반환.
    """
    launcher = _resolve_launcher(binary)
    system_text = _blocks_to_text(system)
    user_text = _messages_to_text(messages)

    is_windows = platform.system() == "Windows"
    cmdline_safe_limit = 7000
    fold_system_into_stdin = is_windows and len(system_text) > cmdline_safe_limit

    args: list[str] = [
        *launcher,
        "--print",
        "--output-format", "json",
        "--input-format", "text",
        "--model", _normalize_model_alias(model),
        "--no-session-persistence",
    ]
    if system_text.strip() and not fold_system_into_stdin:
        args.extend(["--system-prompt", system_text])
    if extra_args:
        args.extend(extra_args)

    stdin_payload = (
        f"[SYSTEM]\n{system_text}\n\n[USER]\n{user_text}"
        if fold_system_into_stdin and system_text.strip()
        else user_text
    )

    sub_env = os.environ.copy()
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        sub_env.pop(key, None)

    def _run_sync() -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                args,
                input=stdin_payload.encode("utf-8"),
                capture_output=True,
                timeout=timeout_sec,
                env=sub_env,
            )
        except FileNotFoundError as exc:
            raise ClaudeCodeNotInstalled(str(exc)) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"claude_code (sync) timed out after {timeout_sec}s"
            ) from exc

    r = await asyncio.to_thread(_run_sync)
    stdout = r.stdout.decode("utf-8", errors="replace")
    stderr = r.stderr.decode("utf-8", errors="replace")

    if r.returncode != 0:
        raise RuntimeError(
            f"claude_code (sync) exited {r.returncode}: "
            f"{stderr[:400] or stdout[:400]}"
        )

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"claude_code (sync) stdout is not valid JSON: {stdout[:400]}"
        ) from e

    if payload.get("is_error"):
        msg = payload.get("result") or "unknown error"
        if "not logged in" in msg.lower() or "login" in msg.lower():
            raise ClaudeCodeAuthError(
                f"Claude Code is not authenticated. Run `claude setup-token`. Detail: {msg}"
            )
        raise RuntimeError(f"claude_code (sync) returned error: {msg}")

    content = str(payload.get("result", ""))
    usage = payload.get("usage") or {}
    total_cost = payload.get("total_cost_usd") or 0.0
    tokens_in = int(usage.get("input_tokens") or 0) + int(
        usage.get("cache_creation_input_tokens") or 0
    )
    tokens_out = int(usage.get("output_tokens") or 0)
    resolved_model = _resolve_reported_model(payload, model)

    return {
        "content": content,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "model": resolved_model,
        "cost_usd": float(total_cost),
        "raw": {
            "provider": "claude_code",
            "session_id": payload.get("session_id"),
            "stop_reason": payload.get("stop_reason"),
            "duration_ms": payload.get("duration_ms"),
            "usage": usage,
            "model_usage": payload.get("modelUsage", {}),
        },
    }


async def _claude_code_stream_native(
    *,
    system: list[dict] | str,
    messages: list[dict],
    model: str,
    max_tokens: int,  # noqa: ARG001
    temperature: float,  # noqa: ARG001
    binary: str = "claude",
    timeout_sec: int = 90,
    extra_args: list[str] | None = None,
):
    """Native streaming — `--output-format stream-json --include-partial-messages`.

    Yields stream events:
        {"type": "text_delta", "text": str}
        {"type": "metadata", "tokens_in"/"tokens_out"/"cost_usd"/"raw"/...}

    Windows asyncio.SelectorEventLoop 환경에선 NotImplementedError → 호출자
    (call_claude_code_stream) 가 batch fallback.
    """
    launcher = _resolve_launcher(binary)

    system_text = _blocks_to_text(system)
    user_text = _messages_to_text(messages)

    is_windows = platform.system() == "Windows"
    cmdline_safe_limit = 7000
    fold_system_into_stdin = is_windows and len(system_text) > cmdline_safe_limit

    args: list[str] = [
        *launcher,
        "--print",
        "--output-format", "stream-json",
        "--include-partial-messages",
        "--input-format", "text",
        "--model", _normalize_model_alias(model),
        "--no-session-persistence",
        "--verbose",  # stream-json 모드는 verbose 필수 (CLI 요구사항)
    ]
    if system_text.strip() and not fold_system_into_stdin:
        args.extend(["--system-prompt", system_text])
    if extra_args:
        args.extend(extra_args)

    if fold_system_into_stdin and system_text.strip():
        stdin_payload = f"[SYSTEM]\n{system_text}\n\n[USER]\n{user_text}"
    else:
        stdin_payload = user_text

    log.debug(
        "claude_code_stream_spawn",
        argv_head=args[:8],
        system_chars=len(system_text),
        user_chars=len(user_text),
    )

    sub_env = os.environ.copy()
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        sub_env.pop(key, None)

    try:
        # limit=10MB — CLI 의 hook_response 가 skill md 통째 single-line 으로
        # 출력 (default 64KB 면 LimitOverrunError, 빈 메시지로 죽음).
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=sub_env,
            limit=10 * 1024 * 1024,
        )
    except FileNotFoundError as e:
        raise ClaudeCodeNotInstalled(str(e)) from e

    # stdin 송신은 background task — Windows pipe buffer (64KB) 한계로 system
    # prompt 가 크면 (19K canon+) write 가 block 됨. CLI 는 stdin 이 닫혀야
    # 본격 처리 시작인데, 우리가 동시에 stdout 을 읽지 않으면 deadlock 발생.
    # 그래서 write/drain/close 를 백그라운드로 돌리고 stdout readline 도
    # 동시 진행.
    assert proc.stdin is not None

    async def _send_stdin() -> None:
        try:
            proc.stdin.write(stdin_payload.encode("utf-8"))
            await proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as e:
            log.warning("claude_code_stdin_send_failed", error=repr(e))
        finally:
            try:
                proc.stdin.close()
            except Exception:  # noqa: BLE001
                pass

    stdin_task = asyncio.create_task(_send_stdin())

    full_text_parts: list[str] = []
    final_usage: dict[str, Any] = {}
    final_cost: float = 0.0
    final_session_id: str | None = None
    final_stop_reason: str | None = None
    final_model_usage: dict = {}
    saw_error: str | None = None

    assert proc.stdout is not None
    try:
        while True:
            try:
                line = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=timeout_sec,
                )
            except asyncio.TimeoutError as e:
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass
                raise RuntimeError(
                    f"claude_code_stream timed out after {timeout_sec}s"
                ) from e

            if not line:
                break  # EOF
            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str:
                continue
            try:
                event = json.loads(line_str)
            except json.JSONDecodeError:
                log.warning("claude_code_stream_bad_jsonl",
                            line_head=line_str[:120])
                continue

            etype = event.get("type")

            # Streaming text 추출 — content_block_delta 가 partial 토큰의 표준 형식
            if etype == "stream_event" or etype == "content_block_delta":
                # nested 가능: stream_event.event.delta.text 또는 content_block_delta.delta.text
                inner = event.get("event") or event
                if inner.get("type") == "content_block_delta":
                    delta = inner.get("delta") or {}
                    text = delta.get("text") or ""
                    if text:
                        full_text_parts.append(text)
                        yield {"type": "text_delta", "text": text}
                continue

            # CLI 형식 변형: assistant 이벤트가 부분 메시지 포함
            if etype == "assistant":
                message = event.get("message") or {}
                for block in message.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text") or ""
                        # partial 모드에선 새 토큰만 와야 정상.
                        # 누적 메시지 형식이면 마지막 부분만 emit.
                        if text and text not in "".join(full_text_parts):
                            new_text = text
                            joined = "".join(full_text_parts)
                            if joined and text.startswith(joined):
                                new_text = text[len(joined):]
                            if new_text:
                                full_text_parts.append(new_text)
                                yield {"type": "text_delta", "text": new_text}
                continue

            # 종료 메시지
            if etype == "result":
                if event.get("is_error"):
                    saw_error = str(event.get("result") or "claude_code error")
                    break
                final_usage = event.get("usage") or {}
                final_cost = float(event.get("total_cost_usd") or 0.0)
                final_session_id = event.get("session_id")
                final_stop_reason = event.get("stop_reason")
                final_model_usage = event.get("modelUsage") or {}
                # result 의 result 필드가 전체 텍스트 — full_text_parts 가 비어있는
                # 케이스 (partial events 불가) 에 fallback
                if not full_text_parts and event.get("result"):
                    text = str(event["result"])
                    full_text_parts.append(text)
                    yield {"type": "text_delta", "text": text}
                continue

            # system 이벤트, message_stop, content_block_start 등은 무시
    finally:
        # stdin background task 정리
        if not stdin_task.done():
            stdin_task.cancel()
            try:
                await stdin_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except (asyncio.TimeoutError, ProcessLookupError):
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass

    if saw_error:
        raise RuntimeError(f"claude_code stream returned error: {saw_error}")
    if proc.returncode is not None and proc.returncode != 0:
        stderr = (await proc.stderr.read()).decode("utf-8", errors="replace") if proc.stderr else ""
        raise RuntimeError(
            f"claude_code_stream exited {proc.returncode}: {stderr[:400]}"
        )

    tokens_in = int(final_usage.get("input_tokens") or 0) + int(
        final_usage.get("cache_creation_input_tokens") or 0
    )
    tokens_out = int(final_usage.get("output_tokens") or 0)
    resolved_model = _resolve_reported_model(
        {"modelUsage": final_model_usage}, model,
    )

    yield {
        "type": "metadata",
        "content": "".join(full_text_parts),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "model": resolved_model,
        "cost_usd": final_cost,
        "raw": {
            "provider": "claude_code",
            "session_id": final_session_id,
            "stop_reason": final_stop_reason,
            "usage": final_usage,
            "model_usage": final_model_usage,
        },
    }


def _normalize_model_alias(model: str) -> str:
    """Map known full model names to CLI-friendly aliases when helpful."""
    aliases = {
        "claude-sonnet-4-5": "sonnet",
        "claude-sonnet-4": "sonnet",
        "claude-opus-4-6": "opus",
        "claude-opus-4": "opus",
        "claude-haiku-4-5": "haiku",
    }
    return aliases.get(model, model)


def _resolve_reported_model(payload: dict[str, Any], requested: str) -> str:
    """Prefer the exact model string Claude Code reports using."""
    model_usage = payload.get("modelUsage") or {}
    if model_usage:
        # Return the model that consumed the most output tokens (main responder)
        best = max(
            model_usage.items(),
            key=lambda kv: (kv[1].get("outputTokens") or 0),
            default=None,
        )
        if best:
            return best[0]
    return requested
