"""KOSPI200 야간선물 — KIS 실선물(1순위) → CME KM=F → EWY ETF 대용(최후).

INFRA-MARKET-ASSETS-002: 기존엔 KM=F(yfinance 미제공) → **EWY(미국 상장 한국 ETF)** 대용만
나갔다 — 텔레그램에 "KOSPI200 야간선물"로 표시되지만 실제론 EWY 였다. 이제 **KIS 실계좌
선물 시세**(연결선물 `101000` = 최근월물 자동)를 1순위로 두어 진짜 KOSPI200 야간선물 등락률을
노출한다. env `KIS_KOSPI200_FUTURES_SYMBOL` 설정 시 활성, 실패 시 기존 yfinance 폴백 체인.

야간 세션(18:00~05:00 KST)이면 야간가, 주간이면 주간 선물가 — KIS 가 세션 무구분 최신가 반환.

Returns:
{
    "kospi200_cme_night": {
        price, change_pct,
        source: "kis" | "KM=F" | "EWY",
        source_kr: "실선물" | "CME" | "EWY ETF(대용)",
        label_kr: "코스피200 선물",
    } | {error}
}
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

from core.logging import get_logger

log = get_logger(__name__)

PRIMARY_SYMBOL = "KM=F"
FALLBACK_SYMBOL = "EWY"

_LABEL_KR = "코스피200 선물"


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


async def _fetch_kis_night_futures() -> dict[str, Any] | None:
    """KIS 실계좌 KOSPI200 선물 시세 (연결선물 최근월물 자동). 미설정·실패 시 None."""
    symbol = os.getenv("KIS_KOSPI200_FUTURES_SYMBOL", "").strip()
    if not symbol:
        return None
    try:
        from connectors.kis import KISClient

        async with KISClient() as kis:
            r = await kis.index_futures_price(symbol)
    except Exception as e:  # noqa: BLE001 — best-effort, 폴백 체인으로 강등
        log.info("kis_night_futures_failed", symbol=symbol, error=str(e))
        return None
    if "error" in r or r.get("change_pct") is None:
        log.info("kis_night_futures_unavailable", symbol=symbol, msg=r.get("error"))
        return None
    return {
        "symbol": symbol,
        "price": r.get("price"),
        "change_pct": r.get("change_pct"),
        "source": "kis",
        "source_kr": "실선물",
        "label_kr": _LABEL_KR,
    }


async def fetch_night_futures() -> dict[str, dict[str, Any]]:
    """KIS 실선물 1순위 → CME KM=F → EWY ETF 대용 순으로 KOSPI200 야간선물 등락률."""
    # 1순위: KIS 실계좌 선물 (진짜 KOSPI200 야간선물)
    kis = await _fetch_kis_night_futures()
    if kis is not None:
        log.info("kr_night_futures", source="kis", change_pct=kis.get("change_pct"))
        return {"kospi200_cme_night": kis}

    # 2순위: CME KM=F (yfinance — 대개 미제공)
    primary = await asyncio.to_thread(_fetch_sync, PRIMARY_SYMBOL)
    if "error" not in primary:
        primary["source"] = PRIMARY_SYMBOL
        primary["source_kr"] = "CME"
        primary["label_kr"] = _LABEL_KR
        log.info("kr_night_futures", source=PRIMARY_SYMBOL, change_pct=primary.get("change_pct"))
        return {"kospi200_cme_night": primary}

    # 3순위: EWY ETF 대용 (미국 상장 한국 ETF — KOSPI200 선물 아님, 대용임을 명시)
    fallback = await asyncio.to_thread(_fetch_sync, FALLBACK_SYMBOL)
    fallback["source"] = FALLBACK_SYMBOL
    fallback["source_kr"] = "EWY ETF(대용)"
    fallback["label_kr"] = "한국 ETF(EWY) — 야간선물 대용"
    fallback["note"] = "EWY ETF proxy — KIS 실선물·CME 미가용"
    log.info(
        "kr_night_futures_fallback",
        source=FALLBACK_SYMBOL,
        change_pct=fallback.get("change_pct"),
        primary_error=primary.get("error"),
    )
    return {"kospi200_cme_night": fallback}
