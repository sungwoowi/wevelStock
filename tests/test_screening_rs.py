"""SCREEN-RS-EXTENSION-001 — 종목 스크리닝 RS + 과열도 결정론 검증.

A. 순수 함수 (stock_rs_score / extension_score / screening_score) — 같은 입력 → 같은 출력 ±0 + 엣지.
B. rank_candidates orchestrator — 풀 정규화 랭킹 + 60일 부족 제외 + cutoff_date 재현.
"""
from __future__ import annotations

from datetime import date as _date
from datetime import timedelta

import pytest

from collectors.scoring import extension_score, screening_score, stock_rs_score


# ============================================================
# A. 순수 함수
# ============================================================


class TestStockRsScore:
    def test_median_is_neutral(self) -> None:
        # 중앙값 → 백분위 0.5 → 5.0
        assert stock_rs_score(5.0, [0.0, 5.0, 10.0]) == 5.0

    def test_strongest_is_top(self) -> None:
        # 풀 최강 (자신 포함) → 백분위 (2 + 0.5)/3 = 0.833 → 8.5
        assert stock_rs_score(10.0, [0.0, 5.0, 10.0]) == 8.5

    def test_weakest_is_bottom(self) -> None:
        # 풀 최약 → (0 + 0.5)/3 = 0.167 → 1.5
        assert stock_rs_score(0.0, [0.0, 5.0, 10.0]) == 1.5

    def test_single_pool_is_neutral(self) -> None:
        # 풀 1종목(=자신) → 5.0 (SPEC 엣지)
        assert stock_rs_score(7.0, [7.0]) == 5.0

    def test_empty_pool_is_neutral(self) -> None:
        assert stock_rs_score(7.0, []) == 5.0

    def test_determinism(self) -> None:
        pool = [3.0, -2.0, 8.5, 1.0, 12.0]
        assert stock_rs_score(8.5, pool) == stock_rs_score(8.5, pool)

    def test_clamp_range(self) -> None:
        v = stock_rs_score(100.0, [100.0, 0.0])
        assert 0.0 <= v <= 10.0


class TestExtensionScore:
    def test_at_ma_is_healthy(self) -> None:
        # price == ma20 → extension 0 → 10 - 0 = 10.0
        assert extension_score(100.0, 100.0, 0.05) == 10.0

    def test_above_ma_penalised(self) -> None:
        # 5% 위, ADR 5% → normalized 1.0 → 10 - 1 = 9.0
        assert extension_score(105.0, 100.0, 0.05, k=1.0) == 9.0

    def test_far_above_clamps_low(self) -> None:
        # 과대 이격 → 0 으로 clamp
        assert extension_score(200.0, 100.0, 0.05, k=1.0) == 0.0

    def test_below_ma_above_ten_clamps(self) -> None:
        # MA 아래 → 10 초과 → 10 clamp
        assert extension_score(95.0, 100.0, 0.05, k=1.0) == 10.0

    def test_ma20_none_returns_none(self) -> None:
        assert extension_score(100.0, None, 0.05) is None

    def test_adr_zero_neutral(self) -> None:
        assert extension_score(105.0, 100.0, 0.0) == 5.0

    def test_adr_none_neutral(self) -> None:
        assert extension_score(105.0, 100.0, None) == 5.0

    def test_k_scaling(self) -> None:
        # k 2배 → 페널티 2배: 5% 위/ADR 5% → norm 1.0 → 10 - 2*1 = 8.0
        assert extension_score(105.0, 100.0, 0.05, k=2.0) == 8.0

    def test_determinism(self) -> None:
        assert extension_score(108.0, 100.0, 0.04, k=1.0) == extension_score(
            108.0, 100.0, 0.04, k=1.0
        )


class TestScreeningScore:
    _W = {
        "strong_bull": {"w_rs": 0.30, "w_ext": 0.15},
        "sideways": {"w_rs": 0.15, "w_ext": 0.30},
    }

    def test_bull_emphasises_rs(self) -> None:
        # rs 8, ext 2, strong_bull(0.30/0.15) → (0.3*8 + 0.15*2)/0.45 = 6.0
        assert screening_score(8.0, 2.0, "strong_bull", self._W) == 6.0

    def test_sideways_emphasises_extension(self) -> None:
        # rs 8, ext 2, sideways(0.15/0.30) → (0.15*8 + 0.30*2)/0.45 = 4.0
        assert screening_score(8.0, 2.0, "sideways", self._W) == 4.0

    def test_unknown_regime_equal_weight(self) -> None:
        # 미정의 regime → 균등 (0.5/0.5) → (8+2)/2 = 5.0
        assert screening_score(8.0, 2.0, "??", self._W) == 5.0

    def test_none_regime_equal_weight(self) -> None:
        assert screening_score(8.0, 2.0, "", {}) == 5.0

    def test_zero_weight_guard(self) -> None:
        w = {"x": {"w_rs": 0.0, "w_ext": 0.0}}
        assert screening_score(8.0, 2.0, "x", w) == 5.0

    def test_determinism(self) -> None:
        assert screening_score(7.0, 3.0, "strong_bull", self._W) == screening_score(
            7.0, 3.0, "strong_bull", self._W
        )


# ============================================================
# B. rank_candidates orchestrator (DB-backed)
# ============================================================


def _bars(close_start: float, return_pct_60d: float, days: int = 80, *, spread: float = 0.0) -> list[dict]:
    """선형 합성 일봉. close[-60] = close_start, close[-1] = start*(1+ret%).

    spread > 0 이면 high/low 에 ±spread 비율 부여 (ADR 양수 확보).
    """
    end_close = close_start * (1 + return_pct_60d / 100)
    bars = []
    d = _date(2025, 1, 2)
    for i in range(days):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        if i < days - 60:
            close = close_start
        else:
            j = i - (days - 60)
            close = close_start + (end_close - close_start) * (j / 59)
        high = close * (1 + spread)
        low = close * (1 - spread)
        bars.append({
            "date": d.strftime("%Y-%m-%d"),
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1_000_000,
            "value": int(close * 1_000_000),
            "change_rate": 0.0,
        })
        d += timedelta(days=1)
    return bars


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from core.db.connection import Database, reset_db

    reset_db()
    db = Database(tmp_path / "test_screening.sqlite")
    from collectors import charts as ch_mod

    monkeypatch.setattr(ch_mod, "get_db", lambda: db)
    # config 캐시 초기화 (실 config/screening.yaml 사용)
    from collectors import screening as sc_mod

    sc_mod.reload_screening_config()
    return db


def test_rank_orders_by_screening_score(isolated_db) -> None:
    from collectors.charts import persist_ohlcv_to_db
    from collectors.screening import rank_candidates

    # 3 종목: C(+15%) > A(+5%) > B(-5%). spread 동일 → 과열도 비슷, rs 가 순위 좌우.
    persist_ohlcv_to_db("A", _bars(10_000, 5.0, spread=0.02), adjusted=True)
    persist_ohlcv_to_db("B", _bars(10_000, -5.0, spread=0.02), adjusted=True)
    persist_ohlcv_to_db("C", _bars(10_000, 15.0, spread=0.02), adjusted=True)

    result = rank_candidates(["A", "B", "C"], "moderate_bull")
    ranked = [r for r in result if r["rank"] is not None]
    assert len(ranked) == 3
    # rs 백분위: C 최강 → rank 1, B 최약 → rank 3
    by_ticker = {r["ticker"]: r for r in ranked}
    assert by_ticker["C"]["rank"] == 1
    assert by_ticker["B"]["rank"] == 3
    assert by_ticker["C"]["rs_score"] > by_ticker["B"]["rs_score"]
    # screening_score 내림차순
    scores = [r["screening_score"] for r in ranked]
    assert scores == sorted(scores, reverse=True)


def test_insufficient_data_excluded(isolated_db) -> None:
    from collectors.charts import persist_ohlcv_to_db
    from collectors.screening import rank_candidates

    persist_ohlcv_to_db("A", _bars(10_000, 5.0, spread=0.02), adjusted=True)
    persist_ohlcv_to_db("SHORT", _bars(10_000, 5.0, days=30, spread=0.02), adjusted=True)  # 60일 미만

    result = rank_candidates(["A", "SHORT"], "moderate_bull")
    by_ticker = {r["ticker"]: r for r in result}
    assert by_ticker["A"]["rank"] == 1
    assert by_ticker["SHORT"]["rank"] is None
    assert by_ticker["SHORT"]["rs_score"] is None
    assert "데이터 부족" in by_ticker["SHORT"]["reason"]


def test_cutoff_date_reproducible(isolated_db) -> None:
    from collectors.charts import persist_ohlcv_to_db
    from collectors.screening import rank_candidates

    persist_ohlcv_to_db("A", _bars(10_000, 5.0, days=120, spread=0.02), adjusted=True)
    persist_ohlcv_to_db("B", _bars(10_000, 20.0, days=120, spread=0.02), adjusted=True)

    # 같은 cutoff → 같은 결과 (결정론)
    cutoff = "2025-04-01"
    r1 = rank_candidates(["A", "B"], "moderate_bull", cutoff_date=cutoff)
    r2 = rank_candidates(["A", "B"], "moderate_bull", cutoff_date=cutoff)
    assert r1 == r2


def test_missing_ticker_excluded(isolated_db) -> None:
    from collectors.charts import persist_ohlcv_to_db
    from collectors.screening import rank_candidates

    persist_ohlcv_to_db("A", _bars(10_000, 5.0, spread=0.02), adjusted=True)
    result = rank_candidates(["A", "NOPE"], "moderate_bull")
    by_ticker = {r["ticker"]: r for r in result}
    assert by_ticker["A"]["rank"] == 1
    assert by_ticker["NOPE"]["rank"] is None
