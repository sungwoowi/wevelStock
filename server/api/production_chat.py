"""Production chat API — PRODUCTION-UX-001.

사용자 자연어 발화 → Intent Classifier → Router → 분석가/전략가 호출 →
SSE 스트림 (또는 JSON 응답).

Endpoints:
  POST /api/chat/production          — 단일 응답 (classification + agent_responses 풀세트)
  POST /api/chat/production/stream   — SSE 스트림 (classification 먼저 + agent text_delta 청크)
  GET  /api/chat/production/info     — production-chat 라우팅 메타 (v1 시연 시나리오, fallback 정책)

contract = production-chat-v1.
"""
from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.intent import (
    classify_intent,
    route_intent,
    route_intent_stream,
)
from core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/chat/production")


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


ProviderName = Literal["gemini", "claude_code", "anthropic", "mock"]


class ProductionChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    provider: ProviderName | None = None
    skip_cache: bool = False  # 테스트/디버깅용
    skip_stage2: bool = False  # Stage 1 만 검증 (테스트용)
    manual_override: dict[str, Any] | None = None  # IntentFallback (PROD-UX-2 후속)


class ProductionChatResponse(BaseModel):
    classification: dict[str, Any]
    agent_responses: list[dict[str, Any]]
    error: str | None = None
    latency_ms: int


def _last_user_text(messages: list[ChatMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    return ""


@router.post("", response_model=ProductionChatResponse)
async def post_production_chat(payload: ProductionChatRequest) -> ProductionChatResponse:
    """단일 응답 — classification + agent_responses 풀세트 JSON.

    멀티턴 messages 배열을 받지만 분류는 **마지막 user 메시지** 기준.
    분석가/전략가 호출 시엔 전체 messages 전달 (멀티턴 컨텍스트 유지).
    """
    last_user = _last_user_text(payload.messages)
    if not last_user.strip():
        raise HTTPException(status_code=400, detail="last user message is empty")

    # manual_override = PROD-UX-2 IntentFallback drop-down 결과. v1 기본 None.
    if payload.manual_override:
        from core.intent.classifier import IntentClassification

        classification = IntentClassification(
            scenario_id=int(payload.manual_override.get("scenario_id", 0)),
            ticker=payload.manual_override.get("ticker"),
            ticker_display=payload.manual_override.get("ticker_display"),
            agent_route=payload.manual_override.get("agent_route", "refuse_or_guide"),
            analyst_ids=list(payload.manual_override.get("analyst_ids") or []),
            confidence=1.0,
            manual_fallback_required=False,
            stage="deterministic",
            latency_ms=0,
            raw_input=last_user,
            reasoning="manual_override",
        )
    else:
        classification = await classify_intent(
            last_user,
            skip_cache=payload.skip_cache,
            skip_stage2=payload.skip_stage2,
            provider=payload.provider,
        )

    messages_dicts = [m.model_dump() for m in payload.messages]
    route_resp = await route_intent(
        classification, messages_dicts, provider=payload.provider
    )
    return ProductionChatResponse(
        classification=route_resp.classification,
        agent_responses=route_resp.agent_responses,
        error=route_resp.error,
        latency_ms=route_resp.latency_ms,
    )


@router.post("/stream")
async def post_production_chat_stream(payload: ProductionChatRequest) -> StreamingResponse:
    """SSE 스트림 — analyst_chat /chat/stream 패턴 mirror + classification 이벤트 첨가.

    이벤트:
        data: {"type":"classification", "scenario_id":1, ...}\n\n
        data: {"type":"agent_start", "agent":"track_a", "kind":"strategist"}\n\n
        data: {"type":"text_delta", "text":"...", "agent":"track_a"}\n\n
        data: {"type":"agent_metadata", "agent":"track_a", ...}\n\n
        data: {"type":"agent_done", "agent":"track_a"}\n\n
        data: {"type":"done"}\n\n
    """
    last_user = _last_user_text(payload.messages)
    if not last_user.strip():
        raise HTTPException(status_code=400, detail="last user message is empty")

    messages_dicts = [m.model_dump() for m in payload.messages]

    async def _event_stream():
        try:
            if payload.manual_override:
                from core.intent.classifier import IntentClassification

                classification = IntentClassification(
                    scenario_id=int(payload.manual_override.get("scenario_id", 0)),
                    ticker=payload.manual_override.get("ticker"),
                    ticker_display=payload.manual_override.get("ticker_display"),
                    agent_route=payload.manual_override.get("agent_route", "refuse_or_guide"),
                    analyst_ids=list(payload.manual_override.get("analyst_ids") or []),
                    confidence=1.0,
                    manual_fallback_required=False,
                    stage="deterministic",
                    latency_ms=0,
                    raw_input=last_user,
                    reasoning="manual_override",
                )
            else:
                classification = await classify_intent(
                    last_user,
                    skip_cache=payload.skip_cache,
                    skip_stage2=payload.skip_stage2,
                    provider=payload.provider,
                )

            async for event in route_intent_stream(
                classification, messages_dicts, provider=payload.provider
            ):
                line = "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                yield line.encode("utf-8")
        except Exception as e:  # noqa: BLE001
            log.error(
                "production_chat_stream_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            err = {
                "type": "error",
                "message": f"production chat failed: {e}",
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


@router.get("/info")
async def get_production_chat_info() -> dict:
    """라우팅 메타 — webapp 헤더에 표시할 v1 정보."""
    return {
        "spec": "PRODUCTION-UX-001",
        "version": "PROD-UX-1",
        "v1_demo_scenarios": [1, 2, 3, 4, 5],
        "v1_frozen_scenarios": list(range(1, 12)),
        "agent_routes": [
            "track_a",
            "track_b",
            "both",
            "analyst_direct",
            "refuse_or_guide",
            "pending_ms5",
        ],
        "manual_fallback_trigger": "confidence < 0.6 OR (ticker 필요 시나리오 + ticker 미매핑)",
        "notes": [
            "PROD-UX-1 = raw 분석가/전략가 응답 표시. 자연어 압축 포맷터는 PROD-UX-2 후속.",
            "기존 /analyst-chat / /strategist-chat 보존 (R&D 데모).",
        ],
    }
