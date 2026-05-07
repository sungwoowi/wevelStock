"""분석가 추론부 조회 — 멀티턴 대화 endpoint.

CLI (`just chat`/`just ask`), 웹앱, 텔레그램 모두 이 endpoint 또는 직접
`core.inference.run_analyst()` 를 wrap 하여 분석가에 질의한다.

Endpoints:
  POST /api/analysts/{analyst_id}/chat   — 멀티턴 messages 배열 받아 응답 1턴 반환

분석가 = `agents/analysts/<id>/manifest.yaml + persona.md`. 5-Layer 의 Layer 2.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.inference import (
    AnalystNotFoundError,
    run_analyst,
)
from core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/analysts")


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


ProviderName = Literal["gemini", "claude_code", "anthropic", "mock"]


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    model: str | None = None
    include_memory: bool = True
    provider: ProviderName | None = None  # 명시 시 그 backend 강제 (auto fallback X)


class ChatResponse(BaseModel):
    text: str
    metadata: dict[str, Any]


@router.post("/{analyst_id}/chat", response_model=ChatResponse)
async def post_analyst_chat(analyst_id: str, payload: ChatRequest) -> ChatResponse:
    """분석가에 멀티턴 messages 배열 전달 → 다음 응답 1턴 반환.

    클라이언트가 대화 history (messages) 를 매 요청마다 누적해 보낸다 (서버 stateless).
    분석가의 canon · persona · RAG · 시계열 메모리는 system 블록으로 자동 주입.

    provider 가 명시되면 그 backend 로 강제 호출 (톤 비교용). None 이면
    config.llm.provider + 자동 폴백 체인.
    """
    messages_dicts = [m.model_dump() for m in payload.messages]
    try:
        resp = await run_analyst(
            analyst_id,
            messages_dicts,
            model=payload.model,
            include_memory=payload.include_memory,
            provider=payload.provider,
        )
    except AnalystNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.error(
            "analyst_chat_failed",
            analyst=analyst_id,
            provider=payload.provider,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"inference failed: {e}") from e

    return ChatResponse(text=resp.text, metadata=resp.metadata)


@router.get("/{analyst_id}")
async def get_analyst_meta(analyst_id: str) -> dict:
    """분석가 메타 정보 (display_name, learning_dept, reads, model).

    웹페이지에서 분석가 헤더를 표시할 때 사용.
    """
    from core.inference import load_analyst_spec

    try:
        spec = load_analyst_spec(analyst_id)
    except AnalystNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return {
        "id": spec.id,
        "display_name": spec.display_name,
        "learning_dept": spec.learning_dept,
        "reads": spec.reads,
        "model": spec.model,
        "max_tokens": spec.max_tokens,
        "temperature": spec.temperature,
    }
