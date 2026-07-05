"""NEWS-EVENT-INTERPRETATION-001 리플레이 데모 — 메타발 06-23~07-04 격상 레인 재현.

읽기 전용 (persist=False) · 기본 LLM 0 (격상 감지 = 결정론). 실 DB 의 라벨링된 기사로
"그날 시스템이 어떤 이벤트를 중심 이벤트로 격상했을 것인가"를 cutoff 재현.

--interpret YYYY-MM-DD 를 주면 그 날짜의 첫 격상 이벤트 1건만 실 LLM 해석 probe
(Flash 1콜, 캐시 저장·원장 라벨 news_interpretation 기록 — 수용 기준 1·6 검증).
"""
from __future__ import annotations

import asyncio
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from collectors.news_source import build_news_digest, interpret_elevated_events

DATES = [f"2026-06-{d:02d}" for d in range(23, 31)] + [f"2026-07-{d:02d}" for d in range(1, 5)]


def replay_detection() -> dict[str, list[dict]]:
    """일자별 격상 이벤트 결정론 재현 (읽기 전용)."""
    out: dict[str, list[dict]] = {}
    print(f"{'날짜':<12}{'격상':<4} 이벤트 (사유 · 출처수 · 대표 기사)")
    print("-" * 110)
    for date in DATES:
        digest = build_news_digest(date, persist=False)
        events = digest.elevated_events
        out[date] = events
        if not events:
            print(f"{date:<12}{0:<6}—")
            continue
        for i, ev in enumerate(events):
            head = f"{date:<12}{len(events):<6}" if i == 0 else " " * 18
            titles = " / ".join((ev.get("trigger_titles") or [])[:2])
            print(
                f"{head}[{ev['elevated_by']}] {ev['theme']} "
                f"(출처 {ev['source_count']}곳, mag{ev['max_magnitude']}) — {titles[:60]}"
            )
    return out


async def probe_interpretation(date: str, events: list[dict]) -> None:
    """첫 격상 이벤트 1건 실 LLM 해석 probe."""
    if not events:
        print(f"\n{date}: 격상 이벤트 없음 — 해석 probe 생략")
        return
    from server.schedulers.jobs.news_ingest import _interpretation_market_context

    target = [events[0]]
    ctx = _interpretation_market_context(date)
    print(f"\n=== 해석 probe (실 LLM 1콜): {date} / {target[0]['theme']} ===")
    print(f"시장 컨텍스트 주입: {'있음' if ctx else '없음(판단 불가 지시)'}")
    await interpret_elevated_events(target, date=date, market_context_md=ctx)
    interp = target[0].get("interpretation")
    if interp is None:
        print("해석 실패 (graceful — 로그 참조)")
        return
    print(json.dumps(interp, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    detected = replay_detection()
    if "--interpret" in sys.argv:
        idx = sys.argv.index("--interpret")
        date = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else "2026-06-27"
        asyncio.run(probe_interpretation(date, detected.get(date, [])))
