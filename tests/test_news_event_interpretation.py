"""NEWS-EVENT-INTERPRETATION-001 (M1) — 격상 레인 + LLM 해석 + 전달 배선 테스트.

범위:
  M1-a  detect_elevated_events — mag3 단건 / mag2×다중소스 결정론 격상 (D1)
  확장  NewsDigest.elevated_events round-trip + build_news_digest 해석 보존 병합 (D2)
  M1-b  interpret_elevated_event — 4축 해석 (call_llm mock, 캐싱 멱등, D3)
  M1-c  render 최상단 "오늘의 중심 이벤트" 섹션 + run_strategist 파라미터 + 폴백 (D5)

LLM 실호출 없음 — call_llm patch (test_news_source mirror). TESTING=1 강제.
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
    NewsDigest,
    build_news_digest,
    detect_elevated_events,
    get_news_digest,
    render_news_digest_md,
    upsert_news_digest,
    upsert_news_items,
)
from core.db.connection import Database, reset_db


# ---------------------------------------------------------------------------
# Fixtures (test_news_source mirror)
# ---------------------------------------------------------------------------
@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    db = Database(tmp_path / "test_nei.sqlite")
    monkeypatch.setattr(ns, "get_db", lambda: db)
    ns.reload_news_source_config()
    return db


def _labeled(url: str, *, title: str = "t", source: str = "Yahoo",
             magnitude: int = 2, refs: list[str] | None = None,
             category: str = "market_sentiment", direction: str = "down",
             collected_at: str = "2026-07-06T00:00:00+00:00") -> NewsItem:
    """라벨 완료 뉴스 헬퍼 — 격상 레인 입력."""
    return NewsItem(
        title=title, url=url, source=source,
        category=category, time_axis="short_theme", direction=direction,
        magnitude=magnitude, confidence=80,
        affected_scope="sector" if refs else "market",
        affected_refs=refs or [], labeled_by="llm",
        collected_at=collected_at,
    )


# ---------------------------------------------------------------------------
# M1-a — detect_elevated_events (결정론, LLM 0)
# ---------------------------------------------------------------------------
def test_mag3_single_elevates():
    """mag3 단건은 즉시 격상 (D1) — elevated_by=mag3_single."""
    items = [_labeled("http://n/1", magnitude=3, refs=["KODEX 반도체"])]
    events = detect_elevated_events(items, multi_source_n=3)
    assert len(events) == 1
    ev = events[0]
    assert ev["elevated_by"] == "mag3_single"
    assert ev["theme"] == "KODEX 반도체"
    assert ev["max_magnitude"] == 3
    assert ev["urls"] == ["http://n/1"]
    assert ev["event_key"]  # 결정론 키 부여 (lifecycle 기초)


def test_mag2_multi_source_elevates():
    """mag2 라도 서로 다른 출처 N건(기본 3) 동시 보도 → 확산 격상 (메타발 유형)."""
    items = [
        _labeled("http://n/1", source="Yahoo", magnitude=2, refs=["KODEX 반도체"]),
        _labeled("http://n/2", source="CNBC", magnitude=2, refs=["KODEX 반도체"]),
        _labeled("http://n/3", source="GoogleNews", magnitude=2, refs=["KODEX 반도체"]),
    ]
    events = detect_elevated_events(items, multi_source_n=3)
    assert len(events) == 1
    ev = events[0]
    assert ev["elevated_by"] == "mag2_multi_source"
    assert ev["source_count"] == 3


def test_mag2_same_source_not_elevated():
    """같은 출처 반복 보도는 확산 아님 — 격상 안 함."""
    items = [
        _labeled(f"http://n/{i}", source="Yahoo", magnitude=2, refs=["KODEX 반도체"])
        for i in range(4)
    ]
    assert detect_elevated_events(items, multi_source_n=3) == []


def test_mag1_and_unlabeled_never_elevate():
    """mag1·미라벨링은 격상 대상 아님."""
    items = [
        _labeled("http://n/1", magnitude=1, refs=["KODEX 반도체"]),
        NewsItem(title="미분류", url="http://n/2", source="Yahoo"),
    ]
    assert detect_elevated_events(items, multi_source_n=3) == []


def test_empty_input_no_events():
    assert detect_elevated_events([], multi_source_n=3) == []


def test_mag3_within_cluster_dedup_single_event():
    """mag3 + 같은 클러스터 mag2 다수 → 이벤트 1건 (mag3_single 우선, 중복 없음)."""
    items = [
        _labeled("http://n/1", source="Yahoo", magnitude=3, refs=["KODEX 반도체"]),
        _labeled("http://n/2", source="CNBC", magnitude=2, refs=["KODEX 반도체"]),
        _labeled("http://n/3", source="GoogleNews", magnitude=2, refs=["KODEX 반도체"]),
    ]
    events = detect_elevated_events(items, multi_source_n=3)
    assert len(events) == 1
    assert events[0]["elevated_by"] == "mag3_single"
    assert events[0]["source_count"] == 3
    assert len(events[0]["urls"]) == 3


def test_deterministic_ordering():
    """복수 이벤트 = max_magnitude desc → source_count desc → key (백테스트 재현)."""
    items = [
        _labeled("http://a/1", source="Yahoo", magnitude=3, refs=["A테마"]),
        _labeled("http://b/1", source="Yahoo", magnitude=2, refs=["B테마"]),
        _labeled("http://b/2", source="CNBC", magnitude=2, refs=["B테마"]),
        _labeled("http://b/3", source="GoogleNews", magnitude=2, refs=["B테마"]),
    ]
    events = detect_elevated_events(items, multi_source_n=3)
    assert [e["theme"] for e in events] == ["A테마", "B테마"]


# ---------------------------------------------------------------------------
# 확장 — NewsDigest.elevated_events round-trip (D2: 컬럼 확장, 신규 테이블 0)
# ---------------------------------------------------------------------------
def test_digest_elevated_events_round_trip(isolated_db):
    ev = {
        "event_key": "kodex-반도체",
        "theme": "KODEX 반도체",
        "elevated_by": "mag2_multi_source",
        "source_count": 3,
        "max_magnitude": 2,
        "trigger_titles": ["메타 AI capex 논란"],
        "urls": ["http://n/1"],
        "interpretation": {"nature": "transient_fear"},
    }
    digest = NewsDigest(date="2026-07-06", scope="market", tone="lean_bearish",
                        elevated_events=[ev], source="computed")
    upsert_news_digest(digest)
    back = get_news_digest("market", "2026-07-06")
    assert back is not None
    assert back.elevated_events == [ev]


def test_digest_without_elevated_events_backward_compat(isolated_db):
    """elevated_events 미지정 기존 경로 — 빈 배열로 round-trip (하위 호환)."""
    upsert_news_digest(NewsDigest(date="2026-07-06", scope="market", source="computed"))
    back = get_news_digest("market", "2026-07-06")
    assert back is not None
    assert back.elevated_events == []


def test_build_news_digest_detects_and_persists_elevated(isolated_db):
    """build_news_digest(market) 가 격상 후보를 결정론 산출·영속 (해석은 None)."""
    items = [
        _labeled("http://n/1", source="Yahoo", magnitude=2, refs=["KODEX 반도체"]),
        _labeled("http://n/2", source="CNBC", magnitude=2, refs=["KODEX 반도체"]),
        _labeled("http://n/3", source="GoogleNews", magnitude=2, refs=["KODEX 반도체"]),
    ]
    upsert_news_items(items)
    digest = build_news_digest("2026-07-06")
    assert len(digest.elevated_events) == 1
    assert digest.elevated_events[0]["interpretation"] is None
    back = get_news_digest("market", "2026-07-06")
    assert back.elevated_events[0]["theme"] == "KODEX 반도체"


def test_build_news_digest_preserves_existing_interpretation(isolated_db):
    """재계산(멱등 upsert) 시 기존 해석 보존 — 같은 event_key 병합 (덮어쓰기 사고 방지)."""
    items = [
        _labeled("http://n/1", source="Yahoo", magnitude=3, refs=["KODEX 반도체"]),
    ]
    upsert_news_items(items)
    first = build_news_digest("2026-07-06")
    key = first.elevated_events[0]["event_key"]
    # 해석 attach 시뮬레이션 (ingest 5.5단계가 하는 일)
    first.elevated_events[0]["interpretation"] = {"nature": "transient_fear"}
    upsert_news_digest(first)
    # 소비자가 on-demand 재계산해도 해석이 살아있어야 함
    recomputed = build_news_digest("2026-07-06")
    assert recomputed.elevated_events[0]["event_key"] == key
    assert recomputed.elevated_events[0]["interpretation"] == {"nature": "transient_fear"}


def test_build_news_digest_ticker_scope_no_elevation(isolated_db):
    """격상 레인은 market scope 전용 — 종목 scope 는 빈 배열 (중심 이벤트=시장 단위)."""
    items = [_labeled("http://n/1", magnitude=3, refs=["005930"])]
    upsert_news_items(items)
    digest = build_news_digest("2026-07-06", ticker="005930")
    assert digest.elevated_events == []


# ---------------------------------------------------------------------------
# M1-b — interpret_elevated_events (LLM 해석 4축, call_llm mock)
# ---------------------------------------------------------------------------
from collectors.news_source import interpret_elevated_events  # noqa: E402


def _event(key: str = "kodex-반도체", **kw) -> dict:
    ev = {
        "event_key": key,
        "theme": "KODEX 반도체",
        "elevated_by": "mag2_multi_source",
        "source_count": 3,
        "max_magnitude": 2,
        "trigger_titles": ["메타 AI capex 논란", "AI 버블 우려"],
        "urls": ["http://n/1", "http://n/2", "http://n/3"],
        "interpretation": None,
    }
    ev.update(kw)
    return ev


_VALID_INTERP = {
    "nature": "transient_fear",
    "axes": {
        "novelty": {"verdict": "재탕", "reason": "연초 예고된 capex 확대의 재탕"},
        "fundamental_alignment": {"verdict": "괴리", "reason": "마이크론 호가이던스 vs 셀오프"},
        "noise_rotation": {"verdict": "의심", "reason": "매일 다른 악재 순환"},
        "market_reaction_alignment": {"verdict": "빌미 우세", "reason": "과열 이격 해소 자리"},
    },
    "impact_path": ["반도체"],
    "trade_implication": "주도주 눌림목 대기, 신규 추격 관망",
    "reassess_condition": "빅테크 실적에서 capex 가이던스 실제 하향 시",
    "confidence": 70,
}


def _llm_resp(payload: dict) -> dict:
    return {
        "content": json.dumps(payload, ensure_ascii=False),
        "model": "gemini-2.5-flash",
        "tokens_in": 100,
        "tokens_out": 200,
        "cost_usd": 0.0007,
    }


async def test_interpret_attaches_four_axes(isolated_db):
    """유효 응답 → interpretation attach (nature + 4축 + 매매함의 + 재평가조건)."""
    events = [_event()]
    with patch.object(ns, "call_llm", return_value=_llm_resp(_VALID_INTERP)) as m:
        out = await interpret_elevated_events(events, date="2026-07-06")
    interp = out[0]["interpretation"]
    assert interp["nature"] == "transient_fear"
    assert set(interp["axes"].keys()) == {
        "novelty", "fundamental_alignment", "noise_rotation", "market_reaction_alignment",
    }
    assert interp["trade_implication"]
    assert interp["reassess_condition"]
    # 원장 질의영역 라벨 + thinking_budget=0 (JSON 잘림 방지)
    kwargs = m.call_args.kwargs
    assert kwargs["call_type"] == "news_interpretation"
    assert kwargs["thinking_budget"] == 0


async def test_interpret_skips_already_interpreted(isolated_db):
    """이미 해석 있는 이벤트는 LLM 재호출 없음 (멱등)."""
    events = [_event(interpretation={"nature": "unresolved"})]
    with patch.object(ns, "call_llm", return_value=_llm_resp(_VALID_INTERP)) as m:
        out = await interpret_elevated_events(events, date="2026-07-06")
    assert m.call_count == 0
    assert out[0]["interpretation"] == {"nature": "unresolved"}


async def test_interpret_cache_hit_second_run(isolated_db):
    """같은 (event_key×기사집합×일자) 재실행 → LLM 콜 1회 (llm_call_cache 멱등)."""
    with patch.object(ns, "call_llm", return_value=_llm_resp(_VALID_INTERP)) as m:
        await interpret_elevated_events([_event()], date="2026-07-06")
        out2 = await interpret_elevated_events([_event()], date="2026-07-06")
    assert m.call_count == 1
    assert out2[0]["interpretation"]["nature"] == "transient_fear"


async def test_interpret_invalid_response_graceful(isolated_db):
    """유효성 실패(nature 불량) → interpretation None 유지, 크래시 없음."""
    bad = dict(_VALID_INTERP, nature="panic!!")
    with patch.object(ns, "call_llm", return_value=_llm_resp(bad)):
        out = await interpret_elevated_events([_event()], date="2026-07-06")
    assert out[0]["interpretation"] is None


async def test_interpret_llm_error_graceful(isolated_db):
    """LLM 예외 → 해당 이벤트만 None, 나머지 진행 (graceful)."""
    async def boom(**kwargs):
        raise RuntimeError("503")
    with patch.object(ns, "call_llm", side_effect=boom):
        out = await interpret_elevated_events([_event()], date="2026-07-06")
    assert out[0]["interpretation"] is None


async def test_interpret_max_events_cap(isolated_db, monkeypatch):
    """비용 상한 — max_events_per_day 초과분은 해석 없이 통과 (격상 폭주 방어)."""
    monkeypatch.setitem(
        ns.load_news_source_config(), "interpretation", {"max_events_per_day": 2}
    )
    events = [_event(key=f"ev-{i}") for i in range(4)]
    with patch.object(ns, "call_llm", return_value=_llm_resp(_VALID_INTERP)) as m:
        out = await interpret_elevated_events(events, date="2026-07-06")
    assert m.call_count == 2
    assert out[0]["interpretation"] is not None
    assert out[2]["interpretation"] is None


async def test_interpret_prompt_includes_market_context(isolated_db):
    """시장 실반응·파동 컨텍스트(4축 재료)가 프롬프트에 주입됨 (사용자 통찰)."""
    ctx = "나스닥 -3.0% | SOX -9.2% | VIX 22 | KOSPI 이격 +8% 과열"
    with patch.object(ns, "call_llm", return_value=_llm_resp(_VALID_INTERP)) as m:
        await interpret_elevated_events(
            [_event()], date="2026-07-06", market_context_md=ctx
        )
    prompt = m.call_args.kwargs["messages"][0]["content"]
    assert "SOX -9.2%" in prompt
    assert "novelty" in prompt  # 4축 질문지 명시


# ---------------------------------------------------------------------------
# M1-b′ — ingest 5.5단계 합류 + 장전 06:40 cron (D5)
# ---------------------------------------------------------------------------
from server.schedulers.jobs import news_ingest as ni  # noqa: E402
from server.schedulers.jobs.news_ingest import run_news_ingest  # noqa: E402


class _FakeDigest:
    def __init__(self, scope: str, elevated: list[dict] | None = None):
        self.scope = scope
        self.tone = "lean_bearish"
        self.source = "computed"
        self.top_themes = [{"theme": "반도체"}]
        self.elevated_events = elevated or []


@pytest.fixture
def patched_ingest(monkeypatch: pytest.MonkeyPatch) -> dict:
    """run_news_ingest 외부 호출 전부 mock — 5.5단계(해석) 흐름 검증용."""
    calls: dict = {"interpret": [], "upsert_digest": [], "elevated": []}

    async def fake_collect(sources):
        return []

    async def fake_universe():
        return [], {}

    async def fake_backfill(**kwargs):
        return {"candidates": 0, "labeled": 0}

    def fake_digest(date, *, ticker=None, sector=None, persist=True):
        scope = f"ticker:{ticker}" if ticker else (f"sector:{sector}" if sector else "market")
        return _FakeDigest(scope, elevated=list(calls["elevated"]) if scope == "market" else [])

    def fake_upsert_digest(digest):
        calls["upsert_digest"].append(digest.scope)

    async def fake_interpret(events, **kwargs):
        calls["interpret"].append({"n": len(events), **kwargs})
        for e in events:
            if e.get("interpretation") is None:
                e["interpretation"] = {"nature": "transient_fear"}
        return events

    monkeypatch.setattr(ns, "collect_from_sources", fake_collect)
    monkeypatch.setattr(ns, "upsert_news_items", lambda items: len(items))
    monkeypatch.setattr(ns, "backfill_unlabeled_news", fake_backfill)
    monkeypatch.setattr(ns, "build_news_digest", fake_digest)
    monkeypatch.setattr(ns, "upsert_news_digest", fake_upsert_digest)
    monkeypatch.setattr(ns, "interpret_elevated_events", fake_interpret)
    monkeypatch.setattr(ni, "_build_universe_and_name_map", fake_universe)
    monkeypatch.setattr(ni, "_interpretation_market_context", lambda date: "KOSPI -2% | SOX -9%")
    monkeypatch.setattr(ns, "RssNewsSource", lambda *a, **k: object())
    return calls


async def test_ingest_interprets_market_elevated_events(patched_ingest):
    """5.5단계 — market 격상 이벤트가 해석되고 digest 재영속 + 결과 dict 노출."""
    patched_ingest["elevated"].append(_event())
    result = await run_news_ingest(date="2026-07-06")
    assert len(patched_ingest["interpret"]) == 1
    call = patched_ingest["interpret"][0]
    assert call["date"] == "2026-07-06"
    assert "SOX -9%" in call["market_context_md"]  # 시장 실반응 컨텍스트 주입
    # market digest 는 step5(1회) + 해석 attach 후(1회) = 2회 영속
    assert patched_ingest["upsert_digest"].count("market") == 2
    assert result["digest"]["elevated"] == 1
    assert result["digest"]["interpreted"] == 1


async def test_ingest_no_elevated_no_interpret_call(patched_ingest):
    """격상 0건 날 — 해석 스테이지 자체가 안 돎 (LLM 콜 0, 비용 0)."""
    result = await run_news_ingest(date="2026-07-06")
    assert patched_ingest["interpret"] == []
    assert result["digest"]["elevated"] == 0
    assert patched_ingest["upsert_digest"].count("market") == 1


def test_premarket_news_cron_registered():
    """장전 06:40 ingest cron 등록 (D5) — misfire 내성 포함 (절전 사고 보강 패턴)."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from server.schedulers.jobs import register_infra_jobs
    from server.schedulers.jobs.auto_signal import MISFIRE_GRACE_SEC

    sched = AsyncIOScheduler(timezone="Asia/Seoul")
    register_infra_jobs(sched)
    job = sched.get_job("news_ingest::premarket")
    assert job is not None, "장전 뉴스 ingest 미등록"
    assert job.misfire_grace_time == MISFIRE_GRACE_SEC
    assert job.coalesce is True
    assert job.max_instances == 1


# ---------------------------------------------------------------------------
# M1-c — 전달 배선: render 최상단 섹션 / lookback 폴백 / run_strategist / auto_signal
# ---------------------------------------------------------------------------
from collectors.news_source import render_market_news_digest_md  # noqa: E402


def test_render_elevated_section_on_top_with_interpretation():
    """격상 이벤트+해석이 md 최상단 섹션으로 — 4축·매매함의·재평가조건 노출."""
    digest = NewsDigest(
        date="2026-07-06", scope="market", tone="lean_bearish",
        category_counts={"market_sentiment": {"up": 0, "neutral": 1, "down": 4}},
        elevated_events=[_event(interpretation=_VALID_INTERP)],
        source="computed",
    )
    md = render_news_digest_md(digest)
    assert "오늘의 중심 이벤트" in md
    # 중심 이벤트 섹션이 카테고리 표보다 위 (최상단 배치)
    assert md.index("오늘의 중심 이벤트") < md.index("카테고리별 방향 카운트")
    assert "단기 공포" in md          # nature 한국어
    assert "주도주 눌림목 대기" in md   # trade_implication
    assert "재평가" in md              # reassess_condition 라벨
    assert "advisory" in md            # M1 경계 명시 (게이트 아님)


def test_render_elevated_without_interpretation_graceful():
    """해석 전(None) 이벤트 — 격상 사실만 노출 + 해석 대기 표기."""
    digest = NewsDigest(
        date="2026-07-06", scope="market", tone="neutral",
        elevated_events=[_event()], source="computed",
    )
    md = render_news_digest_md(digest)
    assert "오늘의 중심 이벤트" in md
    assert "해석 대기" in md


def test_render_market_news_digest_md_lookback_fallback(isolated_db):
    """오늘 digest 부재 → 직전 일자 폴백 + 시점 표기 (D5 stale 침묵 금지)."""
    upsert_news_digest(NewsDigest(
        date="2026-07-05", scope="market", tone="lean_bearish",
        elevated_events=[_event(interpretation=_VALID_INTERP)], source="computed",
    ))
    md = render_market_news_digest_md("2026-07-06")
    assert md is not None
    assert "1일 전" in md and "2026-07-05" in md
    assert "오늘의 중심 이벤트" in md


def test_render_market_news_digest_md_none_when_no_rows(isolated_db):
    """lookback 내 digest 전무 → None (graceful — 주입 생략)."""
    assert render_market_news_digest_md("2026-07-06") is None


async def test_run_strategist_accepts_news_digest_md(monkeypatch):
    """run_strategist(news_digest_md=) → compose [3c] 슬롯 도달 (전략가 도달 첫 경로)."""
    import importlib

    rs = importlib.import_module("core.strategist.run_strategist")

    captured: dict = {}

    async def fake_build_pipeline_prompt(**kwargs):
        captured.update(kwargs)
        from core.knowledge.compose import SystemPromptBundle
        return SystemPromptBundle(blocks=[{"type": "text", "text": "sys"}], cache_breakpoint_count=0)

    async def fake_call_llm(**kwargs):
        return {"content": "verdict: wait", "model": "mock", "tokens_in": 1, "tokens_out": 1}

    async def fake_snapshot():
        return (
            SimpleNamespace(fetched_at=0, failures=[], source_map={}, db_run_ids={}),
            True,
        )

    monkeypatch.setattr(rs, "build_pipeline_prompt", fake_build_pipeline_prompt)
    monkeypatch.setattr(rs, "call_llm", fake_call_llm)
    monkeypatch.setattr(rs, "build_market_snapshot", fake_snapshot)
    monkeypatch.setattr(rs, "render_snapshot_md", lambda s: "snap")

    await rs.run_strategist(
        "track_a", [{"role": "user", "content": "005930"}],
        prefetched_analyst_outputs=[],
        news_digest_md="## [8] 뉴스 종합\n### ⚡ 오늘의 중심 이벤트\n메타발",
    )
    assert "오늘의 중심 이벤트" in (captured.get("news_digest_md") or "")


async def test_auto_signal_injects_news_digest_md(monkeypatch):
    """자동 권고 경로 — 뉴스 digest md 가 전략가 runner 에 전달됨 (M1-c 소비처)."""
    from tests.test_auto_signal import _REC_WAIT, _sample_scorecard  # 기존 픽스처 재사용
    from core.signal import auto_signal as asig
    from core.signal.auto_signal import run_signal_for_ticker

    monkeypatch.setattr(asig, "persist_recommendation", lambda rec: True)
    monkeypatch.setattr(
        asig, "_market_news_digest_md", lambda as_of: "## 뉴스 종합\n중심 이벤트: 메타발"
    )
    seen: dict = {}

    async def _runner(track_id, messages, **kw):
        seen["news_digest_md"] = kw.get("news_digest_md")
        return SimpleNamespace(text=_REC_WAIT)

    r = await run_signal_for_ticker(
        ticker="005930", track="A", snapshot=None, cadence="postclose",
        as_of="2026-07-06", scorecard=_sample_scorecard(),
        strategist_runner=_runner, band_gate=False, notify_signals=False,
    )
    assert r["persisted"] is True
    assert "메타발" in (seen["news_digest_md"] or "")


from types import SimpleNamespace  # noqa: E402
