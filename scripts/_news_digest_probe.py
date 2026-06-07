"""NEWS-SOURCE-001 MS-D 라이브 검증 프로브 (서버/브라우저 없이 실 코드 경로 직접 구동).

NOT a pytest — 실 RSS 수집(네트워크) + 실 LLM 분류(Gemini flash, provider 고정) 호출. TESTING=1 금지.
`_market_view_probe.py` mirror.

흐름:
  [0] capability 체크 — GOOGLE_AI_API_KEY 없으면 실 분류 불가(capability gap) 명시. RSS 는 시도.
  [A] collect_from_sources([RssNewsSource]) — 실 RSS 헤드라인 수집 (Yahoo/CNBC/Google News)
  [B] classify_news_items — 실 Gemini 분류 (키 있을 때만) → news_source_items upsert
  [C] build_news_digest(market) + render_news_digest_md = news_curator 가 받을 [8] 블록
  [D] build_news_digest(ticker=005930) — 종목 scope catalyst_tilt (buy_score N 블렌드 입력)
  [E] _blend_news_catalyst 실증 — N축 신고가 ⨯ 뉴스 촉매 블렌드

검증 포인트: 키 있으면 라벨 채워짐 + tone≠neutral 가능 / 키 없으면 plumbing 만(라벨 0, tone neutral).
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

PROBE_TICKER = "005930"  # 삼성전자 — 종목 scope catalyst_tilt 실증용


def hr(t: str) -> None:
    print("\n" + "=" * 70 + f"\n{t}\n" + "=" * 70)


async def main() -> None:
    from collectors.market_view import _today_kst_str
    from collectors.news_source import (
        RssNewsSource,
        build_news_digest,
        classify_news_items,
        collect_from_sources,
        render_news_digest_md,
        upsert_news_items,
    )
    from core.config import env

    today = _today_kst_str()
    has_key = bool(env("GOOGLE_AI_API_KEY"))

    hr("[0] capability 체크")
    print(f"오늘(KST)        = {today}")
    print(f"GOOGLE_AI_API_KEY = {has_key}")
    if not has_key:
        print(
            "⚠ 실 LLM 분류 불가 (capability gap): GOOGLE_AI_API_KEY 미설정.\n"
            "  → RSS 수집·digest plumbing 은 검증되지만 라벨은 비고 tone=neutral.\n"
            "  → 실 라벨/톤 검증은 키가 설정된 환경에서 본 프로브 재실행."
        )

    hr("[A] 실 RSS 수집 (collect_from_sources)")
    try:
        items = await collect_from_sources([RssNewsSource()])
    except Exception as e:  # noqa: BLE001
        print(f"⚠ RSS 수집 실패 (네트워크 차단 가능): {type(e).__name__}: {e}")
        items = []
    print(f"수집 {len(items)}건 (dedup 후). 상위 5:")
    for it in items[:5]:
        print(f"  - [{it.source}] {it.title[:70]}")

    hr("[B] classify_news_items (실 Gemini 분류 — 키 있을 때만 라벨 채워짐)")
    if items:
        labeled = await classify_news_items(items)
        n_llm = sum(1 for it in labeled if it.labeled_by == "llm")
        print(f"분류 시도 {len(labeled)}건 → LLM 라벨 성공 {n_llm}건 (나머지 rss_raw 보존).")
        for it in labeled[:5]:
            if it.labeled_by == "llm":
                print(f"  - {it.category}/{it.time_axis} {it.direction}(강도{it.magnitude},확신{it.confidence}%) {it.title[:50]}")
        upsert_news_items(labeled)
        print(f"news_source_items upsert {len(labeled)}건 (url 멱등).")
    else:
        print("수집 0건 → 분류 skip.")

    hr("[C] build_news_digest(market) + render [8] 블록 (news_curator 가 받는 것)")
    market_digest = build_news_digest(today)  # market scope, persist=True
    print(f"source={market_digest.source}  tone={market_digest.tone}  "
          f"themes={[t.get('theme') for t in market_digest.top_themes]}")
    print("\n--- [8] 뉴스 종합 블록 (실제 주입 모습) ---")
    print(render_news_digest_md(market_digest))

    hr(f"[D] build_news_digest(ticker={PROBE_TICKER}) — 종목 scope catalyst_tilt")
    tk_digest = build_news_digest(today, ticker=PROBE_TICKER, persist=False)
    print(f"scope={tk_digest.scope}  source={tk_digest.source}  "
          f"tone={tk_digest.tone}  catalyst_tilt={tk_digest.catalyst_tilt}")

    hr("[E] _blend_news_catalyst 실증 — buy_score N축 (신고가 ⨯ 뉴스 촉매)")
    from collectors.buy_score_inputs import _blend_news_catalyst

    reasons: list[str] = []
    axis = {"n": "charts_52w"}
    n_high = 7.0  # 가상 52주 신고가 점수
    n_blended = _blend_news_catalyst(n_high, PROBE_TICKER, today, axis, reasons)
    print(f"n_high(가정)={n_high} → 블렌드 후 N={n_blended}  (axis_source={axis['n']})")
    for r in reasons:
        print(f"  - {r}")

    hr("요약")
    print(
        f"plumbing: RSS {len(items)}건 → 분류 → market digest(source={market_digest.source}) → "
        f"render [8] → ticker digest → N 블렌드 = 전 경로 구동."
    )
    if not has_key:
        print("⚠ 실 라벨/톤은 capability gap (GOOGLE_AI_API_KEY) — 키 환경에서 재실행 시 verified.")


if __name__ == "__main__":
    asyncio.run(main())
