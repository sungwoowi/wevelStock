"""US markets overnight data — indices, semis, macro indicators.

**단일 fetch 소스 = `connectors.yfinance.get_indices()`** 에 위임한다 (INFRA-MARKET-ASSETS-002
중복 fetch 부채 상환, 2026-06-13). 과거엔 이 모듈이 자체 `_fetch_sync` + `OVERNIGHT_SYMBOLS`
를 따로 둬 yfinance 호출 로직이 두 벌(us_macro 경로와) 중복이었다 — 이제 얇은 위임 래퍼.

간밤시황 소비처가 기대하는 로컬 키(`sox`·`usdkrw`)를 TRACKED_SYMBOLS 키(`philly_semi` 등)
에서 rename해 돌려준다. 반환 형식은 get_indices 와 동일:
{
    "nasdaq": {symbol, price, previous_close, change, change_pct} | {error},
    "sp500": {...}, "sox": {...}, "vix": {...}, "dxy": {...}, "usdkrw": {...},
    "us_10y": {...}, "gold": {...}, "wti": {...}, "brent": {...},
    "nq_futures": {...}, "es_futures": {...},
}
"""
from __future__ import annotations

from typing import Any

from core.logging import get_logger

log = get_logger(__name__)

# 간밤시황 로컬 키 → connectors.yfinance TRACKED_SYMBOLS 키.
# 대부분 동일하나 sox=philly_semi(같은 ^SOX) 한 건만 rename.
_OVERNIGHT_NAME_MAP: dict[str, str] = {
    "nasdaq": "nasdaq",
    "sp500": "sp500",
    "sox": "philly_semi",
    "vix": "vix",
    "dxy": "dxy",
    "usdkrw": "usdkrw",
    "us_10y": "us_10y",
    "gold": "gold",
    "wti": "wti",
    "brent": "brent",
    "nq_futures": "nq_futures",
    "es_futures": "es_futures",
}


async def fetch_overnight() -> dict[str, dict[str, Any]]:
    """간밤 미국 지수·거시·야간선물 — connectors.yfinance.get_indices 위임.

    단일 fetch 소스 재사용 (중복 _fetch_sync 제거). 로컬 키(sox·usdkrw)로 rename.
    """
    from connectors.yfinance.client import get_indices

    raw = await get_indices(names=list(_OVERNIGHT_NAME_MAP.values()))
    out: dict[str, dict[str, Any]] = {
        local: raw.get(remote, {"symbol": remote, "error": "missing"})
        for local, remote in _OVERNIGHT_NAME_MAP.items()
    }
    success = sum(1 for v in out.values() if "error" not in v)
    log.info("us_overnight_collected", success=success, total=len(out))
    return out
