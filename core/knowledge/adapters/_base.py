"""어댑터 Protocol + ExtractedDocument dataclass — KNOWLEDGE-SYNC-001 Phase 1.

각 형식별 어댑터 (markdown/text/pdf/xlsx/png) 가 공유하는 인터페이스.
ingest.py 가 ExtractedDocument 를 받아 chunking + metadata 합성.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class ExtractedDocument:
    """어댑터 추출 결과."""

    body_text: str
    frontmatter_meta: dict[str, Any] = field(default_factory=dict)
    extraction_meta: dict[str, Any] = field(default_factory=dict)


class Adapter(Protocol):
    """확장자별 추출 어댑터."""

    extensions: tuple[str, ...]

    def extract(self, path: Path) -> ExtractedDocument: ...
