"""Markdown adapter — python-frontmatter wrapper."""
from __future__ import annotations

from pathlib import Path

import frontmatter

from core.knowledge.adapters._base import ExtractedDocument


class MarkdownAdapter:
    extensions: tuple[str, ...] = (".md",)

    def extract(self, path: Path) -> ExtractedDocument:
        try:
            post = frontmatter.load(path)
        except Exception:
            return ExtractedDocument(body_text=path.read_text(encoding="utf-8"))
        return ExtractedDocument(
            body_text=post.content,
            frontmatter_meta=dict(post.metadata or {}),
        )
