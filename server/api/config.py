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


@router.post("/config/reload")
async def reload_config() -> dict:
    ok = trigger_reload()
    return {"reloaded": ok}
