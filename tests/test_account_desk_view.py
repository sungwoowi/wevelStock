"""PAPER-DESK-UX-001 (RB-MS5) — 데스크 read view 조립 테스트.

기존 테이블(account_fills·team_outputs) read → 회차내역(filled+pending)·매수대기·청산·체결일지.
신규 테이블 0 (재사용 가드 #11). 산정·체결은 desk 엔진 소유, 본 모듈은 read 만.
"""
from __future__ import annotations

import pytest

from collectors import universe_membership
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
    for mod in (desk_view, holdings, paper_trading, portfolio, recommendation, universe_membership):
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


def test_resolve_stock_name_priority(isolated_db):
    rsn = universe_membership.resolve_stock_name
    # ① 사람이 읽을 hint 그대로
    assert rsn("005930", "삼성전자") == "삼성전자"
    # ② hint 가 코드면 무시 → 정적 매핑
    assert rsn("005935", "005935") == "삼성전자우"
    assert rsn("000660", None) == "SK하이닉스"
    # ③ 멤버십 DB 종목명 (정적 매핑 밖)
    universe_membership.persist_universe_membership(
        {"kospi": [{"ticker": "298040", "name": "효성중공업", "rank": 1}]}, date="2026-06-13"
    )
    assert rsn("298040", None) == "효성중공업"
    # ④ 어디에도 없으면 최후 폴백 = 코드
    assert rsn("999999", None) == "999999"


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
    # 노출단 코드 차단 — 보유분 매수대기 사다리도 종목명을 실어야 (코드 폴백 금지)
    held = next(w for w in pending["ladder_waiting"] if w["ticker"] == "005930")
    assert held["display_name"] == "삼성전자"


def test_account_pending_resolves_code_only_display_name(isolated_db):
    # display_name 이 코드(000660)인 관망 권고 → 매수대기 노출 시 이름으로 해석돼야
    recommendation.persist_recommendation(recommendation.parse_recommendation(REC_WATCH))
    pending = desk_view.get_account_pending("kr_long")
    w = next(x for x in pending["watching"] if x["ticker"] == "000660")
    assert w["display_name"] == "SK하이닉스"  # 코드 노출 차단


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
    assert closed[0]["display_name"] == "삼성전자"  # 청산 내역 코드 노출 차단

    fills = desk_view.recent_fills(limit=10)
    assert len(fills) == 3  # 매수 2 + 매도 1
    assert fills[0]["filled_date"] == "2026-06-11"  # 최신순
    assert all(f["display_name"] == "삼성전자" for f in fills)  # 매매일지 코드 노출 차단


def test_holdings_carry_display_name(isolated_db):
    _open_two_tranches()
    hs = holdings.get_holdings("kr_long")
    assert hs and all(h["ticker"] == "005930" for h in hs)
    assert all(h["display_name"] == "삼성전자" for h in hs)  # 보유중 코드 노출 차단


def test_active_recommendations_view(isolated_db):
    _open_two_tranches()
    recs = desk_view.active_recommendations_view()
    assert len(recs) == 1
    assert recs[0]["ticker"] == "005930"
    assert recs[0]["verdict"] == "buy"
    assert recs[0]["track"] == "A"


# TRADE-PLAN-LIFECYCLE 2단계 UI — 단계 라벨·종목명·매수대기 노출
REC_WATCH = """관망.

```yaml
recommendation_id: REC-20260616-000660-A
date: 2026-06-16
ticker: "000660"
display_name: "000660"
track: A
verdict: "wait"
confidence: 40
reasons: ["과열 눌림 대기"]
data:
  funnel_stage: "watching"
  stage_reason: "점수 근접 + 진입 트리거 대기 — 매수대기 단계"
  waiting_entry: 92000
  alpha_posture:
    conditional_entry:
      trigger: "pullback"
      zone_basis: "눌림목 분할 (20일선·직전 스윙저점)"
      entry_zone:
        - {label: "20일선", price: 92000}
contract_version: "1.0"
```
"""


def test_active_recs_view_buy_is_entering_with_name_fallback(isolated_db):
    recommendation.persist_recommendation(recommendation.parse_recommendation(REC_A))
    r = desk_view.active_recommendations_view()[0]
    assert r["funnel_stage"] == "entering"        # verdict=buy 폴백
    assert r["display_name"] == "삼성전자"          # 이름 그대로


def test_active_recs_view_watching_surfaces_stage_name_entry(isolated_db):
    recommendation.persist_recommendation(recommendation.parse_recommendation(REC_WATCH))
    r = desk_view.active_recommendations_view()[0]
    assert r["funnel_stage"] == "watching"
    assert r["stage_reason"] and "매수대기" in r["stage_reason"]
    assert r["watching_entry"] == 92000
    assert r["watching_label"] == "눌림"
    assert r["display_name"] == "SK하이닉스"        # 코드(000660) → 이름 매핑(KR_TICKER_TO_NAME)


def test_active_recs_view_name_and_universe_date_from_membership(isolated_db):
    # 30종 매핑 밖 종목(298040) — 거래대금 상위 멤버십이 종목명·상위 일자를 제공.
    universe_membership.persist_universe_membership(
        {"kospi": [{"ticker": "298040", "name": "효성중공업", "rank": 2}]}, date="2026-06-13"
    )
    rec = recommendation.parse_recommendation(
        REC_A.replace('ticker: "005930"', 'ticker: "298040"')
        .replace('display_name: "삼성전자"', 'display_name: "298040"')
        .replace("REC-20260601-005930-A", "REC-20260601-298040-A")
    )
    recommendation.persist_recommendation(rec)
    r = desk_view.active_recommendations_view()[0]
    assert r["display_name"] == "효성중공업"        # 코드 → 멤버십 종목명
    assert r["universe_last_date"] == "2026-06-13"
    assert isinstance(r["universe_days_ago"], int)
