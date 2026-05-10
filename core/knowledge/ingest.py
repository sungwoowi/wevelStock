"""학습부(dept)별 RAG 인덱싱 — knowledge/reference/<dept>/<category>/* → Chroma.

INFRA-RAG-001 + KNOWLEDGE-SYNC-001 Phase 1:
- 입력: `knowledge/reference/<dept>/<category>/<files>` (md/txt/pdf/xlsx/png)
- 어댑터 디스패치: 확장자별 `core.knowledge.adapters` 의 어댑터로 추출
- 카테고리 메타 주입: `knowledge/canon/<dept>/<category>/_category.yaml` ground truth
- 출력: `data/chroma/<dept>/` (collection name = dept)
- 임베딩: `core.knowledge.embed.get_embedding_function()` (한국어 BGE-m3)
- 멱등성: `collection.upsert(ids=...)` + file_hash skip

CLI:
    just knowledge-ingest <dept>          # 멱등 (upsert)
    just knowledge-ingest <dept> --force  # 컬렉션 삭제 후 재생성
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Iterable

import yaml

from core.knowledge.adapters import get_adapter
from core.knowledge.embed import get_embedding_function
from core.logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = REPO_ROOT / "knowledge" / "reference"
CANON_ROOT = REPO_ROOT / "knowledge" / "canon"
INDEX_ROOT = REPO_ROOT / "data" / "chroma"

# Frontmatter / extraction / category 메타 중 Chroma 에 흘릴 키 화이트리스트.
# Chroma metadata 는 str/int/float/bool 만 허용. 리스트·dict 는 ingest 가 직렬화.
_META_WHITELIST = (
    # frontmatter (markdown)
    "source",
    "extracted_at",
    "subfolder",
    "title",
    "lang",
    "source_pdf",
    "original_filename",
    "learning_dept",
    # extraction_meta (PDF/xlsx/text 어댑터)
    "page_count",
    "sheet_count",
    "char_count",
)

_SOURCE_TYPE_BY_EXT = {
    ".md": "markdown",
    ".txt": "text",
    ".pdf": "pdf",
    ".xlsx": "xlsx",
    ".png": "png",
}


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Simple character-based chunking — sufficient for initial RAG."""
    if not text:
        return []
    chunks: list[str] = []
    i = 0
    step = max(1, chunk_size - overlap)
    while i < len(text):
        chunks.append(text[i : i + chunk_size])
        i += step
    return chunks


def _coerce_meta_value(v: Any) -> str | int | float | bool:
    if isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


def _file_hash(p: Path) -> str:
    """Stable content hash (16 hex chars) for skip-when-unchanged."""
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def _load_category_meta(dept: str, category: str) -> dict[str, Any]:
    """canon 의 _category.yaml ground truth 로드. reference 쪽엔 없음."""
    yml = CANON_ROOT / dept / category / "_category.yaml"
    if not yml.exists():
        return {}
    try:
        loaded = yaml.safe_load(yml.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log.warning("category_yaml_load_failed", path=str(yml), error=str(e))
        return {}
    return loaded or {}


def _source_type_for_ext(suffix: str) -> str:
    return _SOURCE_TYPE_BY_EXT.get(suffix.lower(), "unknown")


def _iter_reference_files(
    dept: str,
) -> Iterable[tuple[str, str, str, dict[str, Any], dict[str, Any], str]]:
    """Yield (rel_path, category, body, frontmatter_meta, extra_meta, file_hash).

    카테고리 폴더 = dept_dir 직속 디렉토리 (`_` prefix 는 skip — 예: `_inbox`).
    카테고리 안의 파일을 확장자별 어댑터로 추출. `_` prefix path 는 모두 skip.
    extra_meta = extraction_meta + category_meta (_category.yaml 내용).
    """
    dept_dir = REFERENCE_ROOT / dept
    if not dept_dir.exists():
        return

    for category_dir in sorted(p for p in dept_dir.iterdir() if p.is_dir()):
        if category_dir.name.startswith("_"):
            continue
        category = category_dir.name
        category_meta = _load_category_meta(dept, category)

        for p in sorted(category_dir.rglob("*")):
            if not p.is_file():
                continue
            # _ prefix (어떤 path part 든) skip — _category.yaml, _inbox/, _draft.md 등
            if any(part.startswith("_") for part in p.relative_to(category_dir).parts):
                continue
            if p.name.lower() == "readme.md":
                continue

            adapter = get_adapter(p.suffix)
            if adapter is None:
                continue
            # SPEC L507: enabled_by_default=False (png 등) 은 silent skip — 비용 보호
            if not getattr(adapter, "enabled_by_default", True):
                log.debug("adapter_skipped_disabled", path=str(p), ext=p.suffix)
                continue

            try:
                extracted = adapter.extract(p)
            except Exception as e:  # noqa: BLE001
                log.warning("adapter_failed", path=str(p), error=str(e))
                continue

            body = extracted.body_text.strip()
            if not body:
                continue

            rel = p.relative_to(dept_dir).as_posix()
            fhash = _file_hash(p)
            extra: dict[str, Any] = {**dict(extracted.extraction_meta), **category_meta}
            yield (
                rel,
                category,
                extracted.body_text,
                dict(extracted.frontmatter_meta),
                extra,
                fhash,
            )


def _build_metadata(
    rel_path: str,
    category: str,
    dept: str,
    fm_meta: dict[str, Any],
    extra_meta: dict[str, Any],
    fhash: str,
    chunk_index: int,
) -> dict[str, Any]:
    """Frontmatter + extraction + category 3중 병합 → Chroma metadata."""
    title = str(fm_meta.get("title") or Path(rel_path).stem)
    suffix = Path(rel_path).suffix

    fm_carry = {
        k: _coerce_meta_value(fm_meta[k])
        for k in _META_WHITELIST
        if k in fm_meta and k not in {"title", "subfolder"}
    }
    # extraction_meta 의 page_count/sheet_count/char_count 는 화이트리스트로 가져옴
    extract_carry = {
        k: _coerce_meta_value(extra_meta[k])
        for k in ("page_count", "sheet_count", "char_count")
        if k in extra_meta
    }
    # _category.yaml 메타: title/description/when_to_inject/target_analysts
    cat_carry: dict[str, Any] = {}
    if "title" in extra_meta:
        cat_carry["category_title"] = str(extra_meta["title"])
    if "description" in extra_meta:
        cat_carry["category_description"] = str(extra_meta["description"])
    if "when_to_inject" in extra_meta:
        cat_carry["when_to_inject"] = str(extra_meta["when_to_inject"])
    if "target_analysts" in extra_meta:
        targets = extra_meta["target_analysts"] or []
        if isinstance(targets, list):
            cat_carry["target_analysts"] = ",".join(str(t) for t in targets)
        else:
            cat_carry["target_analysts"] = str(targets)

    return {
        "source_id": rel_path,
        "source_type": _source_type_for_ext(suffix),
        "source_title": title,
        "source_subfolder": category,
        "category": category,
        "chunk_index": chunk_index,
        "dept": dept,
        "file_hash": fhash,
        **fm_carry,
        **extract_carry,
        **cat_carry,
    }


def ingest(
    dept: str,
    *,
    force: bool = False,
    chunk_size: int = 800,
    overlap: int = 100,
) -> dict[str, Any]:
    """Index all reference files for one learning department into Chroma.

    Idempotent by default (`upsert` on stable chunk IDs). Use `force=True` to
    drop and recreate the collection (e.g., after embedding model change).
    """
    dept_dir = REFERENCE_ROOT / dept
    if not dept_dir.exists():
        raise ValueError(f"reference dir not found: {dept_dir}")

    index_dir = INDEX_ROOT / dept
    index_dir.mkdir(parents=True, exist_ok=True)

    try:
        import chromadb  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError("chromadb>=0.4 required for ingest") from e

    ef = get_embedding_function()
    embedding_model = getattr(ef, "model_name", None) or getattr(ef, "_model_name", "")

    client = chromadb.PersistentClient(path=str(index_dir))
    if force:
        try:
            client.delete_collection(name=dept)
            log.info("collection_dropped_for_force", dept=dept)
        except Exception:  # noqa: BLE001
            pass
    collection = client.get_or_create_collection(name=dept, embedding_function=ef)

    total_chunks = 0
    total_sources = 0
    skipped_unchanged = 0
    by_category: dict[str, int] = {}

    for rel_path, category, body, fm_meta, extra_meta, fhash in _iter_reference_files(dept):
        body = body.strip()
        if not body:
            continue
        total_sources += 1

        # Skip if first chunk already indexed with same file_hash. O(1) lookup.
        first_id = f"{rel_path}::0"
        if not force:
            try:
                existing = collection.get(ids=[first_id], include=["metadatas"])
                if existing.get("ids") and existing.get("metadatas"):
                    prev_meta = existing["metadatas"][0] or {}
                    prev_hash = prev_meta.get("file_hash")
                    prev_category = prev_meta.get("category")
                    if prev_hash == fhash and prev_category == category:
                        skipped_unchanged += 1
                        continue
                    # Backfill: legacy index without category (or hash) → patch metadata
                    # without re-embedding.
                    try:
                        chunk_set = collection.get(
                            where={"source_id": rel_path},
                            include=["metadatas"],
                        )
                        all_ids = chunk_set.get("ids", [])
                        metas_now = chunk_set.get("metadatas", [])
                        if all_ids and prev_hash == fhash:
                            patched = [
                                _build_metadata(
                                    rel_path,
                                    category,
                                    dept,
                                    fm_meta,
                                    extra_meta,
                                    fhash,
                                    (m or {}).get("chunk_index", i),
                                )
                                for i, m in enumerate(metas_now)
                            ]
                            collection.update(ids=all_ids, metadatas=patched)
                            skipped_unchanged += 1
                            log.info(
                                "metadata_backfilled",
                                source=rel_path,
                                category=category,
                                chunks=len(all_ids),
                            )
                            continue
                    except Exception as e:  # noqa: BLE001
                        log.warning(
                            "metadata_backfill_failed",
                            source=rel_path,
                            error=str(e),
                        )
            except Exception as e:  # noqa: BLE001
                log.debug("hash_check_failed", source=rel_path, error=str(e))

        chunks = _chunk_text(body, chunk_size, overlap)
        if not chunks:
            continue
        ids = [f"{rel_path}::{i}" for i in range(len(chunks))]
        metadatas = [
            _build_metadata(rel_path, category, dept, fm_meta, extra_meta, fhash, i)
            for i in range(len(chunks))
        ]
        try:
            collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
            total_chunks += len(chunks)
            by_category[category] = by_category.get(category, 0) + 1
        except Exception as e:  # noqa: BLE001
            log.warning("chroma_upsert_failed", source=rel_path, error=str(e))

    return {
        "status": "ok",
        "dept": dept,
        "sources": total_sources,
        "chunks": total_chunks,
        "skipped_unchanged": skipped_unchanged,
        "by_category": by_category,
        "index_path": str(index_dir),
        "embedding_model": embedding_model,
    }


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Ingest a learning department into Chroma.")
    parser.add_argument("dept", help="learning department id (e.g., wealth_compounding)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="drop existing collection before re-indexing",
    )
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--overlap", type=int, default=100)
    args = parser.parse_args()
    result = ingest(
        args.dept,
        force=args.force,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )
    print(result)


if __name__ == "__main__":
    _cli()
