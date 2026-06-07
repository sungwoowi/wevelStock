"""NEWS-SOURCE-001 (MS-A 데이터 백본) — 어댑터 + DB 영속 테스트.

범위 (MS-A): NewsItem 라벨 확장(하위호환) · NewsSource 어댑터 3종 ·
news_items(url 멱등) / news_digest_snapshot((scope,date) 멱등) DB round-trip.
분류(classify_news_items) · 집계(build_news_digest) 는 MS-B (별 테스트).

LLM 실호출 없음 (MS-A 는 LLM 미사용). RSS fetch 는 mock.
"""
from __future__ import annotations

import pytest

from collectors import news_source as ns
from collectors.news_rss import NewsItem
from collectors.news_source import (
    ManualNewsSource,
    NewsDigest,
    PerplexityNewsSource,
    RssNewsSource,
    collect_from_sources,
    get_news_digest,
    get_news_items,
    load_news_source_config,
    upsert_news_digest,
    upsert_news_items,
)
from core.db.connection import Database, reset_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    """temp DB + news_source 모듈 get_db 패치 (market_view 패턴 mirror)."""
    reset_db()
    db = Database(tmp_path / "test_news.sqlite")
    monkeypatch.setattr(ns, "get_db", lambda: db)
    ns.reload_news_source_config()
    return db


def _item(url: str, title: str = "t", **kw) -> NewsItem:
    return NewsItem(title=title, url=url, source=kw.pop("source", "Yahoo"), **kw)


# ---------------------------------------------------------------------------
# NewsItem 하위호환 + round-trip
# ---------------------------------------------------------------------------
def test_to_dict_backward_compatible_four_keys():
    """브리핑 collect_news 하위호환 — to_dict 는 기존 4 키만 (동작 불변)."""
    it = NewsItem(title="A", url="http://x", source="CNBC", published_at="2026-06-07")
    assert it.to_dict() == {
        "title": "A",
        "url": "http://x",
        "source": "CNBC",
        "published_at": "2026-06-07",
    }


def test_news_item_label_defaults_none():
    """라벨 필드는 전부 Optional 기본값 — 기존 4-인자 생성 호환."""
    it = NewsItem(title="A", url="http://x", source="CNBC")
    assert it.category is None
    assert it.magnitude is None
    assert it.affected_refs == []
    assert it.labeled_by is None


def test_to_record_from_record_round_trip():
    it = NewsItem(
        title="삼성전자 신고가",
        url="http://news/1",
        source="GoogleNews",
        published_at="2026-06-07",
        body="요약 본문",
        category="corporate_events",
        time_axis="short_theme",
        direction="up",
        magnitude=2,
        confidence=80,
        affected_scope="ticker",
        affected_refs=["005930"],
        labeled_by="llm",
        collected_at="2026-06-07T09:00:00+00:00",
    )
    rec = it.to_record()
    # 계약대로 affected 중첩
    assert rec["affected"] == {"scope": "ticker", "refs": ["005930"]}
    back = NewsItem.from_record(rec)
    assert back == it


# ---------------------------------------------------------------------------
# 어댑터
# ---------------------------------------------------------------------------
async def test_rss_source_labels_raw_and_collected(monkeypatch):
    raw = [_item("http://a", "A"), _item("http://b", "B")]

    async def _fake_fetch_items(*, queries=None, limit_per_source=15):
        return [NewsItem(title=i.title, url=i.url, source=i.source) for i in raw]

    monkeypatch.setattr(ns, "fetch_news_items", _fake_fetch_items)
    items = await RssNewsSource().fetch()
    assert len(items) == 2
    assert all(i.labeled_by == "rss_raw" for i in items)
    assert all(i.collected_at for i in items)


async def test_manual_source_parses_and_skips_missing():
    src = ManualNewsSource(
        records=[
            {"title": "유튜브 요약", "url": "http://m/1", "body": "본문", "affected_refs": ["005930"]},
            {"title": "no url"},  # url 결측 → skip
            {"url": "http://m/2"},  # title 결측 → skip
        ]
    )
    items = await src.fetch()
    assert len(items) == 1
    it = items[0]
    assert it.labeled_by == "manual"
    assert it.body == "본문"
    assert it.affected_refs == ["005930"]
    assert it.collected_at


async def test_perplexity_source_not_implemented():
    with pytest.raises(NotImplementedError):
        await PerplexityNewsSource().fetch()


async def test_collect_from_sources_dedup_and_graceful(monkeypatch):
    raw = [_item("http://dup", "1"), _item("http://uniq", "2")]

    async def _fake_fetch_items(*, queries=None, limit_per_source=15):
        return [NewsItem(title=i.title, url=i.url, source=i.source) for i in raw]

    monkeypatch.setattr(ns, "fetch_news_items", _fake_fetch_items)
    manual = ManualNewsSource(records=[{"title": "dup manual", "url": "http://dup"}])
    # RSS 먼저 → http://dup 은 RSS 가 선점, Perplexity 는 graceful skip
    merged = await collect_from_sources([RssNewsSource(), manual, PerplexityNewsSource()])
    urls = [i.url for i in merged]
    assert urls == ["http://dup", "http://uniq"]  # dedup, RSS wins
    assert sum(1 for u in urls if u == "http://dup") == 1


# ---------------------------------------------------------------------------
# DB — news_items (url 멱등)
# ---------------------------------------------------------------------------
def test_upsert_and_get_news_items_round_trip(isolated_db: Database):
    items = [
        _item("http://1", "첫", category="macro_policy", direction="down", magnitude=3),
        _item("http://2", "둘", category="industry_trend", direction="up", labeled_by="llm"),
    ]
    n = upsert_news_items(items)
    assert n == 2
    got = get_news_items(limit=10)
    assert len(got) == 2
    by_url = {g.url: g for g in got}
    assert by_url["http://1"].category == "macro_policy"
    assert by_url["http://1"].magnitude == 3
    assert by_url["http://2"].direction == "up"


def test_news_items_url_idempotent(isolated_db: Database):
    upsert_news_items([_item("http://x", "old", category=None)])
    # 같은 url 재적재 → 라벨 갱신, 행 증가 없음
    upsert_news_items([_item("http://x", "new", category="geopolitics", direction="down")])
    got = get_news_items(limit=10)
    assert len(got) == 1
    assert got[0].title == "new"
    assert got[0].category == "geopolitics"


def test_get_news_items_filters_category(isolated_db: Database):
    upsert_news_items(
        [
            _item("http://a", category="macro_policy", collected_at="2026-06-07T01:00:00+00:00"),
            _item("http://b", category="geopolitics", collected_at="2026-06-07T02:00:00+00:00"),
        ]
    )
    got = get_news_items(category="geopolitics")
    assert [g.url for g in got] == ["http://b"]


# ---------------------------------------------------------------------------
# DB — news_digest_snapshot ((scope, date) 멱등)
# ---------------------------------------------------------------------------
def test_digest_round_trip_and_idempotent(isolated_db: Database):
    d = NewsDigest(
        date="2026-06-07",
        scope="market",
        tone="lean_bullish",
        category_counts={"macro_policy": {"up": 2, "neutral": 1, "down": 0}},
        top_themes=[{"theme": "금리인하", "time_axis": "structural_trend", "trigger_titles": ["t1"]}],
        catalyst_tilt={"direction": "up", "strength": "mid"},
        raw_labels="...",
        source="computed",
    )
    upsert_news_digest(d)
    got = get_news_digest("market", "2026-06-07")
    assert got is not None
    assert got.tone == "lean_bullish"
    assert got.category_counts["macro_policy"]["up"] == 2
    assert got.top_themes[0]["theme"] == "금리인하"
    assert got.catalyst_tilt == {"direction": "up", "strength": "mid"}
    assert got.source == "db"

    # 같은 (scope, date) 재적재 → 갱신, 행 증가 없음
    d2 = NewsDigest(date="2026-06-07", scope="market", tone="bearish", source="computed")
    upsert_news_digest(d2)
    got2 = get_news_digest("market", "2026-06-07")
    assert got2.tone == "bearish"
    rows = isolated_db.fetch_all("SELECT * FROM news_digest_snapshot")
    assert len(rows) == 1


def test_get_digest_missing_returns_none(isolated_db: Database):
    assert get_news_digest("ticker:005930", "2026-06-07") is None


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------
def test_config_has_six_categories_three_axes():
    cfg = load_news_source_config()
    assert len(cfg["categories"]) == 6
    assert "market_sentiment" in cfg["categories"]
    assert len(cfg["time_axes"]) == 3
    assert cfg["sources"]["rss"]["enabled"] is True
    assert cfg["sources"]["perplexity"]["enabled"] is False
