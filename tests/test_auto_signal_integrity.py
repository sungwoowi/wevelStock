"""AUTO-SIGNAL-INTEGRITY-001 — 자동 신호 정합 핫픽스 테스트.

T0-a: 시장 방어 태세(entry_posture=defensive)의 **차등 게이트** — blanket 이 아니라
"defensive 면 buy 후보에 주도주·강세섹터·건강 위치를 추가로 요구"(bear_override 와 같은 결).
사용자 결정 2026-07-05: 차등 게이트 + wait 강등·원판단 기록(posture_blocked).

T0-b: wave_alive 결정론 파생 — Track A=주봉 / Track B=일봉 α label(trend_broken 여부).
실사고 표본 = 후성(093370) 2026-06-16: 3일 +38% 블로우오프 익일, defensive 태세에서 buy 발령.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.signal.alpha_posture import (
    PostureConfig,
    PostureInputs,
    derive_alpha_posture,
    posture_config_from_dict,
)


def _strong_a(**over: object) -> PostureInputs:
    """Track A 매수 후보로 충분한 기본 입력 (테스트별 override)."""
    base = dict(
        track="A", regime="strong_bull", s_score=8.0, buy_score=7.0,
        rs_score=8.0, extension_score=7.0, sector_rs_score=8.0,
        distribution_day_count=0, wave_alive=True,
    )
    base.update(over)
    return PostureInputs(**base)  # type: ignore[arg-type]


# --- T0-a: defensive 차등 게이트 -------------------------------------------


def test_defensive_demotes_non_leader_buy_to_wait() -> None:
    # 방어 태세 + 주도주/강세섹터 아님 → buy 후보라도 wait 강등 (차등 게이트).
    p = derive_alpha_posture(_strong_a(
        entry_posture="defensive", s_score=6.5, rs_score=6.0, sector_rs_score=None,
    ))
    assert p.verdict_candidate == "wait"
    assert p.modulation.get("defensive_demote") is True
    assert p.modulation.get("pre_defensive_candidate") == "buy"  # 원판단 기록
    assert p.conditional_entry is not None
    assert p.conditional_entry["trigger"] == "defensive_release"


def test_defensive_passes_leader_sector_healthy_wave() -> None:
    # 방어 태세여도 주도주 + 강세섹터 + 건강 위치 + 파동 생존 = buy 유지 (공포를 기회로).
    p = derive_alpha_posture(_strong_a(entry_posture="defensive"))
    assert p.verdict_candidate == "buy"
    assert p.modulation.get("defensive_pass") is True


def test_non_defensive_posture_leaves_buy_unchanged() -> None:
    # aggressive/neutral/None 은 기존 동작 그대로 (게이트 미발동).
    for posture in ("aggressive", "neutral", None):
        p = derive_alpha_posture(_strong_a(
            entry_posture=posture, s_score=6.5, rs_score=6.0, sector_rs_score=None,
        ))
        assert p.verdict_candidate == "buy", f"posture={posture}"
        assert "defensive_demote" not in p.modulation


def test_defensive_gate_config_disable() -> None:
    # config 로 게이트 끄면 defensive 여도 기존 동작 (watchdog 외부화 원칙).
    cfg = posture_config_from_dict({"defensive_gate_enabled": False})
    p = derive_alpha_posture(
        _strong_a(entry_posture="defensive", s_score=6.5, rs_score=6.0, sector_rs_score=None),
        cfg,
    )
    assert p.verdict_candidate == "buy"


def test_bear_override_not_double_blocked_under_defensive() -> None:
    # 약세장 bear_override(주도주 눌림목)는 defensive 조건을 이미 충족 → 이중 차단 없음.
    p = derive_alpha_posture(_strong_a(regime="moderate_bear", entry_posture="defensive"))
    assert p.verdict_candidate == "buy"
    assert p.modulation.get("bear_override") is True


def test_defensive_demote_requires_wave() -> None:
    # 방어 태세 통과에 파동 생존 필수 (require_wave_for_bear_override 기본 True 준용).
    p = derive_alpha_posture(_strong_a(entry_posture="defensive", wave_alive=False))
    assert p.verdict_candidate == "wait"
    assert p.modulation.get("defensive_demote") is True


def test_husung_20260616_reproduction() -> None:
    # ★ 후성 06-16 재현: defensive 태세 + 주도주 미달(s 6.5) + 섹터 미상 + 파동 미상.
    #   당시 배선(sector_rs=None·wave=None·posture 미연결)에서는 buy 발령 → 게이트가 wait.
    p = derive_alpha_posture(_strong_a(
        entry_posture="defensive",
        s_score=6.5, buy_score=7.0, rs_score=None,
        sector_rs_score=None, wave_alive=None, extension_score=None,
    ))
    assert p.verdict_candidate == "wait"
    assert p.modulation.get("defensive_demote") is True
    # 같은 입력에서 defensive 아니면 buy 였음을 함께 증명 (게이트가 변별자).
    p2 = derive_alpha_posture(_strong_a(
        s_score=6.5, buy_score=7.0, rs_score=None,
        sector_rs_score=None, wave_alive=None, extension_score=None,
    ))
    assert p2.verdict_candidate == "buy"


def test_danger_gate_still_precedes_defensive() -> None:
    # 폭락 blanket(복합 위험 게이트)은 차등 게이트보다 우선 — 기존 동작 보존.
    p = derive_alpha_posture(_strong_a(entry_posture="defensive", index_change_pct=-3.0))
    assert p.verdict_candidate == "wait"
    assert p.modulation.get("danger_gate") is True
    assert "defensive_demote" not in p.modulation


# --- T0-b: wave_alive 결정론 파생 -------------------------------------------


@dataclass
class _FakeAlphaResult:
    value: float | None
    label: str | None


def test_wave_alive_track_a_uses_weekly() -> None:
    from core.signal.alpha_posture import derive_wave_alive

    results = {
        "daily": _FakeAlphaResult(value=-0.5, label="trend_broken"),
        "weekly": _FakeAlphaResult(value=1.4, label="sweet"),
    }
    assert derive_wave_alive(results, "A") is True   # A = 주봉
    assert derive_wave_alive(results, "B") is False  # B = 일봉 (trend_broken)


def test_wave_alive_trend_broken_is_false() -> None:
    from core.signal.alpha_posture import derive_wave_alive

    results = {"weekly": _FakeAlphaResult(value=-0.2, label="trend_broken")}
    assert derive_wave_alive(results, "A") is False


def test_wave_alive_unavailable_is_none() -> None:
    from core.signal.alpha_posture import derive_wave_alive

    # α 산출 불가(value None) 또는 timeframe 부재 → None (미상, 보수 처리는 소비처가).
    assert derive_wave_alive({"weekly": _FakeAlphaResult(value=None, label=None)}, "A") is None
    assert derive_wave_alive({}, "A") is None
    assert derive_wave_alive(None, "A") is None


# --- M2: auto_signal 배선 (scorecard → posture 입력 + LLM 사후 안전핀) ------

from types import SimpleNamespace  # noqa: E402

import core.signal.auto_signal as asig  # noqa: E402
from core.signal.auto_signal import (  # noqa: E402
    Scorecard,
    _market_state_md,
    posture_inputs_from_scorecard,
    run_signal_for_ticker,
)


def _defensive_scorecard(**over: object) -> Scorecard:
    """defensive 태세 + 주도주 미달 점수표 (후성 06-16 결) — 차등 게이트 발동 조건."""
    base = dict(
        ticker="093370", display_name="후성", market="KOSPI", regime="strong_bull",
        s_score=6.5, t_score=6.0, f_score=5.5, buy_score=7.0, distribution_day_count=2,
        rs_score=6.0, extension_score=7.0, entry_posture="defensive",
        md={"stock_picker_s": "## S md", "stock_picker_buy": "## buy md",
            "trader": "## T md", "flow_analyzer": "## F md"},
    )
    base.update(over)
    return Scorecard(**base)  # type: ignore[arg-type]


def test_scorecard_wave_fields_map_by_track() -> None:
    sc = _defensive_scorecard(wave_alive_weekly=True, wave_alive_daily=False)
    inp_a = posture_inputs_from_scorecard(sc, "A")
    inp_b = posture_inputs_from_scorecard(sc, "B")
    assert inp_a.wave_alive is True    # Track A = 주봉
    assert inp_b.wave_alive is False   # Track B = 일봉
    assert inp_a.entry_posture == "defensive"
    assert inp_b.entry_posture == "defensive"


def test_market_state_md_reports_entry_posture() -> None:
    md = _market_state_md(_defensive_scorecard())
    assert "진입 자세" in md
    assert "defensive" in md


def test_sector_rs_from_s_inputs_only_when_measured() -> None:
    # supply_chain 이 theme→섹터 RS 실측일 때만 섹터 RS 로 채택 (중립 fallback 5.0 은 배제).
    measured = SimpleNamespace(supply_chain_score=8.0, supply_chain_source="theme_sector")
    neutral = SimpleNamespace(supply_chain_score=5.0, supply_chain_source="neutral_fallback")
    assert asig._sector_rs_from_s_inputs(measured) == 8.0
    assert asig._sector_rs_from_s_inputs(neutral) is None
    assert asig._sector_rs_from_s_inputs(None) is None


_REC_BUY_A_NO_REASON = """결론: 매수.

```yaml
recommendation_id: REC-LLM-093370-A
date: "2026-07-05"
ticker: "093370"
display_name: 후성
track: A
verdict: buy
entry_price: 19200
target_price_1: 22000
stop_loss: 18000
confidence: 70
reasons:
  - "테스트 매수 사유"
```
"""

_REC_BUY_A_WITH_DEVIATION = """결론: 매수 (사실 근거 있음).

```yaml
recommendation_id: REC-LLM-093370-A
date: "2026-07-05"
ticker: "093370"
display_name: 후성
track: A
verdict: buy
entry_price: 19200
target_price_1: 22000
stop_loss: 18000
confidence: 70
reasons:
  - "테스트 매수 사유"
data:
  llm_deviation_reason: "대형 수주 공시 + 외인 5일 연속 순매수 — 방어 태세 상회 사실 근거"
```
"""


def _stub_runner(text: str):
    async def _run(track_id, messages, **kw):
        return SimpleNamespace(text=text)
    return _run


async def test_defensive_codegate_demotes_unreasoned_llm_buy(monkeypatch) -> None:
    # ★ 코드 안전핀: 후보가 defensive_demote 인데 LLM 이 사실 근거(llm_deviation_reason) 없이
    #   buy 발행 → 코드가 wait 강등 + posture_blocked 원판단 기록 (persona 는 강제 불가 교훈).
    captured: dict = {}
    monkeypatch.setattr(
        asig, "persist_recommendation",
        lambda rec: (captured.__setitem__("rec", rec), True)[1],
    )
    r = await run_signal_for_ticker(
        ticker="093370", track="A", snapshot=None, cadence="intraday1",
        as_of="2026-07-05", scorecard=_defensive_scorecard(),
        strategist_runner=_stub_runner(_REC_BUY_A_NO_REASON),
        band_gate=False, notify_signals=False,
    )
    assert r["persisted"] is True
    rec = captured["rec"]
    assert rec.verdict == "wait"
    assert rec.data.get("posture_blocked") == "buy"
    assert rec.data["alpha_posture"]["modulation"].get("defensive_demote") is True
    assert r["verdict"] == "wait"


async def test_defensive_codegate_respects_llm_deviation_reason(monkeypatch) -> None:
    # 가드레일 있는 C — LLM 이 사실 근거를 로그하면 buy 존중 (공포를 기회로 판단 경로 보존).
    captured: dict = {}
    monkeypatch.setattr(
        asig, "persist_recommendation",
        lambda rec: (captured.__setitem__("rec", rec), True)[1],
    )
    monkeypatch.setattr(asig, "_emit_trade_signal", _noop_async())
    r = await run_signal_for_ticker(
        ticker="093370", track="A", snapshot=None, cadence="intraday1",
        as_of="2026-07-05", scorecard=_defensive_scorecard(),
        strategist_runner=_stub_runner(_REC_BUY_A_WITH_DEVIATION),
        band_gate=False, notify_signals=False,
    )
    assert r["persisted"] is True
    assert captured["rec"].verdict == "buy"
    assert "posture_blocked" not in captured["rec"].data


def _noop_async():
    async def _n(*a, **k):
        return None
    return _n


# --- M3 (T0-c): 결정론 7계명 체크 — buy 신호 발행 전 -------------------------

_REC_BUY_A_NO_STOP = """결론: 매수.

```yaml
recommendation_id: REC-LLM-005930-A
date: "2026-07-05"
ticker: "005930"
display_name: 삼성전자
track: A
verdict: buy
entry_price: 300000
target_price_1: 330000
confidence: 70
reasons:
  - "테스트 매수 사유"
```
"""

_REC_BUY_A_WITH_STOP = """결론: 매수.

```yaml
recommendation_id: REC-LLM-005930-A
date: "2026-07-05"
ticker: "005930"
display_name: 삼성전자
track: A
verdict: buy
entry_price: 300000
target_price_1: 330000
stop_loss: 279000
confidence: 70
reasons:
  - "테스트 매수 사유"
```
"""


def _healthy_scorecard(**over: object) -> Scorecard:
    """게이트 비발동(neutral 태세) + 지표 풍부한 점수표 — 계명 체크 단독 검증용."""
    base = dict(
        ticker="005930", display_name="삼성전자", market="KOSPI", regime="strong_bull",
        s_score=8.0, t_score=7.0, f_score=6.5, buy_score=7.5, distribution_day_count=1,
        rs_score=8.0, extension_score=7.0, entry_posture="neutral",
        md={"stock_picker_s": "## S md", "stock_picker_buy": "## buy md",
            "trader": "## T md", "flow_analyzer": "## F md"},
    )
    base.update(over)
    return Scorecard(**base)  # type: ignore[arg-type]


async def test_commandment_gate_demotes_buy_without_stop_loss(monkeypatch) -> None:
    # ★ 계명 4 — 손절선 없이 진입 금지. LLM buy 에 stop_loss 부재 → 코드가 wait 강등 + 위반 기록.
    captured: dict = {}
    monkeypatch.setattr(
        asig, "persist_recommendation",
        lambda rec: (captured.__setitem__("rec", rec), True)[1],
    )
    r = await run_signal_for_ticker(
        ticker="005930", track="A", snapshot=None, cadence="intraday1",
        as_of="2026-07-05", scorecard=_healthy_scorecard(),
        strategist_runner=_stub_runner(_REC_BUY_A_NO_STOP),
        band_gate=False, notify_signals=False,
    )
    assert r["persisted"] is True
    rec = captured["rec"]
    assert rec.verdict == "wait"
    viols = rec.data.get("commandment_violations") or []
    assert any(v.get("commandment") == "4" for v in viols)


async def test_commandment_gate_passes_buy_with_stop_and_indicators(monkeypatch) -> None:
    # 손절선 + 지표 3개 이상 → buy 유지 (게이트는 결함만 막고 정상 신호는 통과).
    captured: dict = {}
    monkeypatch.setattr(
        asig, "persist_recommendation",
        lambda rec: (captured.__setitem__("rec", rec), True)[1],
    )
    r = await run_signal_for_ticker(
        ticker="005930", track="A", snapshot=None, cadence="intraday1",
        as_of="2026-07-05", scorecard=_healthy_scorecard(),
        strategist_runner=_stub_runner(_REC_BUY_A_WITH_STOP),
        band_gate=False, notify_signals=False,
    )
    assert r["persisted"] is True
    assert captured["rec"].verdict == "buy"
    assert not captured["rec"].data.get("commandment_violations")


# --- M4 (T0-d): 미라벨링 뉴스 재분류 백필 ------------------------------------

import pytest  # noqa: E402

import collectors.news_source as ns  # noqa: E402
from core.db import Database, reset_db  # noqa: E402


@pytest.fixture
def news_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    """temp DB + news_source get_db 패치 (test_news_source isolated_db mirror)."""
    reset_db()
    db = Database(tmp_path / "test_news_backfill.sqlite")
    monkeypatch.setattr(ns, "get_db", lambda: db)
    ns.reload_news_source_config()
    return db


def _news(url: str, **kw) -> "ns.NewsItem":
    return ns.NewsItem(title=kw.pop("title", "t"), url=url, source="Yahoo", **kw)


def test_get_unlabeled_items_returns_only_missing_labels(news_db) -> None:
    # 메타발 06-23 사고 결: 수집은 됐으나 direction/magnitude 가 NULL 로 방치된 행.
    ns.upsert_news_items([
        _news("http://n/labeled", direction="down", magnitude=3, confidence=80,
              category="macro_policy", labeled_by="llm"),
        _news("http://n/no-direction", magnitude=2),
        _news("http://n/no-magnitude", direction="up"),
    ])
    out = ns.get_unlabeled_items(limit=10)
    urls = {it.url for it in out}
    assert urls == {"http://n/no-direction", "http://n/no-magnitude"}


async def test_backfill_unlabeled_news_classifies_and_persists(news_db, monkeypatch) -> None:
    ns.upsert_news_items([_news("http://n/a"), _news("http://n/b")])

    async def _fake_classify(items, **kw):
        for it in items:
            it.direction, it.magnitude, it.confidence = "down", 3, 80
            it.category, it.time_axis = "macro_policy", "short_theme"
            it.labeled_by = "llm"
        return items

    monkeypatch.setattr(ns, "classify_news_items", _fake_classify)
    result = await ns.backfill_unlabeled_news()
    assert result["candidates"] == 2
    assert result["labeled"] == 2
    # 재조회 시 미라벨링 잔량 0 (영속까지 확인)
    assert ns.get_unlabeled_items(limit=10) == []


async def test_backfill_noop_when_nothing_unlabeled(news_db) -> None:
    ns.upsert_news_items([
        _news("http://n/ok", direction="up", magnitude=1, confidence=70, labeled_by="llm"),
    ])
    result = await ns.backfill_unlabeled_news()
    assert result == {"candidates": 0, "labeled": 0}


async def test_commandment_gate_warns_on_few_indicators_but_keeps_buy(monkeypatch) -> None:
    # 계명 5 — 지표 3개 미만은 warning(기록)이지 강등 아님 (체커 severity 의미 준수).
    captured: dict = {}
    monkeypatch.setattr(
        asig, "persist_recommendation",
        lambda rec: (captured.__setitem__("rec", rec), True)[1],
    )
    sparse = _healthy_scorecard(
        s_score=8.0, buy_score=7.5, t_score=None, f_score=None,
        rs_score=None, extension_score=None,
    )
    r = await run_signal_for_ticker(
        ticker="005930", track="A", snapshot=None, cadence="intraday1",
        as_of="2026-07-05", scorecard=sparse,
        strategist_runner=_stub_runner(_REC_BUY_A_WITH_STOP),
        band_gate=False, notify_signals=False,
    )
    assert r["persisted"] is True
    assert captured["rec"].verdict == "buy"
    warns = captured["rec"].data.get("commandment_warnings") or []
    assert any(w.get("commandment") == "5" for w in warns)
