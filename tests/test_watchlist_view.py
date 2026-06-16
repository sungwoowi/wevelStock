"""관심종목 funnel view 테스트 — 멤버십 ⋈ funnel_stage 조인 (신규 테이블 0)."""
from __future__ import annotations

import pytest

from collectors import universe_membership
from core import watchlist_view
from core.db.connection import Database, reset_db
from core.strategist import recommendation


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    db = Database(tmp_path / "test_watchlist.sqlite")
    for mod in (universe_membership, recommendation):
        monkeypatch.setattr(mod, "get_db", lambda: db)
    monkeypatch.setattr("core.outputs.get_db", lambda: db)
    return db


def _seed_members():
    universe_membership.persist_universe_membership(
        {"kospi": [
            {"ticker": "005930", "name": "삼성전자", "rank": 1, "change_pct": 1.2},
            {"ticker": "000660", "name": "SK하이닉스", "rank": 2, "change_pct": 2.0},
            {"ticker": "298040", "name": "효성중공업", "rank": 3, "change_pct": 6.1},
        ]},
        list_type="trade_value", date="2026-06-16",
    )
    universe_membership.persist_universe_membership(
        {"kosdaq": [{"ticker": "067310", "name": "하나마이크론", "rank": 1, "change_pct": 8.0}]},
        list_type="volume_bull", date="2026-06-16",
    )


_REC_BUY = """매수.
```yaml
recommendation_id: REC-20260616-09:35-000660-A
date: 2026-06-16
ticker: "000660"
display_name: "SK하이닉스"
track: A
verdict: "buy"
entry_price: 180000
stop_loss: 168000
confidence: 70
data:
  funnel_stage: "entering"
contract_version: "1.0"
```
"""


def _stage(track: dict, name: str) -> dict:
    return next(s for s in track["stages"] if s["stage"] == name)


def test_funnel_view_baskets_are_source_summary(isolated_db):
    _seed_members()
    view = watchlist_view.watchlist_funnel_view()
    baskets = {b["list_type"]: b for b in view["baskets"]}
    assert baskets["trade_value"]["count"] == 3  # 후보 바스킷 = 소스
    assert baskets["volume_bull"]["count"] == 1


def test_funnel_view_baskets_grouped_by_date(isolated_db):
    # 바스킷 펼침 — 멤버를 날짜별 그룹(최신 우선) + 종목 리스트.
    universe_membership.persist_universe_membership(
        {"kospi": [{"ticker": "005930", "name": "삼성전자", "rank": 1}]},
        list_type="trade_value", date="2026-06-10",
    )
    universe_membership.persist_universe_membership(
        {"kospi": [{"ticker": "000660", "name": "SK하이닉스", "rank": 2}]},
        list_type="trade_value", date="2026-06-16",
    )
    view = watchlist_view.watchlist_funnel_view()
    tv = next(b for b in view["baskets"] if b["list_type"] == "trade_value")
    assert tv["latest_date"] == "2026-06-16"           # 갱신 시 최신 날짜
    assert [d["date"] for d in tv["dates"]] == ["2026-06-16", "2026-06-10"]  # 최신 우선
    assert tv["dates"][0]["items"][0]["display_name"] == "SK하이닉스"


def test_basket_trade_value_sorted_by_trade_amount_desc(isolated_db):
    # KIS rank 는 시장별 로컬(충돌) → 실 거래대금 내림차순으로 정렬해야 맞음.
    universe_membership.persist_universe_membership(
        {"kospi": [
            {"ticker": "005930", "name": "삼성전자", "rank": 2, "trade_amount": 5_677_000_000_000},
            {"ticker": "000660", "name": "SK하이닉스", "rank": 1, "trade_amount": 7_940_000_000_000},
        ],
         "kosdaq": [{"ticker": "036930", "name": "주성엔지니어링", "rank": 1, "trade_amount": 508_000_000_000}]},
        list_type="trade_value", date="2026-06-16",
    )
    view = watchlist_view.watchlist_funnel_view()
    items = next(b for b in view["baskets"] if b["list_type"] == "trade_value")["dates"][0]["items"]
    assert [it["ticker"] for it in items] == ["000660", "005930", "036930"]  # 거래대금 내림차순(rank 무시)


def test_tracks_only_have_entering_watching(isolated_db):
    # 트랙(장기/단기)은 진입·매수대기만 (관심은 공용).
    _seed_members()
    view = watchlist_view.watchlist_funnel_view()
    for t in view["tracks"]:
        assert {s["stage"] for s in t["stages"]} == {"entering", "watching"}


def test_interest_is_shared_not_per_track(isolated_db):
    # 권고 없으면 후보 4종 전부 공용 관심 1곳 (트랙 중복 X).
    _seed_members()
    view = watchlist_view.watchlist_funnel_view()
    assert view["interest"]["count"] == 4
    for t in view["tracks"]:
        assert sum(s["count"] for s in t["stages"]) == 0  # 트랙엔 진입/대기 0


def test_buy_rec_moves_to_track_and_out_of_shared_interest(isolated_db):
    _seed_members()
    recommendation.persist_recommendation(recommendation.parse_recommendation(_REC_BUY))  # 000660 Track A buy
    view = watchlist_view.watchlist_funnel_view()
    tracks = {t["track"]: t for t in view["tracks"]}
    assert _stage(tracks["A"], "entering")["count"] == 1  # 장기 진입 승격
    assert view["interest"]["count"] == 3  # 공용 관심에서 빠짐(나머지 3)
    interest_tickers = {it["ticker"] for c in view["interest"]["concepts"] for it in c["items"]}
    assert "000660" not in interest_tickers


def test_interest_grouped_by_concept(isolated_db):
    # concept 컬럼으로 관심을 주도주/눌림/바닥 분류.
    universe_membership.persist_universe_membership(
        {"kospi": [
            {"ticker": "111111", "name": "주도주A", "rank": 1, "concept": "leader"},
            {"ticker": "222222", "name": "바닥B", "rank": 2, "concept": "base"},
        ]},
        list_type="trade_value", date="2026-06-16",
    )
    view = watchlist_view.watchlist_funnel_view()
    concepts = {c["concept"]: c for c in view["interest"]["concepts"]}
    assert concepts["leader"]["items"][0]["ticker"] == "111111"
    assert concepts["base"]["items"][0]["ticker"] == "222222"


def test_item_is_dual_when_in_both_baskets(isolated_db):
    # 거래대금 ∩ 거래량 양봉 교집합 → is_dual True.
    universe_membership.persist_universe_membership(
        {"kospi": [{"ticker": "005930", "name": "삼성전자", "rank": 1}]}, list_type="trade_value", date="2026-06-16")
    universe_membership.persist_universe_membership(
        {"kospi": [{"ticker": "005930", "name": "삼성전자", "rank": 3}]}, list_type="volume_bull", date="2026-06-16")
    view = watchlist_view.watchlist_funnel_view()
    item = next(it for c in view["interest"]["concepts"] for it in c["items"] if it["ticker"] == "005930")
    assert item["is_dual"] is True
    assert set(item["sources"]) == {"trade_value", "volume_bull"}


def test_funnel_view_empty_when_no_members(isolated_db):
    view = watchlist_view.watchlist_funnel_view()
    assert view["interest"]["count"] == 0
    for t in view["tracks"]:
        assert all(s["count"] == 0 for s in t["stages"])
