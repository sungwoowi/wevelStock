"""실 swing: 권고 배치 — 여러 종목을 실 LLM 으로 돌려 권고 누적 + 데스크 한 바퀴 + 현황.

실 DB·실 Gemini. 청산은 며칠에 걸쳐 데스크 cron 이 누적(매수 verdict + 목표/손절 도달 시).
usage: uv run python scripts/_swing_batch.py [종목명 종목명 ...]
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

from core.account.desk import run_desk_today  # noqa: E402
from core.strategist.recommendation import load_active_recommendations  # noqa: E402
from server.api.accounts import account_holdings, list_accounts  # noqa: E402
from server.api.guidance import guidance_retrospective  # noqa: E402
from server.api.production_chat import (  # noqa: E402
    ChatMessage,
    ProductionChatRequest,
    post_production_chat,
)

DEFAULT = ["삼성전자", "SK하이닉스", "현대차"]


async def main() -> None:
    names = sys.argv[1:] or DEFAULT
    print("=" * 64)
    print(f"실 swing: 배치 — {names} (provider=gemini)")
    print("=" * 64)

    for name in names:
        payload = ProductionChatRequest(
            messages=[ChatMessage(role="user", content=f"swing: {name}")],
            provider="gemini", skip_formatter=True,
        )
        verdict = "?"
        try:
            resp = await post_production_chat(payload)
            strat = [r for r in resp.agent_responses if r.get("kind") == "strategist"]
            txt = (strat[0].get("text") if strat else "") or ""
            err = strat[0].get("error") if strat else None
            for line in txt.splitlines():
                if "verdict" in line:
                    verdict = line.strip()
                    break
            if err:
                verdict = f"(에러 {str(err)[:40]})"
        except Exception as e:  # noqa: BLE001
            verdict = f"(실패 {type(e).__name__})"
        print(f"  · {name}: {verdict}")

    print("\n[활성 권고 (영속됨)]")
    for r in load_active_recommendations():
        print(f"  {r.recommendation_id} {r.ticker} {r.track} verdict={r.verdict} "
              f"진입={r.entry_price} 손절={r.stop_loss} actionable={r.is_actionable}")

    print("\n[데스크 한 바퀴]")
    s = run_desk_today(as_of=date.today().isoformat())
    print(f"  매수 {s['buy_fills']}건 / 매도 {s['sell_fills']}건 / posture={s['entry_posture']} extreme={s['extreme']}")

    print("\n[계좌 현황]")
    for a in (await list_accounts())["items"]:
        if a["deployed_weight"] > 0:
            h = await account_holdings(a["account_id"])
            print(f"  [{a['label']}] 투입 {a['deployed_weight']*100:.1f}% · 보유 {h['summary']['position_count']}종")

    print("\n[회고 (청산 기준)]")
    retro = await guidance_retrospective(period_days=90)
    print("  " + retro["text"].replace("\n", "\n  "))
    print("\n" + "=" * 64)


if __name__ == "__main__":
    asyncio.run(main())
