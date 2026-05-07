"""LLM client — Anthropic-first with mock fallback.

Fallback behavior:
- If ANTHROPIC_API_KEY is unset AND config.llm.mock_if_no_key == True
  → returns a deterministic mock response (enables dev/CI without keys).
- Otherwise: real Anthropic API call with prompt caching applied to
  system blocks marked with cache_control.

Idempotency:
- core/memory/cache.py handles the cache layer. Callers pass input_hash.

Returned payload is a dict with:
  {
    "content": str,            # concatenated text output
    "tokens_in": int,
    "tokens_out": int,
    "model": str,
    "cost_usd": float,
    "raw": dict,               # raw provider response (sanitized)
  }
"""
from __future__ import annotations

import json
from typing import Any

from core.config import env, get_config
from core.logging import get_logger
from core.memory.cache import get_cached_response, store_cached_response

log = get_logger(__name__)

# Cost table (per 1M tokens). Approximate.
_COSTS_USD_PER_1M = {
    "claude-sonnet-4-5": {"in": 3.0, "out": 15.0},
    "claude-sonnet-4": {"in": 3.0, "out": 15.0},
    "claude-haiku-4-5": {"in": 0.8, "out": 4.0},
    "claude-opus-4": {"in": 15.0, "out": 75.0},
    "claude-opus-4-6": {"in": 15.0, "out": 75.0},
}


def _estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    rates = _COSTS_USD_PER_1M.get(model, {"in": 3.0, "out": 15.0})
    return (tokens_in * rates["in"] + tokens_out * rates["out"]) / 1_000_000


def _mock_response(system: list[dict] | str, messages: list[dict], model: str) -> dict:
    """Deterministic mock used when no API key is available."""
    # Produce a plausible JSON response based on the last user message.
    last = messages[-1]["content"] if messages else "{}"
    mock = {
        "verdict": "neutral",
        "confidence": 55,
        "reasons": [
            "[MOCK] API 키가 없어 모의 응답이 반환됨",
            "실제 판단은 ANTHROPIC_API_KEY 설정 후 가능",
            f"입력 길이: {len(last) if isinstance(last, str) else 0} 문자",
        ],
        "narrative": "[MOCK RESPONSE] 실제 LLM 호출을 위해서는 .env 에 ANTHROPIC_API_KEY 를 설정하세요.",
    }
    text = json.dumps(mock, ensure_ascii=False)
    return {
        "content": text,
        "tokens_in": 100,
        "tokens_out": 100,
        "model": f"{model}-mock",
        "cost_usd": 0.0,
        "raw": {"mock": True},
    }


def _build_anthropic_client():
    """Build an AsyncAnthropic client, picking the correct auth header.

    - sk-ant-oat01-*  → OAuth token from `claude setup-token` → Authorization: Bearer
    - sk-ant-api03-*  → standard API key                     → x-api-key
    - anything else   → try as api_key (best guess)
    """
    from anthropic import AsyncAnthropic

    token = env("ANTHROPIC_API_KEY")
    if not token:
        return None
    if token.startswith("sk-ant-oat"):
        return AsyncAnthropic(auth_token=token)
    return AsyncAnthropic(api_key=token)


# ---------------------------------------------------------------------------
# Gemini (Google AI Studio) provider
# ---------------------------------------------------------------------------

_GEMINI_COSTS = {
    # Free tier: $0. Paid tier (per 1M tokens).
    "gemini-2.5-flash": {"in": 0.075, "out": 0.30},
    "gemini-2.5-pro": {"in": 1.25, "out": 10.0},
    "gemini-2.0-flash": {"in": 0.10, "out": 0.40},
}


def _anthropic_blocks_to_gemini_system(system) -> str:
    """Convert Anthropic-style system (str or list of blocks) to plain text for Gemini.

    Gemini uses a single system_instruction string — no cache_control concept.
    We concat all text blocks in order.
    """
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        parts = []
        for block in system:
            text = block.get("text") if isinstance(block, dict) else None
            if text:
                parts.append(text)
        return "\n\n".join(parts)
    return ""


def _anthropic_messages_to_gemini_contents(messages) -> list:
    """Convert Anthropic messages [{role, content}] to Gemini contents format.

    Gemini uses role='user' or 'model' (not 'assistant').
    """
    out = []
    for msg in messages:
        role = msg.get("role", "user")
        gemini_role = "model" if role == "assistant" else "user"
        content = msg.get("content", "")
        if isinstance(content, list):
            # Anthropic can pass list of blocks; flatten to text
            text_parts = [b.get("text", "") for b in content if isinstance(b, dict)]
            content = "\n".join(text_parts)
        out.append({"role": gemini_role, "parts": [{"text": str(content)}]})
    return out


async def _call_gemini_real(
    system,
    messages,
    model: str,
    max_tokens: int,
    temperature: float,
) -> dict:
    """Call Google Gemini via google-genai SDK."""
    from google import genai
    from google.genai import types

    api_key = env("GOOGLE_AI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_AI_API_KEY missing")

    client = genai.Client(api_key=api_key)
    system_text = _anthropic_blocks_to_gemini_system(system)
    contents = _anthropic_messages_to_gemini_contents(messages)

    config = types.GenerateContentConfig(
        system_instruction=system_text if system_text else None,
        max_output_tokens=max_tokens,
        temperature=temperature,
    )

    # google-genai is sync; wrap in asyncio.to_thread
    import asyncio as _asyncio
    resp = await _asyncio.to_thread(
        client.models.generate_content,
        model=model,
        contents=contents,
        config=config,
    )

    text = getattr(resp, "text", "") or ""
    usage = getattr(resp, "usage_metadata", None)
    tokens_in = getattr(usage, "prompt_token_count", 0) if usage else 0
    tokens_out = getattr(usage, "candidates_token_count", 0) if usage else 0

    rates = _GEMINI_COSTS.get(model, {"in": 0.075, "out": 0.30})
    cost = (tokens_in * rates["in"] + tokens_out * rates["out"]) / 1_000_000

    return {
        "content": text,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "model": model,
        "cost_usd": cost,
        "raw": {
            "finish_reason": str(getattr(resp.candidates[0], "finish_reason", "")) if resp.candidates else "",
            "provider": "gemini",
        },
    }


async def _call_anthropic_real(
    system: list[dict] | str,
    messages: list[dict],
    model: str,
    max_tokens: int,
    temperature: float,
) -> dict:
    """Call Anthropic Messages API. Lazy import to avoid hard dep for tests."""
    client = _build_anthropic_client()
    if client is None:
        raise RuntimeError("ANTHROPIC_API_KEY missing")
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,  # may be str or list-of-blocks (cache-aware)
        messages=messages,
    )
    content_blocks = response.content
    text = "".join(getattr(b, "text", "") for b in content_blocks)
    usage = response.usage
    tokens_in = getattr(usage, "input_tokens", 0)
    tokens_out = getattr(usage, "output_tokens", 0)
    return {
        "content": text,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "model": model,
        "cost_usd": _estimate_cost(model, tokens_in, tokens_out),
        "raw": {
            "id": getattr(response, "id", None),
            "stop_reason": getattr(response, "stop_reason", None),
            "usage": usage.model_dump() if hasattr(usage, "model_dump") else {},
        },
    }


async def call_llm(
    *,
    system: list[dict] | str,
    messages: list[dict],
    input_hash: str | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    json_schema: dict | None = None,
    provider: str | None = None,
) -> dict:
    """Call the configured LLM with optional cache lookup.

    Args:
        system: list of content blocks (for prompt caching) or a plain string.
        messages: list of {"role": "user"|"assistant", "content": str}
        input_hash: when provided, cache is consulted first and response stored.
        model/max_tokens/temperature: override config defaults.
        provider: when set ("gemini"|"claude_code"|"anthropic"|"mock"), force that
                  backend — errors propagate (no auto-fallback). For tone-compare
                  flows where the caller explicitly chose a backend.
                  When None: use cfg.provider with primary→fallback→mock chain.

    Returns:
        dict with content, tokens_in, tokens_out, model, cost_usd, raw.
    """
    cfg = get_config().llm
    model = model or cfg.anthropic.model or cfg.primary
    max_tokens = max_tokens or cfg.anthropic.max_tokens
    temperature = temperature if temperature is not None else cfg.anthropic.temperature

    if provider is not None:
        # Explicit caller choice — honor it. If the chosen backend lacks creds,
        # _resolve_provider fall-through to mock would mask the choice; here we
        # let _dispatch_provider raise on missing creds so the caller sees it.
        resolved_provider = provider
        allow_fallback = False
    else:
        resolved_provider = _resolve_provider(cfg)
        allow_fallback = True

    # Cache lookup — skip in mock mode, and reject stored mock responses even when
    # the provider has since been switched to a real backend.
    if input_hash and resolved_provider != "mock":
        cached = get_cached_response(input_hash)
        if cached is not None and not _is_mock_response(cached):
            log.debug("llm_cache_hit", input_hash=input_hash[:24], provider=resolved_provider)
            return cached

    resp = await _dispatch_provider(
        provider=resolved_provider,
        cfg=cfg,
        system=system,
        messages=messages,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        json_schema=json_schema,
        allow_fallback=allow_fallback,
    )

    # Persist only genuine (non-mock) responses so the cache stays meaningful.
    if input_hash and not _is_mock_response(resp):
        store_cached_response(
            input_hash=input_hash,
            model=resp["model"],
            response=resp,
            tokens_in=resp["tokens_in"],
            tokens_out=resp["tokens_out"],
            cost_usd=resp["cost_usd"],
        )
    return resp


def _resolve_provider(cfg) -> str:
    """Pick which backend to hit.

    - provider=mock                   → mock
    - provider=claude_code            → claude_code
    - provider=gemini + GOOGLE_AI_API_KEY → gemini
    - provider=anthropic + API key    → anthropic
    - *         + no key              → mock (if mock_if_no_key) else error
    """
    provider = getattr(cfg, "provider", "anthropic")
    if provider == "mock":
        return "mock"
    if provider == "claude_code":
        return "claude_code"
    if provider == "gemini":
        if env("GOOGLE_AI_API_KEY"):
            return "gemini"
        if cfg.mock_if_no_key:
            log.info("llm_mock_fallback", reason="no_google_api_key")
            return "mock"
        raise RuntimeError("provider=gemini requires GOOGLE_AI_API_KEY")
    # anthropic
    if env("ANTHROPIC_API_KEY"):
        return "anthropic"
    if cfg.mock_if_no_key:
        log.info("llm_mock_fallback", reason="no_api_key")
        return "mock"
    raise RuntimeError("provider=anthropic requires ANTHROPIC_API_KEY or mock_if_no_key=True")


async def _dispatch_provider(
    *,
    provider: str,
    cfg,
    system,
    messages,
    model: str,
    max_tokens: int,
    temperature: float,
    json_schema: dict | None = None,
    allow_fallback: bool = True,
) -> dict:
    """Dispatch to a backend.

    allow_fallback=True  → primary failure cascades to claude_code → mock
                           (when permitted by cfg.mock_if_no_key). Used for
                           default/auto provider resolution.
    allow_fallback=False → caller chose this backend explicitly; errors
                           propagate without silent provider switch.
    """
    if provider == "mock":
        return _mock_response(system, messages, model)

    if provider == "claude_code":
        from core.llm.claude_code_backend import call_claude_code

        try:
            return await call_claude_code(
                system=system,
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                binary=cfg.claude_code.binary,
                timeout_sec=cfg.claude_code.timeout_sec,
                extra_args=list(cfg.claude_code.extra_args),
                json_schema=json_schema,
            )
        except Exception as e:  # noqa: BLE001
            log.error("llm_call_failed", provider="claude_code", error=str(e))
            if allow_fallback and cfg.mock_if_no_key:
                resp = _mock_response(system, messages, model)
                resp["raw"]["error"] = str(e)
                return resp
            raise

    if provider == "gemini":
        # Gemini uses its own model names — override if caller passed Anthropic model
        gemini_model = model
        if "claude" in model.lower() or not model.startswith("gemini"):
            gemini_model = getattr(
                getattr(cfg, "gemini", None), "model", None
            ) or "gemini-2.5-flash"
        try:
            return await _call_gemini_real(
                system, messages, gemini_model, max_tokens, temperature
            )
        except Exception as gemini_error:  # noqa: BLE001
            log.error("llm_call_failed", provider="gemini", error=str(gemini_error))
            if not allow_fallback:
                raise
            log.warning(
                "llm_gemini_failed_falling_back",
                error=str(gemini_error),
                fallback="claude_code",
            )
            # Fallback chain: gemini → claude_code → mock.
            # claude_code uses local CLI subprocess (Pro/Max subscription, no API key).
            from core.llm.claude_code_backend import call_claude_code

            try:
                resp = await call_claude_code(
                    system=system,
                    messages=messages,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    binary=cfg.claude_code.binary,
                    timeout_sec=cfg.claude_code.timeout_sec,
                    extra_args=list(cfg.claude_code.extra_args),
                    json_schema=json_schema,
                )
                resp["raw"]["primary_provider_error"] = str(gemini_error)
                resp["raw"]["fallback_used"] = "claude_code"
                return resp
            except Exception as claude_error:  # noqa: BLE001
                log.error(
                    "llm_call_failed",
                    provider="gemini+claude_code",
                    gemini_error=str(gemini_error),
                    claude_error=str(claude_error),
                )
                if cfg.mock_if_no_key:
                    resp = _mock_response(system, messages, model)
                    resp["raw"]["error"] = str(gemini_error)
                    resp["raw"]["fallback_error"] = str(claude_error)
                    return resp
                raise

    # provider == "anthropic"
    try:
        return await _call_anthropic_real(system, messages, model, max_tokens, temperature)
    except Exception as e:  # noqa: BLE001
        log.error("llm_call_failed", provider="anthropic", error=str(e))
        if allow_fallback and cfg.mock_if_no_key:
            resp = _mock_response(system, messages, model)
            resp["raw"]["error"] = str(e)
            return resp
        raise


def _is_mock_response(resp: dict) -> bool:
    """A response is considered mock if it was produced without hitting Anthropic."""
    model = resp.get("model", "")
    raw = resp.get("raw") or {}
    return "-mock" in model or bool(raw.get("mock")) or raw.get("error") is not None


def parse_json_response(content: str) -> dict[str, Any]:
    """Extract first JSON object from LLM response content, tolerantly."""
    content = content.strip()
    # Strip ```json fences if present
    if content.startswith("```"):
        first_newline = content.find("\n")
        if first_newline != -1:
            content = content[first_newline + 1 :]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Find first { ... last } window
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(content[start : end + 1])
        raise
