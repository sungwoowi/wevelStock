"""KNOWLEDGE-SYNC-001 Phase 2 M1 — retrieve() 카테고리 필터.

대상: `core.knowledge.retrieve.retrieve(dept, query, *, categories=None, top_k=3)`
- categories=None 이면 ChromaDB query 의 where 인자 = None (legacy 동작)
- categories=[...] 이면 where={"category": {"$in": [...]}} 전달

실 chromadb 호출 없음 — `_get_collection` 을 monkeypatch 로 fake collection 으로 교체.
"""
from __future__ import annotations

import importlib
from typing import Any

import pytest

# core/knowledge/__init__.py 에서 `from .retrieve import retrieve` 로 함수가
# 패키지 attribute 를 가로채서 `import core.knowledge.retrieve` 가 모듈이 아니라
# 함수를 반환한다. importlib 로 모듈을 명시적으로 가져와서 우회.
retrieve_mod = importlib.import_module("core.knowledge.retrieve")


class FakeCollection:
    """`collection.query` 호출을 캡쳐하는 fake. chromadb 응답 형식 모방."""

    def __init__(self) -> None:
        self.last_call: dict[str, Any] | None = None

    def query(
        self,
        *,
        query_texts: list[str],
        n_results: int,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.last_call = {
            "query_texts": query_texts,
            "n_results": n_results,
            "where": where,
        }
        return {
            "ids": [["chunk-0"]],
            "documents": [["fake document body"]],
            "metadatas": [[{
                "source_id": "cat_a/file.md",
                "source_title": "Fake",
                "source_type": "markdown",
                "category": "cat_a",
            }]],
            "distances": [[0.1]],
        }


@pytest.fixture
def fake_collection(monkeypatch: pytest.MonkeyPatch) -> FakeCollection:
    fc = FakeCollection()
    monkeypatch.setattr(retrieve_mod, "_get_collection", lambda dept: fc)
    return fc


@pytest.mark.asyncio
async def test_retrieve_without_categories_passes_none_where(
    fake_collection: FakeCollection,
) -> None:
    """legacy 동작: categories=None → where=None (모든 카테고리)."""
    results = await retrieve_mod.retrieve("test_dept", "query text")
    assert fake_collection.last_call is not None
    assert fake_collection.last_call["where"] is None
    assert fake_collection.last_call["n_results"] == 3
    assert len(results) == 1
    assert results[0].chunk.metadata["category"] == "cat_a"


@pytest.mark.asyncio
async def test_retrieve_with_categories_passes_where_in_filter(
    fake_collection: FakeCollection,
) -> None:
    """categories=[...] → where={'category': {'$in': [...]}}."""
    await retrieve_mod.retrieve(
        "test_dept", "query", categories=["cat_a", "cat_b"], top_k=5
    )
    assert fake_collection.last_call is not None
    assert fake_collection.last_call["where"] == {
        "category": {"$in": ["cat_a", "cat_b"]}
    }
    assert fake_collection.last_call["n_results"] == 5


@pytest.mark.asyncio
async def test_retrieve_empty_categories_treated_as_none(
    fake_collection: FakeCollection,
) -> None:
    """categories=[] (빈 리스트) → falsy 라 where=None (안전 fallback)."""
    await retrieve_mod.retrieve("test_dept", "query", categories=[])
    assert fake_collection.last_call is not None
    assert fake_collection.last_call["where"] is None


@pytest.mark.asyncio
async def test_retrieve_collection_missing_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """collection 이 None 이어도 categories 무관하게 [] 반환."""
    monkeypatch.setattr(retrieve_mod, "_get_collection", lambda dept: None)
    results = await retrieve_mod.retrieve(
        "missing_dept", "q", categories=["foo"]
    )
    assert results == []
