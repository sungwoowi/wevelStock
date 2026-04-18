"""Persistence helpers for team_outputs table."""
from __future__ import annotations

import json
from datetime import date, datetime

from core.contracts.team_output import StandardOutput
from core.db import get_db


def persist_output(output: StandardOutput) -> None:
    """Store a StandardOutput in team_outputs (idempotent)."""
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO team_outputs
                (run_id, team_id, timestamp, target, verdict, confidence,
                 reasons_json, data_json, contract_version, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, team_id, target) DO UPDATE SET
                timestamp       = excluded.timestamp,
                verdict         = excluded.verdict,
                confidence      = excluded.confidence,
                reasons_json    = excluded.reasons_json,
                data_json       = excluded.data_json,
                metadata_json   = excluded.metadata_json
            """,
            (
                output.run_id,
                output.team_id,
                output.timestamp,
                output.target,
                output.verdict,
                output.confidence,
                json.dumps(output.reasons, ensure_ascii=False),
                json.dumps(output.data, ensure_ascii=False),
                output.contract_version,
                output.metadata.model_dump_json(),
            ),
        )


def load_latest(team_id: str, target: str = "global") -> StandardOutput | None:
    """Return the latest team output for (team, target)."""
    db = get_db()
    row = db.fetch_one(
        """
        SELECT * FROM team_outputs
        WHERE team_id = ? AND target = ?
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (team_id, target),
    )
    if row is None:
        return None
    return StandardOutput(
        team_id=row["team_id"],
        run_id=row["run_id"],
        timestamp=row["timestamp"],
        target=row["target"],
        verdict=row["verdict"],
        confidence=row["confidence"],
        reasons=json.loads(row["reasons_json"]),
        data=json.loads(row["data_json"]),
        contract_version=row["contract_version"],
        metadata=json.loads(row["metadata_json"]),
    )


def today_date_string() -> str:
    """Convenience: today's date as YYYY-MM-DD in KST."""
    return date.today().isoformat()


def now_isoformat_with_tz() -> str:
    return datetime.now().astimezone().isoformat()
