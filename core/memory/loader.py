"""Memory context loader — stitches hot/warm/cold memory into an LLM-ready block."""
from __future__ import annotations

import json
from datetime import date, timedelta

from core.contracts.memory import MemoryContext, MemoryRecord, RollupRecord
from core.db import get_db


def _estimate_tokens(text: str) -> int:
    """Rough estimate: ~4 chars per token for mixed Korean/English."""
    return max(1, len(text) // 4)


def _load_recent_memory(team_id: str, target: str, days: int) -> list[MemoryRecord]:
    db = get_db()
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = db.fetch_all(
        """
        SELECT team_id, date, target, input_hash, verdict, confidence,
               reasons_json, narrative, data_json, model, contract_version
        FROM team_memory
        WHERE team_id = ? AND target = ? AND date >= ?
        ORDER BY date DESC
        """,
        (team_id, target, since),
    )
    records: list[MemoryRecord] = []
    for r in rows:
        records.append(
            MemoryRecord(
                team_id=r["team_id"],
                date=r["date"],
                target=r["target"],
                input_hash=r["input_hash"],
                verdict=r["verdict"],
                confidence=r["confidence"] or 0,
                reasons=json.loads(r["reasons_json"] or "[]"),
                narrative=r["narrative"],
                data=json.loads(r["data_json"] or "{}"),
                model=r["model"],
                contract_version=r["contract_version"] or "1.0",
            )
        )
    return records


def _load_rollups(team_id: str, period_type: str, limit: int) -> list[RollupRecord]:
    db = get_db()
    rows = db.fetch_all(
        """
        SELECT team_id, period_type, period_key, summary_md,
               key_events_json, metrics_json
        FROM memory_rollup
        WHERE team_id = ? AND period_type = ?
        ORDER BY period_key DESC
        LIMIT ?
        """,
        (team_id, period_type, limit),
    )
    result: list[RollupRecord] = []
    for r in rows:
        result.append(
            RollupRecord(
                team_id=r["team_id"],
                period_type=r["period_type"],
                period_key=r["period_key"],
                summary_md=r["summary_md"] or "",
                key_events=json.loads(r["key_events_json"] or "[]"),
                metrics=json.loads(r["metrics_json"] or "{}"),
            )
        )
    return result


def _trim_to_budget(ctx: MemoryContext, budget: int) -> MemoryContext:
    """Drop oldest items until total estimate <= budget."""
    def estimate(ctx: MemoryContext) -> int:
        total = 0
        for r in ctx.recent_days:
            total += _estimate_tokens(r.narrative or "") + _estimate_tokens(json.dumps(r.reasons))
        for r in ctx.weekly_rollups + ctx.monthly_rollups:
            total += _estimate_tokens(r.summary_md or "")
        return total

    # Priority: drop monthly first (oldest), then weekly, then recent_days
    while estimate(ctx) > budget:
        if ctx.monthly_rollups:
            ctx.monthly_rollups.pop()
        elif ctx.weekly_rollups:
            ctx.weekly_rollups.pop()
        elif ctx.recent_days:
            ctx.recent_days.pop()
        else:
            break
    ctx.total_tokens_estimate = estimate(ctx)
    return ctx


def load_context(
    team_id: str,
    target: str = "global",
    token_budget: int = 4000,
    recent_days: int = 14,
    weekly_weeks: int = 12,
    monthly_months: int = 6,
) -> MemoryContext:
    """Assemble team memory context within a token budget."""
    ctx = MemoryContext(
        team_id=team_id,
        recent_days=_load_recent_memory(team_id, target, recent_days),
        weekly_rollups=_load_rollups(team_id, "weekly", weekly_weeks),
        monthly_rollups=_load_rollups(team_id, "monthly", monthly_months),
    )
    return _trim_to_budget(ctx, token_budget)


def render_context_markdown(ctx: MemoryContext) -> str:
    """Render a compact markdown summary suitable for LLM system prompt injection."""
    parts: list[str] = []
    if ctx.recent_days:
        parts.append("## Recent 14 days")
        for r in ctx.recent_days:
            reasons = "; ".join(r.reasons[:3])
            parts.append(f"- **{r.date}** `{r.verdict}` ({r.confidence}): {reasons}")
    if ctx.weekly_rollups:
        parts.append("\n## Recent weeks")
        for r in ctx.weekly_rollups:
            first_line = (r.summary_md or "").strip().splitlines()[:1]
            parts.append(f"- **{r.period_key}**: {first_line[0] if first_line else ''}")
    if ctx.monthly_rollups:
        parts.append("\n## Recent months")
        for r in ctx.monthly_rollups:
            parts.append(f"- **{r.period_key}**: see rollup")
    return "\n".join(parts) if parts else "(no prior memory)"


def persist_record(record: MemoryRecord) -> None:
    """Write a MemoryRecord to team_memory (idempotent on input_hash)."""
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO team_memory
                (team_id, date, target, input_hash, verdict, confidence,
                 reasons_json, narrative, data_json, model, contract_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_id, date, target, input_hash) DO UPDATE SET
                verdict      = excluded.verdict,
                confidence   = excluded.confidence,
                reasons_json = excluded.reasons_json,
                narrative    = excluded.narrative,
                data_json    = excluded.data_json,
                model        = excluded.model
            """,
            (
                record.team_id,
                record.date,
                record.target,
                record.input_hash,
                record.verdict,
                record.confidence,
                json.dumps(record.reasons, ensure_ascii=False),
                record.narrative,
                json.dumps(record.data, ensure_ascii=False),
                record.model,
                record.contract_version,
            ),
        )
