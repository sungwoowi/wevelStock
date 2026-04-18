"""Stage: notify_analysis — LLM 분석 결과를 텔레그램/파일로 발송.

이 메시지의 성격:
- 해석/판단 중심
- 근거(reasons) + 출처(pipeline_id) 명시
- 단기/장기 전망 narrative
"""
from __future__ import annotations

from core.logging import get_logger
from core.notification import notify
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)


def _build_analysis_message(analyze_data: dict, pipeline_id: str) -> str:
    verdict = analyze_data.get("verdict", "unknown")
    confidence = analyze_data.get("confidence", 0)
    reasons = analyze_data.get("reasons", [])
    narrative = analyze_data.get("narrative", "")

    verdict_label = {
        "positive": "긍정",
        "neutral": "중립",
        "caution": "주의",
        "alert": "경고",
    }.get(verdict, verdict)

    lines: list[str] = []
    lines.append(f"[시장 분석 의견] 판단: {verdict_label} / 확신도: {confidence}%")
    lines.append(f"출처: {pipeline_id} | 모델: {analyze_data.get('model', '?')}")
    lines.append("")

    if narrative:
        if len(narrative) > 1200:
            narrative = narrative[:1197] + "..."
        lines.append("-- 종합 판단 --")
        lines.append(narrative)
        lines.append("")

    if reasons:
        lines.append("-- 근거 --")
        for i, r in enumerate(reasons[:7], 1):
            r_short = r if len(r) < 200 else r[:197] + "..."
            lines.append(f"{i}. {r_short}")

    return "\n".join(lines).rstrip()


class NotifyAnalysisStage(Stage):
    stage_id = "notify_analysis"
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
        body = _build_analysis_message(analyze_data, ctx.pipeline_id)

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
            title=f"[{ctx.date}] 시장 분석",
            body=body,
            related_run_id=ctx.run_id,
            related_target="global",
        )

        log.info(
            "analysis_notified",
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
                "verdict": verdict,
                "char_count": len(body),
            },
        )
