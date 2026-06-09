"""벤치마크 지수 보유기간 수익률 — GUIDANCE-ACCURACY-TRACKER-001 (RB-MS3) G1.

"이 시스템이 그냥 지수 사두는 것보다 나은가" 의 정직한 검산. 트랙×시장 지수의
[체결일, 청산일] 구간 수익률. 권고 실현수익률 − 이 값 = 초과수익(알파).
지수 데이터 = yfinance 재사용(get_index 패턴). 부재 시 None(추정 X, 채점서 제외).
"""
from __future__ import annotations

from typing import Any, Callable

from core.logging import get_logger

log = get_logger(__name__)

# 트랙×시장 벤치마크 — 국장=코스피 / 미장=S&P500 (config override SLOT)
_MARKET_INDEX: dict[str, str] = {
    "KR": "^KS11",   # KOSPI Composite
    "US": "^GSPC",   # S&P 500 (대안 ^IXIC 나스닥)
}

# fetch(symbol, start_date, end_date) → (start_close, end_close) | None
FetchCloses = Callable[[str, str, str], "tuple[float, float] | None"]


def index_symbol(market: str, config: dict[str, Any] | None = None) -> str:
    """시장(KR/US) → 벤치마크 지수 심볼."""
    mapping = (config or {}).get("market_index", _MARKET_INDEX) if config else _MARKET_INDEX
    return mapping.get(market.upper(), _MARKET_INDEX.get(market.upper(), "^GSPC"))


def benchmark_return_pct(start_close: float, end_close: float) -> float | None:
    """구간 수익률(%) = (end/start − 1)×100. start 0/None → None(graceful)."""
    if not start_close:
        return None
    return (end_close / start_close - 1.0) * 100.0


def _fetch_index_closes_yf(symbol: str, start_date: str, end_date: str) -> tuple[float, float] | None:
    """yfinance 일봉으로 start_date·end_date 근접 종가 (start ≤ , end ≤). 부재 시 None."""
    try:
        import yfinance as yf

        # end 다음날까지 받아 end_date 포함 보장
        hist = yf.Ticker(symbol).history(start=start_date, end=_plus_one_day(end_date), auto_adjust=False)
        if hist is None or hist.empty:
            return None
        closes = hist["Close"]
        start_close = float(closes.iloc[0])
        end_close = float(closes.iloc[-1])
        return (start_close, end_close)
    except Exception as e:  # noqa: BLE001
        log.warning("benchmark_fetch_failed", symbol=symbol, error=str(e))
        return None


def _plus_one_day(date_str: str) -> str:
    from datetime import date, timedelta

    try:
        return (date.fromisoformat(date_str[:10]) + timedelta(days=1)).isoformat()
    except ValueError:
        return date_str


def compute_benchmark_return(
    market: str,
    start_date: str,
    end_date: str,
    *,
    config: dict[str, Any] | None = None,
    fetch: FetchCloses | None = None,
) -> float | None:
    """트랙×시장 지수의 [start_date, end_date] 구간 수익률(%). 데이터 부재 시 None.

    fetch 주입 가능(테스트·백테스트). 기본 = yfinance.
    """
    symbol = index_symbol(market, config)
    fetcher = fetch or _fetch_index_closes_yf
    closes = fetcher(symbol, start_date, end_date)
    if not closes:
        return None
    start_close, end_close = closes
    return benchmark_return_pct(start_close, end_close)
