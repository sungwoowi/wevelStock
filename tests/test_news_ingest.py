"""뉴스 일일 적재 job 테스트 (NEWS-SOURCE-001 일일 cron 합류 + 다중 scope 누적).

run_news_ingest 오케스트레이션 검증:
  - collect → upsert(raw) → universe/name_map → classify(name_code_map=) → upsert(labeled)
    → build_news_digest 다중 scope(market + 종목 N + 섹터) 흐름.
  - 반환 dict 에 date/collected/classified/digest/scopes_persisted/scopes_failed/failures 키.
  - 한 단계(수집·분류·universe·개별 scope) 실패가 나머지를 막지 않고 격리된다 (graceful).
  - 수집 0건이면 classify 미호출, digest scope 루프는 여전히 실행(빈 집계 멱등).
  - market scope digest 반환 키 하위호환 유지.

실 RSS/LLM/KIS 금지 — collectors.news_source 함수 + _build_universe_and_name_map 전부 mock.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from collectors import news_source as ns
from collectors.kr_sectors import DEFAULT_TRACKED_ETFS
from server.schedulers.jobs import news_ingest as ni
from server.schedulers.jobs.news_ingest import run_news_ingest

_N_SECTORS = len(DEFAULT_TRACKED_ETFS)


@dataclass
class _FakeItem:
    url: str
    labeled_by: str = "rss_raw"


@dataclass
class _FakeDigest:
    scope: str = "market"
    tone: str = "lean_bullish"
    source: str = "computed"
    top_themes: list = field(default_factory=lambda: [{"theme": "반도체"}, {"theme": "금융"}])


@pytest.fixture
def patched_news(monkeypatch: pytest.MonkeyPatch) -> dict:
    """뉴스 collector 함수 + universe 헬퍼를 호출 추적 mock 으로 교체."""
    calls: dict = {
        "collect": 0,
        "upsert": [],
        "classify": 0,
        "classify_kwargs": {},
        "digest": [],
        "upsert_digest": [],
        "universe": 0,
    }
    # 테스트별로 특정 scope 의 digest.source 를 'empty' 로 만들거나 예외를 던지도록 설정.
    empty_scopes: set[str] = set()
    boom_scopes: set[str] = set()
    calls["_empty_scopes"] = empty_scopes
    calls["_boom_scopes"] = boom_scopes

    async def fake_collect(sources):
        calls["collect"] += 1
        return [_FakeItem(url="u1"), _FakeItem(url="u2")]

    def fake_upsert(items):
        calls["upsert"].append(len(items))
        return len(items)

    async def fake_classify(items, **kwargs):
        calls["classify"] += 1
        calls["classify_kwargs"] = kwargs
        items[0].labeled_by = "llm"
        return items

    async def fake_universe():
        calls["universe"] += 1
        return ["005930", "000660"], {"삼성전자": "005930"}

    def fake_digest(date, *, ticker=None, sector=None, persist=True):
        if ticker:
            scope = f"ticker:{ticker}"
        elif sector:
            scope = f"sector:{sector}"
        else:
            scope = "market"
        calls["digest"].append({"date": date, "ticker": ticker, "sector": sector, "persist": persist})
        if scope in boom_scopes:
            raise RuntimeError(f"digest boom {scope}")
        src = "empty" if scope in empty_scopes else "computed"
        return _FakeDigest(scope=scope, source=src)

    def fake_upsert_digest(digest):
        calls["upsert_digest"].append(digest.scope)

    monkeypatch.setattr(ns, "collect_from_sources", fake_collect)
    monkeypatch.setattr(ns, "upsert_news_items", fake_upsert)
    monkeypatch.setattr(ns, "classify_news_items", fake_classify)
    monkeypatch.setattr(ns, "build_news_digest", fake_digest)
    monkeypatch.setattr(ns, "upsert_news_digest", fake_upsert_digest)
    monkeypatch.setattr(ni, "_build_universe_and_name_map", fake_universe)
    # RssNewsSource 생성자가 config 읽지 않도록 가벼운 stub
    monkeypatch.setattr(ns, "RssNewsSource", lambda *a, **k: object())
    return calls


def test_full_flow_invoked(patched_news: dict) -> None:
    """collect → upsert×2 → universe → classify → 다중 scope digest. market 키 하위호환."""
    result = asyncio.run(run_news_ingest(date="2026-06-08"))

    assert patched_news["collect"] == 1
    assert patched_news["upsert"] == [2, 2]  # raw + labeled
    assert patched_news["universe"] == 1
    assert patched_news["classify"] == 1

    # market(1) + universe 종목(2) + 섹터(N) 만큼 digest 빌드·영속
    expected = 1 + 2 + _N_SECTORS
    assert len(patched_news["digest"]) == expected
    assert len(patched_news["upsert_digest"]) == expected
    # market scope 가 첫 호출 (ticker/sector None)
    assert patched_news["digest"][0] == {
        "date": "2026-06-08", "ticker": None, "sector": None, "persist": False,
    }

    assert set(result) >= {
        "date", "collected", "classified", "digest",
        "scopes_persisted", "scopes_failed", "elapsed_s", "failures",
    }
    assert result["date"] == "2026-06-08"
    assert result["collected"] == 2
    assert result["classified"] == 1
    assert result["digest"]["tone"] == "lean_bullish"   # market scope 하위호환
    assert result["digest"]["themes"] == 2
    assert result["scopes_persisted"] == expected
    assert result["scopes_failed"] == 0
    assert result["failures"] == []


def test_default_date_is_kst_today(patched_news: dict) -> None:
    """date 미지정 시 KST 오늘로 집계 호출 ('YYYY-MM-DD')."""
    result = asyncio.run(run_news_ingest())
    assert len(result["date"]) == 10 and result["date"][4] == "-"
    assert patched_news["digest"][0]["date"] == result["date"]


def test_classify_receives_name_code_map(patched_news: dict) -> None:
    """classify 가 universe 헬퍼의 name_code_map 을 주입받는다 (캐노니컬화 입력)."""
    asyncio.run(run_news_ingest(date="2026-06-08"))
    assert patched_news["classify_kwargs"].get("name_code_map") == {"삼성전자": "005930"}


def test_digest_loop_market_universe_sectors(patched_news: dict) -> None:
    """scope 루프 = market + universe 종목 + 전체 섹터. 각 scope 인자 정확."""
    asyncio.run(run_news_ingest(date="2026-06-08"))
    scopes = [
        (d["ticker"], d["sector"]) for d in patched_news["digest"]
    ]
    assert (None, None) in scopes                       # market
    assert ("005930", None) in scopes and ("000660", None) in scopes  # universe
    sector_names = {name for _, name in DEFAULT_TRACKED_ETFS}
    for name in sector_names:
        assert (None, name) in scopes                   # 모든 섹터


def test_digest_scope_failure_isolated(patched_news: dict) -> None:
    """한 종목 scope 가 예외 → 나머지 scope 는 계속, failures 격리 기록, 크래시 X."""
    patched_news["_boom_scopes"].add("ticker:000660")
    result = asyncio.run(run_news_ingest(date="2026-06-08"))

    assert any(f["stage"] == "digest:ticker:000660" for f in result["failures"])
    assert result["scopes_failed"] == 1
    # 실패한 1개 빼고 전부 영속
    assert result["scopes_persisted"] == (1 + 2 + _N_SECTORS) - 1
    assert "ticker:000660" not in patched_news["upsert_digest"]
    assert "market" in patched_news["upsert_digest"]


def test_empty_scope_still_persisted_when_toggle_on(patched_news: dict) -> None:
    """persist_empty_scopes=true(기본) → 빈 종목 scope 도 기록 ('미수집' vs 'neutral')."""
    patched_news["_empty_scopes"].add("ticker:000660")
    result = asyncio.run(run_news_ingest(date="2026-06-08"))
    # 빈 scope 도 upsert 됨 → 전부 영속
    assert "ticker:000660" in patched_news["upsert_digest"]
    assert result["scopes_persisted"] == 1 + 2 + _N_SECTORS


def test_universe_fetch_failure_falls_back(
    monkeypatch: pytest.MonkeyPatch, patched_news: dict
) -> None:
    """universe(KIS) 실패 → 종목 scope 없이 market + 섹터만, failures 격리, 크래시 X."""

    async def boom():
        raise RuntimeError("kis down")

    monkeypatch.setattr(ni, "_build_universe_and_name_map", boom)
    result = asyncio.run(run_news_ingest(date="2026-06-08"))

    assert any(f["stage"] == "universe" for f in result["failures"])
    scopes = [(d["ticker"], d["sector"]) for d in patched_news["digest"]]
    assert (None, None) in scopes                       # market 은 진행
    assert not any(t for t, _ in scopes)                # 종목 scope 없음
    assert result["scopes_persisted"] == 1 + _N_SECTORS  # market + 섹터
    # classify 는 빈 map 으로라도 호출됨
    assert patched_news["classify_kwargs"].get("name_code_map") == {}


def test_classify_failure_isolated_digest_still_runs(
    monkeypatch: pytest.MonkeyPatch, patched_news: dict
) -> None:
    """classify 예외 → job 크래시 X. classify 격리 기록 + digest scope 루프 여전히 실행."""

    async def boom(items, **kwargs):
        raise RuntimeError("gemini 503")

    monkeypatch.setattr(ns, "classify_news_items", boom)
    result = asyncio.run(run_news_ingest(date="2026-06-08"))

    assert any(f["stage"] == "classify" for f in result["failures"])
    assert "gemini 503" in result["failures"][0]["error"]
    assert patched_news["upsert"] == [2]                # labeled upsert 스킵
    assert patched_news["digest"]                       # digest 루프 호출됨
    assert result["digest"]["source"] == "computed"


def test_collect_failure_skips_classify(
    monkeypatch: pytest.MonkeyPatch, patched_news: dict
) -> None:
    """수집 실패 → items 비어 classify 미호출. digest scope 루프는 여전히 실행."""

    async def boom(sources):
        raise RuntimeError("rss down")

    monkeypatch.setattr(ns, "collect_from_sources", boom)
    result = asyncio.run(run_news_ingest(date="2026-06-08"))

    assert any(f["stage"] == "collect" for f in result["failures"])
    assert patched_news["classify"] == 0                # 수집 0 → classify 스킵
    assert result["collected"] == 0
    assert patched_news["digest"]                       # digest 는 여전히 호출
