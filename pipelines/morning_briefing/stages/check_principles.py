"""Stage: check_principles — 투자 7계명 준수 체크.

포트폴리오가 있으면 7계명 체크, 없으면 pass.
"""
from __future__ import annotations

import json
from pathlib import Path

from checkers.principles import Thresholds, aggregate, run_all_checks
from core.logging import get_logger
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_PATH = REPO_ROOT / "data" / "seed" / "mock_portfolio.json"


class CheckPrinciplesStage(Stage):
    stage_id = "check_principles"
    stage_type = "check"

    async def run(self, ctx: StageContext) -> StageResult:
        # Load portfolio — seed or from context
        portfolio = ctx.data.get("portfolio")

        if portfolio is None and SEED_PATH.exists():
            raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
            # Use 'normal' scenario as default
            portfolio = raw.get("scenarios", {}).get("normal", {})

        if not portfolio:
            log.info("no_portfolio_for_principles_check", pipeline=ctx.pipeline_id)
            return StageResult(
                stage_id=self.stage_id,
                status="ok",
                data={"skipped": True, "reason": "no portfolio data"},
                verdict="compliant",
                confidence=100,
                reasons=["포트폴리오 데이터 없음 — 체크 생략"],
            )

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
