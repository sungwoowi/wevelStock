"""Positions API — CRUD for watch_positions (manual user registrations).

Users won't track avg_price/quantity (they don't follow AI advice 1:1).
We only store the ticker + optional watch_price + signal counters that
the market_briefing_pre pipeline increments over time.

Endpoints:
  GET    /api/positions/watch              — list
  POST   /api/positions/watch              — add
  PATCH  /api/positions/watch/{id}         — update (status, watch_price, notes)
  DELETE /api/positions/watch/{id}         — remove (hard delete)

  GET    /api/positions/sim                — AI simulation current positions
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WatchPositionIn(BaseModel):
    ticker: str = Field(..., min_length=1)
    name: str | None = None
    market: str = "KR"   # KR | US
    status: str = "watching"  # watching | holding | closed
    watch_price: float | None = None
    notes: str | None = None


class WatchPositionUpdate(BaseModel):
    name: str | None = None
    market: str | None = None
    status: str | None = None
    watch_price: float | None = None
    notes: str | None = None


@router.get("/positions/watch")
async def list_watch(status: str | None = None) -> dict:
    db = get_db()
    if status:
        rows = db.fetch_all(
            "SELECT * FROM watch_positions WHERE status = ? ORDER BY updated_at DESC, created_at DESC",
            (status,),
        )
    else:
        rows = db.fetch_all(
            "SELECT * FROM watch_positions ORDER BY updated_at DESC, created_at DESC"
        )
    return {"items": [dict(r) for r in rows]}


@router.post("/positions/watch")
async def add_watch(body: WatchPositionIn) -> dict:
    db = get_db()
    try:
        with db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO watch_positions
                    (ticker, name, market, status, watch_price, notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    body.ticker, body.name, body.market, body.status,
                    body.watch_price, body.notes, _now(),
                ),
            )
            new_id = cur.lastrowid
            row = conn.execute(
                "SELECT * FROM watch_positions WHERE id = ?", (new_id,)
            ).fetchone()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e
    return dict(row) if row else {"id": new_id}


@router.patch("/positions/watch/{position_id}")
async def update_watch(position_id: int, body: WatchPositionUpdate) -> dict:
    db = get_db()
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    params = list(fields.values()) + [_now(), position_id]
    try:
        with db.connect() as conn:
            conn.execute(
                f"UPDATE watch_positions SET {set_clause}, updated_at = ? WHERE id = ?",
                params,
            )
            row = conn.execute(
                "SELECT * FROM watch_positions WHERE id = ?", (position_id,)
            ).fetchone()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e
    if row is None:
        raise HTTPException(status_code=404, detail=f"position {position_id} not found")
    return dict(row)


@router.delete("/positions/watch/{position_id}")
async def delete_watch(position_id: int) -> dict:
    db = get_db()
    with db.connect() as conn:
        cur = conn.execute(
            "DELETE FROM watch_positions WHERE id = ?", (position_id,)
        )
    return {"deleted": cur.rowcount}


@router.get("/positions/sim")
async def list_sim() -> dict:
    db = get_db()
    rows = db.fetch_all(
        "SELECT * FROM sim_positions ORDER BY last_trade_at DESC"
    )
    trades = db.fetch_all(
        "SELECT * FROM sim_trades ORDER BY created_at DESC LIMIT 50"
    )
    return {
        "positions": [dict(r) for r in rows],
        "recent_trades": [dict(r) for r in trades],
    }
