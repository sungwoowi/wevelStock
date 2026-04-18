"""Monthly rollup — last day of each month."""
from __future__ import annotations

from datetime import date

from core.logging import get_logger
from core.memory.rollup import rollup_all_teams

log = get_logger(__name__)


async def run_monthly_rollup() -> dict:
    produced = rollup_all_teams("monthly", date.today())
    log.info("monthly_rollup_completed", count=len(produced))
    return {"status": "ok", "produced": produced}
