"""Executive synthesis — ARCHITECTURE-HYBRID-EXECUTIVE-001 PoC.

9 분석가 정량 판단 + 2 전략가 권고 raw → **투자 총괄 임원** 페르소나(doctrine)로
사용자 발화에 직답하는 자연어 종합 1개. PRODUCTION-UX 의 formatter('압축기')를
'doctrine 통합 추론 임원'으로 끌어올린 버전.

formatter 와의 차이 (cycle 6 옵션 2 = 하이브리드 임원):
  - system = `agents/executive/persona.md` (임원 doctrine: 5-layer chain / 시나리오 3 /
    상황별 가중치 / 박종훈 변곡점 스코프 / 환각 가드) + canon 주입 + label 사전.
  - DEEP tier (Gemini Pro) — config.llm.areas.executive_synthesis.
  - max_tokens 3500 (formatter 800 대비 풍부한 종합 서사).
  - 전략가 verdict 맹종 X — 분석가 raw 신호를 임원이 직접 재통합 (기계적 'wait' 탈출).

formatter 와 동형 보존:
  - 코드 라벨 본문 노출 금지 (label_dictionary.yaml 사전 주입).
  - mock/upstream_error/빈 응답은 입력에서 제외 + 누락 명시 (가짜 narrative 차단).
  - production 경로 = mock_fallback_allowed=False (feedback_no_silent_mock_in_production).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from core.intent.formatter import _build_label_block, _is_mock_entry, scrub_code_labels
from core.knowledge.compose import load_shared_canon
from core.llm.client import call_llm
from core.llm.tiers import resolve_model_for_area
from core.logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
PERSONA_PATH = REPO_ROOT / "agents" / "executive" / "persona.md"
MANIFEST_PATH = REPO_ROOT / "agents" / "executive" / "manifest.yaml"

# 임원 입력 truncation — DEEP tier (Gemini Pro 1M context) 라 formatter 보다 넉넉.
_ANALYST_TRUNC = 4500
_STRATEGIST_TRUNC = 6000


@dataclass
class ExecutiveResult:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    is_mock: bool
    upstream_error: str | None = None


@lru_cache(maxsize=1)
def _load_persona() -> str:
    if not PERSONA_PATH.exists():
        log.warning("executive_persona_missing", path=str(PERSONA_PATH))
        return "당신은 wevelStock 의 투자 총괄 임원이다. 분석가/전략가 raw 를 종합해 사용자에게 직답한다."
    return PERSONA_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        log.warning("executive_manifest_missing", path=str(MANIFEST_PATH))
        return {}
    try:
        return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8")) or {}
    except Exception as e:  # noqa: BLE001
        log.warning("executive_manifest_load_failed", error=str(e))
        return {}


def reload_executive_config() -> None:
    """테스트/hot reload — persona·manifest 캐시 클리어."""
    _load_persona.cache_clear()
    _load_manifest.cache_clear()


def _build_system_blocks() -> list[dict[str, Any]]:
    """[0] 임원 persona doctrine + [1] canon (변곡점 거시 포함) + [2] label 사전."""
    manifest = _load_manifest()
    canon_categories = manifest.get("canon_categories") or None
    canon = load_shared_canon(canon_categories=canon_categories)

    blocks: list[dict[str, Any]] = [{"type": "text", "text": _load_persona()}]
    if canon.strip():
        blocks.append(
            {
                "type": "text",
                "text": "## Investment Knowledge (Canon)\n\n" + canon,
            }
        )
    blocks.append({"type": "text", "text": _build_label_block()})
    return blocks


def _has_real(entries: list[dict[str, Any]]) -> bool:
    for e in entries:
        if e.get("error"):
            continue
        if _is_mock_entry(e):
            continue
        if (e.get("text") or "").strip():
            return True
    return False


def _compose_user_message(
    user_input: str,
    analyst_outputs: list[dict[str, Any]],
    strategist_outputs: list[dict[str, Any]],
    *,
    market_snapshot_md: str | None = None,
) -> str:
    """임원 종합용 user prompt — 사용자 발화 + 분석가/전략가 raw 풀세트.

    mock/upstream_error/빈 응답은 본문 제외 + 끝에 누락 명시 (formatter 동형).
    """
    lines: list[str] = [f"## 사용자 발화\n{user_input}\n"]

    if market_snapshot_md and market_snapshot_md.strip():
        lines.append("## 실시간 시장 스냅샷 (수치 인용 시 출처)")
        lines.append(market_snapshot_md.strip())
        lines.append("")

    failed_analysts: list[str] = []
    failed_strategists: list[str] = []

    if analyst_outputs:
        lines.append("## 9 분석가 정량 판단 (prefetch raw — 점수·격자·코멘트)")
        for entry in analyst_outputs:
            aid = entry.get("id") or entry.get("agent_id", "?")
            text = (entry.get("text") or "").strip()
            if entry.get("error") or _is_mock_entry(entry) or not text:
                failed_analysts.append(str(aid))
                continue
            if len(text) > _ANALYST_TRUNC:
                text = text[:_ANALYST_TRUNC] + "\n... (truncated)"
            lines.append(f"\n### 분석가: {aid}\n{text}")
        lines.append("")

    if strategist_outputs:
        lines.append("## 전략가 권고 (Track A/B raw — verdict 는 참고만, 기계적 결론에 갇히지 말 것)")
        for entry in strategist_outputs:
            sid = entry.get("agent_id") or entry.get("id", "?")
            text = (entry.get("text") or "").strip()
            if entry.get("error") or _is_mock_entry(entry) or not text:
                failed_strategists.append(str(sid))
                continue
            if len(text) > _STRATEGIST_TRUNC:
                text = text[:_STRATEGIST_TRUNC] + "\n... (truncated)"
            lines.append(f"\n### 전략가: {sid}\n{text}")
        lines.append("")

    if failed_analysts or failed_strategists:
        lines.append("## 응답 누락 (LLM 호출 실패 또는 mock fallback — 추정 금지)")
        if failed_analysts:
            lines.append(f"- 분석가 누락: {', '.join(failed_analysts)}")
        if failed_strategists:
            lines.append(f"- 전략가 누락: {', '.join(failed_strategists)}")
        lines.append(
            "위 영역은 정량 점수가 비었습니다. 추정하지 말고, 있는 anchor 로 통찰을 내되 "
            "비는 부분은 '아직 산출 전'이라 솔직히 밝히세요. **누락이 답 전체를 '관망'으로 만들지 않게** 하세요."
        )
        lines.append("")

    lines.append(
        "위 정량 판단과 권고를 종합하여, 투자 총괄 임원으로서 사용자 발화에 직답하세요. "
        "결론 먼저 + 5-layer 자연어 chain + 시나리오 3(가격 구간·트리거·행동) + 상황별 가중치 통합. "
        "코드 라벨은 자연어로 번역하고, 전략가의 기계적 verdict 에 갇히지 마세요."
    )
    return "\n".join(lines)


async def synthesize_executive(
    user_input: str,
    analyst_outputs: list[dict[str, Any]],
    strategist_outputs: list[dict[str, Any]],
    *,
    market_snapshot_md: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> ExecutiveResult:
    """분석가 + 전략가 raw → 투자 총괄 임원 종합 자연어 답변.

    Args:
        user_input: 사용자 발화 (분류기 원문).
        analyst_outputs: prefetch 분석가 list (각 dict = {id, text, metadata, error}).
        strategist_outputs: 전략가 list (각 dict = {agent_id, text, metadata, error}).
        market_snapshot_md: 선택 — 실시간 시장 스냅샷 markdown (수치 grounding).
        provider: 명시 backend (None = config area tier + auto).
        model: 명시 모델 override (None = resolve_model_for_area). tier A/B 비교용.

    Returns:
        ExecutiveResult. 입력이 전부 mock/error/빈 응답이면 LLM skip + 안내 텍스트.
    """
    started = time.monotonic()
    provider_resolved, resolved_model = resolve_model_for_area("executive_synthesis")
    model = model or resolved_model
    if provider:
        provider_resolved = provider

    if not _has_real(analyst_outputs) and not _has_real(strategist_outputs):
        log.warning(
            "executive_all_responses_missing",
            analyst_count=len(analyst_outputs),
            strategist_count=len(strategist_outputs),
        )
        return ExecutiveResult(
            text=(
                "분석가/전략가 응답을 받지 못했습니다 (LLM 호출 실패 또는 mock fallback). "
                "잠시 후 다시 시도해주세요."
            ),
            model=model,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            latency_ms=int((time.monotonic() - started) * 1000),
            is_mock=False,
            upstream_error="all_upstream_responses_missing",
        )

    manifest = _load_manifest()
    llm_cfg = manifest.get("llm") or {}
    max_tokens = int(llm_cfg.get("max_tokens") or 3500)
    temperature = float(llm_cfg.get("temperature") if llm_cfg.get("temperature") is not None else 0.5)

    system_blocks = _build_system_blocks()
    user_msg = _compose_user_message(
        user_input,
        analyst_outputs,
        strategist_outputs,
        market_snapshot_md=market_snapshot_md,
    )

    try:
        resp = await call_llm(
            system=system_blocks,
            messages=[{"role": "user", "content": user_msg}],
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            provider=provider_resolved if provider_resolved != "mock" else None,
            mock_fallback_allowed=False,
        )
    except Exception as e:  # noqa: BLE001
        log.error(
            "executive_call_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        return ExecutiveResult(
            text=(
                "임원 종합에 실패했습니다. raw 응답을 직접 확인해주세요. "
                f"(오류: {type(e).__name__})"
            ),
            model=model,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            latency_ms=int((time.monotonic() - started) * 1000),
            is_mock=False,
            upstream_error=str(e),
        )

    latency_ms = int((time.monotonic() - started) * 1000)
    raw = resp.get("raw") or {}
    is_mock = "-mock" in str(resp.get("model", "")) or bool(raw.get("mock"))
    return ExecutiveResult(
        text=scrub_code_labels(resp.get("content", "")),
        model=resp.get("model", model),
        tokens_in=int(resp.get("tokens_in", 0)),
        tokens_out=int(resp.get("tokens_out", 0)),
        cost_usd=float(resp.get("cost_usd", 0.0)),
        latency_ms=latency_ms,
        is_mock=is_mock,
        upstream_error=raw.get("error"),
    )
