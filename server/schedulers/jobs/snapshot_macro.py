"""snapshot 매크로 일간 refresh job (INFRA-SNAPSHOT-EXTEND-001 + MARKET-VIEW-SYNTHESIS-001).

평일 18:05 KST cron 발동:
1. refresh_supply_demand_today() — KIS 5주체 EOD fetch + supply_demand_history 2 row upsert
2. refresh_market_macro_all() — KOSPI/KOSDAQ 시장매크로 4축 계산 + market_macro_snapshot 2 row upsert
3. build_market_view("KOSPI") — 섹터 RS + 시장관 종합 일자 스냅샷 적재
   (sector_rs_snapshot + market_view_snapshot). 순환매(rotation)는 *이동* 이라
   다일 누적이 선행이어야 활성화 → 이 일일 적재가 prev 윈도우를 쌓는다 (LB-MS2 운영 ramp).

순차 실행 (KIS rate limit 안전 + market_macro 계산이 supply 적재 후 가능 + market_view 는
macro DB-hit 가능하도록 맨 뒤). ON CONFLICT REPLACE 멱등 — 실패 시 다음 평일 재시도 안전.
각 단계는 독립 try/except 로 격리 (한 단계 실패가 다음 단계를 막지 않음).
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
          "market_view": {"market": ..., "regime": ..., "rotation": ..., "one_liner": ...}
                         또는 {"error": ...},
          "elapsed_s": float,
        }
    """
    from collectors.market_macro import refresh_market_macro_all
    from collectors.market_view import build_market_view
    from collectors.supply_demand_history import refresh_supply_demand_today

    started = time.monotonic()
    log.info("snapshot_macro_refresh_cron_start")

    supply_result: dict[str, Any] = {}
    macro_result: dict[str, Any] = {}
    market_view_result: dict[str, Any] = {}

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

    # 3단계: market_view 종합 적재 (sector_rs_snapshot + market_view_snapshot).
    #   순환매 다일 누적의 일일 적재 지점 (LB-MS2 운영 ramp). KOSPI 만 (KOSDAQ SLOT).
    try:
        view = await build_market_view("KOSPI", force_refresh=True)
        market_view_result = {
            "market": view.market,
            "regime": view.regime,
            "rotation": view.rotation.direction,
            "rotation_strength": view.rotation.strength,
            "one_liner": view.one_liner,
        }
        log.info(
            "snapshot_macro_market_view_done",
            regime=view.regime,
            rotation=view.rotation.direction,
            strength=view.rotation.strength,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("snapshot_macro_market_view_failed", error=str(e))
        market_view_result = {"error": str(e)}

    elapsed = time.monotonic() - started
    log.info(
        "snapshot_macro_refresh_cron_done",
        elapsed_s=round(elapsed, 2),
        supply_ok=len(supply_result.get("refreshed", [])),
        macro_ok=len(macro_result.get("refreshed", [])),
        market_view_ok="error" not in market_view_result,
    )
    return {
        "supply": supply_result,
        "market_macro": macro_result,
        "market_view": market_view_result,
        "elapsed_s": round(elapsed, 2),
    }
