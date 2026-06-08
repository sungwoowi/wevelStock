"""Infrastructure jobs (not tied to any single team)."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.config import get_config
from core.logging import get_logger

from server.schedulers.jobs.backup import run_backup
from server.schedulers.jobs.charts import run_chart_refresh
from server.schedulers.jobs.daily_refresh import run_daily_refresh
from server.schedulers.jobs.daily_rollup import run_daily_rollup
from server.schedulers.jobs.fundamentals import run_fundamentals_refresh
from server.schedulers.jobs.memory_cleanup import run_memory_cleanup
from server.schedulers.jobs.monthly_rollup import run_monthly_rollup
from server.schedulers.jobs.news_ingest import run_news_ingest
from server.schedulers.jobs.snapshot_macro import run_snapshot_macro_refresh
from server.schedulers.jobs.weekly_rollup import run_weekly_rollup

log = get_logger(__name__)


def _cron_from_expr(expr: str, tz: str = "Asia/Seoul") -> CronTrigger:
    m, h, dom, mo, dow = expr.split()
    return CronTrigger(minute=m, hour=h, day=dom, month=mo, day_of_week=dow, timezone=tz)


def register_infra_jobs(scheduler: AsyncIOScheduler) -> int:
    cfg = get_config().scheduler
    tz = get_config().timezone
    registered = 0
    if cfg.backup.cron:
        scheduler.add_job(run_backup, _cron_from_expr(cfg.backup.cron, tz), id="infra::backup")
        registered += 1
    if cfg.daily_rollup.cron:
        scheduler.add_job(run_daily_rollup, _cron_from_expr(cfg.daily_rollup.cron, tz), id="infra::daily_rollup")
        registered += 1
    if cfg.weekly_rollup.cron:
        scheduler.add_job(run_weekly_rollup, _cron_from_expr(cfg.weekly_rollup.cron, tz), id="infra::weekly_rollup")
        registered += 1
    if cfg.monthly_rollup.day:
        scheduler.add_job(
            run_monthly_rollup,
            CronTrigger(
                day=str(cfg.monthly_rollup.day),
                hour=cfg.monthly_rollup.hour or 23,
                minute=cfg.monthly_rollup.minute or 58,
                timezone=tz,
            ),
            id="infra::monthly_rollup",
        )
        registered += 1
    if cfg.memory_cleanup.day:
        scheduler.add_job(
            run_memory_cleanup,
            CronTrigger(
                day=str(cfg.memory_cleanup.day),
                hour=cfg.memory_cleanup.hour or 3,
                minute=cfg.memory_cleanup.minute or 0,
                timezone=tz,
            ),
            id="infra::memory_cleanup",
        )
        registered += 1
    # INFRA-CHART-DATA-001 — 평일 18:00 KST chart_ohlcv refresh (config 불필요, 고정 cron)
    scheduler.add_job(
        run_chart_refresh,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=0, timezone=tz),
        id="infra::chart_ohlcv_refresh",
        replace_existing=True,
    )
    registered += 1
    # INFRA-FUNDAMENTAL-DATA-001 — 일요일 18:00 KST fundamentals refresh (config 불필요, 고정 cron)
    scheduler.add_job(
        run_fundamentals_refresh,
        CronTrigger(day_of_week="sun", hour=18, minute=0, timezone=tz),
        id="infra::fundamentals_refresh",
        replace_existing=True,
    )
    registered += 1
    # 평일 18:05 KST 일일 적재 통합 허브 (고정 cron). macro(snapshot_macro 4단계) + 뉴스 합류.
    # chart_ohlcv refresh(18:00) 뒤라 순차 실행 (KIS rate limit 안전 / 본 job 가 후순위).
    # cron·CLI(`just refresh-daily`)·endpoint(POST /api/infra/refresh-snapshots) 가 동일 호출점 공유.
    scheduler.add_job(
        run_daily_refresh,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=5, timezone=tz),
        id="infra::daily_refresh",
        replace_existing=True,
    )
    registered += 1
    log.info("infra_jobs_registered", count=registered)
    return registered


__all__ = ["register_infra_jobs", "run_backup", "run_daily_rollup", "run_weekly_rollup",
           "run_monthly_rollup", "run_memory_cleanup", "run_chart_refresh",
           "run_fundamentals_refresh", "run_snapshot_macro_refresh", "run_news_ingest",
           "run_daily_refresh"]
