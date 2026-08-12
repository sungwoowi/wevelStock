"""snapshot 매크로 일간 refresh job (INFRA-SNAPSHOT-EXTEND-001 + MARKET-VIEW-SYNTHESIS-001
+ INFRA-US-MACRO-SNAPSHOT-001).

평일 18:05 KST cron 발동:
1. refresh_supply_demand_today() — KIS 5주체 EOD fetch + supply_demand_history 2 row upsert
2. refresh_market_macro_all() — KOSPI/KOSDAQ 시장매크로 4축 계산 + market_macro_snapshot 2 row upsert
3. refresh_us_macro() — 미장 야간 6 지표 fetch + risk-on/off 분류 + us_macro_snapshot 1 row upsert
   (yfinance 재사용). market_view 보다 앞 — build_market_view 가 us_macro DB-hit 하도록.
4. build_market_view("KOSPI") — 섹터 RS + 시장관 종합 일자 스냅샷 적재 (us_macro 흡수 포함)
   (sector_rs_snapshot + market_view_snapshot). 순환매(rotation)는 *이동* 이라
   다일 누적이 선행이어야 활성화 → 이 일일 적재가 prev 윈도우를 쌓는다 (LB-MS2 운영 ramp).

순차 실행 (KIS rate limit 안전 + market_macro 계산이 supply 적재 후 가능 + us_macro 가 market_view
앞 + market_view 는 macro·us_macro DB-hit 가능하도록 맨 뒤). ON CONFLICT REPLACE 멱등 — 실패 시
다음 평일 재시도 안전. 각 단계는 독립 try/except 로 격리 (한 단계 실패가 다음 단계를 막지 않음).
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
    from collectors.us_macro import refresh_us_macro

    started = time.monotonic()
    log.info("snapshot_macro_refresh_cron_start")

    supply_result: dict[str, Any] = {}
    macro_result: dict[str, Any] = {}
    us_macro_result: dict[str, Any] = {}
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

    # 3단계: us_macro 적재 (미장 야간 6 지표 + risk-on/off 분류). market_view 앞 — DB-hit 시키려고.
    try:
        us_macro_result = await refresh_us_macro()
        log.info(
            "snapshot_macro_us_macro_done",
            risk_signal=us_macro_result.get("risk_signal"),
            extreme=us_macro_result.get("extreme"),
            source=us_macro_result.get("source"),
        )
    except Exception as e:  # noqa: BLE001
        log.exception("snapshot_macro_us_macro_failed", error=str(e))
        us_macro_result = {"error": str(e)}

    # 3.5단계: 섹터 RS 양 시장 적재 (ADVISOR-CORE-001 M1-c).
    #   그전엔 KOSPI 만 적재돼 코스닥이 더 강한 국면에서도 코스닥 섹터를 못 봤다.
    #   build_market_view 보다 **앞** — view 가 load_sector_rs_snapshot 으로 DB-hit 하도록.
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from collectors.sector_rs import refresh_sector_rs_all_markets

        today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
        rs_markets = await refresh_sector_rs_all_markets(today)
        log.info("snapshot_macro_sector_rs_done", markets=rs_markets)
    except Exception as e:  # noqa: BLE001 — 섹터 RS 실패가 나머지 단계를 막지 않음
        log.warning("snapshot_macro_sector_rs_failed", error=str(e))

    # 4단계: market_view 종합 적재 (sector_rs_snapshot + market_view_snapshot, us_macro 흡수 포함).
    #   순환매 다일 누적의 일일 적재 지점 (LB-MS2 운영 ramp).
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
        us_macro_ok="error" not in us_macro_result,
        market_view_ok="error" not in market_view_result,
    )
    return {
        "supply": supply_result,
        "market_macro": macro_result,
        "us_macro": us_macro_result,
        "market_view": market_view_result,
        "elapsed_s": round(elapsed, 2),
    }
