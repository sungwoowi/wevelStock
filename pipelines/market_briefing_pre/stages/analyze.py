"""Stage: analyze — LLM 통합 판단 생성 (morning_pre).

Builds system prompt from shared canon + persona + memory, then calls the
LLM once with a structured user prompt containing all prior stage data.
Returns a rich JSON with scenario, news_impact, sector_watch,
positions_advice, new_candidates.
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
from core.outputs import persist_output, today_date_string
from pipelines._base import Stage, StageContext, StageResult, pipeline_prompts_dir

log = get_logger(__name__)

PROMPTS_DIR = pipeline_prompts_dir(__file__)


def _read_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _format_user_prompt(
    overnight_us: dict,
    macro: dict,
    night_futures: dict,
    news: list[dict],
    positions: dict,
    principles: dict,
) -> str:
    template = _read_prompt("briefing.md")
    if not template:
        return json.dumps(
            {
                "overnight_us": overnight_us,
                "macro": macro,
                "night_futures": night_futures,
                "news": news,
                "positions": positions,
                "principles": principles,
            },
            ensure_ascii=False,
            indent=2,
        )
    return template.format(
        overnight_us=json.dumps(overnight_us, ensure_ascii=False, indent=2),
        macro=json.dumps(macro, ensure_ascii=False, indent=2),
        night_futures=json.dumps(night_futures, ensure_ascii=False, indent=2),
        news=json.dumps(news, ensure_ascii=False, indent=2),
        positions=json.dumps(positions, ensure_ascii=False, indent=2),
        principles=json.dumps(principles, ensure_ascii=False, indent=2),
    )


def _parse_llm_response(content: str) -> dict[str, Any]:
    """Extract the top-level JSON from LLM response (tolerant to code fences)."""
    text = content.strip()
    if text.startswith("```"):
        lines = [l for l in text.split("\n") if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

    return {
        "verdict": "neutral",
        "confidence": 40,
        "reasons": ["LLM 응답 파싱 실패 — 원본 텍스트 참조"],
        "narrative": content[:1000],
        "raw_unparsed": True,
    }


def _sanitize_new_candidates(parsed: dict[str, Any]) -> None:
    """Strip placeholder tickers in-place; drop items without a usable name."""
    candidates = parsed.get("new_candidates")
    if not isinstance(candidates, list):
        return
    cleaned: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).strip()
        if ticker and set(ticker) <= {"0", "-", "_", "?", "x", "X", " "}:
            ticker = ""
        item["ticker"] = ticker
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        item["name"] = name
        cleaned.append(item)
    parsed["new_candidates"] = cleaned


def _normalize_verdict(v: str | None) -> str:
    if not v:
        return "neutral"
    v = str(v).lower().strip()
    mapping = {
        "bullish": "positive", "positive": "positive", "strong": "positive",
        "bearish": "caution", "negative": "caution", "weak": "caution",
        "danger": "alert", "critical": "alert", "warning": "alert",
    }
    if v in mapping:
        return mapping[v]
    if v in ("positive", "neutral", "caution", "alert"):
        return v
    for key, target in mapping.items():
        if key in v:
            return target
    return "neutral"


class AnalyzeStage(Stage):
    stage_id = "analyze"
    stage_type = "analyze"

    async def run(self, ctx: StageContext) -> StageResult:
        pipeline_id = ctx.pipeline_id

        overnight = ctx.get_stage_data("collect_overnight_us") or {}
        futures = ctx.get_stage_data("collect_night_futures") or {}
        news_data = ctx.get_stage_data("collect_news") or {}
        positions = ctx.get_stage_data("load_positions") or {}
        principles = ctx.get_stage_data("check_principles") or {}

        overnight_us = overnight.get("overnight_us", {})
        macro = overnight.get("macro", {})
        night_futures = futures.get("night_futures", {})
        news_items = news_data.get("items", [])

        # Build system prompt (canon + persona + memory)
        persona_path = PROMPTS_DIR / "analyst.md"
        system_bundle = await build_pipeline_prompt(
            context_id=pipeline_id,
            persona_path=persona_path,
            include_shared_canon=True,
            include_memory=True,
            token_budget_memory=4000,
            response_rules=(
                "\n## Response rules\n"
                "- Respond with a single JSON object matching the schema in the prompt.\n"
                "- All fields must be present; use empty list/string when not applicable.\n"
                "- news_impact MUST have one entry per input news item (url field copied verbatim).\n"
            ),
        )

        user_content = _format_user_prompt(
            overnight_us=overnight_us,
            macro=macro,
            night_futures=night_futures,
            news=news_items,
            positions=positions,
            principles=principles,
        )

        input_hash = compute_input_hash(
            input_data={
                "overnight_us": overnight_us,
                "macro": macro,
                "night_futures": night_futures,
                "news_urls": [n.get("url") for n in news_items],
                "positions": positions,
                "principles": principles,
            },
            model="claude-sonnet-4-5",
            contract_version="1.0",
        )

        resp = await call_llm(
            call_type="briefing",
            target="global",
            system=system_bundle.blocks,
            messages=[{"role": "user", "content": user_content}],
            input_hash=input_hash,
            max_tokens=8000,
            temperature=0.3,
        )

        parsed = _parse_llm_response(resp["content"])
        _sanitize_new_candidates(parsed)
        verdict = _normalize_verdict(parsed.get("verdict"))
        try:
            confidence = min(100, max(0, int(parsed.get("confidence", 50))))
        except (TypeError, ValueError):
            confidence = 50
        reasons = parsed.get("reasons") or ["분석 완료"]
        if not isinstance(reasons, list) or not reasons:
            reasons = ["분석 완료"]
        narrative = parsed.get("narrative") or ""

        # Persist StandardOutput (team_outputs) + memory (for continuity)
        try:
            output = StandardOutput.build(
                team_id=pipeline_id,
                run_id=ctx.run_id,
                verdict=verdict,
                confidence=confidence,
                reasons=reasons,
                data={
                    "briefing": parsed,
                    "narrative": narrative,
                },
                metadata=OutputMetadata(
                    model=resp.get("model", "unknown"),
                    input_hash=input_hash,
                    cost_usd=resp.get("cost_usd"),
                ),
            )
            persist_output(output)
        except Exception as e:  # noqa: BLE001
            log.warning("output_persist_failed", error=str(e))

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
            "morning_pre_analysis_complete",
            pipeline=pipeline_id,
            verdict=verdict,
            confidence=confidence,
            cost_usd=resp.get("cost_usd"),
        )

        return StageResult(
            stage_id=self.stage_id,
            status="ok",
            data={
                "briefing": parsed,
                "verdict": verdict,
                "confidence": confidence,
                "reasons": reasons,
                "narrative": narrative,
                "model": resp.get("model"),
                "cost_usd": resp.get("cost_usd"),
                "input_hash": input_hash,
            },
            verdict=verdict,
            confidence=confidence,
            reasons=reasons,
        )
