"""fundamentals 주간 refresh job (INFRA-FUNDAMENTAL-DATA-001).

일요일 18:00 KST cron 발동 → KR_NAME_TO_TICKER 35종 + DB distinct ticker
union 모두 yfinance fetch + DB upsert.
SPEC § 8 명세. 자세한 로직은 `collectors.fundamentals.refresh_all_tickers`.
"""
from __future__ import annotations

from typing import Any

from core.logging import get_logger

log = get_logger(__name__)


async def run_fundamentals_refresh() -> dict[str, Any]:
    """일요일 18:00 KST cron entrypoint. APScheduler 가 호출."""
    from collectors.fundamentals import refresh_all_tickers

    log.info("fundamentals_refresh_cron_start")
    try:
        result = await refresh_all_tickers()
        log.info(
            "fundamentals_refresh_cron_done",
            refreshed=len(result.get("refreshed", [])),
            failed=len(result.get("failed", [])),
            elapsed_s=result.get("elapsed_s"),
        )
        return result
    except Exception as e:  # noqa: BLE001
        log.exception("fundamentals_refresh_cron_failed", error=str(e))
        return {"refreshed": [], "failed": [], "error": str(e)}
