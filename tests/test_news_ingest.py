"""뉴스 일일 적재 job 테스트 (NEWS-SOURCE-001 일일 cron 합류).

run_news_ingest 오케스트레이션 검증:
  - collect → upsert(raw) → classify → upsert(labeled) → build_news_digest 흐름.
  - 반환 dict 에 date/collected/classified/digest/elapsed_s/failures 키.
  - 한 단계 실패가 다음 단계를 막지 않고 격리된다 (graceful).
  - 수집 0건이면 classify 미호출, digest 는 여전히 호출(빈 집계 멱등).

실 RSS/LLM 금지 — collectors.news_source 함수를 전부 mock (함수 내부 import 라 원 소스 패치).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from collectors import news_source as ns
from server.schedulers.jobs.news_ingest import run_news_ingest


@dataclass
class _FakeItem:
    url: str
    labeled_by: str = "rss_raw"


@dataclass
class _FakeDigest:
    tone: str = "lean_bullish"
    source: str = "computed"
    top_themes: list = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.top_themes is None:
            self.top_themes = [{"theme": "반도체"}, {"theme": "금융"}]


@pytest.fixture
def patched_news(monkeypatch: pytest.MonkeyPatch) -> dict:
    """뉴스 collector 함수를 호출 추적 mock 으로 교체."""
    calls: dict = {"collect": 0, "upsert": [], "classify": 0, "digest": []}

    async def fake_collect(sources):
        calls["collect"] += 1
        return [_FakeItem(url="u1"), _FakeItem(url="u2")]

    def fake_upsert(items):
        calls["upsert"].append(len(items))
        return len(items)

    async def fake_classify(items, **kwargs):
        calls["classify"] += 1
        # 1건만 라벨 성공 가정
        items[0].labeled_by = "llm"
        return items

    def fake_digest(date, *, ticker=None, sector=None, persist=True):
        calls["digest"].append({"date": date, "persist": persist})
        return _FakeDigest()

    monkeypatch.setattr(ns, "collect_from_sources", fake_collect)
    monkeypatch.setattr(ns, "upsert_news_items", fake_upsert)
    monkeypatch.setattr(ns, "classify_news_items", fake_classify)
    monkeypatch.setattr(ns, "build_news_digest", fake_digest)
    # RssNewsSource 생성자가 config 읽지 않도록 가벼운 stub
    monkeypatch.setattr(ns, "RssNewsSource", lambda *a, **k: object())
    return calls


def test_full_flow_invoked(patched_news: dict) -> None:
    """collect → upsert×2 → classify → digest 전 단계 호출. 집계 키 존재."""
    result = asyncio.run(run_news_ingest(date="2026-06-08"))

    assert patched_news["collect"] == 1
    assert patched_news["upsert"] == [2, 2]  # raw + labeled
    assert patched_news["classify"] == 1
    assert patched_news["digest"] == [{"date": "2026-06-08", "persist": True}]

    assert set(result) >= {"date", "collected", "classified", "digest", "elapsed_s", "failures"}
    assert result["date"] == "2026-06-08"
    assert result["collected"] == 2
    assert result["classified"] == 1
    assert result["digest"]["tone"] == "lean_bullish"
    assert result["digest"]["themes"] == 2
    assert result["failures"] == []


def test_default_date_is_kst_today(patched_news: dict) -> None:
    """date 미지정 시 KST 오늘로 집계 호출 ('YYYY-MM-DD')."""
    result = asyncio.run(run_news_ingest())
    assert len(result["date"]) == 10 and result["date"][4] == "-"
    assert patched_news["digest"][0]["date"] == result["date"]


def test_classify_failure_isolated_digest_still_runs(
    monkeypatch: pytest.MonkeyPatch, patched_news: dict
) -> None:
    """classify 예외 → job 크래시 X. classify 격리 기록 + digest 는 여전히 실행."""

    async def boom(items, **kwargs):
        raise RuntimeError("gemini 503")

    monkeypatch.setattr(ns, "classify_news_items", boom)

    result = asyncio.run(run_news_ingest(date="2026-06-08"))

    assert any(f["stage"] == "classify" for f in result["failures"])
    assert "gemini 503" in result["failures"][0]["error"]
    # raw upsert 는 됐고, digest 는 그래도 호출됨
    assert patched_news["upsert"] == [2]  # labeled upsert 는 스킵
    assert patched_news["digest"]  # digest 호출됨
    assert result["digest"]["source"] == "computed"


def test_collect_failure_skips_classify(
    monkeypatch: pytest.MonkeyPatch, patched_news: dict
) -> None:
    """수집 실패 → items 비어 classify 미호출. digest 는 여전히 실행(빈 집계)."""

    async def boom(sources):
        raise RuntimeError("rss down")

    monkeypatch.setattr(ns, "collect_from_sources", boom)

    result = asyncio.run(run_news_ingest(date="2026-06-08"))

    assert any(f["stage"] == "collect" for f in result["failures"])
    assert patched_news["classify"] == 0  # 수집 0 → classify 스킵
    assert result["collected"] == 0
    assert patched_news["digest"]  # digest 는 여전히 호출
