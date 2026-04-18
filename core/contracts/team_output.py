"""StandardOutput — the canonical JSON contract every team must return.

See docs/CONTRACTS.md for the specification.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

CONTRACT_VERSION = "1.0"


class OutputMetadata(BaseModel):
    """Reproducibility metadata attached to every StandardOutput."""

    model: str | None = None
    canon_version: int | None = None
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    input_hash: str | None = None
    cost_usd: float | None = None


class StandardOutput(BaseModel):
    """Canonical team judgment record.

    All teams return this via agent.run(). Orchestrator writes to team_outputs.
    """

    team_id: str
    run_id: str
    timestamp: str  # ISO-8601 with timezone
    target: str = "global"
    verdict: str
    confidence: int = Field(ge=0, le=100)
    reasons: list[str] = Field(min_length=1)
    data: dict[str, Any] = Field(default_factory=dict)
    contract_version: str = CONTRACT_VERSION
    metadata: OutputMetadata = Field(default_factory=OutputMetadata)

    @field_validator("timestamp")
    @classmethod
    def _validate_timestamp(cls, v: str) -> str:
        # Ensure parseable and has tz info
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"timestamp must be ISO-8601: {v}") from e
        if dt.tzinfo is None:
            raise ValueError("timestamp must include timezone offset")
        return v

    @classmethod
    def build(
        cls,
        *,
        team_id: str,
        run_id: str,
        verdict: str,
        confidence: int,
        reasons: list[str],
        target: str = "global",
        data: dict[str, Any] | None = None,
        metadata: OutputMetadata | dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> StandardOutput:
        """Convenience builder with sensible defaults."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).astimezone().isoformat()
        if isinstance(metadata, dict):
            metadata = OutputMetadata(**metadata)
        if metadata is None:
            metadata = OutputMetadata()
        return cls(
            team_id=team_id,
            run_id=run_id,
            timestamp=timestamp,
            target=target,
            verdict=verdict,
            confidence=confidence,
            reasons=reasons,
            data=data or {},
            metadata=metadata,
        )


# Common verdict enums (optional typing aid; teams may extend)
PrincipleVerdict = Literal["compliant", "warning", "violation"]
BriefingVerdict = Literal["positive", "neutral", "caution", "alert"]
