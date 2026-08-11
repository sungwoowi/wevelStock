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
from core.signal.market_stance import FUTURES_MARKET

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
    persist_futures_supply_demand(data)
    log.info(
        "kr_futures_supply_demand_collected",
        trade_date=data.get("trade_date"),
        foreign_b=data.get("foreign_net_amount_b"),
    )
    return data


def persist_futures_supply_demand(data: dict[str, Any]) -> bool:
    """선물 3주체 수급 영속 (ADVISOR-CORE-001 M1-a).

    지금까지 스냅샷에서 계산만 하고 버려졌다 — 현물↔선물 방향 엇갈림(헤지 청산·반등 대비)
    은 판세의 핵심 신호인데 시계열이 없어 못 봤다.

    저장소 = 기존 `supply_demand_history` 에 `market='K200_FUT'` 행 (가드 #11 — 신규 테이블 0).
    단위 정규화: KRX 십억원 → 백만원 (현물 행과 동일 단위). graceful — 실패해도 수집을 막지 않음.
    """
    from core.db import get_db

    raw_date = str(data.get("trade_date") or "")
    if len(raw_date) != 8 or not raw_date.isdigit():
        return False
    iso = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"

    def _mn(key: str) -> int | None:
        v = data.get(key)
        return int(v) * 1000 if isinstance(v, (int, float)) else None  # 십억 → 백만

    try:
        get_db().execute(
            "INSERT INTO supply_demand_history "
            "(date, market, foreign_net, institution_net, individual_net, "
            " financial_inv_net, pension_net, source) "
            "VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(date, market) DO UPDATE SET "
            "  foreign_net=excluded.foreign_net, institution_net=excluded.institution_net, "
            "  individual_net=excluded.individual_net, source=excluded.source",
            # 선물은 KRX 가 3주체(개인·외인·기관)만 준다. 금융투자·연기금 컬럼은 NOT NULL 이라
            # 0 으로 채우되, market='K200_FUT' 이 "해당 없음"을 명시한다(현물 0 과 혼동 없음).
            (iso, FUTURES_MARKET, _mn("foreign_net_amount_b"),
             _mn("institution_net_amount_b"), _mn("individual_net_amount_b"),
             0, 0, "krx"),
        )
        return True
    except Exception as e:  # noqa: BLE001 — 영속 실패가 스냅샷 빌드를 막지 않음
        log.warning("futures_supply_persist_failed", date=iso, error=str(e))
        return False
