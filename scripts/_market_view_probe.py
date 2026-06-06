"""MARKET-VIEW-SYNTHESIS-001 라이브 검증 프로브 (서버/브라우저 없이 실 코드 경로 직접 구동).

NOT a pytest — 실 데이터(KIS/chart) + 실 LLM(Gemini flash-lite, provider 고정) 호출. TESTING=1 금지.

흐름:
  [A] 실 데이터로 build_market_view → 오늘 regime/섹터RS/순환매/진입자세/한줄 산출 (첫날 rotation=none graceful)
  [B] 다일 누적 시뮬: 7일 전 synthetic prev 스냅샷 seed → force rebuild → 순환매 발생 → 실 Gemini 크로스체크
  [C] render_market_view_md = market_state_analyzer 가 받을 [7] 블록
  [D] formatter prepend = 모든 답변 머리 1줄 (DB 캐시 read)
  [E] cleanup: synthetic prev 행만 삭제 (오늘 실 스냅샷은 보존 = 일일 refresh)
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
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
    from collectors import market_view as mv
    from collectors.market_view import build_market_view, render_market_view_md
    from collectors.sector_rs import SectorRS, persist_sector_rs, load_sector_rs_snapshot
    from core.db import get_db

    today = mv._today_kst_str()

    hr("[A] 실 데이터 build_market_view (오늘, 첫 실행 — rotation graceful)")
    view = await build_market_view("KOSPI", force_refresh=True)
    print(f"date={view.date}  market={view.market}  source={view.source}")
    print(f"regime         = {view.regime}")
    print(f"entry_posture  = {view.entry_posture}  (confidence {view.confidence})")
    print(f"leading_sectors= {[(s['sector'], s['rs_score']) for s in view.leading_sectors]}")
    print(f"rotation       = {view.rotation.direction}  "
          f"(strength={view.rotation.strength}, method={view.rotation.method}, agreement={view.rotation.agreement})")
    print(f"ONE-LINER      → {view.one_liner}")
    print("reasons:")
    for r in view.reasons:
        print(f"  - {r}")

    today_rs = load_sector_rs_snapshot(today, "KOSPI")
    print(f"\n[관찰] 오늘 실 섹터 RS {len(today_rs)}종 적재. 상위 5:")
    for r in today_rs[:5]:
        print(f"  {r.sector:<14} rs={r.rs_score:>5}  (60일 {r.return_60d:+.1f}% vs KOSPI {r.kospi_return_60d:+.1f}%)")

    hr("[B] 다일 누적 시뮬 + 실 Gemini 크로스체크 (7일 전 prev seed → 순환매 발생)")
    # 오늘 실 RS 하위권 2종을 7일 전엔 상위권이었다고 seed → 강한 유입 방향 생성
    if len(today_rs) >= 4:
        prev_date = (date.fromisoformat(today) - timedelta(days=7)).isoformat()
        # synthetic prev: 오늘 상위 2종은 7일전 낮았고(=유입), 오늘 하위 2종은 7일전 높았다(=유출)
        seeded: list[SectorRS] = []
        for r in today_rs:
            seeded.append(SectorRS(sector=r.sector, etf_ticker=r.etf_ticker,
                                   rs_score=r.rs_score, return_60d=r.return_60d,
                                   kospi_return_60d=r.kospi_return_60d, rs_ratio=r.rs_ratio))
        top2 = today_rs[:2]
        bot2 = today_rs[-2:]
        smap = {s.sector: s for s in seeded}
        for r in top2:
            smap[r.sector].rs_score = max(0.0, r.rs_score - 3.0)   # 7일전엔 3점 낮았다 → +3 유입
        for r in bot2:
            smap[r.sector].rs_score = min(10.0, r.rs_score + 3.0)  # 7일전엔 3점 높았다 → -3 유출
        persist_sector_rs(prev_date, "KOSPI", seeded)
        print(f"seed prev({prev_date}): {top2[0].sector}/{top2[1].sector} ↑유입, {bot2[0].sector}/{bot2[1].sector} ↓유출 가정")

        print("\n→ build_market_view force_refresh (rotation 발생 → 실 Gemini flash-lite 크로스체크 호출)...")
        view2 = await build_market_view("KOSPI", force_refresh=True, cross_check=True)
        print(f"rotation       = {view2.rotation.direction}")
        print(f"  strength     = {view2.rotation.strength}")
        print(f"  to_sectors   = {view2.rotation.to_sectors}")
        print(f"  from_sectors = {view2.rotation.from_sectors}")
        print(f"  method       = {view2.rotation.method}   ← hybrid 면 실 LLM 크로스체크 완료")
        print(f"  agreement    = {view2.rotation.agreement}  ← agree/disagree = LLM 검증 결과")
        print(f"  confidence   = {view2.confidence}")
        print(f"ONE-LINER      → {view2.one_liner}")
        print("reasons:")
        for r in view2.reasons:
            print(f"  - {r}")

        hr("[C] render_market_view_md — market_state_analyzer 가 받는 [7] 블록 (실제)")
        print(render_market_view_md(view2))
    else:
        view2 = view
        print("섹터 RS 종목 부족 — 크로스체크 시뮬 skip")

    hr("[D] formatter prepend — 모든 답변 머리 1줄 (DB 캐시 read, 비용 0)")
    from core.intent.formatter import _market_view_prefix
    prefix = _market_view_prefix()
    print(f"prefix(raw) = {prefix!r}")
    sample_answer = "삼성전자는 지금 추격보다 분할 접근이 좋아 보여요."
    print("\n[사용자 답변 예시 — prepend 적용된 최종 모습]")
    print(prefix + sample_answer)

    hr("[E] cleanup — synthetic prev 행만 삭제 (오늘 실 스냅샷은 일일 refresh 로 보존)")
    db = get_db()
    if len(today_rs) >= 4:
        prev_date = (date.fromisoformat(today) - timedelta(days=7)).isoformat()
        with db.connect() as conn:
            conn.execute("DELETE FROM sector_rs_snapshot WHERE date=? AND market='KOSPI'", (prev_date,))
        print(f"deleted synthetic prev snapshot ({prev_date}).")
    mvrow = db.fetch_one("SELECT date, regime, entry_posture, one_liner FROM market_view_snapshot WHERE date=? AND market='KOSPI'", (today,))
    print(f"보존된 오늘 market_view_snapshot: {dict(mvrow) if mvrow else None}")


if __name__ == "__main__":
    asyncio.run(main())
