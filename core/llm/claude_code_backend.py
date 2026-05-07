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
