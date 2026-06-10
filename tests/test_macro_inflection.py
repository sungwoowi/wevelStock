"""is_macro_inflection — 박종훈 frame 게이팅의 결정론 변곡점 판정.

변곡점 = (a) regime 전환 (직전 스냅샷 대비) or (b) Distribution Day 25일 카운트 ≥ 4.
케이스: 평상시 / regime 전환 / DD 임계 / 직전 행 부재(첫날) / 스냅샷 부재 / cutoff.
"""
from __future__ import annotations

import pytest

from collectors import market_macro as mm
from collectors.market_macro import MarketMacro, is_macro_inflection, upsert_market_macro
from core.db.connection import Database, reset_db


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    """temp DB + market_macro 모듈 get_db 패치."""
    reset_db()
    db = Database(tmp_path / "test_macro_inflection.sqlite")
    monkeypatch.setattr(mm, "get_db", lambda: db)
    return db


def _seed_row(
    date: str,
    *,
    market: str = "KOSPI",
    position: str = "above_both",
    trend: str = "uptrend",
    dd: int = 0,
) -> None:
    """regime 결정 필드만 의미 있는 macro 행 upsert.

    기본값 (above_both + uptrend + breadth 0.5 + slope 1.0) = strong_bull.
    downtrend + between = moderate_bear.
    """
    upsert_market_macro(
        MarketMacro(
            date=date,
            market=market,
            index_close=2700.0,
            ma_36m=2500.0, ma_60m=2400.0, position=position,
            ma_20d=2680.0, ma_60d=2650.0,
            ma20_slope_pct_5d=1.0, ma60_slope_pct_20d=0.5, trend=trend,
            advancing=500, declining=350, unchanged=100, breadth_ratio=0.5,
            is_distribution_day=False, change_pct=0.5, volume_change_pct=2.0,
            distribution_count_25d=dd,
        )
    )


def test_steady_state_not_inflection(isolated_db: Database) -> None:
    """같은 regime + DD<4 = 평상시."""
    _seed_row("2026-06-09")
    _seed_row("2026-06-10")
    flag, reason = is_macro_inflection()
    assert flag is False
    assert "평상시" in reason
    assert "strong_bull" in reason


def test_regime_transition_is_inflection(isolated_db: Database) -> None:
    """직전 strong_bull → 오늘 moderate_bear = 변곡점."""
    _seed_row("2026-06-09", position="above_both", trend="uptrend")
    _seed_row("2026-06-10", position="between", trend="downtrend")
    flag, reason = is_macro_inflection()
    assert flag is True
    assert "regime 전환" in reason
    assert "strong_bull" in reason and "moderate_bear" in reason


def test_distribution_days_threshold_is_inflection(isolated_db: Database) -> None:
    """regime 동일해도 DD ≥ 4 = 변곡점 (기관 분산 천장 경고)."""
    _seed_row("2026-06-09", dd=3)
    _seed_row("2026-06-10", dd=4)
    flag, reason = is_macro_inflection()
    assert flag is True
    assert "Distribution Day 4건" in reason


def test_first_day_without_prior_skips_regime_check(isolated_db: Database) -> None:
    """직전 행 부재(첫날) → regime 전환 판정 skip, DD 만 — 보수적 평상시."""
    _seed_row("2026-06-10", dd=1)
    flag, reason = is_macro_inflection()
    assert flag is False
    assert "평상시" in reason


def test_no_snapshot_is_steady_state(isolated_db: Database) -> None:
    """스냅샷 자체가 없으면 보수적으로 평상시."""
    flag, reason = is_macro_inflection()
    assert flag is False
    assert "스냅샷 없음" in reason


def test_cutoff_date_respected(isolated_db: Database) -> None:
    """date_str cutoff = 그 시점까지의 행만 본다 (백테스팅 친화)."""
    _seed_row("2026-06-08", position="above_both", trend="uptrend")
    _seed_row("2026-06-09", position="above_both", trend="uptrend")
    # 미래(최신) 행은 bear 전환이지만 cutoff 가 09 면 평상시
    _seed_row("2026-06-10", position="between", trend="downtrend")
    flag, _ = is_macro_inflection(date_str="2026-06-09")
    assert flag is False
    flag, reason = is_macro_inflection(date_str="2026-06-10")
    assert flag is True and "regime 전환" in reason


def test_markets_isolated(isolated_db: Database) -> None:
    """KOSDAQ 변곡점이 KOSPI 판정에 새지 않는다."""
    _seed_row("2026-06-09", market="KOSDAQ", trend="uptrend")
    _seed_row("2026-06-10", market="KOSDAQ", trend="downtrend", position="between")
    _seed_row("2026-06-09", market="KOSPI")
    _seed_row("2026-06-10", market="KOSPI")
    flag, _ = is_macro_inflection(market="KOSPI")
    assert flag is False
    flag, _ = is_macro_inflection(market="KOSDAQ")
    assert flag is True
