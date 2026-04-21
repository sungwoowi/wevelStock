"""Smoke test for morning_pre pipeline.

Verifies:
- manifest.yaml is discoverable and parsed
- All 8 stage modules are importable
- All stage classes inherit Stage
- PipelineRunner can execute end-to-end with mocked LLM + RSS + yfinance
"""
from __future__ import annotations

import importlib
from unittest.mock import AsyncMock, patch

import pytest

from pipelines._base import PipelineRunner, Stage
from pipelines._registry import get_pipeline


EXPECTED_STAGES = [
    "collect_overnight_us",
    "collect_night_futures",
    "collect_news",
    "load_positions",
    "check_principles",
    "analyze",
    "persist",
    "notify",
]


def test_manifest_loaded() -> None:
    manifest = get_pipeline("morning_pre")
    assert manifest is not None, "morning_pre not discovered by registry"
    assert manifest.status == "active"
    assert len(manifest.stages) == len(EXPECTED_STAGES)
    ids = [s.id for s in manifest.stages]
    assert ids == EXPECTED_STAGES


def test_all_stages_importable() -> None:
    for stage_id in EXPECTED_STAGES:
        mod = importlib.import_module(f"pipelines.morning_pre.stages.{stage_id}")
        stage_classes = [
            obj for name, obj in vars(mod).items()
            if isinstance(obj, type) and issubclass(obj, Stage) and obj is not Stage
        ]
        assert stage_classes, f"No Stage subclass in {stage_id}"


@pytest.mark.asyncio
async def test_runner_executes_with_mocks() -> None:
    """End-to-end run with external IO mocked out."""
    manifest = get_pipeline("morning_pre")
    assert manifest is not None

    # Mock the LLM call — return a minimal valid JSON briefing.
    llm_response = {
        "content": """
        {
          "verdict": "neutral",
          "confidence": 60,
          "scenario": {
            "expected_open": "flat",
            "bias": "neutral",
            "confidence": 60,
            "narrative": "어제 대비 큰 변화 없음"
          },
          "news_impact": [],
          "sector_watch": {"bullish": [], "bearish": []},
          "positions_advice": [],
          "new_candidates": [],
          "reasons": ["r1", "r2", "r3"],
          "narrative": "smoke test"
        }
        """,
        "model": "mock",
        "cost_usd": 0.0,
    }

    overnight_mock = {
        "nasdaq":  {"symbol": "^IXIC", "price": 17500.0, "change_pct": 0.5},
        "sp500":   {"symbol": "^GSPC", "price": 5230.0, "change_pct": 0.3},
        "sox":     {"symbol": "^SOX",  "price": 4980.0, "change_pct": 1.8},
        "vix":     {"symbol": "^VIX",  "price": 15.2,   "change_pct": -2.0},
        "dxy":     {"symbol": "DX-Y.NYB", "price": 103.4, "change_pct": 0.1},
        "us_10y":  {"symbol": "^TNX",  "price": 4.18, "change_pct": 0.2},
        "gold":    {"symbol": "GC=F",  "price": 2351.0, "change_pct": 0.4},
        "wti":     {"symbol": "CL=F",  "price": 78.3,  "change_pct": -0.1},
    }
    futures_mock = {
        "kospi200_cme_night": {
            "symbol": "KM=F", "price": 355.4, "change_pct": 0.6, "source": "KM=F",
        }
    }
    news_mock: list[dict] = []

    with (
        patch("pipelines.morning_pre.stages.collect_overnight_us.fetch_overnight",
              new=AsyncMock(return_value=overnight_mock)),
        patch("pipelines.morning_pre.stages.collect_night_futures.fetch_night_futures",
              new=AsyncMock(return_value=futures_mock)),
        patch("pipelines.morning_pre.stages.collect_news.fetch_news",
              new=AsyncMock(return_value=news_mock)),
        patch("pipelines.morning_pre.stages.analyze.call_llm",
              new=AsyncMock(return_value=llm_response)),
    ):
        runner = PipelineRunner()
        result = await runner.run(manifest, run_id="smoke-test-1")

    assert result.ok, f"Pipeline errored: {result.errors}"
    assert set(result.stages.keys()) == set(EXPECTED_STAGES)

    # Core contracts
    assert result.stages["analyze"].verdict == "neutral"
    assert result.stages["analyze"].confidence == 60
    assert result.stages["persist"].status == "ok"
    assert result.stages["notify"].status == "ok"

    # notify should produce 3 parts
    parts = result.stages["notify"].data.get("parts") or []
    assert len(parts) == 3


def test_sanitize_new_candidates_strips_placeholder_tickers() -> None:
    from pipelines.morning_pre.stages.analyze import _sanitize_new_candidates

    parsed = {
        "new_candidates": [
            {"sector": "반도체장비", "ticker": "000000", "name": "원익IPS", "reason": "x"},
            {"sector": "AI반도체", "ticker": "------", "name": "한미반도체", "reason": "y"},
            {"sector": "방산", "ticker": "012450", "name": "한화에어로스페이스", "reason": "z"},
            {"sector": "?", "ticker": "00000", "name": "  ", "reason": "drop"},
            {"sector": "조선", "ticker": "  ", "name": "HD현대중공업", "reason": "blank ticker ok"},
        ]
    }
    _sanitize_new_candidates(parsed)
    cleaned = parsed["new_candidates"]

    assert len(cleaned) == 4  # 4번째는 name 비어 drop
    assert cleaned[0]["ticker"] == ""
    assert cleaned[1]["ticker"] == ""
    assert cleaned[2]["ticker"] == "012450"
    assert cleaned[3]["ticker"] == ""
    assert cleaned[0]["name"] == "원익IPS"
    assert cleaned[3]["name"] == "HD현대중공업"
