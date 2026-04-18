"""Daily rollup — compress today's team judgments into a daily summary."""
from __future__ import annotations

from datetime import date

from core.logging import get_logger
from core.memory.rollup import rollup_all_teams

log = get_logger(__name__)


async def run_daily_rollup() -> dict:
    produced = rollup_all_teams("daily", date.today())
    log.info("daily_rollup_completed", count=len(produced))
    return {"status": "ok", "produced": produced}
