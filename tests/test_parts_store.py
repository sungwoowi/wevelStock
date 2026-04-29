"""core/briefing/parts_store — get_last_run_before() 단위 테스트."""
from __future__ import annotations

import pytest

from core.briefing import get_last_run_before, upsert_parts
from core.contracts.briefing_part import BriefingPart


def _one_part() -> list[BriefingPart]:
    return [BriefingPart(key="overnight", label="간밤시황", order=1, data={"k": 1})]


@pytest.fixture(autouse=True)
def _reset_briefing_parts() -> None:
    from core.db import get_db

    db = get_db()
    with db.connect() as conn:
        conn.execute("DELETE FROM briefing_parts")


def _force_created_at(run_id: str, created_at_utc: str) -> None:
    from core.db import get_db

    db = get_db()
    with db.connect() as conn:
        conn.execute(
            "UPDATE briefing_parts SET created_at = ? WHERE run_id = ?",
            (created_at_utc, run_id),
        )


def test_returns_none_when_empty() -> None:
    assert get_last_run_before("market_briefing_pre", "2026-04-24 10:00:00") is None


def test_finds_run_strictly_before_cutoff() -> None:
    upsert_parts("market_briefing_pre", "run_before", _one_part())
    _force_created_at("run_before", "2026-04-24 07:30:00")

    result = get_last_run_before("market_briefing_pre", "2026-04-24 09:00:00")
    assert result is not None
    run_id, parts = result
    assert run_id == "run_before"
    assert [p.key for p in parts] == ["overnight"]


def test_excludes_rows_at_or_after_cutoff() -> None:
    upsert_parts("market_briefing_pre", "run_after", _one_part())
    _force_created_at("run_after", "2026-04-24 09:30:00")

    assert get_last_run_before("market_briefing_pre", "2026-04-24 09:00:00") is None


def test_picks_latest_when_multiple_before_cutoff() -> None:
    upsert_parts("market_briefing_pre", "run_old", _one_part())
    upsert_parts("market_briefing_pre", "run_new", _one_part())
    _force_created_at("run_old", "2026-04-24 07:00:00")
    _force_created_at("run_new", "2026-04-24 08:30:00")

    result = get_last_run_before("market_briefing_pre", "2026-04-24 09:00:00")
    assert result is not None
    run_id, _ = result
    assert run_id == "run_new"


def test_filters_by_pipeline_id() -> None:
    upsert_parts("market_briefing_pre", "mp_run", _one_part())
    upsert_parts("other_pipeline", "op_run", _one_part())
    _force_created_at("mp_run", "2026-04-24 07:00:00")
    _force_created_at("op_run", "2026-04-24 07:15:00")

    result = get_last_run_before("market_briefing_pre", "2026-04-24 09:00:00")
    assert result is not None
    run_id, _ = result
    assert run_id == "mp_run"


def test_since_iso_filters_out_older_runs() -> None:
    upsert_parts("market_briefing_pre", "yesterday_run", _one_part())
    upsert_parts("market_briefing_pre", "today_run", _one_part())
    _force_created_at("yesterday_run", "2026-04-23 07:00:00")
    _force_created_at("today_run", "2026-04-24 07:30:00")

    result = get_last_run_before(
        "market_briefing_pre",
        "2026-04-24 09:00:00",
        since_iso="2026-04-24 00:00:00",
    )
    assert result is not None
    run_id, _ = result
    assert run_id == "today_run"


def test_since_iso_none_keeps_no_lower_bound() -> None:
    upsert_parts("market_briefing_pre", "old", _one_part())
    _force_created_at("old", "2026-04-23 07:00:00")

    result = get_last_run_before("market_briefing_pre", "2026-04-24 09:00:00")
    assert result is not None
    assert result[0] == "old"
