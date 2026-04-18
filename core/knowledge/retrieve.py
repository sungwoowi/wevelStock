"""RAG retrieval — Chroma-backed.

Graceful degradation: if Chroma or embeddings are unavailable, returns [].
The full ingestion pipeline (chunk.py, embed.py, store.py, compile.py) is
expected to be implemented before retrieval returns actual chunks.
"""
from __future__ import annotations

from pathlib import Path

from core.contracts.knowledge import KnowledgeChunk, RetrievalResult
from core.logging import get_logger
from core.registry import get_team

log = get_logger(__name__)


def _index_dir(team_id: str) -> Path | None:
    team = get_team(team_id)
    if team is None or team.path is None:
        return None
    return team.path / "knowledge" / "vector-index"


async def retrieve(team_id: str, query: str, top_k: int = 3) -> list[RetrievalResult]:
    """Retrieve top_k chunks from the team's Chroma index, or [] if absent."""
    idx = _index_dir(team_id)
    if idx is None or not idx.exists() or not any(idx.iterdir()):
        return []
    try:
        import chromadb  # type: ignore[import-not-found]
    except ImportError:
        log.debug("chroma_not_installed")
        return []

    try:
        client = chromadb.PersistentClient(path=str(idx))
        collection = client.get_or_create_collection(name=team_id)
        result = collection.query(query_texts=[query], n_results=top_k)
    except Exception as e:  # noqa: BLE001
        log.warning("chroma_query_failed", team=team_id, error=str(e))
        return []

    out: list[RetrievalResult] = []
    ids = result.get("ids", [[]])[0] if result.get("ids") else []
    docs = result.get("documents", [[]])[0] if result.get("documents") else []
    metas = result.get("metadatas", [[]])[0] if result.get("metadatas") else []
    distances = result.get("distances", [[]])[0] if result.get("distances") else []
    for i, doc in enumerate(docs):
        meta = metas[i] if i < len(metas) else {}
        out.append(RetrievalResult(
            chunk=KnowledgeChunk(
                chunk_id=ids[i] if i < len(ids) else f"chunk-{i}",
                team_id=team_id,
                source_id=meta.get("source_id", "unknown"),
                source_title=meta.get("source_title", ""),
                source_type=meta.get("source_type", "markdown"),
                text=doc,
                tags=meta.get("tags", "").split(",") if meta.get("tags") else [],
                metadata={k: str(v) for k, v in meta.items()},
            ),
            score=1.0 - distances[i] if i < len(distances) else 0.0,
        ))
    return out
