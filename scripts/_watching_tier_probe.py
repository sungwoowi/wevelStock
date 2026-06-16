"""TRADE-PLAN-LIFECYCLE-001 2단계 — 매수대기 단계 라이브 검증 프로브 (실 Gemini).

확인 포인트:
  (1) wait 종목이 단계 라벨(관심/매수대기/진입)로 분류되는가 — funnel_stage.
  (2) 매수대기(watching) 종목의 conditional_entry 에 진입존 후보(팩트)가 메뉴 후보와 일치하는가(환각 0).
  (3) LLM 이 진입존 후보 안에서 대기진입가·시나리오를 발행하는가(stage_scenario / waiting_entry).
  (4) buy → entering · 점수 한참 미달 wait → interest.
실 KIS(스냅샷·OHLCV) + 실 Gemini — 테스트 아님(production 경로). 알림 OFF.

usage: uv run python scripts/_watching_tier_probe.py [ticker ...]   (기본 = 4종 large-cap)
"""
from __future__ import annotations

import asyncio
import sys

from core.config import get_config

_DEFAULT = ["004170", "005930", "005380", "017670"]  # 신세계·삼성전자·현대차·SK텔레콤


async def _run_one(ticker: str, track: str, snapshot) -> None:
    from collectors.charts import load_ohlcv_from_db
    from collectors.screening import load_posture_config, load_trade_plan_config
    from core.inference.run_analyst import resolve_ticker
    from core.signal.alpha_posture import (
        derive_alpha_posture, derive_funnel_stage, enrich_conditional_entry,
        render_alpha_posture_md,
    )
    from core.signal.auto_signal import (
        _signal_directive, build_prefetched_entries, compute_scorecard,
        posture_inputs_from_scorecard,
    )
    from core.signal.trade_plan_menu import (
        build_trade_plan_menu, render_trade_plan_menu_md, trade_plan_inputs_from_ohlcv,
    )
    from core.strategist.recommendation import parse_recommendation
    from core.strategist.run_strategist import run_strategist

    code, name = resolve_ticker(ticker)
    sc = await compute_scorecard(ticker, snapshot)
    entries = build_prefetched_entries(sc, track)

    # 결정론 후보 + 메뉴 + 진입존 보강 (funnel 과 동일 경로).
    p_inputs = posture_inputs_from_scorecard(sc, track)
    p_cfg = load_posture_config()
    posture = derive_alpha_posture(p_inputs, p_cfg)
    tp_cfg = load_trade_plan_config()
    menu = build_trade_plan_menu(
        trade_plan_inputs_from_ohlcv(load_ohlcv_from_db(code), ticker=ticker,
                                     extension=sc.extension_score, config=tp_cfg), tp_cfg)
    if posture.conditional_entry is not None:
        posture.conditional_entry = enrich_conditional_entry(posture.conditional_entry, menu)
    posture_md = render_alpha_posture_md(posture)
    menu_md = render_trade_plan_menu_md(menu)

    rec = None
    for attempt in range(3):  # 503 transient 재시도
        try:
            resp = await run_strategist(
                _TRACK_ID[track], [{"role": "user", "content": _signal_directive(sc, track, "probe")}],
                target=ticker, prefetched_analyst_outputs=entries,
                alpha_posture_md=posture_md, trade_plan_menu_md=menu_md,
                provider="gemini", mock_fallback_allowed=False,
            )
            rec = parse_recommendation(getattr(resp, "text", "") or "")
            break
        except Exception as e:  # noqa: BLE001
            if "503" in str(e) and attempt < 2:
                await asyncio.sleep(3 * (attempt + 1))
                continue
            print(f"\n##### {name}({ticker}) [{track}] — 호출 실패: {str(e)[:80]}")
            return

    verdict = rec.verdict if rec else "no_yaml"
    stage = derive_funnel_stage(verdict, p_inputs, posture.conditional_entry, p_cfg)
    print(f"\n##### {name}({ticker}) [{track}] — verdict={verdict}")
    print(f"  [단계] {stage.stage} · {stage.reason} (점수gap={stage.score_gap})")
    print(f"  [후보] posture={posture.verdict_candidate} ({posture.regime_class}) / "
          f"s={sc.s_score} t={sc.t_score} buy={sc.buy_score} ext={sc.extension_score}")
    ce = posture.conditional_entry or {}
    zone = ce.get("entry_zone")
    if zone:
        zone_str = " · ".join(f"{z['label']} {z['price']:,.0f}" for z in zone)
        print(f"  [진입존(팩트)] trigger={ce.get('trigger')} · {zone_str} ({ce.get('zone_basis')})")
    elif ce:
        print(f"  [진입존] trigger={ce.get('trigger')} — 가격 없음({ce.get('zone_basis', ce.get('note'))})")
    if rec is None:
        return
    print(f"  [LLM] funnel_stage={rec.data.get('funnel_stage')} "
          f"waiting_entry={rec.data.get('waiting_entry')}")
    sc_text = rec.data.get("stage_scenario")
    if sc_text:
        print(f"  [LLM 시나리오] {sc_text}")
    # 감사: waiting_entry 가 진입존/메뉴 후보 내인가(환각 0 확인).
    we = rec.data.get("waiting_entry")
    if we and zone:
        prices = [z["price"] for z in zone] + [c.price for c in menu.support_levels]
        bound = any(abs(float(we) - p) <= 0.03 * float(we) for p in prices if p)
        print(f"  [감사] waiting_entry={we} → 진입존/메뉴 후보 내={bound}")


_TRACK_ID = {"A": "track_a", "B": "track_b"}


async def main() -> None:
    get_config()
    tickers = sys.argv[1:] or _DEFAULT
    from collectors.snapshot import build_market_snapshot

    print("=== 2단계 매수대기 단계 라이브 (실 Gemini) ===")
    snapshot, _ = await build_market_snapshot()
    for t in tickers:
        try:
            await _run_one(t, "A", snapshot)
        except Exception as e:  # noqa: BLE001
            print(f"\n##### {t} — 예외: {str(e)[:100]}")


if __name__ == "__main__":
    asyncio.run(main())
