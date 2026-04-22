"""briefing_parts 테이블 I/O 캡슐화.

파이프라인 실행 시 `upsert_parts()` 로 저장,
API/봇은 `get_latest_parts()` / `get_parts_by_run()` / `get_part()` 로 조회.

멱등성: UNIQUE(pipeline_id, run_id, part_key) + ON CONFLICT DO UPDATE.
"""
from __future__ import annotations

import json
from typing import Any

from core.contracts.briefing_part import BriefingPart
from core.db import get_db


def upsert_parts(
    pipeline_id: str,
    run_id: str,
    parts: list[BriefingPart],
) -> None:
    """동일 (pipeline_id, run_id, part_key) 는 덮어쓰기."""
    db = get_db()
    with db.connect() as conn:
        for p in parts:
            conn.execute(
                """
                INSERT INTO briefing_parts
                    (pipeline_id, run_id, part_key, part_label, part_order, data_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(pipeline_id, run_id, part_key) DO UPDATE SET
                    part_label = excluded.part_label,
                    part_order = excluded.part_order,
                    data_json  = excluded.data_json,
                    created_at = datetime('now')
                """,
                (
                    pipeline_id,
                    run_id,
                    p.key,
                    p.label,
                    p.order,
                    json.dumps(p.data, ensure_ascii=False),
                ),
            )


def get_parts_by_run(pipeline_id: str, run_id: str) -> list[BriefingPart]:
    """특정 run 의 파트 전체 (order ASC)."""
    db = get_db()
    rows = db.fetch_all(
        """
        SELECT part_key, part_label, part_order, data_json
        FROM briefing_parts
        WHERE pipeline_id = ? AND run_id = ?
        ORDER BY part_order ASC
        """,
        (pipeline_id, run_id),
    )
    return [_row_to_part(r) for r in rows]


def get_latest_parts(pipeline_id: str) -> tuple[str, list[BriefingPart]] | None:
    """가장 최근 run_id 의 파트 전체. 없으면 None."""
    db = get_db()
    row = db.fetch_one(
        """
        SELECT run_id
        FROM briefing_parts
        WHERE pipeline_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (pipeline_id,),
    )
    if row is None:
        return None
    run_id: str = row["run_id"]
    return run_id, get_parts_by_run(pipeline_id, run_id)


def get_latest_parts_with_age(
    pipeline_id: str,
) -> tuple[str, list[BriefingPart], float] | None:
    """가장 최근 run 의 (run_id, parts, age_seconds) 반환. 없으면 None.

    `age_seconds` 는 DB 의 `datetime('now')` 기준. 여러 프로세스가 공유하는
    DB 시계를 사용하므로 서버 재기동/다중 인스턴스 환경에서도 일관.
    """
    db = get_db()
    row = db.fetch_one(
        """
        SELECT run_id,
               CAST((julianday('now') - julianday(created_at)) * 86400
                    AS REAL) AS age_seconds
        FROM briefing_parts
        WHERE pipeline_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (pipeline_id,),
    )
    if row is None:
        return None
    run_id: str = row["run_id"]
    age: float = float(row["age_seconds"] or 0.0)
    return run_id, get_parts_by_run(pipeline_id, run_id), age


def get_part(pipeline_id: str, run_id: str, key: str) -> BriefingPart | None:
    """단일 파트 조회."""
    db = get_db()
    row = db.fetch_one(
        """
        SELECT part_key, part_label, part_order, data_json
        FROM briefing_parts
        WHERE pipeline_id = ? AND run_id = ? AND part_key = ?
        """,
        (pipeline_id, run_id, key),
    )
    if row is None:
        return None
    return _row_to_part(row)


def _row_to_part(row: Any) -> BriefingPart:
    return BriefingPart(
        key=row["part_key"],
        label=row["part_label"],
        order=row["part_order"],
        data=json.loads(row["data_json"]),
    )
