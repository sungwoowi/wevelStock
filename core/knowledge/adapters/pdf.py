"""PDF adapter — pypdf 텍스트 추출 + 디자인 PDF 한글 공백 휴리스틱.

scripts/sync_knowledge.py 의 extract_pdf_text + normalize_korean_spacing 재사용.
sync_knowledge.py 는 OneDrive 외부 source → reference/ 추출 파이프라인 (별 용도, 유지).
이 어댑터는 ingest 시점 직접 추출.
"""
from __future__ import annotations

import re
from pathlib import Path

from core.knowledge.adapters._base import ExtractedDocument


def _normalize_korean_spacing(text: str) -> str:
    """디자인 PDF (글자 사이 single space) 휴리스틱 정규화.

    pypdf 가 디자인 PDF 를 글자마다 별 textbox 로 추출 → 글자 사이 공백.
    한글 single-space 가 multi-space 의 2배 + 100개 이상이면 제거.
    """
    single = len(re.findall(r"(?<=[가-힣]) (?=[가-힣])", text))
    multi = len(re.findall(r"(?<=[가-힣])  +(?=[가-힣])", text))
    if single > max(multi * 2, 100):
        text = re.sub(r"(?<=[가-힣]) (?=[가-힣])", "", text)
        text = re.sub(r"[ \t]+", " ", text)
    return text


class PdfAdapter:
    extensions: tuple[str, ...] = (".pdf",)

    def extract(self, path: Path) -> ExtractedDocument:
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise RuntimeError("pypdf required for PDF adapter") from e

        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages:
            try:
                t = (page.extract_text() or "").strip()
            except Exception:
                continue
            if t:
                parts.append(t)
        raw = "\n\n".join(parts)
        normalized = _normalize_korean_spacing(raw)
        return ExtractedDocument(
            body_text=normalized,
            extraction_meta={
                "page_count": len(reader.pages),
                "char_count": len(normalized),
            },
        )
