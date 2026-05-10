"""PNG adapter — default OFF (KNOWLEDGE-SYNC-001 SPEC L507).

이미지 → 텍스트 변환은 Anthropic vision API 호출 비용이 발생.
비용 가시화 전까지 default off, ingest 가 png 파일 만나면 skip + warning.

향후 enable 시: anthropic vision 호출 + extraction cache (file_hash 기반)
`data/chroma/<dept>/_extraction_cache/<file_hash>.txt`.
"""
from __future__ import annotations

from pathlib import Path

from core.knowledge.adapters._base import ExtractedDocument


class PngAdapter:
    extensions: tuple[str, ...] = (".png",)
    enabled_by_default: bool = False

    def extract(self, path: Path) -> ExtractedDocument:
        raise NotImplementedError(
            "PNG adapter is default off — Anthropic vision API cost protection. "
            "Enable explicitly when ready (KNOWLEDGE-SYNC-001 SPEC L507)."
        )
