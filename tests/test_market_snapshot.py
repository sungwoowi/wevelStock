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

    # Default: DB 비어있음 — 새 DB-first 테스트가 override 하지 않으면 cold fetch.
    # 기존 테스트 (cold path / partial failure / render) 는 이 default 로 회귀 안전.
    monkeypatch.setattr(
        snap_mod.parts_store,
        "get_latest_parts_with_age",
        lambda pipeline_id: None,
    )
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
    # DB-first metadata 키
    assert "snapshot_source_map" in md
    assert "snapshot_db_run_ids" in md
    assert isinstance(md["snapshot_source_map"], dict)
    assert isinstance(md["snapshot_db_run_ids"], dict)


# ---------------------------------------------------------------------------
# 6. DB-first hybrid — 시간대 인식 임계 함수
# ---------------------------------------------------------------------------


from datetime import datetime  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

from collectors.snapshot import (  # noqa: E402
    _adapt_kr_indices_from_part,
    _adapt_kr_leading_from_part,
    _adapt_kr_supply_sectors_from_part,
    _adapt_overnight_from_part,
    kr_threshold_seconds,
    us_threshold_seconds,
)
from core.contracts.briefing_part import BriefingPart  # noqa: E402

_KST_TZ = ZoneInfo("Asia/Seoul")


def test_kr_threshold_weekday_intraday() -> None:
    """평일 14:00 — 마지막 12:30 cron 부터 1.5h."""
    # 2026-05-08 = Friday
    now = datetime(2026, 5, 8, 14, 0, 0, tzinfo=_KST_TZ)
    th = kr_threshold_seconds(now)
    # 12:30 ~ 14:00 = 5400s + 60 grace
    assert 5400 <= th <= 5500


def test_kr_threshold_weekday_post_close() -> None:
    """평일 22:00 — 마지막 14:30 cron 부터 7.5h."""
    now = datetime(2026, 5, 8, 22, 0, 0, tzinfo=_KST_TZ)
    th = kr_threshold_seconds(now)
    # 14:30 ~ 22:00 = 27000s + 60 grace
    assert 27000 <= th <= 27200


def test_kr_threshold_weekday_pre_open() -> None:
    """평일 09:00 — 09:30 cron 전 → 전 영업일 14:30."""
    # 2026-05-08 = Friday → 전일 = 2026-05-07 (Thursday) 14:30
    now = datetime(2026, 5, 8, 9, 0, 0, tzinfo=_KST_TZ)
    th = kr_threshold_seconds(now)
    # 5/7 14:30 ~ 5/8 09:00 = 18.5h = 66600s + 60
    assert 66500 <= th <= 66800


def test_kr_threshold_weekend_saturday() -> None:
    """토요일 11:00 — 금 14:30 부터 ~20.5h."""
    # 2026-05-09 = Saturday
    now = datetime(2026, 5, 9, 11, 0, 0, tzinfo=_KST_TZ)
    th = kr_threshold_seconds(now)
    # 5/8 14:30 ~ 5/9 11:00 = 73800s + 60
    assert 73700 <= th <= 74000


def test_kr_threshold_monday_pre_open() -> None:
    """월요일 09:00 — 09:30 cron 전 → 금 14:30 부터 ~66.5h."""
    # 2026-05-11 = Monday
    now = datetime(2026, 5, 11, 9, 0, 0, tzinfo=_KST_TZ)
    th = kr_threshold_seconds(now)
    # 5/8 14:30 ~ 5/11 09:00 = 66.5h = 239400s + 60
    assert 239300 <= th <= 239600


def test_us_threshold_weekday_intraday() -> None:
    """평일 14:00 — 당일 07:00 cron 부터 7h."""
    now = datetime(2026, 5, 8, 14, 0, 0, tzinfo=_KST_TZ)
    th = us_threshold_seconds(now)
    # 07:00 ~ 14:00 = 25200s + 60
    assert 25200 <= th <= 25400


def test_us_threshold_weekend_sunday() -> None:
    """일요일 09:00 — 금 07:00 부터 ~50h."""
    # 2026-05-10 = Sunday
    now = datetime(2026, 5, 10, 9, 0, 0, tzinfo=_KST_TZ)
    th = us_threshold_seconds(now)
    # 5/8 07:00 ~ 5/10 09:00 = 50h = 180000s + 60
    assert 179900 <= th <= 180200


# ---------------------------------------------------------------------------
# 7. DB-first hybrid — 어댑터 (data_json → snapshot dict)
# ---------------------------------------------------------------------------


def test_adapter_overnight_part_separates_fear_greed() -> None:
    """overnight part data_json → snapshot.overnight (평면) + fear_greed 분리."""
    part_data = {
        "overnight_us": {
            "nasdaq": {"price": 19873.21, "change_pct": -0.85},
            "vix": {"price": 18.42, "change_pct": 5.30},
            "fear_greed": {"score": 38.0, "rating_kr": "공포"},
        },
        "macro": {
            "dxy": {"price": 105.42, "change_pct": 0.20},
            "usdkrw": {"price": 1487.20, "change_pct": 0.32},
        },
        "night_futures": {"kospi200_cme_night": {}},  # snapshot 무관
    }
    overnight, fg = _adapt_overnight_from_part(part_data)
    # overnight 은 평면 + fear_greed 빠짐
    assert "fear_greed" not in overnight
    assert overnight["nasdaq"]["price"] == 19873.21
    assert overnight["vix"]["change_pct"] == 5.30
    # macro 합쳐짐
    assert overnight["dxy"]["price"] == 105.42
    assert overnight["usdkrw"]["price"] == 1487.20
    # fear_greed 분리
    assert fg["score"] == 38.0
    assert fg["rating_kr"] == "공포"


def test_adapter_market_overview_part_to_kr_indices() -> None:
    part_data = {"indices": _mock_kr_indices(), "fetched_at": "2026-05-08T14:32:00+09:00"}
    out = _adapt_kr_indices_from_part(part_data)
    assert out["kospi"]["value"] == 2521.40
    assert out["kosdaq"]["value"] == 718.20


def test_adapter_supply_sectors_splits_three_fields() -> None:
    part_data = {
        "supply_demand": {"kospi": {"individual_net_amount_m": 940771}},
        "futures_supply_demand": {"trade_date": "20260508", "foreign_net_amount_b": 445},
        "sectors": {"strong": [{"name": "KODEX 2차전지산업"}]},
    }
    sup, fut, sec = _adapt_kr_supply_sectors_from_part(part_data)
    assert sup["kospi"]["individual_net_amount_m"] == 940771
    assert fut["foreign_net_amount_b"] == 445
    assert sec["strong"][0]["name"] == "KODEX 2차전지산업"


def test_adapter_leading_stocks_part_to_kr_leading() -> None:
    part_data = {"leading_stocks": _mock_kr_leading()}
    out = _adapt_kr_leading_from_part(part_data)
    assert out["kospi"][0]["name"] == "HD현대중공업"


# ---------------------------------------------------------------------------
# 8. DB-first hybrid — build_market_snapshot 의 source_map / 부분 fetch
# ---------------------------------------------------------------------------


def _make_now_parts() -> list[BriefingPart]:
    return [
        BriefingPart(
            key="market_overview",
            label="시장개요",
            order=1,
            data={"indices": _mock_kr_indices()},
        ),
        BriefingPart(
            key="supply_sectors",
            label="수급+섹터",
            order=2,
            data={
                "supply_demand": _mock_kr_supply(),
                "futures_supply_demand": _mock_kr_futures_supply(),
                "sectors": _mock_kr_sectors(),
            },
        ),
        BriefingPart(
            key="leading_stocks",
            label="주도주",
            order=3,
            data={"leading_stocks": _mock_kr_leading()},
        ),
    ]


def _make_pre_parts() -> list[BriefingPart]:
    overnight = _mock_overnight()
    fg = _mock_fear_greed()
    overnight_us = {
        "nasdaq": overnight["nasdaq"],
        "sp500": overnight["sp500"],
        "sox": overnight["sox"],
        "vix": overnight["vix"],
        "fear_greed": fg,
    }
    macro = {k: overnight[k] for k in ("dxy", "usdkrw", "us_10y", "gold", "wti")}
    return [
        BriefingPart(
            key="overnight",
            label="간밤시황",
            order=1,
            data={
                "overnight_us": overnight_us,
                "macro": macro,
                "night_futures": {},
            },
        ),
    ]


def _patch_db(
    monkeypatch: pytest.MonkeyPatch,
    *,
    kr_age: float | None,
    us_age: float | None,
) -> None:
    """parts_store.get_latest_parts_with_age 를 그룹별 age 로 mock.

    age=None 이면 해당 파이프라인은 DB 부재.
    """
    now_parts = _make_now_parts()
    pre_parts = _make_pre_parts()

    def _stub(pipeline_id: str):
        if pipeline_id == "market_briefing_now" and kr_age is not None:
            return ("run-now-1", now_parts, kr_age)
        if pipeline_id == "market_briefing_pre" and us_age is not None:
            return ("run-pre-1", pre_parts, us_age)
        return None

    monkeypatch.setattr(snap_mod.parts_store, "get_latest_parts_with_age", _stub)


async def test_db_both_fresh_no_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """양쪽 DB fresh → 7 collector 호출 0회. source_map = both db."""
    _patch_db(monkeypatch, kr_age=600, us_age=3600)

    async def _boom(*args, **kwargs):
        raise AssertionError("cold fetch should NOT happen when DB is fresh")

    for fn in (
        "fetch_overnight", "fetch_fear_greed", "fetch_kr_indices",
        "fetch_kr_supply_demand", "fetch_kr_sectors",
        "fetch_kr_leading_stocks", "fetch_kr_futures_supply_demand",
    ):
        monkeypatch.setattr(snap_mod, fn, _boom)

    snap, hit = await build_market_snapshot()
    assert hit is False  # 인메모리 캐시는 X (DB hit 와 다름)
    assert snap.source_map == {"kr": "db", "us": "db"}
    assert snap.db_run_ids == {
        "market_briefing_now": "run-now-1",
        "market_briefing_pre": "run-pre-1",
    }
    assert snap.failures == []
    # DB 어댑터 결과 확인
    assert snap.kr_indices.get("kospi", {}).get("value") == 2521.40
    assert snap.overnight.get("usdkrw", {}).get("price") == 1487.20
    assert "fear_greed" not in snap.overnight  # 어댑터가 분리
    assert snap.fear_greed.get("score") == 38.0


async def test_db_kr_stale_us_fresh_partial_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """한국만 stale → kr 5 collector 호출, overnight/fg 0회."""
    # KR age 3일 → 임계 초과. US age 1h → fresh.
    _patch_db(monkeypatch, kr_age=86400 * 3, us_age=3600)

    calls: dict[str, int] = {}

    def _wrap(name: str, mock_fn):
        async def _f(*args, **kwargs):
            calls[name] = calls.get(name, 0) + 1
            return mock_fn()
        return _f

    monkeypatch.setattr(snap_mod, "fetch_overnight", _wrap("overnight", _mock_overnight))
    monkeypatch.setattr(snap_mod, "fetch_fear_greed", _wrap("fear_greed", _mock_fear_greed))
    monkeypatch.setattr(snap_mod, "fetch_kr_indices", _wrap("kr_indices", _mock_kr_indices))
    monkeypatch.setattr(snap_mod, "fetch_kr_supply_demand", _wrap("kr_supply", _mock_kr_supply))
    monkeypatch.setattr(snap_mod, "fetch_kr_sectors", _wrap("kr_sectors", _mock_kr_sectors))
    monkeypatch.setattr(snap_mod, "fetch_kr_leading_stocks", _wrap("kr_leading", _mock_kr_leading))
    monkeypatch.setattr(snap_mod, "fetch_kr_futures_supply_demand", _wrap("kr_futures_supply", _mock_kr_futures_supply))

    snap, _ = await build_market_snapshot()
    assert snap.source_map == {"kr": "fetch", "us": "db"}
    # KR 5 collector 호출, US 0 회
    assert calls.get("overnight", 0) == 0
    assert calls.get("fear_greed", 0) == 0
    assert calls.get("kr_indices") == 1
    assert calls.get("kr_supply") == 1
    assert calls.get("kr_sectors") == 1
    assert calls.get("kr_leading") == 1
    assert calls.get("kr_futures_supply") == 1
    # US 데이터는 DB 어댑터로 채워짐
    assert snap.fear_greed.get("score") == 38.0
    assert snap.db_run_ids == {"market_briefing_pre": "run-pre-1"}


async def test_db_us_stale_kr_fresh_partial_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """미국만 stale → overnight + fg 만 호출, KR 5 collector 0회."""
    _patch_db(monkeypatch, kr_age=600, us_age=86400 * 3)

    calls: dict[str, int] = {}

    async def _ov(*a, **k):
        calls["overnight"] = calls.get("overnight", 0) + 1
        return _mock_overnight()

    async def _fg(*a, **k):
        calls["fear_greed"] = calls.get("fear_greed", 0) + 1
        return _mock_fear_greed()

    async def _boom_kr(*a, **k):
        raise AssertionError("KR collector should NOT be called when KR is fresh in DB")

    monkeypatch.setattr(snap_mod, "fetch_overnight", _ov)
    monkeypatch.setattr(snap_mod, "fetch_fear_greed", _fg)
    monkeypatch.setattr(snap_mod, "fetch_kr_indices", _boom_kr)
    monkeypatch.setattr(snap_mod, "fetch_kr_supply_demand", _boom_kr)
    monkeypatch.setattr(snap_mod, "fetch_kr_sectors", _boom_kr)
    monkeypatch.setattr(snap_mod, "fetch_kr_leading_stocks", _boom_kr)
    monkeypatch.setattr(snap_mod, "fetch_kr_futures_supply_demand", _boom_kr)

    snap, _ = await build_market_snapshot()
    assert snap.source_map == {"kr": "db", "us": "fetch"}
    assert calls.get("overnight") == 1
    assert calls.get("fear_greed") == 1
    # KR 데이터는 DB 어댑터
    assert snap.kr_indices.get("kospi", {}).get("value") == 2521.40
    assert snap.db_run_ids == {"market_briefing_now": "run-now-1"}


async def test_db_both_missing_full_fetch() -> None:
    """DB 부재 (autouse default) → 7 collector 모두 호출 + source_map both fetch."""
    snap, _ = await build_market_snapshot()
    assert snap.source_map == {"kr": "fetch", "us": "fetch"}
    assert snap.db_run_ids == {}
    assert snap.failures == []
    assert snap.kr_indices.get("kospi", {}).get("value") == 2521.40


# ---------------------------------------------------------------------------
# 9. Render — 데이터 출처/시점 헤더
# ---------------------------------------------------------------------------


async def test_render_data_source_line_db_both(monkeypatch: pytest.MonkeyPatch) -> None:
    """DB hit 양쪽 → 헤더에 'DB (X 시간 전 적재)' 표기."""
    _patch_db(monkeypatch, kr_age=600, us_age=3600)

    async def _boom(*args, **kwargs):
        raise AssertionError("no fetch")

    for fn in (
        "fetch_overnight", "fetch_fear_greed", "fetch_kr_indices",
        "fetch_kr_supply_demand", "fetch_kr_sectors",
        "fetch_kr_leading_stocks", "fetch_kr_futures_supply_demand",
    ):
        monkeypatch.setattr(snap_mod, fn, _boom)

    snap, _ = await build_market_snapshot()
    md = render_snapshot_md(snap)

    assert "_데이터 출처:" in md
    assert "한국=DB" in md
    assert "미국=DB" in md
    # age formatting
    assert "10분 전 적재" in md  # 600s
    assert "1.0시간 전 적재" in md  # 3600s


async def test_render_data_source_line_full_fetch() -> None:
    """DB 부재 → '직접 수집 (방금)' 표기."""
    snap, _ = await build_market_snapshot()
    md = render_snapshot_md(snap)

    assert "_데이터 출처:" in md
    assert "한국=직접 수집 (방금)" in md
    assert "미국=직접 수집 (방금)" in md


async def test_render_data_source_line_mixed(monkeypatch: pytest.MonkeyPatch) -> None:
    """KR fetch + US DB 혼합.

    임계는 cron 발동 시각 기반이라 현재 시각을 freeze 해야 결정적. 평일 (화요일)
    KST 20:30 으로 고정 → KR threshold ~6h (kr_age=3일 stale → fetch),
    US threshold ~13.5h (us_age=12h fresh → DB).
    """
    from datetime import datetime as _DT

    frozen_now = _DT(2026, 5, 12, 20, 30, tzinfo=snap_mod._KST)

    class _FrozenDateTime(_DT):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is not None:
                return frozen_now.astimezone(tz)
            return frozen_now.replace(tzinfo=None)

    monkeypatch.setattr(snap_mod, "datetime", _FrozenDateTime)
    _patch_db(monkeypatch, kr_age=86400 * 3, us_age=43200)  # 12h us

    snap, _ = await build_market_snapshot()
    md = render_snapshot_md(snap)

    assert "한국=직접 수집 (방금)" in md
    assert "미국=DB" in md
    assert "12.0시간 전 적재" in md


def test_format_age_humanizes() -> None:
    from collectors.snapshot import _format_age

    assert _format_age(30) == "30초 전"
    assert _format_age(600) == "10분 전"
    assert _format_age(3600) == "1.0시간 전"
    assert _format_age(43200) == "12.0시간 전"
    assert _format_age(86400 * 2) == "2.0일 전"
