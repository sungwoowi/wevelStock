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


def _open_collection(dept: str, *, create_if_missing: bool = True) -> Any | None:
    """Chroma collection 핸들. delta sync 는 ingest 와 같은 client 설정.

    `create_if_missing=False` 시 컬렉션 디렉토리가 비어있으면 None 반환 — 첫 sync 가
    아닐 때 잘못된 dept 호출을 빨리 탐지.
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
    chunk_size: int = 800,
    overlap: int = 100,
) -> dict[str, Any]:
    """1 sync run for one dept. delta 인덱싱 + DB run log.

    `since_run_id` 는 SPEC 호환을 위해 인자로 받지만 M2 는 collection metadata 단일
    baseline (DB run log 는 운영 로그). 후속 마일스톤에서 적극 활용 가능.
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
                chunk_size=chunk_size,
                overlap=overlap,
            ))
        except Exception as e:  # noqa: BLE001 — sync_dept 내부에서 처리하지만 보호막
            log.warning("sync_all_dept_unhandled", dept=dept, error=str(e))
    return results


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="KNOWLEDGE-SYNC-001 M2 — delta sync + run log."
    )
    parser.add_argument(
        "dept",
        nargs="?",
        help="learning dept id (생략 시 8 dept 전체 sync)",
    )
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--overlap", type=int, default=100)
    args = parser.parse_args()

    if args.dept:
        result = sync_dept(args.dept, chunk_size=args.chunk_size, overlap=args.overlap)
        print(result)
    else:
        for r in sync_all(chunk_size=args.chunk_size, overlap=args.overlap):
            print(r)


if __name__ == "__main__":
    _cli()
