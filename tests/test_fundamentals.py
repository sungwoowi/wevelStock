"""INFRA-FUNDAMENTAL-DATA-001 — collectors.fundamentals 단위 테스트.

대상:
- get_fundamentals — DB-first / yfinance fallback / 24h TTL / 3-tier fallback
- render_fundamental_data_md — markdown 표 풀세트 + null 안전 + YoY 5분기 미달

모든 yfinance 호출 mock. 실 API 호출 0.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from collectors import fundamentals as fm_mod
from collectors.fundamentals import (
    Fundamentals,
    get_fundamentals,
    persist_fundamentals_to_db,
    render_fundamental_data_md,
    reset_cache,
)
from connectors.yfinance.client import FundamentalNotAvailable
from core.db.connection import Database, reset_db


class _MockYFinance:
    """YFinanceClient mock — fetch_full async stub."""

    def __init__(
        self,
        full: dict[str, Any] | None = None,
        raise_full: Exception | None = None,
    ) -> None:
        self.full = full or self._default_full()
        self.raise_full = raise_full
        self.fetch_full_calls = 0

    @staticmethod
    def _default_full() -> dict[str, Any]:
        return {
            "ticker": "005930",
            "market": "KS",
            "yf_ticker": "005930.KS",
            "eps_ttm": 9512.0,
            "pe_ratio": 12.4,
            "roe": 0.142,
            "operating_margin": 0.187,
            "debt_to_equity": 45.3,
            "quarterly_revenue": [79.8e12, 75.2e12, 72.5e12, 67.4e12, 67.5e12],
            "quarterly_operating_income": [6.7e12, 6.4e12, 5.9e12, 5.2e12, 5.2e12],
            "quarterly_eps": [998.0, 935.0, 873.0, 781.0, 781.0],
            "quarter_labels": [
                "2026Q1", "2025Q4", "2025Q3", "2025Q2", "2025Q1",
            ],
            "annual_eps": [3650.0, 3100.0, 2700.0, 2200.0],
            "annual_labels": ["2025", "2024", "2023", "2022"],
        }

    async def fetch_full(
        self, ticker: str, market: str = "KS"
    ) -> dict[str, Any]:
        self.fetch_full_calls += 1
        if self.raise_full is not None:
            raise self.raise_full
        return {**self.full, "ticker": ticker, "market": market}


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    """tmp DB 격리 + fundamentals 모듈 캐시 리셋."""
    reset_db()
    reset_cache()
    db = Database(tmp_path / "test_fundamentals.sqlite")
    monkeypatch.setattr(fm_mod, "get_db", lambda: db)
    return db


@pytest.fixture(autouse=True)
def _reset_fund_cache() -> None:
    reset_cache()
    yield
    reset_cache()


# ---------------------------------------------------------------------------
# 1. yfinance fetch + DB upsert
# ---------------------------------------------------------------------------


async def test_yfinance_fetch_persists_to_db(
    isolated_db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_yf = _MockYFinance()

    f = await get_fundamentals(
        "005930",
        market="KS",
        yfinance_client=mock_yf,
        force_refresh=True,
        max_age_seconds=0,
    )

    assert f is not None
    assert mock_yf.fetch_full_calls == 1
    assert f.source == "yfinance"
    assert f.eps_ttm == 9512.0
    assert len(f.quarter_labels) == 5
    # 연간 EPS(CAN SLIM A) 보존
    assert f.annual_eps == [3650.0, 3100.0, 2700.0, 2200.0]
    assert f.annual_labels == ["2025", "2024", "2023", "2022"]
    # DB 적재 확인
    row = isolated_db.fetch_one(
        "SELECT ticker, eps_ttm FROM fundamentals WHERE ticker = ?",
        ("005930",),
    )
    assert row is not None
    assert row["eps_ttm"] == 9512.0
    # 연간 EPS DB round-trip (quarterly_data JSON)
    reloaded = fm_mod.load_fundamentals_from_db("005930")
    assert reloaded is not None
    assert reloaded.annual_eps == [3650.0, 3100.0, 2700.0, 2200.0]


# ---------------------------------------------------------------------------
# 2. DB-first — 24h 안이면 yfinance skip
# ---------------------------------------------------------------------------


async def test_db_first_fresh_skips_yfinance(isolated_db: Database) -> None:
    # DB pre-seed (방금 적재)
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pre = Fundamentals(
        ticker="005930", market="KS", fetched_at=0.0,
        fetched_at_iso=now_iso,
        eps_ttm=8000.0, pe_ratio=10.0, roe=0.13,
        operating_margin=0.18, debt_to_equity=40.0,
        quarterly_revenue=[70e12, 65e12],
        quarterly_operating_income=[5e12, 4e12],
        quarterly_eps=[800.0, 700.0],
        quarter_labels=["2026Q1", "2025Q4"],
        source="yfinance", fetched_db_iso=now_iso, stale_hours=0.0,
    )
    persist_fundamentals_to_db(pre)
    reset_cache()

    mock_yf = _MockYFinance()
    f = await get_fundamentals(
        "005930", market="KS",
        yfinance_client=mock_yf, max_age_seconds=0,
    )

    assert f is not None
    assert f.source == "db"
    assert mock_yf.fetch_full_calls == 0  # 24h 안 → skip
    assert f.eps_ttm == 8000.0


# ---------------------------------------------------------------------------
# 3. 24h 만료 → yfinance 재호출
# ---------------------------------------------------------------------------


async def test_stale_triggers_yfinance_refetch(
    isolated_db: Database,
) -> None:
    # DB pre-seed (30h 전 적재)
    old_iso = (
        datetime.now(timezone.utc) - timedelta(hours=30)
    ).isoformat(timespec="seconds")
    pre = Fundamentals(
        ticker="005930", market="KS", fetched_at=0.0,
        fetched_at_iso=old_iso,
        eps_ttm=8000.0, pe_ratio=10.0, roe=0.13,
        operating_margin=0.18, debt_to_equity=40.0,
        quarterly_revenue=[70e12], quarterly_operating_income=[5e12],
        quarterly_eps=[800.0], quarter_labels=["2026Q1"],
        source="yfinance", fetched_db_iso=old_iso, stale_hours=30.0,
    )
    persist_fundamentals_to_db(pre)
    reset_cache()

    mock_yf = _MockYFinance()
    f = await get_fundamentals(
        "005930", market="KS",
        yfinance_client=mock_yf, max_age_seconds=0,
    )

    assert f is not None
    assert f.source == "yfinance"  # 재호출
    assert mock_yf.fetch_full_calls == 1
    assert f.eps_ttm == 9512.0  # mock 값


# ---------------------------------------------------------------------------
# 4. yfinance 실패 + DB stale 7일 안 → stale_cache fallback
# ---------------------------------------------------------------------------


async def test_yfinance_fail_falls_back_to_stale_cache(
    isolated_db: Database,
) -> None:
    # DB pre-seed (5일 전 적재)
    old_iso = (
        datetime.now(timezone.utc) - timedelta(hours=120)
    ).isoformat(timespec="seconds")
    pre = Fundamentals(
        ticker="005930", market="KS", fetched_at=0.0,
        fetched_at_iso=old_iso,
        eps_ttm=7000.0, pe_ratio=9.0, roe=0.12,
        operating_margin=0.15, debt_to_equity=42.0,
        quarterly_revenue=[60e12], quarterly_operating_income=[4e12],
        quarterly_eps=[700.0], quarter_labels=["2026Q1"],
        source="yfinance", fetched_db_iso=old_iso, stale_hours=120.0,
    )
    persist_fundamentals_to_db(pre)
    reset_cache()

    mock_yf = _MockYFinance(raise_full=RuntimeError("yfinance 503"))
    f = await get_fundamentals(
        "005930", market="KS",
        yfinance_client=mock_yf, max_age_seconds=0,
    )

    assert f is not None
    assert f.source == "yfinance_stale"
    assert f.eps_ttm == 7000.0  # DB cache 그대로
    assert any("yfinance_fetch" in fl for fl in f.failures)


# ---------------------------------------------------------------------------
# 5. yfinance 실패 + DB 부재 → None
# ---------------------------------------------------------------------------


async def test_yfinance_fail_no_db_returns_none(
    isolated_db: Database,
) -> None:
    mock_yf = _MockYFinance(raise_full=RuntimeError("yfinance 503"))
    f = await get_fundamentals(
        "005930", market="KS",
        yfinance_client=mock_yf, max_age_seconds=0,
    )

    assert f is None


# ---------------------------------------------------------------------------
# 6. FundamentalNotAvailable (empty info) + DB 부재 → None
# ---------------------------------------------------------------------------


async def test_yfinance_empty_no_db_returns_none(
    isolated_db: Database,
) -> None:
    mock_yf = _MockYFinance(
        raise_full=FundamentalNotAvailable("empty info for INVALID.KS"),
    )
    f = await get_fundamentals(
        "INVALID", market="KS",
        yfinance_client=mock_yf, max_age_seconds=0,
    )
    assert f is None


# ---------------------------------------------------------------------------
# 7. render — markdown 표 풀세트 + YoY 자동
# ---------------------------------------------------------------------------


def test_render_md_full_structure() -> None:
    f = Fundamentals(
        ticker="005930", market="KS",
        fetched_at=0.0, fetched_at_iso="2026-05-20T18:00:00+00:00",
        eps_ttm=9512.0, pe_ratio=12.4, roe=0.142,
        operating_margin=0.187, debt_to_equity=45.3,
        quarterly_revenue=[79.8e12, 75.2e12, 72.5e12, 67.4e12, 67.5e12],
        quarterly_operating_income=[6.7e12, 6.4e12, 5.9e12, 5.2e12, 5.2e12],
        quarterly_eps=[998.0, 935.0, 873.0, 781.0, 781.0],
        quarter_labels=[
            "2026Q1", "2025Q4", "2025Q3", "2025Q2", "2025Q1",
        ],
        source="yfinance", fetched_db_iso="2026-05-20T18:00:00+00:00",
        stale_hours=0.5,
    )
    md = render_fundamental_data_md(f, name="삼성전자")

    # 모든 섹션
    assert "## [5] 펀더멘털 데이터 (INFRA-FUNDAMENTAL-DATA-001)" in md
    assert "### TTM 5 ratio (F2 입력)" in md
    assert "### 분기 실적 (F5 입력)" in md
    assert "### QoQ·YoY (F5 모멘텀 산출 base)" in md
    assert "### 본 분석가 사용 지침" in md
    # ticker + name
    assert "005930" in md
    assert "삼성전자" in md
    # TTM
    assert "EPS TTM" in md
    assert "ROE" in md
    assert "14.2%" in md  # ROE 0.142 → 14.2%
    # 분기
    assert "2026Q1" in md
    assert "2025Q4" in md
    # YoY 계산 (rev: 79.8 vs 67.5 → +18.2%)
    assert "YoY" in md
    assert "+18." in md  # 정확 값은 +18.2% 또는 +18.1%
    # 사용 지침
    assert "2 분기 연속 둔화 시 청산" in md
    # 출처 명시
    assert "yfinance" in md


# ---------------------------------------------------------------------------
# 8. render — null 케이스 안전 렌더
# ---------------------------------------------------------------------------


def test_render_md_handles_null_ratios() -> None:
    f = Fundamentals(
        ticker="005930", market="KS",
        fetched_at=0.0, fetched_at_iso="2026-05-20T18:00:00+00:00",
        eps_ttm=None, pe_ratio=None, roe=None,
        operating_margin=None, debt_to_equity=None,
        quarterly_revenue=[], quarterly_operating_income=[], quarterly_eps=[],
        quarter_labels=[],
        source="unknown", fetched_db_iso=None, stale_hours=0.0,
        failures=["yfinance_empty:test"],
    )
    md = render_fundamental_data_md(f)
    assert "N/A" in md
    assert "분기 데이터 없음" in md
    assert "yfinance_empty" in md


# ---------------------------------------------------------------------------
# 9. YoY 5분기 미달 시 N/A 명시
# ---------------------------------------------------------------------------


def test_render_md_yoy_na_when_under_5_quarters() -> None:
    f = Fundamentals(
        ticker="005930", market="KS",
        fetched_at=0.0, fetched_at_iso="2026-05-20T18:00:00+00:00",
        eps_ttm=9512.0, pe_ratio=12.4, roe=0.142,
        operating_margin=0.187, debt_to_equity=45.3,
        quarterly_revenue=[79.8e12, 75.2e12, 72.5e12, 67.4e12],  # 4분기만
        quarterly_operating_income=[6.7e12, 6.4e12, 5.9e12, 5.2e12],
        quarterly_eps=[998.0, 935.0, 873.0, 781.0],
        quarter_labels=["2026Q1", "2025Q4", "2025Q3", "2025Q2"],
        source="yfinance", fetched_db_iso="2026-05-20T18:00:00+00:00",
        stale_hours=0.5,
    )
    md = render_fundamental_data_md(f)
    # YoY 산출 불가 (5분기 미달)
    assert "YoY" in md
    assert "5분기 미달" in md
    # QoQ 는 산출 가능 (2분기 충분)
    assert "QoQ" in md
