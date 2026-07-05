"""AUTO-SIGNAL-INTEGRITY-001 리플레이 데모 — 실제 DB 의 과거 buy 권고를 새 게이트에 재통과.

읽기 전용 · LLM 0. 당시 영속된 cited_scores + alpha_posture + market_view_snapshot(그날
entry_posture)을 그대로 입력으로 재구성해 derive_alpha_posture(새 차등 게이트 포함)를 돌린다.
"""
from __future__ import annotations

import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from core.db import get_db
from core.signal.alpha_posture import PostureInputs, derive_alpha_posture

db = get_db()

# 검증 표본: 진단에서 확인된 defensive 태세 중 자동 buy 발령 건들.
CASES = [
    ("2026-06-16", "093370", "후성"),
    ("2026-06-17", "093370", "후성"),
    ("2026-06-29", "093370", "후성"),
    ("2026-06-29", "000660", "SK하이닉스"),
    ("2026-06-29", "032830", "삼성생명"),
    ("2026-06-29", "319660", "피에스케이"),
    ("2026-06-29", "178320", "서진시스템"),
    ("2026-07-02", "095610", "테스"),
]


def posture_of(date: str) -> str | None:
    row = db.fetch_one(
        "SELECT entry_posture FROM market_view_snapshot WHERE date = ? AND market = 'KOSPI'",
        (date,),
    )
    return row["entry_posture"] if row else None


print(f"{'날짜':<11}{'종목':<8}{'당시발행':<8}{'그날태세':<10}{'새 게이트':<9} 사유")
print("-" * 110)

for date, ticker, name in CASES:
    row = db.fetch_one(
        "SELECT verdict, data_json FROM team_outputs "
        "WHERE team_id='track_a' AND target=? AND date(timestamp)=? AND verdict='buy' "
        "ORDER BY timestamp DESC LIMIT 1",
        (ticker, date),
    )
    if row is None:
        print(f"{date:<11}{name:<8}(그날 buy 행 없음 — skip)")
        continue
    data = json.loads(row["data_json"]) if row["data_json"] else {}
    cited = data.get("cited_scores") or {}
    ap = data.get("alpha_posture") or {}
    mod = ap.get("modulation") or {}
    ep = posture_of(date)

    # 당시 값 그대로 재구성 (당시 미배선이던 sector_rs·wave 는 그때처럼 None).
    inp = PostureInputs(
        track="A",
        regime=mod.get("regime"),
        s_score=cited.get("s_score"),
        buy_score=cited.get("buy_score"),
        f_score=cited.get("f_score"),
        rs_score=None,
        extension_score=None,
        sector_rs_score=None,
        wave_alive=None,
        distribution_day_count=None,
        entry_posture=ep,
    )
    p = derive_alpha_posture(inp)
    reason = p.selection_reason[-1] if p.selection_reason else ""
    mark = "🚫" if (row["verdict"] == "buy" and p.verdict_candidate != "buy") else "  "
    print(f"{date:<11}{name:<8}{row['verdict']:<8}{ep or '?':<10}{p.verdict_candidate:<9}{mark} {reason}")

print()
print("범례: 🚫 = 당시엔 발행됐지만 새 게이트라면 차단됐을 신호")
