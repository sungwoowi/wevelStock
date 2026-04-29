"""briefings-on-demand v1 — 스케줄 파이프라인 파트 조회/재실행/재전송.

텔레그램 봇 + 웹앱이 공통으로 소비하는 REST API.
계약: `briefing-part-v1` (core/contracts/briefing_part.py)

Endpoints:
  GET  /api/briefings/{pipeline_id}/latest
  GET  /api/briefings/{pipeline_id}/latest/parts/{key}
  POST /api/briefings/{pipeline_id}/run   [?force=true&cache=false]
  POST /api/briefings/{pipeline_id}/resend [?channel=telegram&part_key=all&run_id=...]
"""
from __future__ import annotations

import asyncio
import secrets
import time
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

from core.briefing import (
    get_last_run_before,
    get_latest_parts,
    get_latest_parts_with_age,
    get_parts_by_run,
    render_morning_pre,
)
from core.contracts.briefing_part import (
    BriefingResendResponse,
    BriefingResponse,
    BriefingStatus,
)
from core.logging import get_logger
from core.notification import notify
from pipelines._base import PipelineRunner
from pipelines._registry import get_pipeline

log = get_logger(__name__)

router = APIRouter(prefix="/briefings")

# ----------------------------------------------------------------------------
# 60s in-memory TTL cache for /run (동일 pipeline_id+force 반복 호출 보호).
# 프로세스 메모리 기반 — 서버 재시작 시 초기화. DB 백업 불필요.
# 테스트에서 _time_source 를 monkeypatch 하여 시간 건너뛰기 가능.
# ----------------------------------------------------------------------------
_CACHE_TTL_SEC = 60.0
_run_cache: dict[str, tuple[float, BriefingResponse]] = {}
_run_locks: dict[str, asyncio.Lock] = {}


def _time_source() -> float:
    return time.monotonic()


_KST = ZoneInfo("Asia/Seoul")


def _now_kst() -> datetime:
    """KST 기준 현재 시각. 테스트에서 monkeypatch 포인트."""
    return datetime.now(_KST)


def _cache_key(pipeline_id: str, force: bool) -> str:
    return f"{pipeline_id}:force={force}"


def _cache_get(key: str) -> BriefingResponse | None:
    entry = _run_cache.get(key)
    if entry is None:
        return None
    ts, resp = entry
    if _time_source() - ts > _CACHE_TTL_SEC:
        _run_cache.pop(key, None)
        return None
    return resp.model_copy(update={"cache_hit": True})


def _cache_set(key: str, resp: BriefingResponse) -> None:
    _run_cache[key] = (_time_source(), resp)


def _db_cache_get(pipeline_id: str) -> BriefingResponse | None:
    """DB 레벨 중복 방지 — briefing_parts 의 최근 run 이 TTL 이내면 재사용.

    in-memory `_run_cache` 는 프로세스 로컬이라 서버 재기동 시 초기화되고
    다중 인스턴스 환경에서는 공유 안 됨. 이 함수가 공유 DB 를 통해
    cross-process 중복을 잡아줌.
    """
    latest = get_latest_parts_with_age(pipeline_id)
    if latest is None:
        return None
    run_id, parts, age_sec = latest
    if age_sec > _CACHE_TTL_SEC:
        return None
    return BriefingResponse.build(
        pipeline_id=pipeline_id,
        run_id=run_id,
        parts=parts,
        cache_hit=True,
    )


def _determine_status(metadata: dict[str, Any] | None) -> BriefingStatus:
    """analyze metadata.model 에 '-mock' suffix 가 붙어 있으면 degraded."""
    model = (metadata or {}).get("model") or ""
    return "degraded" if "-mock" in str(model) else "ok"


def _extract_analyze_metadata(pipeline_result) -> dict[str, Any]:
    analyze = pipeline_result.stages.get("analyze")
    if analyze is None:
        return {}
    meta = analyze.data.get("metadata") if isinstance(analyze.data, dict) else None
    return meta or {}


# ----------------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------------

@router.get("/{pipeline_id}/latest", response_model=BriefingResponse)
async def briefing_latest(pipeline_id: str) -> BriefingResponse:
    """가장 최근 run 의 파트 전체."""
    latest = get_latest_parts(pipeline_id)
    if latest is None:
        raise HTTPException(
            status_code=404,
            detail=f"No briefing_parts for pipeline_id={pipeline_id}",
        )
    run_id, parts = latest
    return BriefingResponse.build(
        pipeline_id=pipeline_id,
        run_id=run_id,
        parts=parts,
    )


@router.get("/{pipeline_id}/latest/parts/{key}")
async def briefing_latest_part(pipeline_id: str, key: str) -> dict[str, Any]:
    """단일 파트 조회 — `parts` 대신 단일 객체 반환."""
    latest = get_latest_parts(pipeline_id)
    if latest is None:
        raise HTTPException(
            status_code=404,
            detail=f"No briefing_parts for pipeline_id={pipeline_id}",
        )
    run_id, parts = latest
    match = next((p for p in parts if p.key == key), None)
    if match is None:
        raise HTTPException(
            status_code=404,
            detail=f"Part key={key} not found in latest run={run_id}",
        )
    return {
        "pipeline_id": pipeline_id,
        "run_id": run_id,
        "key": match.key,
        "label": match.label,
        "order": match.order,
        "data": match.data,
    }


@router.post("/{pipeline_id}/run", response_model=BriefingResponse)
async def briefing_run(
    pipeline_id: str,
    force: bool = Query(
        False,
        description="true=LLM 실시간 실행, 09:00 이후 보관본 분기 우회",
    ),
    cache: bool = Query(False, description="true=최근 run 재사용"),
    notify: bool = Query(
        True,
        description="false=파이프라인 내부 notify stage 스킵 (봇이 자체 렌더링하는 경로)",
    ),
) -> BriefingResponse:
    """기본: 09:00 이후 morning_pre 는 당일 아침 보관본 반환 / `cache=true` → 최근 run / `force=true` → 실시간 실행."""
    if cache:
        latest = get_latest_parts(pipeline_id)
        if latest is None:
            raise HTTPException(
                status_code=404,
                detail=f"No cached run for pipeline_id={pipeline_id}",
            )
        run_id, parts = latest
        return BriefingResponse.build(
            pipeline_id=pipeline_id,
            run_id=run_id,
            parts=parts,
            cache_hit=True,
        )

    # market_briefing: 장 시작 전 (09:00 KST 이전) — 거부 대신 fallback 응답.
    # 사용자 의도 (2026-04-30): 새벽·휴장에도 가장 최근 시장 정보를 받고 싶음.
    #
    # fallback1) DB 의 가장 최근 market_briefing_now run 을 재사용 (KIS 호출 0)
    # fallback2) DB miss 면 정상 흐름으로 떨어져 KIS 새 run 생성
    #            (KIS 는 새벽이라도 직전 영업일 종가 반환).
    #
    # `force=True` 는 fallback 우회 + 새 KIS run 강제 (사용자가 직전 보관본의
    # 데이터 누락·갱신 등을 의심해 명시적 새 호출 요청한 경우).
    # 어느 쪽이든 응답 build 시점에서 note="market_closed" 부착 (아래 build 로직).
    # cache 레이어 앞에 배치 — 직전 force=true 로 생성된 post-09:00 run 이
    # 60s cache 에 남아 09:00 이전 호출에 새는 것 방지.
    if pipeline_id == "market_briefing_now" and not force:
        now_kst = _now_kst()
        if now_kst.hour < 9:
            latest = get_latest_parts("market_briefing_now")
            if latest is not None:
                snap_run_id, snap_parts = latest
                log.info(
                    "market_briefing_fallback_db",
                    run_id=snap_run_id,
                    now_kst=now_kst.isoformat(),
                )
                return BriefingResponse.build(
                    pipeline_id=pipeline_id,
                    run_id=snap_run_id,
                    parts=snap_parts,
                    cache_hit=True,
                    note="market_closed",
                )
            # DB miss → 정상 흐름 (cache → runner) 로 떨어짐. note 는 build 시 부착.

    # 장전 브리핑은 09:00 KST 이후엔 당일 아침 보관본 재전송 — LLM 재실행 방지.
    # `force=true` 는 우회 (수동 LLM 실행. 서버 다운 등으로 아침 cron 놓친 경우).
    # cache 레이어 앞에 배치 — force=true 로 방금 생성한 post-09:00 run 이
    # 60s cache 에 남아 force=false 호출에 새는 것 방지.
    if pipeline_id == "market_briefing_pre" and not force:
        now_kst = _now_kst()
        if now_kst.hour >= 9:
            today_midnight_kst = now_kst.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            today_9am_kst = now_kst.replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            today_start_utc = today_midnight_kst.astimezone(
                timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S")
            cutoff_utc = today_9am_kst.astimezone(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            snapshot = get_last_run_before(
                "market_briefing_pre", cutoff_utc, since_iso=today_start_utc
            )
            if snapshot is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "오늘 09:00 이전 장전 브리핑 보관본이 없습니다. "
                        "force=true 로 실시간 실행 가능."
                    ),
                )
            snap_run_id, snap_parts = snapshot
            log.info(
                "briefing_run_preserved_snapshot",
                pipeline=pipeline_id,
                run_id=snap_run_id,
                now_kst=now_kst.isoformat(),
            )
            return BriefingResponse.build(
                pipeline_id=pipeline_id,
                run_id=snap_run_id,
                parts=snap_parts,
                cache_hit=True,
                note="before_market_open",
            )

    key = _cache_key(pipeline_id, force)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    # DB 레벨 중복 방지 — 다른 서버 프로세스/재기동 직후에도 최근 run 재사용.
    db_cached = _db_cache_get(pipeline_id)
    if db_cached is not None:
        return db_cached

    manifest = get_pipeline(pipeline_id)
    if manifest is None:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline not found: {pipeline_id}",
        )

    # 같은 pipeline_id 에 대한 동시 요청 직렬화 — 중복 LLM 호출 방지.
    lock = _run_locks.setdefault(pipeline_id, asyncio.Lock())
    async with lock:
        cached = _cache_get(key)
        if cached is not None:
            return cached
        db_cached = _db_cache_get(pipeline_id)
        if db_cached is not None:
            return db_cached

        run_id = (
            datetime.now(timezone.utc).astimezone().isoformat()
            + f"#manual-{secrets.token_hex(3)}"
        )
        runner = PipelineRunner()
        pipeline_result = await runner.run(
            manifest,
            run_id=run_id,
            input_data={"skip_notify": not notify},
        )

        if pipeline_result.errors:
            log.error(
                "briefing_run_stage_errors",
                pipeline=pipeline_id,
                errors=pipeline_result.errors,
            )

        parts = get_parts_by_run(pipeline_id, run_id)
        if not parts:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Pipeline executed but no briefing_parts persisted "
                    f"(run_id={run_id})"
                ),
            )

        status = _determine_status(_extract_analyze_metadata(pipeline_result))

        # market_briefing 시각별 note:
        #   < 09:00         → "market_closed"        (휴장·새벽 — fallback DB miss 경로)
        #   09:00 ~ 09:19   → "market_briefing_early" (장 개시 직후 신뢰도 낮음)
        #   09:20 ~         → None (정상)
        note: str | None = None
        if pipeline_id == "market_briefing_now":
            now_kst = _now_kst()
            if now_kst.hour < 9:
                note = "market_closed"
            elif now_kst.hour == 9 and now_kst.minute < 20:
                note = "market_briefing_early"

        response = BriefingResponse.build(
            pipeline_id=pipeline_id,
            run_id=run_id,
            parts=parts,
            status=status,
            cache_hit=False,
            note=note,
        )
        _cache_set(key, response)
        return response


@router.post("/{pipeline_id}/resend", response_model=BriefingResendResponse)
async def briefing_resend(
    pipeline_id: str,
    channel: str = Query("telegram"),
    part_key: str = Query("all", description="all | overnight | scenario | ..."),
    run_id: str | None = Query(None, description="생략 시 latest"),
) -> BriefingResendResponse:
    """기존 run 을 채널로 재전송. 캐시 없이 항상 DB 직조회."""
    if channel != "telegram":
        raise HTTPException(
            status_code=400, detail=f"Unsupported channel: {channel}"
        )

    if run_id is None:
        latest = get_latest_parts(pipeline_id)
        if latest is None:
            raise HTTPException(
                status_code=404,
                detail=f"No briefing to resend for pipeline_id={pipeline_id}",
            )
        run_id, parts = latest
    else:
        parts = get_parts_by_run(pipeline_id, run_id)
        if not parts:
            raise HTTPException(
                status_code=404,
                detail=f"No parts for run_id={run_id}",
            )

    if part_key != "all":
        parts = [p for p in parts if p.key == part_key]
        if not parts:
            raise HTTPException(
                status_code=404,
                detail=f"Part key={part_key} not found for run_id={run_id}",
            )

    texts = render_morning_pre(parts, status="ok")
    total = len(texts)
    for idx, (part, text) in enumerate(zip(parts, texts), 1):
        await notify(
            team_id=pipeline_id,
            level="info",
            title=f"[resend] {part.label} {idx}/{total}",
            body=text,
            related_run_id=run_id,
            related_target="global",
        )

    return BriefingResendResponse(
        pipeline_id=pipeline_id,
        run_id=run_id,
        delivered=["telegram"],
    )
