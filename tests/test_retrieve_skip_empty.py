"""INFRA-RUNTIME-EFFICIENCY-001 (b) — 자료 0 시드 dept 의 RAG 자동 OFF.

대상: `core.knowledge.retrieve._get_collection(dept)` 가 빈 collection 이나
미존재 collection 에 대해 BGE-m3 wiring 전에 None 반환하는지 검증.

핵심 본질: `get_embedding_function()` 이 호출되지 않아야 BGE-m3 ~2.5GB 로딩이
회피된다. monkeypatch 로 호출 카운터를 박아 0 회 확인.
"""
from __future__ import annotations

import importlib
import sys
import types
from typing import Any

import pytest

retrieve_mod = importlib.import_module("core.knowledge.retrieve")


class FakeCollection:
    """get_collection().count() 호출만 검증 — query 는 본 테스트 대상 아님."""

    def __init__(self, chunk_count: int) -> None:
        self._count = chunk_count

    def count(self) -> int:
        return self._count


class FakeClient:
    """chromadb.PersistentClient stand-in."""

    def __init__(
        self,
        existing: FakeCollection | None = None,
        get_or_create: FakeCollection | None = None,
    ) -> None:
        self._existing = existing
        self._get_or_create = get_or_create
        self.get_or_create_calls = 0

    def get_collection(self, name: str) -> FakeCollection:  # noqa: ARG002
        if self._existing is None:
            raise ValueError("collection does not exist")
        return self._existing

    def get_or_create_collection(
        self, name: str, embedding_function: Any
    ) -> FakeCollection:  # noqa: ARG002
        self.get_or_create_calls += 1
        assert embedding_function is not None  # ef wiring 보장
        return self._get_or_create or FakeCollection(chunk_count=1)


@pytest.fixture
def patched_env(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Any]:
    """data/chroma/<dept>/ 가짜 디렉토리 + chromadb 모듈 + ef 카운터."""
    # 가짜 INDEX_ROOT — tmp_path/chroma
    monkeypatch.setattr(retrieve_mod, "INDEX_ROOT", tmp_path / "chroma")
    dept_dir = tmp_path / "chroma" / "test_dept"
    dept_dir.mkdir(parents=True)
    (dept_dir / "chroma.sqlite3").write_bytes(b"")  # iterdir 통과용

    ef_calls = {"count": 0}

    def _fake_ef() -> object:
        ef_calls["count"] += 1
        return object()  # truthy embedding_function

    monkeypatch.setattr(retrieve_mod, "get_embedding_function", _fake_ef)

    # chromadb fake 모듈 주입
    client_holder: dict[str, FakeClient | None] = {"client": None}

    def _fake_client_ctor(path: str) -> FakeClient:  # noqa: ARG001
        c = client_holder["client"]
        if c is None:
            raise RuntimeError("test setup did not register a FakeClient")
        return c

    fake_chromadb = types.SimpleNamespace(PersistentClient=_fake_client_ctor)
    monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)

    # lru_cache 초기화 — 이전 테스트의 결과가 새 monkeypatch 를 가린다
    retrieve_mod._get_collection.cache_clear()

    return {"client_holder": client_holder, "ef_calls": ef_calls}


def test_empty_collection_returns_none_without_ef_wiring(
    patched_env: dict[str, Any],
) -> None:
    """자료 0 시드: collection.count() == 0 → ef 호출 0 회 + None 반환."""
    patched_env["client_holder"]["client"] = FakeClient(
        existing=FakeCollection(chunk_count=0)
    )

    result = retrieve_mod._get_collection("test_dept")

    assert result is None
    assert patched_env["ef_calls"]["count"] == 0, (
        "ef 가 호출되면 BGE-m3 ~2.5GB 로딩이 trigger 됨 — 자료 0 시드에선 0 회여야 함"
    )


def test_missing_collection_returns_none_without_ef_wiring(
    patched_env: dict[str, Any],
) -> None:
    """collection 자체가 없음 (get_collection raise) → ef 호출 0 회 + None."""
    patched_env["client_holder"]["client"] = FakeClient(existing=None)

    result = retrieve_mod._get_collection("test_dept")

    assert result is None
    assert patched_env["ef_calls"]["count"] == 0


def test_populated_collection_wires_ef_normally(
    patched_env: dict[str, Any],
) -> None:
    """자료 있음: count() > 0 → ef 1 회 + collection 반환."""
    client = FakeClient(
        existing=FakeCollection(chunk_count=42),
        get_or_create=FakeCollection(chunk_count=42),
    )
    patched_env["client_holder"]["client"] = client

    result = retrieve_mod._get_collection("test_dept")

    assert result is not None
    assert patched_env["ef_calls"]["count"] == 1
    assert client.get_or_create_calls == 1


@pytest.mark.asyncio
async def test_retrieve_returns_empty_when_collection_skipped(
    patched_env: dict[str, Any],
) -> None:
    """end-to-end: 자료 0 시드 dept 에 retrieve 호출 → [] + ef 미호출."""
    patched_env["client_holder"]["client"] = FakeClient(
        existing=FakeCollection(chunk_count=0)
    )

    results = await retrieve_mod.retrieve("test_dept", "임의 질의")

    assert results == []
    assert patched_env["ef_calls"]["count"] == 0
