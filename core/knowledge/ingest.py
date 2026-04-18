"""Knowledge ingestion — PDF/MD/YouTube → chunks → Chroma.

Usage:
    uv run python -m scripts.knowledge ingest <team_id>
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from core.logging import get_logger
from core.registry import get_team

log = get_logger(__name__)


def _extract_text_from_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        log.warning("pypdf_not_installed")
        return ""
    try:
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:  # noqa: BLE001
        log.warning("pdf_extract_failed", path=str(path), error=str(e))
        return ""


def _extract_youtube_transcript(url: str) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore[import-not-found]
    except ImportError:
        log.warning("youtube_transcript_api_not_installed")
        return ""
    # Extract video ID (simple, assumes youtube.com/watch?v=XYZ or youtu.be/XYZ)
    video_id = ""
    if "watch?v=" in url:
        video_id = url.split("watch?v=", 1)[1].split("&", 1)[0]
    elif "youtu.be/" in url:
        video_id = url.rsplit("/", 1)[-1].split("?", 1)[0]
    if not video_id:
        return ""
    try:
        segs = YouTubeTranscriptApi.get_transcript(video_id, languages=["ko", "en"])
        return "\n".join(s["text"] for s in segs)
    except Exception as e:  # noqa: BLE001
        log.warning("youtube_fetch_failed", url=url, error=str(e))
        return ""


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Simple character-based chunking. Good enough for initial scaffolding."""
    if not text:
        return []
    chunks: list[str] = []
    i = 0
    step = max(1, chunk_size - overlap)
    while i < len(text):
        chunks.append(text[i : i + chunk_size])
        i += step
    return chunks


def _iter_sources(sources_dir: Path) -> Iterable[tuple[str, str, str]]:
    """Yield (source_id, source_type, text) for every file in sources/."""
    if not sources_dir.exists():
        return
    for p in sources_dir.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(sources_dir))
        if p.suffix.lower() in {".md", ".txt"}:
            yield (rel, "markdown" if p.suffix == ".md" else "text", p.read_text(encoding="utf-8"))
        elif p.suffix.lower() == ".pdf":
            yield (rel, "pdf", _extract_text_from_pdf(p))
        elif p.name == "urls.txt":
            for url in p.read_text(encoding="utf-8").splitlines():
                url = url.strip()
                if not url or url.startswith("#"):
                    continue
                yield (url, "youtube", _extract_youtube_transcript(url))


async def ingest_team(team_id: str, chunk_size: int = 800, overlap: int = 100) -> dict:
    """Re-index all sources for a team. Returns stats."""
    team = get_team(team_id)
    if team is None or team.path is None:
        raise ValueError(f"Team not found: {team_id}")

    sources_dir = team.path / "knowledge" / "sources"
    index_dir = team.path / "knowledge" / "vector-index"
    index_dir.mkdir(parents=True, exist_ok=True)

    try:
        import chromadb  # type: ignore[import-not-found]
    except ImportError:
        log.warning("chroma_not_installed_skip_ingest")
        return {"status": "skipped", "reason": "chromadb not installed"}

    client = chromadb.PersistentClient(path=str(index_dir))
    # Fresh collection each time — simple & safe for initial scaffold
    try:
        client.delete_collection(name=team_id)
    except Exception:
        pass
    collection = client.create_collection(name=team_id)

    total_chunks = 0
    total_sources = 0
    for source_id, source_type, text in _iter_sources(sources_dir):
        if not text.strip():
            continue
        total_sources += 1
        chunks = _chunk_text(text, chunk_size, overlap)
        if not chunks:
            continue
        ids = [f"{source_id}::{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "source_id": source_id,
                "source_type": source_type,
                "source_title": Path(source_id).stem if source_type != "youtube" else source_id,
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]
        try:
            collection.add(ids=ids, documents=chunks, metadatas=metadatas)
            total_chunks += len(chunks)
        except Exception as e:  # noqa: BLE001
            log.warning("chroma_add_failed", source=source_id, error=str(e))

    return {
        "status": "ok",
        "team": team_id,
        "sources": total_sources,
        "chunks": total_chunks,
        "index_path": str(index_dir),
    }
