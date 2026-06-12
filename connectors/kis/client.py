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
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from dotenv import load_dotenv

from core.logging import get_logger

load_dotenv()
log = get_logger(__name__)

REAL_BASE = "https://openapi.koreainvestment.com:9443"
PAPER_BASE = "https://openapivts.koreainvestment.com:29443"

# Rate limit: KIS 실전서버는 초당 거래건수 제한이 매우 엄격함.
# 1.0초 간격으로는 가끔 "초당 거래건수 초과" 응답이 발생 (특히 무거운 path).
# 1.1초로 약간의 안전 마진을 두고, 그래도 실패하면 _get() 에서 1회 retry.
_CALL_INTERVAL = 1.1  # seconds

# Rate limit 응답을 받았을 때 retry 전 추가 대기. KIS 의 초당 카운터가
# 다음 초로 넘어가도록 충분히 기다림.
_RATE_LIMIT_BACKOFF = 1.5  # seconds
_MAX_RATE_LIMIT_RETRY = 1  # 호출당 최대 retry 횟수

# 업종지수 코드 (market_breadth 등락 종목수 — 전체 시장)
_BREADTH_INDEX_CODE = {"KOSPI": "0001", "KOSDAQ": "1001"}

# KIS 가 발급 응답의 `access_token_token_expired` 를 **KST(한국시간)** 으로 내려줌.
# 이를 UTC 로 오인하면 토큰을 실제보다 9 시간 늦게 만료로 캐싱 → 그 창 동안
# 로컬은 "유효"라 믿지만 KIS 는 이미 만료시켜 모든 호출이 "기간이 만료된 token"
# 으로 실패한다 (2026-06-11 chart_refresh 배치 전수 실패의 근본 원인).
_KST = timezone(timedelta(hours=9))

# 만료 시각보다 이만큼 일찍 선제 재발급 (clock skew + 네트워크 지연 안전 마진).
_TOKEN_REFRESH_MARGIN = timedelta(minutes=10)

# KIS 토큰 발급 "1분당 1회" 제한 대응: 거부 시 대기 후 재시도.
# (같은 app_key 를 쓰는 다른 프로세스가 직전 1 분 내 발급한 경우 등.)
_TOKEN_ISSUE_BACKOFF = 62.0  # seconds — KIS 1 분 창이 확실히 지나도록 약간의 여유
_MAX_TOKEN_ISSUE_RETRY = 1   # 발급당 최대 재시도 (총 2 회 시도)


class KISClient:
    """Async KIS API client with automatic token management.

    토큰은 **process-wide class-level cache** 로 공유 — 같은 KIS_APP_KEY 의
    모든 KISClient 인스턴스가 단일 토큰 reuse. KIS OAuth 의 "1분당 1회" 발급
    한도를 우회 (snapshot + chart 동시 호출 등 burst 시 토큰 재발급 충돌 방지).
    """

    # ------------------------------------------------------------------
    # Process-wide token cache (모든 인스턴스가 공유)
    # ------------------------------------------------------------------
    _shared_token: str | None = None
    _shared_token_expires: datetime | None = None
    _shared_token_key: str | None = None  # 토큰 발급한 app_key 추적 (멀티 계정 안전)
    _shared_token_lock: asyncio.Lock | None = None

    @classmethod
    def _get_token_lock(cls) -> asyncio.Lock:
        # asyncio.Lock 은 event loop 바인딩이 있어 module import 시 만들면 위험.
        # 첫 사용 시 lazy init. 단일 server process 단일 loop 가정.
        if cls._shared_token_lock is None:
            cls._shared_token_lock = asyncio.Lock()
        return cls._shared_token_lock

    def __init__(self) -> None:
        self._app_key = os.getenv("KIS_APP_KEY", "")
        self._app_secret = os.getenv("KIS_APP_SECRET", "")
        self._account_no = os.getenv("KIS_ACCOUNT_NO", "")
        self._is_paper = os.getenv("KIS_IS_PAPER", "true").lower() == "true"
        self._base = PAPER_BASE if self._is_paper else REAL_BASE
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

    @classmethod
    def _token_is_fresh(cls, app_key: str) -> bool:
        """캐시된 토큰이 같은 app_key 이고 만료 마진 이전이면 True."""
        now = datetime.now(timezone.utc)
        return bool(
            cls._shared_token
            and cls._shared_token_expires
            and cls._shared_token_key == app_key
            and now < cls._shared_token_expires - _TOKEN_REFRESH_MARGIN
        )

    async def _ensure_token(self, *, stale_token: str | None = None) -> str:
        """Get or refresh OAuth token. **Process-wide cache** — 모든 인스턴스 공유.

        - 같은 app_key 의 토큰이 살아있으면 즉시 반환 (만료 10 분 전까지)
        - 만료 또는 부재 시 lock 안에서 1번만 발급 (concurrent 호출 burst 안전)
        - stale_token: KIS 가 "기간이 만료된 token" 을 반환했을 때, 실패한 그 토큰을 넘기면
          캐시가 여전히 그 토큰을 들고 있을 때만 강제 재발급. (다른 task 가 이미 새 토큰을
          받았으면 그걸 reuse → 동시 burst 시 재발급 폭주 방지. 만료시각 캐시 오차와 무관하게
          동작하도록 토큰 문자열 일치로 판정.)
        """
        cls = type(self)
        forced = stale_token is not None
        if not forced and cls._token_is_fresh(self._app_key):
            return cls._shared_token  # type: ignore[return-value]

        async with cls._get_token_lock():
            # double-check (다른 task 가 lock 안에서 발급했을 수 있음).
            if forced:
                # 캐시가 더 이상 실패한 토큰이 아니면 (= 누군가 재발급함) 그걸 사용.
                if cls._shared_token_key == self._app_key and cls._shared_token not in (
                    None,
                    stale_token,
                ):
                    return cls._shared_token  # type: ignore[return-value]
            elif cls._token_is_fresh(self._app_key):
                return cls._shared_token  # type: ignore[return-value]

            url = f"{self._base}/oauth2/tokenP"
            body = {
                "grant_type": "client_credentials",
                "appkey": self._app_key,
                "appsecret": self._app_secret,
            }
            assert self._client is not None

            # KIS 는 접근토큰 발급을 "1분당 1회" 로 제한한다. 직전 1 분 내에 (이 프로세스가
            # 아니라 같은 app_key 를 쓰는 다른 프로세스가) 토큰을 발급했다면 발급이 거부된다.
            # 이때 한 번 실패하고 끝내면 배치 전 종목이 줄줄이 실패하므로, 제한 메시지면
            # 잠깐 기다렸다 재시도한다. (lock 보유 중이라 동시 발급 폭주는 없음.)
            data: dict = {}
            for attempt in range(_MAX_TOKEN_ISSUE_RETRY + 1):
                resp = await self._client.post(url, json=body)
                data = resp.json()
                if "access_token" in data:
                    break
                err_text = f"{data.get('msg1', '')} {data.get('error_description', '')}"
                rate_limited = "1분당" in err_text or data.get("error_code") == "EGW00133"
                if rate_limited and attempt < _MAX_TOKEN_ISSUE_RETRY:
                    log.warning(
                        "kis_token_issue_rate_limited",
                        attempt=attempt + 1,
                        wait_s=_TOKEN_ISSUE_BACKOFF,
                    )
                    await asyncio.sleep(_TOKEN_ISSUE_BACKOFF)
                    continue
                break

            if "access_token" not in data:
                raise RuntimeError(
                    f"KIS token failed: {data.get('error_description', data)}"
                )

            cls._shared_token = data["access_token"]
            cls._shared_token_key = self._app_key
            # Parse expiry: "2026-04-18 08:49:59" — KIS 는 이 시각을 **KST** 로 내려준다.
            # KST 로 파싱해야 now(UTC) 와 정합. (UTC 오인 시 9 시간 늦게 만료로 캐싱되어
            # 그 창 동안 만료된 토큰을 계속 재사용하는 버그 발생.)
            exp_str = data.get("access_token_token_expired", "")
            if exp_str:
                cls._shared_token_expires = datetime.strptime(
                    exp_str, "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=_KST)
            else:
                # 응답에 만료시각이 없으면 보수적으로 6 시간 후 만료로 가정 (KIS 기본 24h 보다 짧게).
                cls._shared_token_expires = datetime.now(timezone.utc) + timedelta(hours=6)

            log.info("kis_token_acquired_shared", expires=exp_str)
            # KIS rate limits count token requests — must wait before first data call
            await asyncio.sleep(2.0)
            self._last_call = asyncio.get_event_loop().time()
            return cls._shared_token

    @classmethod
    def reset_token_cache(cls) -> None:
        """테스트 전용 — process-wide 토큰 캐시 초기화."""
        cls._shared_token = None
        cls._shared_token_expires = None
        cls._shared_token_key = None

    async def _rate_limit(self) -> None:
        """Enforce minimum interval between API calls."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_call
        if elapsed < _CALL_INTERVAL:
            await asyncio.sleep(_CALL_INTERVAL - elapsed)
        self._last_call = asyncio.get_event_loop().time()

    async def _get(self, path: str, tr_id: str, params: dict) -> dict:
        """Make authenticated GET request. Retries once on rate-limit error,
        and once on expired-token error (캐시 만료시각 오차 등에 대한 방어)."""
        assert self._client is not None
        token = await self._ensure_token()
        token_retried = False

        data: dict = {}
        for attempt in range(_MAX_RATE_LIMIT_RETRY + 1):
            headers = {
                "authorization": f"Bearer {token}",
                "appkey": self._app_key,
                "appsecret": self._app_secret,
                "tr_id": tr_id,
                "content-type": "application/json; charset=utf-8",
            }
            await self._rate_limit()
            resp = await self._client.get(
                f"{self._base}{path}", headers=headers, params=params
            )
            data = resp.json()
            if data.get("rt_cd") == "0":
                return data

            msg = data.get("msg1", "") or ""
            if "초당 거래건수" in msg and attempt < _MAX_RATE_LIMIT_RETRY:
                log.warning(
                    "kis_rate_limited_retry",
                    path=path,
                    tr_id=tr_id,
                    attempt=attempt + 1,
                    msg=msg,
                )
                await asyncio.sleep(_RATE_LIMIT_BACKOFF)
                continue

            if "만료된 token" in msg and not token_retried:
                # 캐시가 만료된 토큰을 들고 있었음 → 강제 재발급 후 1 회 재시도.
                log.warning("kis_token_expired_refresh", path=path, tr_id=tr_id)
                token = await self._ensure_token(stale_token=token)
                token_retried = True
                continue

            log.warning(
                "kis_api_error",
                path=path,
                tr_id=tr_id,
                msg=msg or "unknown",
            )
            return data

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

    async def index_futures_price(self, symbol: str) -> dict[str, Any]:
        """국내 지수선물 현재가 (INFRA-MARKET-ASSETS-002 — KOSPI200 야간선물 best-effort).

        KIS `inquire-price` (FHMIF10000000, MRKT_DIV='F'). 야간 전용 시세 REST 엔드포인트는
        KIS 에 없음 — 이 일반 선물 시세가 **야간 세션(18:00~05:00 KST) 중 호출 시 야간가**를
        반환한다(세션 무구분). 단 (1) 월물 롤오버되는 계약 종목코드(예 "101W09")를 알아야 하고
        (2) 실계좌 선물옵션 시세 권한이 필요(모의계좌 제한 가능). 그래서 호출부가 env 심볼로
        게이팅하고, 실패/미설정 시 graceful null 로 강등한다.

        Args:
            symbol: KOSPI200 선물 종목코드 (예 "101W09" 최근월물). 빈 값이면 호출부가 skip.

        Returns:
            {symbol, price, change, change_pct, source}. rt_cd != 0 시 {error, symbol}.
        """
        data = await self._get(
            "/uapi/domestic-futureoption/v1/quotations/inquire-price",
            tr_id="FHMIF10000000",
            params={"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": symbol},
        )
        if data.get("rt_cd") != "0":
            return {"error": data.get("msg1", "unknown"), "symbol": symbol}
        o = data.get("output1") or data.get("output") or {}

        def _f(*keys: str) -> float | None:
            for k in keys:
                v = o.get(k)
                if v not in (None, ""):
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        continue
            return None

        return {
            "symbol": symbol,
            "price": _f("futs_prpr", "stck_prpr"),
            "change": _f("futs_prdy_vrss", "prdy_vrss"),
            "change_pct": _f("futs_prdy_ctrt", "prdy_ctrt"),
            "source": "kis_futures",
        }

    async def market_breadth(self, market: str = "KOSPI") -> dict[str, Any]:
        """전체 시장 등락 종목수 (상승/하락/보합/상한/하한). inquire-index-price (FHPUP02100000).

        KRX STAT breadth bld 가 Akamai 봇차단(getJsonData STAT 전 카테고리 "LOGOUT")으로
        폐기됨(2026-05-31) → KIS 업종지수 응답의 `*_issu_cnt` 필드가 **전체 시장** 종목수를
        직접 제공(거래대금 top30 대용이 아닌 정확값).

        Args:
            market: "KOSPI" | "KOSDAQ"

        Returns:
            {market, advancing, declining, unchanged, limit_up, limit_down,
             breadth_ratio, source}. rt_cd != 0 시 카운트 None + source="unavailable".
        """
        market_upper = market.upper()
        index_code = _BREADTH_INDEX_CODE.get(market_upper)
        if index_code is None:
            raise ValueError(f"market must be 'KOSPI' or 'KOSDAQ', got {market!r}")

        data = await self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-index-price",
            tr_id="FHPUP02100000",
            params={"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": index_code},
        )
        if data.get("rt_cd") != "0":
            return {
                "market": market_upper, "advancing": None, "declining": None,
                "unchanged": None, "limit_up": None, "limit_down": None,
                "breadth_ratio": None, "source": "unavailable",
            }
        o = data.get("output") or {}

        def _i(key: str) -> int:
            try:
                return int(o.get(key, 0) or 0)
            except (ValueError, TypeError):
                return 0

        advancing = _i("ascn_issu_cnt")  # 상승 종목수
        declining = _i("down_issu_cnt")  # 하락 종목수
        denom = advancing + declining
        return {
            "market": market_upper,
            "advancing": advancing,
            "declining": declining,
            "unchanged": _i("stnr_issu_cnt"),  # 보합
            "limit_up": _i("uplm_issu_cnt"),   # 상한
            "limit_down": _i("lslm_issu_cnt"),  # 하한
            "breadth_ratio": round(advancing / denom, 4) if denom > 0 else 0.0,
            "source": "kis_index",
        }

    async def volume_rank(
        self,
        limit: int = 30,
        rank_type: str = "amount",  # amount=거래대금, volume=거래량
        market_scope: str = "all",  # all=전체, kospi=코스피만, kosdaq=코스닥만
    ) -> list[dict[str, Any]]:
        """Get top stocks by trading volume or trade amount.

        실제 정렬 기준은 ``FID_BLNG_CLS_CODE``:
        - 0: 평균거래량
        - 1: 거래증가율
        - 2: 평균거래회전율
        - 3: 거래금액 (= 거래대금) ← rank_type="amount"
        - 4: 평균거래금액회전율

        ``FID_COND_SCR_DIV_CODE`` (20171) 는 화면 ID 로 정렬과 무관.

        KIS FID_INPUT_ISCD:
        - 0000 = 전체
        - 0001 = KOSPI만
        - 1001 = KOSDAQ만
        - 2001 = KOSPI200

        KIS OpenAPI는 한 호출당 30개 상한. 페이징 미지원.
        """
        # 정렬 기준 (FID_BLNG_CLS_CODE) — KIS docs 기준
        blng_map = {"amount": "3", "volume": "0"}
        fid_blng = blng_map.get(rank_type, "3")
        iscd_map = {"all": "0000", "kospi": "0001", "kosdaq": "1001"}
        iscd = iscd_map.get(market_scope, "0000")
        market_label = {"all": "unknown", "kospi": "kospi", "kosdaq": "kosdaq"}[market_scope]

        data = await self._get(
            "/uapi/domestic-stock/v1/quotations/volume-rank",
            tr_id="FHPST01710000",
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_COND_SCR_DIV_CODE": "20171",
                "FID_INPUT_ISCD": iscd,
                "FID_DIV_CLS_CODE": "0",
                "FID_BLNG_CLS_CODE": fid_blng,
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

    async def stock_investor_history(self, ticker: str) -> list[dict[str, Any]]:
        """종목별 투자자 순매수 거래대금 일별 시계열 (3주체: 외인·기관·개인).

        inquire-investor (FHKST01010900) output = 당일 + 최근 일자들. INFRA-STOCK-SUPPLY-001.
        Returns:
            [{"date": "2026-05-31", "foreign_net": int(백만원),
              "institution_net": int, "individual_net": int}] (정순 보장 X — 호출부 정렬).
            오류 시 [] (collector 가 시장 프록시 fallback).
        단위: `*_ntby_tr_pbmn`(순매수 거래대금)은 KIS 에서 **이미 백만원** 단위 — 변환 없음.
              (market_investor_total 가 동일 필드를 백만원으로 취급하는 것과 정합. 실서버 005930
               검증: frgn -327,750=−3,278억 / orgn 1,666,582=+1.67조. 2026-05-31 단위 버그 정정.)
        """
        data = await self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-investor",
            tr_id="FHKST01010900",
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker},
        )
        if data.get("rt_cd") != "0":
            return []

        def _m(v: Any) -> int:
            if v in (None, ""):
                return 0
            try:
                return int(v)  # 이미 백만원
            except (ValueError, TypeError):
                return 0

        out: list[dict[str, Any]] = []
        for it in data.get("output", []):
            raw_d = str(it.get("stck_bsop_date", ""))
            if len(raw_d) != 8:
                continue
            out.append({
                "date": f"{raw_d[0:4]}-{raw_d[4:6]}-{raw_d[6:8]}",
                "foreign_net": _m(it.get("frgn_ntby_tr_pbmn")),
                "institution_net": _m(it.get("orgn_ntby_tr_pbmn")),
                "individual_net": _m(it.get("prsn_ntby_tr_pbmn")),
            })
        return out

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
                "pension_net_amount_m": _i(item.get("fund_ntby_tr_pbmn")),
                "etc_corp_net_qty": _i(item.get("etc_corp_ntby_vol")),
                "total_net_qty": _i(item.get("ntby_qty")),
            }
            for item in items
        ]

    async def market_investor_total(self, market: str) -> dict[str, Any]:
        """Whole-market investor net flow (today, cumulative).

        Uses inquire-investor-time-by-market (FHPTJ04030000) — returns one
        aggregated row per market with all investor categories. Unit: 백만원.

        market: "kospi" | "kosdaq"
        """
        if market == "kospi":
            mkt_code, sector_code = "KSP", "0001"
        elif market == "kosdaq":
            mkt_code, sector_code = "KSQ", "1001"
        else:
            raise ValueError(f"market must be 'kospi' or 'kosdaq', got {market!r}")

        data = await self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-investor-time-by-market",
            tr_id="FHPTJ04030000",
            params={
                "FID_INPUT_ISCD": mkt_code,
                "FID_INPUT_ISCD_2": sector_code,
            },
        )
        if data.get("rt_cd") != "0":
            return {"error": data.get("msg1", "unknown"), "market": market}

        rows = data.get("output1") or data.get("output") or []
        if not rows:
            return {"market": market, "no_data": True}
        row = rows[0]

        def _i(v: str | int | None) -> int:
            if v in (None, "", "00000000"):
                return 0
            try:
                return int(v)
            except (ValueError, TypeError):
                return 0

        return {
            "market": market,
            "individual_net_amount_m": _i(row.get("prsn_ntby_tr_pbmn")),
            "foreign_net_amount_m": _i(row.get("frgn_ntby_tr_pbmn")),
            "institution_net_amount_m": _i(row.get("orgn_ntby_tr_pbmn")),
            "fin_invest_net_amount_m": _i(row.get("scrt_ntby_tr_pbmn")),
            "pension_net_amount_m": _i(row.get("fund_ntby_tr_pbmn")),
        }

    # ------------------------------------------------------------------
    # Chart data APIs (INFRA-CHART-DATA-001)
    # ------------------------------------------------------------------

    # 지수 ticker → 별도 endpoint (`inquire-daily-indexchartprice` + tr_id FHKUP03500100).
    # 주식·ETF 와 응답 키 prefix 다름 (stck_* → bstp_nmix_*) + prdy_ctrt 부재 (직접 계산).
    # INFRA-SNAPSHOT-EXTEND-001 SLOT S5 — cycle 13.3 정정 (sample 응답 검증 후).
    _INDEX_TICKERS: frozenset[str] = frozenset({"0001", "1001", "2001"})

    async def get_daily_chart(
        self,
        ticker: str,
        *,
        period_days: int = 1825,
        adjust: bool = True,
    ) -> list[dict[str, Any]]:
        """일봉 OHLCV historical.

        - 주식·ETF: KIS `inquire-daily-itemchartprice` (FHKST03010100), MRKT_DIV='J',
          응답 키 stck_*. 수정주가 옵션 (FID_ORG_ADJ_PRC).
        - 지수 (0001/1001/2001): KIS `inquire-daily-indexchartprice` (FHKUP03500100),
          MRKT_DIV='U', 응답 키 bstp_nmix_*. 수정주가 무관. change_rate 직접 계산
          (전일 close 대비). INFRA-SNAPSHOT-EXTEND-001 SLOT S5 정정.

        KIS 응답은 1 회 호출 당 최대 ~100 봉. 5 년 (1825 봉) 은 페이징으로 누적.

        Returns:
            list of {date, open, high, low, close, volume, change_rate, value}
            (정순 = 과거 → 최신, 최대 period_days 길이)
        """
        from datetime import date as _date
        from datetime import timedelta

        today = _date.today()
        start_dt = today - timedelta(days=int(period_days * 1.6))  # 주말·휴장 보정
        is_index = ticker in self._INDEX_TICKERS
        if is_index:
            endpoint = "/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice"
            tr_id = "FHKUP03500100"
            base_params = {
                "FID_COND_MRKT_DIV_CODE": "U",
                "FID_INPUT_ISCD": ticker,
                "FID_PERIOD_DIV_CODE": "D",
            }
        else:
            endpoint = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
            tr_id = "FHKST03010100"
            base_params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": ticker,
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "1" if adjust else "0",
            }

        bars: list[dict[str, Any]] = []
        seen: set[str] = set()
        cur_end = today

        # 페이징: KIS 가 한 번에 100 봉씩 반환. 가장 과거 봉의 날짜로 cur_end 갱신.
        # 안전 가드: 최대 25 회 (= 2500 봉). period_days 1825 의 1.4 배 여유.
        for _ in range(25):
            data = await self._get(
                endpoint,
                tr_id=tr_id,
                params={
                    **base_params,
                    "FID_INPUT_DATE_1": start_dt.strftime("%Y%m%d"),
                    "FID_INPUT_DATE_2": cur_end.strftime("%Y%m%d"),
                },
            )
            if data.get("rt_cd") != "0":
                break
            rows = data.get("output2") or []
            new_bars: list[dict[str, Any]] = []
            for r in rows:
                d_raw = r.get("stck_bsop_date") or ""
                if not d_raw or d_raw in seen:
                    continue
                # YYYYMMDD → YYYY-MM-DD
                d_iso = f"{d_raw[:4]}-{d_raw[4:6]}-{d_raw[6:8]}"
                try:
                    if is_index:
                        open_v = float(r.get("bstp_nmix_oprc") or 0)
                        high_v = float(r.get("bstp_nmix_hgpr") or 0)
                        low_v = float(r.get("bstp_nmix_lwpr") or 0)
                        close_v = float(r.get("bstp_nmix_prpr") or 0)
                        chg_rate = 0.0  # 지수 응답에 prdy_ctrt 없음 — 정렬 후 일괄 계산
                    else:
                        open_v = float(r.get("stck_oprc") or 0)
                        high_v = float(r.get("stck_hgpr") or 0)
                        low_v = float(r.get("stck_lwpr") or 0)
                        close_v = float(r.get("stck_clpr") or 0)
                        chg_rate = float(r.get("prdy_ctrt") or 0)
                    vol_v = int(float(r.get("acml_vol") or 0))
                    val_v = int(float(r.get("acml_tr_pbmn") or 0))
                except (ValueError, TypeError):
                    continue
                if close_v <= 0:
                    continue
                seen.add(d_raw)
                new_bars.append({
                    "date": d_iso,
                    "open": open_v,
                    "high": high_v,
                    "low": low_v,
                    "close": close_v,
                    "volume": vol_v,
                    "value": val_v,
                    "change_rate": chg_rate,
                })
            if not new_bars:
                break
            bars.extend(new_bars)
            if len(bars) >= period_days:
                break
            oldest = min(new_bars, key=lambda b: b["date"])["date"]
            # 다음 페이지: oldest 직전 날짜까지
            from datetime import datetime as _dt
            cur_end = _dt.strptime(oldest, "%Y-%m-%d").date() - timedelta(days=1)
            if cur_end <= start_dt:
                break

        # 정순 (과거 → 최신) 정렬 + period_days 길이 cap
        bars.sort(key=lambda b: b["date"])
        if len(bars) > period_days:
            bars = bars[-period_days:]

        # 지수: change_rate 가 응답에 부재 → 정렬 후 (close[i] - close[i-1]) / close[i-1] 일괄 계산
        if is_index and bars:
            prev_close = bars[0]["close"]
            for b in bars[1:]:
                if prev_close > 0:
                    b["change_rate"] = round((b["close"] - prev_close) / prev_close * 100, 4)
                prev_close = b["close"]
        return bars

    async def get_current_price(self, ticker: str) -> dict[str, Any]:
        """현재 시점 snapshot 7 필드. INFRA-CHART-DATA-001 명세.

        `stock_price` 의 응답을 chart_data_md snapshot 형식으로 reformat.
        """
        raw = await self.stock_price(ticker)
        if "error" in raw:
            return {"error": raw["error"], "ticker": ticker}
        return {
            "ticker": ticker,
            "current_price": raw.get("price", 0),
            "open_price": raw.get("open", 0),
            "high_price": raw.get("high", 0),
            "low_price": raw.get("low", 0),
            "change_rate": raw.get("change_pct", 0.0),
            "volume_today": raw.get("volume", 0),
            "value_today": raw.get("trade_amount", 0),
        }

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
                "pension_net_amount_m_sum": sum(
                    i.get("pension_net_amount_m", 0) for i in items
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
