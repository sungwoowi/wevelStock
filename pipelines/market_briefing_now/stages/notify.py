"""Stage: notify — briefing_parts 를 읽어 3분할 텔레그램 발송.

봇/API 의 수동 호출은 `skip_notify=True` 로 들어와 스킵 (이중 발송 방지 — Phase 1 M6
패턴). scheduled cron 은 없지만 향후 추가 시를 위한 표준 stage.
"""
from __future__ import annotations

from core.briefing import get_parts_by_run, render_market_briefing
from core.logging import get_logger
from core.notification import notify
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)


async def _send_part(ctx: StageContext, label: str, body: str) -> dict:
    return await notify(
        team_id=ctx.pipeline_id,
        level="info",
        title=f"[{ctx.date}] {label}",
        body=body,
        related_run_id=ctx.run_id,
        related_target="global",
    )


class NotifyStage(Stage):
    stage_id = "notify"
    stage_type = "act"

    async def run(self, ctx: StageContext) -> StageResult:
        if ctx.data.get("skip_notify"):
            log.info(
                "notify_skipped",
                pipeline=ctx.pipeline_id,
                reason="skip_notify_flag",
            )
            return StageResult(
                stage_id=self.stage_id,
                status="ok",
                data={"skipped": True},
            )

        parts = get_parts_by_run(ctx.pipeline_id, ctx.run_id)
        if not parts:
            log.warning("notify_no_parts", run_id=ctx.run_id)
            return StageResult(
                stage_id=self.stage_id,
                status="warning",
                error="no briefing_parts found",
            )

        texts = render_market_briefing(parts)
        total = len(texts)

        sent: list[dict] = []
        for idx, (part, text) in enumerate(zip(parts, texts), 1):
            r = await _send_part(ctx, f"{part.label} {idx}/{total}", text)
            sent.append(
                {
                    "key": part.key,
                    "channel": r.get("channel"),
                    "chars": len(text),
                }
            )

        log.info(
            "market_briefing_notified",
            pipeline=ctx.pipeline_id,
            parts=len(sent),
            channels=[s["channel"] for s in sent],
        )
        return StageResult(
            stage_id=self.stage_id,
            status="ok",
            data={"parts": sent},
        )
