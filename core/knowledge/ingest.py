"""학습부(dept)별 RAG 인덱싱 — knowledge/reference/<dept>/**/*.md → Chroma.

INFRA-RAG-001 5-Layer 리팩터:
- 입력: `knowledge/reference/<dept>/` (sync_knowledge.py 가 멱등 추출한 markdown)
- 출력: `data/chroma/<dept>/` (PersistentClient + collection name = dept)
- 임베딩: `core.knowledge.embed.get_embedding_function()` 명시 wiring (한국어 BGE-m3)
- 멱등성: `collection.upsert(ids=...)` — 동일 chunk_id 재인덱싱 시 덮어씀

CLI:
    just knowledge-ingest <dept>          # 멱등 (upsert)
    just knowledge-ingest <dept> --force  # 컬렉션 삭제 후 재생성
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Iterable

import frontmatter

from core.knowledge.embed import get_embedding_function
from core.logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = REPO_ROOT / "knowledge" / "reference"
INDEX_ROOT = REPO_ROOT / "data" / "chroma"

# Frontmatter 의 어떤 키를 Chroma metadata 에 흘릴지 화이트리스트.
# Chroma metadata 는 str/int/float/bool 만 허용. 리스트·dict 는 직렬화 필요.
_META_WHITELIST = (
    "source",
    "extracted_at",
    "subfolder",
    "title",
    "lang",
)


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


def _iter_reference_files(
    dept_dir: Path,
) -> Iterable[tuple[str, str, dict[str, Any], str]]:
    """Yield (rel_path, body, meta_dict, file_hash) for every reference markdown."""
    for p in sorted(dept_dir.rglob("*.md")):
        if p.name.lower() == "readme.md":
            continue
        rel = p.relative_to(dept_dir).as_posix()
        fhash = _file_hash(p)
        try:
            post = frontmatter.load(p)
        except Exception as e:  # noqa: BLE001
            log.warning("frontmatter_parse_failed", path=str(p), error=str(e))
            yield rel, p.read_text(encoding="utf-8"), {}, fhash
            continue
        meta_in = dict(post.metadata or {})
        meta_out: dict[str, Any] = {
            k: _coerce_meta_value(meta_in[k]) for k in _META_WHITELIST if k in meta_in
        }
        yield rel, post.content, meta_out, fhash


def _resolve_subfolder(rel_path: str, meta: dict[str, Any]) -> str:
    if "subfolder" in meta:
        return str(meta["subfolder"])
    if "/" in rel_path:
        return rel_path.split("/", 1)[0]
    return ""


def ingest(
    dept: str,
    *,
    force: bool = False,
    chunk_size: int = 800,
    overlap: int = 100,
) -> dict[str, Any]:
    """Index all reference markdown for one learning department into Chroma.

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
    for rel_path, body, meta, fhash in _iter_reference_files(dept_dir):
        body = body.strip()
        if not body:
            continue
        total_sources += 1

        # Skip if first chunk already indexed with the same file_hash. Cheap O(1)
        # lookup before paying for ~30 BGE-m3 embeddings per file (~70s on CPU).
        first_id = f"{rel_path}::0"
        if not force:
            try:
                existing = collection.get(ids=[first_id], include=["metadatas"])
                if existing.get("ids") and existing.get("metadatas"):
                    prev_hash = existing["metadatas"][0].get("file_hash")
                    if prev_hash == fhash:
                        skipped_unchanged += 1
                        continue
                    if prev_hash is None:
                        # Backfill: legacy index without file_hash. Patch every
                        # chunk's metadata (no re-embedding, ~30s for whole dept).
                        try:
                            chunk_set = collection.get(
                                where={"source_id": rel_path},
                                include=["metadatas"],
                            )
                            all_ids = chunk_set.get("ids", [])
                            metas_now = chunk_set.get("metadatas", [])
                            if all_ids:
                                patched = [
                                    {**(m or {}), "file_hash": fhash}
                                    for m in metas_now
                                ]
                                collection.update(ids=all_ids, metadatas=patched)
                                skipped_unchanged += 1
                                log.info(
                                    "file_hash_backfilled",
                                    source=rel_path,
                                    chunks=len(all_ids),
                                )
                                continue
                        except Exception as e:  # noqa: BLE001
                            log.warning(
                                "file_hash_backfill_failed",
                                source=rel_path,
                                error=str(e),
                            )
            except Exception as e:  # noqa: BLE001
                log.debug("hash_check_failed", source=rel_path, error=str(e))

        chunks = _chunk_text(body, chunk_size, overlap)
        if not chunks:
            continue
        ids = [f"{rel_path}::{i}" for i in range(len(chunks))]
        title = str(meta.get("title") or Path(rel_path).stem)
        subfolder = _resolve_subfolder(rel_path, meta)
        carry = {
            k: meta[k]
            for k in _META_WHITELIST
            if k in meta and k not in {"title", "subfolder"}
        }
        metadatas = [
            {
                "source_id": rel_path,
                "source_type": "markdown",
                "source_title": title,
                "source_subfolder": subfolder,
                "chunk_index": i,
                "dept": dept,
                "file_hash": fhash,
                **carry,
            }
            for i in range(len(chunks))
        ]
        try:
            collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
            total_chunks += len(chunks)
        except Exception as e:  # noqa: BLE001
            log.warning("chroma_upsert_failed", source=rel_path, error=str(e))

    return {
        "status": "ok",
        "dept": dept,
        "sources": total_sources,
        "chunks": total_chunks,
        "skipped_unchanged": skipped_unchanged,
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
