"""KNOWLEDGE-SYNC-001 Phase 2 M2 — sync run + delta 인덱싱 + DB run log.

흐름 (1 sync = 1 dept):
1. sync_id 생성 (`YYYY-MM-DD-HHMM`, PK 충돌 시 `-SS` 접미)
2. `knowledge_index_runs` 에 `status='running'` row insert
3. reference walk = `ingest._iter_reference_files(dept)` 재사용
4. collection 의 현 metadata 에서 `source_id → file_hash + chunk_ids` 맵 추출
5. delta 분류 = added (인덱스 없음) / modified (file_hash 변경) / deleted (reference 없음)
6. add/modified → `_build_metadata` + `collection.upsert`
7. deleted → `collection.delete(where={"source_id": ...})` hard
8. DB row update — status / ended_at / 카운트

본 모듈은 PROPOSAL / release note LLM 호출은 안 함 (Phase 3).
watchdog / just 명령은 M3 에서 본 함수를 wrap.

CLI:
    uv run python -m core.knowledge.sync <dept>
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from typing import Any

from core.db.connection import get_db
from core.knowledge.embed import get_embedding_function
from core.knowledge.ingest import (
    INDEX_ROOT,
    REFERENCE_ROOT,
    _build_metadata,
    _chunk_text,
    _iter_reference_files,
)
from core.logging import get_logger

log = get_logger(__name__)

# `news` 는 별도 SPEC (rolling canon + retention 패턴 다름).
_DEFAULT_DEPTS: tuple[str, ...] = (
    "principles",
    "trading",
    "market_macro",
    "stock_selection",
    "stock-analysis",
    "wealth_compounding",
    "trading_journal",
    "flow_analysis",
)


def _now_iso() -> str:
    """ISO-8601 KST (Asia/Seoul). 분 단위 sync_id 와 정합."""
    # 실 시간 KST 표시는 RuntimeConfig.timezone 인용이 정공법이지만, M2 는 단순화.
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _make_sync_id(now: datetime | None = None) -> str:
    """`YYYY-MM-DD-HHMM` (분 단위) — PK 충돌 시 호출처가 `-SS` 추가."""
    dt = now or datetime.now(timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d-%H%M")


def _open_collection(
    dept: str,
    *,
    create_if_missing: bool = True,
    drop_existing: bool = False,
) -> Any | None:
    """Chroma collection 핸들. delta sync 는 ingest 와 같은 client 설정.

    `create_if_missing=False` 시 컬렉션 디렉토리가 비어있으면 None 반환 — 첫 sync 가
    아닐 때 잘못된 dept 호출을 빨리 탐지.
    `drop_existing=True` 면 기존 collection 을 drop 후 재생성 (force 재구축 경로).
    """
    try:
        import chromadb  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError("chromadb>=0.4 required for sync") from e

    index_dir = INDEX_ROOT / dept
    if not create_if_missing and (not index_dir.exists() or not any(index_dir.iterdir())):
        return None
    index_dir.mkdir(parents=True, exist_ok=True)

    ef = get_embedding_function()
    client = chromadb.PersistentClient(path=str(index_dir))
    if drop_existing:
        try:
            client.delete_collection(name=dept)
            log.info("collection_dropped_for_force", dept=dept)
        except Exception:  # noqa: BLE001 — 컬렉션 없을 때 안전 무시
            pass
    return client.get_or_create_collection(name=dept, embedding_function=ef)


def _scan_indexed_state(collection: Any) -> dict[str, dict[str, Any]]:
    """현 collection 의 source_id → {file_hash, chunk_ids} 맵.

    `collection.get(include=["metadatas"])` 는 모든 chunk row 반환. 첫 chunk 하나의
    `file_hash` 만 신뢰 (멱등 인덱스 가정 — 같은 파일의 모든 청크는 동일 file_hash).
    """
    try:
        all_rows = collection.get(include=["metadatas"])
    except Exception as e:  # noqa: BLE001
        log.warning("collection_get_failed", error=str(e))
        return {}

    ids = all_rows.get("ids") or []
    metas = all_rows.get("metadatas") or []
    by_source: dict[str, dict[str, Any]] = {}
    for cid, meta in zip(ids, metas):
        meta = meta or {}
        source_id = meta.get("source_id")
        if not source_id:
            continue
        slot = by_source.setdefault(source_id, {"file_hash": None, "chunk_ids": []})
        slot["chunk_ids"].append(cid)
        if slot["file_hash"] is None:
            slot["file_hash"] = meta.get("file_hash")
    return by_source


def _insert_run_row(sync_id: str, dept: str, started_at: str) -> None:
    """`knowledge_index_runs` 에 running row 적재. PK 충돌 시 호출처가 sync_id 갱신."""
    db = get_db()
    db.execute(
        """
        INSERT INTO knowledge_index_runs
            (sync_id, dept, started_at, status)
        VALUES (?, ?, ?, 'running')
        """,
        (sync_id, dept, started_at),
    )


def _update_run_row(sync_id: str, *, status: str, ended_at: str, counts: dict[str, int],
                    error: str | None = None) -> None:
    db = get_db()
    db.execute(
        """
        UPDATE knowledge_index_runs SET
            ended_at = ?,
            status = ?,
            files_added = ?,
            files_modified = ?,
            files_deleted = ?,
            chunks_upserted = ?,
            chunks_deleted = ?,
            error = ?
        WHERE sync_id = ?
        """,
        (
            ended_at,
            status,
            counts.get("files_added", 0),
            counts.get("files_modified", 0),
            counts.get("files_deleted", 0),
            counts.get("chunks_upserted", 0),
            counts.get("chunks_deleted", 0),
            error,
            sync_id,
        ),
    )


def _allocate_sync_id(dept: str, started_at: str, max_retries: int = 5) -> str:
    """PK 충돌 회피: 분 단위 → 초 단위 (중복 시 SS 추가) → ms 추가."""
    now = datetime.now(timezone.utc).astimezone()
    candidates = [
        now.strftime("%Y-%m-%d-%H%M"),
        now.strftime("%Y-%m-%d-%H%M%S"),
    ]
    for candidate in candidates:
        try:
            _insert_run_row(candidate, dept, started_at)
            return candidate
        except Exception:  # noqa: BLE001 — sqlite3.IntegrityError 등
            continue
    # ms 단위까지 fallback
    for _ in range(max_retries):
        sid = now.strftime("%Y-%m-%d-%H%M%S") + f"-{int(time.monotonic_ns()) % 1000:03d}"
        try:
            _insert_run_row(sid, dept, started_at)
            return sid
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError(f"failed to allocate sync_id for dept={dept}")


def sync_dept(
    dept: str,
    *,
    since_run_id: str | None = None,
    force: bool = False,
    chunk_size: int = 800,
    overlap: int = 100,
) -> dict[str, Any]:
    """1 sync run for one dept. delta 인덱싱 + DB run log.

    `since_run_id` 는 SPEC 호환을 위해 인자로 받지만 M2 는 collection metadata 단일
    baseline (DB run log 는 운영 로그). 후속 마일스톤에서 적극 활용 가능.

    `force=True` 면 기존 collection 을 drop 후 모든 reference 자료를 added 로 재구축
    (`ingest --force` 의 sync 버전). drop 직전 indexed_state 의 카운트는
    `files_deleted` / `chunks_deleted` 로 적재돼 운영 로그에서 가시화된다.
    """
    started_at = _now_iso()
    sync_id = _allocate_sync_id(dept, started_at)

    counts = {
        "files_added": 0,
        "files_modified": 0,
        "files_deleted": 0,
        "chunks_upserted": 0,
        "chunks_deleted": 0,
    }
    error_msg: str | None = None
    final_status = "success"

    try:
        dept_dir = REFERENCE_ROOT / dept
        if not dept_dir.exists():
            raise ValueError(f"reference dir not found: {dept_dir}")

        collection = _open_collection(dept, create_if_missing=True)
        if collection is None:
            raise RuntimeError(f"failed to open collection for dept={dept}")

        indexed_state = _scan_indexed_state(collection)

        if force and indexed_state:
            # 운영 가시화: drop 직전 상태를 deleted 카운트로 적재
            prev_files = len(indexed_state)
            prev_chunks = sum(
                len(slot.get("chunk_ids") or []) for slot in indexed_state.values()
            )
            counts["files_deleted"] += prev_files
            counts["chunks_deleted"] += prev_chunks

            # drop + recreate → indexed_state 비우고 모든 파일 added 로 재분류
            collection = _open_collection(
                dept, create_if_missing=True, drop_existing=True
            )
            if collection is None:
                raise RuntimeError(f"failed to reopen collection after drop for dept={dept}")
            indexed_state = {}
            log.info(
                "sync_force_drop",
                dept=dept,
                prev_files=prev_files,
                prev_chunks=prev_chunks,
            )

        seen_sources: set[str] = set()

        # add / modified
        for rel_path, category, body, fm_meta, extra_meta, fhash in _iter_reference_files(dept):
            seen_sources.add(rel_path)
            prev = indexed_state.get(rel_path)

            if prev is None:
                change = "added"
            elif prev.get("file_hash") != fhash:
                change = "modified"
            else:
                # 변경 없음 — backfill 은 ingest.py 에 위임 (M2 범위 외)
                continue

            chunks = _chunk_text(body, chunk_size, overlap)
            if not chunks:
                continue

            ids = [f"{rel_path}::{i}" for i in range(len(chunks))]
            metadatas = [
                _build_metadata(rel_path, category, dept, fm_meta, extra_meta, fhash, i)
                for i in range(len(chunks))
            ]
            try:
                # modified 의 경우, 기존 청크 수가 더 많을 수 있으면 stale id 가 남음.
                # 예: 본문 길이 감소로 청크 수 5→3 이면 id 3,4 가 남음. 안전하게 source_id 로 hard delete 후 upsert.
                if change == "modified":
                    try:
                        collection.delete(where={"source_id": rel_path})
                    except Exception as e:  # noqa: BLE001
                        log.warning("modified_predelete_failed", source=rel_path, error=str(e))
                collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
            except Exception as e:  # noqa: BLE001
                log.warning("chroma_upsert_failed", source=rel_path, error=str(e))
                final_status = "partial"
                continue

            counts["chunks_upserted"] += len(chunks)
            if change == "added":
                counts["files_added"] += 1
            else:
                counts["files_modified"] += 1

        # deleted
        for rel_path, slot in indexed_state.items():
            if rel_path in seen_sources:
                continue
            chunk_ids = slot.get("chunk_ids") or []
            try:
                collection.delete(where={"source_id": rel_path})
            except Exception as e:  # noqa: BLE001
                log.warning("chroma_delete_failed", source=rel_path, error=str(e))
                final_status = "partial"
                continue
            counts["files_deleted"] += 1
            counts["chunks_deleted"] += len(chunk_ids)
    except Exception as e:  # noqa: BLE001
        error_msg = f"{type(e).__name__}: {e}"
        final_status = "failed"
        log.warning("sync_dept_failed", dept=dept, sync_id=sync_id, error=error_msg)

    ended_at = _now_iso()
    _update_run_row(sync_id, status=final_status, ended_at=ended_at, counts=counts, error=error_msg)

    return {
        "sync_id": sync_id,
        "dept": dept,
        "status": final_status,
        "started_at": started_at,
        "ended_at": ended_at,
        **counts,
        "error": error_msg,
    }


def sync_all(
    *,
    since_run_id: str | None = None,
    force: bool = False,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[dict[str, Any]]:
    """8 dept (news 제외) 순회 sync. 한 dept 실패해도 다음 진행."""
    results: list[dict[str, Any]] = []
    for dept in _DEFAULT_DEPTS:
        if not (REFERENCE_ROOT / dept).exists():
            log.debug("sync_skip_no_reference", dept=dept)
            continue
        try:
            results.append(sync_dept(
                dept,
                since_run_id=since_run_id,
                force=force,
                chunk_size=chunk_size,
                overlap=overlap,
            ))
        except Exception as e:  # noqa: BLE001 — sync_dept 내부에서 처리하지만 보호막
            log.warning("sync_all_dept_unhandled", dept=dept, error=str(e))
    return results


def recent_runs(limit: int = 10, dept: str | None = None) -> list[dict[str, Any]]:
    """`knowledge_index_runs` 최신 N row. dept 지정 시 해당 dept 만.

    `just knowledge-status` 의 진입점. 운영자가 "방금 sync 어떻게 됐지?" 를 1줄로
    확인하는 용도.
    """
    db = get_db()
    if dept:
        rows = db.fetch_all(
            "SELECT * FROM knowledge_index_runs WHERE dept = ? "
            "ORDER BY started_at DESC, sync_id DESC LIMIT ?",
            (dept, limit),
        )
    else:
        rows = db.fetch_all(
            "SELECT * FROM knowledge_index_runs "
            "ORDER BY started_at DESC, sync_id DESC LIMIT ?",
            (limit,),
        )
    return [dict(row) for row in rows]


def _format_status_row(row: dict[str, Any]) -> str:
    """`knowledge-status` 출력용 1줄 포맷."""
    sid = row.get("sync_id", "?")
    dept = row.get("dept", "?")
    status = row.get("status", "?")
    added = row.get("files_added", 0) or 0
    modified = row.get("files_modified", 0) or 0
    deleted = row.get("files_deleted", 0) or 0
    chunks_up = row.get("chunks_upserted", 0) or 0
    chunks_del = row.get("chunks_deleted", 0) or 0
    started = row.get("started_at", "")
    ended = row.get("ended_at", "")
    duration = ""
    if started and ended:
        try:
            from datetime import datetime
            t0 = datetime.fromisoformat(started)
            t1 = datetime.fromisoformat(ended)
            duration = f" ({(t1 - t0).total_seconds():.1f}s)"
        except Exception:  # noqa: BLE001
            pass
    err = row.get("error")
    err_suffix = f"  err={err}" if err else ""
    return (
        f"[{sid}] {dept:<22} {status:<8}{duration}  "
        f"+{added}/~{modified}/-{deleted} files, "
        f"+{chunks_up}/-{chunks_del} chunks{err_suffix}"
    )


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="KNOWLEDGE-SYNC-001 M2/M3 — delta sync + run log + status."
    )
    parser.add_argument(
        "dept",
        nargs="?",
        help="learning dept id (생략 시 8 dept 전체)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="기존 collection 을 drop 후 재구축 (knowledge-rebuild)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="sync 실행 대신 knowledge_index_runs 최신 row 출력",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="--status 시 출력 row 수 (default=10)",
    )
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--overlap", type=int, default=100)
    args = parser.parse_args()

    if args.status:
        rows = recent_runs(args.limit, dept=args.dept)
        if not rows:
            print("(no sync runs yet)")
            return
        for row in rows:
            print(_format_status_row(row))
        return

    if args.dept:
        result = sync_dept(
            args.dept,
            force=args.force,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
        )
        print(result)
    else:
        for r in sync_all(
            force=args.force,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
        ):
            print(r)


if __name__ == "__main__":
    _cli()
