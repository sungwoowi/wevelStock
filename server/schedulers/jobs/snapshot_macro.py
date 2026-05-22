"""snapshot 매크로 일간 refresh job (INFRA-SNAPSHOT-EXTEND-001).

평일 18:00 KST cron 발동:
1. refresh_supply_demand_today() — KIS 5주체 EOD fetch + supply_demand_history 2 row upsert
2. refresh_market_macro_all() — KOSPI/KOSDAQ 시장매크로 4축 계산 + market_macro_snapshot 2 row upsert

순차 실행 (KIS rate limit 안전 + market_macro 계산이 supply 적재 후 가능하도록).
SPEC § 10 명세. ON CONFLICT REPLACE 멱등 — 실패 시 다음 평일 재시도 안전.
"""
from __future__ import annotations

import time
from typing import Any

from core.logging import get_logger

log = get_logger(__name__)


async def run_snapshot_macro_refresh() -> dict[str, Any]:
    """평일 18:00 KST cron entrypoint. APScheduler 가 호출.

    Returns:
        {
          "supply": {"refreshed": [...], "failures": [...]},
          "market_macro": {"refreshed": [...], "failures": [...]},
          "elapsed_s": float,
        }
    """
    from collectors.market_macro import refresh_market_macro_all
    from collectors.supply_demand_history import refresh_supply_demand_today

    started = time.monotonic()
    log.info("snapshot_macro_refresh_cron_start")

    supply_result: dict[str, Any] = {}
    macro_result: dict[str, Any] = {}

    # 1단계: supply 적재 (KIS 5주체 EOD)
    try:
        supply_result = await refresh_supply_demand_today()
        log.info(
            "snapshot_macro_supply_done",
            refreshed=supply_result.get("refreshed", []),
            failures=supply_result.get("failures", []),
        )
    except Exception as e:  # noqa: BLE001
        log.exception("snapshot_macro_supply_failed", error=str(e))
        supply_result = {"refreshed": [], "failures": [{"error": str(e)}]}

    # 2단계: market_macro 계산 (chart_ohlcv + KRX breadth)
    try:
        macro_result = await refresh_market_macro_all()
        log.info(
            "snapshot_macro_market_done",
            refreshed=macro_result.get("refreshed", []),
            failures=macro_result.get("failures", []),
        )
    except Exception as e:  # noqa: BLE001
        log.exception("snapshot_macro_market_failed", error=str(e))
        macro_result = {"refreshed": [], "failures": [{"error": str(e)}]}

    elapsed = time.monotonic() - started
    log.info(
        "snapshot_macro_refresh_cron_done",
        elapsed_s=round(elapsed, 2),
        supply_ok=len(supply_result.get("refreshed", [])),
        macro_ok=len(macro_result.get("refreshed", [])),
    )
    return {
        "supply": supply_result,
        "market_macro": macro_result,
        "elapsed_s": round(elapsed, 2),
    }
