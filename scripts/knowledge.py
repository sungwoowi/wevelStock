"""Knowledge RAG CLI — ingest / browse (5-Layer dept-based, INFRA-RAG-001).

Usage:
    just knowledge-ingest <dept>            # 멱등 인덱싱
    just knowledge-ingest <dept> --force    # 컬렉션 재생성
    just knowledge-browse <dept> "<query>"  # top-5 단편 출력
"""
from __future__ import annotations

import argparse
import asyncio
import sys

# Windows PowerShell default cp949 raises on Korean/emoji chunks. Force UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

from core.knowledge.ingest import ingest  # noqa: E402
from core.knowledge.retrieve import retrieve  # noqa: E402


async def _browse(dept: str, query: str, top_k: int) -> None:
    results = await retrieve(dept, query, top_k=top_k)
    if not results:
        print("(no results — index empty, dept missing, or chroma unavailable)")
        return
    for i, r in enumerate(results, 1):
        title = r.chunk.source_title or r.chunk.source_id
        print(f"\n[{i}] score={r.score:.3f}  source={title}")
        print(f"     subfolder={r.chunk.metadata.get('source_subfolder', '')}")
        print(r.chunk.text[:300].replace("\n", " "))


def main() -> None:
    parser = argparse.ArgumentParser(description="Knowledge RAG CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_in = sub.add_parser("ingest", help="index a learning department")
    p_in.add_argument("dept")
    p_in.add_argument("--force", action="store_true")
    p_in.add_argument("--chunk-size", type=int, default=800)
    p_in.add_argument("--overlap", type=int, default=100)

    p_br = sub.add_parser("browse", help="query a department's index")
    p_br.add_argument("dept")
    p_br.add_argument("query")
    p_br.add_argument("--top-k", type=int, default=5)

    args = parser.parse_args()

    if args.cmd == "ingest":
        result = ingest(
            args.dept,
            force=args.force,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
        )
        print(result)
    elif args.cmd == "browse":
        asyncio.run(_browse(args.dept, args.query, args.top_k))


if __name__ == "__main__":
    main()
