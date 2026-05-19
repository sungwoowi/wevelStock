"""INFRA-CHART-DATA-001 — run_analyst 의 chart_data_md 자동 주입 검증.

- stock_analyst (reads_chart_data=True) + target_ticker 있음 → 주입 O + metadata 4 키
- stock_analyst + target_ticker 없음 → silent skip (chart_failures=["target_ticker_absent"])
- 다른 분석가 (reads_chart_data=False) + target_ticker 있음 → 주입 X
"""
from __future__ import annotations

import sys
import time
from typing import Any

import pytest

import core.inference.run_analyst  # noqa: F401
from collectors.charts import ChartData
from collectors.snapshot import MarketSnapshot


ra_mod = sys.modules["core.inference.run_analyst"]


def _fake_snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        fetched_at=time.time(),
        fetched_at_iso="2026-05-20T20:00:00+09:00",
        overnight={}, fear_greed={}, kr_indices={}, kr_supply={},
        kr_futures_supply={}, kr_sectors={}, kr_leading={},
        failures=[], source_map={}, db_run_ids={},
    )


def _fake_chart(ticker: str = "005930") -> ChartData:
    return ChartData(
        ticker=ticker,
        fetched_at=time.time(),
        fetched_at_iso="2026-05-20T20:00:00+09:00",
        snapshot={"current_price": 82000, "open_price": 80500, "high_price": 82300,
                  "low_price": 80200, "change_rate": 1.86,
                  "volume_today": 15000000, "value_today": 1240000000000},
        indicators={
            "current_close": 82000,
            "daily_ma": {f"ma{n}": 80000 + i for i, n in enumerate((4, 7, 20, 60, 120))},
            "weekly_ma": {f"ma{n}": 79000 + i for i, n in enumerate((10, 20, 60))},
            "monthly_ma": {f"ma{n}": 78000 + i for i, n in enumerate((7, 20))},
            "macd": {"macd": 1234, "signal": 980, "histogram": 254},
            "volume": {"today": 15000000, "ma20": 12000000, "spike_ratio": 1.25},
            "fifty_two_week": {
                "high": 85400, "high_date": "2026-04-12",
                "low": 65200, "low_date": "2025-08-30",
                "pct_from_high": -3.98, "pct_from_low": 25.8,
                "window_days": 252,
            },
            "reasons": [],
        },
        ohlcv_count=1200,
        source="db",
        db_last_date="2026-05-20",
        stale_hours=2.0,
        failures=[],
    )


@pytest.fixture(autouse=True)
def _patch_io(monkeypatch: pytest.MonkeyPatch) -> None:
    """공통 mock — snapshot + LLM + chart."""
    snap = _fake_snapshot()

    async def _fake_snap():
        return snap, False

    monkeypatch.setattr(ra_mod, "build_market_snapshot", _fake_snap)
    monkeypatch.setattr(ra_mod, "render_snapshot_md", lambda s: "## stub-snapshot")

    captured: dict[str, Any] = {}

    async def _fake_llm(**kwargs: Any) -> dict[str, Any]:
        captured["system"] = kwargs.get("system")
        return {
            "content": "stub response",
            "tokens_in": 1000,
            "tokens_out": 50,
            "model": "mock",
            "cost_usd": 0.0,
            "raw": {"provider": "mock"},
        }

    monkeypatch.setattr(ra_mod, "call_llm", _fake_llm)
    monkeypatch.setattr(ra_mod, "_captured", captured, raising=False)


# ---------------------------------------------------------------------------
# 1. stock_analyst + target_ticker → chart_data_md 주입 + metadata 정합
# ---------------------------------------------------------------------------


async def test_stock_analyst_with_target_ticker_injects_chart_md(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chart = _fake_chart("005930")

    async def _fake_build(ticker: str, **_kw: Any):
        assert ticker == "005930"
        return chart, False

    monkeypatch.setattr(ra_mod, "build_chart_data", _fake_build)

    resp = await ra_mod.run_analyst(
        "stock_analyst",
        [{"role": "user", "content": "삼성전자 분석"}],
        target_ticker="005930",
    )
    # system 블록 안에 chart 본문 들어가야 함
    system_blocks = ra_mod._captured["system"]
    chart_blocks = [b for b in system_blocks if b.get("text", "").lstrip().startswith("## [4] 차트 데이터")]
    assert len(chart_blocks) == 1
    # metadata 4 키
    md = resp.metadata
    assert md["chart_ticker"] == "005930"
    assert md["chart_source"] == "db"
    assert md["chart_ohlcv_count"] == 1200
    assert md["chart_cache_hit"] is False
    assert md["chart_failures"] == []
    assert md["chart_fetch_seconds"] is not None
    assert md["chart_data_age_seconds"] is not None


# ---------------------------------------------------------------------------
# 2. stock_analyst + target_ticker=None → silent skip + chart_failures 명시
# ---------------------------------------------------------------------------


async def test_stock_analyst_without_target_ticker_skips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"n": 0}

    async def _fake_build(ticker: str, **_kw: Any):
        called["n"] += 1
        return _fake_chart(ticker), False

    monkeypatch.setattr(ra_mod, "build_chart_data", _fake_build)

    resp = await ra_mod.run_analyst(
        "stock_analyst",
        [{"role": "user", "content": "삼성전자 분석"}],
        target_ticker=None,
    )
    # build_chart_data 호출 안 됨
    assert called["n"] == 0
    # system 블록에 chart 본문 없음
    system_blocks = ra_mod._captured["system"]
    assert not any(b.get("text", "").lstrip().startswith("## [4] 차트 데이터") for b in system_blocks)
    # metadata 에 target_ticker_absent failure 명시
    md = resp.metadata
    assert md["chart_failures"] == ["target_ticker_absent"]
    assert md["chart_ticker"] is None


# ---------------------------------------------------------------------------
# 3. 다른 분석가 (reads_chart_data=False) → target_ticker 있어도 주입 X
# ---------------------------------------------------------------------------


async def test_other_analyst_does_not_inject_chart_even_with_ticker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"n": 0}

    async def _fake_build(ticker: str, **_kw: Any):
        called["n"] += 1
        return _fake_chart(ticker), False

    monkeypatch.setattr(ra_mod, "build_chart_data", _fake_build)

    # principle_guardian = reads_chart_data=False (default)
    resp = await ra_mod.run_analyst(
        "principle_guardian",
        [{"role": "user", "content": "7 계명 점검"}],
        target_ticker="005930",
    )
    assert called["n"] == 0  # 호출 자체 skip
    system_blocks = ra_mod._captured["system"]
    assert not any(b.get("text", "").lstrip().startswith("## [4] 차트 데이터") for b in system_blocks)
    md = resp.metadata
    # reads_chart_data=False 면 base_meta 그대로 (failures=[])
    assert md["chart_failures"] == []
    assert md["chart_ticker"] is None
    assert md["chart_source"] is None
