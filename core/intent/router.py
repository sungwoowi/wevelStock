"""Intent router — IntentClassification → 분석가/전략가 호출.

PRODUCTION-UX-001 § 아키텍처 [2] Router. agent_route 별 분기:
  - track_a / track_b → run_strategist(track_id, messages, target=ticker)
  - both              → run_strategist("track_a") + run_strategist("track_b") (asyncio.gather)
  - analyst_direct    → run_analyst(analyst_id, messages, target_ticker=ticker) × N
  - refuse_or_guide   → LLM 직접 답변 (FAST tier, persona/RAG 없이 짧은 안내)
  - pending_ms5       → 고정 안내 메시지 (MS5 미도달)

PROD-UX-1 = raw 응답 그대로 표시 (포맷터 PROD-UX-2 후속).
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from core.inference.run_analyst import (
    AnalystNotFoundError,
    run_analyst,
    run_analyst_stream,
)
from core.intent.classifier import IntentClassification
from core.llm.client import call_llm, call_llm_stream
from core.llm.tiers import resolve_model_for_area
from core.logging import get_logger
from core.strategist.run_strategist import (
    StrategistNotFoundError,
    run_strategist,
    run_strategist_stream,
)

log = get_logger(__name__)


@dataclass
class RouteResponse:
    """라우팅 결과 — agent 별 응답 묶음."""

    classification: dict[str, Any]
    agent_responses: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_REFUSE_GUIDE_SYSTEM = (
    "당신은 wevelStock 의 안내자입니다. 사용자가 시스템 영역 밖 (세금/감정/일반 안내) "
    "질문을 던졌거나 표현이 모호합니다. 1~2 문장으로 친절히 안내하고, 추천 발화 예시 "
    "3개를 bullet 로 제시하세요. 코드 라벨 (S-Score/α/F-Score 등) 사용 금지."
)

_PENDING_MS5_TEXT = (
    "자가 진화 / 시스템 회고 기능은 아직 활성화되지 않았습니다 (MS5 후 활성). "
    "지금은 종목 분석·매수/매도 판단·시장 평가만 가능합니다. 예시:\n"
    "- 삼성전자 들고 있는데 어떻게 해\n"
    "- 지금 시장 어때\n"
    "- 어떤 섹터 강해"
)


async def _call_strategist_safe(
    strategist_id: str,
    messages: list[dict],
    *,
    target: str,
    provider: str | None,
) -> dict[str, Any]:
    """run_strategist wrap — 실패 시 error 필드 채워 반환 (예외 raise X)."""
    try:
        resp = await run_strategist(
            strategist_id, messages, target=target, provider=provider
        )
        return {
            "kind": "strategist",
            "agent_id": strategist_id,
            "target": target,
            "text": resp.text,
            "metadata": resp.metadata,
        }
    except StrategistNotFoundError as e:
        log.warning("router_strategist_missing", strategist=strategist_id, error=str(e))
        return {
            "kind": "strategist",
            "agent_id": strategist_id,
            "target": target,
            "text": "",
            "metadata": {},
            "error": str(e),
        }
    except Exception as e:  # noqa: BLE001
        log.error(
            "router_strategist_failed",
            strategist=strategist_id,
            error_type=type(e).__name__,
            error=str(e),
        )
        return {
            "kind": "strategist",
            "agent_id": strategist_id,
            "target": target,
            "text": "",
            "metadata": {},
            "error": f"{type(e).__name__}: {e}",
        }


async def _call_analyst_safe(
    analyst_id: str,
    messages: list[dict],
    *,
    target_ticker: str | None,
    provider: str | None,
) -> dict[str, Any]:
    """run_analyst wrap — 실패 시 error 필드 채워 반환."""
    try:
        resp = await run_analyst(
            analyst_id,
            messages,
            target_ticker=target_ticker,
            provider=provider,
        )
        return {
            "kind": "analyst",
            "agent_id": analyst_id,
            "target": target_ticker,
            "text": resp.text,
            "metadata": resp.metadata,
        }
    except AnalystNotFoundError as e:
        log.warning("router_analyst_missing", analyst=analyst_id, error=str(e))
        return {
            "kind": "analyst",
            "agent_id": analyst_id,
            "target": target_ticker,
            "text": "",
            "metadata": {},
            "error": str(e),
        }
    except Exception as e:  # noqa: BLE001
        log.error(
            "router_analyst_failed",
            analyst=analyst_id,
            error_type=type(e).__name__,
            error=str(e),
        )
        return {
            "kind": "analyst",
            "agent_id": analyst_id,
            "target": target_ticker,
            "text": "",
            "metadata": {},
            "error": f"{type(e).__name__}: {e}",
        }


async def _call_refuse_or_guide(
    classification: IntentClassification, provider: str | None
) -> dict[str, Any]:
    """refuse_or_guide — FAST tier LLM 직접 답변. persona/RAG 없음."""
    provider_resolved, model = resolve_model_for_area("answer_formatter")
    if provider:
        provider_resolved = provider
    user_msg = (
        f"사용자 발화: {classification.raw_input}\n"
        f"분류 결과: scenario_id={classification.scenario_id}, "
        f"confidence={classification.confidence:.2f}, "
        f"reasoning={classification.reasoning}\n\n"
        "위 발화에 대해 안내 답변을 작성하세요."
    )
    try:
        resp = await call_llm(
            system=_REFUSE_GUIDE_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
            model=model,
            max_tokens=400,
            temperature=0.5,
            provider=provider_resolved if provider_resolved != "mock" else None,
        )
        return {
            "kind": "refuse_or_guide",
            "agent_id": "guide",
            "target": None,
            "text": resp.get("content", ""),
            "metadata": {
                "model": resp.get("model", model),
                "tokens_in": resp.get("tokens_in", 0),
                "tokens_out": resp.get("tokens_out", 0),
                "cost_usd": resp.get("cost_usd", 0.0),
            },
        }
    except Exception as e:  # noqa: BLE001
        log.error("router_refuse_guide_failed", error_type=type(e).__name__, error=str(e))
        return {
            "kind": "refuse_or_guide",
            "agent_id": "guide",
            "target": None,
            "text": (
                "안내 답변 생성에 실패했습니다. 잠시 후 다시 시도해주세요. "
                "예시 발화: '삼성전자 어때', '지금 시장 어때', '어떤 섹터 강해'"
            ),
            "metadata": {"error": f"{type(e).__name__}: {e}"},
            "error": f"{type(e).__name__}: {e}",
        }


def _pending_ms5_response() -> dict[str, Any]:
    return {
        "kind": "pending_ms5",
        "agent_id": "ms5_placeholder",
        "target": None,
        "text": _PENDING_MS5_TEXT,
        "metadata": {"info": "scenario 11 = MS5 후 활성"},
    }


async def route_intent(
    classification: IntentClassification,
    messages: list[dict],
    *,
    provider: str | None = None,
) -> RouteResponse:
    """IntentClassification 에 따라 분석가/전략가/안내 호출. raw 응답 묶음 반환.

    Args:
        classification: classify_intent() 결과.
        messages: 사용자 멀티턴 messages 배열 (run_analyst/run_strategist 가 요구).
        provider: 명시 backend (None = config + auto fallback).

    Returns:
        RouteResponse(classification=dict, agent_responses=list[dict], latency_ms).
    """
    started = time.monotonic()
    route = classification.agent_route
    ticker = classification.ticker

    responses: list[dict[str, Any]] = []

    if route == "track_a":
        target = ticker or "global"
        responses.append(
            await _call_strategist_safe("track_a", messages, target=target, provider=provider)
        )
    elif route == "track_b":
        target = ticker or "global"
        responses.append(
            await _call_strategist_safe("track_b", messages, target=target, provider=provider)
        )
    elif route == "both":
        target = ticker or "global"
        results = await asyncio.gather(
            _call_strategist_safe("track_a", messages, target=target, provider=provider),
            _call_strategist_safe("track_b", messages, target=target, provider=provider),
            return_exceptions=False,
        )
        responses.extend(results)
    elif route == "analyst_direct":
        analyst_ids = classification.analyst_ids or []
        if not analyst_ids:
            log.warning("router_analyst_direct_no_ids", scenario=classification.scenario_id)
            responses.append(await _call_refuse_or_guide(classification, provider))
        else:
            results = await asyncio.gather(
                *(
                    _call_analyst_safe(aid, messages, target_ticker=ticker, provider=provider)
                    for aid in analyst_ids
                ),
                return_exceptions=False,
            )
            responses.extend(results)
    elif route == "refuse_or_guide":
        responses.append(await _call_refuse_or_guide(classification, provider))
    elif route == "pending_ms5":
        responses.append(_pending_ms5_response())
    else:
        log.warning("router_unknown_route", route=route)
        responses.append(await _call_refuse_or_guide(classification, provider))

    return RouteResponse(
        classification=classification.to_dict(),
        agent_responses=responses,
        latency_ms=int((time.monotonic() - started) * 1000),
    )


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


async def _stream_strategist_safe(
    strategist_id: str,
    messages: list[dict],
    *,
    target: str,
    provider: str | None,
    agent_label: str,
):
    """run_strategist_stream wrap — agent 라벨 prefix 첨가."""
    try:
        async for event in run_strategist_stream(
            strategist_id, messages, target=target, provider=provider
        ):
            etype = event.get("type")
            if etype == "text_delta":
                yield {"type": "text_delta", "text": event["text"], "agent": agent_label}
            elif etype == "metadata":
                yield {"type": "agent_metadata", "agent": agent_label, **event}
            elif etype == "error":
                yield {"type": "agent_error", "agent": agent_label, **event}
            elif etype == "done":
                yield {"type": "agent_done", "agent": agent_label}
            else:
                yield event
    except StrategistNotFoundError as e:
        yield {
            "type": "agent_error",
            "agent": agent_label,
            "message": str(e),
            "fatal": True,
        }
        yield {"type": "agent_done", "agent": agent_label}
    except Exception as e:  # noqa: BLE001
        log.error(
            "router_strategist_stream_failed",
            strategist=strategist_id,
            error_type=type(e).__name__,
            error=str(e),
        )
        yield {
            "type": "agent_error",
            "agent": agent_label,
            "message": f"{type(e).__name__}: {e}",
            "fatal": True,
        }
        yield {"type": "agent_done", "agent": agent_label}


async def _stream_analyst_safe(
    analyst_id: str,
    messages: list[dict],
    *,
    target_ticker: str | None,
    provider: str | None,
    agent_label: str,
):
    """run_analyst_stream wrap — agent 라벨 prefix."""
    try:
        async for event in run_analyst_stream(
            analyst_id, messages, target_ticker=target_ticker, provider=provider
        ):
            etype = event.get("type")
            if etype == "text_delta":
                yield {"type": "text_delta", "text": event["text"], "agent": agent_label}
            elif etype == "metadata":
                yield {"type": "agent_metadata", "agent": agent_label, **event}
            elif etype == "error":
                yield {"type": "agent_error", "agent": agent_label, **event}
            elif etype == "done":
                yield {"type": "agent_done", "agent": agent_label}
            else:
                yield event
    except AnalystNotFoundError as e:
        yield {
            "type": "agent_error",
            "agent": agent_label,
            "message": str(e),
            "fatal": True,
        }
        yield {"type": "agent_done", "agent": agent_label}
    except Exception as e:  # noqa: BLE001
        log.error(
            "router_analyst_stream_failed",
            analyst=analyst_id,
            error_type=type(e).__name__,
            error=str(e),
        )
        yield {
            "type": "agent_error",
            "agent": agent_label,
            "message": f"{type(e).__name__}: {e}",
            "fatal": True,
        }
        yield {"type": "agent_done", "agent": agent_label}


async def _stream_refuse_or_guide(
    classification: IntentClassification, provider: str | None, agent_label: str
):
    """refuse_or_guide streaming — FAST tier."""
    provider_resolved, model = resolve_model_for_area("answer_formatter")
    if provider:
        provider_resolved = provider
    user_msg = (
        f"사용자 발화: {classification.raw_input}\n"
        f"분류 결과: scenario_id={classification.scenario_id}, "
        f"confidence={classification.confidence:.2f}\n\n"
        "위 발화에 안내 답변을 작성하세요."
    )
    try:
        async for event in call_llm_stream(
            system=_REFUSE_GUIDE_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
            model=model,
            max_tokens=400,
            temperature=0.5,
            provider=provider_resolved if provider_resolved != "mock" else None,
        ):
            etype = event.get("type")
            if etype == "text_delta":
                yield {"type": "text_delta", "text": event["text"], "agent": agent_label}
            elif etype == "metadata":
                yield {"type": "agent_metadata", "agent": agent_label, **event}
            elif etype == "error":
                yield {"type": "agent_error", "agent": agent_label, **event}
            elif etype == "done":
                yield {"type": "agent_done", "agent": agent_label}
    except Exception as e:  # noqa: BLE001
        log.error("router_refuse_guide_stream_failed", error=str(e))
        yield {
            "type": "agent_error",
            "agent": agent_label,
            "message": f"{type(e).__name__}: {e}",
            "fatal": True,
        }
        yield {"type": "agent_done", "agent": agent_label}


async def route_intent_stream(
    classification: IntentClassification,
    messages: list[dict],
    *,
    provider: str | None = None,
):
    """IntentClassification → SSE 이벤트 stream.

    Yields:
        {"type": "classification", **classification.to_dict()}              # 최초 1회
        {"type": "agent_start", "agent": "<label>", "kind": "..."}          # 각 agent 시작
        {"type": "text_delta", "text": "...", "agent": "<label>"}            # 토큰 청크
        {"type": "agent_metadata", "agent": "<label>", ...}                  # agent 종료 직전
        {"type": "agent_error", "agent": "<label>", "message": "..."}
        {"type": "agent_done", "agent": "<label>"}
        {"type": "done"}                                                     # 최종

    "both" 또는 "analyst_direct" multi-agent 시 = 순차 stream (sequential),
    동시 stream 은 PROD-UX-2 후속 (텍스트 인터리브 UX 복잡도).
    """
    yield {"type": "classification", **classification.to_dict()}

    route = classification.agent_route
    ticker = classification.ticker

    if route in ("track_a", "track_b"):
        target = ticker or "global"
        label = route
        yield {"type": "agent_start", "agent": label, "kind": "strategist"}
        async for ev in _stream_strategist_safe(
            route, messages, target=target, provider=provider, agent_label=label
        ):
            yield ev
    elif route == "both":
        target = ticker or "global"
        for sid in ("track_a", "track_b"):
            yield {"type": "agent_start", "agent": sid, "kind": "strategist"}
            async for ev in _stream_strategist_safe(
                sid, messages, target=target, provider=provider, agent_label=sid
            ):
                yield ev
    elif route == "analyst_direct":
        analyst_ids = classification.analyst_ids or []
        if not analyst_ids:
            yield {"type": "agent_start", "agent": "guide", "kind": "refuse_or_guide"}
            async for ev in _stream_refuse_or_guide(classification, provider, "guide"):
                yield ev
        else:
            for aid in analyst_ids:
                yield {"type": "agent_start", "agent": aid, "kind": "analyst"}
                async for ev in _stream_analyst_safe(
                    aid, messages, target_ticker=ticker, provider=provider, agent_label=aid
                ):
                    yield ev
    elif route == "refuse_or_guide":
        yield {"type": "agent_start", "agent": "guide", "kind": "refuse_or_guide"}
        async for ev in _stream_refuse_or_guide(classification, provider, "guide"):
            yield ev
    elif route == "pending_ms5":
        yield {"type": "agent_start", "agent": "ms5_placeholder", "kind": "pending_ms5"}
        # 짧은 텍스트라 청크 분할 의미 X
        yield {"type": "text_delta", "text": _PENDING_MS5_TEXT, "agent": "ms5_placeholder"}
        yield {"type": "agent_done", "agent": "ms5_placeholder"}
    else:
        yield {"type": "agent_start", "agent": "guide", "kind": "refuse_or_guide"}
        async for ev in _stream_refuse_or_guide(classification, provider, "guide"):
            yield ev

    yield {"type": "done"}
