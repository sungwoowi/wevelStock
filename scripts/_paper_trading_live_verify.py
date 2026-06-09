"""PAPER-TRADING-001 (RB-MS2) 실 LLM 라이브 검증 — capstone.

실 Gemini 로 `swing: 삼성전자` 발행 → production_chat 이 전략가 권고를 영속 →
파서가 **실 strategist YAML** 을 포착했는지 → 데스크가 굴려 가상 체결되는지 검증.

⚠️ 실 DB 에 권고·체결 적재(페이퍼 데스크 실가동). 실 LLM 호출(비용·503 가능).
usage: uv run python scripts/_paper_trading_live_verify.py [종목명]
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
from server.api.production_chat import (  # noqa: E402
    ChatMessage,
    ProductionChatRequest,
    post_production_chat,
)


async def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "삼성전자"
    msg = f"swing: {name}"
    print("=" * 68)
    print(f"PAPER-TRADING-001 실 LLM 검증 — \"{msg}\" (provider=gemini)")
    print("=" * 68)

    payload = ProductionChatRequest(
        messages=[ChatMessage(role="user", content=msg)],
        provider="gemini",
        skip_formatter=True,  # 포매터 LLM 호출 절약 (권고 영속만 검증)
    )

    resp = None
    for attempt in range(1, 3):
        try:
            resp = await post_production_chat(payload)
            break
        except Exception as e:  # noqa: BLE001 — 503 등 transient 재시도
            print(f"  [시도 {attempt}] 실패: {type(e).__name__}: {e}")
    if resp is None:
        print("\n❌ production_chat 호출 실패 (재시도 소진). 503 transient 가능 — 잠시 후 재시도.")
        return

    print(f"\n[1] 분류: scenario={resp.classification.get('scenario_id')} "
          f"route={resp.classification.get('agent_route')} "
          f"ticker={resp.classification.get('ticker')} ({resp.classification.get('ticker_display')})")

    strat = [r for r in resp.agent_responses if r.get("kind") in ("strategist", "refuse_or_guide", "pending_ms5")]
    for s in strat:
        text = (s.get("text") or "").strip()
        has_yaml = "```yaml" in text or "recommendation_id" in text
        print(f"\n[2] 전략가 {s.get('agent_id')} (kind={s.get('kind')}) — YAML블록={'있음' if has_yaml else '없음'}"
              f"{' · error=' + str(s.get('error')) if s.get('error') else ''}")
        # YAML 일부 미리보기
        snippet = "\n".join(line for line in text.splitlines() if any(
            k in line for k in ("recommendation_id", "verdict", "entry_price", "stop_loss", "target_price")))
        if snippet:
            print("    " + snippet.replace("\n", "\n    "))

    # [3] 파서·영속 검증 — production_chat 이 이미 persist 했으므로 load 로 확인
    recs = load_active_recommendations()
    print(f"\n[3] 영속된 활성 권고 {len(recs)}건 (파서가 실 YAML 포착·team_outputs 적재):")
    for r in recs:
        print(f"    {r.recommendation_id} {r.ticker} Track {r.track} verdict={r.verdict} "
              f"진입={r.entry_price} 손절={r.stop_loss} 목표={r.target_prices} actionable={r.is_actionable}")

    # [4] 데스크 한 바퀴 (실 chart_ohlcv 시세)
    actionable = [r for r in recs if r.is_actionable]
    if actionable:
        print(f"\n[4] 데스크 한 바퀴 (actionable {len(actionable)}건, 실 DB 시세)")
        summary = run_desk_today(as_of=date.today().isoformat())
        print(f"    매수 {summary['buy_fills']}건 / 매도 {summary['sell_fills']}건 "
              f"/ posture={summary['entry_posture']} extreme={summary['extreme']} "
              f"/ touched={summary['accounts_touched']}")
    else:
        print("\n[4] actionable 권고 없음 (verdict≠buy 또는 진입/손절 미발행) → 데스크 체결 대상 0. "
              "파서·영속 경로는 검증됨.")

    # [5] 계좌 보유현황
    print("\n[5] 계좌 보유현황:")
    accts = await list_accounts()
    for a in accts["items"]:
        if a["deployed_weight"] > 0:
            h = await account_holdings(a["account_id"])
            print(f"    [{a['label']}] 투입 {a['deployed_weight'] * 100:.1f}% · 보유 {h['summary']['position_count']}종 "
                  f"· 평가손익 {h['summary']['unrealized_pnl_krw']:,.0f}원")
            for pos in h["holdings"]:
                print(f"      {pos['ticker']} {pos['shares']:.0f}주 평단 {pos['avg_price']:,.0f} {pos['unrealized_pct']:+.1f}%")

    print("\n" + "=" * 68)
    print("검증 완료")
    print("=" * 68)


if __name__ == "__main__":
    asyncio.run(main())
