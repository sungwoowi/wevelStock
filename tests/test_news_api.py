"""뉴스 API (PAPER-DESK-UX 뉴스 화면) — `/api/news/digest`·`/items` 라우터 read 조립 테스트.

기존 집계(build_news_digest)·테이블(news_digest_snapshot·news_source_items) read 만 — 신규 0.
LLM 실호출 없음(이미 분류된 item 직접 적재). TESTING=1.
"""
from __future__ import annotations

import asyncio
import os

import pytest

os.environ.setdefault("TESTING", "1")

from collectors import news_source as ns
from collectors.news_rss import NewsItem
from collectors.news_source import upsert_news_items
from core.db.connection import Database, reset_db
from server.api import news as news_api


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    db = Database(tmp_path / "test_news_api.sqlite")
    monkeypatch.setattr(ns, "get_db", lambda: db)
    ns.reload_news_source_config()
    return db


def _classified(url: str, title: str, **kw) -> NewsItem:
    return NewsItem(
        title=title,
        url=url,
        source=kw.pop("source", "Yahoo"),
        category=kw.pop("category", "macro_policy"),
        time_axis=kw.pop("time_axis", "short_theme"),
        direction=kw.pop("direction", "up"),
        magnitude=kw.pop("magnitude", 2),
        confidence=kw.pop("confidence", 80),
        affected_scope=kw.pop("affected_scope", "market"),
        labeled_by="llm",
        collected_at=kw.pop("collected_at", "2026-06-14T09:00:00"),
        **kw,
    )


def test_news_items_endpoint(isolated_db):
    upsert_news_items([
        _classified("u1", "Fed holds rates", category="macro_policy"),
        _classified("u2", "Chip demand surges", category="industry_trend"),
    ])
    res = asyncio.run(news_api.news_items(limit=30))
    assert res["count"] == 2
    assert "Fed holds rates" in {it["title"] for it in res["items"]}
    # category 필터
    res2 = asyncio.run(news_api.news_items(limit=30, category="industry_trend"))
    assert res2["count"] == 1
    assert res2["items"][0]["title"] == "Chip demand surges"


def test_news_digest_fallback_build(isolated_db):
    # snapshot 부재 → 당일 items 로 결정론 재집계(persist 0)
    upsert_news_items([
        _classified("u1", "Rally", direction="up", magnitude=3, collected_at="2026-06-14T09:00:00"),
    ])
    res = asyncio.run(news_api.news_digest(date="2026-06-14"))
    assert res["scope"] == "market"
    assert res["source"] == "computed"
    assert res["tone"] in ("bullish", "lean_bullish")


def test_news_digest_empty_graceful(isolated_db):
    res = asyncio.run(news_api.news_digest(date="2026-06-14"))
    assert res["source"] == "empty"
    assert res["tone"] == "neutral"
