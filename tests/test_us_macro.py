"""INFRA-US-MACRO-SNAPSHOT-001 — 미장 매크로 collector (MS-1).

1. classify_us_risk 결정론 매트릭스 (risk_on / neutral / risk_off / vix_panic)
2. compute_us_macro DB-first (오늘 row 박혀 있으면 fetch X)
3. graceful (yfinance 실패 → source=unavailable, 중립)
4. DB round-trip 멱등
5. 흡수 helper (one_liner 토큰 / reason / render)

외부 API 실호출 금지 — get_indices mock.
"""
from __future__ import annotations

import pytest

from collectors import us_macro as um
from collectors.us_macro import (
    USMacroSnapshot,
    classify_us_risk,
    compute_us_macro,
    reload_us_macro_config,
    upsert_us_macro,
    us_macro_reason,
    us_one_liner_token,
)
from core.db.connection import Database, reset_db


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    """temp DB + us_macro module 의 get_db 패치 + config 캐시 클리어."""
    reset_db()
    reload_us_macro_config()
    db = Database(tmp_path / "test_us_macro.sqlite")
    monkeypatch.setattr(um, "get_db", lambda: db)
    return db


# ---------------------------------------------------------------------------
# classify_us_risk 결정론 매트릭스 (순수 — DB 불필요)
# ---------------------------------------------------------------------------


def _classify(**kw):
    base = dict(
        nasdaq_change_pct=0.0,
        sp500_change_pct=0.0,
        sox_change_pct=0.0,
        vix=15.0,
        dxy_change_pct=0.0,
        us_10y_change_bp=0.0,
    )
    base.update(kw)
    return classify_us_risk(**base)


def test_classify_risk_on_strong_equity():
    """반도체·지수 강한 상승 + 잔잔한 VIX → risk_on."""
    signal, score, extreme, _ = _classify(
        nasdaq_change_pct=1.5, sp500_change_pct=1.2, sox_change_pct=2.5, vix=14.0
    )
    assert signal == "risk_on"
    assert extreme == "none"
    assert score >= 0.7


def test_classify_risk_off_weak_equity():
    """반도체·지수 급락 → risk_off (VIX 정상이라도 모멘텀으로)."""
    signal, score, extreme, _ = _classify(
        nasdaq_change_pct=-1.5, sp500_change_pct=-1.0, sox_change_pct=-2.5, vix=18.0
    )
    assert signal == "risk_off"
    assert extreme == "none"
    assert score <= -0.7


def test_classify_neutral_mixed():
    """혼조 (작은 변화) → neutral."""
    signal, _, extreme, _ = _classify(
        nasdaq_change_pct=0.2, sp500_change_pct=-0.1, sox_change_pct=0.1, vix=16.0
    )
    assert signal == "neutral"
    assert extreme == "none"


def test_classify_vix_panic_gate_forces_risk_off():
    """VIX 패닉 (≥30) → 주식이 올라도 risk_off + extreme=vix_panic."""
    signal, _, extreme, reasons = _classify(
        nasdaq_change_pct=2.0, sp500_change_pct=2.0, sox_change_pct=3.0, vix=35.0
    )
    assert signal == "risk_off"
    assert extreme == "vix_panic"
    assert any("패닉" in r for r in reasons)


def test_classify_headwind_dollar_rates_penalize():
    """달러·금리 급등 역풍이 약한 상승을 risk_off 쪽으로 끌어내림."""
    on_signal, on_score, _, _ = _classify(
        nasdaq_change_pct=0.8, sp500_change_pct=0.8, sox_change_pct=0.8,
        dxy_change_pct=0.0, us_10y_change_bp=0.0,
    )
    hw_signal, hw_score, _, _ = _classify(
        nasdaq_change_pct=0.8, sp500_change_pct=0.8, sox_change_pct=0.8,
        dxy_change_pct=1.0, us_10y_change_bp=15.0,
    )
    assert hw_score < on_score  # 역풍이 점수를 깎음


def test_classify_all_missing_returns_neutral():
    """전 지표 결측 → neutral (추정 안 함)."""
    signal, score, extreme, reasons = classify_us_risk(
        nasdaq_change_pct=None, sp500_change_pct=None, sox_change_pct=None,
        vix=None, dxy_change_pct=None, us_10y_change_bp=None,
    )
    assert signal == "neutral"
    assert score == 0.0
    assert extreme == "none"
    assert any("결측" in r for r in reasons)


# ---------------------------------------------------------------------------
# compute_us_macro DB-first + graceful
# ---------------------------------------------------------------------------


def _fake_indices(**overrides):
    """get_indices 반환 형태 모사. overrides 로 일부 지표 교체."""
    base = {
        "nasdaq": {"symbol": "^IXIC", "price": 20000.0, "change_pct": 1.0, "change": 200.0},
        "sp500": {"symbol": "^GSPC", "price": 6000.0, "change_pct": 0.8, "change": 48.0},
        "philly_semi": {"symbol": "^SOX", "price": 5000.0, "change_pct": 2.0, "change": 100.0},
        "vix": {"symbol": "^VIX", "price": 14.0, "change_pct": -5.0, "change": -0.7},
        "dxy": {"symbol": "DX-Y.NYB", "price": 104.0, "change_pct": 0.1, "change": 0.1},
        "us_10y": {"symbol": "^TNX", "price": 4.5, "change_pct": 0.2, "change": 0.05},
        "gold": {"symbol": "GC=F", "price": 2600.0, "change_pct": 0.3, "change": 8.0},
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_compute_db_first_hit_skips_fetch(isolated_db, monkeypatch):
    """오늘 row 가 이미 있으면 get_indices 호출 안 함."""
    today = um._today_kst_str()
    upsert_us_macro(USMacroSnapshot(
        date=today, nasdaq_change_pct=1.0, sp500_change_pct=1.0, sox_change_pct=1.0,
        vix=13.0, vix_change_pct=-1.0, dxy=104.0, dxy_change_pct=0.0,
        us_10y=4.5, us_10y_change_bp=0.0, gold_change_pct=0.0,
        risk_signal="risk_on", signal_score=1.0, extreme="none", reasons=["cached"],
    ))

    called = {"n": 0}

    async def _boom(names=None):
        called["n"] += 1
        raise AssertionError("get_indices should not be called on DB hit")

    monkeypatch.setattr("connectors.yfinance.client.get_indices", _boom)
    snap = await compute_us_macro()
    assert snap.source == "db"
    assert snap.risk_signal == "risk_on"
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_compute_fetch_and_classify(isolated_db, monkeypatch):
    """DB miss → get_indices fetch → classify → upsert (risk_on)."""
    async def _fake(names=None):
        return _fake_indices()

    monkeypatch.setattr("connectors.yfinance.client.get_indices", _fake)
    snap = await compute_us_macro(force_refresh=True)
    assert snap.source == "computed"
    assert snap.risk_signal == "risk_on"
    assert snap.sox_change_pct == 2.0
    assert snap.us_10y_change_bp == 5.0  # change 0.05 * 100
    # DB round-trip 멱등
    again = await compute_us_macro()
    assert again.source == "db"
    assert again.risk_signal == "risk_on"


@pytest.mark.asyncio
async def test_compute_graceful_on_fetch_failure(isolated_db, monkeypatch):
    """yfinance 전 지표 error → source=unavailable, 중립 폴백 (막지 않음)."""
    async def _all_error(names=None):
        return {n: {"symbol": n, "error": "no history"} for n in (names or [])}

    monkeypatch.setattr("connectors.yfinance.client.get_indices", _all_error)
    snap = await compute_us_macro(force_refresh=True)
    assert snap.source == "unavailable"
    assert snap.risk_signal == "neutral"
    assert snap.extreme == "none"


@pytest.mark.asyncio
async def test_compute_vix_panic_live(isolated_db, monkeypatch):
    """라이브 경로 vix_panic — 주식 강세라도 risk_off 게이트."""
    async def _panic(names=None):
        return _fake_indices(vix={"symbol": "^VIX", "price": 36.0, "change_pct": 40.0, "change": 10.0})

    monkeypatch.setattr("connectors.yfinance.client.get_indices", _panic)
    snap = await compute_us_macro(force_refresh=True)
    assert snap.extreme == "vix_panic"
    assert snap.risk_signal == "risk_off"


# ---------------------------------------------------------------------------
# 흡수 helper
# ---------------------------------------------------------------------------


def _snap(signal: str, extreme: str = "none", source: str = "computed") -> USMacroSnapshot:
    return USMacroSnapshot(
        date="2026-06-07", nasdaq_change_pct=1.0, sp500_change_pct=1.0, sox_change_pct=2.0,
        vix=14.0, vix_change_pct=-1.0, dxy=104.0, dxy_change_pct=0.0,
        us_10y=4.5, us_10y_change_bp=0.0, gold_change_pct=0.0,
        risk_signal=signal, signal_score=0.0, extreme=extreme, source=source,
    )


def test_one_liner_token_only_for_directional():
    assert us_one_liner_token(_snap("risk_off")) == " · 미장 위험회피"
    assert us_one_liner_token(_snap("risk_on")) == " · 미장 위험선호"
    assert us_one_liner_token(_snap("neutral")) == ""           # 중립 생략 (F2)
    assert us_one_liner_token(_snap("risk_on", source="unavailable")) == ""
    assert us_one_liner_token(None) == ""


def test_us_macro_reason_neutral_is_none():
    assert us_macro_reason(_snap("neutral")) is None
    r = us_macro_reason(_snap("risk_off"))
    assert r is not None and "위험회피" in r and "강등" in r
