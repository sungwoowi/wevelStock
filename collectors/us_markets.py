"""US markets overnight data — indices, semis, macro indicators.

Backed by connectors.yfinance.get_indices() and extends it with oil (CL=F).

Returned shape:
{
    "nasdaq":      {price, change_pct, previous_close, ...} | {error},
    "sp500":       {...},
    "sox":         {...},
    "vix":         {...},
    "dxy":         {...},
    "us_10y":      {...},
    "gold":        {...},
    "wti":         {...},
}
"""
from __future__ import annotations

import asyncio
from typing import Any

from core.logging import get_logger

log = get_logger(__name__)

# Ticker map for yfinance (reused + WTI added).
OVERNIGHT_SYMBOLS = {
    "nasdaq":  "^IXIC",
    "sp500":   "^GSPC",
    "sox":     "^SOX",
    "vix":     "^VIX",
    "dxy":     "DX-Y.NYB",
    "usdkrw":  "KRW=X",
    "us_10y":  "^TNX",
    "gold":    "GC=F",
    "wti":     "CL=F",
    # 야간선물·브렌트 (INFRA-MARKET-ASSETS-002) — 간밤시황 노출용.
    "brent":      "BZ=F",   # 브렌트 원유 선물
    "nq_futures": "NQ=F",   # 나스닥100 야간선물
    "es_futures": "ES=F",   # S&P500 야간선물
}


def _fetch_sync(symbol: str) -> dict[str, Any]:
    """Blocking yfinance call — wrapped via asyncio.to_thread."""
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


async def fetch_overnight() -> dict[str, dict[str, Any]]:
    """Fetch all overnight indices + macro indicators.

    yfinance's sqlite cache isn't thread-safe, so we run sequentially.
    """
    out: dict[str, dict[str, Any]] = {}
    for name, symbol in OVERNIGHT_SYMBOLS.items():
        out[name] = await asyncio.to_thread(_fetch_sync, symbol)

    success = sum(1 for v in out.values() if "error" not in v)
    log.info("us_overnight_collected", success=success, total=len(out))
    return out
