"""Register pipeline/team schedules from manifest.yaml files."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pipeline runner (new)
# ---------------------------------------------------------------------------

async def _run_pipeline(pipeline_id: str) -> None:
    """Invoked by APScheduler — run a pipeline."""
    from datetime import datetime, timezone
    from uuid import uuid4

    from pipelines._base import PipelineRunner
    from pipelines._registry import get_pipeline

    manifest = get_pipeline(pipeline_id)
    if manifest is None:
        log.error("scheduled_pipeline_not_found", pipeline=pipeline_id)
        return

    run_id = f"{datetime.now(timezone.utc).isoformat()}#sched-{uuid4().hex[:6]}"
    runner = PipelineRunner()
    try:
        result = await runner.run(manifest, run_id=run_id)
        log.info(
            "scheduled_pipeline_complete",
            pipeline=pipeline_id,
            ok=result.ok,
            verdict=result.final_verdict,
        )
    except Exception as e:  # noqa: BLE001
        log.error("scheduled_pipeline_failed", pipeline=pipeline_id, error=str(e))


# ---------------------------------------------------------------------------
# Trigger builder (shared)
# ---------------------------------------------------------------------------

def _build_trigger(schedule: dict):
    trigger = schedule.get("trigger") if isinstance(schedule, dict) else getattr(schedule, "trigger", None)

    if trigger == "cron":
        expr = schedule.get("expr") if isinstance(schedule, dict) else getattr(schedule, "expr", None)
        tz = schedule.get("timezone") if isinstance(schedule, dict) else getattr(schedule, "timezone", None)
        if not expr:
            return None
        parts = expr.split()
        if len(parts) != 5:
            return None
        minute, hour, dom, month, dow = parts
        return CronTrigger(
            minute=minute, hour=hour, day=dom, month=month, day_of_week=dow,
            timezone=tz or "Asia/Seoul",
        )
    if trigger == "interval":
        hours = schedule.get("hours", 0) if isinstance(schedule, dict) else getattr(schedule, "hours", 0) or 0
        minutes = schedule.get("minutes", 0) if isinstance(schedule, dict) else getattr(schedule, "minutes", 0) or 0
        seconds = schedule.get("seconds", 0) if isinstance(schedule, dict) else getattr(schedule, "seconds", 0) or 0
        if not (hours or minutes or seconds):
            return None
        return IntervalTrigger(hours=hours, minutes=minutes, seconds=seconds)
    return None


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_pipeline_schedules(scheduler: AsyncIOScheduler) -> int:
    """Register schedules from pipeline manifests. Returns count registered."""
    from pipelines._registry import list_active_pipelines

    count = 0
    for pipeline in list_active_pipelines():
        for idx, sched in enumerate(pipeline.schedule):
            t = _build_trigger(sched)
            if t is None:
                continue
            job_id = f"pipeline::{pipeline.id}::{idx}"
            scheduler.add_job(
                _run_pipeline,
                trigger=t,
                args=[pipeline.id],
                id=job_id,
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            log.info("pipeline_schedule_registered", job=job_id, pipeline=pipeline.id)
            count += 1
    return count


# Backward compat alias
def register_team_schedules(scheduler: AsyncIOScheduler) -> int:
    """Legacy — now delegates to pipeline schedules."""
    return register_pipeline_schedules(scheduler)
