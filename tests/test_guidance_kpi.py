"""GUIDANCE-ACCURACY-TRACKER-001 (RB-MS3) G2 — KPI 집계 view 테스트.

account_fills(청산된 가상매매) + team_outputs(권고 stop/RR) read → 실현수익률·벤치마크
초과(알파)·방향적중률·R/R 실현율·트랙분리. 복사 0(집계). 벤치마크 fetch 주입.
"""
from __future__ import annotations

import pytest

from core.account import paper_trading, portfolio
from core.account.sizing import reload_accounts_config
from core.db.connection import Database, reset_db
from core.guidance import kpi as kpi_mod
from core.guidance.kpi import get_kpi_summary
from core.strategist import recommendation
from core.strategist.recommendation import parse_recommendation, persist_recommendation

REC_B = """매수.

```yaml
recommendation_id: REC-20260601-005930-B
date: 2026-06-01
ticker: "005930"
display_name: "삼성전자"
track: B
verdict: "buy"
entry_price: 100
target_price_1: 130
stop_loss: 90
risk_reward: 3.0
cited_scores: {buy_score: 7}
confidence: 70
reasons: ["타점"]
contract_version: "1.0"
```
"""


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    reload_accounts_config()
    db = Database(tmp_path / "test_kpi.sqlite")
    for mod in (paper_trading, portfolio, recommendation, kpi_mod):
        monkeypatch.setattr(mod, "get_db", lambda: db)
    monkeypatch.setattr("core.outputs.get_db", lambda: db)
    return db


def _open_and_close_position():
    """권고 영속 + 매수 100주@100 + 목표 매도 100주@130 (청산)."""
    persist_recommendation(parse_recommendation(REC_B))
    paper_trading.record_buy_fill(
        recommendation_id="REC-20260601-005930-B", account_id="kr_swing", ticker="005930",
        track="B", leg=1, limit_price=100.0, fill_price=100.0, value_krw=10_000.0,
        filled_date="2026-06-01", reason="entry",
    )
    paper_trading.record_sell_fill(
        recommendation_id="REC-20260601-005930-B", account_id="kr_swing", ticker="005930",
        track="B", leg=1, fill_price=130.0, shares=100.0, filled_date="2026-06-11",
        reason="target_1",
    )


def test_kpi_summary_realized_return_and_alpha(isolated_db):
    _open_and_close_position()
    summary = get_kpi_summary(
        track="B", period_days=90, as_of="2026-06-12",
        benchmark_fetch=lambda sym, s, e: (100.0, 110.0),  # 벤치마크 +10%
    )
    assert summary["closed_count"] == 1
    assert summary["realized_return_avg_pct"] == pytest.approx(30.0)   # (130-100)/100
    assert summary["benchmark_return_avg_pct"] == pytest.approx(10.0)
    assert summary["alpha_avg_pct"] == pytest.approx(20.0)             # 30 - 10
    assert summary["win_rate_pct"] == pytest.approx(100.0)


def test_kpi_rr_realization(isolated_db):
    _open_and_close_position()
    summary = get_kpi_summary(track="B", period_days=90, as_of="2026-06-12",
                              benchmark_fetch=lambda *a: None)
    # 실현 R/R = (130-100)/(100-90)=3.0, 권고 R/R=3.0 → 100%
    assert summary["rr_realization_avg_pct"] == pytest.approx(100.0)


def test_kpi_holding_days(isolated_db):
    _open_and_close_position()
    rec = get_kpi_summary(track="B", period_days=90, as_of="2026-06-12",
                          benchmark_fetch=lambda *a: None)["records"][0]
    assert rec["holding_days"] == 10  # 06-01 → 06-11


def test_kpi_excludes_open_position(isolated_db):
    # 매수만 (미청산) → 채점 대상 아님
    persist_recommendation(parse_recommendation(REC_B))
    paper_trading.record_buy_fill(
        recommendation_id="REC-20260601-005930-B", account_id="kr_swing", ticker="005930",
        track="B", leg=1, limit_price=100.0, fill_price=100.0, value_krw=10_000.0,
        filled_date="2026-06-01", reason="entry",
    )
    summary = get_kpi_summary(track="B", period_days=90, as_of="2026-06-12", benchmark_fetch=lambda *a: None)
    assert summary["closed_count"] == 0


def test_kpi_benchmark_none_excluded_from_alpha(isolated_db):
    # 벤치마크 데이터 부재 → alpha 집계서 제외(추정 X), 실현수익률은 유지
    _open_and_close_position()
    summary = get_kpi_summary(track="B", period_days=90, as_of="2026-06-12", benchmark_fetch=lambda *a: None)
    assert summary["closed_count"] == 1
    assert summary["realized_return_avg_pct"] == pytest.approx(30.0)
    assert summary["alpha_avg_pct"] is None


def test_kpi_period_filter_excludes_old(isolated_db):
    _open_and_close_position()  # exit 2026-06-11
    summary = get_kpi_summary(track="B", period_days=5, as_of="2026-06-30", benchmark_fetch=lambda *a: None)
    assert summary["closed_count"] == 0  # 청산일이 30-5=25 이전(06-11) → 제외


def test_kpi_track_split(isolated_db):
    _open_and_close_position()  # Track B
    all_summary = get_kpi_summary(track=None, period_days=90, as_of="2026-06-12", benchmark_fetch=lambda *a: None)
    assert all_summary["closed_count"] == 1
    assert all_summary["by_track"]["B"]["closed_count"] == 1
    assert all_summary["by_track"]["A"]["closed_count"] == 0


def test_kpi_account_scope(isolated_db):
    # 계좌별 필터 (PAPER-DESK-UX-001 계좌 상세) — kr_swing 에서 청산
    _open_and_close_position()
    mine = get_kpi_summary(account_id="kr_swing", period_days=90, as_of="2026-06-12",
                           benchmark_fetch=lambda *a: None)
    assert mine["account_id"] == "kr_swing"
    assert mine["closed_count"] == 1
    assert mine["realized_return_avg_pct"] == pytest.approx(30.0)
    assert mine["records"][0]["account_id"] == "kr_swing"
    other = get_kpi_summary(account_id="kr_long", period_days=90, as_of="2026-06-12",
                            benchmark_fetch=lambda *a: None)
    assert other["closed_count"] == 0
