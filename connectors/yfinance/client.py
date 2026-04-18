"""Yahoo Finance async wrapper for overseas indices and gold.

Used to fetch data KIS API doesn't provide:
- ^IXIC: Nasdaq Composite
- ^SOX: Philadelphia Semiconductor Index (SOX)
- GC=F: Gold Futures
- ^DJI: Dow Jones
- DX-Y.NYB: Dollar Index (DXY)
"""
from __future__ import annotations

import asyncio
from typing import Any

from core.logging import get_logger

log = get_logger(__name__)

TRACKED_SYMBOLS = {
    "nasdaq": "^IXIC",
    "philly_semi": "^SOX",
    "gold": "GC=F",
    "dow": "^DJI",
    "dxy": "DX-Y.NYB",
    "sp500": "^GSPC",
    "us_10y": "^TNX",
    "vix": "^VIX",
}


def _fetch_sync(symbol: str) -> dict[str, Any]:
    """Blocking yfinance call — wrapped in to_thread by caller."""
    import yfinance as yf

    try:
        ticker = yf.Ticker(symbol)
        # Use 2-day history for stable previous close + current comparison
        hist = ticker.history(period="5d", auto_adjust=False)
        if hist.empty:
            return {"symbol": symbol, "error": "no history data"}

        # Most recent close vs previous close
        closes = hist["Close"].tolist()
        if len(closes) < 2:
            return {"symbol": symbol, "error": "insufficient history"}

        price = float(closes[-1])
        prev = float(closes[-2])
        change = price - prev
        change_pct = (change / prev * 100) if prev else 0.0

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "previous_close": round(prev, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
        }
    except Exception as e:  # noqa: BLE001
        return {"symbol": symbol, "error": str(e)}


async def get_index(symbol: str) -> dict[str, Any]:
    """Get a single index/symbol asynchronously."""
    return await asyncio.to_thread(_fetch_sync, symbol)


async def get_indices(
    names: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Get multiple indices sequentially (yfinance sqlite cache isn't thread-safe).

    Default: all TRACKED_SYMBOLS.
    """
    if names is None:
        names = list(TRACKED_SYMBOLS.keys())

    out: dict[str, dict[str, Any]] = {}
    for name in names:
        symbol = TRACKED_SYMBOLS.get(name, name)
        try:
            out[name] = await asyncio.to_thread(_fetch_sync, symbol)
        except Exception as e:  # noqa: BLE001
            out[name] = {"symbol": symbol, "error": str(e)}

    success = len([v for v in out.values() if "error" not in v])
    log.info("yfinance_fetched", count=success, total=len(out))
    return out
