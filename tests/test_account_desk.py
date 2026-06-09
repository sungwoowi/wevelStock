"""PAPER-TRADING-001 (RB-MS2) M4 — 매일 도는 데스크 한 바퀴 테스트.

활성 권고 → size_position(RB-MS1) → 지정가 도달 매수 / 목표·손절 매도 → 멱등.
OHLC·market_context 주입으로 LLM·네트워크 0.
"""
from __future__ import annotations

import pytest

from core.account import desk, holdings, paper_trading, portfolio
from core.account.desk import run_desk_once
from core.account.sizing import reload_accounts_config
from core.db.connection import Database, reset_db
from core.strategist import recommendation
from core.strategist.recommendation import parse_recommendation, persist_recommendation

SAMPLE_B = """매수 권고.

```yaml
recommendation_id: REC-20260609-005930-B
date: 2026-06-09
ticker: "005930"
display_name: "삼성전자"
track: B
verdict: "buy"
entry_price: 68000
target_price_1: 74000
target_price_2: null
target_price_3: null
stop_loss: 65000
risk_reward: 2.0
cited_scores:
  buy_score: 7
  t_score: 7
confidence: 75
reasons:
  - "타점 점수 7"
contract_version: "1.0"
```
"""

SAMPLE_HOLD = SAMPLE_B.replace('verdict: "buy"', 'verdict: "hold"').replace(
    "REC-20260609-005930-B", "REC-20260609-005930-Bh"
)


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    reload_accounts_config()
    db = Database(tmp_path / "test_desk.sqlite")
    for mod in (paper_trading, portfolio, recommendation, desk, holdings):
        monkeypatch.setattr(mod, "get_db", lambda: db)
    monkeypatch.setattr("core.outputs.get_db", lambda: db)  # persist_recommendation 경유
    return db


def _ohlc(high: float, low: float, close: float | None = None):
    def provider(ticker: str, as_of: str):
        return {"high": high, "low": low, "close": close if close is not None else low}
    return provider


def test_desk_fills_first_tranche_when_entry_reached(isolated_db):
    persist_recommendation(parse_recommendation(SAMPLE_B))
    summary = run_desk_once(
        as_of="2026-06-09",
        ohlc_provider=_ohlc(high=69000, low=67000),  # entry 68000 도달, 목표·손절 미도달
        market_context=("aggressive", "none"),
    )
    assert summary["buy_fills"] >= 1
    pos = paper_trading.get_position("kr_swing", "005930")
    assert pos is not None
    assert pos["tranche_count"] == 1
    # KR 종목은 미장 계좌(us_swing)엔 체결되지 않음
    assert paper_trading.get_position("us_swing", "005930") is None


def test_desk_is_idempotent_same_day(isolated_db):
    persist_recommendation(parse_recommendation(SAMPLE_B))
    run_desk_once(as_of="2026-06-09", ohlc_provider=_ohlc(69000, 67000),
                  market_context=("aggressive", "none"))
    pos1 = paper_trading.get_position("kr_swing", "005930")
    run_desk_once(as_of="2026-06-09", ohlc_provider=_ohlc(69000, 67000),
                  market_context=("aggressive", "none"))
    pos2 = paper_trading.get_position("kr_swing", "005930")
    assert pos2["shares"] == pytest.approx(pos1["shares"])
    assert pos2["tranche_count"] == pos1["tranche_count"]


def test_desk_sells_at_target(isolated_db):
    persist_recommendation(parse_recommendation(SAMPLE_B))
    run_desk_once(as_of="2026-06-09", ohlc_provider=_ohlc(69000, 67000),
                  market_context=("aggressive", "none"))  # 매수
    summary = run_desk_once(
        as_of="2026-06-15",
        ohlc_provider=_ohlc(high=75000, low=70000),  # 목표 74000 도달
        market_context=("aggressive", "none"),
    )
    assert summary["sell_fills"] >= 1
    # 단일 목표 전량 익절 → 보유 청산
    assert paper_trading.get_position("kr_swing", "005930") is None


def test_desk_stop_priority_closes_position(isolated_db):
    persist_recommendation(parse_recommendation(SAMPLE_B))
    run_desk_once(as_of="2026-06-09", ohlc_provider=_ohlc(69000, 67000),
                  market_context=("aggressive", "none"))
    run_desk_once(
        as_of="2026-06-16",
        ohlc_provider=_ohlc(high=75000, low=64000),  # 손절 65000·목표 74000 동시 → 손절 우선
        market_context=("aggressive", "none"),
    )
    assert paper_trading.get_position("kr_swing", "005930") is None
    fills = isolated_db.fetch_all(
        "SELECT reason FROM account_fills WHERE side='sell' AND account_id='kr_swing'"
    )
    assert any(f["reason"] == "stop" for f in fills)


def test_desk_skips_non_actionable_recommendation(isolated_db):
    persist_recommendation(parse_recommendation(SAMPLE_HOLD))
    summary = run_desk_once(as_of="2026-06-09", ohlc_provider=_ohlc(69000, 67000),
                            market_context=("aggressive", "none"))
    assert summary["buy_fills"] == 0
    assert paper_trading.get_position("kr_swing", "005930") is None


def test_desk_vix_panic_freezes_new_entry(isolated_db):
    persist_recommendation(parse_recommendation(SAMPLE_B))
    summary = run_desk_once(
        as_of="2026-06-09", ohlc_provider=_ohlc(69000, 67000),
        market_context=("defensive", "vix_panic"),  # 동결 → size_position 차단
    )
    assert summary["buy_fills"] == 0
    assert paper_trading.get_position("kr_swing", "005930") is None
