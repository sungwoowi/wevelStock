"""Stage: collect_market — 시세/환율/금리/지수 데이터 수집.

KIS API가 설정되어 있으면 실제 데이터, 아니면 seed 폴백.

수집 범위:
- 국내지수: KOSPI, KOSDAQ
- 해외지수: 나스닥, 필라델피아 반도체, 금 (yfinance)
- 주요 종목: 삼성전자, SK하이닉스
- 섹터 ETF 15개 + 강세 섹터 추출 (change_pct >= 1%)
- 거래대금 상위 + 사용자 필터 주도주
- 시장 수급: KOSPI/KOSDAQ 외국인/기관/투신/연기금
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from core.logging import get_logger
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_PATH = REPO_ROOT / "data" / "seed" / "mock_macro.json"

# 추적할 ETF 목록 (ticker, name)
TRACKED_ETFS = [
    ("091160", "KODEX 반도체"),
    ("396500", "KODEX AI반도체핵심장비"),
    ("394670", "KODEX AI반도체"),
    ("385590", "KODEX AI전력핵심"),
    ("472170", "ACE 원자력TOP10"),
    ("091180", "KODEX 자동차"),
    ("139260", "TIGER 200 금융"),
    ("139270", "TIGER 200 건설"),
    ("400590", "KODEX 방산TOP10"),
    ("492060", "TIGER K방산&우주"),
    ("466920", "TIGER 조선TOP10"),
    ("396510", "KODEX 로봇액티브"),
    ("305720", "KODEX 2차전지산업"),
    ("244580", "KODEX 바이오"),
    ("228790", "TIGER 화장품"),
]


def _filter_leading_stocks(
    volume_rank: list[dict[str, Any]],
    kospi_top20_tickers: set[str],
    kospi_limit: int = 10,
    kosdaq_limit: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    """거래대금 순위(이미 market 필드 포함)에서 사용자 규칙으로 주도주 분리.

    우선 필터:
      코스피: top20 내 >=3%, top20 밖 >=5%
      코스닥: >=5%
    필터 통과 개수가 limit에 못 미치면, 거래대금 상위 순으로 나머지를 채움.
    각 종목에 `match` 필드로 조건충족 여부 표시 ("meets_criteria" / "fill_by_amount").
    """
    kospi_matched: list[dict] = []
    kosdaq_matched: list[dict] = []
    kospi_rest: list[dict] = []
    kosdaq_rest: list[dict] = []

    for item in volume_rank:
        ticker = item.get("ticker", "")
        pct = item.get("change_pct", 0) or 0
        market = item.get("market", "unknown")

        if market == "kospi":
            is_top20 = ticker in kospi_top20_tickers
            threshold = 3.0 if is_top20 else 5.0
            enriched = {
                **item,
                "cap_tier": "top20" if is_top20 else "mid_small",
            }
            if pct >= threshold:
                enriched["match"] = "meets_criteria"
                kospi_matched.append(enriched)
            else:
                enriched["match"] = "fill_by_amount"
                kospi_rest.append(enriched)
        elif market == "kosdaq":
            enriched = dict(item)
            if pct >= 5.0:
                enriched["match"] = "meets_criteria"
                kosdaq_matched.append(enriched)
            else:
                enriched["match"] = "fill_by_amount"
                kosdaq_rest.append(enriched)

    # 부족분은 거래대금 상위로 채움 (volume_rank는 이미 거래대금 순 정렬됨)
    kospi = kospi_matched + kospi_rest
    kospi = kospi[:kospi_limit]
    kosdaq = kosdaq_matched + kosdaq_rest
    kosdaq = kosdaq[:kosdaq_limit]

    return {
        "kospi": kospi,
        "kosdaq": kosdaq,
        "stats": {
            "kospi_matched": len(kospi_matched),
            "kospi_fill": max(0, kospi_limit - len(kospi_matched)),
            "kosdaq_matched": len(kosdaq_matched),
            "kosdaq_fill": max(0, kosdaq_limit - len(kosdaq_matched)),
        },
    }


async def _collect_from_kis() -> dict:
    """Collect real market data from KIS API."""
    from connectors.kis import KISClient

    data: dict = {"source": "kis"}

    async with KISClient() as kis:
        # --- 국내지수 ---
        kospi = await kis.index_price("0001")
        kosdaq = await kis.index_price("1001")
        data["indices_domestic"] = {"kospi": kospi, "kosdaq": kosdaq}

        # --- 주요 종목 ---
        samsung = await kis.stock_price("005930")
        sk_hynix = await kis.stock_price("000660")
        data["major_stocks"] = {"samsung": samsung, "sk_hynix": sk_hynix}

        # --- ETF 섹터 15개 ---
        etf_results = []
        for ticker, name in TRACKED_ETFS:
            etf = await kis.etf_price(ticker)
            etf["name"] = name
            etf_results.append(etf)
        etf_results.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
        data["etf_sectors"] = etf_results
        data["strong_sectors"] = [
            e for e in etf_results if (e.get("change_pct") or 0) >= 1.0
        ]

        # --- 거래대금 상위: KOSPI 30 + KOSDAQ 30 (시장별 정확 분류) ---
        vol_kospi = await kis.volume_rank(limit=30, rank_type="amount", market_scope="kospi")
        vol_kosdaq = await kis.volume_rank(limit=30, rank_type="amount", market_scope="kosdaq")
        data["volume_rank_kospi"] = vol_kospi
        data["volume_rank_kosdaq"] = vol_kosdaq

        # --- KOSPI 시총 top20 (주도주 필터 기준) ---
        kospi_cap_top20 = await kis.market_cap_rank(market="0001", limit=20)
        data["market_cap_top20_kospi"] = kospi_cap_top20
        kospi_top20 = {m["ticker"] for m in kospi_cap_top20}

        # --- 주도주 분류 (사용자 규칙 기반) ---
        # KOSPI 주도주 10개, KOSDAQ 주도주 5개
        leading = _filter_leading_stocks(
            vol_kospi + vol_kosdaq,  # 이미 market 필드가 채워져 있음
            kospi_top20_tickers=kospi_top20,
            kospi_limit=10,
            kosdaq_limit=5,
        )
        data["leading_stocks"] = {
            "kospi": leading["kospi"],
            "kosdaq": leading["kosdaq"],
            "stats": leading["stats"],
            "note": "KOSPI 10 + KOSDAQ 5. 조건(top20+3% or 밖+5% / 코스닥 5%) 우선, 부족 시 거래대금 상위로 채움. match 필드 확인.",
        }

        # --- 시장 수급 (외국인/기관/투신/연기금) ---
        investor = await kis.market_investor_summary()
        data["investor_flow"] = investor

    return data


async def _collect_overseas() -> dict:
    """해외지수 수집 (나스닥/필라델피아 반도체/금) via yfinance."""
    try:
        from connectors.yfinance import get_indices
    except ImportError:
        return {"note": "yfinance connector not installed"}
    try:
        return await get_indices()
    except Exception as e:  # noqa: BLE001
        log.warning("yfinance_collect_failed", error=str(e))
        return {"error": str(e)}


def _collect_from_seed() -> dict:
    """Fallback: load seed data."""
    if not SEED_PATH.exists():
        return {"source": "seed", "error": "seed file not found"}
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return {
        "source": "seed",
        "date": raw.get("date"),
        "indicators": raw.get("indicators", {}),
        "notable_events": raw.get("notable_events", []),
        "summary_hint": raw.get("summary_hint", ""),
    }


class CollectMarketStage(Stage):
    stage_id = "collect_market"
    stage_type = "collect"

    async def run(self, ctx: StageContext) -> StageResult:
        use_kis = bool(os.getenv("KIS_APP_KEY"))

        if use_kis:
            try:
                # KIS + yfinance 병렬 실행 (rate limit 공유 안 됨)
                import asyncio as _asyncio
                kis_task = _asyncio.create_task(_collect_from_kis())
                overseas_task = _asyncio.create_task(_collect_overseas())
                data, overseas = await _asyncio.gather(kis_task, overseas_task)

                data["date"] = ctx.date
                data["indices_overseas"] = overseas

                # Logging summary
                kospi = data.get("indices_domestic", {}).get("kospi", {})
                strong_count = len(data.get("strong_sectors", []))
                leading_ks = len(
                    data.get("leading_stocks", {}).get("kospi", [])
                )
                leading_kq = len(
                    data.get("leading_stocks", {}).get("kosdaq", [])
                )

                log.info(
                    "market_data_collected",
                    pipeline=ctx.pipeline_id,
                    source="kis+yfinance",
                    kospi=f"{kospi.get('value','?')} ({kospi.get('change_pct','?')}%)",
                    strong_sectors=strong_count,
                    leading_kospi=leading_ks,
                    leading_kosdaq=leading_kq,
                )
                return StageResult(stage_id=self.stage_id, status="ok", data=data)

            except Exception as e:  # noqa: BLE001
                log.warning("kis_collect_failed_fallback_seed", error=str(e))

        data = _collect_from_seed()
        data["date"] = data.get("date", ctx.date)
        log.info(
            "market_data_collected",
            pipeline=ctx.pipeline_id,
            source="seed",
            indicator_count=len(data.get("indicators", {})),
        )
        return StageResult(stage_id=self.stage_id, status="ok", data=data)
