"""CME KOSPI200 overnight futures (or EWY ETF fallback).

KOSPI200 night futures:
  - Primary: "KM=F" (CME KOSPI200 futures), not always available on yfinance
  - Fallback: "EWY" (iShares MSCI South Korea ETF, US-listed, trades during US hours)

Returns:
{
    "kospi200_cme_night": {price, change_pct, source: "KM=F" | "EWY"} | {error}
}
"""
from __future__ import annotations

import asyncio
from typing import Any

from core.logging import get_logger

log = get_logger(__name__)

PRIMARY_SYMBOL = "KM=F"
FALLBACK_SYMBOL = "EWY"


def _fetch_sync(symbol: str) -> dict[str, Any]:
    try:
        import yfinance as yf
    except ImportError:
        return {"symbol": symbol, "error": "yfinance not installed"}

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d", auto_adjust=False)
        if hist.empty:
            return {"symbol": symbol, "error": "no history"}
        closes = hist["Close"].tolist()
        if len(closes) < 2:
            return {"symbol": symbol, "error": "insufficient history"}
        price = float(closes[-1])
        prev = float(closes[-2])
        change_pct = ((price - prev) / prev * 100) if prev else 0.0
        return {
            "symbol": symbol,
            "price": round(price, 2),
            "previous_close": round(prev, 2),
            "change_pct": round(change_pct, 2),
        }
    except Exception as e:  # noqa: BLE001
        return {"symbol": symbol, "error": str(e)}


async def fetch_night_futures() -> dict[str, dict[str, Any]]:
    """Try primary symbol first, fall back to EWY ETF if unavailable."""
    primary = await asyncio.to_thread(_fetch_sync, PRIMARY_SYMBOL)
    if "error" not in primary:
        primary["source"] = PRIMARY_SYMBOL
        log.info("kr_night_futures", source=PRIMARY_SYMBOL, change_pct=primary.get("change_pct"))
        return {"kospi200_cme_night": primary}

    fallback = await asyncio.to_thread(_fetch_sync, FALLBACK_SYMBOL)
    fallback["source"] = FALLBACK_SYMBOL
    fallback["note"] = "EWY ETF used as proxy (CME KM=F unavailable)"
    log.info(
        "kr_night_futures_fallback",
        source=FALLBACK_SYMBOL,
        change_pct=fallback.get("change_pct"),
        primary_error=primary.get("error"),
    )
    return {"kospi200_cme_night": fallback}
