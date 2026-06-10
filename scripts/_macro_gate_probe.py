"""박종훈 frame 게이팅 라이브 probe — 실 prefetch 에서 변곡점 지침 부착 확인.

실 DB·실 Gemini (track_a 풀세트 분석가 6명 1회 호출). 확인 항목:
  1. wealth_strategist entry 에 macro_inflection 플래그가 붙는가
  2. render 결과에 [거시 frame 사용 지침] 이 (평상시/변곡점) 올바르게 박히는가
usage: uv run python scripts/_macro_gate_probe.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

from collectors.market_macro import is_macro_inflection  # noqa: E402
from core.intent.classifier import IntentClassification  # noqa: E402
from core.intent.router import _prefetch_analysts_for_tracks  # noqa: E402
from core.strategist.run_strategist import render_prefetched_analyst_outputs  # noqa: E402


async def main() -> None:
    flag, reason = is_macro_inflection()
    print(f"[결정론 판정] inflection={flag} — {reason}\n")

    cls = IntentClassification(
        scenario_id=0,  # fallback = track_a 풀세트 6명 (wealth_strategist 포함)
        ticker="005930",
        ticker_display="삼성전자",
        agent_route="track_a",
        analyst_ids=[],
        confidence=1.0,
        manual_fallback_required=False,
        stage="deterministic",
        latency_ms=0,
        raw_input="long: 삼성전자",
    )
    entries = await _prefetch_analysts_for_tracks(
        ["track_a"],
        classification=cls,
        messages=[{"role": "user", "content": "long: 삼성전자"}],
        provider="gemini",
    )
    ws = [e for e in entries if e["id"] == "wealth_strategist"]
    print(f"[prefetch] 분석가 {len(entries)}명 — wealth_strategist entry: {bool(ws)}")
    if ws:
        print(f"[entry 플래그] macro_inflection = {ws[0].get('macro_inflection')}")

    md = render_prefetched_analyst_outputs(entries)
    directive = [l for l in md.splitlines() if "거시 frame 사용 지침" in l]
    print(f"\n[렌더 지침] {'부착됨' if directive else '❌ 미부착'}")
    for line in directive:
        print(f"  {line}")


if __name__ == "__main__":
    asyncio.run(main())
