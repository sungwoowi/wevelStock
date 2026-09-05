"""chart_ohlcv refresh job (INFRA-CHART-DATA-001).

평일 18:00 KST = **증분** (마지막 보유 봉 이후만) / 주 1회 = **전체 재적재**.
자세한 로직은 `collectors.charts.refresh_all_tickers`.

두 모드로 나눈 이유 (2026-08-15):
  - 증분만으로 충분하지 않다. 액면분할·유상증자가 나면 **과거 봉의 수정주가가 통째로**
    바뀌는데, 증분은 새 봉만 받으므로 옛 값이 그대로 남아 조용히 틀린 차트가 된다.
  - 반대로 매일 전체를 받는 건 낭비였다. 종목당 1,825봉 = 19 페이징 × 1.1초 ≈ 22초,
    200종이면 73분. 그래서 18:00 갱신이 19:15에야 끝나 18:00 판세·18:05 자동 권고가
    **갱신 중인 차트**를 읽었다.
그래서 평일은 증분(≈4분), 장이 없는 일요일에 전체를 다시 받아 수정주가를 맞춘다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from core.logging import get_logger

log = get_logger(__name__)


def _should_run_full(now: datetime | None = None) -> bool:
    """오늘이 전체 재적재 요일인가 (config `chart_refresh.full_refresh_weekday`)."""
    from collectors.screening import get_chart_refresh_config

    today = (now or datetime.now(ZoneInfo("Asia/Seoul"))).weekday()
    return today == int(get_chart_refresh_config()["full_refresh_weekday"])


async def run_chart_refresh() -> dict[str, Any]:
    """cron entrypoint. 요일에 따라 증분/전체를 스스로 고른다."""
    from collectors.charts import refresh_all_tickers

    full = _should_run_full()
    log.info("chart_refresh_cron_start", mode="full" if full else "incremental")
    try:
        result = await refresh_all_tickers(full=full)
        log.info(
            "chart_refresh_cron_done",
            mode=result.get("mode"),
            refreshed=len(result.get("refreshed", [])),
            failed=len(result.get("failed", [])),
            bars_requested=result.get("bars_requested"),
            elapsed_s=result.get("elapsed_s"),
        )
        return result
    except Exception as e:  # noqa: BLE001
        log.exception("chart_refresh_cron_failed", error=str(e))
        return {"refreshed": [], "failed": [], "error": str(e)}
