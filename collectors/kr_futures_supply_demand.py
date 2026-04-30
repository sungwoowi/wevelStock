"""KOSPI200 선물 시장 투자자 수급 — KRX 메인 위젯 backend.

KIS OpenAPI 가 선물 시장 투자자별 매매동향을 노출하지 않아 KRX 정보데이터시스템
(data.krx.co.kr) 의 메인 위젯 backend 를 사용. 단위 십억원, 3주체 (개인/외인/기관).

Returned shape:
{
    "trade_date": "20260430",
    "individual_net_amount_b": int,   # 개인 순매수 (십억원)
    "foreign_net_amount_b": int,
    "institution_net_amount_b": int,
    "fetched_at_krx": "2026.04.30 PM 11:05:36",
    "source": "krx",
    "fetched_at": "...",
}
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from connectors.krx import KRXClient
from core.logging import get_logger

log = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")


async def fetch_kr_futures_supply_demand(
    krx: KRXClient | None = None,
) -> dict[str, Any]:
    """Fetch KOSPI200 futures whole-market investor flow (3 categories)."""
    if krx is None:
        async with KRXClient() as own:
            data = await own.k200_futures_investor_today()
    else:
        data = await krx.k200_futures_investor_today()

    data["fetched_at"] = datetime.now(_KST).isoformat(timespec="seconds")
    log.info(
        "kr_futures_supply_demand_collected",
        trade_date=data.get("trade_date"),
        foreign_b=data.get("foreign_net_amount_b"),
    )
    return data
