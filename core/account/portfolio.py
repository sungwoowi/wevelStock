"""계좌 정의 로드 + 계좌 상태 DB-first 부트스트랩 — ACCOUNT-MANAGER-001 (RB-MS1).

`load_accounts()` = config/accounts.yaml → AccountDef 4개.
`get_account_state()` = `account_state` 테이블 DB-first read. 행 없으면 seed 기준 0 비중 부트스트랩
(MS1 단독 1차 — 가상 체결 write 는 RB-MS2 PAPER-TRADING-001).

가상(페이퍼) 전용. import 금지·DB 경유([[agent_architecture_pattern]]).
"""
from __future__ import annotations

from typing import Any

from core.account.sizing import AccountDef, AccountState, load_accounts_config
from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)


def load_accounts(config: dict[str, Any] | None = None) -> list[AccountDef]:
    """config/accounts.yaml 의 4계좌 정의 → AccountDef 리스트."""
    cfg = config if config is not None else load_accounts_config()
    out: list[AccountDef] = []
    for a in cfg.get("accounts", []):
        out.append(
            AccountDef(
                account_id=str(a["account_id"]),
                market=str(a.get("market", "KR")),
                track=str(a.get("track", "A")),
                horizon=str(a.get("horizon", "long")),
                seed_krw=float(a.get("seed_krw", 10_000_000)),
                label=str(a.get("label", a["account_id"])),
            )
        )
    return out


def get_account(account_id: str, config: dict[str, Any] | None = None) -> AccountDef | None:
    """account_id → AccountDef (정의에 없으면 None)."""
    for a in load_accounts(config):
        if a.account_id == account_id:
            return a
    return None


def get_account_state(account_id: str, config: dict[str, Any] | None = None) -> AccountState:
    """account_state DB-first read. 행 없으면 0 비중 부트스트랩(추정 X, graceful)."""
    try:
        row = get_db().fetch_one(
            "SELECT * FROM account_state WHERE account_id = ?",
            (account_id,),
        )
    except Exception:  # noqa: BLE001 — DB 부재 환경에서도 막지 않음
        row = None

    if row is None:
        return AccountState(account_id=account_id, deployed_weight=0.0, trading_deployed_weight=0.0)

    def _f(key: str) -> float:
        v = row[key]
        return float(v) if v is not None else 0.0

    return AccountState(
        account_id=row["account_id"],
        deployed_weight=_f("deployed_weight"),
        trading_deployed_weight=_f("trading_deployed_weight"),
        positions=[],
    )


def upsert_account_state(state: AccountState, *, seed_krw: float) -> None:
    """account_state ON CONFLICT REPLACE 멱등 upsert (account_id PK). RB-MS2 가 주 사용자."""
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO account_state "
            "(account_id, seed_krw, cash_krw, deployed_weight, trading_deployed_weight, updated_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(account_id) DO UPDATE SET "
            " seed_krw=excluded.seed_krw, cash_krw=excluded.cash_krw, "
            " deployed_weight=excluded.deployed_weight, "
            " trading_deployed_weight=excluded.trading_deployed_weight, "
            " updated_at=excluded.updated_at",
            (
                state.account_id,
                seed_krw,
                seed_krw * (1.0 - state.deployed_weight),
                state.deployed_weight,
                state.trading_deployed_weight,
            ),
        )
