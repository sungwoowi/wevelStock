"""Chroma EmbeddingFunction 어댑터.

INFRA-RAG-001 후: ingest/retrieve 가 Chroma collection 생성 시 이 함수의
반환을 `embedding_function=` 인자로 전달. 그 전엔 Chroma 가 영문 default
(`all-MiniLM-L6-v2`) 로 fallback 했음 — 한국어 학습부 RAG 의 핵심 wiring.
"""
from __future__ import annotations

from typing import Any

from core.config import env, get_config
from core.logging import get_logger

log = get_logger(__name__)


def get_embedding_function() -> Any:
    """Return a chromadb EmbeddingFunction instance based on runtime config.

    Raises RuntimeError when the configured backend is unusable (missing
    dependency or API key) — silent fallback would mean the user thinks
    한국어 RAG 가 동작한다고 믿지만 실제로 영문 임베딩이 깔리는 사고를 부른다.
    """
    cfg = get_config().knowledge.embedding

    if cfg.provider == "local":
        try:
            from chromadb.utils.embedding_functions import (  # type: ignore[import-not-found]
                SentenceTransformerEmbeddingFunction,
            )
        except ImportError as e:
            raise RuntimeError(
                "chromadb.utils.embedding_functions unavailable — "
                "ensure chromadb>=0.4 installed"
            ) from e
        log.info("embedding_function_init", provider="local", model=cfg.model)
        return SentenceTransformerEmbeddingFunction(model_name=cfg.model)

    if cfg.provider == "openai":
        try:
            from chromadb.utils.embedding_functions import (  # type: ignore[import-not-found]
                OpenAIEmbeddingFunction,
            )
        except ImportError as e:
            raise RuntimeError("chromadb OpenAI EF unavailable") from e
        key = env("OPENAI_API_KEY_FOR_EMBEDDING") or env("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY (or OPENAI_API_KEY_FOR_EMBEDDING) required "
                "for knowledge.embedding.provider=openai"
            )
        log.info("embedding_function_init", provider="openai", model=cfg.model)
        return OpenAIEmbeddingFunction(api_key=key, model_name=cfg.model)

    raise ValueError(f"unknown embedding provider: {cfg.provider}")
