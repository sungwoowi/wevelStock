"""Stage: notify — 분석 결과를 텔레그램/파일로 발송."""
from __future__ import annotations

from core.logging import get_logger
from core.notification import notify
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)


def _format_briefing(analyze_data: dict) -> str:
    """Format analysis result into a human-readable briefing message."""
    verdict = analyze_data.get("verdict", "unknown")
    confidence = analyze_data.get("confidence", 0)
    reasons = analyze_data.get("reasons", [])
    narrative = analyze_data.get("narrative", "")

    verdict_emoji = {
        "positive": "[긍정]",
        "neutral": "[중립]",
        "caution": "[주의]",
        "alert": "[경고]",
    }.get(verdict, f"[{verdict}]")

    lines = [
        f"아침 시황 브리핑 {verdict_emoji}",
        f"확신도: {confidence}%",
        "",
    ]

    if narrative:
        # Truncate if too long for Telegram
        if len(narrative) > 500:
            narrative = narrative[:497] + "..."
        lines.append(narrative)
        lines.append("")

    if reasons:
        lines.append("--- 주요 근거 ---")
        for i, r in enumerate(reasons[:5], 1):
            lines.append(f"{i}. {r}")

    return "\n".join(lines)


class NotifyStage(Stage):
    stage_id = "notify"
    stage_type = "act"

    async def run(self, ctx: StageContext) -> StageResult:
        analyze_data = ctx.get_stage_data("analyze")

        if not analyze_data:
            return StageResult(
                stage_id=self.stage_id,
                status="warning",
                data={"skipped": True, "reason": "no analysis data"},
            )

        verdict = analyze_data.get("verdict", "neutral")
        body = _format_briefing(analyze_data)

        # Determine notification level
        level_map = {
            "positive": "info",
            "neutral": "info",
            "caution": "warning",
            "alert": "critical",
        }
        level = level_map.get(verdict, "info")

        result = await notify(
            team_id=ctx.pipeline_id,
            level=level,
            title=f"[{ctx.date}] 아침 시황 브리핑",
            body=body,
            related_run_id=ctx.run_id,
            related_target="global",
        )

        log.info(
            "briefing_notified",
            pipeline=ctx.pipeline_id,
            channel=result.get("channel"),
            verdict=verdict,
        )

        return StageResult(
            stage_id=self.stage_id,
            status="ok",
            data={
                "channel": result.get("channel"),
                "telegram_ok": result.get("telegram_ok", False),
            },
        )
