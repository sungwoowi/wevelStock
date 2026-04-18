"""Embedding generation — OpenAI or local sentence-transformers.

Graceful: if neither is available, returns None and caller skips RAG.
"""
from __future__ import annotations

from core.config import env, get_config
from core.logging import get_logger

log = get_logger(__name__)


async def embed_texts(texts: list[str]) -> list[list[float]] | None:
    """Return a list of embedding vectors, or None if backend unavailable."""
    cfg = get_config().knowledge.embedding
    if cfg.provider == "openai":
        return await _embed_openai(texts, cfg.model)
    if cfg.provider == "local":
        return _embed_local(texts, cfg.model)
    return None


async def _embed_openai(texts: list[str], model: str) -> list[list[float]] | None:
    key = env("OPENAI_API_KEY_FOR_EMBEDDING") or env("OPENAI_API_KEY")
    if not key:
        log.warning("no_openai_embedding_key")
        return None
    try:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "input": texts},
            )
            if resp.status_code != 200:
                log.warning("openai_embed_failed", status=resp.status_code)
                return None
            data = resp.json()
            return [item["embedding"] for item in data["data"]]
    except Exception as e:  # noqa: BLE001
        log.warning("openai_embed_error", error=str(e))
        return None


def _embed_local(texts: list[str], model_name: str) -> list[list[float]] | None:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
    except ImportError:
        log.warning("sentence_transformers_not_installed")
        return None
    model = SentenceTransformer(model_name)
    vectors = model.encode(texts, convert_to_numpy=True)
    return vectors.tolist()
