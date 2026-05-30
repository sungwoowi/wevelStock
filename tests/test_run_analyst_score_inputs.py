"""INFRA-SCORE-INPUTS-001 — run_analyst 의 technicals_md / flow_inputs_md 자동 주입 검증.

- trader (reads_technicals=True) + target_ticker → [5b] 주입 + advisory_t_score metadata
- trader + target_ticker 없음 → silent skip (technicals_failures=["target_ticker_absent"])
- flow_analyzer (reads_flow_inputs=True) → [5c] 주입 (시장 레벨, ticker 없이도) + advisory_f_score
- 다른 분석가 → 주입 X
"""
from __future__ import annotations

import sys
import time
from typing import Any

import pytest

import core.inference.run_analyst  # noqa: F401
from collectors.flow_inputs import FlowInputs
from collectors.snapshot import MarketSnapshot
from collectors.technicals import TechnicalInputs

ra_mod = sys.modules["core.inference.run_analyst"]


def _fake_snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        fetched_at=time.time(),
        fetched_at_iso="2026-05-30T20:00:00+09:00",
        overnight={}, fear_greed={}, kr_indices={}, kr_supply={},
        kr_futures_supply={}, kr_sectors={}, kr_leading={},
        failures=[], source_map={}, db_run_ids={},
    )


def _fake_ti() -> TechnicalInputs:
    return TechnicalInputs(
        ticker="005930", divergence_pct=10.0, macd={"histogram": 254, "signal": 980, "norm": 3.1},
        volume_ratio=1.8, rr=None, alpha=None,
        divergence_score=8.0, macd_score=7.0, volume_score=8.0, rr_score=None,
        advisory_t_score=6.5, reasons=[], source="db",
    )


def _fake_fi() -> FlowInputs:
    return FlowInputs(
        ticker="", market="KOSPI", actual_days=60,
        net_sums={"foreign_net": 100, "institution_net": 80, "individual_net": -180,
                  "financial_inv_net": 0, "pension_net": 0},
        momentum_raw=0.6, inflow_speed_raw=None, agreement=6.0,
        momentum_score=7.0, inflow_score=None, theme_match_score=5.0,
        advisory_f_score=5.8, reasons=[], source="db",
    )


@pytest.fixture(autouse=True)
def _patch_io(monkeypatch: pytest.MonkeyPatch) -> None:
    snap = _fake_snapshot()

    async def _fake_snap():
        return snap, False

    monkeypatch.setattr(ra_mod, "build_market_snapshot", _fake_snap)
    monkeypatch.setattr(ra_mod, "render_snapshot_md", lambda s: "## stub-snapshot")

    captured: dict[str, Any] = {}

    async def _fake_llm(**kwargs: Any) -> dict[str, Any]:
        captured["system"] = kwargs.get("system")
        return {
            "content": "stub", "tokens_in": 1, "tokens_out": 1,
            "model": "mock", "cost_usd": 0.0, "raw": {"provider": "mock"},
        }

    monkeypatch.setattr(ra_mod, "call_llm", _fake_llm)
    monkeypatch.setattr(ra_mod, "_captured", captured, raising=False)


async def test_trader_injects_technicals_md(monkeypatch: pytest.MonkeyPatch) -> None:
    received = {"v": None}

    async def _fake_build(ticker: str, **_kw: Any) -> TechnicalInputs:
        received["v"] = ticker
        return _fake_ti()

    monkeypatch.setattr(ra_mod, "build_technicals", _fake_build)

    resp = await ra_mod.run_analyst(
        "trader", [{"role": "user", "content": "삼성전자 타점"}], target_ticker="005930",
    )
    assert received["v"] == "005930"
    blocks = ra_mod._captured["system"]
    assert any(b.get("text", "").lstrip().startswith("## [5b] 타점 입력 지표") for b in blocks)
    assert resp.metadata["advisory_t_score"] == 6.5
    assert resp.metadata["technicals_ticker_used"] == "005930"


async def test_trader_without_ticker_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"n": 0}

    async def _fake_build(ticker: str, **_kw: Any) -> TechnicalInputs:
        called["n"] += 1
        return _fake_ti()

    monkeypatch.setattr(ra_mod, "build_technicals", _fake_build)

    resp = await ra_mod.run_analyst(
        "trader", [{"role": "user", "content": "타점"}], target_ticker=None,
    )
    assert called["n"] == 0
    blocks = ra_mod._captured["system"]
    assert not any(b.get("text", "").lstrip().startswith("## [5b]") for b in blocks)
    assert resp.metadata["technicals_failures"] == ["target_ticker_absent"]


async def test_flow_analyzer_injects_flow_inputs_md(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_build(**_kw: Any) -> FlowInputs:
        return _fake_fi()

    monkeypatch.setattr(ra_mod, "build_flow_inputs", _fake_build)

    # ticker 없이도 시장 레벨로 주입
    resp = await ra_mod.run_analyst(
        "flow_analyzer", [{"role": "user", "content": "수급 어때?"}],
    )
    blocks = ra_mod._captured["system"]
    assert any(b.get("text", "").lstrip().startswith("## [5c] 수급 입력 지표") for b in blocks)
    assert resp.metadata["advisory_f_score"] == 5.8
    assert resp.metadata["flow_inputs_market"] == "KOSPI"


async def test_other_analyst_no_score_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"t": 0, "f": 0}

    async def _ft(ticker: str, **_kw: Any) -> TechnicalInputs:
        called["t"] += 1
        return _fake_ti()

    async def _ff(**_kw: Any) -> FlowInputs:
        called["f"] += 1
        return _fake_fi()

    monkeypatch.setattr(ra_mod, "build_technicals", _ft)
    monkeypatch.setattr(ra_mod, "build_flow_inputs", _ff)

    await ra_mod.run_analyst(
        "principle_guardian", [{"role": "user", "content": "7계명"}], target_ticker="005930",
    )
    assert called["t"] == 0 and called["f"] == 0
    blocks = ra_mod._captured["system"]
    assert not any(b.get("text", "").lstrip().startswith("## [5b]") for b in blocks)
    assert not any(b.get("text", "").lstrip().startswith("## [5c]") for b in blocks)
