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
from pathlib import Path
from typing import Any

import yaml

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
    load_strategist_spec,
    run_strategist,
    run_strategist_stream,
)

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYST_SUBTASKS_PATH = REPO_ROOT / "config" / "analyst_subtasks.yaml"
SCENARIO_ROUTING_PATH = REPO_ROOT / "config" / "scenario_analyst_routing.yaml"

_ANALYST_SUBTASKS_CACHE: dict | None = None
_SCENARIO_ROUTING_CACHE: dict | None = None


def _load_analyst_subtasks() -> dict:
    """analyst_subtasks.yaml lazy 로드. 캐시."""
    global _ANALYST_SUBTASKS_CACHE
    if _ANALYST_SUBTASKS_CACHE is None:
        if not ANALYST_SUBTASKS_PATH.exists():
            log.warning("analyst_subtasks_missing", path=str(ANALYST_SUBTASKS_PATH))
            _ANALYST_SUBTASKS_CACHE = {"common_directives": "", "analysts": {}}
        else:
            try:
                _ANALYST_SUBTASKS_CACHE = (
                    yaml.safe_load(ANALYST_SUBTASKS_PATH.read_text(encoding="utf-8")) or {}
                )
            except Exception as e:  # noqa: BLE001
                log.warning("analyst_subtasks_load_failed", error=str(e))
                _ANALYST_SUBTASKS_CACHE = {"common_directives": "", "analysts": {}}
    return _ANALYST_SUBTASKS_CACHE


def _load_scenario_routing() -> dict:
    """scenario_analyst_routing.yaml lazy 로드. 캐시."""
    global _SCENARIO_ROUTING_CACHE
    if _SCENARIO_ROUTING_CACHE is None:
        if not SCENARIO_ROUTING_PATH.exists():
            log.warning("scenario_routing_missing", path=str(SCENARIO_ROUTING_PATH))
            _SCENARIO_ROUTING_CACHE = {"scenarios": {}}
        else:
            try:
                _SCENARIO_ROUTING_CACHE = (
                    yaml.safe_load(SCENARIO_ROUTING_PATH.read_text(encoding="utf-8")) or {}
                )
            except Exception as e:  # noqa: BLE001
                log.warning("scenario_routing_load_failed", error=str(e))
                _SCENARIO_ROUTING_CACHE = {"scenarios": {}}
    return _SCENARIO_ROUTING_CACHE


def reload_subtasks_and_routing() -> None:
    """테스트/hot reload — 두 캐시 모두 클리어."""
    global _ANALYST_SUBTASKS_CACHE, _SCENARIO_ROUTING_CACHE
    _ANALYST_SUBTASKS_CACHE = None
    _SCENARIO_ROUTING_CACHE = None


def _resolve_analyst_ids_for_scenario(
    scenario_id: int, track_ids: list[str]
) -> list[str]:
    """시나리오 ID 별 축약 매핑 우선, 없으면 track_ids 의 reads_analysts 합집합 fallback.

    해석 후 track_required(config) 의 track 별 필수 분석가를 보강한다 — 시나리오 축약은
    Track A 기준이라, swing(Track B) 라우팅 시 trader(T-Score) 같은 권위 발행자가
    누락되던 결함을 방지(2026-06-01 시연 발견).
    """
    routing = _load_scenario_routing()
    sc_map = (routing.get("scenarios") or {}).get(scenario_id)
    resolved: list[str]
    if sc_map and (sc_map.get("analysts") or []):
        resolved = list(sc_map["analysts"])
    else:
        # fallback = track reads_analysts 합집합 (PROD-UX-1 기존 패턴)
        aid_set: set[str] = set()
        for tid in track_ids:
            try:
                spec = load_strategist_spec(tid)
                aid_set.update(spec.reads_analysts)
            except StrategistNotFoundError:
                continue
        resolved = sorted(aid_set)

    # track 별 필수 분석가 보강 (순서 보존 + 중복 skip)
    required = routing.get("track_required") or {}
    for tid in track_ids:
        for aid in required.get(tid) or []:
            if aid not in resolved:
                resolved.append(aid)
    return resolved


def _build_subtask_prompt(
    analyst_id: str,
    *,
    ticker: str | None,
    ticker_display: str | None,
    original_input: str,
    scenario_id: int,
) -> str:
    """분석가 별 sub-task prompt 생성. template 에 placeholder 치환."""
    data = _load_analyst_subtasks()
    template = (data.get("analysts") or {}).get(analyst_id)
    common = data.get("common_directives", "")
    scenario_routing = _load_scenario_routing()
    sc_meta = (scenario_routing.get("scenarios") or {}).get(scenario_id, {})
    scenario_name = sc_meta.get("name", f"scenario_{scenario_id}")

    if not template:
        # fallback — 본 분석가 sub-task 없으면 원본 발화 그대로 (legacy 호환)
        return original_input

    return template.format(
        ticker=ticker or "global",
        ticker_display=ticker_display or "",
        original_input=original_input,
        scenario_name=scenario_name,
    ) + ("\n" + common if common else "")


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
    prefetched_analyst_outputs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """run_strategist wrap — 실패 시 error 필드 채워 반환 (예외 raise X).

    Args:
        prefetched_analyst_outputs: 옵션 A — 라우터가 미리 동시 호출해 둔 분석가
            raw 응답들. None 이면 전략가가 DB read 모드.
    """
    try:
        resp = await run_strategist(
            strategist_id,
            messages,
            target=target,
            provider=provider,
            prefetched_analyst_outputs=prefetched_analyst_outputs,
            mock_fallback_allowed=False,
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
            mock_fallback_allowed=False,
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


async def _prefetch_analysts_for_tracks(
    track_ids: list[str],
    *,
    classification: IntentClassification,
    messages: list[dict],
    provider: str | None,
) -> list[dict[str, Any]]:
    """옵션 A + Sub-task decomposition + 시나리오별 축약.

    PRODUCTION-UX 사이클 3 (사용자 회피 진단 정합):
      - 사용자 발화 forward 가 아니라 분석가별 **sub-task prompt** 로 분해
      - 시나리오 ID 별 **축약 매핑** (config/scenario_analyst_routing.yaml)
        — 시나리오 2 (신규 진입) 시 6명 → 5명 등 본질 영역만

    prism-insight 의 Orchestrator pass-through + wevelStock 의 asyncio.gather 결합.
    DB write 우회 — 본 production-chat 흐름 내 일관성만 보장.

    Args:
        track_ids: ["track_a"] 또는 ["track_a", "track_b"] (both)
        classification: IntentClassification 풀세트 (scenario_id, ticker 등)

    Returns:
        list of {"id": analyst_id, "text": str, "metadata": dict, "error": str | None,
                 "subtask_prompt": str (디버깅용)}.
        분석가 호출 실패 시 error 필드만 채워서 반환 (raise X).
    """
    ordered = _resolve_analyst_ids_for_scenario(
        classification.scenario_id, track_ids
    )
    if not ordered:
        return []

    # 각 분석가에 별도 sub-task prompt 던짐 — 사용자 발화 forward X.
    # messages 의 마지막 user 메시지를 sub-task prompt 로 치환 (멀티턴 prior 는 보존).
    tasks = []
    subtask_prompts: list[str] = []
    for aid in ordered:
        prompt = _build_subtask_prompt(
            aid,
            ticker=classification.ticker,
            ticker_display=classification.ticker_display,
            original_input=classification.raw_input,
            scenario_id=classification.scenario_id,
        )
        subtask_prompts.append(prompt)
        # messages 의 마지막 user 메시지 prompt 로 치환
        if messages and messages[-1].get("role") == "user":
            subtask_messages = messages[:-1] + [{"role": "user", "content": prompt}]
        else:
            subtask_messages = list(messages) + [{"role": "user", "content": prompt}]
        tasks.append(
            _call_analyst_safe(
                aid,
                subtask_messages,
                target_ticker=classification.ticker,
                provider=provider,
            )
        )

    results = await asyncio.gather(*tasks, return_exceptions=False)
    return [
        {
            "id": r.get("agent_id", aid),
            "text": r.get("text", ""),
            "metadata": r.get("metadata", {}),
            "error": r.get("error"),
            "subtask_prompt": subtask_prompts[i],
        }
        for i, (aid, r) in enumerate(zip(ordered, results))
    ]


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
            mock_fallback_allowed=False,
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

    if route in ("track_a", "track_b", "both"):
        target = ticker or "global"
        track_ids = ["track_a", "track_b"] if route == "both" else [route]
        # 옵션 A + sub-task decomposition + 시나리오별 축약
        prefetched = await _prefetch_analysts_for_tracks(
            track_ids,
            classification=classification,
            messages=messages,
            provider=provider,
        )
        # prefetch 응답을 agent_responses 에 먼저 동봉 (UI 근거 토글용 raw 자료).
        for entry in prefetched:
            responses.append(
                {
                    "kind": "analyst_prefetch",
                    "agent_id": entry["id"],
                    "target": ticker,
                    "text": entry.get("text", ""),
                    "metadata": entry.get("metadata", {}),
                    "error": entry.get("error"),
                }
            )
        if route == "both":
            strat_results = await asyncio.gather(
                _call_strategist_safe(
                    "track_a",
                    messages,
                    target=target,
                    provider=provider,
                    prefetched_analyst_outputs=prefetched,
                ),
                _call_strategist_safe(
                    "track_b",
                    messages,
                    target=target,
                    provider=provider,
                    prefetched_analyst_outputs=prefetched,
                ),
                return_exceptions=False,
            )
            responses.extend(strat_results)
        else:
            responses.append(
                await _call_strategist_safe(
                    route,
                    messages,
                    target=target,
                    provider=provider,
                    prefetched_analyst_outputs=prefetched,
                )
            )
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
    prefetched_analyst_outputs: list[dict[str, Any]] | None = None,
):
    """run_strategist_stream wrap — agent 라벨 prefix 첨가.

    옵션 A 적용: prefetched_analyst_outputs 가 있으면 전략가가 DB read 우회.
    """
    try:
        async for event in run_strategist_stream(
            strategist_id,
            messages,
            target=target,
            provider=provider,
            prefetched_analyst_outputs=prefetched_analyst_outputs,
            mock_fallback_allowed=False,
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
            analyst_id, messages, target_ticker=target_ticker, provider=provider,
            mock_fallback_allowed=False,
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
            mock_fallback_allowed=False,
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

    if route in ("track_a", "track_b", "both"):
        target = ticker or "global"
        track_ids = ["track_a", "track_b"] if route == "both" else [route]
        # 옵션 A + sub-task + 축약 — 사용자 가시화 (각 분석가 진행 표시)
        yield {"type": "prefetch_start", "track_ids": track_ids}
        prefetched = await _prefetch_analysts_for_tracks(
            track_ids,
            classification=classification,
            messages=messages,
            provider=provider,
        )
        for entry in prefetched:
            yield {
                "type": "analyst_prefetch",
                "agent": entry["id"],
                "kind": "analyst_prefetch",
                "text": entry.get("text", ""),
                "metadata": entry.get("metadata", {}),
                "error": entry.get("error"),
            }
        yield {
            "type": "prefetch_done",
            "analysts": [e["id"] for e in prefetched],
            "missing": [e["id"] for e in prefetched if e.get("error") or not (e.get("text") or "").strip()],
        }
        for tid in track_ids:
            yield {"type": "agent_start", "agent": tid, "kind": "strategist"}
            async for ev in _stream_strategist_safe(
                tid,
                messages,
                target=target,
                provider=provider,
                agent_label=tid,
                prefetched_analyst_outputs=prefetched,
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
