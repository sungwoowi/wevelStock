"""Recent notifications endpoint for the dashboard.

INFRA-MARKET-ASSETS-002 (notification-persistence-v1):
- GET /notifications/recent — notification_type·is_read 노출 + unread_count (종 배지 소스).
- POST /notifications/mark-read — is_read=1 갱신 (멱등). body {ids:[...]} 또는 {all:true}.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from core.db import get_db

router = APIRouter()


@router.get("/notifications/recent")
async def recent_notifications(limit: int = 20) -> dict:
    db = get_db()
    rows = db.fetch_all(
        """
        SELECT id, team_id, level, title, body, channel, delivered,
               related_run_id, related_target, notification_type, is_read, created_at
        FROM notifications_log
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    unread_row = db.fetch_one(
        "SELECT COUNT(*) AS n FROM notifications_log WHERE is_read = 0"
    )
    unread_count = int(unread_row["n"]) if unread_row else 0
    return {
        "notifications": [dict(r) for r in rows],
        "unread_count": unread_count,
    }


class MarkReadRequest(BaseModel):
    """body {ids:[1,2,...]} 또는 {all:true}. 둘 다면 all 우선."""

    ids: list[int] | None = None
    all: bool = False


@router.post("/notifications/mark-read")
async def mark_notifications_read(req: MarkReadRequest) -> dict:
    """is_read=1 갱신. 멱등 — 이미 읽은 항목 재호출 무해.

    Returns {"updated": <행수>, "unread_count": <남은 미독>}.
    """
    db = get_db()
    if req.all:
        cur = db.execute(
            "UPDATE notifications_log SET is_read = 1 WHERE is_read = 0"
        )
        updated = cur.rowcount if cur.rowcount is not None else 0
    elif req.ids:
        placeholders = ",".join("?" for _ in req.ids)
        cur = db.execute(
            f"UPDATE notifications_log SET is_read = 1 WHERE id IN ({placeholders})",
            tuple(req.ids),
        )
        updated = cur.rowcount if cur.rowcount is not None else 0
    else:
        updated = 0

    unread_row = db.fetch_one(
        "SELECT COUNT(*) AS n FROM notifications_log WHERE is_read = 0"
    )
    unread_count = int(unread_row["n"]) if unread_row else 0
    return {"updated": updated, "unread_count": unread_count}
