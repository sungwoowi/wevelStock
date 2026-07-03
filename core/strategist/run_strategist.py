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


# 분석가 metadata 의 결정론 advisory 점수 → cited_scores 필드 매핑.
# 점수 *값* 은 결정론 계산(advisory)이므로 LLM 재추출에 맡기지 않고 구조적으로 직접 주입한다
# (2026-06-01 production 시연에서 buy_score=6.0 이 자유텍스트 재추출 단계에서 null 로 누락된
# 결함 해소). alpha 는 단일 collapse 값이 없으므로(multi-timeframe) 여기 포함하지 않고
# stock_analyst raw text 의 timeframe 별 해석을 LLM 이 따른다.
_ADVISORY_SCORE_FIELDS: dict[str, str] = {
    "advisory_s_score": "s_score",
    "advisory_buy_score": "buy_score",
    "advisory_t_score": "t_score",
    "advisory_f_score": "f_score",
}


def _deterministic_scores_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """분석가 metadata 에서 None 이 아닌 결정론 advisory 점수만 cited_scores 키로 추출."""
    out: dict[str, Any] = {}
    for meta_key, cited_key in _ADVISORY_SCORE_FIELDS.items():
        val = metadata.get(meta_key)
        if val is not None:
            out[cited_key] = val
    return out


def render_prefetched_analyst_outputs(prefetched: list[dict[str, Any]]) -> str:
    """PRODUCTION-UX-001 옵션 A — production-chat 라우터가 분석가 N명을 동시 호출해
    얻은 raw text 응답을 전략가 system prompt 에 직접 주입하는 블록.

    DB read (team_outputs) 우회 — 본 production-chat 흐름 내 일관성만 보장. prism-insight
    의 Orchestrator pass-through 패턴 + wevelStock 의 asyncio.gather 병렬 결합.

    결정론 점수(`advisory_*`)는 raw text 와 별도로 **구조적으로 직접 주입**한다 — LLM 이
    자유텍스트 격자에서 점수를 재추출하다 누락하는 결함 방어 (점수 값=결정론, 해석/verdict=LLM).

    Args:
        prefetched: list of {"id": str, "text": str, "metadata": dict, "error": str | None}

    Returns:
        markdown block.
    """
    if not prefetched:
        return ""
    lines = [
        "## Analyst Direct Outputs (Layer 2 — production-chat 직접 주입)",
        "",
        "아래는 본 사용자 발화 직전에 reads_analysts 분석가들을 동시 호출하여 받은 raw 응답",
        "원문입니다. DB (`team_outputs`) read 우회 — 본 응답 흐름 내 일관성만 보장.",
        "",
        "**cited_scores 점수 필드 규칙 (중요)**: 각 분석가 아래의 '결정론 점수' 줄에 명시된",
        "s_score / buy_score / t_score / f_score 값은 결정론 계산값이므로 cited_scores 에",
        "**그대로** 인용하라 (LLM 추정·재계산 금지, raw text 격자에서 다시 읽지 말 것).",
        "결정론 점수 줄에 없는 점수만 null. alpha 는 단일 collapse 값이 없으므로 stock_analyst",
        "raw text 의 timeframe 별 해석을 따른다 (단일 값 강요 금지).",
        "그 외 명제 ID / verdict / confidence 는 raw text 에서 인용. error 가 있는 분석가는",
        "cited_scores 해당 필드 = null + reasons 에 '분석가 응답 누락' 명시.",
        "",
    ]
    for entry in prefetched:
        aid = entry.get("id", "unknown")
        text = (entry.get("text") or "").strip()
        err = entry.get("error")
        lines.append(f"### {aid}")
        # 박종훈 frame 게이팅 — wealth_strategist 의 보수적 거시 frame 이 평상시
        # 트레이딩 verdict 를 누르지 않게, 결정론 변곡점 플래그에 따라 사용 지침을
        # 자동 부착 (advisory — 점수 collapse 아님, verdict 차단 아님).
        inflection = entry.get("macro_inflection")
        if aid == "wealth_strategist" and isinstance(inflection, dict):
            if inflection.get("flag"):
                lines.append(
                    f"**[거시 frame 사용 지침 — 변곡점 감지: {inflection.get('reason', '')}]** "
                    "아래 frame 을 verdict 에 전면 반영하라 (강등·방어 전환 근거로 승격)."
                )
            else:
                lines.append(
                    "**[거시 frame 사용 지침 — 평상시]** 아래 자산전략가 frame 은 "
                    "자산배분(달러/원 비중)·사이클 위치 *맥락*으로만 인용하라. 종목 진입 "
                    "verdict(buy/wait) 의 직접 근거로 사용 금지 — 이 frame 은 설계상 "
                    "보수적이며 매매 신호가 아니다."
                )
        if err:
            lines.append(f"**호출 실패** — {err}. 본 분석가 의견은 미반영.")
            lines.append("")
            continue
        # 결정론 권위 점수 (metadata) 를 raw text 와 무관하게 먼저 주입 — 누수 방어.
        det = _deterministic_scores_from_metadata(entry.get("metadata") or {})
        if det:
            pretty = ", ".join(f"{k}={v}" for k, v in det.items())
            lines.append(f"**결정론 점수 (권위값, cited_scores 에 그대로 인용)**: {pretty}")
        if not text:
            # raw 응답이 비어도 결정론 점수가 있으면 그 점수는 살린다 (점수 ⊥ LLM 서술).
            if det:
                lines.append("_(raw 응답 비어있음 — 위 결정론 점수만 권위값으로 사용)_")
            else:
                lines.append("**빈 응답** — 본 분석가 의견은 미반영.")
            lines.append("")
            continue
        # 길이 제한: 분석가 1명 당 max ~3000 chars (system prompt 폭발 방지).
        # 6명 x 3000 = 18K chars ≈ ~5K tokens — 전략가 prompt 안정.
        if len(text) > 3000:
            text = text[:3000] + "\n... (truncated)"
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


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
    prefetched_analyst_outputs: list[dict[str, Any]] | None = None,
    alpha_posture_md: str | None = None,
    trade_plan_menu_md: str | None = None,
    mock_fallback_allowed: bool = True,
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
        prefetched_analyst_outputs: PRODUCTION-UX-001 옵션 A — production-chat
            라우터가 미리 동시 호출해 받은 분석가 raw 응답 list. None 이면 기존
            DB (team_outputs) read 모드. dict 형식 =
            {"id": str, "text": str, "metadata": dict, "error": str | None}.

    Returns:
        StrategistResponse(text, metadata)
    """
    if not messages:
        raise ValueError("messages 가 비어있습니다 (최소 1턴 user 입력 필요)")

    spec = load_strategist_spec(strategist_id)
    # RAG dept = reads 의 첫 dept (멀티 dept RAG 는 compose 측 확장 백로그)
    rag_dept = spec.reads_depts[0] if spec.reads_depts else None
    query_for_rag = _last_user_text(messages)

    # 분석가 자료 모으기 — prefetch 우선 (옵션 A), 없으면 DB read (기존)
    if prefetched_analyst_outputs is not None:
        scores = {}  # DB read 우회
        scores_md = render_prefetched_analyst_outputs(prefetched_analyst_outputs)
        analyst_source = "prefetch"
    else:
        scores = gather_analyst_scores(spec.reads_analysts, target=target)
        scores_md = render_analyst_scores_block(scores)
        analyst_source = "db_read"

    # 결정론 차등 변조 후보 (BRAIN-ALPHA-FLEXIBILITY-001) — 분석가 블록 뒤에 권위 베이스라인으로
    # 주입. 자동 권고 funnel 만 전달(채팅 경로는 None → 무변).
    if alpha_posture_md:
        scores_md = f"{scores_md}\n\n{alpha_posture_md}" if scores_md else alpha_posture_md

    # 결정론 가격대 메뉴 (TRADE-PLAN-LIFECYCLE-001 B-MS1) — 다단 손절/분할매수/목표 후보를
    # 사실로 주입. LLM 은 이 중에서 선택·조합(숫자 환각 차단). funnel 만 전달(채팅 None → 무변).
    if trade_plan_menu_md:
        scores_md = f"{scores_md}\n\n{trade_plan_menu_md}" if scores_md else trade_plan_menu_md

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

    # 분석가 자료 블록 insert (RAG 직전, source 에 따라 prefetch 또는 db_read)
    blocks = _insert_analyst_scores_block(bundle.blocks, scores_md)

    sys_chars = _system_char_count(blocks)
    rag_chunks = _rag_chunks_in_blocks(blocks)
    if analyst_source == "prefetch":
        prefetched = prefetched_analyst_outputs or []
        analyst_published = sum(
            1 for e in prefetched if not e.get("error") and (e.get("text") or "").strip()
        )
        analyst_missing = len(prefetched) - analyst_published
        analyst_missing_ids = [
            e.get("id", "?")
            for e in prefetched
            if e.get("error") or not (e.get("text") or "").strip()
        ]
    else:
        analyst_published = sum(1 for s in scores.values() if s.get("found"))
        analyst_missing = sum(1 for s in scores.values() if not s.get("found"))
        analyst_missing_ids = [aid for aid, s in scores.items() if not s.get("found")]

    started = time.monotonic()
    resp = await call_llm(
        call_type=f"strategist:{strategist_id}",
        target=target,
        system=blocks,
        messages=messages,
        model=model or spec.model,
        max_tokens=max_tokens or spec.max_tokens,
        temperature=temperature if temperature is not None else spec.temperature,
        provider=provider,
        mock_fallback_allowed=mock_fallback_allowed,
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
        "analyst_source": analyst_source,
        "analyst_published_count": analyst_published,
        "analyst_missing_count": analyst_missing,
        "analyst_missing_ids": analyst_missing_ids,
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
    prefetched_analyst_outputs: list[dict[str, Any]] | None = None,
    mock_fallback_allowed: bool = True,
):
    """run_strategist 의 streaming 변종. text_delta + 종료 시 metadata.

    Args (run_strategist 와 동일 시그니처 + prefetched_analyst_outputs):
        prefetched_analyst_outputs: PRODUCTION-UX-001 옵션 A — production-chat
            라우터가 미리 동시 호출해 받은 분석가 raw list. None 이면 DB read.

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

    if prefetched_analyst_outputs is not None:
        scores = {}
        scores_md = render_prefetched_analyst_outputs(prefetched_analyst_outputs)
        analyst_source = "prefetch"
    else:
        scores = gather_analyst_scores(spec.reads_analysts, target=target)
        scores_md = render_analyst_scores_block(scores)
        analyst_source = "db_read"

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
    if analyst_source == "prefetch":
        prefetched = prefetched_analyst_outputs or []
        analyst_published = sum(
            1 for e in prefetched if not e.get("error") and (e.get("text") or "").strip()
        )
        analyst_missing = len(prefetched) - analyst_published
        analyst_missing_ids = [
            e.get("id", "?")
            for e in prefetched
            if e.get("error") or not (e.get("text") or "").strip()
        ]
    else:
        analyst_published = sum(1 for s in scores.values() if s.get("found"))
        analyst_missing = sum(1 for s in scores.values() if not s.get("found"))
        analyst_missing_ids = [aid for aid, s in scores.items() if not s.get("found")]

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
        mock_fallback_allowed=mock_fallback_allowed,
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
        "analyst_source": analyst_source,
        "analyst_published_count": analyst_published,
        "analyst_missing_count": analyst_missing,
        "analyst_missing_ids": analyst_missing_ids,
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
