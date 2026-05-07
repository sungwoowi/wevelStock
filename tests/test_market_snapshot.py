"""단계 2 — 시장 스냅샷 자동 주입 단위 테스트.

대상:
- collectors.snapshot.build_market_snapshot — 7 collector 병렬 + 5분 캐시 + partial failure
- collectors.snapshot.render_snapshot_md — 정상/에러 dict 모두 안전
- core.knowledge.compose.build_pipeline_prompt — market_snapshot_md 블록 주입
- core.inference.run_analyst — metadata snapshot_* 3키 노출

모든 collector + LLM 호출 mock. 실 API 호출 0.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from collectors import snapshot as snap_mod
from collectors.snapshot import (
    MarketSnapshot,
    build_market_snapshot,
    render_snapshot_md,
    reset_cache,
)


# ---------------------------------------------------------------------------
# Mock collector returns (collect_kr_market 의 실 shape 모방)
# ---------------------------------------------------------------------------


def _mock_overnight() -> dict[str, Any]:
    return {
        "nasdaq": {"price": 19873.21, "previous_close": 20043.50, "change_pct": -0.85},
        "sp500": {"price": 5892.41, "previous_close": 5917.12, "change_pct": -0.42},
        "sox": {"price": 5012.33, "previous_close": 5073.20, "change_pct": -1.20},
        "vix": {"price": 18.42, "previous_close": 17.50, "change_pct": 5.30},
        "dxy": {"price": 105.42, "previous_close": 105.21, "change_pct": 0.20},
        "usdkrw": {"price": 1487.20, "previous_close": 1482.45, "change_pct": 0.32},
        "us_10y": {"price": 4.51, "previous_close": 4.46, "change_pct": 1.20},
        "gold": {"price": 2640.10, "previous_close": 2619.20, "change_pct": 0.80},
        "wti": {"price": 71.20, "previous_close": 71.56, "change_pct": -0.50},
    }


def _mock_fear_greed() -> dict[str, Any]:
    return {
        "score": 38.0,
        "rating": "fear",
        "rating_kr": "공포",
        "previous_close": 36.86,
        "change": 1.14,
        "change_pct": 3.10,
    }


def _mock_kr_indices() -> dict[str, Any]:
    return {
        "kospi": {"value": 2521.40, "change_pct": -0.55, "trade_amount": 12340000, "volume": 717859},
        "kosdaq": {"value": 718.20, "change_pct": 0.10, "trade_amount": 8230000, "volume": 1255886},
        "kospi200": {"value": 335.21, "change_pct": -0.45, "trade_amount": 0, "volume": 0},
        "fetched_at": "2026-05-08T14:32:00+09:00",
        "source": "kis",
    }


def _mock_kr_supply() -> dict[str, Any]:
    return {
        "kospi": {
            "individual_net_amount_m": 940771,
            "foreign_net_amount_m": -1455933,
            "institution_net_amount_m": 283792,
            "fin_invest_net_amount_m": 508920,
            "pension_net_amount_m": 35039,
        },
        "kosdaq": {
            "individual_net_amount_m": 128603,
            "foreign_net_amount_m": -42542,
            "institution_net_amount_m": -28700,
            "fin_invest_net_amount_m": -15000,
            "pension_net_amount_m": 8400,
        },
    }


def _mock_kr_sectors() -> dict[str, Any]:
    return {
        "all": [
            {"name": "KODEX 2차전지산업", "ticker": "305720", "change_pct": 2.02},
            {"name": "KODEX AI반도체", "ticker": "394670", "change_pct": 1.09},
            {"name": "KODEX 반도체", "ticker": "091160", "change_pct": 0.5},
        ],
        "strong": [
            {"name": "KODEX 2차전지산업", "ticker": "305720", "change_pct": 2.02},
            {"name": "KODEX AI반도체", "ticker": "394670", "change_pct": 1.09},
        ],
        "min_change_pct": 1.0,
    }


def _mock_kr_leading() -> dict[str, Any]:
    return {
        "kospi": [
            {"name": "HD현대중공업", "ticker": "329180", "change_pct": 3.45,
             "match": "meets_criteria", "cap_tier": "top20"},
            {"name": "삼성SDI", "ticker": "006400", "change_pct": 4.71,
             "match": "meets_criteria", "cap_tier": "top20"},
        ],
        "kosdaq": [
            {"name": "서진시스템", "ticker": "178320", "change_pct": 10.53,
             "match": "meets_criteria"},
        ],
        "stats": {"kospi_matched": 2, "kospi_fill": 0, "kosdaq_matched": 1, "kosdaq_fill": 0},
    }


def _mock_kr_futures_supply() -> dict[str, Any]:
    return {
        "trade_date": "20260508",
        "individual_net_amount_b": -41,
        "foreign_net_amount_b": 445,
        "institution_net_amount_b": -400,
        "fetched_at_krx": "2026.05.08 PM 15:30:00",
        "source": "krx",
    }


@pytest.fixture(autouse=True)
def _patch_collectors(monkeypatch: pytest.MonkeyPatch):
    """기본 happy-path: 7 collector 모두 정상 mock."""
    reset_cache()

    async def _ov() -> dict[str, Any]:
        return _mock_overnight()

    async def _fg() -> dict[str, Any]:
        return _mock_fear_greed()

    async def _idx(kis=None) -> dict[str, Any]:
        return _mock_kr_indices()

    async def _sup(kis=None) -> dict[str, Any]:
        return _mock_kr_supply()

    async def _sec(kis=None, **_kw) -> dict[str, Any]:
        return _mock_kr_sectors()

    async def _lead(kis=None, **_kw) -> dict[str, Any]:
        return _mock_kr_leading()

    async def _fut(krx=None) -> dict[str, Any]:
        return _mock_kr_futures_supply()

    monkeypatch.setattr(snap_mod, "fetch_overnight", _ov)
    monkeypatch.setattr(snap_mod, "fetch_fear_greed", _fg)
    monkeypatch.setattr(snap_mod, "fetch_kr_indices", _idx)
    monkeypatch.setattr(snap_mod, "fetch_kr_supply_demand", _sup)
    monkeypatch.setattr(snap_mod, "fetch_kr_sectors", _sec)
    monkeypatch.setattr(snap_mod, "fetch_kr_leading_stocks", _lead)
    monkeypatch.setattr(snap_mod, "fetch_kr_futures_supply_demand", _fut)

    # KIS/KRX context manager 도 mock — 진짜 토큰 발급 막음
    class _DummyKIS:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class _DummyKRX:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(snap_mod, "KISClient", _DummyKIS)
    monkeypatch.setattr(snap_mod, "KRXClient", _DummyKRX)
    yield


# ---------------------------------------------------------------------------
# 1. 캐시 동작
# ---------------------------------------------------------------------------


async def test_cold_call_then_cache_hit() -> None:
    snap1, hit1 = await build_market_snapshot(max_age_seconds=300)
    assert hit1 is False
    assert isinstance(snap1, MarketSnapshot)
    assert snap1.failures == []

    snap2, hit2 = await build_market_snapshot(max_age_seconds=300)
    assert hit2 is True
    assert snap2 is snap1  # 캐시 그대로 (객체 동일성)


async def test_ttl_expired_refetches(monkeypatch: pytest.MonkeyPatch) -> None:
    snap1, hit1 = await build_market_snapshot(max_age_seconds=60)
    assert hit1 is False

    # 70 초 후 시뮬레이션 — TTL 60 초 넘음
    base = snap_mod._LAST_AT
    monkeypatch.setattr(snap_mod.time, "time", lambda: base + 70)

    snap2, hit2 = await build_market_snapshot(max_age_seconds=60)
    assert hit2 is False
    assert snap2 is not snap1  # 새 객체


# ---------------------------------------------------------------------------
# 2. Partial failure
# ---------------------------------------------------------------------------


async def test_partial_failure_keeps_other_collectors(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _broken(kis=None, **_kw):
        raise RuntimeError("KIS rate limit exceeded")

    monkeypatch.setattr(snap_mod, "fetch_kr_sectors", _broken)

    snap, hit = await build_market_snapshot()
    assert hit is False
    assert "kr_sectors" in snap.failures
    assert "error" in snap.kr_sectors
    assert "rate limit" in snap.kr_sectors["error"]
    # 나머지는 정상
    assert snap.failures == ["kr_sectors"]
    assert "error" not in snap.overnight
    assert snap.kr_indices.get("kospi", {}).get("value") == 2521.40


# ---------------------------------------------------------------------------
# 3. Render 안전성
# ---------------------------------------------------------------------------


async def test_render_with_all_data() -> None:
    snap, _ = await build_market_snapshot()
    md = render_snapshot_md(snap)

    # 실 수치가 들어갔는지 spot check
    assert "1,487.20" in md or "1,487" in md  # USD/KRW
    assert "VIX" in md
    assert "공포" in md  # F&G rating_kr
    assert "KOSPI" in md
    assert "+9,408억" in md  # 개인 net amount (940,771 백만 → +9,408억)
    assert "강세 섹터" in md
    assert "주도주" in md
    assert "HD현대중공업" in md
    assert "[수집 실패" not in md  # 정상 케이스 — 실패 마커 없음


async def test_render_with_partial_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _broken_fg():
        raise ValueError("CNN blocked")

    monkeypatch.setattr(snap_mod, "fetch_fear_greed", _broken_fg)

    snap, _ = await build_market_snapshot()
    md = render_snapshot_md(snap)

    assert "[수집 실패" in md
    assert "CNN blocked" in md
    assert "fear_greed" in md  # 누락 collector 표시
    # 다른 섹션은 정상 렌더
    assert "KOSPI" in md


# ---------------------------------------------------------------------------
# 4. compose 통합
# ---------------------------------------------------------------------------


async def test_compose_includes_snapshot_block_before_rag() -> None:
    from core.knowledge.compose import build_pipeline_prompt

    bundle = await build_pipeline_prompt(
        context_id="test_ctx",
        persona_path=None,
        include_shared_canon=False,
        include_memory=False,
        market_snapshot_md="### USD/KRW 1,487 (+0.32%)",
        response_rules=None,
    )
    blocks = bundle.blocks
    snapshot_block_idx = next(
        i for i, b in enumerate(blocks)
        if b.get("text", "").startswith("## Market Snapshot")
    )
    # snapshot 블록은 cache_control 없음 (5분 갱신)
    assert "cache_control" not in blocks[snapshot_block_idx]
    assert "USD/KRW 1,487" in blocks[snapshot_block_idx]["text"]


async def test_compose_skips_snapshot_when_none() -> None:
    from core.knowledge.compose import build_pipeline_prompt

    bundle = await build_pipeline_prompt(
        context_id="test_ctx",
        persona_path=None,
        include_shared_canon=False,
        include_memory=False,
        market_snapshot_md=None,
        response_rules=None,
    )
    for b in bundle.blocks:
        assert not b.get("text", "").startswith("## Market Snapshot")


# ---------------------------------------------------------------------------
# 5. run_analyst 통합 — metadata 3키
# ---------------------------------------------------------------------------


async def test_run_analyst_metadata_includes_snapshot_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_market_snapshot + call_llm 둘 다 mock — 분석가 manifest 만 실 로드."""
    import sys

    import core.inference.run_analyst  # noqa: F401 — submodule import for sys.modules
    ra_mod = sys.modules["core.inference.run_analyst"]
    from core.inference.run_analyst import run_analyst

    # call_llm mock
    async def _fake_llm(*, system, messages, **kwargs):
        return {
            "text": "ok",
            "model": "mock-model",
            "tokens_in": 100,
            "tokens_out": 10,
            "cost_usd": 0.0,
            "raw": {"usage": {}, "provider": "mock"},
        }

    monkeypatch.setattr(ra_mod, "call_llm", _fake_llm)

    # build_market_snapshot 도 mock — 진짜 collector 호출 회피
    fake_snap = MarketSnapshot(
        fetched_at=time.time(),
        fetched_at_iso="2026-05-08T14:32:00+09:00",
        overnight={}, fear_greed={}, kr_indices={}, kr_supply={},
        kr_futures_supply={}, kr_sectors={}, kr_leading={}, failures=[],
    )

    async def _fake_snap_call():
        return fake_snap, False

    monkeypatch.setattr(ra_mod, "build_market_snapshot", _fake_snap_call)
    monkeypatch.setattr(ra_mod, "render_snapshot_md", lambda s: "## stub snapshot")

    resp = await run_analyst(
        "wealth_strategist",
        [{"role": "user", "content": "test"}],
    )
    md = resp.metadata
    assert "snapshot_age_seconds" in md
    assert "snapshot_fetch_seconds" in md
    assert "snapshot_cache_hit" in md
    assert md["snapshot_cache_hit"] is False
    assert isinstance(md["snapshot_age_seconds"], int)
    assert isinstance(md["snapshot_fetch_seconds"], (int, float))
