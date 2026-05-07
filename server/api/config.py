"""Config inspection + reload endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from core.config import get_config, trigger_reload

router = APIRouter()


@router.get("/config")
async def get_config_json() -> dict:
    """Return current runtime config as JSON. Secrets are NOT included."""
    cfg = get_config()
    return cfg.model_dump()


@router.get("/config/llm")
async def get_config_llm() -> dict:
    """Return resolved LLM provider + model — for webapp 'auto' label.

    Webapp 의 LLM 선택 UI 가 '자동 (기본)' 옵션의 실제 매핑을 동적 표시하도록.
    """
    cfg = get_config().llm
    provider = cfg.provider
    if provider == "gemini":
        model = getattr(getattr(cfg, "gemini", None), "model", None) or "gemini-2.5-flash"
    elif provider == "anthropic":
        model = cfg.anthropic.model or cfg.primary
    elif provider == "claude_code":
        model = cfg.anthropic.model or cfg.primary  # CLI 가 alias 매핑 (sonnet/opus)
    else:
        model = "mock"
    return {
        "provider": provider,
        "model": model,
        "fallback_chain": [provider, "claude_code", "mock"]
        if provider != "claude_code"
        else [provider, "mock"],
    }


@router.post("/config/reload")
async def reload_config() -> dict:
    ok = trigger_reload()
    return {"reloaded": ok}
