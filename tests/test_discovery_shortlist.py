"""종목 발굴 경로 (Discovery Shortlist) 테스트 — PRODUCTION-UX-001 보강.

종목 미지정 추천 질의에 rank_candidates 결정론 랭킹 셔틀리스트를 stock_picker 에 주입.
순수 render / builder(snapshot·rank mock) / 라우터 트리거 3층 검증.
"""
from __future__ import annotations

import pytest

from collectors.screening import render_screening_shortlist_md


# ============================================================
# render_screening_shortlist_md (순수)
# ============================================================


def _ranked():
    return [
        {"rank": 1, "ticker": "000660", "rs_score": 8.0, "extension_score": 7.5, "screening_score": 7.8},
        {"rank": 2, "ticker": "005930", "rs_score": 6.5, "extension_score": 8.0, "screening_score": 7.0},
        {"rank": 3, "ticker": "035420", "rs_score": 4.5, "extension_score": 9.0, "screening_score": 6.0},
        {"rank": None, "ticker": "999999", "rs_score": None, "extension_score": None,
         "screening_score": None, "reason": "60일 데이터 부족"},
    ]


def test_render_topn_cut_and_names():
    md = render_screening_shortlist_md(
        _ranked(), {"000660": "SK하이닉스", "005930": "삼성전자"},
        top_n=2, track="track_b", regime="moderate_bull",
    )
    assert "SK하이닉스 (000660)" in md
    assert "삼성전자 (005930)" in md
    assert "035420" not in md   # top_n=2 컷
    assert "999999" not in md   # rank None 제외
    assert "단기 트레이딩" in md
    assert "moderate_bull" in md


def test_render_name_fallback_to_ticker():
    md = render_screening_shortlist_md(_ranked(), {}, top_n=1)
    assert "(000660)" in md  # 이름 없으면 ticker 표기


def test_render_empty():
    md = render_screening_shortlist_md([], {}, top_n=5)
    assert "추천 보류" in md or "후보 없음" in md


def test_render_all_unrankable():
    only_excluded = [{"rank": None, "ticker": "999999", "screening_score": None}]
    md = render_screening_shortlist_md(only_excluded, {}, top_n=5)
    assert "추천 보류" in md or "후보 없음" in md


# ============================================================
# build_discovery_shortlist_md (snapshot + rank mock)
# ============================================================


@pytest.mark.asyncio
async def test_build_discovery_shortlist_md(monkeypatch):
    import importlib
    from types import SimpleNamespace

    # core.inference.__init__ 가 run_analyst 함수로 서브모듈을 shadow → importlib 로 실모듈 획득
    ra = importlib.import_module("core.inference.run_analyst")
    sc = importlib.import_module("collectors.screening")

    snap = SimpleNamespace(
        kr_leading={"kospi": [{"ticker": "000660"}, {"ticker": "005930"}], "kosdaq": []},
        market_macro={},  # regime skip
    )

    async def fake_snapshot():
        return snap, False

    def fake_rank(tickers, regime, **kw):
        assert "000660" in tickers
        return [
            {"rank": 1, "ticker": "000660", "rs_score": 8.0, "extension_score": 7.0, "screening_score": 7.5},
            {"rank": 2, "ticker": "005930", "rs_score": 6.0, "extension_score": 8.0, "screening_score": 6.8},
        ]

    monkeypatch.setattr(ra, "build_market_snapshot", fake_snapshot)
    monkeypatch.setattr(sc, "rank_candidates", fake_rank)

    md, meta = await ra.build_discovery_shortlist_md(track="track_b", top_n=5)
    assert md is not None
    assert "000660" in md
    assert meta["discovery_pool_size"] == 2
    assert meta["discovery_top"] == ["000660", "005930"]


@pytest.mark.asyncio
async def test_build_discovery_empty_pool(monkeypatch):
    import importlib
    from types import SimpleNamespace

    ra = importlib.import_module("core.inference.run_analyst")

    snap = SimpleNamespace(kr_leading={}, market_macro={})

    async def fake_snapshot():
        return snap, False

    # DB universe fallback 도 빈 풀로
    monkeypatch.setattr(ra, "build_market_snapshot", fake_snapshot)
    monkeypatch.setattr(
        "core.db.get_db",
        lambda: SimpleNamespace(fetch_all=lambda *a, **k: []),
    )
    md, meta = await ra.build_discovery_shortlist_md()
    assert md is None
    assert meta.get("discovery_error") == "empty_pool"


# ============================================================
# 라우터 트리거 (_build_subtask_prompt / _prefetch)
# ============================================================


def test_subtask_discovery_template_for_stock_picker():
    from core.intent.router import _build_subtask_prompt, reload_subtasks_and_routing

    reload_subtasks_and_routing()
    p = _build_subtask_prompt(
        "stock_picker", ticker=None, ticker_display=None,
        original_input="단타 종목 있어?", scenario_id=5, discovery_md="SHORTLIST_TABLE",
    )
    assert "SHORTLIST_TABLE" in p
    assert "추천 후보" in p

    # ticker 지정(비발굴) → per-ticker 템플릿, 셔틀리스트 미주입
    p2 = _build_subtask_prompt(
        "stock_picker", ticker="005930", ticker_display="삼성전자",
        original_input="삼성 어때", scenario_id=2, discovery_md=None,
    )
    assert "SHORTLIST_TABLE" not in p2
    assert "CAN SLIM" in p2 or "주도주" in p2


@pytest.mark.asyncio
async def test_prefetch_discovery_injects_and_adds_stock_picker(monkeypatch):
    import core.intent.router as rt
    from core.intent.classifier import IntentClassification

    import importlib

    async def fake_disc(*, track="track_b", top_n=5):
        return "TABLE_MD_INJECTED", {"discovery_top": ["000660"]}

    ra_mod = importlib.import_module("core.inference.run_analyst")
    monkeypatch.setattr(ra_mod, "build_discovery_shortlist_md", fake_disc)

    captured: dict[str, str] = {}

    async def fake_call(analyst_id, messages, *, target_ticker, provider):
        captured[analyst_id] = messages[-1]["content"]
        return {"kind": "analyst", "agent_id": analyst_id, "target": target_ticker,
                "text": "ok", "metadata": {}}

    monkeypatch.setattr(rt, "_call_analyst_safe", fake_call)

    cls = IntentClassification(
        scenario_id=5, ticker=None, ticker_display=None, agent_route="track_b",
        analyst_ids=[], confidence=0.9, manual_fallback_required=False,
        stage="llm", latency_ms=0, raw_input="단타 종목 있어?", reasoning="",
    )
    out = await rt._prefetch_analysts_for_tracks(
        ["track_b"], classification=cls,
        messages=[{"role": "user", "content": "단타 종목 있어?"}], provider="mock",
    )
    ids = [o["id"] for o in out]
    assert "stock_picker" in ids
    assert "TABLE_MD_INJECTED" in captured.get("stock_picker", "")


# ============================================================
# formatter discovery 모드 (셔틀리스트 양식)
# ============================================================


def test_is_discovery_helper():
    from types import SimpleNamespace

    from server.api.production_chat import _is_discovery

    assert _is_discovery(SimpleNamespace(ticker=None, agent_route="track_b")) is True
    assert _is_discovery(SimpleNamespace(ticker=None, agent_route="both")) is True
    assert _is_discovery(SimpleNamespace(ticker="005930", agent_route="track_b")) is False
    assert _is_discovery(SimpleNamespace(ticker=None, agent_route="analyst_direct")) is False


@pytest.mark.asyncio
async def test_format_answer_discovery_selects_shortlist_prompt(monkeypatch):
    import core.intent.formatter as fmt_mod

    captured: dict = {}

    async def fake_call_llm(*, system, messages, model, **kw):
        captured["system"] = system
        return {"content": "추천 후보: 삼성전기 …", "model": "gemini-x",
                "tokens_in": 1, "tokens_out": 1, "cost_usd": 0.0}

    monkeypatch.setattr(fmt_mod, "call_llm", fake_call_llm)
    analysts = [{"id": "stock_picker", "text": "추천 후보 3종 …", "metadata": {}}]

    await fmt_mod.format_answer("단타 종목 있어?", analysts, [], provider="gemini", discovery=True)
    sys_disc = " ".join(b["text"] for b in captured["system"])
    assert "종목 추천 답변기" in sys_disc

    captured.clear()
    await fmt_mod.format_answer("삼성 어때", analysts, [], provider="gemini", discovery=False)
    sys_norm = " ".join(b["text"] for b in captured["system"])
    assert "답변 압축기" in sys_norm
