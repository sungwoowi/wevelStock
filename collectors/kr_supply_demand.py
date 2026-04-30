"""Korean market supply/demand — whole-market investor net flow per market.

Uses KIS `market_investor_total()` (inquire-investor-time-by-market,
FHPTJ04030000) which returns one cumulative row per market covering ALL
investor categories — not a top-N aggregate. 5 categories surfaced:
개인 / 외인 / 기관 / 금투 / 연기금.

Returned shape:
{
    "kospi": {
        "individual_net_amount_m":  int,  # 개인  (백만원)
        "foreign_net_amount_m":     int,  # 외인
        "institution_net_amount_m": int,  # 기관 (합계, 금투+투신+보험+연기금+기타)
        "fin_invest_net_amount_m":  int,  # 금투 (증권사 자기매매)
        "pension_net_amount_m":     int,  # 연기금 (KIS fund)
    },
    "kosdaq": { ... same shape ... },
    "note":   "시장 전체 누적 (KIS inquire-investor-time-by-market).",
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
    kospi = await kis.market_investor_total("kospi")
    kosdaq = await kis.market_investor_total("kosdaq")
    return {
        "kospi": kospi,
        "kosdaq": kosdaq,
        "note": "시장 전체 누적 (KIS inquire-investor-time-by-market).",
        "source": "kis",
        "fetched_at": datetime.now(_KST).isoformat(timespec="seconds"),
    }


async def fetch_kr_supply_demand(kis: KISClient | None = None) -> dict[str, Any]:
    """Fetch KOSPI/KOSDAQ whole-market investor flow (5 categories).

    Two KIS calls (inquire-investor-time-by-market for KOSPI + KOSDAQ).
    With 1.1s rate limit ~ 2.2s.
    """
    if kis is None:
        async with KISClient() as own:
            result = await _fetch_inner(own)
    else:
        result = await _fetch_inner(kis)

    log.info(
        "kr_supply_demand_collected",
        kospi_foreign_m=result["kospi"].get("foreign_net_amount_m"),
        kosdaq_foreign_m=result["kosdaq"].get("foreign_net_amount_m"),
    )
    return result
