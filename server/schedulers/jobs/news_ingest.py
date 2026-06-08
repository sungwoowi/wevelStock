"""뉴스 일일 적재 job (NEWS-SOURCE-001 후속 SLOT "일일 cron").

평일 18:05 KST 일일 허브(run_daily_refresh)의 뉴스 단계. 그동안 뉴스 적재
(fetch→classify→digest)는 함수만 있고 cron 에 미등록이었다 → 본 job 으로 합류.

흐름:
  1. collect_from_sources([RssNewsSource()]) — 자동수집 RSS fetch (url dedup, 어댑터 graceful)
  2. upsert_news_items() — news_source_items url 멱등 적재 (raw 내구성 먼저)
  3. classify_news_items() — LLM 라벨 (gemini, llm_call_cache url 멱등 → 재호출 캐시 hit)
  4. upsert_news_items() — 라벨 재적재
  5. build_news_digest(today) — 'market' scope 결정론 tone 집계 + news_digest_snapshot 멱등

멱등: url PK(news_source_items) / (scope,date) PK(news_digest_snapshot) → 하루 여러 번 안전.
graceful: 외부 호출(RSS/Gemini) 실패가 전체를 막지 않도록 단계별 격리. snapshot_macro 패턴 mirror.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from core.logging import get_logger

log = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")


def _today_kst_str() -> str:
    """us_macro._today_kst_str mirror — 적재 날짜는 KST 기준."""
    return datetime.now(_KST).strftime("%Y-%m-%d")


async def run_news_ingest(date: str | None = None) -> dict[str, Any]:
    """뉴스 일일 적재 entrypoint. 일일 허브가 호출.

    Args:
        date: 집계 대상 KST 날짜('YYYY-MM-DD'). None 시 오늘(KST).

    Returns:
        {
          "date": str,
          "collected": int,        # RSS 수집 건수
          "classified": int,       # LLM 라벨 성공 건수
          "digest": {"tone": ..., "source": ..., "themes": int} 또는 {"error": ...},
          "elapsed_s": float,
          "failures": [{"stage": ..., "error": ...}],
        }
    """
    from collectors.news_source import (
        RssNewsSource,
        build_news_digest,
        classify_news_items,
        collect_from_sources,
        upsert_news_items,
    )

    target_date = date or _today_kst_str()
    started = time.monotonic()
    log.info("news_ingest_start", date=target_date)

    failures: list[dict[str, str]] = []
    collected = 0
    classified = 0
    digest_result: dict[str, Any] = {}

    # 1~2단계: 수집 + raw 내구성 적재
    items: list[Any] = []
    try:
        items = await collect_from_sources([RssNewsSource()])
        collected = len(items)
        upsert_news_items(items)
        log.info("news_ingest_collected", count=collected)
    except Exception as e:  # noqa: BLE001
        log.exception("news_ingest_collect_failed", error=str(e))
        failures.append({"stage": "collect", "error": str(e)})

    # 3~4단계: LLM 분류 + 라벨 재적재 (캐시 멱등). 수집분이 있을 때만.
    if items:
        try:
            classified_items = await classify_news_items(items)
            classified = sum(1 for it in classified_items if it.labeled_by == "llm")
            upsert_news_items(classified_items)
            log.info("news_ingest_classified", labeled=classified, total=len(classified_items))
        except Exception as e:  # noqa: BLE001
            log.exception("news_ingest_classify_failed", error=str(e))
            failures.append({"stage": "classify", "error": str(e)})

    # 5단계: 결정론 집계 (market scope). 분류 실패해도 적재된 항목으로 집계.
    try:
        digest = build_news_digest(target_date, persist=True)
        digest_result = {
            "tone": digest.tone,
            "source": digest.source,
            "themes": len(digest.top_themes),
        }
        log.info("news_ingest_digest_done", tone=digest.tone, source=digest.source)
    except Exception as e:  # noqa: BLE001
        log.exception("news_ingest_digest_failed", error=str(e))
        digest_result = {"error": str(e)}
        failures.append({"stage": "digest", "error": str(e)})

    elapsed = time.monotonic() - started
    log.info(
        "news_ingest_done",
        date=target_date,
        collected=collected,
        classified=classified,
        elapsed_s=round(elapsed, 2),
        failures=len(failures),
    )
    return {
        "date": target_date,
        "collected": collected,
        "classified": classified,
        "digest": digest_result,
        "elapsed_s": round(elapsed, 2),
        "failures": failures,
    }
