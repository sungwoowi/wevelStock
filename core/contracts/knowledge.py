"""Knowledge (RAG) layer contracts."""
from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeChunk(BaseModel):
    """A single retrievable chunk of team knowledge."""

    chunk_id: str
    team_id: str
    source_id: str           # file path or youtube URL etc
    source_title: str = ""
    source_type: str = "markdown"  # markdown | pdf | youtube | text
    text: str
    tokens: int = 0
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    chunk: KnowledgeChunk
    score: float = 0.0


class CanonInfo(BaseModel):
    """Summary of a team's compiled.md (Canon)."""

    team_id: str
    version: int = 0
    path: str = "knowledge/compiled.md"
    token_budget: int = 8000
    last_compiled: str | None = None


class SystemPromptBundle(BaseModel):
    """System prompt blocks ready for Anthropic messages API.

    `blocks` is shaped for prompt caching: early blocks can be marked with
    cache_control to benefit from ephemeral cache (5-min TTL, 90% discount).
    """

    blocks: list[dict] = Field(default_factory=list)
    cache_breakpoint_count: int = 0
    total_tokens_estimate: int = 0
