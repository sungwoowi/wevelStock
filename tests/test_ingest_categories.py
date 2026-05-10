"""KNOWLEDGE-SYNC-001 Phase 1 — ingest 카테고리 metadata 통합 테스트.

대상:
- _iter_reference_files: 카테고리 폴더 인식, _ prefix skip, 어댑터 디스패치
- _load_category_meta: canon 의 _category.yaml 로드
- _build_metadata: frontmatter + extraction + category 3중 병합
- ingest(): 멱등성 (file_hash skip) + metadata backfill (legacy index 업데이트)

실 chromadb 호출 없음 (mock). reference / canon 폴더는 tmp_path 동적 생성.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import core.knowledge.ingest as ingest_mod
from core.knowledge.ingest import _build_metadata, _load_category_meta


def _make_dept_tree(root: Path, dept: str, structure: dict[str, Any]) -> None:
    """root 아래 reference/<dept>/<category>/<files> + canon/<dept>/<category>/_category.yaml 생성."""
    ref_root = root / "knowledge" / "reference" / dept
    canon_root = root / "knowledge" / "canon" / dept
    for category, payload in structure.items():
        cat_ref = ref_root / category
        cat_canon = canon_root / category
        cat_ref.mkdir(parents=True, exist_ok=True)
        cat_canon.mkdir(parents=True, exist_ok=True)
        # _category.yaml in canon
        cat_yaml = payload.get("_category.yaml", "")
        if cat_yaml:
            (cat_canon / "_category.yaml").write_text(cat_yaml, encoding="utf-8")
        # files in reference
        for filename, content in payload.get("files", {}).items():
            f = cat_ref / filename
            if isinstance(content, bytes):
                f.write_bytes(content)
            else:
                f.write_text(content, encoding="utf-8")


@pytest.fixture
def fake_dept_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """tmp_path 에 fake dept 트리 만들고 ingest 의 ROOT 들을 redirect."""
    _make_dept_tree(
        tmp_path,
        "test_dept",
        {
            "cat_a": {
                "_category.yaml": (
                    "category_id: cat_a\n"
                    "title: 카테고리 A\n"
                    "description: 첫 카테고리\n"
                    "target_analysts: [foo_analyst, bar_analyst]\n"
                    "when_to_inject: always\n"
                ),
                "files": {
                    "01-alpha.md": "---\ntitle: 알파\nlang: ko\n---\n\n알파 본문 내용 한국어 텍스트.",
                    "02-beta.txt": "베타 plain text 본문",
                    "_inbox_skipped.md": "이 파일은 _ prefix 라 skip 되어야 함",
                },
            },
            "cat_b": {
                "_category.yaml": (
                    "category_id: cat_b\n"
                    "title: 카테고리 B\n"
                    "when_to_inject: regime_shift\n"
                ),
                "files": {
                    "01-charlie.md": "찰리 본문",
                },
            },
            "_skipped_cat": {
                "files": {"x.md": "이 카테고리 자체가 _ prefix 라 무시"},
            },
        },
    )
    monkeypatch.setattr(ingest_mod, "REFERENCE_ROOT", tmp_path / "knowledge" / "reference")
    monkeypatch.setattr(ingest_mod, "CANON_ROOT", tmp_path / "knowledge" / "canon")
    return tmp_path


# ---------------------------------------------------------------------------
# _load_category_meta
# ---------------------------------------------------------------------------


def test_load_category_meta_returns_yaml_dict(fake_dept_tree: Path) -> None:
    meta = _load_category_meta("test_dept", "cat_a")
    assert meta["category_id"] == "cat_a"
    assert meta["title"] == "카테고리 A"
    assert meta["target_analysts"] == ["foo_analyst", "bar_analyst"]


def test_load_category_meta_missing_returns_empty(fake_dept_tree: Path) -> None:
    assert _load_category_meta("test_dept", "nonexistent") == {}


# ---------------------------------------------------------------------------
# _iter_reference_files
# ---------------------------------------------------------------------------


def test_iter_reference_files_yields_categories_and_skips_underscore(
    fake_dept_tree: Path,
) -> None:
    items = list(ingest_mod._iter_reference_files("test_dept"))
    rels = [it[0] for it in items]
    cats = [it[1] for it in items]

    # _skipped_cat 카테고리 + _inbox_skipped.md 둘 다 제외
    assert "_skipped_cat/x.md" not in rels
    assert "cat_a/_inbox_skipped.md" not in rels

    # 정상 자료 3 (01-alpha.md, 02-beta.txt, 01-charlie.md)
    assert len(items) == 3
    assert "cat_a/01-alpha.md" in rels
    assert "cat_a/02-beta.txt" in rels
    assert "cat_b/01-charlie.md" in rels
    assert set(cats) == {"cat_a", "cat_b"}


def test_iter_reference_files_carries_category_meta(fake_dept_tree: Path) -> None:
    items = list(ingest_mod._iter_reference_files("test_dept"))
    cat_a_items = [it for it in items if it[1] == "cat_a"]
    assert cat_a_items
    _, _, _, fm, extra, _ = cat_a_items[0]
    # _category.yaml 의 키들이 extra 로 들어옴
    assert extra.get("title") == "카테고리 A"
    assert extra.get("when_to_inject") == "always"
    assert extra.get("target_analysts") == ["foo_analyst", "bar_analyst"]


def test_iter_reference_files_uses_correct_adapter(fake_dept_tree: Path) -> None:
    items = list(ingest_mod._iter_reference_files("test_dept"))
    by_rel = {it[0]: it for it in items}
    # md → frontmatter 분리됨
    md = by_rel["cat_a/01-alpha.md"]
    assert md[3] == {"title": "알파", "lang": "ko"}
    assert "알파 본문 내용" in md[2]
    # txt → 전문 그대로
    txt = by_rel["cat_a/02-beta.txt"]
    assert txt[2] == "베타 plain text 본문"
    assert txt[4].get("char_count") == len("베타 plain text 본문")


# ---------------------------------------------------------------------------
# _build_metadata
# ---------------------------------------------------------------------------


def test_build_metadata_merges_three_sources() -> None:
    fm = {"title": "원본 제목", "lang": "ko", "page_count": 5}
    extra = {
        "title": "카테고리 A",  # _category.yaml
        "description": "설명",
        "when_to_inject": "always",
        "target_analysts": ["foo", "bar"],
        "char_count": 1000,
    }
    meta = _build_metadata(
        rel_path="cat_a/file.md",
        category="cat_a",
        dept="test_dept",
        fm_meta=fm,
        extra_meta=extra,
        fhash="abc123",
        chunk_index=2,
    )
    # 기본 필드
    assert meta["source_id"] == "cat_a/file.md"
    assert meta["source_type"] == "markdown"
    assert meta["source_title"] == "원본 제목"
    assert meta["category"] == "cat_a"
    assert meta["dept"] == "test_dept"
    assert meta["chunk_index"] == 2
    assert meta["file_hash"] == "abc123"
    # frontmatter carry
    assert meta["lang"] == "ko"
    assert meta["page_count"] == 5
    # extraction carry
    assert meta["char_count"] == 1000
    # category carry — 별도 prefix 로 (frontmatter title 과 충돌 방지)
    assert meta["category_title"] == "카테고리 A"
    assert meta["category_description"] == "설명"
    assert meta["when_to_inject"] == "always"
    # target_analysts list → comma-joined
    assert meta["target_analysts"] == "foo,bar"


def test_build_metadata_handles_missing_category_yaml() -> None:
    """카테고리 yaml 없는 dept 에서도 동작."""
    meta = _build_metadata(
        rel_path="x/y.txt",
        category="x",
        dept="d",
        fm_meta={},
        extra_meta={"char_count": 10},
        fhash="h",
        chunk_index=0,
    )
    assert meta["category"] == "x"
    assert meta["source_type"] == "text"
    assert "category_title" not in meta
    assert "when_to_inject" not in meta
    assert meta["char_count"] == 10
