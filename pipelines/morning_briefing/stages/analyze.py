"""Stage: analyze — LLM 종합 분석 (두뇌 이식 적용).

공유 Canon(knowledge/canon/) + 파이프라인 페르소나 + 메모리를 주입하고,
수집된 시장 데이터 + 뉴스 + 원칙 체크 결과를 종합 분석.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.contracts.memory import MemoryRecord
from core.contracts.team_output import OutputMetadata, StandardOutput
from core.knowledge.compose import build_pipeline_prompt
from core.llm.client import call_llm
from core.logging import get_logger
from core.memory.hasher import compute_input_hash
from core.memory.loader import persist_record
from core.outputs import now_isoformat_with_tz, persist_output, today_date_string
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _read_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _format_user_prompt(
    market_data: dict[str, Any],
    news_data: dict[str, Any],
    principles_result: dict[str, Any],
) -> str:
    """Fill the briefing prompt template with stage data."""
    template = _read_prompt("briefing.md")
    if not template:
        # Fallback: raw data dump
        return json.dumps(
            {
                "market": market_data,
                "news": news_data,
                "principles": principles_result,
            },
            ensure_ascii=False,
            indent=2,
        )

    return template.format(
        market_data=json.dumps(market_data, ensure_ascii=False, indent=2),
        news_data=json.dumps(news_data, ensure_ascii=False, indent=2),
        principles_result=json.dumps(principles_result, ensure_ascii=False, indent=2),
    )


def _find_nested(obj: Any, key: str) -> Any:
    """Recursively search for a key in nested dicts/lists."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _find_nested(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_nested(item, key)
            if found is not None:
                return found
    return None


def _extract_reasons(obj: Any) -> list[str]:
    """Extract a reasons list from possibly nested response."""
    # Direct top-level
    if isinstance(obj, dict):
        for key in ("reasons", "key_reasons", "evidence", "rationale"):
            val = obj.get(key)
            if isinstance(val, list) and val:
                return [str(r) for r in val if r]

        # Search nested
        for key in ("reasons", "evidence", "key_drivers", "rationale"):
            val = _find_nested(obj, key)
            if isinstance(val, list) and val:
                return [str(r) for r in val if r]

    return []


def _normalize_verdict(v: str | None) -> str:
    """Normalize various LLM verdict values to our 4 categories."""
    if not v:
        return "neutral"
    v = str(v).lower().strip()
    mapping = {
        "bullish": "positive", "positive": "positive", "strong": "positive",
        "buy": "positive", "optimistic": "positive",
        "bearish": "caution", "negative": "caution", "weak": "caution",
        "sell": "caution",
        "danger": "alert", "critical": "alert", "warning": "alert",
        "neutral": "neutral", "sideways": "neutral", "mixed": "neutral",
        "sideways_with_rotation": "neutral",
    }
    if v in mapping:
        return mapping[v]
    # Partial match
    for key, target in mapping.items():
        if key in v:
            return target
    return "neutral"


def _parse_llm_response(content: str) -> dict[str, Any]:
    """Extract structured judgment from LLM response.

    Handles:
    - Plain JSON at top level
    - Markdown code blocks
    - Nested JSON (verdict/confidence/reasons buried inside other keys)
    - Non-standard verdict values (bullish/sideways_with_rotation/etc.)
    """
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    raw = None
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                raw = json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

    if raw is None:
        return {
            "verdict": "neutral",
            "confidence": 50,
            "reasons": ["LLM 응답 파싱 실패 — 원본 텍스트 참조"],
            "narrative": text[:1000],
            "raw_unparsed": True,
        }

    # Extract fields with nested fallback
    verdict_raw = raw.get("verdict") or _find_nested(raw, "verdict")
    verdict = _normalize_verdict(verdict_raw)

    conf_val = raw.get("confidence")
    if conf_val is None:
        conf_val = _find_nested(raw, "confidence")
    try:
        confidence = min(100, max(0, int(conf_val))) if conf_val is not None else 50
    except (ValueError, TypeError):
        confidence = 50

    reasons = _extract_reasons(raw)
    if not reasons:
        # Last resort: use summary or first text field
        summary = raw.get("narrative") or _find_nested(raw, "summary")
        if summary:
            reasons = [str(summary)[:200]]
        else:
            reasons = ["분석 완료 (근거 파싱 실패)"]

    narrative = (
        raw.get("narrative")
        or _find_nested(raw, "summary")
        or _find_nested(raw, "narrative")
        or json.dumps(raw, ensure_ascii=False)[:500]
    )

    return {
        "verdict": verdict,
        "confidence": confidence,
        "reasons": reasons,
        "narrative": str(narrative),
        "raw": raw,
    }


class AnalyzeStage(Stage):
    stage_id = "analyze"
    stage_type = "analyze"

    async def run(self, ctx: StageContext) -> StageResult:
        pipeline_id = ctx.pipeline_id

        # Gather prior stage data
        market_data = ctx.get_stage_data("collect_market")
        news_data = ctx.get_stage_data("collect_news")
        principles_data = ctx.get_stage_data("check_principles")

        # Build system prompt (shared canon + persona + memory)
        persona_path = PROMPTS_DIR / "analyst.md"
        system_bundle = await build_pipeline_prompt(
            context_id=pipeline_id,
            persona_path=persona_path,
            include_shared_canon=True,
            include_memory=True,
            token_budget_memory=4000,
        )

        # Build user message
        user_content = _format_user_prompt(market_data, news_data, principles_data)

        # Compute input hash for idempotency/caching
        input_hash = compute_input_hash(
            input_data={
                "market": market_data,
                "news": news_data,
                "principles": principles_data,
            },
            model="claude-sonnet-4-5",
            contract_version="1.0",
        )

        # Call LLM
        resp = await call_llm(
            system=system_bundle.blocks,
            messages=[{"role": "user", "content": user_content}],
            input_hash=input_hash,
            max_tokens=2000,
            temperature=0.3,
        )

        # Parse response
        parsed = _parse_llm_response(resp["content"])
        verdict = parsed.get("verdict", "neutral")
        confidence = min(100, max(0, int(parsed.get("confidence", 50))))
        reasons = parsed.get("reasons", ["분석 완료"])
        if not reasons:
            reasons = ["분석 완료"]
        narrative = parsed.get("narrative", resp["content"][:500])

        # Persist StandardOutput
        output = StandardOutput.build(
            team_id=pipeline_id,
            run_id=ctx.run_id,
            verdict=verdict,
            confidence=confidence,
            reasons=reasons,
            data={
                "narrative": narrative,
                "market_summary": market_data.get("indicators", {}),
                "raw_analysis": parsed,
            },
            metadata=OutputMetadata(
                model=resp.get("model", "unknown"),
                input_hash=input_hash,
                cost_usd=resp.get("cost_usd"),
            ),
        )
        try:
            persist_output(output)
        except Exception as e:  # noqa: BLE001
            log.warning("output_persist_failed", error=str(e))

        # Persist memory (for continuity)
        try:
            persist_record(MemoryRecord(
                team_id=pipeline_id,
                date=today_date_string(),
                target="global",
                input_hash=input_hash,
                verdict=verdict,
                confidence=confidence,
                reasons=reasons,
                narrative=narrative,
                data=parsed,
                model=resp.get("model", "unknown"),
                contract_version="1.0",
            ))
        except Exception as e:  # noqa: BLE001
            log.warning("memory_persist_failed", error=str(e))

        log.info(
            "analysis_complete",
            pipeline=pipeline_id,
            verdict=verdict,
            confidence=confidence,
            cost_usd=resp.get("cost_usd"),
        )

        return StageResult(
            stage_id=self.stage_id,
            status="ok",
            data={
                "verdict": verdict,
                "confidence": confidence,
                "reasons": reasons,
                "narrative": narrative,
                "model": resp.get("model"),
                "cost_usd": resp.get("cost_usd"),
            },
            verdict=verdict,
            confidence=confidence,
            reasons=reasons,
        )
