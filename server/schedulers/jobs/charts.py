"""chart_ohlcv 일일 refresh job (INFRA-CHART-DATA-001).

평일 18:00 KST cron 발동 → DB chart_ohlcv 의 distinct ticker 모두 KIS daily fetch.
SPEC § 7 명세. 자세한 로직은 `collectors.charts.refresh_all_tickers`.
"""
from __future__ import annotations

from typing import Any

from core.logging import get_logger

log = get_logger(__name__)


async def run_chart_refresh() -> dict[str, Any]:
    """평일 18:00 KST cron entrypoint. APScheduler 가 호출."""
    from collectors.charts import refresh_all_tickers

    log.info("chart_refresh_cron_start")
    try:
        result = await refresh_all_tickers()
        log.info(
            "chart_refresh_cron_done",
            refreshed=len(result.get("refreshed", [])),
            failed=len(result.get("failed", [])),
            elapsed_s=result.get("elapsed_s"),
        )
        return result
    except Exception as e:  # noqa: BLE001
        log.exception("chart_refresh_cron_failed", error=str(e))
        return {"refreshed": [], "failed": [], "error": str(e)}
