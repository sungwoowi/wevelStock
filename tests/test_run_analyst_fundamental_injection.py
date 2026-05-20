"""INFRA-FUNDAMENTAL-DATA-001 — run_analyst 의 fundamental_data_md 자동 주입 검증.

- stock_analyst (reads_fundamental_data=True) + target_ticker 있음 → 주입 O + metadata 7 키
- stock_analyst + target_ticker 없음 → silent skip (fundamental_failures=['target_ticker_absent'])
- stock_analyst + 미매핑 종목명 → fundamental_failures=ticker_resolve_failed
- 다른 분석가 (reads_fundamental_data=False) → 주입 X
- KOSDAQ ticker → market="KQ" 자동 전달
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from typing import Any

import pytest

import core.inference.run_analyst  # noqa: F401
from collectors.charts import ChartData
from collectors.fundamentals import Fundamentals
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
        snapshot={"current_price": 82000, "open_price": 80500,
                  "high_price": 82300, "low_price": 80200, "change_rate": 1.86,
                  "volume_today": 15000000, "value_today": 1240000000000},
        indicators={"current_close": 82000, "reasons": []},
        ohlcv_count=1200, source="db",
        db_last_date="2026-05-20", stale_hours=2.0, failures=[],
    )


def _fake_fundamentals(ticker: str = "005930", market: str = "KS") -> Fundamentals:
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return Fundamentals(
        ticker=ticker, market=market,
        fetched_at=time.time(), fetched_at_iso=now_iso,
        eps_ttm=9512.0, pe_ratio=12.4, roe=0.142,
        operating_margin=0.187, debt_to_equity=45.3,
        quarterly_revenue=[79.8e12, 75.2e12, 72.5e12, 67.4e12, 67.5e12],
        quarterly_operating_income=[6.7e12, 6.4e12, 5.9e12, 5.2e12, 5.2e12],
        quarterly_eps=[998.0, 935.0, 873.0, 781.0, 781.0],
        quarter_labels=["2026Q1", "2025Q4", "2025Q3", "2025Q2", "2025Q1"],
        source="yfinance", fetched_db_iso=now_iso, stale_hours=0.5,
    )


@pytest.fixture(autouse=True)
def _patch_io(monkeypatch: pytest.MonkeyPatch) -> None:
    """공통 mock — snapshot + LLM + chart (fundamental 은 각 테스트마다 별도)."""
    snap = _fake_snapshot()

    async def _fake_snap():
        return snap, False

    monkeypatch.setattr(ra_mod, "build_market_snapshot", _fake_snap)
    monkeypatch.setattr(ra_mod, "render_snapshot_md", lambda s: "## stub-snapshot")

    async def _fake_build_chart(ticker: str, **_kw: Any):
        return _fake_chart(ticker), False

    monkeypatch.setattr(ra_mod, "build_chart_data", _fake_build_chart)

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
# 1. stock_analyst + target_ticker → fundamental_data_md 주입 + metadata 7 키
# ---------------------------------------------------------------------------


async def test_stock_analyst_with_target_ticker_injects_fundamental_md(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, Any] = {"ticker": None, "market": None}

    async def _fake_get(ticker: str, market: str = "KS", **_kw: Any):
        received["ticker"] = ticker
        received["market"] = market
        return _fake_fundamentals(ticker, market)

    monkeypatch.setattr(ra_mod, "get_fundamentals", _fake_get)

    resp = await ra_mod.run_analyst(
        "stock_analyst",
        [{"role": "user", "content": "삼성전자 분석"}],
        target_ticker="005930",
    )
    # KOSPI ticker → market="KS"
    assert received["ticker"] == "005930"
    assert received["market"] == "KS"
    # system 블록에 fundamental 본문 들어가야 함
    system_blocks = ra_mod._captured["system"]
    fund_blocks = [
        b for b in system_blocks
        if b.get("text", "").lstrip().startswith("## [5] 펀더멘털 데이터")
    ]
    assert len(fund_blocks) == 1
    # metadata 7 키 정합
    md = resp.metadata
    assert md["fundamental_ticker_used"] == "005930"
    assert md["fundamental_source"] == "yfinance"
    assert md["fundamental_quarter_count"] == 5
    assert md["fundamental_ratios_count"] == 5  # 5 ratio 모두 있음
    assert md["fundamental_failures"] == []
    assert md["fundamental_age_seconds"] is not None
    assert md["fundamental_fetched_at"] is not None


# ---------------------------------------------------------------------------
# 2. stock_analyst + target_ticker=None → silent skip
# ---------------------------------------------------------------------------


async def test_stock_analyst_without_target_ticker_skips_fundamental(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"n": 0}

    async def _fake_get(ticker: str, market: str = "KS", **_kw: Any):
        called["n"] += 1
        return _fake_fundamentals(ticker, market)

    monkeypatch.setattr(ra_mod, "get_fundamentals", _fake_get)

    resp = await ra_mod.run_analyst(
        "stock_analyst",
        [{"role": "user", "content": "분석"}],
        target_ticker=None,
    )
    assert called["n"] == 0  # 호출 자체 skip
    system_blocks = ra_mod._captured["system"]
    assert not any(
        b.get("text", "").lstrip().startswith("## [5] 펀더멘털 데이터")
        for b in system_blocks
    )
    md = resp.metadata
    assert md["fundamental_failures"] == ["target_ticker_absent"]
    assert md["fundamental_ticker_used"] is None


# ---------------------------------------------------------------------------
# 3. 미매핑 종목명 → fundamental_failures=ticker_resolve_failed
# ---------------------------------------------------------------------------


async def test_stock_analyst_with_unmapped_name_yields_resolve_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"n": 0}

    async def _fake_get(ticker: str, market: str = "KS", **_kw: Any):
        called["n"] += 1
        return _fake_fundamentals(ticker, market)

    monkeypatch.setattr(ra_mod, "get_fundamentals", _fake_get)

    resp = await ra_mod.run_analyst(
        "stock_analyst",
        [{"role": "user", "content": "분석"}],
        target_ticker="없는주식이름abc",
    )
    assert called["n"] == 0
    md = resp.metadata
    assert len(md["fundamental_failures"]) == 1
    assert md["fundamental_failures"][0].startswith("ticker_resolve_failed:")
    assert "없는주식이름abc" in md["fundamental_failures"][0]


# ---------------------------------------------------------------------------
# 4. 다른 분석가 (reads_fundamental_data=False) → 주입 X
# ---------------------------------------------------------------------------


async def test_other_analyst_does_not_inject_fundamental(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"n": 0}

    async def _fake_get(ticker: str, market: str = "KS", **_kw: Any):
        called["n"] += 1
        return _fake_fundamentals(ticker, market)

    monkeypatch.setattr(ra_mod, "get_fundamentals", _fake_get)

    # principle_guardian = reads_fundamental_data=False (default)
    resp = await ra_mod.run_analyst(
        "principle_guardian",
        [{"role": "user", "content": "7 계명 점검"}],
        target_ticker="005930",
    )
    assert called["n"] == 0  # 호출 자체 skip
    system_blocks = ra_mod._captured["system"]
    assert not any(
        b.get("text", "").lstrip().startswith("## [5] 펀더멘털 데이터")
        for b in system_blocks
    )
    md = resp.metadata
    # reads_fundamental_data=False 면 base_meta 그대로
    assert md["fundamental_failures"] == []
    assert md["fundamental_ticker_used"] is None
    assert md["fundamental_source"] is None


# ---------------------------------------------------------------------------
# 5. KOSDAQ ticker → market="KQ" 자동 전달
# ---------------------------------------------------------------------------


async def test_kosdaq_ticker_passes_market_kq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, Any] = {"market": None}

    async def _fake_get(ticker: str, market: str = "KS", **_kw: Any):
        received["market"] = market
        return _fake_fundamentals(ticker, market)

    monkeypatch.setattr(ra_mod, "get_fundamentals", _fake_get)

    # 에코프로비엠 (247540) = KOSDAQ
    resp = await ra_mod.run_analyst(
        "stock_analyst",
        [{"role": "user", "content": "에코프로비엠 분석"}],
        target_ticker="247540",
    )
    assert received["market"] == "KQ"
    md = resp.metadata
    assert md["fundamental_ticker_used"] == "247540"


# ---------------------------------------------------------------------------
# 6. get_fundamentals 가 None 반환 → fundamental_failures=no_fundamental_data
# ---------------------------------------------------------------------------


async def test_get_fundamentals_none_yields_no_data_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_get(ticker: str, market: str = "KS", **_kw: Any):
        return None  # yfinance 실패 + DB 부재 시나리오

    monkeypatch.setattr(ra_mod, "get_fundamentals", _fake_get)

    resp = await ra_mod.run_analyst(
        "stock_analyst",
        [{"role": "user", "content": "분석"}],
        target_ticker="005930",
    )
    system_blocks = ra_mod._captured["system"]
    assert not any(
        b.get("text", "").lstrip().startswith("## [5] 펀더멘털 데이터")
        for b in system_blocks
    )
    md = resp.metadata
    assert md["fundamental_failures"] == ["no_fundamental_data"]
    assert md["fundamental_ticker_used"] == "005930"
