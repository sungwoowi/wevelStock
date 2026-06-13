"""Yahoo Finance async wrapper.

기존 (해외 지수 + 금):
- ^IXIC: Nasdaq Composite
- ^SOX: Philadelphia Semiconductor Index (SOX)
- GC=F: Gold Futures
- ^DJI: Dow Jones
- DX-Y.NYB: Dollar Index (DXY)

INFRA-FUNDAMENTAL-DATA-001 (분기 실적 + TTM 5 ratio):
- YFinanceClient — fetch_info / fetch_quarterly / fetch_full
- 한국 KOSPI=`.KS` / KOSDAQ=`.KQ` / 미주 suffix X 자동 변환
"""
from __future__ import annotations

import asyncio
import math
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
    "usdkrw": "KRW=X",      # 원달러 환율 (간밤시황 fetch_overnight 위임용)
    # 야간자산 (INFRA-MARKET-ASSETS-002) — gold 와 동일 야간 카테고리.
    "wti": "CL=F",          # WTI 원유 선물
    "brent": "BZ=F",        # 브렌트 원유 선물
    "nq_futures": "NQ=F",   # 나스닥100 야간선물
    "es_futures": "ES=F",   # S&P500 야간선물
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


# =============================================================================
# INFRA-FUNDAMENTAL-DATA-001 — fundamental client (TTM 5 ratio + 분기 5분기)
# =============================================================================


def _to_yf_ticker(ticker: str, market: str) -> str:
    """6자리 한국 ticker + market → yfinance ticker.

    한국 KOSPI: "005930" + "KS" → "005930.KS"
    한국 KOSDAQ: "247540" + "KQ" → "247540.KQ"
    미주: "AAPL" + "US" → "AAPL"
    """
    if market == "KS":
        return f"{ticker}.KS"
    if market == "KQ":
        return f"{ticker}.KQ"
    return ticker


def _quarter_label(ts: Any) -> str:
    """datetime/Timestamp → 'YYYYQN'."""
    try:
        return f"{ts.year}Q{(ts.month - 1) // 3 + 1}"
    except (AttributeError, TypeError):
        return str(ts)


def _clean_float(v: Any) -> float | None:
    """NaN / None / 비숫자 → None. 정상값은 float."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


class FundamentalNotAvailable(RuntimeError):
    """yfinance 가 빈 데이터 반환 (delisted / 잘못된 ticker)."""


class YFinanceClient:
    """INFRA-FUNDAMENTAL-DATA-001 — fundamental 데이터 async wrapper.

    sync API (`Ticker.info` / `Ticker.quarterly_financials` /
    `Ticker.quarterly_earnings`) 를 asyncio.to_thread 로 wrap.
    """

    async def fetch_info(self, yf_ticker: str) -> dict[str, Any]:
        """5 ratio TTM 추출. 빈 dict 반환 시 {'empty': True}."""
        return await asyncio.to_thread(self._fetch_info_sync, yf_ticker)

    async def fetch_quarterly(self, yf_ticker: str) -> dict[str, Any]:
        """분기 5분기 매출·영업이익·EPS + quarter_labels."""
        return await asyncio.to_thread(self._fetch_quarterly_sync, yf_ticker)

    async def fetch_annual(self, yf_ticker: str) -> dict[str, Any]:
        """연간 EPS (최근 4년, recent-first) + annual_labels (CAN SLIM A 입력)."""
        return await asyncio.to_thread(self._fetch_annual_sync, yf_ticker)

    async def fetch_full(self, ticker: str, market: str = "KS") -> dict[str, Any]:
        """info + quarterly + annual 결합. 표준 dict 반환.

        Raises:
            FundamentalNotAvailable: yfinance info 가 empty (delisted / invalid).
        """
        yf_t = _to_yf_ticker(ticker, market)
        info = await self.fetch_info(yf_t)
        if not info or info.get("empty"):
            err = info.get("error") if info else "no info"
            raise FundamentalNotAvailable(
                f"yfinance returned empty info for {yf_t}: {err}"
            )
        quarterly = await self.fetch_quarterly(yf_t)
        annual = await self.fetch_annual(yf_t)
        return {
            "ticker": ticker,
            "market": market,
            "yf_ticker": yf_t,
            **info,
            **quarterly,
            **annual,
        }

    @staticmethod
    def _fetch_info_sync(yf_ticker: str) -> dict[str, Any]:
        import yfinance as yf

        try:
            ticker = yf.Ticker(yf_ticker)
            info = ticker.info or {}
            if not info or len(info) <= 1:
                return {"empty": True}
            return {
                "eps_ttm": _clean_float(info.get("trailingEps")),
                "pe_ratio": _clean_float(info.get("trailingPE")),
                "roe": _clean_float(info.get("returnOnEquity")),
                "operating_margin": _clean_float(info.get("operatingMargins")),
                "debt_to_equity": _clean_float(info.get("debtToEquity")),
            }
        except Exception as e:  # noqa: BLE001
            log.warning("yfinance_info_fetch_failed", ticker=yf_ticker, error=str(e))
            return {"empty": True, "error": str(e)}

    @staticmethod
    def _fetch_quarterly_sync(yf_ticker: str) -> dict[str, Any]:
        import yfinance as yf

        empty_result = {
            "quarterly_revenue": [],
            "quarterly_operating_income": [],
            "quarterly_eps": [],
            "quarter_labels": [],
        }
        try:
            ticker = yf.Ticker(yf_ticker)
            # quarterly_financials ↔ quarterly_income_stmt API drift 대응
            qf = None
            for attr in ("quarterly_financials", "quarterly_income_stmt"):
                try:
                    val = getattr(ticker, attr, None)
                    if val is not None and not val.empty:
                        qf = val
                        break
                except Exception:  # noqa: BLE001
                    continue

            try:
                qe = getattr(ticker, "quarterly_earnings", None)
            except Exception:  # noqa: BLE001
                qe = None

            revenue: list[float | None] = []
            operating_income: list[float | None] = []
            eps: list[float | None] = []
            labels: list[str] = []

            if qf is not None and not qf.empty:
                cols = list(qf.columns)[:5]  # 최근 5분기 (descending)
                for col in cols:
                    labels.append(_quarter_label(col))
                for row_key in ("Total Revenue", "TotalRevenue"):
                    if row_key in qf.index:
                        for col in cols:
                            revenue.append(_clean_float(qf.at[row_key, col]))
                        break
                for row_key in ("Operating Income", "OperatingIncome"):
                    if row_key in qf.index:
                        for col in cols:
                            operating_income.append(_clean_float(qf.at[row_key, col]))
                        break

            if qe is not None and not qe.empty:
                eps_col = next(
                    (c for c in ("EPS", "Earnings") if c in qe.columns), None
                )
                if eps_col is not None:
                    for v in list(qe[eps_col])[:5]:
                        eps.append(_clean_float(v))
                    if not labels:
                        for idx in list(qe.index)[:5]:
                            labels.append(str(idx))

            return {
                "quarterly_revenue": revenue,
                "quarterly_operating_income": operating_income,
                "quarterly_eps": eps,
                "quarter_labels": labels,
            }
        except Exception as e:  # noqa: BLE001
            log.warning(
                "yfinance_quarterly_fetch_failed", ticker=yf_ticker, error=str(e)
            )
            return empty_result

    @staticmethod
    def _fetch_annual_sync(yf_ticker: str) -> dict[str, Any]:
        """연간 income statement 의 Diluted/Basic EPS row → 최근 4년 (recent-first).

        CAN SLIM A (연간 EPS 3년 가속) 입력. 결측·API drift 시 빈 리스트(정직).
        """
        import yfinance as yf

        empty_result: dict[str, Any] = {"annual_eps": [], "annual_labels": []}
        try:
            ticker = yf.Ticker(yf_ticker)
            # income_stmt ↔ financials API drift 대응 (둘 다 연간 income statement)
            af = None
            for attr in ("income_stmt", "financials"):
                try:
                    val = getattr(ticker, attr, None)
                    if val is not None and not val.empty:
                        af = val
                        break
                except Exception:  # noqa: BLE001
                    continue
            if af is None or af.empty:
                return empty_result

            cols = list(af.columns)[:4]  # 최근 4년 (descending)
            labels = [
                str(c.year) if hasattr(c, "year") else str(c) for c in cols
            ]
            eps: list[float | None] = []
            for row_key in ("Diluted EPS", "Basic EPS", "DilutedEPS", "BasicEPS"):
                if row_key in af.index:
                    for col in cols:
                        eps.append(_clean_float(af.at[row_key, col]))
                    break
            if not eps:
                return {"annual_eps": [], "annual_labels": labels}
            return {"annual_eps": eps, "annual_labels": labels}
        except Exception as e:  # noqa: BLE001
            log.warning(
                "yfinance_annual_fetch_failed", ticker=yf_ticker, error=str(e)
            )
            return empty_result
