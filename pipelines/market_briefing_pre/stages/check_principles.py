"""Stage: check_principles — 7계명 준수 체크 (morning_pre).

load_positions 의 sim_positions 를 portfolio 로 변환하여 체크.
watch_positions 는 평단/수량이 없어 비중 계산이 불가 — 제외.
"""
from __future__ import annotations

from checkers.principles import Thresholds, aggregate, run_all_checks
from core.logging import get_logger
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)


def _build_portfolio_from_sim(sim_positions: list[dict]) -> dict:
    """Convert sim_positions rows to a portfolio dict expected by checkers.

    checkers/principles expects roughly:
      {
        "holdings": [{ticker, market, avg_price, quantity, current_value, ...}],
        "total_value": number,
        "cash": number,
        ...
      }

    Without live prices we use avg_price × quantity as an approximation of
    current value — enough for weight/limit checks.
    """
    holdings = []
    total = 0.0
    for p in sim_positions:
        qty = p.get("total_quantity") or 0
        avg = p.get("avg_price") or 0.0
        value = float(qty) * float(avg)
        total += value
        holdings.append({
            "ticker": p.get("ticker"),
            "name": p.get("name"),
            "avg_price": avg,
            "quantity": qty,
            "current_value": value,
            "strategy": "swing",
        })
    return {
        "holdings": holdings,
        "total_value": total,
        "cash": 0.0,
    }


class CheckPrinciplesStage(Stage):
    stage_id = "check_principles"
    stage_type = "check"

    async def run(self, ctx: StageContext) -> StageResult:
        positions = ctx.get_stage_data("load_positions")
        sim = positions.get("sim", []) if positions else []

        if not sim:
            log.info("no_sim_positions_principles_skip", pipeline=ctx.pipeline_id)
            return StageResult(
                stage_id=self.stage_id,
                status="ok",
                data={"skipped": True, "reason": "no sim positions"},
                verdict="compliant",
                confidence=100,
                reasons=["AI 시뮬 포지션 없음 — 체크 생략"],
            )

        portfolio = _build_portfolio_from_sim(sim)
        results = run_all_checks(portfolio, Thresholds())
        verdict, confidence, reasons, data = aggregate(results)

        log.info(
            "principles_checked",
            pipeline=ctx.pipeline_id,
            verdict=verdict,
            violations=len(data.get("violations", [])),
        )

        return StageResult(
            stage_id=self.stage_id,
            status="warning" if verdict == "violation" else "ok",
            data=data,
            verdict=verdict,
            confidence=confidence,
            reasons=reasons,
        )
