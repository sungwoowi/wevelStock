"""Stage: collect_night_futures — CME KOSPI200 야간 선물 (EWY 대체)."""
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
