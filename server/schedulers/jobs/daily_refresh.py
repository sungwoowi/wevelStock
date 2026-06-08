"""일일 적재 통합 entrypoint (dev cron 미작동 부채 해소).

문제: APScheduler 가 FastAPI lifespan 내부에만 살아 있어(server/main.py) 서버 미상주 시
18:05 허브가 미발동 → us_macro/sector_rs/chart/뉴스 다일 누적이 막힌다.

해결: 18:05 cron · CLI(`just refresh-daily`) · 수동 endpoint(POST /api/infra/refresh-snapshots)
**세 surface 가 모두 이 단일 run_daily_refresh() 를 호출**. dev 머신은 Windows 작업 스케줄러가
평일 `just refresh-daily` 를 돌리면 서버와 무관하게 누적이 이어진다.

구성:
  1. run_snapshot_macro_refresh() — 기존 4 macro 단계(supply→market_macro→us_macro→market_view, 무변경)
  2. run_news_ingest() — 뉴스 수집·분류·집계 (NEWS-SOURCE-001 일일 cron 합류)

각 서브잡은 독립 try/except 로 격리(한 잡 실패가 다른 잡을 막지 않음). 모든 하위 refresh 가
ON CONFLICT REPLACE 멱등이라 하루 여러 번 호출해도 안전.
"""
from __future__ import annotations

import time
from typing import Any

from core.logging import get_logger

log = get_logger(__name__)


async def run_daily_refresh() -> dict[str, Any]:
    """일일 적재 단일 호출점. cron/CLI/endpoint 공용.

    Returns:
        {
          "snapshot_macro": {...} 또는 {"error": ...},
          "news": {...} 또는 {"error": ...},
          "elapsed_s": float,
        }
    """
    from server.schedulers.jobs.news_ingest import run_news_ingest
    from server.schedulers.jobs.snapshot_macro import run_snapshot_macro_refresh

    started = time.monotonic()
    log.info("daily_refresh_start")

    snapshot_result: dict[str, Any] = {}
    news_result: dict[str, Any] = {}

    # 1단계: macro 허브 (supply→market_macro→us_macro→market_view). 자체 내부 격리 보유.
    try:
        snapshot_result = await run_snapshot_macro_refresh()
    except Exception as e:  # noqa: BLE001
        log.exception("daily_refresh_snapshot_macro_failed", error=str(e))
        snapshot_result = {"error": str(e)}

    # 2단계: 뉴스 일일 적재 (수집→분류→집계). 자체 내부 격리 보유.
    try:
        news_result = await run_news_ingest()
    except Exception as e:  # noqa: BLE001
        log.exception("daily_refresh_news_failed", error=str(e))
        news_result = {"error": str(e)}

    elapsed = time.monotonic() - started
    log.info(
        "daily_refresh_done",
        elapsed_s=round(elapsed, 2),
        snapshot_ok="error" not in snapshot_result,
        news_ok="error" not in news_result,
    )
    return {
        "snapshot_macro": snapshot_result,
        "news": news_result,
        "elapsed_s": round(elapsed, 2),
    }
