"""PAPER-TRADING-001 (RB-MS2) M4 — accounts API 테스트 (엔드포인트 함수 직접 호출)."""
from __future__ import annotations

import pytest

from core.account import holdings, paper_trading, portfolio
from core.account.sizing import reload_accounts_config
from core.db.connection import Database, reset_db
from server.api import accounts as accounts_api


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    reload_accounts_config()
    db = Database(tmp_path / "test_acct_api.sqlite")
    for mod in (paper_trading, portfolio, holdings):
        monkeypatch.setattr(mod, "get_db", lambda: db)
    return db


@pytest.mark.asyncio
async def test_list_accounts_returns_four_with_state(isolated_db):
    resp = await accounts_api.list_accounts()
    items = resp["items"]
    assert len(items) == 4
    kr_long = next(i for i in items if i["account_id"] == "kr_long")
    assert kr_long["deployed_weight"] == pytest.approx(0.0)
    assert kr_long["available_weight"] == pytest.approx(1.0)
    assert kr_long["seed_krw"] == 10_000_000


@pytest.mark.asyncio
async def test_account_holdings_after_fill(isolated_db):
    paper_trading.record_buy_fill(
        recommendation_id="REC-20260609-005930-A", account_id="kr_long", ticker="005930",
        track="A", leg=1, limit_price=100.0, fill_price=100.0, value_krw=1_000_000.0,
        filled_date="2026-06-09", reason="entry",
    )
    resp = await accounts_api.account_holdings("kr_long")
    assert resp["summary"]["position_count"] == 1
    assert resp["holdings"][0]["ticker"] == "005930"


@pytest.mark.asyncio
async def test_account_holdings_unknown_account_404(isolated_db):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await accounts_api.account_holdings("nonexistent")
    assert exc.value.status_code == 404


def test_render_accounts_text_pure():
    from server.telegram.commands import render_accounts_text

    items = [{"account_id": "kr_long", "label": "국장 중장기",
              "deployed_weight": 0.1, "available_weight": 0.9}]
    holdings_by_id = {"kr_long": {
        "holdings": [{"ticker": "005930", "shares": 100.0, "avg_price": 68000.0,
                      "unrealized_pct": 5.0, "priced": True}],
        "summary": {"position_count": 1, "unrealized_pnl_krw": 340000.0, "realized_pnl_krw": 0.0},
    }}
    text = render_accounts_text(items, holdings_by_id)
    assert "국장 중장기" in text
    assert "005930" in text
    assert "+5.0%" in text
    # 코드 라벨(track A/verdict 등) 노출 금지
    assert "verdict" not in text and "track" not in text.lower()
