"""INFRA-US-MACRO-SNAPSHOT-001 라이브 검증 프로브 (서버/브라우저 없이 실 코드 경로 직접 구동).

NOT a pytest — 실 yfinance(미장 야간 6 지표) 호출. TESTING=1 금지.

흐름:
  [A] capability 체크 (yfinance import)
  [B] 실 compute_us_macro → 미장 6 지표 fetch + risk-on/off 분류 + us_macro_snapshot upsert
  [C] 흡수 실증 — build_market_view(KOSPI) → entry_posture 강등·게이트 + one_liner 미장 토큰
  [D] render — market_state_analyzer 가 받는 [7] 블록의 '미장 야간' 라인
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def hr(t: str) -> None:
    print("\n" + "=" * 70 + f"\n{t}\n" + "=" * 70)


async def main() -> None:
    hr("[A] capability 체크 — yfinance import")
    try:
        import yfinance  # noqa: F401
        print("yfinance OK")
    except ImportError:
        print("yfinance 미설치 — probe 는 source=unavailable graceful 만 확인 가능")

    from collectors.us_macro import (
        compute_us_macro,
        render_us_macro_md,
        us_macro_metadata,
    )

    hr("[B] 실 compute_us_macro — 미장 야간 fetch + risk-on/off 분류 + upsert")
    snap = await compute_us_macro(force_refresh=True)
    print(f"date={snap.date}  source={snap.source}")
    print(f"risk_signal = {snap.risk_signal}   signal_score = {snap.signal_score}   extreme = {snap.extreme}")
    print(f"나스닥 {snap.nasdaq_change_pct}  S&P {snap.sp500_change_pct}  필반 {snap.sox_change_pct}")
    print(f"VIX {snap.vix} ({snap.vix_change_pct}%)  달러 {snap.dxy} ({snap.dxy_change_pct}%)")
    print(f"미10년물 {snap.us_10y}% ({snap.us_10y_change_bp}bp)  금 {snap.gold_change_pct}%")
    print("reasons:")
    for r in snap.reasons:
        print(f"  - {r}")
    print(f"metadata = {us_macro_metadata(snap)}")

    hr("[C] 흡수 실증 — build_market_view(KOSPI) 가 us_macro 흡수 (강등·게이트 + one_liner 토큰)")
    from collectors.market_view import build_market_view

    view = await build_market_view("KOSPI", force_refresh=True)
    print(f"regime        = {view.regime}")
    print(f"entry_posture = {view.entry_posture}   (미장 {snap.risk_signal}/{snap.extreme} 반영 여부 확인)")
    print(f"ONE-LINER     → {view.one_liner}")
    print("reasons (미장 줄 포함 확인):")
    for r in view.reasons:
        print(f"  - {r}")

    hr("[D] render — market_state_analyzer [7] 블록의 '미장 야간' 라인")
    if snap.source != "unavailable":
        print(render_us_macro_md(snap))
    else:
        print("미장 야간 데이터 없음 (unavailable) — 라인 생략 graceful 동작")


if __name__ == "__main__":
    asyncio.run(main())
