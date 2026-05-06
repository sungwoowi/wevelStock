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

from core.knowledge.compose import build_pipeline_prompt
from core.llm.client import call_llm
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
) -> AnalystResponse:
    """단일 분석가 호출. 멀티턴 messages 배열 그대로 수용.

    Args:
        analyst_id: agents/analysts/<id>/ 의 디렉토리명
        messages: [{"role": "user"|"assistant", "content": str}, ...]
                  단일 턴이면 길이 1, 멀티턴이면 누적
        model/max_tokens/temperature: manifest 값을 override (선택)
        include_memory: core/memory 시계열 메모리 주입 ON/OFF

    Returns:
        AnalystResponse(text, metadata)
    """
    if not messages:
        raise ValueError("messages 가 비어있습니다 (최소 1턴 user 입력 필요)")

    spec = load_analyst_spec(analyst_id)
    rag_dept = spec.reads[0] if spec.reads else None
    query_for_rag = _last_user_text(messages)

    bundle = await build_pipeline_prompt(
        context_id=spec.id,
        persona_path=spec.persona_path,
        include_shared_canon=True,
        include_memory=include_memory,
        token_budget_memory=4000,
        query_for_rag=query_for_rag,
        rag_dept=rag_dept,
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
    )
    latency_s = time.monotonic() - started

    cache_read, cache_creation = _extract_cache_tokens(resp.get("raw") or {})

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
        "is_mock": "-mock" in str(resp.get("model", "")),
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
