"""자동 권고 생성 cron 잡 (AUTO-SIGNAL-GENERATION-001 M3).

평일 4 cadence 에 run_signal_cadence 를 발동 → watchlist 결정론 스크리닝 → 밴드 게이트 →
전략가 직접 호출 → 권고 persist. 사용자 개입 0.

  - 장중: 09:35 / 12:35 / 14:35 (market_briefing_now 09:30/12:30/14:30 스냅샷 갱신 직후 =
    fresh 외인·기관 수급). 본 모듈이 INTRADAY_CADENCES 로 등록(__init__.py).
  - 장마감: 18:05 (postclose) — run_daily_refresh 가 macro·뉴스 후, 데스크 *앞에* 호출
    (데스크가 그날 권고를 체결하도록). 본 모듈의 run_auto_signal_job("postclose").

마스터 스위치 = config signal_gate.auto_run_enabled (false → 전체 no-op, 비용 부담 시 즉시 OFF).
production 경로 = provider="gemini" · mock_fallback_allowed=False (실 배포 모델, silent mock 금지).
"""
from __future__ import annotations

from typing import Any

from core.logging import get_logger

log = get_logger(__name__)

# 장중 cadence (라벨, 시(KST), 분). 시각=스냅샷 갱신 직후. 비활성/조정은 config 마스터 스위치.
INTRADAY_CADENCES: list[tuple[str, int, int]] = [
    ("intraday1", 9, 35),
    ("intraday2", 12, 35),
    ("intraday3", 14, 35),
]


async def run_auto_signal_job(cadence: str = "postclose") -> dict[str, Any]:
    """한 cadence 자동 권고 생성 (cron/daily_refresh 공용 entrypoint). 격리·graceful.

    config 마스터 스위치 OFF → no-op. 예외는 잡 안에서 잡아 다른 잡·데스크를 막지 않음.
    """
    from collectors.screening import get_auto_signal_enabled

    if not get_auto_signal_enabled():
        log.info("auto_signal_disabled", cadence=cadence)
        return {"cadence": cadence, "disabled": True}

    log.info("auto_signal_job_start", cadence=cadence)
    try:
        from core.signal.auto_signal import run_signal_cadence

        summary = await run_signal_cadence(
            cadence=cadence, provider="gemini", mock_fallback_allowed=False
        )
        log.info(
            "auto_signal_job_done",
            cadence=cadence, screened=summary.get("screened"),
            persisted=summary.get("persisted"), buys=summary.get("buys"),
            skipped_band=summary.get("skipped_band"),
        )
        return summary
    except Exception as e:  # noqa: BLE001 — 잡 실패가 cron·데스크를 막지 않음
        log.exception("auto_signal_job_failed", cadence=cadence, error=str(e))
        return {"cadence": cadence, "error": str(e)}
