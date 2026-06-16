"""TRADE-PLAN-LIFECYCLE-001 B-MS1 — 라이브 검증 프로브 (실 Gemini).

결정론 가격대 메뉴가 전략가에 주입되고, 권고가 다단 손절/분할매수/목표를 발행하며,
menu_bound·오닐 clamp 가드레일이 작동하는지 여러 종목으로 눈으로 확인한다.
실 KIS(스냅샷·OHLCV) + 실 Gemini(Flash) — 테스트 아님(production 경로). 알림 OFF.

usage: uv run python scripts/_trade_plan_probe.py [ticker ...]   (기본 = 4종 large-cap)
"""
from __future__ import annotations

import asyncio
import sys

from core.config import get_config

_DEFAULT = ["004170", "005930", "005380", "017670"]  # 신세계·삼성전자·현대차·SK텔레콤


async def _run_one(ticker: str, snapshot) -> None:
    from collectors.charts import load_ohlcv_from_db
    from collectors.screening import load_trade_plan_config
    from core.inference.run_analyst import resolve_ticker
    from core.signal.auto_signal import (
        _signal_directive, build_prefetched_entries, compute_scorecard,
    )
    from core.signal.trade_plan_menu import (
        build_trade_plan_menu, render_trade_plan_menu_md, trade_plan_inputs_from_ohlcv,
    )
    from core.strategist.recommendation import parse_recommendation
    from core.strategist.run_strategist import run_strategist

    code, name = resolve_ticker(ticker)
    sc = await compute_scorecard(ticker, snapshot)
    entries = build_prefetched_entries(sc, "A")
    cfg = load_trade_plan_config()
    menu = build_trade_plan_menu(
        trade_plan_inputs_from_ohlcv(load_ohlcv_from_db(code), ticker=ticker,
                                     extension=sc.extension_score, config=cfg), cfg)
    menu_md = render_trade_plan_menu_md(menu)

    rec = None
    for attempt in range(3):  # 503 transient 재시도
        try:
            resp = await run_strategist(
                "track_a", [{"role": "user", "content": _signal_directive(sc, "A", "probe")}],
                target=ticker, prefetched_analyst_outputs=entries,
                trade_plan_menu_md=menu_md, provider="gemini", mock_fallback_allowed=False,
            )
            rec = parse_recommendation(getattr(resp, "text", "") or "")
            break
        except Exception as e:  # noqa: BLE001
            if "503" in str(e) and attempt < 2:
                await asyncio.sleep(3 * (attempt + 1))
                continue
            print(f"\n##### {name}({ticker}) — 호출 실패: {str(e)[:80]}")
            return

    print(f"\n##### {name}({ticker}) — verdict={rec.verdict if rec else 'no_yaml'}")
    sc_line = " · ".join(f"{c.label} {c.price:,.0f}" for c in menu.stop_candidates)
    print(f"  [메뉴] 기준가 {menu.entry_hint:,.0f} / 기본손절 {menu.default_stop:,.0f} / 손절후보: {sc_line}")
    print(f"         목표후보: {' · '.join(f'{t.label} {t.price:,.0f}' for t in menu.target_candidates) or '—'}")
    if rec is None:
        return
    plan = rec.data.get("trade_plan") or {}
    print(f"  [LLM] entry={rec.entry_price} stop={rec.stop_loss} targets={rec.target_prices} R/R={rec.risk_reward}")
    if plan.get("scaled_buy"):
        print(f"  [다단 분할매수] {[(l['leg'], l['price'], l['ratio']) for l in plan['scaled_buy']]}")
    if plan.get("scaled_sell"):
        print(f"  [다단 분할매도] {[(l['leg'], l['price'], l['ratio']) for l in plan['scaled_sell']]}")
    print(f"  [가드레일] stop_basis={plan.get('stop_basis')} stop_label={plan.get('stop_label')} "
          f"deviation={plan.get('deviation_reason')}")


async def main() -> None:
    get_config()
    tickers = sys.argv[1:] or _DEFAULT
    from collectors.snapshot import build_market_snapshot

    print("=== B-MS1 트레이드 플랜 메뉴 라이브 (실 Gemini, Track A) ===")
    snapshot, _ = await build_market_snapshot()
    for t in tickers:
        try:
            await _run_one(t, snapshot)
        except Exception as e:  # noqa: BLE001
            print(f"\n##### {t} — 예외: {str(e)[:100]}")


if __name__ == "__main__":
    asyncio.run(main())
