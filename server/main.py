"""FastAPI entrypoint — uvicorn server.main:app

Combines REST API + APScheduler + config watchdog + Telegram bot in one process.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_config, start_watcher, stop_watcher
from core.db import get_db
from core.logging import get_logger
from core.scheduler import get_scheduler, shutdown_scheduler

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup + shutdown hooks."""
    log.info("server_starting")

    # 1. Load config (triggers validation + starts watchdog)
    cfg = get_config()
    start_watcher()

    # 2. Initialize DB
    get_db()
    log.info("db_ready", path=cfg.database.path)

    # 3. Schedulers (infra jobs + pipeline schedules)
    sched = get_scheduler()
    try:
        from server.schedulers.loader import register_pipeline_schedules
        from server.schedulers.jobs import register_infra_jobs
        register_infra_jobs(sched)
        register_pipeline_schedules(sched)
        sched.start()
        log.info("scheduler_started", jobs=len(sched.get_jobs()))
    except Exception as e:  # noqa: BLE001
        log.error("scheduler_init_failed", error=str(e))

    # 4. Gap filler (fire-and-forget on boot)
    try:
        from server.schedulers.jobs.gap_filler import run_gap_filler

        await run_gap_filler()
    except Exception as e:  # noqa: BLE001
        log.warning("gap_filler_failed", error=str(e))

    # 5. Knowledge watcher (KNOWLEDGE-SYNC-001 Phase 2 M3) — reference/** 변경 감지 + 60s debounce.
    # 절전모드/서버 다운 중에 변경된 자료를 catchup 하기 위해 startup 시 1회 reconcile (fire-and-forget).
    knowledge_observer = None
    reconcile_task: asyncio.Task | None = None
    try:
        from core.knowledge.watcher import start_observer

        knowledge_observer = start_observer()

        async def _knowledge_reconcile() -> None:
            try:
                from core.knowledge.sync import sync_all

                await asyncio.to_thread(sync_all)
                log.info("knowledge_reconcile_done")
            except Exception as e:  # noqa: BLE001
                log.warning("knowledge_reconcile_failed", error=str(e))

        reconcile_task = asyncio.create_task(_knowledge_reconcile())
    except Exception as e:  # noqa: BLE001
        log.warning("knowledge_watcher_init_failed", error=str(e))

    # 6. Telegram bot (BRIEFING-ON-DEMAND-001) — long-polling task.
    # 토큰 미설정 시 build_application() 이 None 반환하여 봇만 비활성.
    bot_task: asyncio.Task | None = None
    try:
        from server.telegram import build_application, run_polling_forever

        bot_app = build_application()
        if bot_app is not None:
            bot_task = asyncio.create_task(run_polling_forever(bot_app))
    except Exception as e:  # noqa: BLE001
        log.warning("telegram_bot_init_failed", error=str(e))

    log.info("server_ready", host=cfg.server.host, port=cfg.server.port)
    yield

    log.info("server_stopping")
    if bot_task is not None:
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass
        except Exception as e:  # noqa: BLE001
            log.warning("telegram_bot_shutdown_failed", error=str(e))
    if reconcile_task is not None and not reconcile_task.done():
        reconcile_task.cancel()
        try:
            await reconcile_task
        except asyncio.CancelledError:
            pass
        except Exception as e:  # noqa: BLE001
            log.warning("knowledge_reconcile_shutdown_failed", error=str(e))
    if knowledge_observer is not None:
        try:
            from core.knowledge.watcher import stop_observer

            stop_observer(knowledge_observer)
        except Exception as e:  # noqa: BLE001
            log.warning("knowledge_watcher_stop_failed", error=str(e))
    shutdown_scheduler()
    stop_watcher()


app = FastAPI(title="wevelStock", version="0.1.0", lifespan=lifespan)

# CORS for the webapp
try:
    _allowed = get_config().server.cors.allowed_origins
except Exception:
    _allowed = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
from server.api import accounts as accounts_route  # noqa: E402
from server.api import analyst_chat as analyst_chat_route  # noqa: E402
from server.api import briefings as briefings_route  # noqa: E402
from server.api import briefings_on_demand as briefings_on_demand_route  # noqa: E402
from server.api import config as config_route  # noqa: E402
from server.api import infra as infra_route  # noqa: E402
from server.api import notifications as notif_route  # noqa: E402
from server.api import pipelines as pipelines_route  # noqa: E402
from server.api import positions as positions_route  # noqa: E402
from server.api import production_chat as production_chat_route  # noqa: E402
from server.api import strategist_chat as strategist_chat_route  # noqa: E402
from server.api import teams as teams_route  # noqa: E402

app.include_router(pipelines_route.router, prefix="/api", tags=["pipelines"])
app.include_router(teams_route.router, prefix="/api", tags=["teams"])
app.include_router(config_route.router, prefix="/api", tags=["config"])
app.include_router(notif_route.router, prefix="/api", tags=["notifications"])
app.include_router(briefings_route.router, prefix="/api", tags=["briefings"])
app.include_router(
    briefings_on_demand_route.router, prefix="/api", tags=["briefings-on-demand"]
)
app.include_router(positions_route.router, prefix="/api", tags=["positions"])
app.include_router(analyst_chat_route.router, prefix="/api", tags=["analysts"])
app.include_router(strategist_chat_route.router, prefix="/api", tags=["strategists"])
app.include_router(production_chat_route.router, prefix="/api", tags=["production-chat"])
app.include_router(infra_route.router, prefix="/api", tags=["infra"])
app.include_router(accounts_route.router, prefix="/api", tags=["accounts"])


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "repo_root": str(Path(__file__).resolve().parents[1])}


@app.get("/")
async def root() -> dict:
    return {"name": "wevelStock", "docs": "/docs", "api": "/api/pipelines"}
