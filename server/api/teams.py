"""Team registry + latest-output endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.outputs import load_latest
from core.registry import list_all_teams

router = APIRouter()


@router.get("/teams")
async def list_teams() -> dict:
    teams = list_all_teams()
    return {
        "teams": [
            {
                "id": t.id,
                "name": t.name,
                "runtime": t.runtime,
                "status": t.status,
                "depends_on": t.depends_on,
                "schedule": [s.model_dump() for s in t.schedule],
            }
            for t in teams
        ]
    }


@router.get("/teams/{team_id}/latest")
async def latest_output(team_id: str, target: str = "global") -> dict:
    output = load_latest(team_id, target)
    if output is None:
        raise HTTPException(status_code=404, detail=f"No output yet for {team_id}/{target}")
    return output.model_dump()
