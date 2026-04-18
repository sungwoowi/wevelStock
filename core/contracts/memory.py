"""Memory layer contracts."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RollupPeriod = Literal["daily", "weekly", "monthly", "quarterly", "yearly"]


class MemoryRecord(BaseModel):
    """A single team judgment snapshot stored in team_memory."""

    team_id: str
    date: str  # YYYY-MM-DD (local tz)
    target: str
    input_hash: str
    verdict: str
    confidence: int = Field(ge=0, le=100)
    reasons: list[str]
    narrative: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    model: str | None = None
    contract_version: str = "1.0"


class RollupRecord(BaseModel):
    team_id: str
    period_type: RollupPeriod
    period_key: str
    summary_md: str = ""
    key_events: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class MemoryContext(BaseModel):
    """Assembled context passed to the LLM."""

    team_id: str
    recent_days: list[MemoryRecord] = Field(default_factory=list)
    weekly_rollups: list[RollupRecord] = Field(default_factory=list)
    monthly_rollups: list[RollupRecord] = Field(default_factory=list)
    total_tokens_estimate: int = 0


class LLMCallCache(BaseModel):
    input_hash: str
    model: str
    response_json: str
    tokens_in: int
    tokens_out: int
    cost_usd: float = 0.0
    ttl_days: int = 7
