"""Gap filler — runs on server boot to detect missed days and backfill.

Initial implementation is a stub: it updates last_snapshot.json to today
and logs any detected gap. Full backfill (KIS/FRED historical fetch) happens
when MCP servers are in place.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from core.logging import get_logger

log = get_logger(__name__)

SNAPSHOT_PATH = Path("data/snapshots/last_snapshot.json")


async def run_gap_filler() -> dict:
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    today = date.today()

    if not SNAPSHOT_PATH.exists():
        log.info("first_boot_no_snapshot")
        SNAPSHOT_PATH.write_text(json.dumps({"last_run_date": today.isoformat()}), encoding="utf-8")
        return {"status": "first_boot"}

    try:
        snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        last = date.fromisoformat(snap.get("last_run_date", today.isoformat()))
    except (json.JSONDecodeError, ValueError):
        log.warning("snapshot_corrupt")
        SNAPSHOT_PATH.write_text(json.dumps({"last_run_date": today.isoformat()}), encoding="utf-8")
        return {"status": "snapshot_reset"}

    gap_days = (today - last).days
    if gap_days <= 0:
        return {"status": "no_gap"}
    if gap_days > 0:
        log.info("gap_detected", days=gap_days, last_run=last.isoformat())

    # Stub: would call KIS/FRED MCP for historical data here
    missing = [(last + timedelta(days=i + 1)).isoformat() for i in range(gap_days)]
    SNAPSHOT_PATH.write_text(
        json.dumps({
            "last_run_date": today.isoformat(),
            "previous_gap_days": gap_days,
            "filled_dates": missing,
            "note": "stub — integrate KIS/FRED MCP to actually backfill",
        }),
        encoding="utf-8",
    )
    return {"status": "ok", "gap_days": gap_days, "dates": missing}
