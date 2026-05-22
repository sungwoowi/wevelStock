"""5주체 수급 60일 시계열 collector (INFRA-SNAPSHOT-EXTEND-001 C 카테고리).

flow_analyzer F-Score 4축 base (테마-주체 매칭 + 60일 모멘텀 + 자금 유입 속도 + 부호 일치도).
KIS `market_investor_total` (inquire-investor-time-by-market, FHPTJ04030000) 호출 →
KOSPI/KOSDAQ 양 시장 5주체 (외인·기관·개인·금융투자·연기금) 일별 누적 net 매수액 적재.

흐름:
  1. `refresh_supply_demand_today()` — cron 진입점 (평일 18:00 KST).
     KIS market_investor_total("kospi") + market_investor_total("kosdaq") →
     `supply_demand_history` 에 today_kst row 2 개 upsert (KOSPI + KOSDAQ).
  2. `get_supply_60d(market)` — snapshot.py 가 호출. 최근 60 거래일 5주체 합산 +
     agreement_score 산출.

agreement_score:
  - 5주체 net 의 부호 일치도. 가장 많은 동일 부호 주체 수 / 5 × 10.
  - 5/5 (모두 매수 또는 모두 매도) = 10, 4/5 = 8, 3/5 = 6.
  - SLOT S3 = 정밀 공식 (선형 vs 비선형) flow_analyzer manifest 동시 결정 백로그.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from connectors.kis import KISClient
from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")
_SUPPLY_WINDOW_DAYS = 60

_INVESTOR_KEYS = (
    "foreign_net",
    "institution_net",
    "individual_net",
    "financial_inv_net",
    "pension_net",
)


@dataclass
class SupplyRow:
    """1 일 1 시장 의 5주체 net 매수액 (백만원)."""

    date: str
    market: str
    foreign_net: int
    institution_net: int
    individual_net: int
    financial_inv_net: int
    pension_net: int
    source: str = "kis"


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _sign(v: int) -> int:
    if v > 0:
        return 1
    if v < 0:
        return -1
    return 0


def agreement_score(nets: dict[str, int] | list[int]) -> float:
    """5주체 net 부호 일치도 → 0~10 (가장 많은 동일 부호 주체 수 / 5 × 10).

    예: [+, +, +, +, +] → 5/5 → 10.0
        [+, +, +, +, -] → 4/5 → 8.0
        [+, +, +, -, -] → 3/5 → 6.0
        [0, 0, 0, 0, 0] → 5/5 (모두 0) → 10.0 (특이 케이스, 데이터 부재)
    """
    if isinstance(nets, dict):
        values = [nets.get(k, 0) for k in _INVESTOR_KEYS]
    else:
        values = list(nets)
    if not values:
        return 0.0
    signs = [_sign(v) for v in values]
    counts: dict[int, int] = {1: 0, 0: 0, -1: 0}
    for s in signs:
        counts[s] = counts.get(s, 0) + 1
    max_same = max(counts.values())
    return round(max_same / len(values) * 10, 2)


def _today_kst_str() -> str:
    return datetime.now(_KST).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# DB layer
# ---------------------------------------------------------------------------


def upsert_supply_row(row: SupplyRow) -> None:
    """supply_demand_history ON CONFLICT REPLACE 멱등 upsert."""
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO supply_demand_history "
            "(date, market, foreign_net, institution_net, individual_net, "
            " financial_inv_net, pension_net, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(date, market) DO UPDATE SET "
            " foreign_net=excluded.foreign_net, "
            " institution_net=excluded.institution_net, "
            " individual_net=excluded.individual_net, "
            " financial_inv_net=excluded.financial_inv_net, "
            " pension_net=excluded.pension_net, "
            " source=excluded.source",
            (
                row.date, row.market,
                row.foreign_net, row.institution_net, row.individual_net,
                row.financial_inv_net, row.pension_net, row.source,
            ),
        )


def load_supply_window(market: str, *, days: int = _SUPPLY_WINDOW_DAYS) -> list[SupplyRow]:
    """market 의 최근 days 거래일 supply 시계열 반환 (정순)."""
    db = get_db()
    rows = db.fetch_all(
        "SELECT date, market, foreign_net, institution_net, individual_net, "
        "       financial_inv_net, pension_net, source "
        "FROM supply_demand_history "
        "WHERE market = ? "
        "ORDER BY date DESC LIMIT ?",
        (market.upper(), days),
    )
    items = [
        SupplyRow(
            date=r["date"],
            market=r["market"],
            foreign_net=int(r["foreign_net"]),
            institution_net=int(r["institution_net"]),
            individual_net=int(r["individual_net"]),
            financial_inv_net=int(r["financial_inv_net"]),
            pension_net=int(r["pension_net"]),
            source=r["source"] or "kis",
        )
        for r in rows
    ]
    items.reverse()  # 정순 (과거 → 최신)
    return items


# ---------------------------------------------------------------------------
# Async public API
# ---------------------------------------------------------------------------


def _kis_market_to_label(market_key: str) -> str:
    return {"kospi": "KOSPI", "kosdaq": "KOSDAQ"}[market_key]


async def refresh_supply_demand_today(kis: KISClient | None = None) -> dict[str, Any]:
    """오늘 KOSPI + KOSDAQ 5주체 net fetch + upsert. cron 진입점.

    Returns:
        {"refreshed": ["KOSPI", "KOSDAQ"], "failures": [...]}
    """
    today_str = _today_kst_str()
    refreshed: list[str] = []
    failures: list[dict[str, str]] = []

    async def _refresh_one(kis_client: KISClient, market_key: str) -> None:
        market_label = _kis_market_to_label(market_key)
        data = await kis_client.market_investor_total(market_key)
        if "error" in data or data.get("no_data"):
            failures.append({
                "market": market_label,
                "error": data.get("error") or "no_data",
            })
            return
        row = SupplyRow(
            date=today_str,
            market=market_label,
            foreign_net=int(data.get("foreign_net_amount_m", 0)),
            institution_net=int(data.get("institution_net_amount_m", 0)),
            individual_net=int(data.get("individual_net_amount_m", 0)),
            financial_inv_net=int(data.get("fin_invest_net_amount_m", 0)),
            pension_net=int(data.get("pension_net_amount_m", 0)),
        )
        upsert_supply_row(row)
        refreshed.append(market_label)

    if kis is None:
        async with KISClient() as own:
            for mkt in ("kospi", "kosdaq"):
                await _refresh_one(own, mkt)
    else:
        for mkt in ("kospi", "kosdaq"):
            await _refresh_one(kis, mkt)

    return {
        "refreshed": refreshed,
        "failures": failures,
        "completed_at": datetime.now(_KST).isoformat(timespec="seconds"),
    }


async def get_supply_60d(market: str = "KOSPI") -> dict[str, Any]:
    """`supply_demand_history` 의 최근 60 거래일 5 주체 net 합산 + agreement_score.

    snapshot.py 의 build_market_snapshot 가 호출. flow_analyzer F-Score base.

    Returns:
        {
          "market": "KOSPI",
          "window_days": 60,
          "actual_days": int (실제 시계열 길이),
          "foreign_net_60d": int, "institution_net_60d": int, ...,
          "agreement_score_60d": float,
        }
    """
    market_upper = market.upper()
    rows = load_supply_window(market_upper, days=_SUPPLY_WINDOW_DAYS)
    if not rows:
        return {
            "market": market_upper,
            "window_days": _SUPPLY_WINDOW_DAYS,
            "actual_days": 0,
            "foreign_net_60d": 0,
            "institution_net_60d": 0,
            "individual_net_60d": 0,
            "financial_inv_net_60d": 0,
            "pension_net_60d": 0,
            "agreement_score_60d": 0.0,
        }

    sums = {k: 0 for k in _INVESTOR_KEYS}
    for r in rows:
        sums["foreign_net"] += r.foreign_net
        sums["institution_net"] += r.institution_net
        sums["individual_net"] += r.individual_net
        sums["financial_inv_net"] += r.financial_inv_net
        sums["pension_net"] += r.pension_net

    return {
        "market": market_upper,
        "window_days": _SUPPLY_WINDOW_DAYS,
        "actual_days": len(rows),
        "foreign_net_60d": sums["foreign_net"],
        "institution_net_60d": sums["institution_net"],
        "individual_net_60d": sums["individual_net"],
        "financial_inv_net_60d": sums["financial_inv_net"],
        "pension_net_60d": sums["pension_net"],
        "agreement_score_60d": agreement_score(sums),
    }
