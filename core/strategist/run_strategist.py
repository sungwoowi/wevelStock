"""전략가 (Layer 3) 단일 호출 함수.

`run_strategist(strategist_id, messages, target=...)` = 전략가의 권고/응답 생성.
`core/inference/run_analyst.py` 와 1:1 대응 패턴 + 분석가 점수 주입 추가.

흐름:
  1. agents/strategists/<id>/manifest.yaml 로드 (reads_analysts, reads, canon_categories, llm.*, response_rules)
  2. agents/strategists/<id>/persona.md 경로 확정
  3. 분석가 점수 모으기: reads_analysts 의 team_outputs DB 최신 row read (target=current target)
  4. market snapshot 빌드 (분석가와 동일)
  5. compose.build_pipeline_prompt(...) → SystemPromptBundle
  6. 분석가 점수 블록을 bundle.blocks 에 insert (RAG 직전, not cached)
  7. core.llm.client.call_llm(system=blocks, messages=messages, ...)
  8. metadata 산출 (분석가 metadata + 분석가 발행 카운트·누락 카운트)

분석가 점수 누락 처리: reads_analysts 의 분석가가 발행 안 했으면 "미발행" 으로
명시 + LLM 권고 시 cited_scores 해당 필드 = null 으로 박도록 양식 강제 (persona.md
Anti-patterns).

team_outputs DB write 는 본 함수가 직접 하지 X. 호출처 (server/api/...) 가 응답을
파싱해 StandardOutput 으로 어댑팅 후 persist_output() 호출. 본 함수는 LLM 호출까지만.
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
from core.outputs import load_latest

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
STRATEGISTS_DIR = REPO_ROOT / "agents" / "strategists"


@dataclass(frozen=True)
class StrategistSpec:
    """agents/strategists/<id>/manifest.yaml + persona.md 경로 묶음."""

    id: str
    display_name: str
    track: str
    reads_analysts: list[str]
    reads_depts: list[str]
    canon_categories: list[str]
    persona_path: Path
    model: str | None
    max_tokens: int
    temperature: float
    response_rules: str | None


@dataclass
class StrategistResponse:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class StrategistNotFoundError(FileNotFoundError):
    pass


def load_strategist_spec(strategist_id: str) -> StrategistSpec:
    """전략가 manifest 로드. 없으면 StrategistNotFoundError."""
    strategist_dir = STRATEGISTS_DIR / strategist_id
    manifest_path = strategist_dir / "manifest.yaml"
    persona_path = strategist_dir / "persona.md"
    if not manifest_path.exists():
        raise StrategistNotFoundError(
            f"manifest not found: {manifest_path} (전략가 '{strategist_id}' 가 등록되지 않았습니다)"
        )
    if not persona_path.exists():
        raise StrategistNotFoundError(f"persona not found: {persona_path}")

    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    llm_cfg = raw.get("llm") or {}

    return StrategistSpec(
        id=raw.get("id", strategist_id),
        display_name=raw.get("display_name", strategist_id),
        track=str(raw.get("track", "")),
        reads_analysts=list(raw.get("reads_analysts") or []),
        reads_depts=list(raw.get("reads") or []),
        canon_categories=list(raw.get("canon_categories") or []),
        persona_path=persona_path,
        model=llm_cfg.get("model"),
        max_tokens=int(llm_cfg.get("max_tokens", 6000)),
        temperature=float(llm_cfg.get("temperature", 0.4)),
        response_rules=raw.get("response_rules"),
    )


def gather_analyst_scores(analyst_ids: list[str], target: str = "global") -> dict[str, dict[str, Any]]:
    """reads_analysts 의 각 분석가가 team_outputs 에 발행한 최신 row 모음.

    Returns:
        {analyst_id: {
            "found": bool,
            "timestamp": str | None,
            "verdict": str | None,
            "confidence": int | None,
            "reasons": list[str],
            "data": dict,
        }}

    DB 접근 실패 시에도 크래시 금지 — found=False 로 처리해 LLM 이 환각 대신
    "미발행" 으로 처리하도록 한다.
    """
    result: dict[str, dict[str, Any]] = {}
    for aid in analyst_ids:
        try:
            latest = load_latest(team_id=aid, target=target)
        except Exception as e:  # noqa: BLE001
            log.warning("analyst_load_failed", analyst=aid, error=str(e))
            result[aid] = {"found": False, "error": str(e)}
            continue

        if latest is None:
            result[aid] = {"found": False}
        else:
            result[aid] = {
                "found": True,
                "timestamp": latest.timestamp,
                "verdict": latest.verdict,
                "confidence": latest.confidence,
                "reasons": list(latest.reasons),
                "data": dict(latest.data),
            }
    return result


def render_analyst_scores_block(scores: dict[str, dict[str, Any]]) -> str:
    """분석가 점수를 system prompt 용 markdown 렌더.

    LLM 이 이 블록을 보고 권고 양식 cited_scores 에 인용한다. 미발행 분석가는
    명시적으로 표시 — 환각 대신 null 처리하도록.
    """
    lines = [
        "## Analyst Scores (Layer 2 — team_outputs DB read)",
        "",
        "아래는 reads_analysts 6 분석가의 최신 발행물입니다.",
        "권고 양식 cited_scores 에 인용 시 본 블록의 점수만 사용 (다른 값 추정 금지).",
        "미발행 분석가는 cited_scores 해당 필드 = null + reasons 에 '분석가 미발행' 명시.",
        "",
    ]
    for aid, score in scores.items():
        lines.append(f"### {aid}")
        if not score.get("found"):
            err = score.get("error")
            if err:
                lines.append(f"**조회 실패** — {err}. 미발행으로 처리.")
            else:
                lines.append("**미발행** — team_outputs 에 row 없음. cited_scores 해당 필드 = null.")
            lines.append("")
            continue

        lines.append(f"- timestamp: {score.get('timestamp')}")
        lines.append(f"- verdict: {score.get('verdict')}")
        lines.append(f"- confidence: {score.get('confidence')}")
        reasons = score.get("reasons") or []
        if reasons:
            lines.append("- reasons:")
            for r in reasons[:3]:
                lines.append(f"  - {r}")
        data = score.get("data") or {}
        if data:
            lines.append("- data:")
            for k, v in data.items():
                lines.append(f"  - {k}: {v}")
        lines.append("")
    return "\n".join(lines)


def _last_user_text(messages: list[dict]) -> str | None:
    """마지막 user 메시지의 텍스트 (RAG query 로 사용)."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [b.get("text", "") for b in content if isinstance(b, dict)]
                joined = "\n".join(p for p in parts if p)
                return joined or None
    return None


def _system_char_count(blocks: list[dict]) -> int:
    return sum(len(b.get("text", "")) for b in blocks if isinstance(b, dict))


def _rag_chunks_in_blocks(blocks: list[dict]) -> int:
    for b in blocks:
        text = b.get("text", "")
        if text.startswith("## Retrieved References"):
            return text.count("\n### [")
    return 0


def _insert_analyst_scores_block(blocks: list[dict], scores_md: str) -> list[dict]:
    """bundle.blocks 의 RAG 직전 (또는 끝의 response_rules 직전) 에 분석가 점수 블록 insert.

    not cached — 분석가 점수는 시점 의존이라 캐시 X.
    """
    if not scores_md.strip():
        return blocks

    score_block = {
        "type": "text",
        "text": scores_md,
    }

    # RAG 블록 위치 찾기 (## Retrieved References)
    for idx, b in enumerate(blocks):
        text = b.get("text", "")
        if text.startswith("## Retrieved References"):
            return blocks[:idx] + [score_block] + blocks[idx:]

    # RAG 없으면 response_rules (마지막 블록, ## Response rules) 직전
    if blocks:
        last = blocks[-1]
        if last.get("text", "").lstrip().startswith("## Response rules") or last.get(
            "text", ""
        ).lstrip().startswith("## Response rules"):
            return blocks[:-1] + [score_block, last]

    # fallback: 끝에 append
    return [*blocks, score_block]


def _extract_cache_tokens(raw: dict) -> tuple[int, int]:
    usage = raw.get("usage") or {}
    return (
        int(usage.get("cache_read_input_tokens") or 0),
        int(usage.get("cache_creation_input_tokens") or 0),
    )


async def run_strategist(
    strategist_id: str,
    messages: list[dict],
    *,
    target: str = "global",
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    include_memory: bool = True,
    provider: str | None = None,
) -> StrategistResponse:
    """단일 전략가 호출. 멀티턴 messages 배열 그대로 수용.

    Args:
        strategist_id: agents/strategists/<id>/ 의 디렉토리명 (예: "track_a")
        messages: [{"role": "user"|"assistant", "content": str}, ...]
        target: team_outputs 의 target (종목 ticker / "global"). 분석가 점수 조회
                기준. Track A/B 권고는 보통 종목별이므로 ticker 가 자연.
        model/max_tokens/temperature: manifest override
        include_memory: core/memory 시계열 메모리 주입 ON/OFF
        provider: backend 강제 (None = config + auto fallback)

    Returns:
        StrategistResponse(text, metadata)
    """
    if not messages:
        raise ValueError("messages 가 비어있습니다 (최소 1턴 user 입력 필요)")

    spec = load_strategist_spec(strategist_id)
    # RAG dept = reads 의 첫 dept (멀티 dept RAG 는 compose 측 확장 백로그)
    rag_dept = spec.reads_depts[0] if spec.reads_depts else None
    query_for_rag = _last_user_text(messages)

    # 분석가 점수 모으기 (target 별)
    scores = gather_analyst_scores(spec.reads_analysts, target=target)
    scores_md = render_analyst_scores_block(scores)

    # market snapshot (분석가와 동일)
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

    # 분석가 점수 블록 insert (RAG 직전)
    blocks = _insert_analyst_scores_block(bundle.blocks, scores_md)

    sys_chars = _system_char_count(blocks)
    rag_chunks = _rag_chunks_in_blocks(blocks)
    analyst_published = sum(1 for s in scores.values() if s.get("found"))
    analyst_missing = sum(1 for s in scores.values() if not s.get("found"))

    started = time.monotonic()
    resp = await call_llm(
        system=blocks,
        messages=messages,
        model=model or spec.model,
        max_tokens=max_tokens or spec.max_tokens,
        temperature=temperature if temperature is not None else spec.temperature,
        provider=provider,
    )
    latency_s = time.monotonic() - started

    cache_read, cache_creation = _extract_cache_tokens(resp.get("raw") or {})

    raw = resp.get("raw") or {}
    upstream_error = raw.get("error")
    is_mock = "-mock" in str(resp.get("model", "")) or bool(raw.get("mock"))
    provider_used = (
        raw.get("fallback_used")
        or raw.get("provider")
        or (provider if provider else "auto")
    )

    metadata = {
        "strategist_id": spec.id,
        "display_name": spec.display_name,
        "track": spec.track,
        "target": target,
        "reads_analysts": list(spec.reads_analysts),
        "analyst_published_count": analyst_published,
        "analyst_missing_count": analyst_missing,
        "analyst_missing_ids": [aid for aid, s in scores.items() if not s.get("found")],
        "rag_dept": rag_dept,
        "rag_chunks_returned": rag_chunks,
        "system_prompt_chars": sys_chars,
        "system_blocks": len(blocks),
        "cache_breakpoint_count": bundle.cache_breakpoint_count,
        "tokens_in": resp.get("tokens_in", 0),
        "tokens_out": resp.get("tokens_out", 0),
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_creation,
        "model": resp.get("model", ""),
        "cost_usd": resp.get("cost_usd", 0.0),
        "latency_s": round(latency_s, 2),
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
    }

    log.info(
        "strategist_call_done",
        strategist=spec.id,
        track=spec.track,
        target=target,
        analyst_published=analyst_published,
        analyst_missing=analyst_missing,
        chars=sys_chars,
        rag_chunks=rag_chunks,
        tokens_in=metadata["tokens_in"],
        tokens_out=metadata["tokens_out"],
        cost_usd=metadata["cost_usd"],
        latency_s=metadata["latency_s"],
    )

    return StrategistResponse(text=resp.get("content", ""), metadata=metadata)


async def run_strategist_stream(
    strategist_id: str,
    messages: list[dict],
    *,
    target: str = "global",
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    include_memory: bool = True,
    provider: str | None = None,
):
    """run_strategist 의 streaming 변종. text_delta + 종료 시 metadata.

    Yields:
        {"type": "text_delta", "text": str}
        {"type": "metadata", **metadata}
        {"type": "error", ...}
        {"type": "done"}
    """
    if not messages:
        raise ValueError("messages 가 비어있습니다 (최소 1턴 user 입력 필요)")

    spec = load_strategist_spec(strategist_id)
    rag_dept = spec.reads_depts[0] if spec.reads_depts else None
    query_for_rag = _last_user_text(messages)

    scores = gather_analyst_scores(spec.reads_analysts, target=target)
    scores_md = render_analyst_scores_block(scores)

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

    blocks = _insert_analyst_scores_block(bundle.blocks, scores_md)
    sys_chars = _system_char_count(blocks)
    rag_chunks = _rag_chunks_in_blocks(blocks)
    analyst_published = sum(1 for s in scores.values() if s.get("found"))
    analyst_missing = sum(1 for s in scores.values() if not s.get("found"))

    started = time.monotonic()
    first_token_at: float | None = None
    last_metadata: dict | None = None
    last_error: dict | None = None

    async for event in call_llm_stream(
        system=blocks,
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
            continue
        elif etype == "error":
            last_error = event
            yield event
        elif etype == "done":
            break
        else:
            yield event

    latency_s = time.monotonic() - started
    first_token_ms = (
        int((first_token_at - started) * 1000) if first_token_at else None
    )

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
        "strategist_id": spec.id,
        "display_name": spec.display_name,
        "track": spec.track,
        "target": target,
        "reads_analysts": list(spec.reads_analysts),
        "analyst_published_count": analyst_published,
        "analyst_missing_count": analyst_missing,
        "analyst_missing_ids": [aid for aid, s in scores.items() if not s.get("found")],
        "rag_dept": rag_dept,
        "rag_chunks_returned": rag_chunks,
        "system_prompt_chars": sys_chars,
        "system_blocks": len(blocks),
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
        "content": md_src.get("content", ""),
    }

    log.info(
        "strategist_stream_done",
        strategist=spec.id,
        track=spec.track,
        target=target,
        analyst_published=analyst_published,
        analyst_missing=analyst_missing,
        chars=sys_chars,
        tokens_in=metadata["tokens_in"],
        tokens_out=metadata["tokens_out"],
        cost_usd=metadata["cost_usd"],
        latency_s=metadata["latency_s"],
        first_token_ms=first_token_ms,
    )

    yield {"type": "metadata", **metadata}
    yield {"type": "done"}
