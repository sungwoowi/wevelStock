"""INFRA-CHART-DATA-001 — collectors.charts 단위 테스트.

대상:
- build_chart_data — DB-first / KIS fallback / 60s TTL 인메모리 캐시 / 3-tier fallback
- render_chart_data_md — markdown 표 풀세트 + 한국어 라벨 + 안전 렌더 (null 케이스)
- get_db_last_fetched_at / load_ohlcv_from_db / persist_ohlcv_to_db — DB helper

모든 KIS API 호출 mock. 실 API 호출 0. TESTING=1 환경 강제.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest

from collectors import charts as ch_mod
from collectors.charts import (
    ChartData,
    build_chart_data,
    persist_ohlcv_to_db,
    render_chart_data_md,
    reset_cache,
)
from core.db.connection import Database, reset_db


def _gen_bars(start: date, days: int, base_close: float = 80000.0) -> list[dict[str, Any]]:
    """결정론 OHLCV bars 생성. 종가는 base 기준 sin-wave 변동."""
    import math as _m

    bars: list[dict[str, Any]] = []
    d = start
    for i in range(days):
        # 영업일만 (월~금)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        close = base_close * (1 + 0.05 * _m.sin(i * 0.1))
        bars.append({
            "date": d.strftime("%Y-%m-%d"),
            "open": close * 0.99,
            "high": close * 1.02,
            "low": close * 0.98,
            "close": close,
            "volume": 12_000_000 + i * 1000,
            "value": int(close * (12_000_000 + i * 1000)),
            "change_rate": 0.5,
        })
        d += timedelta(days=1)
    return bars


class _MockKIS:
    """KIS client mock. async context manager + 두 메서드."""

    def __init__(
        self,
        daily_bars: list[dict[str, Any]] | None = None,
        current: dict[str, Any] | None = None,
        raise_chart: Exception | None = None,
        raise_snapshot: Exception | None = None,
    ) -> None:
        self.daily_bars = daily_bars or _gen_bars(date(2021, 1, 4), 300)
        self.current = current or {
            "ticker": "005930",
            "current_price": 82000,
            "open_price": 80500,
            "high_price": 82300,
            "low_price": 80200,
            "change_rate": 1.86,
            "volume_today": 15_234_567,
            "value_today": 1_248_123_456_000,
        }
        self.raise_chart = raise_chart
        self.raise_snapshot = raise_snapshot
        self.chart_calls = 0
        self.snapshot_calls = 0

    async def __aenter__(self) -> _MockKIS:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def get_daily_chart(
        self, ticker: str, *, period_days: int = 1825, adjust: bool = True
    ) -> list[dict[str, Any]]:
        self.chart_calls += 1
        if self.raise_chart is not None:
            raise self.raise_chart
        return self.daily_bars

    async def get_current_price(self, ticker: str) -> dict[str, Any]:
        self.snapshot_calls += 1
        if self.raise_snapshot is not None:
            raise self.raise_snapshot
        return self.current


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    """tmp DB 격리 + charts 모듈 캐시 리셋."""
    reset_db()
    reset_cache()
    db = Database(tmp_path / "test_charts.sqlite")
    monkeypatch.setattr(ch_mod, "get_db", lambda: db)
    return db


@pytest.fixture(autouse=True)
def _reset_charts_cache() -> None:
    reset_cache()
    yield
    reset_cache()


# ---------------------------------------------------------------------------
# 1. KIS fetch + DB upsert
# ---------------------------------------------------------------------------


async def test_fetch_kis_persists_to_db(
    isolated_db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_kis = _MockKIS()
    monkeypatch.setattr(ch_mod, "KISClient", lambda: mock_kis)

    chart, hit = await build_chart_data("005930", max_age_seconds=60)

    assert hit is False
    assert mock_kis.chart_calls == 1
    assert mock_kis.snapshot_calls == 1
    assert chart.ohlcv_count >= 200
    assert chart.source == "kis"
    # DB 적재 확인
    rows = isolated_db.fetch_all("SELECT COUNT(*) AS n FROM chart_ohlcv WHERE ticker = ?", ("005930",))
    assert rows[0]["n"] >= 200


# ---------------------------------------------------------------------------
# 2. DB-first — fresh 시 KIS 호출 skip (snapshot 만)
# ---------------------------------------------------------------------------


async def test_db_first_fresh_skips_kis_chart_fetch(
    isolated_db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    # DB pre-seed (방금 적재한 것으로)
    bars = _gen_bars(date(2025, 1, 6), 250)
    persist_ohlcv_to_db("005930", bars, adjusted=True)

    mock_kis = _MockKIS()
    monkeypatch.setattr(ch_mod, "KISClient", lambda: mock_kis)

    chart, _ = await build_chart_data("005930", max_age_seconds=60)
    assert chart.source == "db"
    assert mock_kis.chart_calls == 0  # KIS chart fetch skip
    assert mock_kis.snapshot_calls == 1  # snapshot 만 호출


# ---------------------------------------------------------------------------
# 3. 60s 인메모리 TTL — cache hit
# ---------------------------------------------------------------------------


async def test_cache_hit_within_ttl(
    isolated_db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_kis = _MockKIS()
    monkeypatch.setattr(ch_mod, "KISClient", lambda: mock_kis)

    chart1, hit1 = await build_chart_data("005930", max_age_seconds=60)
    chart2, hit2 = await build_chart_data("005930", max_age_seconds=60)

    assert hit1 is False
    assert hit2 is True
    assert chart2 is chart1
    assert mock_kis.snapshot_calls == 1  # 두 번째는 cache hit, KIS X


# ---------------------------------------------------------------------------
# 4. TTL 만료 시 재호출
# ---------------------------------------------------------------------------


async def test_cache_miss_after_ttl(
    isolated_db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_kis = _MockKIS()
    monkeypatch.setattr(ch_mod, "KISClient", lambda: mock_kis)

    chart1, _ = await build_chart_data("005930", max_age_seconds=60)
    # 70 초 후 시뮬레이션
    base = ch_mod._LAST_AT_BY_TICKER["005930"]
    monkeypatch.setattr(ch_mod.time, "time", lambda: base + 70)

    chart2, hit2 = await build_chart_data("005930", max_age_seconds=60)
    assert hit2 is False
    assert chart2 is not chart1


# ---------------------------------------------------------------------------
# 5. KIS fetch 실패 + DB stale 5일 안 → cache 사용
# ---------------------------------------------------------------------------


async def test_kis_error_falls_back_to_db_when_stale_within_5d(
    isolated_db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    # DB pre-seed (4일 전 적재)
    bars = _gen_bars(date(2025, 1, 6), 250)
    persist_ohlcv_to_db("005930", bars, adjusted=True)
    old_iso = (datetime.now(timezone.utc) - timedelta(hours=96)).isoformat(timespec="seconds")
    with isolated_db.connect() as conn:
        conn.execute(
            "UPDATE chart_ohlcv SET fetched_at = ? WHERE ticker = ?",
            (old_iso, "005930"),
        )

    mock_kis = _MockKIS(raise_chart=RuntimeError("KIS 503"))
    monkeypatch.setattr(ch_mod, "KISClient", lambda: mock_kis)

    chart, _ = await build_chart_data("005930", max_age_seconds=60)
    # 96h > _STALE_MAX_HOURS(168) 안이므로 stale_cache fallback
    assert chart.source == "stale_cache"
    assert any("kis_chart_fetch" in f for f in chart.failures)
    assert chart.ohlcv_count >= 200  # DB cache 그대로 사용


# ---------------------------------------------------------------------------
# 6. KIS fetch 실패 + DB 부재 → source unknown
# ---------------------------------------------------------------------------


async def test_kis_error_no_db_yields_unknown_source(
    isolated_db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_kis = _MockKIS(raise_chart=RuntimeError("KIS 503"))
    monkeypatch.setattr(ch_mod, "KISClient", lambda: mock_kis)

    chart, _ = await build_chart_data("005930", max_age_seconds=60)
    assert chart.source == "unknown"
    assert chart.ohlcv_count == 0
    assert any("kis_chart_fetch" in f for f in chart.failures)


# ---------------------------------------------------------------------------
# 7. snapshot KIS 실패 → snapshot 빈 dict + failures 적재 (chart 자체는 발행)
# ---------------------------------------------------------------------------


async def test_snapshot_kis_error_partial_release(
    isolated_db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_kis = _MockKIS(raise_snapshot=RuntimeError("snapshot 503"))
    monkeypatch.setattr(ch_mod, "KISClient", lambda: mock_kis)

    chart, _ = await build_chart_data("005930", max_age_seconds=60)
    assert chart.snapshot == {}
    assert any("kis_snapshot" in f for f in chart.failures)
    # historical fetch 는 성공
    assert chart.ohlcv_count >= 200


# ---------------------------------------------------------------------------
# 8. render — markdown 표 풀세트 구조
# ---------------------------------------------------------------------------


async def test_render_md_full_structure(
    isolated_db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_kis = _MockKIS()
    monkeypatch.setattr(ch_mod, "KISClient", lambda: mock_kis)

    chart, _ = await build_chart_data("005930", max_age_seconds=60)
    md = render_chart_data_md(chart, name="삼성전자")

    # 모든 섹션 헤더 존재
    assert "## [4] 차트 데이터 (INFRA-CHART-DATA-001)" in md
    assert "### 현재 시점 snapshot" in md
    assert "### 월봉 추세" in md
    assert "### 주봉 추세" in md
    assert "### 일봉 추세" in md
    assert "### MACD (12-26-9, daily)" in md
    assert "### 거래량 패턴" in md
    assert "### 52주 고저" in md
    # 한국어 라벨
    assert "월봉 7MA" in md
    assert "월봉 20MA" in md
    assert "주봉 10MA" in md
    assert "주봉 60MA" in md
    assert "일봉 4MA" in md
    assert "일봉 120MA" in md
    # 출처 명시
    assert "Ticker: 005930" in md or "**Ticker**: 005930" in md
    assert "삼성전자" in md
    assert "수정주가 기준" in md


# ---------------------------------------------------------------------------
# 9. render — null 케이스 안전 렌더
# ---------------------------------------------------------------------------


async def test_render_md_handles_null_indicators() -> None:
    chart = ChartData(
        ticker="005930",
        fetched_at=0.0,
        fetched_at_iso="2026-05-20T20:00:00+09:00",
        snapshot={},
        indicators={"reasons": ["ohlcv 부재"]},
        ohlcv_count=0,
        source="unknown",
        db_last_date=None,
        stale_hours=0.0,
        failures=["kis_chart_fetch:RuntimeError"],
    )
    md = render_chart_data_md(chart)
    # 크래시 없이 렌더 + null 표기
    assert "null" in md
    assert "출처**: unknown" in md or "출처: unknown" in md
    assert "kis_chart_fetch" in md


# ---------------------------------------------------------------------------
# 10. snapshot 7 필드 모두 표에 포함
# ---------------------------------------------------------------------------


async def test_snapshot_7_fields_in_render(
    isolated_db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_kis = _MockKIS()
    monkeypatch.setattr(ch_mod, "KISClient", lambda: mock_kis)

    chart, _ = await build_chart_data("005930", max_age_seconds=60)
    md = render_chart_data_md(chart)

    for field in (
        "current_price", "open_price", "high_price", "low_price",
        "change_rate", "volume_today", "value_today",
    ):
        assert field in md, f"snapshot field {field} missing"


# ---------------------------------------------------------------------------
# 11. 다른 ticker 캐시 격리
# ---------------------------------------------------------------------------


async def test_multiple_tickers_cached_separately(
    isolated_db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_kis = _MockKIS()
    monkeypatch.setattr(ch_mod, "KISClient", lambda: mock_kis)

    c1, _ = await build_chart_data("005930", max_age_seconds=60)
    c2, _ = await build_chart_data("000660", max_age_seconds=60)
    assert c1.ticker == "005930"
    assert c2.ticker == "000660"
    assert mock_kis.chart_calls == 2  # 두 ticker 모두 KIS 한 번씩
    # 같은 ticker 재호출은 cache hit
    c3, hit3 = await build_chart_data("005930", max_age_seconds=60)
    assert hit3 is True
    assert c3 is c1


# ---------------------------------------------------------------------------
# 12. failures 가 ChartData 에 propagate
# ---------------------------------------------------------------------------


async def test_failures_propagated_to_chartdata(
    isolated_db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_kis = _MockKIS(raise_snapshot=ValueError("rate limit"))
    monkeypatch.setattr(ch_mod, "KISClient", lambda: mock_kis)

    chart, _ = await build_chart_data("005930", max_age_seconds=60)
    assert isinstance(chart.failures, list)
    assert any("kis_snapshot" in f for f in chart.failures)
