"""CNN Fear & Greed Index — undocumented JSON endpoint.

CNN이 공식 API를 제공하지 않아 production.dataviz.cnn.io 를 사용한다.
브라우저 스타일 User-Agent/Referer 가 없으면 HTTP 418 로 차단된다.
CNN 이 막으면 {"error": "..."} 반환하고 상위에서 정상 graceful degrade.

Returned shape (success):
  {
    "score": 69.2,              # 0~100
    "rating": "greed",          # extreme fear | fear | neutral | greed | extreme greed
    "rating_kr": "탐욕",
    "previous_close": 68.1,
    "change": 1.14,             # score - previous_close
    "change_pct": 1.68,
  }
"""
from __future__ import annotations

from typing import Any

import httpx

from core.logging import get_logger

log = get_logger(__name__)

_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://edition.cnn.com/markets/fear-and-greed",
    "Origin": "https://edition.cnn.com",
}

_RATING_KR = {
    "extreme fear": "극도의 공포",
    "fear": "공포",
    "neutral": "중립",
    "greed": "탐욕",
    "extreme greed": "극도의 탐욕",
}


async def fetch_fear_greed() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_URL, headers=_HEADERS)
        if resp.status_code != 200:
            log.warning("fear_greed_non200", status=resp.status_code)
            return {"error": f"http {resp.status_code}"}
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        log.warning("fear_greed_fetch_failed", error=str(e))
        return {"error": str(e)}

    fg = data.get("fear_and_greed") or {}
    score = fg.get("score")
    if score is None:
        return {"error": "no score in response"}
    rating = str(fg.get("rating", "")).lower()
    prev = fg.get("previous_close")
    change = (score - prev) if prev is not None else None
    change_pct = (change / prev * 100) if (change is not None and prev) else None
    log.info("fear_greed_collected", score=round(score, 1), rating=rating)
    return {
        "score": round(score, 1),
        "rating": rating,
        "rating_kr": _RATING_KR.get(rating, rating),
        "previous_close": round(prev, 1) if prev is not None else None,
        "change": round(change, 2) if change is not None else None,
        "change_pct": round(change_pct, 2) if change_pct is not None else None,
    }
