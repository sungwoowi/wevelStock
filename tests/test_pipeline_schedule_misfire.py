"""스케줄 misfire 내성 (2026-07-06 시황 브리핑 3연속 스킵 사고 + 08-13 차트 갱신 전멸).

2026-06-15 절전 사고 보강이 infra 잡(auto_signal·daily_refresh)에만 적용되고
loader.py 파이프라인 잡은 기본 misfire_grace_time=1초로 남아 있던 빈틈 —
이벤트 루프가 발화 정각에 1초만 바빠도(차트 캐치업 22s 청크·BGE 배치·전략가 호출)
영구 스킵. market_briefing_now 09:30/12:30/14:30 이 하루 3번 전부 침묵한 근본 원인.

**2026-08-13 세 번째 재발**: 07-06 보강도 *일부* 등록 지점만 고쳐서
`infra::chart_ohlcv_refresh`·`fundamentals_refresh`·backup·rollup 3종·memory_cleanup 이
유예 1초로 남아 있었다 → 08-10~08-12 `chart_ohlcv` 갱신 0. 판세의 섹터 RS 가 5일 낡은
차트로 계산됐다. 그래서 이제 **잡을 하나씩 열거하지 않고 전수로 검사**한다 — 새 잡이
유예 없이 추가되면 이 테스트가 즉시 잡는다 (네 번째 재발 차단).
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


def test_all_infra_jobs_registered_with_misfire_tolerance():
    """**전수 검사** — infra 잡 중 유예 없는 잡이 하나라도 있으면 실패.

    잡 이름을 열거하지 않는 게 핵심이다. 07-06 보강이 열거식이라 chart refresh 를
    빠뜨렸고 한 달 뒤 갱신이 통째로 멈췄다. 앞으로 어떤 잡이 추가되든 자동 커버된다.
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from server.schedulers.jobs import register_infra_jobs
    from server.schedulers.jobs.auto_signal import MISFIRE_GRACE_SEC

    sched = AsyncIOScheduler(timezone="Asia/Seoul")
    count = register_infra_jobs(sched)
    assert count >= 5

    jobs = sched.get_jobs()
    assert jobs, "infra 잡 미등록"
    naked = [j.id for j in jobs if j.misfire_grace_time != MISFIRE_GRACE_SEC]
    assert not naked, (
        f"유예 미설정 잡: {naked} — 기본 1초는 절전·루프 stall 에 영구 스킵된다 "
        "(2026-08-13 chart_ohlcv 3일 전멸의 근본 원인). _MISFIRE_KW 를 붙일 것."
    )
    for job in jobs:
        assert job.coalesce is True, f"{job.id}: coalesce 미설정"
        assert job.max_instances == 1, f"{job.id}: max_instances 미설정"
