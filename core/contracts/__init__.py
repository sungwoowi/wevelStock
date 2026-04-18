"""Shared Pydantic contracts used across teams and core modules."""
from core.contracts.knowledge import CanonInfo, KnowledgeChunk, RetrievalResult, SystemPromptBundle
from core.contracts.memory import LLMCallCache, MemoryContext, MemoryRecord, RollupRecord
from core.contracts.spec_frontmatter import ParsedSpec, SpecFrontmatter, SpecParseError, find_all_specs, parse_spec
from core.contracts.team_output import CONTRACT_VERSION, BriefingVerdict, OutputMetadata, PrincipleVerdict, StandardOutput

__all__ = [
    "CONTRACT_VERSION",
    "StandardOutput",
    "OutputMetadata",
    "PrincipleVerdict",
    "BriefingVerdict",
    "MemoryRecord",
    "RollupRecord",
    "MemoryContext",
    "LLMCallCache",
    "KnowledgeChunk",
    "RetrievalResult",
    "CanonInfo",
    "SystemPromptBundle",
    "SpecFrontmatter",
    "ParsedSpec",
    "SpecParseError",
    "parse_spec",
    "find_all_specs",
]
