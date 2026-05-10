"""분석가 단일 호출 함수.

`run_analyst(analyst_id, messages)` = 멀티턴 messages 배열을 받아 분석가의 응답을
반환한다. 단일 턴이면 messages 길이 1, 멀티턴이면 [user, assistant, user, ...] 누적.

흐름:
  1. agents/analysts/<id>/manifest.yaml 로드 (reads, llm.*, response_rules)
  2. agents/analysts/<id>/persona.md 경로 확정
  3. compose.build_pipeline_prompt(rag_dept=reads[0], query_for_rag=last_user_msg, ...)
     → SystemPromptBundle (canon + persona + memory + RAG + response_rules 블록)
  4. core.llm.client.call_llm(system=blocks, messages=messages, ...)
  5. metadata 산출 (system char 수, RAG 회수 chunk 수, cache token, cost, latency)

Anthropic prompt caching 은 build_pipeline_prompt 가 cache_control 을 system 블록에
이미 박아준다. messages 는 매 턴 변하므로 캐시 X.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from collectors.snapshot import build_market_snapshot, render_snapshot_md
from core.knowledge.compose import build_pipeline_prompt
from core.llm.client import call_llm, call_llm_stream
from core.logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSTS_DIR = REPO_ROOT / "agents" / "analysts"


@dataclass(frozen=True)
class AnalystSpec:
    """agents/analysts/<id>/manifest.yaml + persona.md 경로 묶음."""

    id: str
    display_name: str
    learning_dept: str
    reads: list[str]
    canon_categories: list[str]
    persona_path: Path
    model: str | None
    max_tokens: int
    temperature: float
    response_rules: str | None


@dataclass
class AnalystResponse:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AnalystNotFoundError(FileNotFoundError):
    pass


def load_analyst_spec(analyst_id: str) -> AnalystSpec:
    """분석가 manifest 로드. 분석가가 없으면 AnalystNotFoundError."""
    analyst_dir = ANALYSTS_DIR / analyst_id
    manifest_path = analyst_dir / "manifest.yaml"
    persona_path = analyst_dir / "persona.md"
    if not manifest_path.exists():
        raise AnalystNotFoundError(
            f"manifest not found: {manifest_path} (분석가 '{analyst_id}' 가 등록되지 않았습니다)"
        )
    if not persona_path.exists():
        raise AnalystNotFoundError(f"persona not found: {persona_path}")

    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    llm_cfg = raw.get("llm") or {}

    return AnalystSpec(
        id=raw.get("id", analyst_id),
        display_name=raw.get("display_name", analyst_id),
        learning_dept=raw.get("learning_dept", ""),
        reads=list(raw.get("reads") or []),
        canon_categories=list(raw.get("canon_categories") or []),
        persona_path=persona_path,
        model=llm_cfg.get("model"),
        max_tokens=int(llm_cfg.get("max_tokens", 4000)),
        temperature=float(llm_cfg.get("temperature", 0.4)),
        response_rules=raw.get("response_rules"),
    )


def _last_user_text(messages: list[dict]) -> str | None:
    """마지막 user 메시지의 텍스트 (RAG query 로 사용)."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                # Anthropic 의 content blocks 형식 — 텍스트 부분만 추출
                parts = [b.get("text", "") for b in content if isinstance(b, dict)]
                joined = "\n".join(p for p in parts if p)
                return joined or None
    return None


def _system_char_count(blocks: list[dict]) -> int:
    return sum(len(b.get("text", "")) for b in blocks if isinstance(b, dict))


def _rag_chunks_in_blocks(blocks: list[dict]) -> int:
    """## Retrieved References 블록의 ### 헤더 개수 = 회수된 chunk 수."""
    for b in blocks:
        text = b.get("text", "")
        if text.startswith("## Retrieved References"):
            return text.count("\n### [")
    return 0


def _extract_cache_tokens(raw: dict) -> tuple[int, int]:
    """raw["usage"] 에서 cache_read / cache_creation tokens 추출."""
    usage = raw.get("usage") or {}
    return (
        int(usage.get("cache_read_input_tokens") or 0),
        int(usage.get("cache_creation_input_tokens") or 0),
    )


async def run_analyst(
    analyst_id: str,
    messages: list[dict],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    include_memory: bool = True,
    provider: str | None = None,
) -> AnalystResponse:
    """단일 분석가 호출. 멀티턴 messages 배열 그대로 수용.

    Args:
        analyst_id: agents/analysts/<id>/ 의 디렉토리명
        messages: [{"role": "user"|"assistant", "content": str}, ...]
                  단일 턴이면 길이 1, 멀티턴이면 누적
        model/max_tokens/temperature: manifest 값을 override (선택)
        include_memory: core/memory 시계열 메모리 주입 ON/OFF
        provider: "gemini" | "claude_code" | "anthropic" | "mock" 명시 시 그
                  backend 강제 호출 (자동 폴백 X — 에러 propagate). None 이면
                  config.llm.provider + 자동 폴백 체인. 톤 비교용.

    Returns:
        AnalystResponse(text, metadata)
    """
    if not messages:
        raise ValueError("messages 가 비어있습니다 (최소 1턴 user 입력 필요)")

    spec = load_analyst_spec(analyst_id)
    rag_dept = spec.reads[0] if spec.reads else None
    query_for_rag = _last_user_text(messages)

    snap_started = time.monotonic()
    snapshot, snapshot_cache_hit = await build_market_snapshot()
    snapshot_fetch_seconds = round(time.monotonic() - snap_started, 2)
    snapshot_age_seconds = max(0, int(time.time() - snapshot.fetched_at))
    market_snapshot_md = render_snapshot_md(snapshot)

    bundle = await build_pipeline_prompt(
        context_id=spec.id,
        persona_path=spec.persona_path,
        include_shared_canon=True,
        include_memory=include_memory,
        token_budget_memory=4000,
        query_for_rag=query_for_rag,
        rag_dept=rag_dept,
        canon_categories=spec.canon_categories or None,
        market_snapshot_md=market_snapshot_md,
        response_rules=spec.response_rules,
    )

    sys_chars = _system_char_count(bundle.blocks)
    rag_chunks = _rag_chunks_in_blocks(bundle.blocks)

    started = time.monotonic()
    resp = await call_llm(
        system=bundle.blocks,
        messages=messages,
        model=model or spec.model,
        max_tokens=max_tokens or spec.max_tokens,
        temperature=temperature if temperature is not None else spec.temperature,
        provider=provider,
    )
    latency_s = time.monotonic() - started

    cache_read, cache_creation = _extract_cache_tokens(resp.get("raw") or {})

    # raw error / mock fallback 가시화 — 503/rate limit/키 누락 같은 silent fallback 진단용
    raw = resp.get("raw") or {}
    upstream_error = raw.get("error")
    is_mock = "-mock" in str(resp.get("model", "")) or bool(raw.get("mock"))

    # provider_used: 실제 응답을 만든 backend (auto fallback 시 fallback_used 우선)
    provider_used = (
        raw.get("fallback_used")
        or raw.get("provider")
        or (provider if provider else "auto")
    )

    metadata = {
        "analyst_id": spec.id,
        "display_name": spec.display_name,
        "learning_dept": spec.learning_dept,
        "rag_dept": rag_dept,
        "rag_chunks_returned": rag_chunks,
        "system_prompt_chars": sys_chars,
        "system_blocks": len(bundle.blocks),
        "cache_breakpoint_count": bundle.cache_breakpoint_count,
        "tokens_in": resp.get("tokens_in", 0),
        "tokens_out": resp.get("tokens_out", 0),
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_creation,
        "model": resp.get("model", ""),
        "cost_usd": resp.get("cost_usd", 0.0),
        "latency_s": round(latency_s, 2),
        "is_mock": is_mock,
        "upstream_error": upstream_error,  # 실 LLM 호출 실패 시 원인 (mock fallback 진단)
        "provider_requested": provider,  # 사용자 명시 선택 (None = auto)
        "provider_used": provider_used,  # 실제 응답 backend
        "snapshot_age_seconds": snapshot_age_seconds,
        "snapshot_fetch_seconds": snapshot_fetch_seconds,
        "snapshot_cache_hit": snapshot_cache_hit,
        "snapshot_failures": snapshot.failures,
        "snapshot_source_map": dict(snapshot.source_map),
        "snapshot_db_run_ids": dict(snapshot.db_run_ids),
    }

    log.info(
        "analyst_call_done",
        analyst=spec.id,
        chars=sys_chars,
        rag_chunks=rag_chunks,
        tokens_in=metadata["tokens_in"],
        tokens_out=metadata["tokens_out"],
        cache_read=cache_read,
        cost_usd=metadata["cost_usd"],
        latency_s=metadata["latency_s"],
    )

    return AnalystResponse(text=resp.get("content", ""), metadata=metadata)


async def run_analyst_stream(
    analyst_id: str,
    messages: list[dict],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    include_memory: bool = True,
    provider: str | None = None,
):
    """run_analyst 의 streaming 변종. text_delta 이벤트 흘림 + 종료 시 metadata.

    Yields:
        {"type": "text_delta", "text": str}      # 토큰 청크
        {"type": "metadata", **metadata_dict}     # 종료 직전 1회 (run_analyst 의
                                                    metadata 키 + cumulative content)
        {"type": "error", ...}                    # provider 실패
        {"type": "done"}                          # 정상 종료

    System prompt 합성 (manifest+persona+canon+RAG+memory+market_snapshot) 은
    run_analyst 와 동일. call_llm 대신 call_llm_stream 사용.
    """
    if not messages:
        raise ValueError("messages 가 비어있습니다 (최소 1턴 user 입력 필요)")

    spec = load_analyst_spec(analyst_id)
    rag_dept = spec.reads[0] if spec.reads else None
    query_for_rag = _last_user_text(messages)

    snap_started = time.monotonic()
    snapshot, snapshot_cache_hit = await build_market_snapshot()
    snapshot_fetch_seconds = round(time.monotonic() - snap_started, 2)
    snapshot_age_seconds = max(0, int(time.time() - snapshot.fetched_at))
    market_snapshot_md = render_snapshot_md(snapshot)

    bundle = await build_pipeline_prompt(
        context_id=spec.id,
        persona_path=spec.persona_path,
        include_shared_canon=True,
        include_memory=include_memory,
        token_budget_memory=4000,
        query_for_rag=query_for_rag,
        rag_dept=rag_dept,
        canon_categories=spec.canon_categories or None,
        market_snapshot_md=market_snapshot_md,
        response_rules=spec.response_rules,
    )

    sys_chars = _system_char_count(bundle.blocks)
    rag_chunks = _rag_chunks_in_blocks(bundle.blocks)

    started = time.monotonic()
    first_token_at: float | None = None
    last_metadata: dict | None = None
    last_error: dict | None = None

    async for event in call_llm_stream(
        system=bundle.blocks,
        messages=messages,
        model=model or spec.model,
        max_tokens=max_tokens or spec.max_tokens,
        temperature=temperature if temperature is not None else spec.temperature,
        provider=provider,
    ):
        etype = event.get("type")
        if etype == "text_delta":
            if first_token_at is None:
                first_token_at = time.monotonic()
            yield event
        elif etype == "metadata":
            last_metadata = event
            # metadata 는 우리가 보강한 형식으로 끝에 다시 emit
            continue
        elif etype == "error":
            last_error = event
            yield event
        elif etype == "done":
            # done 은 마지막에 우리가 emit
            break
        else:
            # 알 수 없는 이벤트 — 그대로 흘림
            yield event

    latency_s = time.monotonic() - started
    first_token_ms = (
        int((first_token_at - started) * 1000) if first_token_at else None
    )

    # last_metadata 가 없으면 (예: error 만 발생) 빈 dict 로 보호
    md_src = last_metadata or {}
    raw = md_src.get("raw") or {}
    cache_read, cache_creation = _extract_cache_tokens(raw)
    upstream_error = raw.get("error") or (last_error.get("message") if last_error else None)
    is_mock = "-mock" in str(md_src.get("model", "")) or bool(raw.get("mock"))
    provider_used = (
        raw.get("fallback_used")
        or raw.get("provider")
        or (provider if provider else "auto")
    )

    metadata = {
        "analyst_id": spec.id,
        "display_name": spec.display_name,
        "learning_dept": spec.learning_dept,
        "rag_dept": rag_dept,
        "rag_chunks_returned": rag_chunks,
        "system_prompt_chars": sys_chars,
        "system_blocks": len(bundle.blocks),
        "cache_breakpoint_count": bundle.cache_breakpoint_count,
        "tokens_in": md_src.get("tokens_in", 0),
        "tokens_out": md_src.get("tokens_out", 0),
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_creation,
        "model": md_src.get("model", ""),
        "cost_usd": md_src.get("cost_usd", 0.0),
        "latency_s": round(latency_s, 2),
        "first_token_ms": first_token_ms,
        "is_mock": is_mock,
        "upstream_error": upstream_error,
        "provider_requested": provider,
        "provider_used": provider_used,
        "snapshot_age_seconds": snapshot_age_seconds,
        "snapshot_fetch_seconds": snapshot_fetch_seconds,
        "snapshot_cache_hit": snapshot_cache_hit,
        "snapshot_failures": snapshot.failures,
        "snapshot_source_map": dict(snapshot.source_map),
        "snapshot_db_run_ids": dict(snapshot.db_run_ids),
        "content": md_src.get("content", ""),  # 누적 텍스트 (검증용)
    }

    log.info(
        "analyst_stream_done",
        analyst=spec.id,
        chars=sys_chars,
        rag_chunks=rag_chunks,
        tokens_in=metadata["tokens_in"],
        tokens_out=metadata["tokens_out"],
        cache_read=cache_read,
        cost_usd=metadata["cost_usd"],
        latency_s=metadata["latency_s"],
        first_token_ms=first_token_ms,
    )

    yield {"type": "metadata", **metadata}
    yield {"type": "done"}
