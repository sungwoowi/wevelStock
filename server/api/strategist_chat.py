"""전략가 (Layer 3) 호출 — 멀티턴 대화 endpoint.

CLI (`just chat-strategist`/`just ask-strategist`), 웹앱, 텔레그램 모두 이
endpoint 또는 직접 `core.strategist.run_strategist()` 를 wrap 하여 전략가에 질의한다.

Endpoints:
  POST /api/strategists/{strategist_id}/chat         — 멀티턴 messages → 응답 1턴
  POST /api/strategists/{strategist_id}/chat/stream  — SSE token streaming
  GET  /api/strategists/{strategist_id}              — 전략가 메타 정보

전략가 = `agents/strategists/<id>/manifest.yaml + persona.md`. 5-Layer 의 Layer 3.
analyst_chat 패턴 1:1 차용 + `target` 필드 추가 (전략가는 종목별 권고 발행 단위).
"""
from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.logging import get_logger
from core.strategist import (
    StrategistNotFoundError,
    run_strategist,
)
from core.strategist.run_strategist import run_strategist_stream

log = get_logger(__name__)

router = APIRouter(prefix="/strategists")


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


ProviderName = Literal["gemini", "claude_code", "anthropic", "mock"]


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    target: str = "global"  # team_outputs target (ticker 또는 "global")
    model: str | None = None
    include_memory: bool = True
    provider: ProviderName | None = None  # 명시 시 그 backend 강제 (auto fallback X)


class ChatResponse(BaseModel):
    text: str
    metadata: dict[str, Any]


@router.post("/{strategist_id}/chat", response_model=ChatResponse)
async def post_strategist_chat(
    strategist_id: str, payload: ChatRequest
) -> ChatResponse:
    """전략가에 멀티턴 messages 배열 전달 → 다음 응답 1턴 반환.

    클라이언트가 대화 history (messages) 를 매 요청마다 누적해 보낸다 (서버 stateless).
    canon · persona · RAG · 시계열 메모리 + reads_analysts 의 team_outputs DB 점수가
    system 블록으로 자동 주입.

    `target` 은 분석가 점수 조회 대상 (종목 ticker / "global"). 기본 = "global".
    `provider` 명시 시 그 backend 강제 (auto fallback X). None 이면 runtime.yaml +
    자동 폴백.
    """
    messages_dicts = [m.model_dump() for m in payload.messages]
    try:
        resp = await run_strategist(
            strategist_id,
            messages_dicts,
            target=payload.target,
            model=payload.model,
            include_memory=payload.include_memory,
            provider=payload.provider,
        )
    except StrategistNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.error(
            "strategist_chat_failed",
            strategist=strategist_id,
            target=payload.target,
            provider=payload.provider,
            error=str(e),
            error_type=type(e).__name__,
            error_repr=repr(e),
        )
        error_detail = str(e) or f"{type(e).__name__} (empty message)"
        raise HTTPException(status_code=500, detail=f"inference failed: {error_detail}") from e

    return ChatResponse(text=resp.text, metadata=resp.metadata)


@router.post("/{strategist_id}/chat/stream")
async def post_strategist_chat_stream(
    strategist_id: str, payload: ChatRequest,
) -> StreamingResponse:
    """전략가 streaming endpoint — SSE (text/event-stream).

    이벤트 (llm-stream-event-v1, analyst_chat 와 동일 schema):
        data: {"type":"text_delta","text":"..."}\n\n
        data: {"type":"metadata", ...}\n\n
        data: {"type":"error","message":"..."}\n\n
        data: {"type":"done"}\n\n
    """
    messages_dicts = [m.model_dump() for m in payload.messages]

    async def _event_stream():
        try:
            async for event in run_strategist_stream(
                strategist_id,
                messages_dicts,
                target=payload.target,
                model=payload.model,
                include_memory=payload.include_memory,
                provider=payload.provider,
            ):
                line = "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                yield line.encode("utf-8")
        except StrategistNotFoundError as e:
            err = {
                "type": "error",
                "message": str(e),
                "provider": "n/a",
                "fatal": True,
                "status": 404,
            }
            yield ("data: " + json.dumps(err, ensure_ascii=False) + "\n\n").encode("utf-8")
            yield ('data: {"type":"done"}\n\n').encode("utf-8")
        except Exception as e:  # noqa: BLE001
            log.error(
                "strategist_chat_stream_failed",
                strategist=strategist_id,
                target=payload.target,
                error=str(e),
                error_type=type(e).__name__,
                error_repr=repr(e),
            )
            error_detail = str(e) or f"{type(e).__name__} (empty message)"
            err = {
                "type": "error",
                "message": f"inference failed: {error_detail}",
                "provider": "n/a",
                "fatal": True,
                "status": 500,
            }
            yield ("data: " + json.dumps(err, ensure_ascii=False) + "\n\n").encode("utf-8")
            yield ('data: {"type":"done"}\n\n').encode("utf-8")

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{strategist_id}")
async def get_strategist_meta(strategist_id: str) -> dict:
    """전략가 메타 정보 (display_name, track, reads_analysts, reads, model 등).

    웹페이지에서 전략가 헤더를 표시할 때 사용.
    """
    from core.strategist import load_strategist_spec

    try:
        spec = load_strategist_spec(strategist_id)
    except StrategistNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return {
        "id": spec.id,
        "display_name": spec.display_name,
        "track": spec.track,
        "reads_analysts": spec.reads_analysts,
        "reads": spec.reads_depts,
        "canon_categories": spec.canon_categories,
        "model": spec.model,
        "max_tokens": spec.max_tokens,
        "temperature": spec.temperature,
    }
