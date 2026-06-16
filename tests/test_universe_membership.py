"""거래대금 상위 멤버십 영속/조회 테스트 (TRADE-PLAN-LIFECYCLE 후속).

종목명 소스(get_stock_name) + "며칠 전 상위" 추적(last_universe_date/days_since)을 검증.
"""
from __future__ import annotations

import pytest

from collectors import universe_membership as um
from core.db.connection import Database, reset_db


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    db = Database(tmp_path / "test_universe.sqlite")
    monkeypatch.setattr(um, "get_db", lambda: db)
    return db


_LEADING = {
    "kospi": [
        {"ticker": "005930", "name": "삼성전자", "rank": 1, "trade_amount": 9_000_000, "change_pct": 1.2},
        {"ticker": "298040", "name": "효성중공업", "rank": 2, "trade_amount": 5_000_000, "change_pct": 6.1},
    ],
    "kosdaq": [
        {"ticker": "067310", "name": "하나마이크론", "rank": 1, "trade_amount": 3_000_000, "change_pct": 8.0},
    ],
}


def test_persist_writes_all_groups(isolated_db):
    n = um.persist_universe_membership(_LEADING, date="2026-06-16")
    assert n == 3
    assert um.get_stock_name("005930") == "삼성전자"
    assert um.get_stock_name("067310") == "하나마이크론"


def test_persist_is_idempotent_per_date(isolated_db):
    um.persist_universe_membership(_LEADING, date="2026-06-16")
    um.persist_universe_membership(_LEADING, date="2026-06-16")  # 같은 날 재호출(cadence) → 행 중복 X
    rows = isolated_db.fetch_all("SELECT COUNT(*) AS c FROM universe_membership")
    assert rows[0]["c"] == 3


def test_get_stock_name_returns_latest(isolated_db):
    um.persist_universe_membership(_LEADING, date="2026-06-10")
    # 이름이 바뀐(또는 갱신된) 최신 일자가 우선.
    um.persist_universe_membership(
        {"kospi": [{"ticker": "005930", "name": "삼성전자우선", "rank": 3}]}, date="2026-06-16"
    )
    assert um.get_stock_name("005930") == "삼성전자우선"


def test_get_stock_name_missing_is_none(isolated_db):
    assert um.get_stock_name("999999") is None
    assert um.get_stock_name("") is None


def test_last_universe_date_and_days_since(isolated_db):
    um.persist_universe_membership(_LEADING, date="2026-06-13")
    assert um.last_universe_date("298040") == "2026-06-13"
    assert um.days_since_universe("298040", as_of="2026-06-16") == 3
    assert um.days_since_universe("298040", as_of="2026-06-13") == 0


def test_days_since_missing_is_none(isolated_db):
    assert um.last_universe_date("999999") is None
    assert um.days_since_universe("999999", as_of="2026-06-16") is None


def test_persist_skips_blank_ticker(isolated_db):
    n = um.persist_universe_membership({"kospi": [{"ticker": "", "name": "공백"}]}, date="2026-06-16")
    assert n == 0


def test_persist_non_dict_is_zero(isolated_db):
    assert um.persist_universe_membership(None) == 0  # type: ignore[arg-type]


def test_list_type_separates_same_ticker_same_day(isolated_db):
    # 같은 종목이 거래대금·거래량양봉 두 리스트에 동시 → list_type 으로 분리 저장(2행).
    um.persist_universe_membership(
        {"kospi": [{"ticker": "005930", "name": "삼성전자", "rank": 1}]},
        list_type="trade_value", date="2026-06-16",
    )
    um.persist_universe_membership(
        {"kospi": [{"ticker": "005930", "name": "삼성전자", "rank": 4}]},
        list_type="volume_bull", date="2026-06-16",
    )
    rows = isolated_db.fetch_all("SELECT COUNT(*) AS c FROM universe_membership")
    assert rows[0]["c"] == 2


def test_get_list_members_returns_latest_by_rank(isolated_db):
    um.persist_universe_membership(
        {"kospi": [{"ticker": "298040", "name": "효성중공업", "rank": 2}],
         "kosdaq": [{"ticker": "067310", "name": "하나마이크론", "rank": 1}]},
        list_type="volume_bull", date="2026-06-16",
    )
    # 다른 리스트(거래대금)는 섞이지 않아야.
    um.persist_universe_membership(
        {"kospi": [{"ticker": "005930", "name": "삼성전자", "rank": 1}]},
        list_type="trade_value", date="2026-06-16",
    )
    members = um.get_list_members("volume_bull")
    tickers = [m["ticker"] for m in members]
    assert tickers == ["067310", "298040"]  # rank 순(1, 2)
    assert all(m["name"] for m in members)


def test_get_list_members_empty_when_none(isolated_db):
    assert um.get_list_members("volume_bull") == []


def test_get_list_members_rolling_union_latest_per_ticker(isolated_db):
    # 최근 N일 rolling union — 같은 종목 여러 날 → 최신행 1개, 다른 종목은 다 포함.
    um.persist_universe_membership(
        {"kospi": [{"ticker": "005930", "name": "삼성전자", "rank": 5}]},
        list_type="trade_value", date="2026-06-10",
    )
    um.persist_universe_membership(
        {"kospi": [{"ticker": "005930", "name": "삼성전자", "rank": 1},
                   {"ticker": "000660", "name": "SK하이닉스", "rank": 2}]},
        list_type="trade_value", date="2026-06-16",
    )
    members = um.get_list_members("trade_value", within_days=3650)
    tickers = [m["ticker"] for m in members]
    assert tickers.count("005930") == 1  # 중복 종목은 최신행만
    samsung = next(m for m in members if m["ticker"] == "005930")
    assert samsung["rank"] == 1 and samsung["date"] == "2026-06-16"  # 최신 일자 행
    assert "000660" in tickers  # union
