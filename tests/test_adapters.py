"""KNOWLEDGE-SYNC-001 Phase 1 — 어댑터 5종 단위 테스트.

대상:
- MarkdownAdapter: frontmatter + body 분리
- TextAdapter: UTF-8 read + char_count
- PdfAdapter: page_count + 한글 공백 휴리스틱 (normalize)
- XlsxAdapter: 다중 sheet → tab-delimited body
- PngAdapter: default off (NotImplementedError + enabled_by_default=False)

실 외부 API 호출 0. fixture 는 tmp_path 로 동적 생성.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.knowledge.adapters import ADAPTERS, get_adapter
from core.knowledge.adapters._base import ExtractedDocument
from core.knowledge.adapters.markdown import MarkdownAdapter
from core.knowledge.adapters.pdf import PdfAdapter, _normalize_korean_spacing
from core.knowledge.adapters.png import PngAdapter
from core.knowledge.adapters.text import TextAdapter
from core.knowledge.adapters.xlsx import XlsxAdapter


# ---------------------------------------------------------------------------
# 레지스트리
# ---------------------------------------------------------------------------


def test_adapter_registry_covers_5_extensions() -> None:
    assert set(ADAPTERS.keys()) == {".md", ".txt", ".pdf", ".xlsx", ".png"}


def test_get_adapter_case_insensitive() -> None:
    assert isinstance(get_adapter(".MD"), MarkdownAdapter)
    assert isinstance(get_adapter(".PNG"), PngAdapter)
    assert get_adapter(".unknown") is None


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def test_markdown_adapter_extracts_frontmatter_and_body(tmp_path: Path) -> None:
    md = tmp_path / "doc.md"
    md.write_text(
        "---\ntitle: 테스트\nlang: ko\n---\n\n본문 내용입니다.",
        encoding="utf-8",
    )
    ed = MarkdownAdapter().extract(md)
    assert isinstance(ed, ExtractedDocument)
    assert "본문 내용" in ed.body_text
    assert ed.frontmatter_meta == {"title": "테스트", "lang": "ko"}


def test_markdown_adapter_handles_no_frontmatter(tmp_path: Path) -> None:
    md = tmp_path / "plain.md"
    md.write_text("# 제목\n\n본문만 있음", encoding="utf-8")
    ed = MarkdownAdapter().extract(md)
    assert "본문만 있음" in ed.body_text
    assert ed.frontmatter_meta == {}


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------


def test_text_adapter_reads_utf8_and_reports_char_count(tmp_path: Path) -> None:
    txt = tmp_path / "f.txt"
    body = "한글 텍스트 테스트입니다."
    txt.write_text(body, encoding="utf-8")
    ed = TextAdapter().extract(txt)
    assert ed.body_text == body
    assert ed.extraction_meta["char_count"] == len(body)


# ---------------------------------------------------------------------------
# PDF — pypdf 의존성 (이미 설치되어 있음)
# ---------------------------------------------------------------------------


def test_normalize_korean_spacing_collapses_design_pdf_singles() -> None:
    # 디자인 PDF 패턴: 한글 글자 사이 single space (>= 100개)
    text = "돈 이 휴 지 가 되 는 시 대 " * 20
    normalized = _normalize_korean_spacing(text)
    assert "돈이휴지" in normalized.replace(" ", "")
    # multi-space 가 더 많으면 normalize 안 함
    text2 = "돈  이  휴  지" * 30
    out = _normalize_korean_spacing(text2)
    assert "돈  이" in out  # 보존


def test_pdf_adapter_extracts_page_count(tmp_path: Path) -> None:
    """real pypdf write — blank page 1개 PDF 생성."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    pdf_path = tmp_path / "blank.pdf"
    with pdf_path.open("wb") as f:
        writer.write(f)

    ed = PdfAdapter().extract(pdf_path)
    assert ed.extraction_meta["page_count"] == 1
    # blank page → 텍스트 0
    assert ed.body_text == ""


# ---------------------------------------------------------------------------
# XLSX
# ---------------------------------------------------------------------------


def test_xlsx_adapter_combines_sheets_with_headers(tmp_path: Path) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Sheet1"
    ws1["A1"] = "header1"
    ws1["B1"] = "header2"
    ws1["A2"] = "한국어"
    ws1["B2"] = 42
    ws2 = wb.create_sheet("계산")
    ws2["A1"] = "수식"
    ws2["A2"] = "=A1+1"  # data_only=True 라 빈 값으로 읽힐 가능성
    xlsx_path = tmp_path / "f.xlsx"
    wb.save(xlsx_path)

    ed = XlsxAdapter().extract(xlsx_path)
    assert "## Sheet: Sheet1" in ed.body_text
    assert "## Sheet: 계산" in ed.body_text
    assert "header1\theader2" in ed.body_text
    assert "한국어\t42" in ed.body_text
    assert ed.extraction_meta["sheet_count"] == 2


# ---------------------------------------------------------------------------
# PNG — default off
# ---------------------------------------------------------------------------


def test_png_adapter_disabled_by_default() -> None:
    assert PngAdapter().enabled_by_default is False


def test_png_adapter_raises_not_implemented(tmp_path: Path) -> None:
    fake = tmp_path / "img.png"
    fake.write_bytes(b"fake png bytes")
    with pytest.raises(NotImplementedError):
        PngAdapter().extract(fake)
