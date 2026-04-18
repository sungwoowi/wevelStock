"""LLM call cache — idempotency + cost savings."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from core.db import get_db


def get_cached_response(input_hash: str, ttl_days: int = 7) -> dict | None:
    """Return cached LLM response dict if present and within TTL."""
    db = get_db()
    row = db.fetch_one(
        "SELECT response_json, created_at FROM llm_call_cache WHERE input_hash = ?",
        (input_hash,),
    )
    if row is None:
        return None
    created = datetime.fromisoformat(row["created_at"])
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created > timedelta(days=ttl_days):
        return None
    try:
        return json.loads(row["response_json"])
    except (json.JSONDecodeError, TypeError):
        return None


def store_cached_response(
    *,
    input_hash: str,
    model: str,
    response: dict,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
    ttl_days: int = 7,
) -> None:
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO llm_call_cache
                (input_hash, model, response_json, tokens_in, tokens_out, cost_usd, ttl_days, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(input_hash) DO UPDATE SET
                response_json = excluded.response_json,
                tokens_in     = excluded.tokens_in,
                tokens_out    = excluded.tokens_out,
                cost_usd      = excluded.cost_usd,
                created_at    = excluded.created_at
            """,
            (
                input_hash,
                model,
                json.dumps(response, ensure_ascii=False),
                tokens_in,
                tokens_out,
                cost_usd,
                ttl_days,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def prune_expired(default_ttl_days: int = 7) -> int:
    """Delete cache entries whose TTL has passed. Returns number deleted."""
    db = get_db()
    with db.connect() as conn:
        cur = conn.execute(
            """
            DELETE FROM llm_call_cache
            WHERE datetime(created_at, '+' || COALESCE(ttl_days, ?) || ' days') < datetime('now')
            """,
            (default_ttl_days,),
        )
        return cur.rowcount if cur.rowcount else 0
