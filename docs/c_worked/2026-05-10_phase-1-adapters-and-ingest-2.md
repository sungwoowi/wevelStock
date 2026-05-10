---
date: 2026-05-10
topic: KNOWLEDGE-SYNC-001 Phase 1 — 어댑터 5종 + ingest 카테고리 metadata + wealth_compounding force re-index
status: completed
plan_file: C:\Users\HOME\.claude\plans\lovely-napping-pudding.md
---

# 2026-05-10 · KNOWLEDGE-SYNC-001 Phase 1 (어댑터 + ingest)

## 배경

Phase 0 (폴더 마이그레이션) 후속 코드 마일스톤. 자료 형식별 어댑터 (md/txt/pdf/xlsx/png) + ingest 카테고리 인식 + _category.yaml 메타 주입 = 분석가가 자기 카테고리 자료를 RAG 로 골라 받을 수 있는 1차 인프라. 핵심 판단: **chunk_id 포맷은 그대로** (rel_path 가 이미 `<category>/<file>` 형태) — metadata 에 `category` 필드만 추가해 backfill 단순화.

## 한 일

### Step A — 자료 카테고리 정렬 (.gitignore, commit X)
- `knowledge/reference/stock-analysis/technical_analysis/` 27 파일 → `fractal_wave/` 22 PDF + `log_chart/` 4 (xlsx 1, PNG 2, txt 1) + `technical_basics/` 1 txt
- `rag_docs/` 삭제 (log_chart 와 중복, 사용자 명시)

### Step B-1 — 어댑터 5종 (신규)
- `core/knowledge/adapters/_base.py` — `Adapter` Protocol + `ExtractedDocument` dataclass
- `core/knowledge/adapters/markdown.py` — `frontmatter.load()` wrap
- `core/knowledge/adapters/text.py` — UTF-8 read + char_count
- `core/knowledge/adapters/pdf.py` — `sync_knowledge.py` 의 `extract_pdf_text` + `_normalize_korean_spacing` 이관 (page_count / char_count)
- `core/knowledge/adapters/xlsx.py` — `openpyxl` 기반, sheet header + tab-delimited 단일 body
- `core/knowledge/adapters/png.py` — `enabled_by_default=False` (vision API 비용 보호, SPEC L507)
- `core/knowledge/adapters/__init__.py` — `ADAPTERS` 레지스트리 + `get_adapter(ext)`
- `pyproject.toml` — `openpyxl>=3.1` 추가

### Step B-2 — ingest.py 재작성
- `core/knowledge/ingest.py` (281줄, +199/-82) — `_iter_reference_files(dept)` 가 카테고리 폴더 직속 탐색 + `_` prefix 모든 path part skip + 어댑터 디스패치. `_load_category_meta(dept, category)` 가 canon 의 `_category.yaml` ground truth 로드. `_build_metadata` 가 frontmatter + extraction + category 3중 병합. 멱등 backfill 시 `(file_hash, category)` 동시 비교. `enabled_by_default=False` 어댑터는 silent skip (log.debug)

### Step C — 테스트 + 검증
- `tests/test_adapters.py` (10 tests) — 레지스트리 / md / text / pdf (blank page) / xlsx (2-sheet) / png (NotImplementedError) / `_normalize_korean_spacing` 휴리스틱
- `tests/test_ingest_categories.py` (7 tests) — `_load_category_meta` / `_iter_reference_files` (`_` prefix skip + adapter dispatch) / `_build_metadata` 3중 병합 / canon yaml 없을 때 fallback

## 검증 결과

- ✅ `_iter_reference_files('stock-analysis')` dry-run: 36 sources / 4 카테고리 / 5형식 (md 12 / pdf 21 / txt 2 / xlsx 1, PNG 2 silent skip)
- ✅ `ingest('wealth_compounding', force=True)` (75min, BGE-m3 CPU): 25 sources / 787 chunks / 6 카테고리 (asset_classes 30 / crisis_signals 224 / currency_pricing 150 / debt_rate_cycle 153 / macro_roadmap 38 / monetary_evolution 192)
- ✅ chunk metadata 18 keys: `category` / `category_title` / `category_description` / `when_to_inject` / `target_analysts` / `dept` / `file_hash` / `extracted_at` / `page_count` / `source_pdf` / ...
- ✅ retrieve smoke: "인플레이션 시대의 통화 가치" → top 3 (monetary_evolution × 2 + currency_pricing × 1, score 0.59~0.64), category 라벨 정확 노출
- ✅ pytest **111 passed** in 60s (기존 94 + 신규 17)
- ✅ 1 commit + push (`325fe19`)

## 의도적으로 안 한 것 (Phase 2 보류)

- `retrieve.py` 에 `categories: list[str]` 필터 인자 — Phase 2
- `compose.py` 의 `canon_categories` 기반 선택 주입 — Phase 2 (M3 페르소나 의존)
- `core/db/schema.sql` 의 `knowledge_index_runs` 테이블 — Phase 2
- `core/knowledge/sync.py` (delta → 어댑터 → 인덱싱 → run log) — Phase 2
- `core/knowledge/watcher.py` watchdog (60s debounce) — Phase 2
- `scripts/knowledge_sync.py` + justfile 4 명령 — Phase 2
- `since_run_id` 델타 모드 — Phase 2 (DB 의존)
- png 어댑터 vision 활성화 — 비용 가시화 후
- xlsx sheet 별 분리 인덱싱 — SPEC 528행 SLOT
- 다른 dept (principles / trading / stock-analysis) 재인덱싱 — Phase 2 sync 자동 또는 수동 force re-index

## 맥락 재진입 힌트

- **chunk_id 포맷 그대로**: rel_path = `<category>/<file>` 라 이미 카테고리 정보 포함. metadata 에 `category` 필드만 추가. 따라서 같은 자료의 폴더 위치만 안 바뀌면 멱등.
- **force 재인덱싱 트리거**: Phase 0 의 `git mv` 로 `lectures/` → `monetary_evolution/` 같은 path 변경 → 멱등 캐시 안 적중 → 새 인덱싱 진행되며 legacy stale chunks (lectures/...) 와 공존 위험. 옵션 B (force=True 1회) 로 collection drop + 깨끗 재인덱싱 (~75min).
- **png 정책**: `enabled_by_default=False` → ingest 가 silent skip (log.debug). NotImplementedError 분기 안 탐. enable 시 flag 만 True 로.
- **로컬 vs 클라우드 전략**: 로컬에서 끝까지 + 어댑터 패턴 추상화 + 24/7 봇 필요 시점에 작은 VM 1대로 통째 이전 (DB 분리 X). Supabase·Pinecone 무료 티어로 1~3년 운영 가능 — 마이그레이션 비용 거의 0.

## 다음에 이어서 할 작업 (우선순위)

1. **KNOWLEDGE-SYNC-001 Phase 2** (2~3 세션) — `retrieve.py` 카테고리 필터 + `compose.py` `canon_categories` 주입 + DB `knowledge_index_runs` 테이블 + `core/knowledge/sync.py` (delta → 어댑터 → run log) + `core/knowledge/watcher.py` (watchdog 60s) + `scripts/knowledge_sync.py` + justfile 4 명령. 종료 시 = **사용자 reference push → 60s 자동 색인 + 분석가 페르소나의 `canon_categories` 동작** = 프로토타입 1차 동작점.
2. **M3 분석가 분화 SPEC 작성** (3~5 세션) — 9 페르소나 (8-섹션 portable: Identity / Domain Frame / Inputs / Outputs / Reasoning Doctrine / Knowledge Categories / Anti-patterns / Cross-Agent Boundaries) + identity seed PROPOSAL 흐름 (자료 0 시드 5명: 시장상태 / 종목선정 / 매매저널 / 수급 / 뉴스). Phase 2 완료 후 본격 진입.
3. **stock-analysis dept 재인덱싱 + 검증** (~1 세션) — 정리 완료된 `fractal_wave/` (md 3 + pdf 22) + `log_chart/` (md 7 + xlsx 1 + txt 1) + `technical_basics/` (md 1 + txt 1) + `fundamental_analysis/` (md 1) `force=True` 로 인덱싱. "프랙탈 파동 매수 타점" / "로그차트 목표가 계산" 같은 한국어 쿼리로 카테고리 라벨 + score 검증. wealth_compounding 패턴 그대로 복사 (~75min/dept).

## 커밋 상태

- 1 commit: `325fe19 feat(knowledge): KNOWLEDGE-SYNC-001 Phase 1 — 어댑터 5종 + ingest 카테고리 metadata` — push 완료 (`64d0f85..325fe19`)
- wrap-up (이 파일 + RESUME + SESSIONS + project_state) 별도 commit 진행 예정
