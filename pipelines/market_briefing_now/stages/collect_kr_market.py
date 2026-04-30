"""Stage: collect_kr_market — 4 collectors via single shared KISClient.

KIS API 의 1초 rate limit 때문에 client 단위 직렬 호출. 4 collector 합 약 22 콜
+ 토큰 발급 = 약 24~28 초 소요. 이는 텔레그램 30~60 초 응답 윈도우 안.
"""
from __future__ import annotations

from collectors.kr_futures_supply_demand import fetch_kr_futures_supply_demand
from collectors.kr_indices import fetch_kr_indices
from collectors.kr_leading_stocks import fetch_kr_leading_stocks
from collectors.kr_sectors import fetch_kr_sectors
from collectors.kr_supply_demand import fetch_kr_supply_demand
from connectors.kis import KISClient
from core.logging import get_logger
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)


class CollectKrMarketStage(Stage):
    stage_id = "collect_kr_market"
    stage_type = "collect"

    async def run(self, ctx: StageContext) -> StageResult:
        futures_supply: dict = {}
        try:
            async with KISClient() as kis:
                indices = await fetch_kr_indices(kis)
                supply = await fetch_kr_supply_demand(kis)
                leading = await fetch_kr_leading_stocks(kis)
                sectors = await fetch_kr_sectors(kis)
            try:
                futures_supply = await fetch_kr_futures_supply_demand()
            except Exception as e:  # noqa: BLE001
                # KRX 비공식 endpoint 실패는 fatal 아님. 빈 dict 로 두고 진행.
                log.warning("kr_futures_supply_failed", error=str(e))
        except Exception as e:  # noqa: BLE001
            log.error("kr_market_collect_failed", error=str(e))
            return StageResult(
                stage_id=self.stage_id,
                status="error",
                error=str(e),
            )

        kospi = indices.get("kospi", {}).get("value")
        log.info(
            "kr_market_collected",
            kospi=kospi,
            kosdaq=indices.get("kosdaq", {}).get("value"),
            strong_sectors=len(sectors.get("strong", [])),
        )
        return StageResult(
            stage_id=self.stage_id,
            status="ok",
            data={
                "indices": indices,
                "supply_demand": supply,
                "futures_supply_demand": futures_supply,
                "leading_stocks": leading,
                "sectors": sectors,
            },
        )
