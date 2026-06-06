"""SPEC frontmatter parser — validates the metadata block at the top of every SPEC file.

See docs/STRUCTURE.md § SPEC 문서 규약.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import frontmatter
from pydantic import BaseModel, Field, ValidationError

SpecType = Literal["feature", "refactor", "infra", "protocol", "roadmap"]
SpecStatus = Literal["draft", "approved", "implementing", "implemented", "verified", "done"]
# 2층 SPEC 구조 (docs/STRUCTURE.md § SPEC 2-tier):
#   roadmap        = 큰 방향·마일스톤만 보유. 코드 직접 생성 X (generates 비움). children 로 자식 SPEC 연결.
#   implementation = 실제 generates 코드를 가진 SDD 단위. parent 로 소속 roadmap 명시(선택).
SpecLevel = Literal["roadmap", "implementation"]


class SpecFrontmatter(BaseModel):
    """Required metadata on every SPEC file."""

    spec_id: str
    title: str
    team: str
    type: SpecType = "feature"
    status: SpecStatus = "draft"
    level: SpecLevel = "implementation"
    parent: str | None = None              # implementation → 소속 roadmap spec_id (선택)
    children: list[str] = Field(default_factory=list)  # roadmap → 자식 implementation spec_id 목록
    generates: list[str] = Field(default_factory=list)
    modifies: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    contracts: list[dict[str, str]] = Field(default_factory=list)


class ParsedSpec(BaseModel):
    path: Path
    meta: SpecFrontmatter
    body: str

    model_config = {"arbitrary_types_allowed": True}


class SpecParseError(Exception):
    """Raised when a SPEC file is missing required frontmatter."""


def parse_spec(path: Path) -> ParsedSpec:
    """Parse a SPEC markdown file and validate frontmatter."""
    if not path.exists():
        raise SpecParseError(f"SPEC not found: {path}")
    post = frontmatter.load(path)
    if not post.metadata:
        raise SpecParseError(f"SPEC has no frontmatter: {path}")
    try:
        meta = SpecFrontmatter(**post.metadata)
    except ValidationError as e:
        raise SpecParseError(f"Invalid SPEC frontmatter in {path}:\n{e}") from e
    return ParsedSpec(path=path, meta=meta, body=post.content)


def find_all_specs(root: Path) -> list[Path]:
    """Locate every SPEC file in teams/*/specs and docs/specs."""
    paths: list[Path] = []
    teams_root = root / "teams"
    if teams_root.exists():
        for p in teams_root.glob("*/specs/*.md"):
            if p.name.startswith("_"):
                continue
            paths.append(p)
    docs_specs = root / "docs" / "specs"
    if docs_specs.exists():
        paths.extend(docs_specs.glob("*.md"))
    return sorted(paths)
