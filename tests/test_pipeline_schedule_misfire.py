"""파이프라인 스케줄 misfire 내성 (2026-07-06 시황 브리핑 3연속 스킵 사고).

2026-06-15 절전 사고 보강이 infra 잡(auto_signal·daily_refresh)에만 적용되고
loader.py 파이프라인 잡은 기본 misfire_grace_time=1초로 남아 있던 빈틈 —
이벤트 루프가 발화 정각에 1초만 바빠도(차트 캐치업 22s 청크·BGE 배치·전략가 호출)
영구 스킵. market_briefing_now 09:30/12:30/14:30 이 하루 3번 전부 침묵한 근본 원인.
"""
from __future__ import annotations

import os

os.environ.setdefault("TESTING", "1")


def test_pipeline_jobs_registered_with_misfire_tolerance():
    """모든 파이프라인 잡 = grace 1h·coalesce·max_instances=1 (infra 잡과 동일 내성)."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from server.schedulers.jobs.auto_signal import MISFIRE_GRACE_SEC
    from server.schedulers.loader import register_pipeline_schedules

    sched = AsyncIOScheduler(timezone="Asia/Seoul")
    count = register_pipeline_schedules(sched)
    assert count >= 2  # market_briefing_now + market_briefing_pre

    pipeline_jobs = [j for j in sched.get_jobs() if j.id.startswith("pipeline::")]
    assert pipeline_jobs, "파이프라인 잡 미등록"
    for job in pipeline_jobs:
        assert job.misfire_grace_time == MISFIRE_GRACE_SEC, (
            f"{job.id}: misfire_grace_time={job.misfire_grace_time} — 기본 1초는 "
            "루프 정각 stall 에 영구 스킵됨 (2026-07-06 사고)"
        )
        assert job.coalesce is True
        assert job.max_instances == 1
