"""Korean sector ETFs — pre-defined list of KODEX/TIGER/ACE sector ETFs.

Reads change_pct for each tracked ETF, sorts by strongest, returns full list
plus a filtered "strong" subset (>= min_change_pct).

Returned shape:
{
    "all":    [{ticker, name, price, change_pct, volume, trade_amount}, ...] sorted desc by change_pct,
    "strong": [...] subset where change_pct >= min_change_pct,
    "source": "kis",
    "fetched_at": "...",
}

The default ETF universe matches `docs/a_wanted/user_want_spec.md` Task3.
Callers can pass a custom list via `etfs` (e.g. loaded from runtime.yaml).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from connectors.kis import KISClient
from core.logging import get_logger

log = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")

DEFAULT_TRACKED_ETFS: list[tuple[str, str]] = [
    ("091160", "KODEX 반도체"),
    ("396500", "KODEX AI반도체핵심장비"),
    ("394670", "KODEX AI반도체"),
    ("487240", "KODEX AI전력핵심"),
    ("472170", "ACE 원자력TOP10"),
    ("091180", "KODEX 자동차"),
    ("139260", "TIGER 200 금융"),
    ("139270", "TIGER 200 건설"),
    ("0080G0", "KODEX 방산TOP10"),
    ("463250", "TIGER K방산&우주"),
    ("466920", "TIGER 조선TOP10"),
    ("396510", "KODEX 로봇액티브"),
    ("305720", "KODEX 2차전지산업"),
    ("244580", "KODEX 바이오"),
    ("228790", "TIGER 화장품"),
]


async def _fetch_inner(
    kis: KISClient,
    etfs: list[tuple[str, str]],
    min_change_pct: float,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for ticker, name in etfs:
        row = await kis.etf_price(ticker)
        row["name"] = name
        rows.append(row)

    rows.sort(key=lambda r: r.get("change_pct") or 0, reverse=True)
    strong = [r for r in rows if (r.get("change_pct") or 0) >= min_change_pct]

    return {
        "all": rows,
        "strong": strong,
        "min_change_pct": min_change_pct,
        "source": "kis",
        "fetched_at": datetime.now(_KST).isoformat(timespec="seconds"),
    }


async def fetch_kr_sectors(
    kis: KISClient | None = None,
    *,
    etfs: list[tuple[str, str]] | None = None,
    min_change_pct: float = 1.0,
) -> dict[str, Any]:
    """Fetch ETF prices for all tracked sectors.

    `etfs` defaults to DEFAULT_TRACKED_ETFS. One KIS call per ETF — with the
    1s rate limit, 15 ETFs ~ 15s. Pass a shared KISClient to reuse token.
    """
    universe = etfs if etfs is not None else DEFAULT_TRACKED_ETFS

    if kis is None:
        async with KISClient() as own:
            result = await _fetch_inner(own, universe, min_change_pct)
    else:
        result = await _fetch_inner(kis, universe, min_change_pct)

    log.info(
        "kr_sectors_collected",
        total=len(result["all"]),
        strong=len(result["strong"]),
        threshold=min_change_pct,
    )
    return result
