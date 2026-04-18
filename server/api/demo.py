"""Demo trigger endpoint — runs orchestrator on a given scenario."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from teams.orchestrator.src.agent import Agent as Orchestrator

router = APIRouter()


@router.post("/demo/run")
async def run_demo(scenario: str = "over-allocation") -> dict:
    valid_scenarios = {"normal", "over-allocation", "no-stop-loss", "emotional"}
    if scenario not in valid_scenarios:
        raise HTTPException(
            status_code=400,
            detail=f"scenario must be one of {sorted(valid_scenarios)}",
        )
    run_id = f"{datetime.now(timezone.utc).isoformat()}#demo-{uuid4().hex[:8]}"
    orch = Orchestrator()
    out = await orch.run({"run_id": run_id, "scenario": scenario})
    return out.model_dump()
