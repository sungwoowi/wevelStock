"""실 render_overnight 간밤시황 텔레그램 발송 (INFRA-MARKET-ASSETS-002 최종 검증).

NOT a pytest — 실 yfinance/KIS/CNN + 실 텔레그램. 실제 브리핑과 동일 렌더 경로
(collect_overnight_us 가 만드는 data dict 그대로 → render_overnight).
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


async def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()

    from collectors.fear_greed import fetch_fear_greed
    from collectors.kr_futures import fetch_night_futures
    from collectors.us_markets import fetch_overnight
    from core.briefing.render import render_overnight
    from core.notification.service import notify

    # collect_overnight_us 와 동일하게 data dict 구성
    raw = await fetch_overnight()
    raw["fear_greed"] = await fetch_fear_greed()
    indices_keys = {"nasdaq", "sp500", "sox", "vix", "fear_greed", "nq_futures", "es_futures"}
    overnight_us = {k: raw[k] for k in indices_keys if k in raw}
    macro = {k: raw[k] for k in ("dxy", "usdkrw", "us_10y", "gold", "wti", "brent") if k in raw}
    night_futures = await fetch_night_futures()

    data = {"overnight_us": overnight_us, "macro": macro, "night_futures": night_futures}
    body = render_overnight(data)

    print("─── 발송할 간밤시황 ───")
    print(body)
    print("───────────────────────")

    result = await notify(
        team_id="market_briefing_now",
        level="info",
        title="🌙 간밤시황 (야간선물·야간자산 반영 검증)",
        body=body,
        notification_type="market_briefing",
    )
    print(f"\n발송 결과: channel={result.get('channel')}  telegram_ok={result.get('telegram_ok')}")


if __name__ == "__main__":
    asyncio.run(main())
