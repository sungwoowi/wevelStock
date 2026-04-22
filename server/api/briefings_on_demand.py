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

from fastapi import APIRouter, HTTPException, Query

from core.briefing import (
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
    force: bool = Query(True, description="true=새 run 실행 (default)"),
    cache: bool = Query(False, description="true=최근 run 재사용"),
) -> BriefingResponse:
    """`cache=true` → 최근 run 재사용. 기본 `force=true` → 새 run 실행."""
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
        pipeline_result = await runner.run(manifest, run_id=run_id)

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

        response = BriefingResponse.build(
            pipeline_id=pipeline_id,
            run_id=run_id,
            parts=parts,
            status=status,
            cache_hit=False,
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
