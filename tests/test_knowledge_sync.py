"""KNOWLEDGE-SYNC-001 Phase 2 M2 — sync run + delta + DB run log.

대상: `core.knowledge.sync`
- sync_dept(dept) 가 reference walk + collection 비교로 delta 분류
- add/modified → upsert, deleted → hard delete (where source_id)
- DB knowledge_index_runs 에 run row 적재 (running → success/partial/failed)

실 chromadb / 실 embedding 호출 없음 — `_open_collection` monkeypatch + DB 는 tmp_path.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import core.knowledge.ingest as ingest_mod
import core.knowledge.sync as sync_mod
from core.db.connection import Database, reset_db


class FakeCollection:
    """In-memory chunk store. chromadb collection 의 부분집합."""

    def __init__(self) -> None:
        # id → (document, metadata)
        self._chunks: dict[str, tuple[str, dict[str, Any]]] = {}

    def get(self, *, ids: list[str] | None = None, where: dict[str, Any] | None = None,
            include: list[str] | None = None) -> dict[str, Any]:
        if ids is not None:
            sel = [i for i in ids if i in self._chunks]
        elif where is not None:
            # 단순화: source_id eq 만 지원
            sid = where.get("source_id")
            if isinstance(sid, dict):
                sid = sid.get("$eq", sid)
            sel = [
                cid for cid, (_, meta) in self._chunks.items()
                if meta.get("source_id") == sid
            ]
        else:
            sel = list(self._chunks.keys())
        return {
            "ids": sel,
            "documents": [self._chunks[i][0] for i in sel],
            "metadatas": [self._chunks[i][1] for i in sel],
        }

    def upsert(self, *, ids: list[str], documents: list[str],
               metadatas: list[dict[str, Any]]) -> None:
        for i, doc, meta in zip(ids, documents, metadatas):
            self._chunks[i] = (doc, dict(meta))

    def delete(self, *, where: dict[str, Any] | None = None,
               ids: list[str] | None = None) -> None:
        if ids is not None:
            for i in ids:
                self._chunks.pop(i, None)
            return
        if where is None:
            return
        sid = where.get("source_id")
        if isinstance(sid, dict):
            sid = sid.get("$eq", sid)
        for cid in [c for c, (_, m) in self._chunks.items() if m.get("source_id") == sid]:
            self._chunks.pop(cid, None)


def _write_md(p: Path, body: str, *, frontmatter: str = "") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    if frontmatter:
        p.write_text(f"---\n{frontmatter}\n---\n\n{body}", encoding="utf-8")
    else:
        p.write_text(body, encoding="utf-8")


@pytest.fixture
def isolated_world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """tmp_path 에 reference + canon dept tree + tmp DB + fake collection."""
    ref_root = tmp_path / "knowledge" / "reference"
    canon_root = tmp_path / "knowledge" / "canon"
    dept = "test_dept"
    cat = "alpha"
    (canon_root / dept / cat).mkdir(parents=True, exist_ok=True)
    (canon_root / dept / cat / "_category.yaml").write_text(
        "category_id: alpha\ntitle: 알파\nwhen_to_inject: always\n",
        encoding="utf-8",
    )
    # 초기 자료 2개
    _write_md(ref_root / dept / cat / "01.md", "첫 자료 본문")
    _write_md(ref_root / dept / cat / "02.md", "두 번째 자료 본문")

    # ingest 의 ROOT redirect (sync 가 ingest 의 헬퍼 import 시 같은 ROOT 본다)
    monkeypatch.setattr(ingest_mod, "REFERENCE_ROOT", ref_root)
    monkeypatch.setattr(ingest_mod, "CANON_ROOT", canon_root)
    monkeypatch.setattr(sync_mod, "REFERENCE_ROOT", ref_root)
    monkeypatch.setattr(sync_mod, "INDEX_ROOT", tmp_path / "data" / "chroma")

    # fake collection 1개를 dept 에 fix
    coll = FakeCollection()
    monkeypatch.setattr(
        sync_mod,
        "_open_collection",
        lambda dept_name, *, create_if_missing=True: coll,
    )

    # tmp DB
    reset_db()
    db = Database(tmp_path / "data" / "test.sqlite")
    monkeypatch.setattr("core.knowledge.sync.get_db", lambda: db)

    return {"ref_root": ref_root, "dept": dept, "cat": cat, "coll": coll, "db": db}


def test_first_sync_indexes_all_files_as_added(isolated_world: dict[str, Any]) -> None:
    """빈 인덱스 + 자료 2개 → files_added=2, status=success."""
    result = sync_mod.sync_dept(isolated_world["dept"])

    assert result["status"] == "success"
    assert result["files_added"] == 2
    assert result["files_modified"] == 0
    assert result["files_deleted"] == 0
    assert result["chunks_upserted"] >= 2  # 본문이 짧아 1 청크씩이라도 최소 2

    # collection 에 2 source 쌓임
    coll: FakeCollection = isolated_world["coll"]
    assert {m["source_id"] for _, m in coll._chunks.values()} == {
        "alpha/01.md",
        "alpha/02.md",
    }

    # DB row 적재
    row = isolated_world["db"].fetch_one(
        "SELECT * FROM knowledge_index_runs WHERE sync_id = ?",
        (result["sync_id"],),
    )
    assert row is not None
    assert row["dept"] == isolated_world["dept"]
    assert row["status"] == "success"
    assert row["files_added"] == 2
    assert row["ended_at"] is not None


def test_second_sync_no_changes_yields_zero_delta(isolated_world: dict[str, Any]) -> None:
    """동일 파일 재 sync → delta 0 (모두 file_hash 일치 skip)."""
    sync_mod.sync_dept(isolated_world["dept"])  # 첫 sync
    result = sync_mod.sync_dept(isolated_world["dept"])  # 두 번째

    assert result["status"] == "success"
    assert result["files_added"] == 0
    assert result["files_modified"] == 0
    assert result["files_deleted"] == 0
    assert result["chunks_upserted"] == 0
    assert result["chunks_deleted"] == 0


def test_sync_detects_modified_file(isolated_world: dict[str, Any]) -> None:
    """파일 1개 수정 → files_modified=1, chunks_upserted>0."""
    sync_mod.sync_dept(isolated_world["dept"])  # 첫 sync

    target = isolated_world["ref_root"] / isolated_world["dept"] / isolated_world["cat"] / "01.md"
    target.write_text("첫 자료 본문 — 수정된 내용 추가됨", encoding="utf-8")

    result = sync_mod.sync_dept(isolated_world["dept"])

    assert result["status"] == "success"
    assert result["files_added"] == 0
    assert result["files_modified"] == 1
    assert result["files_deleted"] == 0
    assert result["chunks_upserted"] >= 1


def test_sync_detects_deleted_file(isolated_world: dict[str, Any]) -> None:
    """파일 1개 삭제 → files_deleted=1, collection.delete 호출, chunks_deleted>0."""
    sync_mod.sync_dept(isolated_world["dept"])  # 첫 sync

    target = isolated_world["ref_root"] / isolated_world["dept"] / isolated_world["cat"] / "02.md"
    target.unlink()

    result = sync_mod.sync_dept(isolated_world["dept"])

    assert result["status"] == "success"
    assert result["files_deleted"] == 1
    assert result["chunks_deleted"] >= 1
    coll: FakeCollection = isolated_world["coll"]
    assert {m["source_id"] for _, m in coll._chunks.values()} == {"alpha/01.md"}


def test_db_run_log_records_each_sync(isolated_world: dict[str, Any]) -> None:
    """연속 sync 2회 시 DB 에 2 row 적재 + 인덱스 활용 query 가능."""
    r1 = sync_mod.sync_dept(isolated_world["dept"])
    r2 = sync_mod.sync_dept(isolated_world["dept"])

    rows = isolated_world["db"].fetch_all(
        "SELECT sync_id, status FROM knowledge_index_runs WHERE dept = ? ORDER BY started_at DESC, sync_id DESC",
        (isolated_world["dept"],),
    )
    sync_ids = {row["sync_id"] for row in rows}
    # 두 sync 모두 기록되어야 함 (동분 충돌 시 second-precision fallback 으로 PK 분리)
    assert {r1["sync_id"], r2["sync_id"]} <= sync_ids
    assert all(row["status"] in {"success", "partial"} for row in rows)


def test_sync_dept_missing_reference_dir_marks_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """reference dir 없는 dept 호출 → status=failed + DB row 의 error 채워짐."""
    monkeypatch.setattr(sync_mod, "REFERENCE_ROOT", tmp_path / "knowledge" / "reference")
    monkeypatch.setattr(sync_mod, "INDEX_ROOT", tmp_path / "data" / "chroma")
    reset_db()
    db = Database(tmp_path / "data" / "test.sqlite")
    monkeypatch.setattr("core.knowledge.sync.get_db", lambda: db)

    result = sync_mod.sync_dept("nonexistent_dept")
    assert result["status"] == "failed"
    assert "reference dir not found" in (result["error"] or "")

    row = db.fetch_one(
        "SELECT * FROM knowledge_index_runs WHERE sync_id = ?",
        (result["sync_id"],),
    )
    assert row is not None
    assert row["status"] == "failed"
    assert row["error"] is not None
