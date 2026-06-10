"""WEALTH-COMPOUND-TRACKER-001 (RB-MS4) — wealth API 테스트 (엔드포인트 직접 호출)."""
from __future__ import annotations

import pytest

from core.account import compounding, holdings, paper_trading, portfolio
from core.account.compounding import snapshot_equity
from core.account.sizing import reload_accounts_config
from core.db.connection import Database, reset_db
from server.api import wealth as wealth_api


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    reload_accounts_config()
    db = Database(tmp_path / "test_wealth_api.sqlite")
    for mod in (paper_trading, portfolio, holdings, compounding):
        monkeypatch.setattr(mod, "get_db", lambda: db)
    return db


@pytest.mark.asyncio
async def test_wealth_curve_endpoint(isolated_db):
    snapshot_equity("2026-06-12", price_lookup=lambda t: 100.0)
    out = await wealth_api.wealth_curve()
    assert out["account_id"] == "all"
    assert len(out["points"]) == 1
    assert "realized_equity_krw" in out["points"][0]


@pytest.mark.asyncio
async def test_wealth_progress_endpoint(isolated_db):
    snapshot_equity("2026-06-12", price_lookup=lambda t: 100.0)
    out = await wealth_api.wealth_progress()
    assert out["total_seed_krw"] == pytest.approx(400_000_000.0)  # 계좌당 1억 × 4
    assert "mdd_pct" in out and "progress_pct" in out
