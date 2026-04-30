"""Korean leading stocks — KOSPI / KOSDAQ trade-amount ranking + user filter.

User-defined leading stock criteria:
- KOSPI top-20 by market cap: change_pct >= 2%  (revised 2026-04-30 from 3%)
- KOSPI outside top-20:        change_pct >= 5%
- KOSDAQ (any cap):            change_pct >= 5%

Items that don't meet the threshold are still returned (filling up to limit)
with `match: "fill_by_amount"`; matched items have `match: "meets_criteria"`.

Returned shape:
{
    "kospi":  [up to kospi_limit items],
    "kosdaq": [up to kosdaq_limit items],
    "stats":  {kospi_matched, kospi_fill, kosdaq_matched, kosdaq_fill},
    "kospi_top20_tickers": [ticker, ...],
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


def _filter(
    rank_rows: list[dict[str, Any]],
    kospi_top20: set[str],
    kospi_limit: int,
    kosdaq_limit: int,
) -> dict[str, Any]:
    kospi_matched: list[dict] = []
    kospi_rest: list[dict] = []
    kosdaq_matched: list[dict] = []
    kosdaq_rest: list[dict] = []

    for item in rank_rows:
        ticker = item.get("ticker", "")
        pct = item.get("change_pct") or 0
        market = item.get("market", "unknown")

        if market == "kospi":
            is_top20 = ticker in kospi_top20
            threshold = 2.0 if is_top20 else 5.0
            enriched = {**item, "cap_tier": "top20" if is_top20 else "mid_small"}
            if pct >= threshold:
                enriched["match"] = "meets_criteria"
                kospi_matched.append(enriched)
            else:
                enriched["match"] = "fill_by_amount"
                kospi_rest.append(enriched)
        elif market == "kosdaq":
            enriched = dict(item)
            if pct >= 5.0:
                enriched["match"] = "meets_criteria"
                kosdaq_matched.append(enriched)
            else:
                enriched["match"] = "fill_by_amount"
                kosdaq_rest.append(enriched)

    kospi = (kospi_matched + kospi_rest)[:kospi_limit]
    kosdaq = (kosdaq_matched + kosdaq_rest)[:kosdaq_limit]

    return {
        "kospi": kospi,
        "kosdaq": kosdaq,
        "stats": {
            "kospi_matched": len(kospi_matched),
            "kospi_fill": max(0, kospi_limit - len(kospi_matched)),
            "kosdaq_matched": len(kosdaq_matched),
            "kosdaq_fill": max(0, kosdaq_limit - len(kosdaq_matched)),
        },
    }


async def _fetch_inner(
    kis: KISClient,
    kospi_limit: int,
    kosdaq_limit: int,
) -> dict[str, Any]:
    vol_kospi = await kis.volume_rank(limit=30, rank_type="amount", market_scope="kospi")
    vol_kosdaq = await kis.volume_rank(limit=30, rank_type="amount", market_scope="kosdaq")
    cap_top20 = await kis.market_cap_rank(market="0001", limit=20)
    kospi_top20 = {m["ticker"] for m in cap_top20}

    filtered = _filter(
        vol_kospi + vol_kosdaq,
        kospi_top20=kospi_top20,
        kospi_limit=kospi_limit,
        kosdaq_limit=kosdaq_limit,
    )

    return {
        **filtered,
        "kospi_top20_tickers": sorted(kospi_top20),
        "source": "kis",
        "fetched_at": datetime.now(_KST).isoformat(timespec="seconds"),
        "note": (
            "KOSPI 10 + KOSDAQ 7. 조건(top20+2% / 외부+5% / 코스닥+5%) 우선, "
            "부족 시 거래대금 상위로 채움. match 필드 확인."
        ),
    }


async def fetch_kr_leading_stocks(
    kis: KISClient | None = None,
    *,
    kospi_limit: int = 10,
    kosdaq_limit: int = 7,
) -> dict[str, Any]:
    """Fetch KOSPI/KOSDAQ leading stocks per user criteria.

    Three KIS calls (volume_rank kospi + kosdaq + market_cap_rank kospi).
    With 1s rate limit ~ 3s.
    """
    if kis is None:
        async with KISClient() as own:
            result = await _fetch_inner(own, kospi_limit, kosdaq_limit)
    else:
        result = await _fetch_inner(kis, kospi_limit, kosdaq_limit)

    stats = result["stats"]
    log.info(
        "kr_leading_stocks_collected",
        kospi=len(result["kospi"]),
        kosdaq=len(result["kosdaq"]),
        kospi_matched=stats["kospi_matched"],
        kosdaq_matched=stats["kosdaq_matched"],
    )
    return result
