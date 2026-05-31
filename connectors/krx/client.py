"""KRX 정보데이터시스템 (data.krx.co.kr) 비공식 backend client.

KRX 공개 통계 페이지가 호출하는 `getJsonData.cmd` endpoint 를 직접 호출.
공식 OpenAPI 가 아니라 페이지 backend 라 referer/UA 헤더 필수.
"""
from __future__ import annotations

from typing import Any

import httpx

from core.logging import get_logger

log = get_logger(__name__)

_BASE_URL = "https://data.krx.co.kr"
_HEADERS = {
    "Referer": "https://data.krx.co.kr/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
}

# KOSPI200 선물 prodId (KRX 메인 위젯)
PRODID_K200_FUTURES = "KR___FUK2I"
BLD_MAIN_INVESTOR = "dbms/MDC/MAIN/MDCMAIN00103"

# 시장 등락 종목 수 (상승/하락/보합) — INFRA-SNAPSHOT-EXTEND-001
# KRX 통계 페이지 STAT/04/0402 의 backend bld. 정확한 spec 은 SLOT S4 = production smoke 시 검증.
BLD_MARKET_BREADTH = "dbms/MDC/STAT/standard/MDCSTAT04302"
MKTID_KOSPI = "STK"   # 코스피
MKTID_KOSDAQ = "KSQ"  # 코스닥

# 개별종목 투자자별 거래실적 (일별추이, 순매수 거래대금) — INFRA-STOCK-SUPPLY-001
# ⚠️ INTERVIEW-SLOT: 아래 bld+params 는 2026-05-31 smoke 에서 400 Bad Request. 유력 가설 =
#   isuCd 에 풀 ISIN(KR7005930003) 요구 + bld 일별추이=MDCSTAT02403 + mktId/inqTpCd params.
#   data.krx.co.kr 개별종목 투자자별 거래실적 페이지 devtools 로 실 POST 검증 필요 (pykrx 참고).
#   미해소 동안 collector 는 빈 결과 → flow_inputs 시장 프록시 fallback (비차단).
# 응답 단위는 원(₩) 가정 → 백만원으로 정규화. 컬럼 부재/오류 시 collector 가 시장 프록시 fallback.
BLD_STOCK_INVESTOR = "dbms/MDC/STAT/standard/MDCSTAT02401"
# KRX 응답 row 의 (5주체 → 순매수 거래대금 컬럼명) best-guess 맵. smoke 시 정정 지점.
_STOCK_INVESTOR_COLS = {
    "foreign_net": "FORN_NETBID_TRDVAL",        # 외국인
    "institution_net": "ORGN_NETBID_TRDVAL",    # 기관합계
    "individual_net": "PRSN_NETBID_TRDVAL",     # 개인
    "financial_inv_net": "FININV_NETBID_TRDVAL",  # 금융투자
    "pension_net": "PNST_NETBID_TRDVAL",        # 연기금등
}
_STOCK_DATE_KEYS = ("TRD_DD", "trd_dd")


def _parse_signed_int(s: str) -> int:
    """KRX 응답의 콤마 포함 부호 정수 → int. 빈 값/오류 시 0."""
    if s is None or s == "":
        return 0
    try:
        return int(s.replace(",", "").replace(" ", ""))
    except (ValueError, AttributeError):
        return 0


def _krx_date_to_iso(raw: str) -> str | None:
    """KRX 날짜("2026/05/31" | "20260531" | "2026.05.31") → "2026-05-31". 실패 시 None."""
    if not raw:
        return None
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    if len(digits) != 8:
        return None
    return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"


class KRXClient:
    """data.krx.co.kr getJsonData backend client (httpx)."""

    def __init__(self, timeout: float = 10.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            headers=_HEADERS,
            timeout=timeout,
        )

    async def __aenter__(self) -> "KRXClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._client.aclose()

    async def _post_json(self, payload: dict[str, str]) -> dict[str, Any]:
        r = await self._client.post(
            "/comm/bldAttendant/getJsonData.cmd",
            data=payload,
        )
        r.raise_for_status()
        return r.json()

    async def k200_futures_investor_today(self) -> dict[str, Any]:
        """KOSPI200 선물 당일 투자자별 매매 (3주체).

        KRX 메인 위젯 (MDCMAIN00103) 응답. 단위: 십억원.
        Returns:
        {
          "trade_date": "20260430",
          "individual_net_amount_b": int,   # 개인 순매수 (십억원)
          "foreign_net_amount_b": int,      # 외인
          "institution_net_amount_b": int,  # 기관
          "fetched_at_krx": "2026.04.30 PM 11:05:36",
          "source": "krx",
        }
        """
        data = await self._post_json({
            "prodId": PRODID_K200_FUTURES,
            "bld": BLD_MAIN_INVESTOR,
        })
        rows = data.get("output") or []

        result: dict[str, Any] = {
            "trade_date": "",
            "individual_net_amount_b": 0,
            "foreign_net_amount_b": 0,
            "institution_net_amount_b": 0,
            "fetched_at_krx": data.get("CURRENT_DATETIME", ""),
            "source": "krx",
        }
        for row in rows:
            tp = row.get("INVST_TP", "")
            net = _parse_signed_int(row.get("NETBID_TRDVAL", ""))
            if "개인" in tp:
                result["individual_net_amount_b"] = net
            elif "외국인" in tp:
                result["foreign_net_amount_b"] = net
            elif "기관" in tp:
                result["institution_net_amount_b"] = net
            if not result["trade_date"]:
                result["trade_date"] = row.get("TRD_DD", "")

        return result

    async def stock_investor_supply(
        self, ticker: str, *, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """개별종목 투자자별 순매수 거래대금 일별추이 (5주체). INFRA-STOCK-SUPPLY-001.

        Args:
            ticker: "005930" (6자리)
            start_date / end_date: "YYYYMMDD" (KRX 형식)

        Returns:
            per-date 행 리스트 (정순 보장 X — 호출부 정렬). 각 행:
            {"date": "2026-05-31", "foreign_net": int(백만원), "institution_net": ...,
             "individual_net": ..., "financial_inv_net": ..., "pension_net": ...}
            오류·빈 응답 시 [] (collector 가 시장 프록시 fallback).

        bld·컬럼명은 INTERVIEW-SLOT (production smoke 시 검증). 단위 원→백만원 정규화.
        """
        try:
            data = await self._post_json({
                "bld": BLD_STOCK_INVESTOR,
                "isuCd": ticker,
                "isuCd2": ticker,
                "strtDd": start_date,
                "endDd": end_date,
                "trdVolVal": "2",   # 2 = 거래대금 (1 = 거래량)
                "askBid": "3",      # 3 = 순매수
            })
        except Exception:  # noqa: BLE001 — 네트워크/HTTP 오류 → fallback 위해 빈 결과
            return []

        rows = data.get("output") or data.get("block1") or []
        out: list[dict[str, Any]] = []
        for row in rows:
            raw_date = ""
            for k in _STOCK_DATE_KEYS:
                if row.get(k):
                    raw_date = str(row[k])
                    break
            if not raw_date:
                continue
            iso = _krx_date_to_iso(raw_date)
            if iso is None:
                continue
            rec: dict[str, Any] = {"date": iso}
            for key, col in _STOCK_INVESTOR_COLS.items():
                won = _parse_signed_int(row.get(col, ""))
                rec[key] = won // 1_000_000  # 원 → 백만원
            out.append(rec)
        return out

    async def market_breadth(self, market: str = "KOSPI") -> dict[str, Any]:
        """시장 등락 종목 수 (상승/하락/보합/상한/하한). INFRA-SNAPSHOT-EXTEND-001.

        KRX 통계 페이지 backend (MDCSTAT04302) 호출. market_state_analyzer breadth 축 base.
        정확한 bld·payload 는 SLOT S4 = production smoke 시 검증. 차단 시 KIS 종목 list
        iterate fallback 안 검토.

        Args:
            market: "KOSPI" | "KOSDAQ"

        Returns:
            {
              "market": "KOSPI",
              "trade_date": "20260521",
              "advancing": int,    # 상승 종목 수
              "declining": int,    # 하락 종목 수
              "unchanged": int,    # 보합 종목 수
              "limit_up": int,     # 상한가
              "limit_down": int,   # 하한가
              "breadth_ratio": float,  # advancing / (advancing + declining)
              "source": "krx",
            }
        """
        from datetime import date as _date

        market_upper = market.upper()
        if market_upper == "KOSPI":
            mkt_id = MKTID_KOSPI
        elif market_upper == "KOSDAQ":
            mkt_id = MKTID_KOSDAQ
        else:
            raise ValueError(f"market must be 'KOSPI' or 'KOSDAQ', got {market!r}")

        today_str = _date.today().strftime("%Y%m%d")
        data = await self._post_json({
            "bld": BLD_MARKET_BREADTH,
            "mktId": mkt_id,
            "trdDd": today_str,
            "share": "1",
            "money": "1",
        })

        rows = data.get("output") or data.get("OutBlock_1") or []
        result: dict[str, Any] = {
            "market": market_upper,
            "trade_date": today_str,
            "advancing": 0,
            "declining": 0,
            "unchanged": 0,
            "limit_up": 0,
            "limit_down": 0,
            "breadth_ratio": 0.0,
            "source": "krx",
        }
        # KRX 응답 행 식별자가 한국어 라벨 ("상승" / "하락" / "보합") 로 추정.
        # 정확한 키는 SLOT S4 production 검증 시 확정. 일단 휴리스틱.
        for row in rows:
            label = row.get("ISU_NM", "") or row.get("INVST_TP_NM", "") or ""
            count = _parse_signed_int(row.get("ISU_CNT", "") or row.get("VAL", "0"))
            if "상승" in label and "상한" not in label:
                result["advancing"] = count
            elif "하락" in label and "하한" not in label:
                result["declining"] = count
            elif "보합" in label:
                result["unchanged"] = count
            elif "상한" in label:
                result["limit_up"] = count
            elif "하한" in label:
                result["limit_down"] = count

        denom = result["advancing"] + result["declining"]
        if denom > 0:
            result["breadth_ratio"] = round(result["advancing"] / denom, 4)
        return result
