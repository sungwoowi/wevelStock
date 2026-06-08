"""Infra API endpoints — 수동 트리거 (dev cron 미작동 부채 해소).

서버가 떠 있을 때 웹앱·텔레그램·curl 에서 일일 적재를 즉시 발동. 18:05 cron 과 동일한
run_daily_refresh() 를 호출(단일 호출점). user_want_spec "수동 트리거 모드" 충족.
얇게 — 잡으로 위임(server/CLAUDE.md).
"""
from __future__ import annotations

from fastapi import APIRouter

from core.logging import get_logger
from server.schedulers.jobs.daily_refresh import run_daily_refresh

log = get_logger(__name__)

router = APIRouter(prefix="/infra")


@router.post("/refresh-snapshots")
async def refresh_snapshots() -> dict:
    """일일 적재(macro + 뉴스) 수동 발동. 멱등이라 여러 번 호출 안전. 집계 결과 반환."""
    log.info("infra_refresh_snapshots_manual_trigger")
    result = await run_daily_refresh()
    return result
