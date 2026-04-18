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

def load_shared_canon() -> str:
    """Load all MD files from knowledge/canon/ as a combined canon string.

    These represent the user's core investment knowledge — always injected
    into every LLM call regardless of pipeline.
    """
    canon_dir = KNOWLEDGE_DIR / "canon"
    if not canon_dir.exists():
        return ""
    parts: list[str] = []
    for md_file in sorted(canon_dir.glob("*.md")):
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
    response_rules: str | None = None,
) -> SystemPromptBundle:
    """Assemble system prompt for a pipeline stage.

    Layout (all cached blocks use Anthropic prompt caching):
      [0] Shared canon (knowledge/canon/*.md)     — cached
      [1] Pipeline persona (prompts/analyst.md)    — cached
      [2] Memory context (recent days + rollups)   — cached
      [3] RAG chunks (dynamic)                     — not cached
      [4] Response rules                           — not cached
    """
    blocks: list[dict] = []

    # [0] Shared canon — the user's brain
    if include_shared_canon:
        canon = load_shared_canon().strip()
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

    # [3] RAG chunks (not cached — query-dependent)
    if query_for_rag:
        try:
            from core.knowledge.retrieve import retrieve
            # Use "shared" collection for pipeline mode
            results = await retrieve("shared", query_for_rag, top_k=3)
        except Exception as e:  # noqa: BLE001
            log.warning("retrieval_failed", context=context_id, error=str(e))
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
