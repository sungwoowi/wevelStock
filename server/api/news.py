"""News API — 뉴스 종합(digest) + 수집 뉴스 리스트 (NEWS-SOURCE-001 소비, PAPER-DESK-UX 뉴스 화면).

기존 집계(`build_news_digest`)·테이블(`news_digest_snapshot`·`news_source_items`) read 조립 —
신규 테이블 0 (CLAUDE.md 절대원칙 #11). LLM·수집 0 (DB-first, 일일 cron 적재분 read).

Endpoints:
  GET /api/news/digest?date=&ticker=&sector= — 뉴스 종합(tone 5단·top_themes·catalyst_tilt)
  GET /api/news/items?limit=&category=       — 수집 뉴스 최신순

webapp `/news` 가 동일 소비. 빈 데이터 graceful(source='empty').
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date as date_cls

from fastapi import APIRouter

from collectors.news_source import (
    build_news_digest,
    digest_to_dict,
    get_news_digest,
    get_news_items,
)
from core.logging import get_logger

log = get_logger(__name__)

router = APIRouter()


@router.get("/news/digest")
async def news_digest(
    date: str | None = None, ticker: str | None = None, sector: str | None = None
) -> dict:
    """뉴스 종합 — DB-first `news_digest_snapshot`, 부재 시 당일 items 로 결정론 재집계(persist 0)."""
    day = date or date_cls.today().isoformat()
    scope = f"ticker:{ticker}" if ticker else f"sector:{sector}" if sector else "market"
    digest = get_news_digest(scope, day)
    if digest is None:
        digest = build_news_digest(day, ticker=ticker, sector=sector, persist=False)
    return digest_to_dict(digest)


@router.get("/news/items")
async def news_items(limit: int = 30, category: str | None = None) -> dict:
    """수집 뉴스 최신순 (`news_source_items`, collected_at DESC)."""
    items = get_news_items(category=category, limit=limit)
    return {"items": [asdict(it) for it in items], "count": len(items)}
