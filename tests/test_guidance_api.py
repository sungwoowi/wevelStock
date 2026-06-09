"""GUIDANCE-ACCURACY-TRACKER-001 (RB-MS3) G3 — guidance API 테스트 (엔드포인트 직접 호출)."""
from __future__ import annotations

import pytest

from core.account import paper_trading, portfolio
from core.account.sizing import reload_accounts_config
from core.db.connection import Database, reset_db
from core.guidance import kpi as kpi_mod
from core.strategist import recommendation
from core.strategist.recommendation import parse_recommendation, persist_recommendation
from server.api import guidance as guidance_api

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
    db = Database(tmp_path / "test_guidance_api.sqlite")
    for mod in (paper_trading, portfolio, recommendation, kpi_mod):
        monkeypatch.setattr(mod, "get_db", lambda: db)
    monkeypatch.setattr("core.outputs.get_db", lambda: db)
    return db


def _closed_position():
    persist_recommendation(parse_recommendation(REC_B))
    paper_trading.record_buy_fill(
        recommendation_id="REC-20260601-005930-B", account_id="kr_swing", ticker="005930",
        track="B", leg=1, limit_price=100.0, fill_price=100.0, value_krw=10_000.0,
        filled_date="2026-06-01", reason="entry",
    )
    paper_trading.record_sell_fill(
        recommendation_id="REC-20260601-005930-B", account_id="kr_swing", ticker="005930",
        track="B", leg=1, fill_price=130.0, shares=100.0, filled_date="2026-06-11", reason="target_1",
    )


@pytest.mark.asyncio
async def test_guidance_kpi_endpoint(isolated_db):
    _closed_position()
    out = await guidance_api.guidance_kpi(track="B", period_days=3650)
    assert out["closed_count"] == 1
    assert out["realized_return_avg_pct"] == pytest.approx(30.0)


@pytest.mark.asyncio
async def test_guidance_retrospective_endpoint(isolated_db):
    _closed_position()
    out = await guidance_api.guidance_retrospective(period_days=3650)
    assert "summary" in out and "text" in out
    assert "회고" in out["text"]
    assert out["summary"]["closed_count"] == 1


@pytest.mark.asyncio
async def test_guidance_retrospective_empty(isolated_db):
    out = await guidance_api.guidance_retrospective(period_days=90)
    assert out["summary"]["closed_count"] == 0
    assert "청산된 권고가 아직 없습니다" in out["text"]
