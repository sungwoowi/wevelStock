"""Stage: notify — briefing_parts 를 읽어 3분할 텔레그램 발송.

persist stage 가 이미 `briefing_parts` 에 3행을 저장해둠. 이 stage 는 그걸 조회
하여 `core.briefing.render.render_morning_pre()` 로 문자열을 만들고, 각 파트를
`core.notification.notify()` 로 전송한다. LLM mock 폴백 상태면 `status="degraded"`
로 렌더러에 전달하여 경고 prefix 가 붙게 한다.

렌더 로직은 `core/briefing/render.py` 에 있고 (웹앱/봇 공용). 이 stage 는
텔레그램 송신 orchestration 만 담당.
"""
from __future__ import annotations

from core.briefing import get_parts_by_run, render_morning_pre
from core.logging import get_logger
from core.notification import notify
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)


async def _send_part(ctx: StageContext, label: str, body: str) -> dict:
    return await notify(
        team_id=ctx.pipeline_id,
        level="info",
        title=f"[{ctx.date} 07:00] {label}",
        body=body,
        related_run_id=ctx.run_id,
        related_target="global",
    )


class NotifyStage(Stage):
    stage_id = "notify"
    stage_type = "act"

    async def run(self, ctx: StageContext) -> StageResult:
        parts = get_parts_by_run(ctx.pipeline_id, ctx.run_id)
        if not parts:
            log.warning("notify_no_parts", run_id=ctx.run_id)
            return StageResult(
                stage_id=self.stage_id,
                status="warning",
                error="no briefing_parts found for this run",
            )

        # LLM mock 폴백 상태 판정 — metadata.model 에 '-mock' suffix 가 붙음.
        analyze_data = ctx.get_stage_data("analyze") or {}
        model = (analyze_data.get("metadata") or {}).get("model", "") or ""
        llm_status = "degraded" if "-mock" in model else "ok"

        texts = render_morning_pre(parts, status=llm_status)
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
            "morning_pre_notified",
            pipeline=ctx.pipeline_id,
            parts=len(sent),
            channels=[s["channel"] for s in sent],
            llm_status=llm_status,
        )

        return StageResult(
            stage_id=self.stage_id,
            status="ok",
            data={"parts": sent, "llm_status": llm_status},
        )
