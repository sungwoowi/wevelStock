"""Plain text adapter — UTF-8 read."""
from __future__ import annotations

from pathlib import Path

from core.knowledge.adapters._base import ExtractedDocument


class TextAdapter:
    extensions: tuple[str, ...] = (".txt",)

    def extract(self, path: Path) -> ExtractedDocument:
        text = path.read_text(encoding="utf-8", errors="replace")
        return ExtractedDocument(
            body_text=text,
            extraction_meta={"char_count": len(text)},
        )
