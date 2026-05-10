"""Compose system prompt for LLM pipelines/teams (persona + canon + memory + RAG).

Structured to benefit from Anthropic prompt caching (cache_control on
stable blocks — persona, canon, memory). Retrieved chunks are dynamic
and not cached.

Supports two modes:
  - Legacy team mode: build_system_prompt(team_id=...)
  - Pipeline mode:    build_pipeline_prompt(context_id=..., persona_path=...)
"""
from __future__ import annotations

from pathlib import Path

from core.contracts.knowledge import SystemPromptBundle
from core.logging import get_logger
from core.memory.loader import render_context_markdown
from core.registry import get_team

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"


def _read_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Shared Knowledge (the user's brain)
# ---------------------------------------------------------------------------

def load_shared_canon(canon_categories: list[str] | None = None) -> str:
    """Load MD files from knowledge/canon/ (recursively) as a combined canon string.

    Walks 9 지식부 sub-folders (principles/, trading/, market_macro/, ...) plus
    any future siblings. README.md files are scaffolding-only and excluded.

    `canon_categories` 가 주어지면 `["dept/category", ...]` 형태로 해석해
    해당 카테고리 폴더의 md 만 통과 (KNOWLEDGE-SYNC-001 Phase 2 M1). None 이면
    9 지식부 전체 (legacy 동작).
    """
    canon_dir = KNOWLEDGE_DIR / "canon"
    if not canon_dir.exists():
        return ""
    md_files = sorted(
        canon_dir.rglob("*.md"),
        key=lambda p: p.relative_to(canon_dir).as_posix(),
    )
    allowed = set(canon_categories) if canon_categories else None
    parts: list[str] = []
    for md_file in md_files:
        if md_file.name.lower() == "readme.md":
            continue
        if allowed is not None:
            rel_parts = md_file.relative_to(canon_dir).parts
            if len(rel_parts) < 3:
                continue  # canon 직속 / dept 직속 md 는 카테고리 필터 모드에서 제외
            if f"{rel_parts[0]}/{rel_parts[1]}" not in allowed:
                continue
        content = _read_file(md_file).strip()
        if content:
            parts.append(content)
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Legacy team mode (backward compat)
# ---------------------------------------------------------------------------

def load_canon(team_id: str) -> str:
    team = get_team(team_id)
    if team is None or team.path is None:
        return ""
    canon_path = team.path / "knowledge" / "compiled.md"
    return _read_file(canon_path)


def load_persona(team_id: str) -> str:
    team = get_team(team_id)
    if team is None or team.path is None:
        return ""
    persona_path = team.path / "persona.md"
    return _read_file(persona_path)


async def build_system_prompt(
    team_id: str,
    *,
    query_for_rag: str | None = None,
    include_memory: bool = True,
    token_budget_memory: int = 3000,
) -> SystemPromptBundle:
    """Legacy: Assemble system prompt for a team-based agent."""
    from core.knowledge.retrieve import retrieve  # late import

    blocks: list[dict] = []

    persona = load_persona(team_id).strip()
    if persona:
        blocks.append({
            "type": "text",
            "text": f"## Persona\n{persona}",
            "cache_control": {"type": "ephemeral"},
        })

    canon = load_canon(team_id).strip()
    if canon:
        blocks.append({
            "type": "text",
            "text": f"## Knowledge (Canon)\n{canon}",
            "cache_control": {"type": "ephemeral"},
        })

    if include_memory:
        try:
            from core.memory.loader import load_context
            ctx = load_context(team_id, token_budget=token_budget_memory)
            memory_md = render_context_markdown(ctx)
        except Exception as e:  # noqa: BLE001
            log.warning("memory_load_failed", team=team_id, error=str(e))
            memory_md = ""
        if memory_md:
            blocks.append({
                "type": "text",
                "text": f"## Recent context\n{memory_md}",
                "cache_control": {"type": "ephemeral"},
            })

    if query_for_rag:
        try:
            # legacy: team_id 가 곧 dept 이름이라고 가정 (호환 경로)
            results = await retrieve(team_id, query_for_rag, top_k=3)
        except Exception as e:  # noqa: BLE001
            log.warning("retrieval_failed", team=team_id, error=str(e))
            results = []
        if results:
            chunks_text = "\n\n".join(
                f"### [{r.chunk.source_title or r.chunk.source_id}]\n{r.chunk.text}"
                for r in results
            )
            blocks.append({
                "type": "text",
                "text": f"## Retrieved references\n{chunks_text}",
            })

    blocks.append({
        "type": "text",
        "text": (
            "\n## Response rules\n"
            "- Respond with a single JSON object.\n"
            "- Required keys: verdict (string), confidence (0-100 integer), "
            "reasons (array of strings, minimum 3), narrative (string).\n"
            "- If uncertain, lower confidence and explain in narrative."
        ),
    })

    return SystemPromptBundle(
        blocks=blocks,
        cache_breakpoint_count=sum(1 for b in blocks if b.get("cache_control")),
    )


# ---------------------------------------------------------------------------
# Pipeline mode (new)
# ---------------------------------------------------------------------------

async def build_pipeline_prompt(
    *,
    context_id: str,
    persona_path: Path | None = None,
    include_shared_canon: bool = True,
    include_memory: bool = True,
    token_budget_memory: int = 4000,
    query_for_rag: str | None = None,
    rag_dept: str | None = None,
    canon_categories: list[str] | None = None,
    market_snapshot_md: str | None = None,
    response_rules: str | None = None,
) -> SystemPromptBundle:
    """Assemble system prompt for a pipeline stage.

    Layout (cache_control 박힌 블록만 Anthropic prompt caching 대상):
      [0] Shared canon (knowledge/canon/*.md)     — cached
      [1] Pipeline persona (prompts/analyst.md)    — cached
      [2] Memory context (recent days + rollups)   — cached
      [3] Market snapshot (5분 갱신)                — not cached
      [4] RAG chunks (query 종속)                   — not cached
      [5] Response rules                           — not cached

    RAG: `query_for_rag` 와 `rag_dept` 둘 다 주어지면 retrieve. 둘 다 없으면 skip.
    Market snapshot: `market_snapshot_md` 주어지면 RAG 직전 삽입 (캐시 분리선 뒤).
    """
    blocks: list[dict] = []

    # [0] Shared canon — the user's brain
    if include_shared_canon:
        canon = load_shared_canon(canon_categories=canon_categories).strip()
        if canon:
            blocks.append({
                "type": "text",
                "text": f"## Investment Knowledge (Canon)\n{canon}",
                "cache_control": {"type": "ephemeral"},
            })

    # [1] Pipeline-specific persona
    if persona_path:
        persona = _read_file(persona_path).strip()
        if persona:
            blocks.append({
                "type": "text",
                "text": f"## Persona\n{persona}",
                "cache_control": {"type": "ephemeral"},
            })

    # [2] Memory context (continuity across days)
    if include_memory:
        try:
            from core.memory.loader import load_context
            ctx = load_context(context_id, token_budget=token_budget_memory)
            memory_md = render_context_markdown(ctx)
        except Exception as e:  # noqa: BLE001
            log.warning("memory_load_failed", context=context_id, error=str(e))
            memory_md = ""
        if memory_md:
            blocks.append({
                "type": "text",
                "text": f"## Recent Context (Memory)\n{memory_md}",
                "cache_control": {"type": "ephemeral"},
            })

    # [3] Market snapshot (not cached — 5분마다 갱신)
    if market_snapshot_md:
        blocks.append({
            "type": "text",
            "text": f"## Market Snapshot (current)\n{market_snapshot_md}",
        })

    # [4] RAG chunks (not cached — query-dependent)
    if query_for_rag and rag_dept:
        # canon_categories 중 rag_dept 와 일치하는 항목의 카테고리만 추출
        rag_categories: list[str] | None = None
        if canon_categories:
            rag_categories = [
                cc.split("/", 1)[1]
                for cc in canon_categories
                if "/" in cc and cc.split("/", 1)[0] == rag_dept
            ] or None
        try:
            from core.knowledge.retrieve import retrieve
            results = await retrieve(
                rag_dept,
                query_for_rag,
                categories=rag_categories,
                top_k=3,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("retrieval_failed", context=context_id, dept=rag_dept, error=str(e))
            results = []
    else:
        results = []
    if results:
        chunks_text = "\n\n".join(
            f"### [{r.chunk.source_title or r.chunk.source_id}]\n{r.chunk.text}"
            for r in results
        )
        blocks.append({
            "type": "text",
            "text": f"## Retrieved References\n{chunks_text}",
        })

    # [4] Response rules
    rules = response_rules or (
        "\n## Response rules\n"
        "- Respond with a single JSON object.\n"
        "- Required keys: verdict (string), confidence (0-100 integer), "
        "reasons (array of strings, minimum 3), narrative (string).\n"
        "- If uncertain, lower confidence and explain in narrative."
    )
    blocks.append({"type": "text", "text": rules})

    return SystemPromptBundle(
        blocks=blocks,
        cache_breakpoint_count=sum(1 for b in blocks if b.get("cache_control")),
    )
