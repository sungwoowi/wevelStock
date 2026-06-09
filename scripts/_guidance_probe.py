"""GUIDANCE-ACCURACY-TRACKER-001 (RB-MS3) 라이브 probe — 권고→가상매매 청산→회고 채점.

격리 temp DB + 결정론(벤치마크 주입). RB-MS2 account_fills 를 읽어 시장 대비 채점·회고.
usage: uv run python scripts/_guidance_probe.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import core.account.paper_trading as pt  # noqa: E402
import core.account.portfolio as pf  # noqa: E402
import core.guidance.kpi as kpi  # noqa: E402
import core.outputs as outp  # noqa: E402
import core.strategist.recommendation as rc  # noqa: E402
from core.account.sizing import reload_accounts_config  # noqa: E402
from core.db.connection import Database  # noqa: E402
from core.guidance.retrospective import render_retrospective  # noqa: E402


def _rec_yaml(rec_id, ticker, name, track, entry, stop, target, rr):
    return f"""```yaml
recommendation_id: {rec_id}
date: 2026-06-01
ticker: "{ticker}"
display_name: "{name}"
track: {track}
verdict: "buy"
entry_price: {entry}
target_price_1: {target}
stop_loss: {stop}
risk_reward: {rr}
cited_scores: {{buy_score: 7}}
confidence: 70
reasons: ["probe"]
contract_version: "1.0"
```"""


def _close(rec_id, ticker, track, account, entry, exit_price, stop, target, rr, name, entry_d, exit_d, reason):
    rc.persist_recommendation(rc.parse_recommendation(_rec_yaml(rec_id, ticker, name, track, entry, stop, target, rr)))
    pt.record_buy_fill(recommendation_id=rec_id, account_id=account, ticker=ticker, track=track,
                       leg=1, limit_price=entry, fill_price=entry, value_krw=entry * 100, filled_date=entry_d, reason="entry")
    pt.record_sell_fill(recommendation_id=rec_id, account_id=account, ticker=ticker, track=track,
                        leg=(0 if reason == "stop" else 1), fill_price=exit_price, shares=100.0, filled_date=exit_d, reason=reason)


def main() -> None:
    db = Database(Path(tempfile.mkdtemp()) / "guidance_probe.sqlite")
    for m in (pt, pf, rc, kpi):
        m.get_db = lambda: db
    outp.get_db = lambda: db
    reload_accounts_config()

    print("=" * 64)
    print("GUIDANCE-ACCURACY-TRACKER-001 (RB-MS3) 라이브 probe — 회고 채점")
    print("=" * 64)

    # 2 청산: 단기(B) 익절 +30% / 단기(B) 손절 -10%
    _close("REC-20260601-005930-B", "005930", "B", "kr_swing", 100, 130, 90, 130, 3.0, "삼성전자", "2026-06-01", "2026-06-09", "target_1")
    _close("REC-20260602-000660-B", "000660", "B", "kr_swing", 100, 90, 90, 130, 3.0, "SK하이닉스", "2026-06-02", "2026-06-05", "stop")

    # 벤치마크 +5% 가정 주입 (실 yfinance 대신 결정론)
    summary = kpi.get_kpi_summary(period_days=3650, as_of="2026-06-12", benchmark_fetch=lambda s, a, b: (100.0, 105.0))
    print("\n" + render_retrospective(summary))
    print(f"\n[raw] closed={summary['closed_count']} 실현평균={summary['realized_return_avg_pct']}% "
          f"알파={summary['alpha_avg_pct']}%p 적중률={summary['win_rate_pct']}%")
    print("\n" + "=" * 64)
    print("probe 완료 — account_fills 실현 → 시장 대비 채점·회고 동작 ✅")
    print("=" * 64)


if __name__ == "__main__":
    main()
