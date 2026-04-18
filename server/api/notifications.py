"""Recent notifications endpoint for the dashboard."""
from __future__ import annotations

from fastapi import APIRouter

from core.db import get_db

router = APIRouter()


@router.get("/notifications/recent")
async def recent_notifications(limit: int = 20) -> dict:
    db = get_db()
    rows = db.fetch_all(
        """
        SELECT id, team_id, level, title, body, channel, delivered,
               related_run_id, related_target, created_at
        FROM notifications_log
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return {"notifications": [dict(r) for r in rows]}
