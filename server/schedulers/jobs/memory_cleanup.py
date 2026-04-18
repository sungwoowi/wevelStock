"""Memory cleanup — monthly purge of expired narratives and cache."""
from __future__ import annotations

from core.logging import get_logger
from core.memory.cleanup import cleanup_all

log = get_logger(__name__)


async def run_memory_cleanup() -> dict:
    stats = cleanup_all()
    log.info("memory_cleanup_finished", **stats)
    return {"status": "ok", **stats}
