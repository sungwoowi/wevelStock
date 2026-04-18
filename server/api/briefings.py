"""Briefings API — feed + detail views for the webapp.

Endpoints:
  GET /api/briefings/feed            — list of recent briefings across all pipelines
  GET /api/briefings/{run_id}        — full briefing JSON for one run
  GET /api/briefings/by-pipeline/{pipeline_id}/latest — latest for a specific pipeline

Data source: team_outputs (data_json.briefing) + notifications_log.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)

router = APIRouter()


def _row_to_feed_entry(row) -> dict:
    data = {}
    try:
        data = json.loads(row["data_json"] or "{}")
    except json.JSONDecodeError:
        pass
    briefing = data.get("briefing") if isinstance(data, dict) else None
    scenario = (briefing or {}).get("scenario") or {}
    return {
        "run_id": row["run_id"],
        "pipeline_id": row["team_id"],
        "timestamp": row["timestamp"],
        "verdict": row["verdict"],
        "confidence": row["confidence"],
        "expected_open": scenario.get("expected_open"),
        "bias": scenario.get("bias"),
        "narrative_preview": (scenario.get("narrative") or "")[:200],
    }


@router.get("/briefings/feed")
async def briefings_feed(limit: int = 20, pipeline_id: str | None = None) -> dict:
    """List recent briefings ordered by timestamp DESC."""
    db = get_db()
    if pipeline_id:
        rows = db.fetch_all(
            """
            SELECT run_id, team_id, timestamp, verdict, confidence, data_json
            FROM team_outputs
            WHERE team_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (pipeline_id, limit),
        )
    else:
        rows = db.fetch_all(
            """
            SELECT run_id, team_id, timestamp, verdict, confidence, data_json
            FROM team_outputs
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
    return {"items": [_row_to_feed_entry(r) for r in rows]}


@router.get("/briefings/{run_id}")
async def briefing_detail(run_id: str) -> dict:
    """Return the full briefing JSON for a single run."""
    db = get_db()
    row = db.fetch_one(
        """
        SELECT run_id, team_id, timestamp, verdict, confidence,
               reasons_json, data_json, contract_version
        FROM team_outputs
        WHERE run_id = ?
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (run_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"No briefing for run_id={run_id}")

    try:
        data = json.loads(row["data_json"] or "{}")
    except json.JSONDecodeError:
        data = {}
    try:
        reasons = json.loads(row["reasons_json"] or "[]")
    except json.JSONDecodeError:
        reasons = []

    # Also attach news_items + predictions tied to this run
    news = db.fetch_all(
        """
        SELECT title, url, source, published_at,
               impact_direction, impact_magnitude, impact_note
        FROM news_items WHERE run_id = ?
        """,
        (run_id,),
    )
    preds = db.fetch_all(
        """
        SELECT ticker, prediction_type, prediction, confidence, reason,
               related_trade_id, metadata_json
        FROM predictions WHERE run_id = ?
        """,
        (run_id,),
    )

    return {
        "run_id": row["run_id"],
        "pipeline_id": row["team_id"],
        "timestamp": row["timestamp"],
        "verdict": row["verdict"],
        "confidence": row["confidence"],
        "reasons": reasons,
        "briefing": data.get("briefing") or data,
        "news_items": [dict(r) for r in news],
        "predictions": [dict(r) for r in preds],
    }


@router.get("/briefings/by-pipeline/{pipeline_id}/latest")
async def briefing_latest(pipeline_id: str) -> dict:
    """Return the latest briefing for one pipeline."""
    db = get_db()
    row = db.fetch_one(
        """
        SELECT run_id FROM team_outputs
        WHERE team_id = ?
        ORDER BY timestamp DESC LIMIT 1
        """,
        (pipeline_id,),
    )
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"No briefing for pipeline={pipeline_id}",
        )
    return await briefing_detail(row["run_id"])
