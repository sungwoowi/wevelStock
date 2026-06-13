"""PAPER-DESK-UX-001 (RB-MS5) — 데스크 read view 조립 테스트.

기존 테이블(account_fills·team_outputs) read → 회차내역(filled+pending)·매수대기·청산·체결일지.
신규 테이블 0 (재사용 가드 #11). 산정·체결은 desk 엔진 소유, 본 모듈은 read 만.
"""
from __future__ import annotations

import pytest

from core.account import desk_view, holdings, paper_trading, portfolio
from core.account.sizing import reload_accounts_config
from core.db.connection import Database, reset_db
from core.strategist import recommendation

REC_A = """매수.

```yaml
recommendation_id: REC-20260601-005930-A
date: 2026-06-01
ticker: "005930"
display_name: "삼성전자"
track: A
verdict: "buy"
entry_price: 100
target_price_1: 130
stop_loss: 90
risk_reward: 3.0
cited_scores: {s_score: 8}
confidence: 70
reasons: ["추세 정배열"]
contract_version: "1.0"
```
"""


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    reload_accounts_config()
    db = Database(tmp_path / "test_desk_view.sqlite")
    for mod in (desk_view, holdings, paper_trading, portfolio, recommendation):
        monkeypatch.setattr(mod, "get_db", lambda: db)
    monkeypatch.setattr("core.outputs.get_db", lambda: db)
    return db


def _open_two_tranches() -> None:
    """권고 영속 + 1·2차 매수(3차 계획 중 2차까지). kr_long(Track A)."""
    recommendation.persist_recommendation(recommendation.parse_recommendation(REC_A))
    paper_trading.record_buy_fill(
        recommendation_id="REC-20260601-005930-A", account_id="kr_long", ticker="005930",
        track="A", leg=1, limit_price=100.0, fill_price=100.0, value_krw=400_000.0,
        filled_date="2026-06-05", reason="entry",
    )
    paper_trading.record_buy_fill(
        recommendation_id="REC-20260601-005930-A", account_id="kr_long", ticker="005930",
        track="A", leg=2, limit_price=96.0, fill_price=96.0, value_krw=300_000.0,
        filled_date="2026-06-08", reason="add",
    )


def test_position_tranches_filled_and_pending(isolated_db):
    _open_two_tranches()
    tr = desk_view.get_position_tranches("kr_long", "005930")
    assert tr["stop_loss"] == pytest.approx(90.0)
    assert [f["leg"] for f in tr["filled"]] == [1, 2]
    # 원안 분할 3차(neutral_ratios 3단) 중 미체결 = 3차
    assert [p["leg"] for p in tr["pending"]] == [3]
    assert tr["pending"][0]["limit_price"] < 100.0  # entry→stop 보간(물타기 차단)


def test_account_pending_ladder_waiting(isolated_db):
    _open_two_tranches()
    pending = desk_view.get_account_pending("kr_long")
    legs = [(w["ticker"], w["leg"]) for w in pending["ladder_waiting"]]
    assert ("005930", 3) in legs
    assert pending["watching"] == []  # 관망(verdict≠buy) 권고 없음


def test_account_closed_and_recent_fills(isolated_db):
    _open_two_tranches()
    paper_trading.record_sell_fill(
        recommendation_id="REC-20260601-005930-A", account_id="kr_long", ticker="005930",
        track="A", leg=1, fill_price=130.0, shares=1000.0, filled_date="2026-06-11",
        reason="target_1",
    )
    closed = desk_view.get_account_closed("kr_long")
    assert len(closed) == 1
    assert closed[0]["reason"] == "target_1"
    assert closed[0]["realized_pnl_krw"] > 0

    fills = desk_view.recent_fills(limit=10)
    assert len(fills) == 3  # 매수 2 + 매도 1
    assert fills[0]["filled_date"] == "2026-06-11"  # 최신순


def test_active_recommendations_view(isolated_db):
    _open_two_tranches()
    recs = desk_view.active_recommendations_view()
    assert len(recs) == 1
    assert recs[0]["ticker"] == "005930"
    assert recs[0]["verdict"] == "buy"
    assert recs[0]["track"] == "A"
