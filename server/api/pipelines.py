"""Pipeline API endpoints — list, run, latest output."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from core.logging import get_logger
from core.outputs import load_latest
from pipelines._base import PipelineRunner
from pipelines._registry import get_pipeline, list_all_pipelines

log = get_logger(__name__)

router = APIRouter()


@router.get("/pipelines")
async def list_pipelines() -> dict:
    """List all registered pipelines with status."""
    pipelines = list_all_pipelines()
    return {
        "pipelines": [
            {
                "id": p.id,
                "name": p.name,
                "status": p.status,
                "stages": [s.id for s in p.stages],
                "schedule": p.schedule,
            }
            for p in pipelines
        ]
    }


@router.get("/pipelines/{pipeline_id}/latest")
async def pipeline_latest(pipeline_id: str, target: str = "global") -> dict:
    """Get the latest output for a pipeline."""
    output = load_latest(pipeline_id, target)
    if output is None:
        raise HTTPException(
            status_code=404,
            detail=f"No output yet for pipeline {pipeline_id}",
        )
    return output.model_dump()


@router.post("/pipelines/{pipeline_id}/run")
async def run_pipeline(pipeline_id: str) -> dict:
    """Manually trigger a pipeline run."""
    manifest = get_pipeline(pipeline_id)
    if manifest is None:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline '{pipeline_id}' not found",
        )

    run_id = f"{datetime.now(timezone.utc).isoformat()}#manual-{uuid4().hex[:6]}"
    runner = PipelineRunner()

    log.info("pipeline_manual_trigger", pipeline=pipeline_id, run_id=run_id)
    result = await runner.run(manifest, run_id=run_id)

    return {
        "pipeline_id": result.pipeline_id,
        "run_id": result.run_id,
        "ok": result.ok,
        "final_verdict": result.final_verdict,
        "final_confidence": result.final_confidence,
        "stages": {
            sid: {
                "status": sr.status,
                "verdict": sr.verdict,
                "confidence": sr.confidence,
                "reasons": sr.reasons,
                "error": sr.error,
            }
            for sid, sr in result.stages.items()
        },
        "errors": result.errors,
    }
