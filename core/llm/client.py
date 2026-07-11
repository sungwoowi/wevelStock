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

import asyncio
import json
from typing import Any, AsyncIterator

from core.config import env, get_config
from core.llm.ledger import record_llm_cost
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
    # Free tier: $0. Paid tier (per 1M tokens), verified vs
    # https://ai.google.dev/gemini-api/docs/pricing (2026-07-12).
    # NOTE 낡은 값 정정: 2.5-flash 는 0.075/0.30(구 1.5/2.0-lite 요금)으로 박혀 있어
    #   실비를 1/3 로 축소 보고했음. GA 정식 요금으로 교체.
    "gemini-2.5-flash": {"in": 0.30, "out": 2.50},
    "gemini-2.5-flash-lite": {"in": 0.10, "out": 0.40},
    # 2.5-pro: >200k 프롬프트는 2.50/15.0 이나 본 시스템 호출은 ≤200k 라 기본 티어만 반영.
    "gemini-2.5-pro": {"in": 1.25, "out": 10.0},
    "gemini-2.0-flash": {"in": 0.10, "out": 0.40},  # 2026-06-01 shut down; legacy 행 대비 유지
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
    thinking_budget: int | None = None,
) -> dict:
    """Call Google Gemini via google-genai SDK.

    thinking_budget: Gemini 2.5 reasoning 모델의 thinking 토큰 예산.
        - None  → 미설정 (모델 기본 thinking, 분석가 등 긴 추론에 유리).
        - 0     → thinking 비활성 (flash). 결정론 분류/선택 호출용 — thinking 토큰이
                  max_output_tokens 예산을 잠식해 JSON 출력이 잘리는 사고 방지.
        - N>0   → 명시 budget.
    """
    from google import genai
    from google.genai import types

    api_key = env("GOOGLE_AI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_AI_API_KEY missing")

    client = genai.Client(api_key=api_key)
    system_text = _anthropic_blocks_to_gemini_system(system)
    contents = _anthropic_messages_to_gemini_contents(messages)

    config_kwargs: dict = dict(
        system_instruction=system_text if system_text else None,
        max_output_tokens=max_tokens,
        temperature=temperature,
    )
    if thinking_budget is not None:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)
    config = types.GenerateContentConfig(**config_kwargs)

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
    # Gemini 2.5 reasoning 모델의 thinking 토큰: max_output_tokens 예산을 잠식하고
    # output rate 로 과금된다. 비용 정확성 위해 cost 에 포함 (candidates 와 별도 surface).
    tokens_thinking = (getattr(usage, "thoughts_token_count", 0) if usage else 0) or 0

    rates = _GEMINI_COSTS.get(model, {"in": 0.30, "out": 2.50})
    cost = (tokens_in * rates["in"] + (tokens_out + tokens_thinking) * rates["out"]) / 1_000_000

    return {
        "content": text,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "model": model,
        "cost_usd": cost,
        "raw": {
            "finish_reason": str(getattr(resp.candidates[0], "finish_reason", "")) if resp.candidates else "",
            "thinking_tokens": tokens_thinking,
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
    mock_fallback_allowed: bool = True,
    thinking_budget: int | None = None,
    call_type: str = "general",
    target: str | None = None,
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
        mock_fallback_allowed: When False, suppresses the silent mock fallback
            that normally activates when `cfg.mock_if_no_key=True` and all real
            providers fail. Set to False on user-facing paths (production-chat)
            so that errors propagate to the caller instead of returning a fake
            response. Default True preserves legacy dev/CI behaviour.
        thinking_budget: Gemini-only thinking 토큰 예산. None=모델 기본, 0=비활성
            (flash, 결정론 JSON 호출용 — thinking 의 예산 잠식 잘림 방지), N=명시.
            anthropic/claude_code/mock 백엔드에서는 무시(no-op).
        call_type: 비용 원장(llm_cost_ledger) 질의영역 라벨 — 'anchor_selection' /
            'analyst:<id>' / 'strategist:<track>' / 'briefing' / 'news_classify' 등.
            운영자 화면이 이 축으로 지출을 집계. 기본 'general'.
        target: 원장 target 컬럼 — 종목코드/'global' 등 (optional).

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
        resolved_provider = _resolve_provider(cfg, mock_fallback_allowed=mock_fallback_allowed)
        allow_fallback = True

    # Cache lookup — skip in mock mode, and reject stored mock responses even when
    # the provider has since been switched to a real backend.
    if input_hash and resolved_provider != "mock":
        cached = get_cached_response(input_hash)
        if cached is not None and not _is_mock_response(cached):
            log.debug("llm_cache_hit", input_hash=input_hash[:24], provider=resolved_provider)
            _record_ledger(cached, resolved_provider, call_type, target, cache_hit=True)
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
        mock_fallback_allowed=mock_fallback_allowed,
        thinking_budget=thinking_budget,
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
    # 비용 원장 — served 응답 1건 기록 (mock 은 제외 — dev/CI 노이즈).
    if not _is_mock_response(resp):
        _record_ledger(resp, resolved_provider, call_type, target, cache_hit=False)
    return resp


def _record_ledger(
    resp: dict,
    resolved_provider: str,
    call_type: str,
    target: str | None,
    *,
    cache_hit: bool,
) -> None:
    """resp dict → llm_cost_ledger 1행. 실제 서빙한 provider 는 raw.provider 우선."""
    provider = ((resp.get("raw") or {}).get("provider")) or resolved_provider
    record_llm_cost(
        provider=provider,
        model=resp.get("model") or "unknown",
        call_type=call_type,
        target=target,
        tokens_in=resp.get("tokens_in") or 0,
        tokens_out=resp.get("tokens_out") or 0,
        cost_usd=0.0 if cache_hit else (resp.get("cost_usd") or 0.0),
        cache_hit=cache_hit,
        success=True,
    )


def _resolve_provider(cfg, *, mock_fallback_allowed: bool = True) -> str:
    """Pick which backend to hit.

    - provider=mock                   → mock
    - provider=claude_code            → claude_code
    - provider=gemini + GOOGLE_AI_API_KEY → gemini
    - provider=anthropic + API key    → anthropic
    - *         + no key              → mock (if mock_if_no_key and mock_fallback_allowed) else error
    """
    provider = getattr(cfg, "provider", "anthropic")
    if provider == "mock":
        return "mock"
    if provider == "claude_code":
        return "claude_code"
    if provider == "gemini":
        if env("GOOGLE_AI_API_KEY"):
            return "gemini"
        if cfg.mock_if_no_key and mock_fallback_allowed:
            log.info("llm_mock_fallback", reason="no_google_api_key")
            return "mock"
        raise RuntimeError("provider=gemini requires GOOGLE_AI_API_KEY")
    # anthropic
    if env("ANTHROPIC_API_KEY"):
        return "anthropic"
    if cfg.mock_if_no_key and mock_fallback_allowed:
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
    mock_fallback_allowed: bool = True,
    thinking_budget: int | None = None,
) -> dict:
    """Dispatch to a backend.

    allow_fallback=True  → primary failure cascades to claude_code → mock
                           (when permitted by cfg.mock_if_no_key). Used for
                           default/auto provider resolution.
    allow_fallback=False → caller chose this backend explicitly; errors
                           propagate without silent provider switch.
    mock_fallback_allowed=False → suppresses the final mock_if_no_key fallback
                                  even when allow_fallback=True. Used on
                                  user-facing paths so mock responses never
                                  surface as if they were real.
    """
    if provider == "mock":
        return _mock_response(system, messages, model)

    if provider == "claude_code":
        from core.llm.claude_code_backend import call_claude_code

        # subprocess 일시적 burst (returncode!=0 + 빈 stderr/stdout) 흡수용 1회 재시도.
        # RuntimeError("...exited ...") 만 재시도 — TimeoutError·ClaudeCodeNotInstalled·
        # ClaudeCodeAuthError·JSONDecode 등 영구 실패는 즉시 break.
        last_exc: Exception | None = None
        for attempt in range(2):
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
                last_exc = e
                is_transient = (
                    isinstance(e, RuntimeError)
                    and "exited" in (str(e) or "")
                )
                if is_transient and attempt == 0:
                    log.warning(
                        "llm_claude_code_transient_retry",
                        attempt=attempt + 1,
                        error=str(e) or repr(e),
                    )
                    await asyncio.sleep(0.2)
                    continue
                break

        e = last_exc
        log.error(
            "llm_call_failed",
            provider="claude_code",
            error=str(e),
            error_type=type(e).__name__,
            error_repr=repr(e),
        )
        if allow_fallback and cfg.mock_if_no_key and mock_fallback_allowed:
            resp = _mock_response(system, messages, model)
            resp["raw"]["error"] = str(e) or repr(e)
            return resp
        raise e  # type: ignore[misc]

    if provider == "gemini":
        # Gemini uses its own model names — override if caller passed Anthropic model
        gemini_model = model
        if "claude" in model.lower() or not model.startswith("gemini"):
            gemini_model = getattr(
                getattr(cfg, "gemini", None), "model", None
            ) or "gemini-2.5-flash"
        # 일시적 서버 과부하(503 UNAVAILABLE·overloaded·500 INTERNAL)·일시 rate-limit 흡수용
        # bounded 재시도. 크레딧 고갈(RESOURCE_EXHAUSTED)·인증 등 영구 실패는 즉시 중단(재시도 무의미).
        gemini_error: Exception | None = None
        for _attempt in range(3):
            try:
                return await _call_gemini_real(
                    system, messages, gemini_model, max_tokens, temperature,
                    thinking_budget=thinking_budget,
                )
            except Exception as e:  # noqa: BLE001
                gemini_error = e
                msg = str(e) or repr(e)
                transient = (
                    any(t in msg for t in ("503", "UNAVAILABLE", "overloaded", "high demand", "500 INTERNAL"))
                    and "RESOURCE_EXHAUSTED" not in msg
                )
                if transient and _attempt < 2:
                    log.warning("llm_gemini_transient_retry", attempt=_attempt + 1, error=msg)
                    await asyncio.sleep(0.8 * (_attempt + 1))
                    continue
                break

        log.error("llm_call_failed", provider="gemini", error=str(gemini_error))
        if not allow_fallback:
            raise gemini_error  # type: ignore[misc]
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
            if cfg.mock_if_no_key and mock_fallback_allowed:
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
        if allow_fallback and cfg.mock_if_no_key and mock_fallback_allowed:
            resp = _mock_response(system, messages, model)
            resp["raw"]["error"] = str(e)
            return resp
        raise


def _is_mock_response(resp: dict) -> bool:
    """A response is considered mock if it was produced without hitting Anthropic."""
    model = resp.get("model", "")
    raw = resp.get("raw") or {}
    return "-mock" in model or bool(raw.get("mock")) or raw.get("error") is not None


# ---------------------------------------------------------------------------
# Streaming — token-by-token 응답 (INFRA-LLM-STREAM-001)
# ---------------------------------------------------------------------------
#
# 이벤트 계약 (llm-stream-event-v1):
#   {"type": "text_delta", "text": str}                    # 토큰 청크
#   {"type": "metadata",   "tokens_in"/"tokens_out"/...}   # 종료 직전 1회
#   {"type": "error",      "message": str, "fatal": bool}  # provider 실패
#   {"type": "done"}                                       # 정상 종료 마커
#
# call_llm 과 인터페이스 비슷하지만 cache layer 미적용 (streaming + 멱등성
# 캐시는 후속 백로그). fallback 은 첫 청크 전 실패만 가능 — 첫 청크 후 실패는
# partial + error event 로 전파.


async def _stream_mock(system, messages, model: str) -> AsyncIterator[dict]:
    """결정론적 mock stream — 짧은 청크로 분할 yield."""
    full = _mock_response(system, messages, model)
    text = full["content"]
    # 5 글자씩 청크 (테스트 가시성 위해 작게)
    chunk_size = 5
    for i in range(0, len(text), chunk_size):
        yield {"type": "text_delta", "text": text[i : i + chunk_size]}
        await asyncio.sleep(0)  # 다른 코루틴 양보
    yield {
        "type": "metadata",
        "content": full["content"],
        "tokens_in": full["tokens_in"],
        "tokens_out": full["tokens_out"],
        "model": full["model"],
        "cost_usd": full["cost_usd"],
        "raw": full["raw"],
    }
    yield {"type": "done"}


async def _stream_anthropic(
    system, messages, model: str, max_tokens: int, temperature: float,
) -> AsyncIterator[dict]:
    """Anthropic SDK messages.stream() — text_delta 이벤트 흘림 + 종료 후 usage."""
    client = _build_anthropic_client()
    if client is None:
        raise RuntimeError("ANTHROPIC_API_KEY missing")

    full_text_parts: list[str] = []
    final_message = None
    async with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=messages,
    ) as stream:
        async for event in stream:
            # event types: message_start / content_block_start / content_block_delta /
            #              content_block_stop / message_delta / message_stop
            etype = getattr(event, "type", None)
            if etype == "content_block_delta":
                delta = getattr(event, "delta", None)
                text = getattr(delta, "text", None) if delta else None
                if text:
                    full_text_parts.append(text)
                    yield {"type": "text_delta", "text": text}
        final_message = await stream.get_final_message()

    usage = getattr(final_message, "usage", None)
    tokens_in = getattr(usage, "input_tokens", 0) if usage else 0
    tokens_out = getattr(usage, "output_tokens", 0) if usage else 0
    yield {
        "type": "metadata",
        "content": "".join(full_text_parts),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "model": model,
        "cost_usd": _estimate_cost(model, tokens_in, tokens_out),
        "raw": {
            "id": getattr(final_message, "id", None),
            "stop_reason": getattr(final_message, "stop_reason", None),
            "usage": usage.model_dump() if usage and hasattr(usage, "model_dump") else {},
        },
    }


async def _stream_gemini(
    system, messages, model: str, max_tokens: int, temperature: float,
) -> AsyncIterator[dict]:
    """Gemini async stream via google-genai. usage 마지막 chunk 의 usage_metadata."""
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

    full_text_parts: list[str] = []
    last_usage = None
    async for chunk in await client.aio.models.generate_content_stream(
        model=model, contents=contents, config=config,
    ):
        text = getattr(chunk, "text", None) or ""
        if text:
            full_text_parts.append(text)
            yield {"type": "text_delta", "text": text}
        usage = getattr(chunk, "usage_metadata", None)
        if usage is not None:
            last_usage = usage

    tokens_in = getattr(last_usage, "prompt_token_count", 0) if last_usage else 0
    tokens_out = getattr(last_usage, "candidates_token_count", 0) if last_usage else 0
    rates = _GEMINI_COSTS.get(model, {"in": 0.30, "out": 2.50})
    cost = (tokens_in * rates["in"] + tokens_out * rates["out"]) / 1_000_000
    yield {
        "type": "metadata",
        "content": "".join(full_text_parts),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "model": model,
        "cost_usd": cost,
        "raw": {"provider": "gemini"},
    }


async def call_llm_stream(
    *,
    system: list[dict] | str,
    messages: list[dict],
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    provider: str | None = None,
    mock_fallback_allowed: bool = True,
) -> AsyncIterator[dict]:
    """LLM 호출 + 토큰 스트림. provider 분기 + 첫 청크 전 fallback chain.

    Yields:
        {"type": "text_delta"|"metadata"|"error"|"done", ...}

    Note:
        - cache layer 미적용 (streaming + 멱등성은 후속 백로그)
        - fallback: 첫 청크 받기 전 실패 = 다음 provider, 첫 청크 후 실패 = error event
        - provider 명시 시 fallback X (해당 backend 만 시도, 에러 propagate)
        - mock_fallback_allowed=False → 모든 real provider 실패 시 mock stream 으로
          떨어지지 않고 명시 error event + done 으로 종료. production-chat 사용자
          경로에서 mock 응답이 사용자에게 노출되지 않도록.
    """
    cfg = get_config().llm
    model = model or cfg.anthropic.model or cfg.primary
    max_tokens = max_tokens or cfg.anthropic.max_tokens
    temperature = temperature if temperature is not None else cfg.anthropic.temperature

    if provider is not None:
        resolved_provider = provider
        allow_fallback = False
    else:
        resolved_provider = _resolve_provider(cfg, mock_fallback_allowed=mock_fallback_allowed)
        allow_fallback = True

    # provider chain — auto 모드 시 gemini → claude_code → mock
    if allow_fallback and resolved_provider in ("gemini", "anthropic"):
        chain = [resolved_provider, "claude_code"]
    else:
        chain = [resolved_provider]

    last_error: Exception | None = None
    for prov in chain:
        first_chunk_received = False
        try:
            iterator = _provider_stream(
                prov, cfg, system, messages, model, max_tokens, temperature,
            )
            async for event in iterator:
                if event.get("type") == "text_delta":
                    first_chunk_received = True
                yield event
            return  # 정상 종료 후 done
        except Exception as e:  # noqa: BLE001
            log.error("llm_stream_failed", provider=prov, error=str(e),
                      error_repr=repr(e), error_type=type(e).__name__,
                      first_chunk=first_chunk_received)
            if first_chunk_received or not allow_fallback:
                # 부분 stream 후 실패 — error event 만 emit, fallback X
                yield {"type": "error", "message": str(e),
                       "provider": prov, "fatal": True}
                yield {"type": "done"}
                return
            last_error = e
            # 첫 청크 전 실패 → 다음 provider 시도
            continue

    # 모든 provider 실패 → mock 또는 error
    if cfg.mock_if_no_key and mock_fallback_allowed:
        async for event in _stream_mock(system, messages, model):
            if event.get("type") == "metadata":
                event["raw"] = dict(event.get("raw") or {})
                event["raw"]["error"] = str(last_error) if last_error else "all_providers_failed"
                event["raw"]["fallback_used"] = "mock"
            yield event
        return

    yield {"type": "error",
           "message": str(last_error) if last_error else "all providers failed",
           "provider": "all", "fatal": True}
    yield {"type": "done"}


async def _provider_stream(
    provider: str, cfg, system, messages,
    model: str, max_tokens: int, temperature: float,
) -> AsyncIterator[dict]:
    """단일 provider stream. text_delta * N → metadata → done."""
    if provider == "mock":
        async for ev in _stream_mock(system, messages, model):
            yield ev
        return

    if provider == "anthropic":
        async for ev in _stream_anthropic(
            system, messages, model, max_tokens, temperature,
        ):
            yield ev
        yield {"type": "done"}
        return

    if provider == "gemini":
        gemini_model = model
        if "claude" in model.lower() or not model.startswith("gemini"):
            gemini_model = getattr(
                getattr(cfg, "gemini", None), "model", None,
            ) or "gemini-2.5-flash"
        async for ev in _stream_gemini(
            system, messages, gemini_model, max_tokens, temperature,
        ):
            yield ev
        yield {"type": "done"}
        return

    if provider == "claude_code":
        from core.llm.claude_code_backend import call_claude_code_stream

        async for ev in call_claude_code_stream(
            system=system, messages=messages, model=model,
            max_tokens=max_tokens, temperature=temperature,
            binary=cfg.claude_code.binary,
            timeout_sec=cfg.claude_code.timeout_sec,
            extra_args=list(cfg.claude_code.extra_args),
        ):
            yield ev
        yield {"type": "done"}
        return

    raise RuntimeError(f"unknown provider: {provider}")


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
