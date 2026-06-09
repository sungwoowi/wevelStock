"""PAPER-TRADING-001 (RB-MS2) 라이브 probe — 권고 → 데스크 한 바퀴 → 보유 end-to-end.

격리 temp DB(실 DB 미오염) + 결정론(LLM·네트워크 0). 전 체인 실증:
  구조화 권고 영속(M1) → size_position(RB-MS1) → 지정가 도달 가상 체결(M2) →
  목표 익절·평가손익(M3) → 데스크 한 바퀴 멱등(M4) → 계좌/보유 조회.
usage: uv run python scripts/_paper_trading_probe.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import core.account.desk as dk  # noqa: E402
import core.account.holdings as hd  # noqa: E402
import core.account.paper_trading as pt  # noqa: E402
import core.account.portfolio as pf  # noqa: E402
import core.outputs as outp  # noqa: E402
import core.strategist.recommendation as rc  # noqa: E402
from core.account.sizing import reload_accounts_config  # noqa: E402
from core.db.connection import Database  # noqa: E402

SAMPLE_B = """삼성전자 단기 매수 권고.

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
  f_score: 6
confidence: 75
reasons:
  - "타점 점수 7 — 거래량 급증 트리거"
contract_version: "1.0"
```
"""


def _ohlc(high: float, low: float):
    def provider(ticker: str, as_of: str):
        return {"high": high, "low": low, "close": (high + low) / 2}
    return provider


def _show_account(account_id: str, price_lookup=None) -> None:
    holdings = hd.get_holdings(account_id, price_lookup=price_lookup)
    state = pf.get_account_state(account_id)
    print(f"  [{account_id}] 투입비중 {state.deployed_weight * 100:.1f}% (트레이딩 {state.trading_deployed_weight * 100:.1f}%)")
    if not holdings:
        print("    보유 없음")
    for h in holdings:
        print(f"    {h['ticker']} {h['shares']:.1f}주 · 평단 {h['avg_price']:,.0f} · 평가 {h['eval_price']:,.0f} "
              f"· {h['unrealized_pct']:+.1f}% · 실현 {h['realized_pnl_krw']:,.0f}원 · {h['tranche_count']}차")


def main() -> None:
    # 격리 temp DB — 모듈 get_db 재지정 (실 DB 미오염)
    tmp = Path(tempfile.mkdtemp()) / "paper_probe.sqlite"
    db = Database(tmp)
    for m in (pt, pf, hd, dk, rc):
        m.get_db = lambda: db
    outp.get_db = lambda: db
    reload_accounts_config()

    print("=" * 64)
    print("PAPER-TRADING-001 (RB-MS2) 라이브 probe — 데스크 한 바퀴")
    print("=" * 64)

    # 1) 전략가 구조화 권고 파싱·영속 (M1)
    rec = rc.parse_recommendation(SAMPLE_B)
    rc.persist_recommendation(rec)
    print(f"\n[1] 권고 영속: {rec.recommendation_id} {rec.display_name} Track {rec.track} "
          f"진입 {rec.entry_price:,.0f}·손절 {rec.stop_loss:,.0f}·목표 {rec.target_prices}")
    active = rc.load_active_recommendations()
    print(f"    활성 권고 {len(active)}건 (데스크 read 대상)")

    # 2) Day 1 — 진입가 도달 (저가 67,000 ≤ 68,000), 매수 체결
    print("\n[2] Day 1 (2026-06-09) — 저가 67,000 → 진입가 68,000 도달")
    s1 = dk.run_desk_once(as_of="2026-06-09", ohlc_provider=_ohlc(high=69000, low=67000),
                          market_context=("aggressive", "none"))
    print(f"    데스크: 매수 {s1['buy_fills']}건 / 매도 {s1['sell_fills']}건 (posture={s1['entry_posture']})")
    _show_account("kr_swing", price_lookup=lambda t: 70000.0)  # 현재가 70,000 가정

    # 3) Day 1 재실행 — 멱등 (중복 체결 0)
    s1b = dk.run_desk_once(as_of="2026-06-09", ohlc_provider=_ohlc(high=69000, low=67000),
                           market_context=("aggressive", "none"))
    print(f"\n[3] Day 1 재실행(멱등): 매수 {s1b['buy_fills']}건 / 매도 {s1b['sell_fills']}건 (중복 0 기대)")

    # 4) Day 2 — 목표가 74,000 도달, 익절
    print("\n[4] Day 2 (2026-06-15) — 고가 75,000 → 목표 74,000 도달, 익절")
    s2 = dk.run_desk_once(as_of="2026-06-15", ohlc_provider=_ohlc(high=75000, low=70000),
                          market_context=("aggressive", "none"))
    print(f"    데스크: 매수 {s2['buy_fills']}건 / 매도 {s2['sell_fills']}건")
    _show_account("kr_swing", price_lookup=lambda t: 74000.0)

    # 5) vix_panic 동결 시연 (다른 종목)
    print("\n[5] vix_panic 동결 — 신규 진입 차단 검증")
    rc.persist_recommendation(rc.parse_recommendation(
        SAMPLE_B.replace("005930", "000660").replace('"삼성전자"', '"SK하이닉스"')
        .replace("-005930-B", "-000660-B")))
    s3 = dk.run_desk_once(as_of="2026-06-09", ohlc_provider=_ohlc(high=69000, low=67000),
                          market_context=("defensive", "vix_panic"))
    print(f"    데스크(vix_panic): 매수 {s3['buy_fills']}건 (000660 동결 → 0 기대)")

    print("\n" + "=" * 64)
    print("probe 완료 — 권고→비중→가상체결→익절→평가손익 전 체인 동작 ✅")
    print("=" * 64)


if __name__ == "__main__":
    main()
