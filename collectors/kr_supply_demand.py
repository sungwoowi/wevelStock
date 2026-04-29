"""Korean market supply/demand — foreign / institution net flow per market.

Uses KIS `market_investor_summary()` which aggregates foreign-institution-top
ranking for KOSPI (0001) and KOSDAQ (1001). Sums are over top-30 by net
amount, not the entire market — labeled accordingly.

Returned shape:
{
    "kospi":  {
        "foreign_net_amount_m_sum":     int,  # 백만원
        "institution_net_amount_m_sum": int,
        "fin_invest_net_amount_m_sum":  int,
        "top_foreign_buys":  [up to 5],
        "top_foreign_sells": [up to 5],
        "count": 30,
    },
    "kosdaq": { ... same shape ... },
    "note":   "상위 30개 합산 기준. 시장 전체 정확한 합계 아님.",
    "source": "kis",
    "fetched_at": "...",
}
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from connectors.kis import KISClient
from core.logging import get_logger

log = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")


async def _fetch_inner(kis: KISClient) -> dict[str, Any]:
    summary = await kis.market_investor_summary()
    # `market_investor_summary` already shapes per-market aggregates.
    # Lift the inner aggregated dicts up so the consumer sees flat shape.
    return {
        "kospi": {
            **summary.get("kospi", {}).get("aggregated", {}),
            "top_30_raw": summary.get("kospi", {}).get("top_30_raw", []),
        },
        "kosdaq": {
            **summary.get("kosdaq", {}).get("aggregated", {}),
            "top_30_raw": summary.get("kosdaq", {}).get("top_30_raw", []),
        },
        "note": summary.get("note", ""),
        "source": "kis",
        "fetched_at": datetime.now(_KST).isoformat(timespec="seconds"),
    }


async def fetch_kr_supply_demand(kis: KISClient | None = None) -> dict[str, Any]:
    """Fetch KOSPI/KOSDAQ foreign+institution net-flow summary.

    Two KIS calls (foreign-institution-total for KOSPI + KOSDAQ).
    With 1s rate limit ~ 2s.
    """
    if kis is None:
        async with KISClient() as own:
            result = await _fetch_inner(own)
    else:
        result = await _fetch_inner(kis)

    log.info(
        "kr_supply_demand_collected",
        kospi_foreign_m=result["kospi"].get("foreign_net_amount_m_sum"),
        kosdaq_foreign_m=result["kosdaq"].get("foreign_net_amount_m_sum"),
    )
    return result
