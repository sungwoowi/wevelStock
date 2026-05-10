"""KNOWLEDGE-SYNC-001 Phase 2 M1 — compose 의 canon_categories 주입.

대상:
- `load_shared_canon(canon_categories=None)`: dept/category 형식 화이트리스트 → md 필터
- `build_pipeline_prompt(canon_categories=...)`: Investment Knowledge 블록 + RAG retrieve 호출
  의 categories 인자 둘 다 카테고리 필터 적용

실 chromadb / LLM 호출 없음 — retrieve 를 monkeypatch.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest

import core.knowledge.compose as compose_mod
from core.contracts.knowledge import KnowledgeChunk, RetrievalResult

# core/knowledge/__init__.py 에서 `from .retrieve import retrieve` 가 패키지
# attribute 를 함수로 가로채는 문제 우회 (test_retrieve_categories.py 와 동일).
retrieve_mod = importlib.import_module("core.knowledge.retrieve")


def _make_canon_tree(root: Path) -> None:
    """`<root>/canon/<dept>/<category>/<file>.md` 트리 생성."""
    canon = root / "canon"
    layouts = {
        "dept_alpha": {
            "cat_x": {"01-x.md": "ALPHA-X 본문"},
            "cat_y": {"01-y.md": "ALPHA-Y 본문"},
        },
        "dept_beta": {
            "cat_z": {"01-z.md": "BETA-Z 본문"},
        },
    }
    for dept, cats in layouts.items():
        for cat, files in cats.items():
            cat_dir = canon / dept / cat
            cat_dir.mkdir(parents=True, exist_ok=True)
            for fn, body in files.items():
                (cat_dir / fn).write_text(body, encoding="utf-8")
            (cat_dir / "_category.yaml").write_text(
                f"category_id: {cat}\ntitle: {cat} title\n", encoding="utf-8"
            )
            # README.md scaffolding (excluded by load_shared_canon)
            (cat_dir / "README.md").write_text("scaffold readme", encoding="utf-8")


@pytest.fixture
def fake_canon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _make_canon_tree(tmp_path)
    monkeypatch.setattr(compose_mod, "KNOWLEDGE_DIR", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# load_shared_canon
# ---------------------------------------------------------------------------


def test_load_shared_canon_legacy_returns_all_categories(fake_canon: Path) -> None:
    """canon_categories=None (legacy) → 모든 dept/category 의 md 통합."""
    out = compose_mod.load_shared_canon()
    assert "ALPHA-X 본문" in out
    assert "ALPHA-Y 본문" in out
    assert "BETA-Z 본문" in out
    assert "scaffold readme" not in out  # README 제외


def test_load_shared_canon_filters_to_whitelist(fake_canon: Path) -> None:
    """canon_categories=['dept_alpha/cat_x'] → cat_x md 만 통과."""
    out = compose_mod.load_shared_canon(canon_categories=["dept_alpha/cat_x"])
    assert "ALPHA-X 본문" in out
    assert "ALPHA-Y 본문" not in out
    assert "BETA-Z 본문" not in out


def test_load_shared_canon_supports_multiple_depts(fake_canon: Path) -> None:
    out = compose_mod.load_shared_canon(
        canon_categories=["dept_alpha/cat_y", "dept_beta/cat_z"]
    )
    assert "ALPHA-Y 본문" in out
    assert "BETA-Z 본문" in out
    assert "ALPHA-X 본문" not in out


def test_load_shared_canon_empty_list_treated_as_no_filter(
    fake_canon: Path,
) -> None:
    """canon_categories=[] → falsy, legacy 동작."""
    out = compose_mod.load_shared_canon(canon_categories=[])
    assert "ALPHA-X 본문" in out
    assert "BETA-Z 본문" in out


# ---------------------------------------------------------------------------
# build_pipeline_prompt
# ---------------------------------------------------------------------------


def _fake_chunk(category: str, body: str) -> RetrievalResult:
    return RetrievalResult(
        chunk=KnowledgeChunk(
            chunk_id=f"{category}-0",
            team_id="dept_alpha",
            source_id=f"{category}/file.md",
            source_title=f"src-{category}",
            source_type="markdown",
            text=body,
            tags=[],
            metadata={"category": category},
        ),
        score=0.9,
    )


@pytest.mark.asyncio
async def test_build_pipeline_prompt_passes_canon_categories_to_retrieve(
    fake_canon: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """canon_categories 의 dept 와 rag_dept 가 일치하는 항목만 retrieve(categories=...)."""
    captured: dict[str, Any] = {}

    async def fake_retrieve(
        dept: str,
        query: str,
        *,
        categories: list[str] | None = None,
        top_k: int = 3,
    ) -> list[RetrievalResult]:
        captured["dept"] = dept
        captured["query"] = query
        captured["categories"] = categories
        captured["top_k"] = top_k
        return [_fake_chunk("cat_x", "RAG body x")]

    monkeypatch.setattr(retrieve_mod, "retrieve", fake_retrieve)
    monkeypatch.setattr(
        "core.memory.loader.load_context", lambda ctx_id, token_budget: None
    )
    monkeypatch.setattr(
        compose_mod, "render_context_markdown", lambda ctx: ""
    )

    bundle = await compose_mod.build_pipeline_prompt(
        context_id="test_analyst",
        persona_path=None,
        include_shared_canon=True,
        include_memory=False,
        query_for_rag="test question",
        rag_dept="dept_alpha",
        canon_categories=["dept_alpha/cat_x", "dept_beta/cat_z"],
    )

    # retrieve 는 dept_alpha 의 cat_x 만 받아야 함 (dept_beta 는 rag_dept 와 불일치)
    assert captured["dept"] == "dept_alpha"
    assert captured["categories"] == ["cat_x"]
    assert captured["query"] == "test question"

    # canon 블록은 dept_alpha/cat_x + dept_beta/cat_z 만 포함
    canon_block = next(
        b for b in bundle.blocks if "Investment Knowledge" in b["text"]
    )
    assert "ALPHA-X 본문" in canon_block["text"]
    assert "BETA-Z 본문" in canon_block["text"]
    assert "ALPHA-Y 본문" not in canon_block["text"]


@pytest.mark.asyncio
async def test_build_pipeline_prompt_without_canon_categories_legacy(
    fake_canon: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """canon_categories=None (legacy) → retrieve 에 categories=None, canon 전체 주입."""
    captured: dict[str, Any] = {}

    async def fake_retrieve(
        dept: str,
        query: str,
        *,
        categories: list[str] | None = None,
        top_k: int = 3,
    ) -> list[RetrievalResult]:
        captured["categories"] = categories
        return []

    monkeypatch.setattr(retrieve_mod, "retrieve", fake_retrieve)

    bundle = await compose_mod.build_pipeline_prompt(
        context_id="test_analyst",
        persona_path=None,
        include_shared_canon=True,
        include_memory=False,
        query_for_rag="q",
        rag_dept="dept_alpha",
        canon_categories=None,
    )

    assert captured["categories"] is None
    canon_block = next(
        b for b in bundle.blocks if "Investment Knowledge" in b["text"]
    )
    # 전체 dept 포함
    assert "ALPHA-X 본문" in canon_block["text"]
    assert "ALPHA-Y 본문" in canon_block["text"]
    assert "BETA-Z 본문" in canon_block["text"]


@pytest.mark.asyncio
async def test_build_pipeline_prompt_canon_categories_no_match_for_rag_dept(
    fake_canon: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """canon_categories 가 모두 다른 dept → retrieve(categories=None) (해당 dept 전체)."""
    captured: dict[str, Any] = {}

    async def fake_retrieve(
        dept: str,
        query: str,
        *,
        categories: list[str] | None = None,
        top_k: int = 3,
    ) -> list[RetrievalResult]:
        captured["categories"] = categories
        return []

    monkeypatch.setattr(retrieve_mod, "retrieve", fake_retrieve)

    await compose_mod.build_pipeline_prompt(
        context_id="x",
        persona_path=None,
        include_shared_canon=False,
        include_memory=False,
        query_for_rag="q",
        rag_dept="dept_alpha",
        canon_categories=["dept_beta/cat_z"],  # rag_dept(dept_alpha) 와 무관
    )
    # rag_dept 와 매칭되는 카테고리 0개 → None (dept 전체 회수, 안전 fallback)
    assert captured["categories"] is None
