"""Stage: collect_news — Yahoo/CNBC/Google News RSS 헤드라인 수집.

Returns raw list of {title, url, source, published_at}. Impact tagging
happens downstream in the analyze stage (LLM judges from title only).
"""
from __future__ import annotations

from collectors.news_rss import fetch_news
from core.logging import get_logger
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)

MAX_NEWS_TO_LLM = 20


class CollectNewsStage(Stage):
    stage_id = "collect_news"
    stage_type = "collect"

    async def run(self, ctx: StageContext) -> StageResult:
        items = await fetch_news()

        # Cap at MAX_NEWS_TO_LLM to control LLM prompt size.
        capped = items[:MAX_NEWS_TO_LLM]

        log.info(
            "news_collected",
            pipeline=ctx.pipeline_id,
            total=len(items),
            sent_to_llm=len(capped),
        )

        status = "ok" if capped else "warning"
        return StageResult(
            stage_id=self.stage_id,
            status=status,
            data={
                "items": capped,
                "total_available": len(items),
            },
        )
