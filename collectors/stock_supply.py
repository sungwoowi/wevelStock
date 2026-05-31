"""종목 레벨 5주체 수급 collector (INFRA-STOCK-SUPPLY-001).

F-Score 세 축(theme_match·momentum·inflow_speed)을 시장 프록시 → **종목 실측** 승급.
`supply_demand_history.py`(시장 레벨) 1:1 mirror + ticker 축. KRX 종목별 투자자별 거래실적
on-demand 수집 → `stock_supply_history` 캐시. theme_match 골격은 net_sums 입력만 교체(무수정 재사용).

흐름:
  1. `ensure_stock_supply_series(ticker)` — flow_inputs 가 호출. 캐시 sparse 면 60일 백필,
     아니면 당일분만 재-fetch (R3-a). cutoff_date 지정 시 live fetch X (백테스팅 재현).
  2. `load_stock_supply_window(ticker)` — 순수 DB 로드 (정순).
  3. `get_stock_market_cap(ticker)` — KIS 시총(억) → 백만원 (inflow_speed 분모).

미가용(KRX 실패·신규·미장) 시 빈 시계열 → flow_inputs 가 시장 프록시 fallback (R2-a).
agreement_score 는 supply_demand_history 순수 함수 재사용 (신설 0).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from connectors.krx import KRXClient
from core.db import get_db
from core.logging import get_logger
from collectors.supply_demand_history import agreement_score  # 순수 함수 재사용

log = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")
_WINDOW_DAYS = 60
# 60 거래일 ≈ 약 88 달력일. 백필 시 넉넉히 잡아 거래일 60 확보.
_BACKFILL_CALENDAR_DAYS = 95
_REFRESH_CALENDAR_DAYS = 7  # 당일 + 직전 며칠 재-fetch (갭 보정)

_INVESTOR_KEYS = (
    "foreign_net",
    "institution_net",
    "individual_net",
    "financial_inv_net",
    "pension_net",
)


@dataclass
class StockSupplyRow:
    """1 종목 1 일 의 5주체 net 매수액 (백만원)."""

    ticker: str
    date: str
    foreign_net: int
    institution_net: int
    individual_net: int
    financial_inv_net: int
    pension_net: int
    source: str = "krx"


def _today_kst_str() -> str:
    return datetime.now(_KST).strftime("%Y-%m-%d")


def _iso_to_krx(iso: str) -> str:
    """"2026-05-31" → "20260531"."""
    return iso.replace("-", "")


# ---------------------------------------------------------------------------
# DB layer (supply_demand_history.py mirror + ticker)
# ---------------------------------------------------------------------------


def upsert_stock_supply_row(row: StockSupplyRow) -> None:
    """stock_supply_history ON CONFLICT (ticker, date) REPLACE 멱등 upsert."""
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO stock_supply_history "
            "(ticker, date, foreign_net, institution_net, individual_net, "
            " financial_inv_net, pension_net, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(ticker, date) DO UPDATE SET "
            " foreign_net=excluded.foreign_net, "
            " institution_net=excluded.institution_net, "
            " individual_net=excluded.individual_net, "
            " financial_inv_net=excluded.financial_inv_net, "
            " pension_net=excluded.pension_net, "
            " source=excluded.source",
            (
                row.ticker, row.date,
                row.foreign_net, row.institution_net, row.individual_net,
                row.financial_inv_net, row.pension_net, row.source,
            ),
        )


def load_stock_supply_window(ticker: str, *, days: int = _WINDOW_DAYS) -> list[StockSupplyRow]:
    """ticker 의 최근 days 거래일 수급 시계열 (정순: 과거 → 최신)."""
    db = get_db()
    rows = db.fetch_all(
        "SELECT ticker, date, foreign_net, institution_net, individual_net, "
        "       financial_inv_net, pension_net, source "
        "FROM stock_supply_history WHERE ticker = ? "
        "ORDER BY date DESC LIMIT ?",
        (ticker, days),
    )
    items = [
        StockSupplyRow(
            ticker=r["ticker"],
            date=r["date"],
            foreign_net=int(r["foreign_net"]),
            institution_net=int(r["institution_net"]),
            individual_net=int(r["individual_net"]),
            financial_inv_net=int(r["financial_inv_net"]),
            pension_net=int(r["pension_net"]),
            source=r["source"] or "krx",
        )
        for r in rows
    ]
    items.reverse()
    return items


def get_stock_supply_latest_date(ticker: str) -> str | None:
    """stock_supply_history 의 ticker 최신 row date (없으면 None)."""
    db = get_db()
    row = db.fetch_one(
        "SELECT MAX(date) AS last_date FROM stock_supply_history WHERE ticker = ?",
        (ticker,),
    )
    if not row or row["last_date"] is None:
        return None
    return str(row["last_date"])


# ---------------------------------------------------------------------------
# Fetch (KRX) + orchestration
# ---------------------------------------------------------------------------


async def fetch_stock_supply(
    ticker: str,
    *,
    calendar_days: int = _BACKFILL_CALENDAR_DAYS,
    cutoff_date: str | None = None,
    krx: KRXClient | None = None,
) -> int:
    """KRX 종목별 투자자 거래실적 fetch → upsert. 적재 행 수 반환 (오류 시 0).

    end = cutoff_date or today_kst, start = end - calendar_days. cutoff 이후 행 제외.
    """
    end_iso = cutoff_date or _today_kst_str()
    try:
        end_dt = datetime.strptime(end_iso, "%Y-%m-%d")
    except (ValueError, TypeError):
        return 0
    start_iso = (end_dt - timedelta(days=calendar_days)).strftime("%Y-%m-%d")

    async def _do(client: KRXClient) -> int:
        try:
            rows = await client.stock_investor_supply(
                ticker, start_date=_iso_to_krx(start_iso), end_date=_iso_to_krx(end_iso)
            )
        except Exception as e:  # noqa: BLE001
            log.warning("stock_supply_fetch_failed", ticker=ticker, error=str(e))
            return 0
        count = 0
        for r in rows:
            d = r.get("date")
            if not d or (cutoff_date and d > cutoff_date):
                continue
            upsert_stock_supply_row(StockSupplyRow(
                ticker=ticker,
                date=d,
                foreign_net=int(r.get("foreign_net", 0)),
                institution_net=int(r.get("institution_net", 0)),
                individual_net=int(r.get("individual_net", 0)),
                financial_inv_net=int(r.get("financial_inv_net", 0)),
                pension_net=int(r.get("pension_net", 0)),
                source="krx",
            ))
            count += 1
        return count

    if krx is None:
        async with KRXClient() as own:
            return await _do(own)
    return await _do(krx)


async def ensure_stock_supply_series(
    ticker: str,
    *,
    days: int = _WINDOW_DAYS,
    cutoff_date: str | None = None,
    krx: KRXClient | None = None,
) -> list[StockSupplyRow]:
    """종목 수급 시계열 보장 + 반환. flow_inputs 진입점.

    - cutoff_date 지정(백테스팅): live fetch X. 저장된 행 중 ≤ cutoff 만.
    - 평상시: 캐시 sparse(< days) 면 60일 백필, 아니면 당일분 재-fetch(R3-a).
    - 미가용(빈 결과) 시 [] 반환 → 호출부(flow_inputs) 가 시장 프록시 fallback.
    """
    ticker = (ticker or "").strip()
    if not ticker:
        return []

    if cutoff_date is None:
        existing = load_stock_supply_window(ticker, days=days)
        if len(existing) < days:
            await fetch_stock_supply(ticker, calendar_days=_BACKFILL_CALENDAR_DAYS, krx=krx)
        else:
            # 당일분 + 직전 며칠만 재-fetch (멱등 upsert, 과거 보존)
            await fetch_stock_supply(ticker, calendar_days=_REFRESH_CALENDAR_DAYS, krx=krx)

    rows = load_stock_supply_window(ticker, days=days)
    if cutoff_date:
        rows = [r for r in rows if r.date <= cutoff_date]
    return rows


async def get_stock_market_cap(ticker: str, *, kis: Any | None = None) -> float | None:
    """KIS 시총(억) → 백만원 (1억 = 100백만원). inflow_speed 분모. 실패 시 None."""
    from connectors.kis import KISClient

    async def _do(client: Any) -> float | None:
        try:
            data = await client.stock_price(ticker)
        except Exception as e:  # noqa: BLE001
            log.warning("stock_market_cap_failed", ticker=ticker, error=str(e))
            return None
        if not isinstance(data, dict) or "error" in data:
            return None
        cap_eok = data.get("market_cap")
        if not cap_eok:
            return None
        return float(cap_eok) * 100.0  # 억 → 백만원

    if kis is None:
        async with KISClient() as own:
            return await _do(own)
    return await _do(kis)


# ---------------------------------------------------------------------------
# 60d 합산 (contract: stock-supply-v1) — snapshot/검증용
# ---------------------------------------------------------------------------


def sum_stock_supply(rows: list[StockSupplyRow]) -> dict[str, int]:
    """시계열 → 5주체 net 60일 합."""
    sums = {k: 0 for k in _INVESTOR_KEYS}
    for r in rows:
        sums["foreign_net"] += r.foreign_net
        sums["institution_net"] += r.institution_net
        sums["individual_net"] += r.individual_net
        sums["financial_inv_net"] += r.financial_inv_net
        sums["pension_net"] += r.pension_net
    return sums


async def get_stock_supply_60d(
    ticker: str, *, cutoff_date: str | None = None,
    kis: Any | None = None, krx: KRXClient | None = None,
) -> dict[str, Any]:
    """ticker 60일 5주체 net 합 + agreement + market_cap. stock-supply-v1 contract.

    actual_days == 0 → 미가용 (호출부 시장 프록시 fallback).
    """
    rows = await ensure_stock_supply_series(ticker, cutoff_date=cutoff_date, krx=krx)
    if not rows:
        return {
            "ticker": ticker, "actual_days": 0,
            **{f"{k}_60d": 0 for k in _INVESTOR_KEYS},
            "agreement_score_60d": 0.0, "market_cap": None, "source": "unavailable",
        }
    sums = sum_stock_supply(rows)
    market_cap = None if cutoff_date else await get_stock_market_cap(ticker, kis=kis)
    return {
        "ticker": ticker,
        "actual_days": len(rows),
        **{f"{k}_60d": sums[k] for k in _INVESTOR_KEYS},
        "agreement_score_60d": agreement_score(sums),
        "market_cap": market_cap,
        "source": "stock_krx",
    }
