"""Korean market indices — KOSPI / KOSDAQ via KIS OpenAPI.

Returned shape:
{
    "kospi":  {value, change, change_pct, volume, trade_amount} | {error},
    "kosdaq": {...},
    "source": "kis",
    "fetched_at": "ISO-8601 KST",
}

All numeric values are pre-cleaned (KIS string responses parsed to int/float).
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
    kospi = await kis.index_price("0001")
    kosdaq = await kis.index_price("1001")
    # KOSPI200 — 코스피 선물의 기초지수. 선물 본 가격은 KIS 선물옵션 API 별도.
    kospi200 = await kis.index_price("2001")
    return {
        "kospi": kospi,
        "kosdaq": kosdaq,
        "kospi200": kospi200,
        "source": "kis",
        "fetched_at": datetime.now(_KST).isoformat(timespec="seconds"),
    }


async def fetch_kr_indices(kis: KISClient | None = None) -> dict[str, Any]:
    """Fetch KOSPI + KOSDAQ + KOSPI200 index snapshots.

    Pass an existing KISClient to share token + rate limit; otherwise a
    short-lived client is created. Three API calls (~3.5s with 1.1s rate limit).
    """
    if kis is None:
        async with KISClient() as own:
            result = await _fetch_inner(own)
    else:
        result = await _fetch_inner(kis)

    log.info(
        "kr_indices_collected",
        kospi=result["kospi"].get("value"),
        kosdaq=result["kosdaq"].get("value"),
        kospi200=result["kospi200"].get("value"),
    )
    return result
