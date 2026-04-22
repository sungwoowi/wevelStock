"""BriefingPart — briefing-part-v1 계약.

파이프라인 1회 실행(=브리핑) 의 내부 UI 섹션(=파트) 단위 JSON 스키마.
텔레그램 봇과 웹앱이 동일한 API 를 소비하도록 하는 공통 계약.

See docs/specs/BRIEFING-ON-DEMAND-001-briefings-on-demand.md
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

CONTRACT_VERSION = "1.0"

BriefingStatus = Literal["ok", "degraded"]


class BriefingPart(BaseModel):
    """브리핑의 UI 섹션 1개. `data` 필드 내부 스키마는 파이프라인별 자유."""

    key: str  # overnight | scenario | positions | ...
    label: str
    order: int = Field(ge=1)
    data: dict[str, Any] = Field(default_factory=dict)


class BriefingResponse(BaseModel):
    """`GET/POST /api/briefings/{pipeline_id}/...` 응답.

    렌더링(텔레그램 텍스트 / 웹앱 컴포넌트)은 클라이언트 책임.
    서버는 구조화 JSON 만 반환.
    """

    pipeline_id: str
    run_id: str
    generated_at: str  # ISO-8601 with timezone
    status: BriefingStatus = "ok"
    cache_hit: bool = False
    parts: list[BriefingPart] = Field(default_factory=list)
    contract_version: str = CONTRACT_VERSION

    @field_validator("generated_at")
    @classmethod
    def _validate_generated_at(cls, v: str) -> str:
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"generated_at must be ISO-8601: {v}") from e
        if dt.tzinfo is None:
            raise ValueError("generated_at must include timezone offset")
        return v

    @classmethod
    def build(
        cls,
        *,
        pipeline_id: str,
        run_id: str,
        parts: list[BriefingPart],
        status: BriefingStatus = "ok",
        cache_hit: bool = False,
        generated_at: str | None = None,
    ) -> BriefingResponse:
        if generated_at is None:
            generated_at = datetime.now(timezone.utc).astimezone().isoformat()
        return cls(
            pipeline_id=pipeline_id,
            run_id=run_id,
            generated_at=generated_at,
            status=status,
            cache_hit=cache_hit,
            parts=parts,
        )


class BriefingResendResponse(BaseModel):
    """`POST /api/briefings/{pipeline_id}/resend` 응답."""

    pipeline_id: str
    run_id: str
    delivered: list[str] = Field(default_factory=list)  # ["telegram"] 등
    contract_version: str = CONTRACT_VERSION
