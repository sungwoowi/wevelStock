"""Weekly rollup — Sunday 23:55 by default."""
from __future__ import annotations

from datetime import date, timedelta

from core.logging import get_logger
from core.memory.rollup import rollup_all_teams

log = get_logger(__name__)


async def run_weekly_rollup() -> dict:
    # anchor on yesterday so "this week" is fully closed
    anchor = date.today() - timedelta(days=1)
    produced = rollup_all_teams("weekly", anchor)
    log.info("weekly_rollup_completed", count=len(produced))
    return {"status": "ok", "produced": produced}
