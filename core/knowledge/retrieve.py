"""학습부(dept) 단위 RAG 회수 — Chroma 백업.

INFRA-RAG-001 5-Layer:
- 입력: dept 문자열 (= collection name = `data/chroma/<dept>/` 디렉토리)
- 임베딩 일치 보장: ingest 가 사용한 동일 `get_embedding_function()` 을 collection 에 wiring
- PersistentClient + collection 핸들은 `lru_cache` 로 dept 당 1회만 생성
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from core.contracts.knowledge import KnowledgeChunk, RetrievalResult
from core.knowledge.embed import get_embedding_function
from core.logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_ROOT = REPO_ROOT / "data" / "chroma"


def _index_dir(dept: str) -> Path:
    return INDEX_ROOT / dept


@lru_cache(maxsize=8)
def _get_collection(dept: str) -> Any | None:
    """Cache one Chroma collection per dept. Returns None if unusable."""
    idx = _index_dir(dept)
    if not idx.exists() or not any(idx.iterdir()):
        return None
    try:
        import chromadb  # type: ignore[import-not-found]
    except ImportError:
        log.debug("chroma_not_installed")
        return None
    try:
        ef = get_embedding_function()
        client = chromadb.PersistentClient(path=str(idx))
        return client.get_or_create_collection(name=dept, embedding_function=ef)
    except Exception as e:  # noqa: BLE001
        log.warning("chroma_open_failed", dept=dept, error=str(e))
        return None


async def retrieve(
    dept: str,
    query: str,
    *,
    categories: list[str] | None = None,
    top_k: int = 3,
) -> list[RetrievalResult]:
    """Retrieve top_k chunks from `data/chroma/<dept>/`, or [] if absent.

    `categories` 가 주어지면 chunk metadata 의 `category` 필드가 해당 리스트에
    속하는 청크만 반환 (KNOWLEDGE-SYNC-001 Phase 2 M1). None 이면 dept 전체.
    """
    collection = _get_collection(dept)
    if collection is None:
        return []
    where: dict[str, Any] | None
    if categories:
        where = {"category": {"$in": list(categories)}}
    else:
        where = None
    try:
        result = collection.query(query_texts=[query], n_results=top_k, where=where)
    except Exception as e:  # noqa: BLE001
        log.warning("chroma_query_failed", dept=dept, error=str(e))
        return []

    out: list[RetrievalResult] = []
    ids = result.get("ids", [[]])[0] if result.get("ids") else []
    docs = result.get("documents", [[]])[0] if result.get("documents") else []
    metas = result.get("metadatas", [[]])[0] if result.get("metadatas") else []
    distances = result.get("distances", [[]])[0] if result.get("distances") else []
    for i, doc in enumerate(docs):
        meta = metas[i] if i < len(metas) else {}
        out.append(
            RetrievalResult(
                chunk=KnowledgeChunk(
                    chunk_id=ids[i] if i < len(ids) else f"chunk-{i}",
                    team_id=dept,  # 5-Layer: contract field carries dept value
                    source_id=meta.get("source_id", "unknown"),
                    source_title=meta.get("source_title", ""),
                    source_type=meta.get("source_type", "markdown"),
                    text=doc,
                    tags=(
                        meta.get("tags", "").split(",") if meta.get("tags") else []
                    ),
                    metadata={k: str(v) for k, v in meta.items()},
                ),
                score=1.0 - distances[i] if i < len(distances) else 0.0,
            )
        )
    return out
