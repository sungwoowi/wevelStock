"""Stage: persist — collect_kr_market 결과를 briefing_parts 3행 저장.

LLM 분석 없는 raw 데이터 발송. predictions/sim_trades 미사용 (장중 관찰 목적).
"""
from __future__ import annotations

from core.briefing import upsert_parts
from core.contracts.briefing_part import BriefingPart
from core.logging import get_logger
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)

_PARTS_META: list[tuple[str, str, int]] = [
    ("market_overview", "시장개요", 1),
    ("supply_sectors", "수급+강세섹터", 2),
    ("leading_stocks", "주도주", 3),
]


class PersistStage(Stage):
    stage_id = "persist"
    stage_type = "act"

    async def run(self, ctx: StageContext) -> StageResult:
        market = ctx.get_stage_data("collect_kr_market") or {}
        indices = market.get("indices") or {}
        supply = market.get("supply_demand") or {}
        leading = market.get("leading_stocks") or {}
        sectors = market.get("sectors") or {}

        parts = [
            BriefingPart(
                key=_PARTS_META[0][0],
                label=_PARTS_META[0][1],
                order=_PARTS_META[0][2],
                data={
                    "indices": indices,
                    "fetched_at": indices.get("fetched_at"),
                },
            ),
            BriefingPart(
                key=_PARTS_META[1][0],
                label=_PARTS_META[1][1],
                order=_PARTS_META[1][2],
                data={
                    "supply_demand": supply,
                    "sectors": sectors,
                },
            ),
            BriefingPart(
                key=_PARTS_META[2][0],
                label=_PARTS_META[2][1],
                order=_PARTS_META[2][2],
                data={
                    "leading_stocks": leading,
                },
            ),
        ]

        try:
            upsert_parts(ctx.pipeline_id, ctx.run_id, parts)
        except Exception as e:  # noqa: BLE001
            log.warning("market_briefing_persist_failed", error=str(e))
            return StageResult(
                stage_id=self.stage_id,
                status="warning",
                error=str(e),
                data={"counts": {"briefing_parts": 0}},
            )

        log.info("market_briefing_persisted", pipeline=ctx.pipeline_id, parts=len(parts))
        return StageResult(
            stage_id=self.stage_id,
            status="ok",
            data={"counts": {"briefing_parts": len(parts)}},
        )
