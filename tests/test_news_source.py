"""NEWS-SOURCE-001 (MS-A 데이터 백본 + MS-B 분류·digest) — 테스트.

범위 (MS-A): NewsItem 라벨 확장(하위호환) · NewsSource 어댑터 3종 ·
news_source_items(url 멱등) / news_digest_snapshot((scope,date) 멱등) DB round-trip.
범위 (MS-B): classify_news_items(LLM 라벨, call_llm mock) · build_news_digest(결정론 집계) ·
render_news_digest_md([8] 블록).

LLM 실호출 없음 — classify 테스트는 call_llm 을 patch (anchors mirror). TESTING=1 강제.
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

os.environ.setdefault("TESTING", "1")

from collectors import news_source as ns
from collectors.news_rss import NewsItem
from collectors.news_source import (
    ManualNewsSource,
    NewsDigest,
    PerplexityNewsSource,
    RssNewsSource,
    build_news_digest,
    classify_news_items,
    collect_from_sources,
    get_news_digest,
    get_news_items,
    load_news_source_config,
    render_news_digest_md,
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


def test_config_has_classify_and_digest_blocks():
    cfg = load_news_source_config()
    assert cfg["classify"]["provider"] == "gemini"
    assert cfg["classify"]["max_tokens"] >= 512
    bands = cfg["digest"]["tone_bands"]
    assert bands["bearish"] < bands["lean_bearish"] < bands["lean_bullish"] < bands["bullish"]


# ---------------------------------------------------------------------------
# MS-B — classify_news_items (LLM 라벨, call_llm patch)
# ---------------------------------------------------------------------------
def _llm_resp(labels: dict) -> dict:
    """call_llm 반환 mock (anchors 테스트 패턴)."""
    return {
        "content": json.dumps(labels, ensure_ascii=False),
        "tokens_in": 50, "tokens_out": 20, "cost_usd": 0.0,
        "model": "gemini-2.5-flash", "raw": {},
    }


_VALID_LABELS = {
    "category": "macro_policy",
    "time_axis": "structural_trend",
    "direction": "up",
    "magnitude": 2,
    "confidence": 80,
    "affected_scope": "market",
    "affected_refs": [],
}


async def test_classify_applies_labels(isolated_db: Database):
    item = _item("http://n1", "Fed 인하")
    with patch("collectors.news_source.call_llm", return_value=_llm_resp(_VALID_LABELS)):
        out = await classify_news_items([item], skip_cache=True)
    it = out[0]
    assert it.labeled_by == "llm"
    assert it.category == "macro_policy"
    assert it.time_axis == "structural_trend"
    assert it.direction == "up"
    assert it.magnitude == 2
    assert it.confidence == 80


async def test_classify_invalid_label_keeps_unchanged(isolated_db: Database):
    """잘못된 카테고리 → graceful, 기존 라벨(rss_raw) 유지."""
    item = _item("http://n2", "ambiguous", labeled_by="rss_raw")
    bad = dict(_VALID_LABELS, category="not_a_category")
    with patch("collectors.news_source.call_llm", return_value=_llm_resp(bad)):
        out = await classify_news_items([item], skip_cache=True)
    assert out[0].labeled_by == "rss_raw"
    assert out[0].category is None


async def test_classify_graceful_on_exception(isolated_db: Database):
    item = _item("http://n3", "x", labeled_by="rss_raw")

    async def _raise(**kw):
        raise RuntimeError("network")

    with patch("collectors.news_source.call_llm", side_effect=_raise):
        out = await classify_news_items([item], skip_cache=True)
    assert out[0].labeled_by == "rss_raw"
    assert out[0].category is None


async def test_classify_cache_hit_skips_second_call(isolated_db: Database):
    """skip_cache=False → 첫 호출 저장, 둘째는 LLM 미호출 (라벨 영속)."""
    with patch("collectors.news_source.call_llm", return_value=_llm_resp(_VALID_LABELS)) as m:
        await classify_news_items([_item("http://n4", "제목")], skip_cache=False)
        assert m.call_count == 1

    async def _boom(**kw):
        raise AssertionError("cache 가 있는데 LLM 을 호출함")

    with patch("collectors.news_source.call_llm", side_effect=_boom):
        out = await classify_news_items([_item("http://n4", "제목")], skip_cache=False)
    assert out[0].labeled_by == "llm"
    assert out[0].category == "macro_policy"


async def test_classify_preserves_manual_affected(isolated_db: Database):
    """수동 입력 affected_refs 는 LLM 추정으로 덮어쓰지 않음 (사람 우선)."""
    item = _item("http://n5", "삼성", affected_scope="ticker", affected_refs=["005930"])
    labels = dict(_VALID_LABELS, affected_scope="market", affected_refs=[])
    with patch("collectors.news_source.call_llm", return_value=_llm_resp(labels)):
        out = await classify_news_items([item], skip_cache=True)
    assert out[0].affected_scope == "ticker"
    assert out[0].affected_refs == ["005930"]


# ---------------------------------------------------------------------------
# MS-B — build_news_digest (결정론 집계)
# ---------------------------------------------------------------------------
def _labeled(url, direction, magnitude, *, category="macro_policy",
             time_axis="structural_trend", confidence=80, refs=None,
             date="2026-06-07", title="t") -> NewsItem:
    return NewsItem(
        title=title, url=url, source="Yahoo",
        category=category, time_axis=time_axis, direction=direction,
        magnitude=magnitude, confidence=confidence,
        affected_scope=("ticker" if refs else "market"),
        affected_refs=list(refs or []), labeled_by="llm",
        collected_at=f"{date}T09:00:00+00:00",
    )


def test_digest_empty_is_neutral(isolated_db: Database):
    d = build_news_digest("2026-06-07")
    assert d.source == "empty"
    assert d.tone == "neutral"
    assert d.scope == "market"


def test_digest_bullish_tone(isolated_db: Database):
    upsert_news_items([
        _labeled("http://b1", "up", 3, confidence=90),
        _labeled("http://b2", "up", 3, confidence=90),
    ])
    d = build_news_digest("2026-06-07")
    assert d.source == "computed"
    assert d.tone == "bullish"
    assert d.catalyst_tilt["direction"] == "up"
    assert d.catalyst_tilt["strength"] == "strong"


def test_digest_bearish_tone(isolated_db: Database):
    upsert_news_items([
        _labeled("http://x1", "down", 3, confidence=90),
        _labeled("http://x2", "down", 2, confidence=80),
    ])
    d = build_news_digest("2026-06-07")
    assert d.tone == "bearish"
    assert d.catalyst_tilt["direction"] == "down"


def test_digest_category_counts(isolated_db: Database):
    upsert_news_items([
        _labeled("http://c1", "up", 2, category="macro_policy"),
        _labeled("http://c2", "down", 2, category="macro_policy"),
        _labeled("http://c3", "up", 1, category="geopolitics"),
    ])
    d = build_news_digest("2026-06-07")
    assert d.category_counts["macro_policy"] == {"up": 1, "neutral": 0, "down": 1}
    assert d.category_counts["geopolitics"]["up"] == 1


def test_digest_ticker_scope_filters_by_refs(isolated_db: Database):
    upsert_news_items([
        _labeled("http://t1", "up", 3, refs=["005930"], title="삼성 호재"),
        _labeled("http://t2", "down", 3, refs=["000660"], title="하이닉스 악재"),
    ])
    d = build_news_digest("2026-06-07", ticker="005930")
    assert d.scope == "ticker:005930"
    assert d.tone in ("lean_bullish", "bullish")
    # 다른 종목 뉴스는 raw 에 없어야
    assert "하이닉스" not in d.raw_labels
    assert "삼성" in d.raw_labels


def test_digest_top_themes(isolated_db: Database):
    upsert_news_items([
        _labeled("http://m1", "up", 2, refs=["005930"], title="삼성 1"),
        _labeled("http://m2", "up", 2, refs=["005930"], title="삼성 2"),
        _labeled("http://m3", "down", 1, refs=["000660"], title="하이닉스 1"),
    ])
    d = build_news_digest("2026-06-07")
    themes = {t["theme"]: t for t in d.top_themes}
    assert "005930" in themes
    assert len(themes["005930"]["trigger_titles"]) == 2


def test_digest_date_filter_excludes_other_days(isolated_db: Database):
    upsert_news_items([
        _labeled("http://d1", "up", 3, date="2026-06-07"),
        _labeled("http://d2", "down", 3, date="2026-06-06"),
    ])
    d = build_news_digest("2026-06-07")
    assert "http://d2" not in d.raw_labels
    assert d.catalyst_tilt["direction"] == "up"


def test_digest_persists_idempotent(isolated_db: Database):
    upsert_news_items([_labeled("http://p1", "up", 3)])
    build_news_digest("2026-06-07")
    build_news_digest("2026-06-07")  # 재실행
    rows = isolated_db.fetch_all("SELECT * FROM news_digest_snapshot WHERE scope='market'")
    assert len(rows) == 1
    stored = get_news_digest("market", "2026-06-07")
    assert stored is not None
    assert stored.tone == "bullish"


# ---------------------------------------------------------------------------
# MS-B — render_news_digest_md
# ---------------------------------------------------------------------------
def test_render_has_header_and_tone():
    d = NewsDigest(
        date="2026-06-07", scope="market", tone="lean_bullish",
        category_counts={"macro_policy": {"up": 2, "neutral": 0, "down": 0}},
        top_themes=[{"theme": "005930", "time_axis": "short_theme", "trigger_titles": ["삼성 호재"]}],
        catalyst_tilt={"direction": "up", "strength": "mid"},
        raw_labels="- [macro_policy/structural_trend] up(강도2,확신80%) Fed 인하",
        source="computed",
    )
    md = render_news_digest_md(d)
    assert "## [8] 뉴스 종합" in md
    assert "lean_bullish" in md
    assert "거시·통화·재정" in md  # 카테고리 한국어 라벨
    assert "삼성 호재" in md
    assert "정밀 점수 아님" in md  # M4 명시


def test_render_empty_digest():
    d = NewsDigest(date="2026-06-07", scope="market", tone="neutral", source="empty")
    md = render_news_digest_md(d)
    assert "분류된 뉴스 없음" in md
