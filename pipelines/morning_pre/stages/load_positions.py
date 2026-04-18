"""Stage: load_positions — DB에서 watch_positions + sim_positions 로드.

Loads both:
  - watch_positions (status in {watching, holding}): 수동 등록 관심/보유 종목
  - sim_positions (status in {holding, partial_exit}): AI 시뮬 현재 포지션

Output shape passed downstream:
{
    "watch": [{ticker, name, market, status, watch_price, ...}, ...],
    "sim":   [{ticker, name, avg_price, total_quantity, buy_count, ...}, ...],
    "counts": {"watch": N, "sim": M}
}
"""
from __future__ import annotations

from core.db import get_db
from core.logging import get_logger
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)


def _rows_to_dicts(rows: list) -> list[dict]:
    return [dict(r) for r in rows]


class LoadPositionsStage(Stage):
    stage_id = "load_positions"
    stage_type = "collect"

    async def run(self, ctx: StageContext) -> StageResult:
        db = get_db()

        try:
            watch_rows = db.fetch_all(
                """
                SELECT id, ticker, name, market, status, watch_price,
                       buy_signal_cnt, sell_signal_cnt, hold_signal_cnt,
                       last_signal_at, last_signal_type, notes
                FROM watch_positions
                WHERE status IN ('watching', 'holding')
                ORDER BY updated_at DESC, created_at DESC
                """
            )
        except Exception as e:  # noqa: BLE001
            log.warning("watch_positions_load_failed", error=str(e))
            watch_rows = []

        try:
            sim_rows = db.fetch_all(
                """
                SELECT ticker, name, avg_price, total_quantity,
                       buy_count, sell_count, realized_pnl, unrealized_pnl,
                       status, first_entry_at, last_trade_at
                FROM sim_positions
                WHERE status IN ('holding', 'partial_exit')
                ORDER BY last_trade_at DESC
                """
            )
        except Exception as e:  # noqa: BLE001
            log.warning("sim_positions_load_failed", error=str(e))
            sim_rows = []

        watch = _rows_to_dicts(watch_rows)
        sim = _rows_to_dicts(sim_rows)

        log.info(
            "positions_loaded",
            pipeline=ctx.pipeline_id,
            watch_count=len(watch),
            sim_count=len(sim),
        )

        return StageResult(
            stage_id=self.stage_id,
            status="ok",
            data={
                "watch": watch,
                "sim": sim,
                "counts": {"watch": len(watch), "sim": len(sim)},
            },
        )
