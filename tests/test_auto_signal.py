"""AUTO-SIGNAL-GENERATION-001 — 자동 권고 생성 테스트.

M1 (funnel Stage 0, LLM 0): watchlist 합집합(universe ∪ 보유 ∪ 관심, 국장) +
결정론 스크리닝 컷(rank_candidates → screening_score 임계·상한).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.db.connection import Database, reset_db
from core.signal import auto_signal as asig
from core.signal import watchlist as wl
from core.signal.auto_signal import (
    Scorecard,
    _market_state_md,
    _signal_directive,
    build_prefetched_entries,
    run_signal_cadence,
    run_signal_for_ticker,
)


@pytest.fixture(autouse=True)
def captured_notify(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """모든 테스트에서 notify 를 캡처 stub 으로 치환 — 실 텔레그램/파일/DB 차단.

    M4 알림 테스트는 이 리스트로 발송 내역 검증. 그 외 테스트는 side-effect 차단용.
    """
    sent: list[dict] = []

    async def _fake(**kw):
        sent.append(kw)
        return {"channel": "test"}

    monkeypatch.setattr(asig, "notify", _fake)
    return sent


# ---------------------------------------------------------------------------
# is_kr_ticker / _kr_only — 순수 (국장 = 6자리 숫자)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ticker,expected",
    [
        ("005930", True),    # 삼성전자
        ("000660", True),    # SK하이닉스
        ("AAPL", False),     # 미장
        ("00593", False),    # 5자리
        ("0059300", False),  # 7자리
        ("", False),
        ("12a456", False),   # 숫자 아님
    ],
)
def test_is_kr_ticker(ticker, expected):
    assert wl.is_kr_ticker(ticker) is expected


def test_kr_only_filters_non_kr():
    assert wl._kr_only(["005930", "AAPL", "000660", "TSLA"]) == ["005930", "000660"]


# ---------------------------------------------------------------------------
# build_watchlist — 합집합 (소스 주입)
# ---------------------------------------------------------------------------


async def test_build_watchlist_unions_and_dedups():
    out = await wl.build_watchlist(
        universe_tickers=["005930", "000660"],
        held_tickers=["000660", "005380"],   # 000660 중복
        watch_tickers=["005930", "035720"],  # 005930 중복
    )
    # dedup + 순서 보존 (universe → held → watch)
    assert out == ["005930", "000660", "005380", "035720"]


async def test_build_watchlist_kr_only_filters_us():
    out = await wl.build_watchlist(
        universe_tickers=["005930", "AAPL"],
        held_tickers=["TSLA"],
        watch_tickers=["000660"],
    )
    assert out == ["005930", "000660"]


async def test_build_watchlist_kr_only_false_keeps_all():
    out = await wl.build_watchlist(
        universe_tickers=["005930", "AAPL"],
        held_tickers=[],
        watch_tickers=[],
        kr_only=False,
    )
    assert out == ["005930", "AAPL"]


async def test_build_watchlist_universe_fetch_failure_is_graceful():
    async def _boom(_kis):
        raise RuntimeError("KIS down")

    out = await wl.build_watchlist(
        held_tickers=["005930"],
        watch_tickers=["000660"],
        universe_fetcher=_boom,
    )
    # universe 실패해도 보유·관심은 살아남음
    assert out == ["005930", "000660"]


async def test_build_watchlist_uses_injected_universe_fetcher():
    async def _fetcher(_kis):
        return ["005930", "000660"]

    out = await wl.build_watchlist(
        held_tickers=[], watch_tickers=[], universe_fetcher=_fetcher,
    )
    assert out == ["005930", "000660"]


# ---------------------------------------------------------------------------
# load_held_tickers / load_watch_tickers — DB read
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    db = Database(tmp_path / "test_signal.sqlite")
    monkeypatch.setattr(wl, "get_db", lambda: db)
    return db


def test_load_held_tickers_distinct_positive_shares(isolated_db):
    isolated_db.executemany(
        "INSERT INTO account_positions (account_id, ticker, shares) VALUES (?, ?, ?)",
        [
            ("kr_long", "005930", 100.0),
            ("kr_swing", "005930", 50.0),   # 같은 종목 다른 계좌 → distinct 로 1개
            ("kr_long", "000660", 30.0),
            ("kr_long", "005380", 0.0),     # shares 0 → 제외
        ],
    )
    assert sorted(wl.load_held_tickers()) == ["000660", "005930"]


def test_load_held_tickers_empty(isolated_db):
    assert wl.load_held_tickers() == []


def test_load_watch_tickers_watching_and_holding_only(isolated_db):
    isolated_db.executemany(
        "INSERT INTO watch_positions (ticker, status) VALUES (?, ?)",
        [
            ("005930", "watching"),
            ("000660", "holding"),
            ("035720", "closed"),   # 제외
        ],
    )
    assert sorted(wl.load_watch_tickers()) == ["000660", "005930"]


async def test_build_watchlist_reads_db_when_sources_not_injected(isolated_db):
    isolated_db.execute(
        "INSERT INTO account_positions (account_id, ticker, shares) VALUES (?, ?, ?)",
        ("kr_long", "005380", 10.0),
    )
    isolated_db.execute(
        "INSERT INTO watch_positions (ticker, status) VALUES (?, ?)",
        ("035720", "watching"),
    )
    out = await wl.build_watchlist(universe_tickers=["005930"])
    assert out == ["005930", "005380", "035720"]


# ---------------------------------------------------------------------------
# screen_watchlist — 결정론 컷 (ranker 주입)
# ---------------------------------------------------------------------------


def _fake_ranker(rows):
    """주어진 dict 리스트를 그대로 돌려주는 ranker stub."""
    def _r(tickers, regime, *, cutoff_date=None):
        return rows
    return _r


def test_screen_watchlist_applies_min_score_cut():
    rows = [
        {"ticker": "005930", "screening_score": 7.5},
        {"ticker": "000660", "screening_score": 4.0},   # 컷 미달
        {"ticker": "005380", "screening_score": 5.0},   # 경계 = 통과
    ]
    out = wl.screen_watchlist(
        ["005930", "000660", "005380"], "strong_bull",
        min_score=5.0, max_candidates=0, ranker=_fake_ranker(rows),
    )
    assert [r["ticker"] for r in out] == ["005930", "005380"]


def test_screen_watchlist_sorts_desc_and_caps():
    rows = [
        {"ticker": "A", "screening_score": 6.0},
        {"ticker": "B", "screening_score": 9.0},
        {"ticker": "C", "screening_score": 7.0},
    ]
    out = wl.screen_watchlist(
        ["A", "B", "C"], None, min_score=5.0, max_candidates=2,
        ranker=_fake_ranker(rows),
    )
    # 내림차순 정렬 + 상한 2
    assert [r["ticker"] for r in out] == ["B", "C"]


def test_screen_watchlist_excludes_none_score():
    rows = [
        {"ticker": "005930", "screening_score": 8.0},
        {"ticker": "000660", "screening_score": None},  # 60일 데이터 부족 → 제외
    ]
    out = wl.screen_watchlist(
        ["005930", "000660"], "sideways", min_score=5.0, max_candidates=0,
        ranker=_fake_ranker(rows),
    )
    assert [r["ticker"] for r in out] == ["005930"]


def test_screen_watchlist_empty_input_returns_empty():
    assert wl.screen_watchlist([], "strong_bull") == []


def test_screen_watchlist_tie_break_stable_by_ticker():
    rows = [
        {"ticker": "000660", "screening_score": 7.0},
        {"ticker": "005930", "screening_score": 7.0},
    ]
    out = wl.screen_watchlist(
        ["000660", "005930"], None, min_score=5.0, max_candidates=0,
        ranker=_fake_ranker(rows),
    )
    # 동점 → ticker 안정 정렬
    assert [r["ticker"] for r in out] == ["000660", "005930"]


def test_screen_watchlist_uses_config_defaults_when_unspecified(monkeypatch):
    # min_score/max_candidates 미지정 시 config 로더 호출 확인
    monkeypatch.setattr(wl, "get_signal_min_score", lambda: 6.0)
    monkeypatch.setattr(wl, "get_signal_max_candidates", lambda: 1)
    rows = [
        {"ticker": "A", "screening_score": 9.0},
        {"ticker": "B", "screening_score": 6.5},
        {"ticker": "C", "screening_score": 5.5},  # 6.0 미달
    ]
    out = wl.screen_watchlist(["A", "B", "C"], None, ranker=_fake_ranker(rows))
    assert [r["ticker"] for r in out] == ["A"]  # 컷 6.0 통과 2개 중 상한 1


# ===========================================================================
# M2 — funnel Stage 1 (전략가 직접 호출, 분석가 우회)
# ===========================================================================

# 전략가 stub 응답 — strategist-recommendation-v1 YAML (parse_recommendation 수용).
_REC_WAIT = """결론: 관망.

```yaml
recommendation_id: REC-LLM-005930-A
date: "2026-06-15"
ticker: "005930"
display_name: 삼성전자
track: A
verdict: wait
confidence: 35
reasons:
  - "테스트 관망 사유"
cited_scores:
  s_score: 7.0
  buy_score: 6.5
```
"""

_REC_BUY_B = """결론: 매수.

```yaml
recommendation_id: REC-LLM-005930-B
date: "2026-06-15"
ticker: "005930"
display_name: 삼성전자
track: B
verdict: buy
entry_price: 70000
target_price_1: 77000
stop_loss: 66000
confidence: 62
reasons:
  - "테스트 매수 사유"
cited_scores:
  t_score: 7.5
  buy_score: 7.0
```
"""


def _stub_runner(text):
    async def _run(track_id, messages, **kw):
        return SimpleNamespace(text=text)
    return _run


# ---------------------------------------------------------------------------
# build_prefetched_entries — 결정론 점수표 → 전략가 entries (분석가 우회)
# ---------------------------------------------------------------------------


def _sample_scorecard():
    return Scorecard(
        ticker="005930", display_name="삼성전자", market="KOSPI", regime="strong_bull",
        s_score=7.0, t_score=6.0, f_score=5.5, buy_score=6.5, distribution_day_count=2,
        md={
            "stock_picker_s": "## S md", "stock_picker_buy": "## buy md",
            "trader": "## T md", "flow_analyzer": "## F md",
        },
    )


def _score_ids(entries):
    """점수 보유 entry (bypass note 아님)."""
    return {e["id"] for e in entries if not e.get("metadata", {}).get("batch_bypassed")}


def test_build_entries_track_a_has_picker_flow_market_state_not_trader():
    entries = build_prefetched_entries(_sample_scorecard(), "A")
    assert _score_ids(entries) == {"stock_picker", "flow_analyzer", "market_state_analyzer"}


def test_build_entries_track_b_includes_trader():
    entries = build_prefetched_entries(_sample_scorecard(), "B")
    assert _score_ids(entries) == {"stock_picker", "trader", "flow_analyzer", "market_state_analyzer"}


def test_build_entries_injects_bypass_notes_for_omitted_analysts():
    # 배치 우회 분석가는 "누락" 아니라 "의도적 우회" entry 로 주입 → LLM 이 미발행으로 안 셈
    # (2026-06-15 라이브: persona text 로는 못 막아 구조로 해결).
    entries = {e["id"]: e for e in build_prefetched_entries(_sample_scorecard(), "A")}
    for aid in ("stock_analyst", "wealth_strategist", "principle_guardian"):
        assert aid in entries
        assert entries[aid]["metadata"].get("batch_bypassed") is True
        assert entries[aid]["error"] is None          # 호출 실패 아님
        assert "우회" in entries[aid]["text"]


def test_build_entries_inject_advisory_scores_in_metadata():
    entries = {e["id"]: e for e in build_prefetched_entries(_sample_scorecard(), "B")}
    assert entries["stock_picker"]["metadata"]["advisory_s_score"] == 7.0
    assert entries["stock_picker"]["metadata"]["advisory_buy_score"] == 6.5
    assert entries["trader"]["metadata"]["advisory_t_score"] == 6.0
    assert entries["flow_analyzer"]["metadata"]["advisory_f_score"] == 5.5
    # 모든 entry 는 error 없음 (배치 = 결정론, 호출 실패 아님)
    assert all(e["error"] is None for e in entries.values())


def test_market_state_md_reports_signals_and_defers_danger_judgment():
    # 위험 판정(≥N kill)을 여기서 재적용하지 않고 AlphaPosture danger_gate 에 위임.
    sc = Scorecard(ticker="005930", regime="parabolic", distribution_day_count=5,
                   index_change_pct=-3.1, breadth_ratio=0.18)
    md = _market_state_md(sc)
    assert "parabolic" in md
    assert "5" in md                       # DD 값은 보고
    assert "-3.1" in md                    # 당일 급락률 노출
    assert "kill-switch 임계(≥4)" not in md  # stale 하드코딩 제거
    assert "위험 게이트" in md              # 판정은 후보 게이트가 소유


def test_signal_directive_mentions_ticker_track_cadence_and_wait():
    d = _signal_directive(_sample_scorecard(), "A", "intraday1")
    assert "005930" in d and "중장기" in d and "intraday1" in d and "wait" in d


# ---------------------------------------------------------------------------
# 차등 변조 배선 (BRAIN-ALPHA-FLEXIBILITY-001 M3a) — AlphaPosture 후보 주입·영속
# ---------------------------------------------------------------------------


def test_posture_inputs_from_scorecard_maps_fields():
    sc = _sample_scorecard()
    sc.rs_score = 8.0
    sc.extension_score = 7.0
    inp = asig.posture_inputs_from_scorecard(sc, "A")
    assert inp.track == "A"
    assert inp.regime == "strong_bull"
    assert inp.s_score == 7.0
    assert inp.buy_score == 6.5
    assert inp.rs_score == 8.0
    assert inp.extension_score == 7.0
    # sector_rs·wave 는 이번 마일스톤 미배선 → None (graceful)
    assert inp.sector_rs_score is None
    assert inp.wave_alive is None


async def test_run_signal_for_ticker_injects_posture_md_and_persists_alpha_posture(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        asig, "persist_recommendation",
        lambda rec: (captured.__setitem__("rec", rec), True)[1],
    )
    seen: dict = {}

    async def _runner(track_id, messages, **kw):
        seen["alpha_posture_md"] = kw.get("alpha_posture_md")
        return SimpleNamespace(text=_REC_WAIT)

    r = await run_signal_for_ticker(
        ticker="005930", track="A", snapshot=None, cadence="postclose",
        as_of="2026-06-15", scorecard=_sample_scorecard(),
        strategist_runner=_runner, band_gate=False,
    )
    assert r["persisted"] is True
    # 결정론 후보 md 가 전략가에 주입됨
    assert seen["alpha_posture_md"] and "결정론 차등 변조 후보" in seen["alpha_posture_md"]
    # 권고 data_json 에 결정론 후보 영속(설명가능성 — LLM verdict 와 무관하게 항상)
    ap = captured["rec"].data["alpha_posture"]
    assert ap["verdict_candidate"] in {"buy", "wait", "sell"}
    assert "regime_class" in ap and "selection_reason" in ap


# TRADE-PLAN-LIFECYCLE-001 B-MS1 — 결정론 가격대 메뉴 주입 + 영속 + 절대 가드레일
_REC_BUY_CLAMP = """매수.
```yaml
recommendation_id: REC-X
date: 2026-06-16
ticker: "005930"
track: A
verdict: "buy"
entry_price: 10000
target_price_1: 12000
stop_loss: 9000
contract_version: "1.0"
```
"""


def _synthetic_ohlcv():
    import pandas as pd

    idx = pd.date_range("2024-01-01", periods=300, freq="B")
    base = [10_000 + i * 2 + (250 if i % 20 < 10 else -250) for i in range(300)]
    close = pd.Series(base, index=idx, dtype=float)
    return pd.DataFrame({
        "open": close, "high": close + 120, "low": close - 120,
        "close": close, "volume": pd.Series([1_000_000.0] * 300, index=idx),
    })


async def test_run_signal_injects_trade_plan_menu_and_clamps_oneill(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        asig, "persist_recommendation",
        lambda rec: (captured.__setitem__("rec", rec), True)[1],
    )
    monkeypatch.setattr(
        "collectors.charts.load_ohlcv_from_db", lambda *a, **k: _synthetic_ohlcv()
    )
    seen: dict = {}

    async def _runner(track_id, messages, **kw):
        seen["tp_md"] = kw.get("trade_plan_menu_md")
        return SimpleNamespace(text=_REC_BUY_CLAMP)

    r = await run_signal_for_ticker(
        ticker="005930", track="A", snapshot=None, cadence="postclose",
        as_of="2026-06-16", scorecard=_sample_scorecard(),
        strategist_runner=_runner, band_gate=False, notify_signals=False,
    )
    assert r["persisted"] is True
    # 결정론 가격대 메뉴가 전략가에 사실로 주입됨
    assert seen["tp_md"] and "결정론 가격대 메뉴" in seen["tp_md"]
    rec = captured["rec"]
    # 메뉴 영속(설명가능성)
    assert "trade_plan_menu" in rec.data
    assert rec.data["trade_plan_menu"]["entry_hint"] is not None
    # 절대 가드레일 — 손절 −10%(9000) → 오닐 −7% floor(9300) clamp
    assert rec.stop_loss == pytest.approx(9300.0)
    assert rec.data["trade_plan"]["oneill_clamped"]["to"] == pytest.approx(9300.0)
    assert "menu_bound" in rec.data["trade_plan"]


# ---------------------------------------------------------------------------
# run_signal_for_ticker — 전략가 직접 호출 → cadence-keyed persist (source=auto)
# ---------------------------------------------------------------------------


async def test_run_signal_for_ticker_persists_with_cadence_id_and_source(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        asig, "persist_recommendation",
        lambda rec: (captured.__setitem__("rec", rec), True)[1],
    )
    r = await run_signal_for_ticker(
        ticker="005930", track="A", snapshot=None, cadence="postclose",
        as_of="2026-06-15", scorecard=_sample_scorecard(),
        strategist_runner=_stub_runner(_REC_WAIT), band_gate=False,
    )
    assert r["persisted"] is True
    assert r["verdict"] == "wait"
    rec = captured["rec"]
    # cadence-keyed 멱등 id + source/cadence 태그
    assert rec.recommendation_id == "REC-2026-06-15-postclose-005930-A"
    assert rec.data["source"] == "auto"
    assert rec.data["cadence"] == "postclose"
    assert rec.data["recommendation_id"] == "REC-2026-06-15-postclose-005930-A"


async def test_run_signal_for_ticker_no_yaml_skips_persist(monkeypatch):
    monkeypatch.setattr(asig, "persist_recommendation", lambda rec: True)
    r = await run_signal_for_ticker(
        ticker="005930", track="A", snapshot=None, cadence="postclose",
        as_of="2026-06-15", scorecard=_sample_scorecard(),
        strategist_runner=_stub_runner("YAML 없는 개념 설명 응답"), band_gate=False,
    )
    assert r["persisted"] is False
    assert r["reason"] == "no_yaml"


async def test_run_signal_for_ticker_bad_track_skips(monkeypatch):
    r = await run_signal_for_ticker(
        ticker="005930", track="Z", snapshot=None, cadence="postclose",
        as_of="2026-06-15", scorecard=_sample_scorecard(),
        strategist_runner=_stub_runner(_REC_WAIT),
    )
    assert r["persisted"] is False and r["reason"] == "bad_track"


# ---------------------------------------------------------------------------
# run_signal_cadence — watchlist→screen→종목×트랙→persist 한 바퀴
# ---------------------------------------------------------------------------


async def test_run_signal_cadence_funnel(monkeypatch):
    async def _watchlist(**kw):
        return ["005930", "000660"]

    async def _scorecard(ticker, snapshot):
        return Scorecard(ticker=ticker, display_name=ticker, s_score=7.0, buy_score=6.5)

    monkeypatch.setattr(asig, "build_watchlist", _watchlist)
    monkeypatch.setattr(asig, "get_current_regime", lambda as_of: "strong_bull")
    # 컷: 005930 통과(7.5), 000660 미달은 screen 이 거름 → 1종목만
    monkeypatch.setattr(
        asig, "screen_watchlist",
        lambda wlist, regime, **kw: [{"ticker": "005930", "screening_score": 7.5}],
    )
    monkeypatch.setattr(asig, "compute_scorecard", _scorecard)
    monkeypatch.setattr(asig, "persist_recommendation", lambda rec: True)

    summary = await run_signal_cadence(
        cadence="intraday1", as_of="2026-06-15",
        snapshot=object(), strategist_runner=_stub_runner(_REC_BUY_B),
        band_gate=False,
    )
    assert summary["watchlist"] == 2
    assert summary["screened"] == 1
    # 1 종목 × 2 트랙 = 2 평가
    assert summary["evaluated"] == 2
    assert summary["persisted"] == 2
    # _REC_BUY_B = verdict buy → 2 건 다 buy
    assert summary["buys"] == 2
    assert summary["regime"] == "strong_bull"


async def test_run_signal_cadence_empty_watchlist(monkeypatch):
    async def _empty(**kw):
        return []

    monkeypatch.setattr(asig, "build_watchlist", _empty)
    monkeypatch.setattr(asig, "get_current_regime", lambda as_of: None)
    monkeypatch.setattr(asig, "screen_watchlist", lambda wlist, regime, **kw: [])
    summary = await run_signal_cadence(
        cadence="postclose", as_of="2026-06-15", snapshot=object(),
        strategist_runner=_stub_runner(_REC_WAIT), band_gate=False,
    )
    assert summary["evaluated"] == 0 and summary["persisted"] == 0


# ===========================================================================
# M2.5 — 의사결정 밴드 게이트 (장중 다중 cadence 비용 제어)
# ===========================================================================

from core.signal.auto_signal import _band, band_fingerprint  # noqa: E402


@pytest.mark.parametrize(
    "value,width,expected",
    [
        (6.0, 1.0, 6), (6.4, 1.0, 6), (6.9, 1.0, 6), (7.0, 1.0, 7),
        (None, 1.0, None), (7.5, 0.5, 15),
    ],
)
def test_band_floor_buckets(value, width, expected):
    assert _band(value, width) == expected


def test_band_fingerprint_stable_for_same_scorecard():
    sc1 = _sample_scorecard()
    sc2 = _sample_scorecard()
    assert band_fingerprint(sc1, "A") == band_fingerprint(sc2, "A")


def test_band_fingerprint_differs_by_track():
    sc = _sample_scorecard()
    assert band_fingerprint(sc, "A") != band_fingerprint(sc, "B")


def test_band_fingerprint_changes_on_score_band_cross():
    sc_a = _sample_scorecard()           # buy_score 6.5 → band 6
    sc_b = _sample_scorecard()
    sc_b.buy_score = 7.2                  # → band 7 (밴드 넘음)
    assert band_fingerprint(sc_a, "A") != band_fingerprint(sc_b, "A")


def test_band_fingerprint_unchanged_within_band():
    sc_a = _sample_scorecard()           # buy_score 6.5 → band 6
    sc_b = _sample_scorecard()
    sc_b.buy_score = 6.9                  # 같은 band 6 → 지문 동일
    assert band_fingerprint(sc_a, "A") == band_fingerprint(sc_b, "A")


def test_band_fingerprint_changes_on_kill_switch():
    sc_a = _sample_scorecard()           # dd 2 → 0
    sc_b = _sample_scorecard()
    sc_b.distribution_day_count = 4      # ≥4 → kill bit 1
    assert band_fingerprint(sc_a, "A") != band_fingerprint(sc_b, "A")


def test_band_fingerprint_changes_on_regime():
    sc_a = _sample_scorecard()           # strong_bull
    sc_b = _sample_scorecard()
    sc_b.regime = "strong_bear"
    assert band_fingerprint(sc_a, "A") != band_fingerprint(sc_b, "A")


async def test_gate_skips_when_fingerprint_matches(monkeypatch):
    """직전 지문과 같으면 전략가 호출 0 (스킵)."""
    calls = {"n": 0}

    async def _runner(track_id, messages, **kw):
        calls["n"] += 1
        return SimpleNamespace(text=_REC_WAIT)

    monkeypatch.setattr(asig, "persist_recommendation", lambda rec: True)
    sc = _sample_scorecard()
    fp = band_fingerprint(sc, "A", score_width=1.0)
    r = await run_signal_for_ticker(
        ticker="005930", track="A", snapshot=None, cadence="intraday2",
        as_of="2026-06-15", scorecard=sc, strategist_runner=_runner,
        band_gate=True, last_fingerprint_reader=lambda t, tr: fp,
    )
    assert r.get("skipped") is True
    assert r["reason"] == "band_unchanged"
    assert calls["n"] == 0  # 전략가 호출 안 됨 = 비용 0


async def test_gate_proceeds_when_fingerprint_differs(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        asig, "persist_recommendation",
        lambda rec: (captured.__setitem__("rec", rec), True)[1],
    )
    r = await run_signal_for_ticker(
        ticker="005930", track="A", snapshot=None, cadence="intraday2",
        as_of="2026-06-15", scorecard=_sample_scorecard(),
        strategist_runner=_stub_runner(_REC_WAIT),
        band_gate=True, last_fingerprint_reader=lambda t, tr: "STALE-DIFFERENT",
    )
    assert r["persisted"] is True
    # 지문이 rec.data 에 박혀 다음 cadence 비교 기준이 됨
    assert captured["rec"].data["band_fingerprint"] == band_fingerprint(_sample_scorecard(), "A")


async def test_gate_disabled_always_calls(monkeypatch):
    calls = {"n": 0}

    async def _runner(track_id, messages, **kw):
        calls["n"] += 1
        return SimpleNamespace(text=_REC_WAIT)

    monkeypatch.setattr(asig, "persist_recommendation", lambda rec: True)
    sc = _sample_scorecard()
    fp = band_fingerprint(sc, "A")
    # 지문이 같아도 band_gate=False 면 호출
    r = await run_signal_for_ticker(
        ticker="005930", track="A", snapshot=None, cadence="intraday2",
        as_of="2026-06-15", scorecard=sc, strategist_runner=_runner,
        band_gate=False, last_fingerprint_reader=lambda t, tr: fp,
    )
    assert r["persisted"] is True
    assert calls["n"] == 1


# ===========================================================================
# M3 — 스케줄러 잡 (run_auto_signal_job)
# ===========================================================================

import collectors.screening as _screening  # noqa: E402
from server.schedulers.jobs import auto_signal as _job  # noqa: E402
from server.schedulers.jobs.auto_signal import INTRADAY_CADENCES  # noqa: E402


def test_intraday_cadences_are_three_after_snapshot_refresh():
    assert INTRADAY_CADENCES == [
        ("intraday1", 9, 35), ("intraday2", 12, 35), ("intraday3", 14, 35),
    ]


async def test_job_noop_when_disabled(monkeypatch):
    calls = {"n": 0}

    async def _cadence(**kw):
        calls["n"] += 1
        return {}

    monkeypatch.setattr(_screening, "get_auto_signal_enabled", lambda: False)
    monkeypatch.setattr(asig, "run_signal_cadence", _cadence)
    out = await _job.run_auto_signal_job("intraday1")
    assert out["disabled"] is True
    assert calls["n"] == 0  # 마스터 OFF → run_signal_cadence 호출 안 됨


async def test_job_calls_cadence_with_production_provider(monkeypatch):
    captured = {}

    async def _cadence(**kw):
        captured.update(kw)
        return {"cadence": kw["cadence"], "screened": 2, "persisted": 3, "buys": 1}

    monkeypatch.setattr(_screening, "get_auto_signal_enabled", lambda: True)
    monkeypatch.setattr(asig, "run_signal_cadence", _cadence)
    out = await _job.run_auto_signal_job("postclose")
    assert out["persisted"] == 3
    assert captured["cadence"] == "postclose"
    # production 경로 = 실 배포 모델, silent mock 금지
    assert captured["provider"] == "gemini"
    assert captured["mock_fallback_allowed"] is False


async def test_job_graceful_on_cadence_failure(monkeypatch):
    async def _boom(**kw):
        raise RuntimeError("snapshot down")

    monkeypatch.setattr(_screening, "get_auto_signal_enabled", lambda: True)
    monkeypatch.setattr(asig, "run_signal_cadence", _boom)
    out = await _job.run_auto_signal_job("intraday2")
    assert "error" in out and "snapshot down" in out["error"]


def test_cadence_jobs_registered_with_misfire_tolerance():
    """절전/단절로 cron 을 놓쳐도 깨어나면 따라잡도록 misfire 내성 등록 (2026-06-15 사고 보강).

    기본 misfire_grace_time=1초라 짧은 절전에도 영구 스킵되던 것을 보강. 장중 3 cadence +
    postclose(18:05 daily_refresh) 모두 grace=MISFIRE_GRACE_SEC·coalesce·max_instances=1.
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from server.schedulers.jobs import register_infra_jobs
    from server.schedulers.jobs.auto_signal import MISFIRE_GRACE_SEC

    sched = AsyncIOScheduler(timezone="Asia/Seoul")
    register_infra_jobs(sched)

    for cadence, _h, _m in INTRADAY_CADENCES:
        job = sched.get_job(f"auto_signal::{cadence}")
        assert job is not None, f"{cadence} 미등록"
        assert job.misfire_grace_time == MISFIRE_GRACE_SEC
        assert job.coalesce is True
        assert job.max_instances == 1

    # postclose 권고 cadence 를 품은 18:05 daily_refresh 도 동일 내성
    drj = sched.get_job("infra::daily_refresh")
    assert drj is not None
    assert drj.misfire_grace_time == MISFIRE_GRACE_SEC
    assert drj.coalesce is True
    assert drj.max_instances == 1


# ===========================================================================
# M4 — 알림 (🟢 매수/매도 개별 · 🔵 일일 요약)
# ===========================================================================


async def test_buy_verdict_emits_green_trade_signal(monkeypatch, captured_notify):
    monkeypatch.setattr(asig, "persist_recommendation", lambda rec: True)
    await run_signal_for_ticker(
        ticker="005930", track="B", snapshot=None, cadence="intraday1",
        as_of="2026-06-15", scorecard=_sample_scorecard(),
        strategist_runner=_stub_runner(_REC_BUY_B), band_gate=False,
    )
    assert len(captured_notify) == 1
    n = captured_notify[0]
    assert n["notification_type"] == "trade_signal"
    assert "매수" in n["title"] and "005930" in n["title"]


async def test_wait_verdict_emits_no_signal(monkeypatch, captured_notify):
    monkeypatch.setattr(asig, "persist_recommendation", lambda rec: True)
    await run_signal_for_ticker(
        ticker="005930", track="A", snapshot=None, cadence="intraday1",
        as_of="2026-06-15", scorecard=_sample_scorecard(),
        strategist_runner=_stub_runner(_REC_WAIT), band_gate=False,
    )
    assert captured_notify == []  # 관망은 개별 알림 없음 (스팸 방지)


async def test_notify_signals_false_suppresses(monkeypatch, captured_notify):
    monkeypatch.setattr(asig, "persist_recommendation", lambda rec: True)
    await run_signal_for_ticker(
        ticker="005930", track="B", snapshot=None, cadence="intraday1",
        as_of="2026-06-15", scorecard=_sample_scorecard(),
        strategist_runner=_stub_runner(_REC_BUY_B), band_gate=False,
        notify_signals=False,
    )
    assert captured_notify == []


async def test_postclose_cadence_emits_blue_daily_summary(monkeypatch, captured_notify):
    async def _watchlist(**kw):
        return ["005930"]

    async def _scorecard(ticker, snapshot):
        return Scorecard(ticker=ticker, display_name=ticker, s_score=7.0, buy_score=6.5)

    monkeypatch.setattr(asig, "build_watchlist", _watchlist)
    monkeypatch.setattr(asig, "get_current_regime", lambda as_of: "strong_bull")
    monkeypatch.setattr(
        asig, "screen_watchlist",
        lambda wlist, regime, **kw: [{"ticker": "005930", "screening_score": 7.5}],
    )
    monkeypatch.setattr(asig, "compute_scorecard", _scorecard)
    monkeypatch.setattr(asig, "persist_recommendation", lambda rec: True)

    await run_signal_cadence(
        cadence="postclose", as_of="2026-06-15", snapshot=object(),
        strategist_runner=_stub_runner(_REC_BUY_B), band_gate=False,
    )
    summaries = [n for n in captured_notify if n["notification_type"] == "market_briefing"]
    assert len(summaries) == 1
    assert "일일 요약" in summaries[0]["title"]


async def test_intraday_cadence_emits_no_daily_summary(monkeypatch, captured_notify):
    async def _watchlist(**kw):
        return ["005930"]

    async def _scorecard(ticker, snapshot):
        return Scorecard(ticker=ticker, display_name=ticker, s_score=7.0, buy_score=6.5)

    monkeypatch.setattr(asig, "build_watchlist", _watchlist)
    monkeypatch.setattr(asig, "get_current_regime", lambda as_of: "strong_bull")
    monkeypatch.setattr(
        asig, "screen_watchlist",
        lambda wlist, regime, **kw: [{"ticker": "005930", "screening_score": 7.5}],
    )
    monkeypatch.setattr(asig, "compute_scorecard", _scorecard)
    monkeypatch.setattr(asig, "persist_recommendation", lambda rec: True)

    await run_signal_cadence(
        cadence="intraday2", as_of="2026-06-15", snapshot=object(),
        strategist_runner=_stub_runner(_REC_BUY_B), band_gate=False,
    )
    # 장중은 일일 요약 없음 (개별 🟢 매수만)
    summaries = [n for n in captured_notify if n["notification_type"] == "market_briefing"]
    assert summaries == []
    greens = [n for n in captured_notify if n["notification_type"] == "trade_signal"]
    assert len(greens) == 2  # 1종목 × 2트랙 buy


# ===========================================================================
# M6 — 병렬화 + 재시도 (속도·신뢰성)
# ===========================================================================

from core.signal.auto_signal import _is_transient  # noqa: E402


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """재시도 backoff 실제 sleep 제거 (테스트 가속)."""
    async def _fast(_s):
        return None
    monkeypatch.setattr(asig.asyncio, "sleep", _fast)


def _seq_runner(texts, raises=None):
    """호출마다 다른 응답/예외 — 재시도 검증용. .calls['n'] = 호출 수."""
    state = {"n": 0}

    async def _run(track_id, messages, **kw):
        i = state["n"]
        state["n"] += 1
        if raises and i < len(raises) and raises[i] is not None:
            raise raises[i]
        return SimpleNamespace(text=texts[min(i, len(texts) - 1)])

    _run.calls = state
    return _run


@pytest.mark.parametrize(
    "msg,expected",
    [
        ("503 UNAVAILABLE", True), ("model overloaded", True),
        ("deadline exceeded", True), ("rate limit", True),
        ("invalid ticker", False), ("KeyError", False),
    ],
)
def test_is_transient(msg, expected):
    assert _is_transient(msg) is expected


async def test_retry_recovers_from_transient_503(monkeypatch):
    monkeypatch.setattr(asig, "persist_recommendation", lambda rec: True)
    runner = _seq_runner([_REC_WAIT], raises=[RuntimeError("503 UNAVAILABLE"), None])
    r = await run_signal_for_ticker(
        ticker="005930", track="A", snapshot=None, cadence="postclose",
        as_of="2026-06-15", scorecard=_sample_scorecard(),
        strategist_runner=runner, band_gate=False, retries=1,
    )
    assert r["persisted"] is True
    assert runner.calls["n"] == 2  # 1차 503 → 2차 성공


async def test_retry_recovers_from_no_yaml(monkeypatch):
    monkeypatch.setattr(asig, "persist_recommendation", lambda rec: True)
    runner = _seq_runner(["YAML 없는 산문 응답", _REC_WAIT])
    r = await run_signal_for_ticker(
        ticker="005930", track="A", snapshot=None, cadence="postclose",
        as_of="2026-06-15", scorecard=_sample_scorecard(),
        strategist_runner=runner, band_gate=False, retries=1,
    )
    assert r["persisted"] is True
    assert runner.calls["n"] == 2


async def test_retry_exhausted_returns_reason(monkeypatch):
    monkeypatch.setattr(asig, "persist_recommendation", lambda rec: True)
    runner = _seq_runner([_REC_WAIT], raises=[RuntimeError("503"), RuntimeError("503")])
    r = await run_signal_for_ticker(
        ticker="005930", track="A", snapshot=None, cadence="postclose",
        as_of="2026-06-15", scorecard=_sample_scorecard(),
        strategist_runner=runner, band_gate=False, retries=1,
    )
    assert r["persisted"] is False
    assert "503" in r["reason"]
    assert runner.calls["n"] == 2  # 시도 2회 후 포기


async def test_non_transient_error_not_retried(monkeypatch):
    monkeypatch.setattr(asig, "persist_recommendation", lambda rec: True)
    runner = _seq_runner([_REC_WAIT], raises=[ValueError("bad ticker schema")])
    r = await run_signal_for_ticker(
        ticker="005930", track="A", snapshot=None, cadence="postclose",
        as_of="2026-06-15", scorecard=_sample_scorecard(),
        strategist_runner=runner, band_gate=False, retries=3,
    )
    assert r["persisted"] is False
    assert runner.calls["n"] == 1  # 비-transient → 재시도 안 함


async def test_cadence_parallel_processes_all_tickers(monkeypatch):
    import collectors.screening as screening

    async def _watchlist(**kw):
        return ["005930", "000660", "035720"]

    async def _scorecard(ticker, snapshot):
        return Scorecard(ticker=ticker, display_name=ticker, s_score=7.0, buy_score=6.5)

    monkeypatch.setattr(asig, "build_watchlist", _watchlist)
    monkeypatch.setattr(asig, "get_current_regime", lambda as_of: "strong_bull")
    monkeypatch.setattr(
        asig, "screen_watchlist",
        lambda wlist, regime, **kw: [{"ticker": t, "screening_score": 7.5} for t in wlist],
    )
    monkeypatch.setattr(asig, "compute_scorecard", _scorecard)
    monkeypatch.setattr(asig, "persist_recommendation", lambda rec: True)
    monkeypatch.setattr(screening, "get_signal_concurrency", lambda: 3)

    summary = await run_signal_cadence(
        cadence="postclose", as_of="2026-06-15", snapshot=object(),
        strategist_runner=_stub_runner(_REC_WAIT), band_gate=False,
    )
    # 3 종목 × 2 트랙 = 6 평가 (병렬 경로에서도 전부 처리)
    assert summary["evaluated"] == 6
    assert summary["persisted"] == 6
    assert summary["screened"] == 3


async def test_cadence_scorecard_failure_isolated(monkeypatch):
    import collectors.screening as screening

    async def _watchlist(**kw):
        return ["005930", "BADXXX"]

    async def _scorecard(ticker, snapshot):
        if ticker == "BADXXX":
            raise RuntimeError("chart fetch failed")
        return Scorecard(ticker=ticker, display_name=ticker, s_score=7.0, buy_score=6.5)

    monkeypatch.setattr(asig, "build_watchlist", _watchlist)
    monkeypatch.setattr(asig, "get_current_regime", lambda as_of: "strong_bull")
    monkeypatch.setattr(
        asig, "screen_watchlist",
        lambda wlist, regime, **kw: [{"ticker": t, "screening_score": 7.5} for t in wlist],
    )
    monkeypatch.setattr(asig, "compute_scorecard", _scorecard)
    monkeypatch.setattr(asig, "persist_recommendation", lambda rec: True)
    monkeypatch.setattr(screening, "get_signal_concurrency", lambda: 2)

    summary = await run_signal_cadence(
        cadence="postclose", as_of="2026-06-15", snapshot=object(),
        strategist_runner=_stub_runner(_REC_WAIT), band_gate=False,
    )
    # 정상 종목은 persist, 실패 종목은 격리 (cadence 안 죽음)
    assert summary["persisted"] == 2  # 005930 × 2 트랙
    bad = [r for r in summary["results"] if r["ticker"] == "BADXXX"]
    assert len(bad) == 2 and all("scorecard" in r["reason"] for r in bad)
