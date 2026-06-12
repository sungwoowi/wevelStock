"""야간선물 실측 텔레그램 발송 (INFRA-MARKET-ASSETS-002 검증).

NOT a pytest — 실 KIS + yfinance + 실 텔레그램 발송. 사용자 명시 요청 시에만.
KOSPI200 야간선물(KIS 실선물) + 미국 야간자산 한글 라벨이 제대로 나가는지 폰으로 확인.
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


def _pct(v) -> str:
    return f"{v:+.2f}%" if v is not None else "—"


async def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()  # 텔레그램 토큰 + KIS 심볼 로드

    from collectors.kr_futures import fetch_night_futures
    from collectors.us_macro import OVERNIGHT_ASSET_LABELS_KR, compute_us_macro
    from core.notification.service import notify

    # 1) KOSPI200 야간선물 (KIS 실선물)
    nf_data = await fetch_night_futures()
    nf = nf_data.get("kospi200_cme_night", {})

    # 2) 미국 야간자산 + 지수 (us_macro)
    snap = await compute_us_macro(force_refresh=True)

    lines: list[str] = []
    lines.append("🌙 야간선물 실측 테스트")
    lines.append("")
    if "error" not in nf and nf.get("change_pct") is not None:
        lines.append(
            f"🔮 KOSPI200 야간선물 {_pct(nf.get('change_pct'))} "
            f"({nf.get('source_kr', nf.get('source'))})"
        )
    else:
        lines.append(f"🔮 KOSPI200 야간선물: 조회 실패 ({nf.get('error', '?')})")
    lines.append("")
    lines.append("🌃 미국 야간자산 (전일 대비)")
    for key, label in OVERNIGHT_ASSET_LABELS_KR.items():
        val = getattr(snap, f"{key}_change_pct", None)
        lines.append(f"  · {label} {_pct(val)}")
    lines.append("")
    lines.append("🇺🇸 미국 지수 (간밤)")
    lines.append(f"  · 나스닥 {_pct(snap.nasdaq_change_pct)}")
    lines.append(f"  · 필반(SOX) {_pct(snap.sox_change_pct)}")
    lines.append(f"  · VIX {snap.vix}")

    body = "\n".join(lines)
    print("─── 발송할 메시지 ───")
    print(body)
    print("────────────────────")

    result = await notify(
        team_id="market_briefing_now",
        level="info",
        title="🌙 야간선물 실측 테스트",
        body=body,
        notification_type="market_briefing",
    )
    print(f"\n발송 결과: channel={result.get('channel')}  "
          f"telegram_ok={result.get('telegram_ok')}  type={result.get('notification_type')}")


if __name__ == "__main__":
    asyncio.run(main())
