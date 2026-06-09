"""WEALTH-COMPOUND-TRACKER-001 (RB-MS4) 라이브 probe — 자산 곡선(두 시리즈) + 복리 진척.

격리 temp DB + 결정론. 매일 자산 스냅샷 → 실현 vs 총자산 두 곡선 + 연 18% 목표 대비.
usage: uv run python scripts/_wealth_probe.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import core.account.compounding as cp  # noqa: E402
import core.account.holdings as hd  # noqa: E402
import core.account.paper_trading as pt  # noqa: E402
import core.account.portfolio as pf  # noqa: E402
from core.account.sizing import reload_accounts_config  # noqa: E402
from core.db.connection import Database  # noqa: E402


def main() -> None:
    db = Database(Path(tempfile.mkdtemp()) / "wealth_probe.sqlite")
    for m in (pt, pf, hd, cp):
        m.get_db = lambda: db
    reload_accounts_config()

    print("=" * 64)
    print("WEALTH-COMPOUND-TRACKER-001 (RB-MS4) 라이브 probe — 복리 자산 곡선")
    print("=" * 64)

    # 단기 계좌: 100주 매수 → 일부 익절(실현) + 일부 보유(평가)
    pt.record_buy_fill(recommendation_id="REC-A", account_id="kr_swing", ticker="005930", track="B",
                       leg=1, limit_price=100.0, fill_price=100.0, value_krw=10_000.0, filled_date="2026-06-01", reason="entry")

    # Day 1: 보유만 (평가 +20%)
    cp.snapshot_equity("2026-06-01", price_lookup=lambda t: 120.0)
    # Day 2: 50주 익절(실현) + 50주 보유(평가 +30%)
    pt.record_sell_fill(recommendation_id="REC-A", account_id="kr_swing", ticker="005930", track="B",
                        leg=1, fill_price=130.0, shares=50.0, filled_date="2026-06-05", reason="target_1")
    cp.snapshot_equity("2026-06-05", price_lookup=lambda t: 130.0)

    curve = cp.get_equity_curve(account_id="kr_swing")
    print("\n[자산 곡선 — 단기 계좌] (두 시리즈)")
    print("  날짜        | 실현만(확정)     | 총자산(평가포함)")
    for p in curve["points"]:
        print(f"  {p['date']} | {p['realized_equity_krw']:>14,.0f} | {p['equity_krw']:>14,.0f}")

    prog = cp.get_compound_progress(as_of="2026-06-05", benchmark_fetch=lambda s, a, b: (100.0, 102.0))
    print("\n[복리 진척 — 4계좌 통합]")
    print(cp.render_compound_summary(prog, cp.get_equity_curve(as_of="2026-06-05")))

    print("\n" + "=" * 64)
    print("probe 완료 — 매일 스냅샷 → 실현/총 두 곡선 + 목표 대비 동작 ✅")
    print("=" * 64)


if __name__ == "__main__":
    main()
