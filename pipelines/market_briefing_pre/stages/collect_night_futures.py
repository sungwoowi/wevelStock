"""Stage: collect_night_futures — KOSPI200 야간선물 (KIS 실선물 1순위 → CME → EWY 대용).

INFRA-MARKET-ASSETS-002: KIS 실계좌 선물 시세를 1순위로 — 기존 EWY ETF 대용을 진짜
KOSPI200 야간선물로 교체. fetch_night_futures 가 폴백 체인 처리.
"""
from __future__ import annotations

from collectors.kr_futures import fetch_night_futures
from core.logging import get_logger
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)


class CollectNightFuturesStage(Stage):
    stage_id = "collect_night_futures"
    stage_type = "collect"

    async def run(self, ctx: StageContext) -> StageResult:
        data = await fetch_night_futures()

        futures = data.get("kospi200_cme_night", {})
        has_error = "error" in futures
        status = "warning" if has_error else "ok"

        log.info(
            "night_futures_collected",
            pipeline=ctx.pipeline_id,
            source=futures.get("source"),
            change_pct=futures.get("change_pct"),
            error=futures.get("error"),
        )

        return StageResult(
            stage_id=self.stage_id,
            status=status,
            data={"night_futures": data},
        )
