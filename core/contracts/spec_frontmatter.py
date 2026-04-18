"""SPEC frontmatter parser — validates the metadata block at the top of every SPEC file.

See docs/STRUCTURE.md § SPEC 문서 규약.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import frontmatter
from pydantic import BaseModel, Field, ValidationError

SpecType = Literal["feature", "refactor", "infra", "protocol"]
SpecStatus = Literal["draft", "approved", "implementing", "implemented", "verified"]


class SpecFrontmatter(BaseModel):
    """Required metadata on every SPEC file."""

    spec_id: str
    title: str
    team: str
    type: SpecType = "feature"
    status: SpecStatus = "draft"
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
