"""파일 형식별 reference 자료 추출 어댑터 (KNOWLEDGE-SYNC-001 Phase 1).

각 어댑터는 ExtractedDocument 반환. ingest.py 가 확장자별 디스패치.
신규 형식 추가 = 어댑터 1개 + ADAPTERS 등록 1줄.
"""
from __future__ import annotations

from core.knowledge.adapters._base import Adapter, ExtractedDocument
from core.knowledge.adapters.markdown import MarkdownAdapter
from core.knowledge.adapters.pdf import PdfAdapter
from core.knowledge.adapters.png import PngAdapter
from core.knowledge.adapters.text import TextAdapter
from core.knowledge.adapters.xlsx import XlsxAdapter

ADAPTERS: dict[str, Adapter] = {
    ".md": MarkdownAdapter(),
    ".txt": TextAdapter(),
    ".pdf": PdfAdapter(),
    ".xlsx": XlsxAdapter(),
    ".png": PngAdapter(),
}


def get_adapter(extension: str) -> Adapter | None:
    """확장자 → 어댑터 lookup. 미지원 형식은 None (ingest 가 skip)."""
    return ADAPTERS.get(extension.lower())


__all__ = [
    "ADAPTERS",
    "Adapter",
    "ExtractedDocument",
    "MarkdownAdapter",
    "PdfAdapter",
    "PngAdapter",
    "TextAdapter",
    "XlsxAdapter",
    "get_adapter",
]
