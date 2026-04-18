"""Memory cleanup — enforce retention policies.

Scheduled monthly:
- team_memory.narrative -> NULL after raw_days (keep structured data forever).
- memory_rollup: drop daily > daily_days, weekly > weekly_days, monthly > monthly_days.
- llm_call_cache: drop expired entries.
"""
from __future__ import annotations

from core.config import get_config
from core.db import get_db
from core.logging import get_logger
from core.memory.cache import prune_expired

log = get_logger(__name__)


def cleanup_all() -> dict[str, int]:
    cfg = get_config().memory.retention
    db = get_db()
    stats: dict[str, int] = {}

    with db.connect() as conn:
        # narrative purge
        cur = conn.execute(
            """
            UPDATE team_memory
            SET narrative = NULL
            WHERE narrative IS NOT NULL
              AND julianday('now') - julianday(date) > ?
            """,
            (cfg.raw_days,),
        )
        stats["narratives_purged"] = cur.rowcount if cur.rowcount else 0

        # daily rollups
        cur = conn.execute(
            """
            DELETE FROM memory_rollup
            WHERE period_type = 'daily'
              AND julianday('now') - julianday(period_key) > ?
            """,
            (cfg.daily_days,),
        )
        stats["daily_rollups_deleted"] = cur.rowcount if cur.rowcount else 0

        # weekly (approximate: period_key like '2026-W16')
        cur = conn.execute(
            """
            DELETE FROM memory_rollup
            WHERE period_type = 'weekly'
              AND julianday('now') - julianday(substr(period_key, 1, 4) || '-01-01') > ?
            """,
            (cfg.weekly_days,),
        )
        stats["weekly_rollups_deleted"] = cur.rowcount if cur.rowcount else 0

        # monthly
        if cfg.monthly_days is not None:
            cur = conn.execute(
                """
                DELETE FROM memory_rollup
                WHERE period_type = 'monthly'
                  AND julianday('now') - julianday(period_key || '-01') > ?
                """,
                (cfg.monthly_days,),
            )
            stats["monthly_rollups_deleted"] = cur.rowcount if cur.rowcount else 0

    stats["cache_entries_pruned"] = prune_expired(get_config().memory.idempotency.cache_ttl_days)

    log.info("memory_cleanup_completed", **stats)
    return stats
