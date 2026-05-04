"""sync_knowledge.py — 외부 source(PDF 등) → knowledge/reference/<learning_dept>/ 로 멱등 추출.

config/knowledge_sources.yaml 의 학습부별 source 폴더를 스캔하여
PDF 를 텍스트로 추출하고 frontmatter 메타와 함께 reference/ 에 저장.

핵심 동작:
  - 멱등: 같은 slug 의 .md 가 이미 있으면 skip (재실행 안전)
  - slugify: 한국어 보존, 이모지·괄호 제거, 공백·하이픈 → underscore
  - frontmatter: source_pdf 경로 + 추출 시각 + char/page count

사용:
  uv run python -m scripts.sync_knowledge <learning_dept_id>
  예: uv run python -m scripts.sync_knowledge wealth_compounding
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import frontmatter
import yaml
from pypdf import PdfReader

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "knowledge_sources.yaml"
REFERENCE_ROOT = REPO_ROOT / "knowledge" / "reference"


def slugify(stem: str) -> str:
    """한국어 보존, 이모지·괄호·특수기호 제거, 공백·하이픈 → underscore."""
    # 괄호 안 내용 제거: [정규 강의 VOD], (정리본) 등
    stem = re.sub(r"[\[\(].*?[\]\)]", " ", stem)
    # "Part 1" → "part1" 통일
    stem = re.sub(r"[Pp]art\s*(\d+)", r"part\1", stem)
    # 한국어 + 영숫자 + 공백·하이픈만 남기고 나머지(이모지·특수기호) 제거
    stem = re.sub(r"[^\w\s가-힣ㄱ-ㅎㅏ-ㅣ\d-]", " ", stem)
    # 공백·하이픈을 underscore 로
    stem = re.sub(r"[-\s]+", "_", stem)
    # 다중 underscore 정리
    stem = re.sub(r"_+", "_", stem).strip("_")
    return stem


def normalize_korean_spacing(text: str) -> str:
    """디자인 PDF (글자 사이 single space) 휴리스틱 정규화.

    pypdf 가 디자인된 PDF (글자마다 별도 textbox) 를 글자 사이 공백으로
    추출하는 경우가 있다. "돈 이  휴 지" → "돈이 휴지" 로 복원.

    휴리스틱: 한글 single-space 패턴이 한글 multi-space 패턴의 2배 이상
    + 100개 이상이면 디자인 PDF 로 판정. 일반 강의 PDF 는 영향 없음.
    """
    single_space_count = len(re.findall(r"(?<=[가-힣]) (?=[가-힣])", text))
    multi_space_count = len(re.findall(r"(?<=[가-힣])  +(?=[가-힣])", text))
    if single_space_count > max(multi_space_count * 2, 100):
        # 한글 사이 single space 제거 (글자 합치기)
        text = re.sub(r"(?<=[가-힣]) (?=[가-힣])", "", text)
        # 공백 정규화 (다중 → 단일)
        text = re.sub(r"[ \t]+", " ", text)
    return text


def extract_pdf_text(pdf_path: Path) -> tuple[str, int]:
    """PDF → text. (텍스트, 페이지 수) 반환. 페이지 단위 추출 실패는 skip."""
    reader = PdfReader(str(pdf_path))
    parts: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                parts.append(text)
        except Exception:  # noqa: BLE001
            continue
    raw = "\n\n".join(parts)
    return normalize_korean_spacing(raw), len(reader.pages)


def resolve_subfolder(rel_parent: str, mapping: dict[str, str], default: str) -> str:
    """원본 sub 폴더 → reference 안에서의 sub 폴더명. 매핑 없으면 원본 또는 default."""
    if rel_parent in mapping:
        return mapping[rel_parent]
    if rel_parent == "":
        return default
    return rel_parent


def sync_learning_dept(dept_id: str, dept_cfg: dict) -> dict:
    source_root = Path(dept_cfg["source"])
    if not source_root.exists():
        raise SystemExit(f"source not found: {source_root}")

    subfolder_map: dict[str, str] = dept_cfg.get("subfolder_map", {})
    target_root = REFERENCE_ROOT / dept_id
    target_root.mkdir(parents=True, exist_ok=True)

    extracted = 0
    skipped = 0
    total_chars = 0
    failed: list[tuple[str, str]] = []
    extracted_files: list[tuple[str, int]] = []

    pdfs = sorted(source_root.rglob("*.pdf"))
    print(f"  scanning {source_root}")
    print(f"  found {len(pdfs)} PDF(s)")

    for pdf_path in pdfs:
        rel_parent = pdf_path.parent.relative_to(source_root).as_posix()
        if rel_parent == ".":
            rel_parent = ""
        sub = resolve_subfolder(rel_parent, subfolder_map, dept_id)

        slug = slugify(pdf_path.stem)
        target = target_root / sub / f"{slug}.md"

        if target.exists():
            skipped += 1
            continue

        try:
            text, page_count = extract_pdf_text(pdf_path)
        except Exception as e:  # noqa: BLE001
            failed.append((pdf_path.name, str(e)))
            continue

        post = frontmatter.Post(content=text)
        post["learning_dept"] = dept_id
        post["original_filename"] = pdf_path.name
        post["source_pdf"] = str(pdf_path).replace("\\", "/")
        post["extracted_at"] = datetime.now(timezone.utc).isoformat()
        post["page_count"] = page_count
        post["char_count"] = len(text)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(frontmatter.dumps(post), encoding="utf-8")
        extracted += 1
        total_chars += len(text)
        extracted_files.append((target.relative_to(REFERENCE_ROOT).as_posix(), len(text)))

    return {
        "extracted": extracted,
        "skipped": skipped,
        "total_chars": total_chars,
        "estimated_tokens": total_chars,  # 한국어 1 char ≈ 1 token (대략)
        "failed": failed,
        "extracted_files": extracted_files,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m scripts.sync_knowledge <learning_dept_id>")
        print(f"  config: {CONFIG_PATH.relative_to(REPO_ROOT)}")
        return 2

    dept_id = argv[1]
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    dept_cfg = config.get("learning_depts", {}).get(dept_id)
    if not dept_cfg:
        print(f"learning_dept '{dept_id}' not found in {CONFIG_PATH.name}")
        print(f"available: {list(config.get('learning_depts', {}).keys())}")
        return 2

    print(f"=== sync_knowledge: {dept_id} ===")
    result = sync_learning_dept(dept_id, dept_cfg)
    print()
    print(f"  extracted:   {result['extracted']}")
    print(f"  skipped:     {result['skipped']}  (already in reference/)")
    print(f"  total chars: {result['total_chars']:,}")
    print(f"  est. tokens: ~{result['estimated_tokens']:,}  (Korean 1 char ~= 1 token)")
    if result["failed"]:
        print(f"  failed: {len(result['failed'])}")
        for name, err in result["failed"]:
            print(f"    - {name}: {err[:120]}")

    if result["extracted_files"]:
        print()
        print("  extracted files (top 10 by size):")
        for path, chars in sorted(result["extracted_files"], key=lambda x: -x[1])[:10]:
            print(f"    {chars:>8,} chars  {path}")

    return 0 if not result["failed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
