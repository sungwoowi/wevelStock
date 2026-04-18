"""Rollup generation — daily/weekly/monthly/quarterly summarization.

Initial implementation uses a template-based summarizer (no LLM cost).
Later versions can route to LLM for richer narratives.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Iterable

from core.contracts.memory import RollupRecord
from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)


def _iso_week_key(d: date) -> str:
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _month_key(d: date) -> str:
    return d.strftime("%Y-%m")


def _summarize_verdicts(verdicts: Iterable[str]) -> str:
    counts = Counter(verdicts)
    total = sum(counts.values()) or 1
    parts = [f"{v}={c} ({c * 100 // total}%)" for v, c in counts.most_common()]
    return ", ".join(parts) if parts else "no data"


def build_daily_rollup(team_id: str, day: date) -> RollupRecord | None:
    db = get_db()
    rows = db.fetch_all(
        """
        SELECT verdict, confidence, reasons_json, narrative
        FROM team_memory
        WHERE team_id = ? AND date = ?
        """,
        (team_id, day.isoformat()),
    )
    if not rows:
        return None

    verdicts = [r["verdict"] for r in rows if r["verdict"]]
    avg_conf = sum((r["confidence"] or 0) for r in rows) / len(rows)
    reasons: list[str] = []
    for r in rows:
        try:
            reasons.extend(json.loads(r["reasons_json"] or "[]")[:2])
        except json.JSONDecodeError:
            pass

    summary = (
        f"# {team_id} — {day.isoformat()}\n"
        f"- 결정 분포: {_summarize_verdicts(verdicts)}\n"
        f"- 평균 신뢰도: {avg_conf:.1f}\n"
        f"- 주요 근거: {'; '.join(reasons[:5])}"
    )
    return RollupRecord(
        team_id=team_id,
        period_type="daily",
        period_key=day.isoformat(),
        summary_md=summary,
        metrics={"avg_confidence": avg_conf, "count": len(rows)},
    )


def build_weekly_rollup(team_id: str, anchor_day: date | None = None) -> RollupRecord | None:
    """Summarize the ISO week containing anchor_day (default: yesterday)."""
    anchor_day = anchor_day or (date.today() - timedelta(days=1))
    week_key = _iso_week_key(anchor_day)
    iso_year, iso_week, _ = anchor_day.isocalendar()
    monday = date.fromisocalendar(iso_year, iso_week, 1)
    sunday = date.fromisocalendar(iso_year, iso_week, 7)
    db = get_db()
    rows = db.fetch_all(
        """
        SELECT verdict, confidence FROM team_memory
        WHERE team_id = ? AND date BETWEEN ? AND ?
        """,
        (team_id, monday.isoformat(), sunday.isoformat()),
    )
    if not rows:
        return None
    verdicts = [r["verdict"] for r in rows if r["verdict"]]
    avg_conf = sum((r["confidence"] or 0) for r in rows) / len(rows)
    summary = (
        f"# {team_id} — Week {week_key}\n"
        f"- 기간: {monday} ~ {sunday}\n"
        f"- 판단 분포: {_summarize_verdicts(verdicts)}\n"
        f"- 평균 신뢰도: {avg_conf:.1f}"
    )
    return RollupRecord(
        team_id=team_id,
        period_type="weekly",
        period_key=week_key,
        summary_md=summary,
        metrics={"avg_confidence": avg_conf, "count": len(rows)},
    )


def build_monthly_rollup(team_id: str, any_day_in_month: date) -> RollupRecord | None:
    month_key = _month_key(any_day_in_month)
    db = get_db()
    rows = db.fetch_all(
        """
        SELECT verdict, confidence FROM team_memory
        WHERE team_id = ? AND strftime('%Y-%m', date) = ?
        """,
        (team_id, month_key),
    )
    if not rows:
        return None
    verdicts = [r["verdict"] for r in rows if r["verdict"]]
    avg_conf = sum((r["confidence"] or 0) for r in rows) / len(rows)
    summary = (
        f"# {team_id} — Month {month_key}\n"
        f"- 판단 분포: {_summarize_verdicts(verdicts)}\n"
        f"- 평균 신뢰도: {avg_conf:.1f}\n"
        f"- 레코드 수: {len(rows)}"
    )
    return RollupRecord(
        team_id=team_id,
        period_type="monthly",
        period_key=month_key,
        summary_md=summary,
        metrics={"avg_confidence": avg_conf, "count": len(rows)},
    )


def persist_rollup(rollup: RollupRecord) -> None:
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO memory_rollup
                (team_id, period_type, period_key, summary_md, key_events_json, metrics_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_id, period_type, period_key) DO UPDATE SET
                summary_md      = excluded.summary_md,
                key_events_json = excluded.key_events_json,
                metrics_json    = excluded.metrics_json
            """,
            (
                rollup.team_id,
                rollup.period_type,
                rollup.period_key,
                rollup.summary_md,
                json.dumps(rollup.key_events, ensure_ascii=False),
                json.dumps(rollup.metrics, ensure_ascii=False),
            ),
        )


def rollup_all_teams(period: str, anchor: date | None = None) -> list[str]:
    """Run rollup for all teams with memory enabled."""
    from core.registry import list_active_teams  # late import to avoid cycle

    anchor = anchor or date.today()
    produced: list[str] = []
    for team in list_active_teams():
        try:
            if period == "daily":
                r = build_daily_rollup(team.id, anchor)
            elif period == "weekly":
                r = build_weekly_rollup(team.id, anchor)
            elif period == "monthly":
                r = build_monthly_rollup(team.id, anchor)
            else:
                continue
        except Exception as e:  # noqa: BLE001
            log.error("rollup_build_failed", team=team.id, period=period, error=str(e))
            continue
        if r:
            persist_rollup(r)
            produced.append(f"{team.id}:{period}:{r.period_key}")
    return produced
