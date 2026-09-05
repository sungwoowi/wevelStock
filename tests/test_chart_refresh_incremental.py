"""chart_ohlcv 증분 갱신 + 보관 상한 (2026-08-15).

배경: 매일 종목당 1,825봉을 통째로 다시 받고 있었다. KIS 는 1콜당 ~100봉이라
종목당 19 페이징 × 1.1초 ≈ 22초, 200종이면 **73분**. 그래서 18:00 갱신이
19:15에야 끝나 18:00 판세·18:05 자동 권고가 갱신 중인 차트를 읽었다.

검증 무게중심:
  ① 증분 폭이 gap 을 **덮되** 과하지 않은가 (모자라면 구멍, 과하면 73분 회귀)
  ② 신규·장기 공백은 전체로 떨어지는가
  ③ 주 1회 전체 재적재가 살아 있는가 (수정주가 정합 — 증분만으론 과거가 틀어진다)
  ④ 보관 상한이 최신 봉을 안 건드리는가
"""
from __future__ import annotations

import os
from datetime import date

os.environ.setdefault("TESTING", "1")

import pytest

from collectors import charts
from core.db.connection import Database, reset_db


@pytest.fixture()
def db(tmp_path, monkeypatch):
    reset_db()
    d = Database(tmp_path / "charts.sqlite")
    monkeypatch.setattr(charts, "get_db", lambda: d)
    return d


CFG = {
    "full_period_days": 1825,
    "incremental_buffer_bars": 10,
    "min_incremental_bars": 12,
    "max_incremental_gap_days": 200,
    "full_refresh_weekday": 6,
    "retention_bars": 2600,
}

TODAY = date(2026, 8, 17)


# --- 1. 증분 폭 산정 ---------------------------------------------------------


def test_one_day_gap_requests_a_tiny_window():
    """하루치만 비었으면 최소 봉 수 — 1콜로 끝나는 게 이 작업의 전부다."""
    want = charts._incremental_period_days("2026-08-14", TODAY, CFG)
    assert want == CFG["min_incremental_bars"]
    assert want < 100        # KIS 1콜 = ~100봉 → 페이징 0회


def test_gap_is_covered_with_buffer():
    """30일 공백 → 거래일 환산 + 여유. 모자라면 구멍이 영구히 남는다."""
    want = charts._incremental_period_days("2026-07-18", TODAY, CFG)
    trading_days = int(30 * 5 / 7)
    assert want >= trading_days
    assert want == trading_days + CFG["incremental_buffer_bars"]


def test_long_gap_falls_back_to_full():
    """오래 비면 증분이 전체보다 비싸지지 않게 그냥 전체로."""
    assert charts._incremental_period_days("2025-01-02", TODAY, CFG) == 1825


def test_new_ticker_gets_full_history():
    """신규 종목은 보유 봉이 없다 → 백테스트·월봉 파동이 쓸 깊이를 처음부터 받는다."""
    assert charts._incremental_period_days(None, TODAY, CFG) == 1825


def test_same_day_rerun_still_requests_a_window():
    """당일 재실행도 0 이 아니라 최소 창 — 장중 정정 봉을 덮는다."""
    assert charts._incremental_period_days("2026-08-17", TODAY, CFG) == CFG["min_incremental_bars"]


def test_corrupt_date_falls_back_to_full_not_crash():
    assert charts._incremental_period_days("not-a-date", TODAY, CFG) == 1825


def test_incremental_never_exceeds_full():
    """어떤 gap 에서도 전체보다 크게 요청하지 않는다."""
    for iso in ("2026-08-16", "2026-06-01", "2026-02-01"):
        assert charts._incremental_period_days(iso, TODAY, CFG) <= 1825


# --- 2. 마지막 봉 조회 -------------------------------------------------------


def _bar(db, ticker, d, close=100.0):
    db.execute(
        "INSERT OR REPLACE INTO chart_ohlcv "
        "(ticker, date, open, high, low, close, volume, adjusted, fetched_at) "
        "VALUES (?,?,?,?,?,?,?,1,?)",
        (ticker, d, close, close, close, close, 1000, f"{d}T18:00:00+09:00"),
    )


def test_last_bar_dates_reads_all_in_one_pass(db):
    _bar(db, "005930", "2026-08-14")
    _bar(db, "005930", "2026-08-13")
    _bar(db, "000660", "2026-08-12")
    out = charts._last_bar_dates(db, ["005930", "000660", "999999"])
    assert out == {"005930": "2026-08-14", "000660": "2026-08-12"}


def test_ticker_without_bars_is_absent_not_none(db):
    """없는 종목은 키 자체가 없어야 한다 — None 이 섞이면 호출부가 0 처럼 다룬다."""
    _bar(db, "005930", "2026-08-14")
    assert "999999" not in charts._last_bar_dates(db, ["005930", "999999"])


# --- 3. 보관 상한 ------------------------------------------------------------


def test_retention_disabled_by_zero_is_noop(db):
    for i in range(1, 6):
        _bar(db, "005930", f"2026-08-{i:02d}")
    assert charts.prune_ohlcv_history(0)["enabled"] is False
    assert db.fetch_one("SELECT COUNT(*) n FROM chart_ohlcv")["n"] == 5


def test_retention_keeps_the_newest_bars(db):
    for i in range(1, 11):
        _bar(db, "005930", f"2026-08-{i:02d}", close=float(i))
    out = charts.prune_ohlcv_history(3)
    assert out["pruned"] == 7
    rows = db.fetch_all("SELECT date FROM chart_ohlcv ORDER BY date")
    assert [r["date"] for r in rows] == ["2026-08-08", "2026-08-09", "2026-08-10"]


def test_retention_leaves_short_history_alone(db):
    """보유가 상한보다 적으면 손대지 않는다 (기본값이 현재 보유보다 훨씬 커서 평소 no-op)."""
    for i in range(1, 4):
        _bar(db, "005930", f"2026-08-{i:02d}")
    assert charts.prune_ohlcv_history(2600)["pruned"] == 0
    assert db.fetch_one("SELECT COUNT(*) n FROM chart_ohlcv")["n"] == 3


def test_retention_is_per_ticker(db):
    for i in range(1, 8):
        _bar(db, "005930", f"2026-08-{i:02d}")
    _bar(db, "000660", "2026-08-01")
    charts.prune_ohlcv_history(3)
    n_a = db.fetch_one("SELECT COUNT(*) n FROM chart_ohlcv WHERE ticker='005930'")["n"]
    n_b = db.fetch_one("SELECT COUNT(*) n FROM chart_ohlcv WHERE ticker='000660'")["n"]
    assert (n_a, n_b) == (3, 1)


# --- 4. 주 1회 전체 재적재 (수정주가 정합) -----------------------------------


def test_sunday_triggers_full_refresh():
    """증분만 돌리면 액면분할 뒤 과거 수정주가가 조용히 틀린 채 남는다."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from server.schedulers.jobs.charts import _should_run_full

    sunday = datetime(2026, 8, 16, 18, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    assert sunday.weekday() == 6
    assert _should_run_full(sunday) is True


def test_weekday_stays_incremental():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from server.schedulers.jobs.charts import _should_run_full

    monday = datetime(2026, 8, 17, 18, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    assert monday.weekday() == 0
    assert _should_run_full(monday) is False


def test_full_refresh_day_is_configurable():
    from collectors.screening import get_chart_refresh_config

    cfg = get_chart_refresh_config()
    assert 0 <= cfg["full_refresh_weekday"] <= 6
    assert cfg["full_period_days"] >= 1825      # 백테스트·월봉 파동이 소비하는 깊이


def test_cron_includes_the_full_refresh_day():
    """전체 재적재 요일이 cron 에서 빠지면 수정주가 정합이 영원히 안 돈다."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from collectors.screening import get_chart_refresh_config
    from server.schedulers.jobs import register_infra_jobs

    sched = AsyncIOScheduler(timezone="Asia/Seoul")
    register_infra_jobs(sched)
    job = sched.get_job("infra::chart_ohlcv_refresh")
    assert job is not None
    dow = str(next(f for f in job.trigger.fields if f.name == "day_of_week"))
    full_day = int(get_chart_refresh_config()["full_refresh_weekday"])
    # APScheduler 는 월=0…일=6 을 mon…sun 으로 표기
    assert ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][full_day] in dow
