"""ACCOUNT-MANAGER-001 (RB-MS1) — 계좌 정의 로드 + 계좌 상태 DB-first 부트스트랩 테스트."""
from __future__ import annotations

import pytest

from core.account import portfolio
from core.account.sizing import AccountState, reload_accounts_config
from core.db.connection import Database, reset_db


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    """temp DB + portfolio.get_db 패치 + config 캐시 클리어."""
    reset_db()
    reload_accounts_config()
    db = Database(tmp_path / "test_accounts.sqlite")
    monkeypatch.setattr(portfolio, "get_db", lambda: db)
    return db


def test_load_accounts_returns_four():
    accts = portfolio.load_accounts()
    assert len(accts) == 4
    assert {a.account_id for a in accts} == {"kr_long", "kr_swing", "us_long", "us_swing"}


def test_load_accounts_track_and_seed():
    by_id = {a.account_id: a for a in portfolio.load_accounts()}
    assert by_id["kr_long"].track == "A"
    assert by_id["kr_swing"].track == "B"
    assert by_id["us_long"].seed_krw == 10_000_000


def test_get_account_state_bootstraps_when_no_row(isolated_db):
    # DB 에 행이 없으면 seed 기준 0 비중으로 부트스트랩 (MS1 단독 1차)
    state = portfolio.get_account_state("kr_long")
    assert isinstance(state, AccountState)
    assert state.account_id == "kr_long"
    assert state.deployed_weight == 0.0
    assert state.trading_deployed_weight == 0.0


def test_get_account_state_round_trips(isolated_db):
    portfolio.upsert_account_state(
        AccountState(account_id="kr_swing", deployed_weight=0.18, trading_deployed_weight=0.18),
        seed_krw=10_000_000,
    )
    state = portfolio.get_account_state("kr_swing")
    assert state.deployed_weight == pytest.approx(0.18)
    assert state.trading_deployed_weight == pytest.approx(0.18)


def test_get_account_state_unknown_account_returns_zero_state(isolated_db):
    # 정의에 없는 계좌 → 0 상태 (graceful, 추정 X)
    state = portfolio.get_account_state("nonexistent")
    assert state.deployed_weight == 0.0
