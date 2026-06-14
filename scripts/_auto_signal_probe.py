"""AUTO-SIGNAL-GENERATION-001 M5 — 라이브 검증 프로브 (실 Gemini·실 알림).

한 cadence 자동 권고 생성을 실제로 1회 돌려 권고·알림이 멀쩡한지 눈으로 확인한다.
실 KIS(스냅샷·점수) + 실 Gemini(Flash) + 실 알림(텔레그램/파일). 테스트 아님 — production 경로.

usage: uv run python scripts/_auto_signal_probe.py [cadence]
  cadence 기본 = "probe" (실 cron 의 postclose 와 id 충돌 회피). "postclose" 주면 🔵 일일요약도 발화.
"""
from __future__ import annotations

import asyncio
import json
import sys

from core.config import get_config


async def main() -> None:
    get_config()  # dotenv 로드 (env 키 활성화)
    cadence = sys.argv[1] if len(sys.argv) > 1 else "probe"

    from core.signal.auto_signal import run_signal_cadence

    print(f"=== M5 라이브 자동 권고 생성 (cadence={cadence}) ===")
    summary = await run_signal_cadence(
        cadence=cadence, provider="gemini", mock_fallback_allowed=False,
    )
    print("\n--- cadence 요약 ---")
    for k in ("cadence", "as_of", "regime", "watchlist", "screened",
              "evaluated", "persisted", "buys", "sells", "waits", "skipped_band"):
        print(f"  {k}: {summary.get(k)}")

    print("\n--- 종목별 결과 ---")
    for r in summary.get("results", []):
        line = f"  {r.get('ticker')} {r.get('track')}: "
        if r.get("skipped"):
            line += "SKIP(band)"
        elif r.get("persisted"):
            line += f"{r.get('verdict')} → persist {r.get('recommendation_id')}"
        else:
            line += f"미persist ({r.get('reason')})"
        print(line)

    # 실제 DB 영속 확인 (source=auto)
    from core.db import get_db

    rows = get_db().fetch_all(
        "SELECT team_id, target, verdict, confidence, data_json FROM team_outputs "
        "WHERE team_id IN ('track_a','track_b') ORDER BY timestamp DESC LIMIT 10"
    )
    print(f"\n--- team_outputs 최근 track 권고 {len(rows)}건 (DB 확인) ---")
    for row in rows:
        try:
            data = json.loads(row["data_json"])
            src = data.get("source", "?")
            cad = data.get("cadence", "?")
        except Exception:
            src = cad = "?"
        print(f"  [{row['team_id']}] {row['target']} {row['verdict']} "
              f"conf={row['confidence']} src={src} cadence={cad}")


if __name__ == "__main__":
    asyncio.run(main())
