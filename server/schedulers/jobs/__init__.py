"""Infrastructure jobs (not tied to any single team)."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.config import get_config
from core.logging import get_logger

from server.schedulers.jobs.auto_signal import (
    INTRADAY_CADENCES,
    MISFIRE_GRACE_SEC,
    run_auto_signal_job,
)
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


def _news_premarket_cfg() -> dict:
    """config/news_source.yaml premarket 섹션 (하드코딩 금지). 부재 시 기본값."""
    from collectors.news_source import load_news_source_config

    return (load_news_source_config().get("premarket") or {})


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
    # ※ 자동 권고 생성 postclose cadence 는 run_daily_refresh 내부에서 데스크 *앞에* 호출.
    scheduler.add_job(
        run_daily_refresh,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=5, timezone=tz),
        id="infra::daily_refresh",
        replace_existing=True,
        # 절전/단절로 18:05 을 놓쳐도 1h 안에 깨어나면 따라잡음 (postclose 권고 cadence 포함).
        misfire_grace_time=MISFIRE_GRACE_SEC,
        coalesce=True,
        max_instances=1,
    )
    registered += 1

    # NEWS-EVENT-INTERPRETATION-001 M1-b′ (D5) — 장전 06:40 KST 뉴스 ingest (평일).
    #   간밤 미장발 이벤트(메타발 유형)를 수집→분류→격상→해석해 07:00 장전 브리핑과
    #   09:35 장중 회차가 해석된 상태로 읽게 함. 분류=url 캐싱(간밤 신규분만 실비용),
    #   해석=격상 시 0~2콜. 18:05 daily_refresh 의 뉴스 단계와 같은 entrypoint (멱등).
    #   config news_source.yaml premarket 섹션으로 시각·토글 외부화.
    _premarket_cfg = _news_premarket_cfg()
    if _premarket_cfg.get("enabled", True):
        scheduler.add_job(
            run_news_ingest,
            CronTrigger(
                day_of_week="mon-fri",
                hour=int(_premarket_cfg.get("hour", 6)),
                minute=int(_premarket_cfg.get("minute", 40)),
                timezone=tz,
            ),
            id="news_ingest::premarket",
            replace_existing=True,
            misfire_grace_time=MISFIRE_GRACE_SEC,
            coalesce=True,
            max_instances=1,
        )
        registered += 1

    # AUTO-SIGNAL-GENERATION-001 M3 — 장중 자동 권고 생성 (09:35/12:35/14:35 KST 평일).
    #   스냅샷 갱신(market_briefing_now 09:30/12:30/14:30) 직후 = fresh 외인·기관 수급.
    #   마스터 스위치(config signal_gate.auto_run_enabled) OFF 면 잡 자체가 no-op.
    for cadence, hour, minute in INTRADAY_CADENCES:
        scheduler.add_job(
            run_auto_signal_job,
            CronTrigger(day_of_week="mon-fri", hour=hour, minute=minute, timezone=tz),
            id=f"auto_signal::{cadence}",
            args=[cadence],
            replace_existing=True,
            # 절전/단절로 cadence 시각을 놓쳐도 1h 안에 깨어나면 따라잡음 (2026-06-15 사고 보강).
            misfire_grace_time=MISFIRE_GRACE_SEC,
            coalesce=True,
            max_instances=1,
        )
        registered += 1

    log.info("infra_jobs_registered", count=registered)
    return registered


__all__ = ["register_infra_jobs", "run_backup", "run_daily_rollup", "run_weekly_rollup",
           "run_monthly_rollup", "run_memory_cleanup", "run_chart_refresh",
           "run_fundamentals_refresh", "run_snapshot_macro_refresh", "run_news_ingest",
           "run_daily_refresh"]
