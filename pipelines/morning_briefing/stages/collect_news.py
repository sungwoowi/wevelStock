"""Stage: collect_news — 뉴스/시황 수집 + 분류.

현재: mock 뉴스 데이터 반환 (seed 모드)
추후: 뉴스 API + LLM 분류로 교체
"""
from __future__ import annotations

from core.logging import get_logger
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)


class CollectNewsStage(Stage):
    stage_id = "collect_news"
    stage_type = "collect"

    async def run(self, ctx: StageContext) -> StageResult:
        # --- Seed mode (MVP): 하드코딩 mock 뉴스 ---
        mock_news = [
            {
                "category": "macro",
                "horizon": "long_term",
                "headline": "연준, 금리 동결 유지 전망 강화",
                "sentiment": "neutral",
            },
            {
                "category": "sector",
                "horizon": "short_term",
                "headline": "AI 반도체 수요 급증, TSMC 실적 호조",
                "sentiment": "positive",
            },
            {
                "category": "geopolitics",
                "horizon": "long_term",
                "headline": "미중 무역 협상 ��전 소식",
                "sentiment": "positive",
            },
        ]

        log.info(
            "news_collected",
            pipeline=ctx.pipeline_id,
            source="mock",
            count=len(mock_news),
        )

        return StageResult(
            stage_id=self.stage_id,
            status="ok",
            data={
                "source": "mock",
                "news": mock_news,
                "news_count": len(mock_news),
            },
        )
