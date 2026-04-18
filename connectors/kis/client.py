"""KIS OpenAPI client — token management + market data queries.

Usage:
    from connectors.kis import KISClient

    async with KISClient() as kis:
        price = await kis.stock_price("005930")  # Samsung
        kospi = await kis.index_price("0001")    # KOSPI
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from dotenv import load_dotenv

from core.logging import get_logger

load_dotenv()
log = get_logger(__name__)

REAL_BASE = "https://openapi.koreainvestment.com:9443"
PAPER_BASE = "https://openapivts.koreainvestment.com:29443"

# Rate limit: KIS 실전서버는 초당 거래건수 제한이 매우 엄격함
# 1초 간격으로 안전하게 호출 (초당 1회)
_CALL_INTERVAL = 1.0  # seconds


class KISClient:
    """Async KIS API client with automatic token management."""

    def __init__(self) -> None:
        self._app_key = os.getenv("KIS_APP_KEY", "")
        self._app_secret = os.getenv("KIS_APP_SECRET", "")
        self._account_no = os.getenv("KIS_ACCOUNT_NO", "")
        self._is_paper = os.getenv("KIS_IS_PAPER", "true").lower() == "true"
        self._base = PAPER_BASE if self._is_paper else REAL_BASE
        self._token: str | None = None
        self._token_expires: datetime | None = None
        self._client: httpx.AsyncClient | None = None
        self._last_call: float = 0

    @property
    def configured(self) -> bool:
        return bool(self._app_key and self._app_secret)

    async def __aenter__(self) -> KISClient:
        self._client = httpx.AsyncClient(timeout=15.0)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _ensure_token(self) -> str:
        """Get or refresh OAuth token."""
        now = datetime.now(timezone.utc)
        if self._token and self._token_expires and now < self._token_expires:
            return self._token

        url = f"{self._base}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
        }
        assert self._client is not None
        resp = await self._client.post(url, json=body)
        data = resp.json()

        if "access_token" not in data:
            raise RuntimeError(
                f"KIS token failed: {data.get('error_description', data)}"
            )

        self._token = data["access_token"]
        # Parse expiry: "2026-04-18 08:49:59"
        exp_str = data.get("access_token_token_expired", "")
        if exp_str:
            self._token_expires = datetime.strptime(
                exp_str, "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=timezone.utc)

        log.info("kis_token_acquired", expires=exp_str)
        # KIS rate limits count token requests — must wait before first data call
        await asyncio.sleep(2.0)
        self._last_call = asyncio.get_event_loop().time()
        return self._token

    async def _rate_limit(self) -> None:
        """Enforce minimum interval between API calls."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_call
        if elapsed < _CALL_INTERVAL:
            await asyncio.sleep(_CALL_INTERVAL - elapsed)
        self._last_call = asyncio.get_event_loop().time()

    async def _get(self, path: str, tr_id: str, params: dict) -> dict:
        """Make authenticated GET request."""
        token = await self._ensure_token()
        headers = {
            "authorization": f"Bearer {token}",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
            "tr_id": tr_id,
            "content-type": "application/json; charset=utf-8",
        }
        await self._rate_limit()
        assert self._client is not None
        resp = await self._client.get(
            f"{self._base}{path}", headers=headers, params=params
        )
        data = resp.json()
        if data.get("rt_cd") != "0":
            log.warning(
                "kis_api_error",
                path=path,
                tr_id=tr_id,
                msg=data.get("msg1", "unknown"),
            )
        return data

    # ------------------------------------------------------------------
    # Market data APIs
    # ------------------------------------------------------------------

    async def stock_price(self, ticker: str) -> dict[str, Any]:
        """Get current stock price. Returns parsed dict or empty on error."""
        data = await self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            tr_id="FHKST01010100",
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker},
        )
        if data.get("rt_cd") != "0":
            return {"error": data.get("msg1", "unknown"), "ticker": ticker}
        o = data["output"]
        market_name = o.get("rprs_mrkt_kor_name", "")  # KOSPI, KOSPI200, KOSDAQ
        # Normalize to KOSPI / KOSDAQ
        if "KOSDAQ" in market_name:
            market = "kosdaq"
        elif "KOSPI" in market_name:
            market = "kospi"
        else:
            market = "unknown"
        return {
            "ticker": ticker,
            "market": market,
            "market_raw": market_name,
            "price": int(o.get("stck_prpr", 0)),
            "change": int(o.get("prdy_vrss", 0)),
            "change_pct": float(o.get("prdy_ctrt", 0)),
            "volume": int(o.get("acml_vol", 0)),
            "trade_amount": int(o.get("acml_tr_pbmn", 0)),
            "high": int(o.get("stck_hgpr", 0)),
            "low": int(o.get("stck_lwpr", 0)),
            "open": int(o.get("stck_oprc", 0)),
            "market_cap": int(o.get("hts_avls", 0)),  # 시가총액 (억)
        }

    async def index_price(self, index_code: str) -> dict[str, Any]:
        """Get index price (0001=KOSPI, 1001=KOSDAQ, 2001=KOSPI200)."""
        data = await self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-index-price",
            tr_id="FHPUP02100000",
            params={"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": index_code},
        )
        if data.get("rt_cd") != "0":
            return {"error": data.get("msg1", "unknown"), "index": index_code}
        o = data["output"]
        return {
            "index": index_code,
            "value": float(o.get("bstp_nmix_prpr", 0)),
            "change": float(o.get("bstp_nmix_prdy_vrss", 0)),
            "change_pct": float(o.get("bstp_nmix_prdy_ctrt", 0)),
            "volume": int(o.get("acml_vol", 0)),
            "trade_amount": int(o.get("acml_tr_pbmn", 0)),
        }

    async def volume_rank(
        self,
        limit: int = 30,
        rank_type: str = "amount",  # amount=거래대금, volume=거래량
        market_scope: str = "all",  # all=전체, kospi=코스피만, kosdaq=코스닥만
    ) -> list[dict[str, Any]]:
        """Get top stocks by trading volume or trade amount.

        KIS FID_COND_SCR_DIV_CODE:
        - 20174 = 거래대금 상위
        - 20170 = 거래량 상위

        KIS FID_INPUT_ISCD:
        - 0000 = 전체
        - 0001 = KOSPI만
        - 1001 = KOSDAQ만
        - 2001 = KOSPI200

        KIS OpenAPI는 한 호출당 30개 상한. 페이징 미지원.
        """
        scr_code = "20174" if rank_type == "amount" else "20170"
        iscd_map = {"all": "0000", "kospi": "0001", "kosdaq": "1001"}
        iscd = iscd_map.get(market_scope, "0000")
        market_label = {"all": "unknown", "kospi": "kospi", "kosdaq": "kosdaq"}[market_scope]

        data = await self._get(
            "/uapi/domestic-stock/v1/quotations/volume-rank",
            tr_id="FHPST01710000",
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_COND_SCR_DIV_CODE": scr_code,
                "FID_INPUT_ISCD": iscd,
                "FID_DIV_CLS_CODE": "0",
                "FID_BLNG_CLS_CODE": "0",
                "FID_TRGT_CLS_CODE": "111111111",
                "FID_TRGT_EXLS_CLS_CODE": "000000",
                "FID_INPUT_PRICE_1": "0",
                "FID_INPUT_PRICE_2": "0",
                "FID_VOL_CNT": "0",
                "FID_INPUT_DATE_1": "",
            },
        )
        if data.get("rt_cd") != "0":
            return []
        items = data.get("output", [])[:limit]
        return [
            {
                "rank": int(item.get("data_rank", 0) or 0),
                "ticker": item.get("mksc_shrn_iscd", ""),
                "name": item.get("hts_kor_isnm", ""),
                "market": market_label,  # 호출 시 지정된 시장 (kospi/kosdaq/unknown)
                "price": int(item.get("stck_prpr", 0) or 0),
                "change_pct": float(item.get("prdy_ctrt", 0) or 0),
                "volume": int(item.get("acml_vol", 0) or 0),
                "trade_amount": int(item.get("acml_tr_pbmn", 0) or 0),
            }
            for item in items
        ]

    async def etf_price(self, ticker: str) -> dict[str, Any]:
        """Get ETF current price (same API as stock, market code 'J')."""
        return await self.stock_price(ticker)

    async def investor_trend(self, ticker: str) -> dict[str, Any]:
        """Get investor trading trend for a stock (today + recent days).

        Returns today's net buy/sell by investor type:
        - prsn: 개인
        - frgn: 외국인
        - orgn: 기관
        """
        data = await self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-investor",
            tr_id="FHKST01010900",
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker},
        )
        if data.get("rt_cd") != "0":
            return {"error": data.get("msg1", "unknown"), "ticker": ticker}
        items = data.get("output", [])
        if not items:
            return {"ticker": ticker, "no_data": True}

        def _safe_int(val: str | int) -> int:
            if not val or val == "":
                return 0
            try:
                return int(val)
            except (ValueError, TypeError):
                return 0

        # First item is today (may have partial data during market hours)
        today = items[0]
        return {
            "ticker": ticker,
            "date": today.get("stck_bsop_date", ""),
            "price": _safe_int(today.get("stck_clpr", 0)),
            "change": _safe_int(today.get("prdy_vrss", 0)),
            "individual_net_qty": _safe_int(today.get("prsn_ntby_qty", 0)),
            "foreign_net_qty": _safe_int(today.get("frgn_ntby_qty", 0)),
            "institution_net_qty": _safe_int(today.get("orgn_ntby_qty", 0)),
            "individual_net_amount": _safe_int(today.get("prsn_ntby_tr_pbmn", 0)),
            "foreign_net_amount": _safe_int(today.get("frgn_ntby_tr_pbmn", 0)),
            "institution_net_amount": _safe_int(today.get("orgn_ntby_tr_pbmn", 0)),
        }

    async def market_cap_rank(
        self,
        market: str = "0001",  # 0001=KOSPI, 1001=KOSDAQ
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get top stocks by market capitalization."""
        data = await self._get(
            "/uapi/domestic-stock/v1/ranking/market-cap",
            tr_id="FHPST01740000",
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_COND_SCR_DIV_CODE": "20174",
                "FID_INPUT_ISCD": market,
                "FID_DIV_CLS_CODE": "0",
                "FID_TRGT_CLS_CODE": "0",
                "FID_TRGT_EXLS_CLS_CODE": "0",
                "FID_INPUT_PRICE_1": "",
                "FID_INPUT_PRICE_2": "",
                "FID_VOL_CNT": "",
            },
        )
        if data.get("rt_cd") != "0":
            return []

        def _i(v: Any) -> int:
            try:
                return int(v) if v not in (None, "") else 0
            except (ValueError, TypeError):
                return 0

        items = data.get("output", [])[:limit]
        return [
            {
                "rank": _i(item.get("data_rank")),
                "ticker": item.get("mksc_shrn_iscd", ""),
                "name": item.get("hts_kor_isnm", ""),
                "price": _i(item.get("stck_prpr")),
                "market_cap": _i(item.get("stck_avls")),  # 시가총액 (억)
            }
            for item in items
        ]

    async def foreign_institution_top(
        self,
        market: str = "0000",  # 0000=전체, 0001=KOSPI, 1001=KOSDAQ
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Get top stocks by foreign+institution net buying (today).

        Returns per-stock net buy breakdown by investor type:
        - frgn: 외국인
        - orgn: 기관 전체
        - ivtr: 투신(금융투자)
        - insu: 보험
        - fund: 기금(연기금 근사)
        - etc_corp: 기타법인
        """
        data = await self._get(
            "/uapi/domestic-stock/v1/quotations/foreign-institution-total",
            tr_id="FHPTJ04400000",
            params={
                "FID_COND_MRKT_DIV_CODE": "V",
                "FID_COND_SCR_DIV_CODE": "16449",
                "FID_INPUT_ISCD": market,
                "FID_DIV_CLS_CODE": "0",
                "FID_RANK_SORT_CLS_CODE": "0",
                "FID_ETC_CLS_CODE": "0",
            },
        )
        if data.get("rt_cd") != "0":
            return []

        def _i(v: str | int) -> int:
            try:
                return int(v) if v not in (None, "", "00000000") else 0
            except (ValueError, TypeError):
                return 0

        def _f(v: str | int) -> float:
            try:
                return float(v) if v not in (None, "") else 0.0
            except (ValueError, TypeError):
                return 0.0

        items = data.get("output", [])[:limit]
        return [
            {
                "ticker": item.get("mksc_shrn_iscd", ""),
                "name": item.get("hts_kor_isnm", ""),
                "price": _i(item.get("stck_prpr")),
                "change_pct": _f(item.get("prdy_ctrt")),
                "volume": _i(item.get("acml_vol")),
                "foreign_net_qty": _i(item.get("frgn_ntby_qty")),
                "foreign_net_amount_m": _i(item.get("frgn_ntby_tr_pbmn")),  # 백만원
                "institution_net_qty": _i(item.get("orgn_ntby_qty")),
                "institution_net_amount_m": _i(item.get("orgn_ntby_tr_pbmn")),
                "fin_invest_net_qty": _i(item.get("ivtr_ntby_qty")),  # 금융투자(투신)
                "fin_invest_net_amount_m": _i(item.get("ivtr_ntby_tr_pbmn")),
                "insurance_net_qty": _i(item.get("insu_ntby_qty")),
                "pension_net_qty": _i(item.get("fund_ntby_qty")),  # 기금(연기금)
                "etc_corp_net_qty": _i(item.get("etc_corp_ntby_vol")),
                "total_net_qty": _i(item.get("ntby_qty")),
            }
            for item in items
        ]

    async def market_investor_summary(self) -> dict[str, Any]:
        """Market-level investor flow summary.

        Strategy:
        1. Query foreign_institution_top for KOSPI (0001) and KOSDAQ (1001)
        2. Aggregate net amounts across top 30 as market proxy
        3. Include per-investor-type totals (foreign/inst/fin_invest/pension)
        """
        kospi_top = await self.foreign_institution_top(market="0001", limit=30)
        kosdaq_top = await self.foreign_institution_top(market="1001", limit=30)

        def _aggregate(items: list[dict]) -> dict[str, Any]:
            if not items:
                return {"count": 0, "note": "no data"}
            totals = {
                "count": len(items),
                "foreign_net_amount_m_sum": sum(
                    i.get("foreign_net_amount_m", 0) for i in items
                ),
                "institution_net_amount_m_sum": sum(
                    i.get("institution_net_amount_m", 0) for i in items
                ),
                "fin_invest_net_amount_m_sum": sum(
                    i.get("fin_invest_net_amount_m", 0) for i in items
                ),
                "top_foreign_buys": sorted(
                    [i for i in items if i.get("foreign_net_amount_m", 0) > 0],
                    key=lambda x: -x["foreign_net_amount_m"],
                )[:5],
                "top_foreign_sells": sorted(
                    [i for i in items if i.get("foreign_net_amount_m", 0) < 0],
                    key=lambda x: x["foreign_net_amount_m"],
                )[:5],
            }
            return totals

        return {
            "kospi": {
                "aggregated": _aggregate(kospi_top),
                "top_30_raw": kospi_top,
            },
            "kosdaq": {
                "aggregated": _aggregate(kosdaq_top),
                "top_30_raw": kosdaq_top,
            },
            "note": "상위 30개 합산 기준. 시장 전체 정확한 합계 아님.",
        }
