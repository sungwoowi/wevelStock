"""섹터 다중 시간축 (ADVISOR-CORE-001 F2).

사용자 지적(2026-08-12): *"섹터가 60일 기준이라면 큰 흐름은 반영하지만 후행적이고,
시장이 변곡 턴하는 그 미묘함은 숙련된 인간의 직감·시장의 반응만큼을 캐치할 수 없다"*

실제 사례: 반도체가 60일 초과수익 -10.7% 라 "회피" 밴드인데, 그날 삼성전자는 20일선
하단에서 변곡하는 장대양봉이 나왔다. 60일 숫자는 아직 안 움직인다 — 구조적 후행.

→ **60일(추세) + 20일·5일(전환) + 당일(반응)** 을 같이 보고, 축 간 엇갈림에 이름을 붙인다.
외부 호출 0 — chart_ohlcv fixture 로 계산.
"""
from __future__ import annotations

import pytest

from collectors import sector_rs as srs
from core.db.connection import Database, reset_db


@pytest.fixture()
def db(tmp_path, monkeypatch):
    reset_db()
    d = Database(tmp_path / "tf.sqlite")
    monkeypatch.setattr(srs, "get_db", lambda: d)
    return d


def _series(db, ticker: str, closes: list[float]) -> None:
    """종가 시계열 주입 — 마지막이 최신."""
    rows = [
        (ticker, f"2026-{(5 + i // 28):02d}-{(i % 28) + 1:02d}", c, c, c, c, 1000,
         "2026-08-12T18:00:00")
        for i, c in enumerate(closes)
    ]
    db.executemany(
        "INSERT OR REPLACE INTO chart_ohlcv "
        "(ticker, date, open, high, low, close, volume, fetched_at) VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )


@pytest.fixture(autouse=True)
def _chart_from_db(db, monkeypatch):
    import pandas as pd

    def _load(ticker: str, limit: int = 100):
        rows = db.fetch_all(
            "SELECT date, close FROM chart_ohlcv WHERE ticker = ? ORDER BY date DESC LIMIT ?",
            (ticker, limit),
        )
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([{"date": r["date"], "close": r["close"]} for r in rows])
        return df.iloc[::-1].reset_index(drop=True)

    monkeypatch.setattr(srs, "load_ohlcv_from_db", _load)


def _flat_then(bench: float, sector_tail: list[float], bars: int = 61):
    """벤치마크는 평평, 섹터만 끝에서 움직이는 시계열 생성기."""
    head = [100.0] * (bars - len(sector_tail))
    return [bench] * bars, head + sector_tail


# --- 1. 다중 시간축 산출 -------------------------------------------------------


async def test_computes_1d_5d_20d_60d_excess(db) -> None:
    _series(db, "0001", [100.0] * 61)                 # 벤치마크 평평
    _series(db, "E1", [100.0] * 60 + [110.0])         # 마지막 날 +10%
    rows = await srs.compute_sector_rs([("E1", "테마")], market="KOSPI")
    r = rows[0]
    assert r.excess_1d == pytest.approx(10.0, abs=0.1)
    assert r.excess_5d == pytest.approx(10.0, abs=0.1)
    assert r.excess_20d == pytest.approx(10.0, abs=0.1)
    assert r.rs_ratio == pytest.approx(10.0, abs=0.1)   # 60일


async def test_short_history_yields_none_not_zero(db) -> None:
    """봉이 모자라면 None — 0(보합)으로 착각하면 안 된다."""
    _series(db, "0001", [100.0] * 61)
    _series(db, "E1", [100.0] * 3)
    rows = await srs.compute_sector_rs([("E1", "테마")], market="KOSPI")
    assert rows == [] or rows[0].excess_20d is None


# --- 2. 전환 감지 — 축 간 엇갈림에 이름을 붙인다 ------------------------------


def test_rebound_attempt_when_long_weak_but_short_strong() -> None:
    """60일 회피인데 5일·당일 강세 = 바닥에서 도는 중 (반도체 케이스)."""
    assert srs.turning_signal(excess_60d=-10.7, excess_5d=4.2, excess_1d=3.1) == "rebound_attempt"


def test_fatigue_when_long_strong_but_short_weak() -> None:
    """60일 주도주인데 최근 밀림 = 주도주 피로."""
    assert srs.turning_signal(excess_60d=27.4, excess_5d=-3.5, excess_1d=-2.0) == "fatigue"


def test_no_signal_when_aligned() -> None:
    assert srs.turning_signal(excess_60d=20.0, excess_5d=3.0, excess_1d=1.0) is None
    assert srs.turning_signal(excess_60d=-20.0, excess_5d=-3.0, excess_1d=-1.0) is None


def test_no_signal_on_weak_short_move() -> None:
    """잡음 방지 — 단기 움직임이 미미하면 전환으로 안 본다."""
    assert srs.turning_signal(excess_60d=-15.0, excess_5d=0.3, excess_1d=0.2) is None


def test_none_inputs_are_safe() -> None:
    assert srs.turning_signal(excess_60d=None, excess_5d=1.0, excess_1d=1.0) is None
    assert srs.turning_signal(excess_60d=-15.0, excess_5d=None, excess_1d=None) is None


# --- 3. 판세가 오늘 반응·전환을 읽는다 ----------------------------------------


def _sector_row(db, sector, ratio, ex1=None, ex5=None, ex20=None, market="KOSPI"):
    db.execute(
        "INSERT OR REPLACE INTO sector_rs_snapshot "
        "(date, market, sector, etf_ticker, rs_score, return_60d, kospi_return_60d, "
        " rs_ratio, excess_1d, excess_5d, excess_20d) VALUES (?,?,?,?,5.0,0,0,?,?,?,?)",
        ("2026-08-12", market, sector, "000000", ratio, ex1, ex5, ex20),
    )


def test_stance_surfaces_today_movers(db, monkeypatch) -> None:
    from core.signal import market_stance as ms

    monkeypatch.setattr(ms, "get_db", lambda: db)
    db.execute(
        "INSERT OR REPLACE INTO market_macro_snapshot (date, market, index_close) "
        "VALUES ('2026-08-12','KOSPI',100)"
    )
    _sector_row(db, "반도체", -10.7, ex1=3.1, ex5=4.2)
    _sector_row(db, "화장품", 27.4, ex1=-2.0, ex5=-3.5)
    b = ms.build_stance_facts("2026-08-12", "postclose").sectors
    assert [e.sector for e in b.today_strong] == ["반도체"]
    assert [e.sector for e in b.today_weak] == ["화장품"]


def test_stance_flags_turning_sectors(db, monkeypatch) -> None:
    """60일 회피 + 오늘 강세 = 전환 시도로 표시 (사용자가 원한 '변곡의 미묘함')."""
    from core.signal import market_stance as ms

    monkeypatch.setattr(ms, "get_db", lambda: db)
    db.execute(
        "INSERT OR REPLACE INTO market_macro_snapshot (date, market, index_close) "
        "VALUES ('2026-08-12','KOSPI',100)"
    )
    _sector_row(db, "반도체", -10.7, ex1=3.1, ex5=4.2)
    b = ms.build_stance_facts("2026-08-12", "postclose").sectors
    assert [e.sector for e in b.turning] == ["반도체"]
    assert b.turning[0].turning == "rebound_attempt"


def test_render_shows_today_and_turning(db, monkeypatch) -> None:
    from core.signal import market_stance as ms

    monkeypatch.setattr(ms, "get_db", lambda: db)
    db.execute(
        "INSERT OR REPLACE INTO market_macro_snapshot (date, market, index_close) "
        "VALUES ('2026-08-12','KOSPI',100)"
    )
    _sector_row(db, "반도체", -10.7, ex1=3.1, ex5=4.2)
    _sector_row(db, "화장품", 27.4, ex1=-2.0, ex5=-3.5)
    md = ms.render_stance_facts_md(ms.build_stance_facts("2026-08-12", "postclose"))
    assert "오늘" in md
    assert "반등 시도" in md or "전환" in md
    assert "반도체" in md


def test_render_omits_timeframe_block_when_absent(db, monkeypatch) -> None:
    """구 데이터(당일 축 없음)여도 렌더가 깨지지 않는다."""
    from core.signal import market_stance as ms

    monkeypatch.setattr(ms, "get_db", lambda: db)
    db.execute(
        "INSERT OR REPLACE INTO market_macro_snapshot (date, market, index_close) "
        "VALUES ('2026-08-12','KOSPI',100)"
    )
    _sector_row(db, "반도체", -10.7)
    md = ms.render_stance_facts_md(ms.build_stance_facts("2026-08-12", "postclose"))
    assert "반도체" in md
