---
date: 2026-05-10
topic: KNOWLEDGE-SYNC-001 Phase 2 M1 — retrieve/compose 카테고리 화이트리스트
status: completed
plan_file: C:\Users\HOME\.claude\plans\unified-prancing-galaxy.md
---

# 2026-05-10 · KNOWLEDGE-SYNC-001 Phase 2 M1 (canon_categories)

## 배경

Phase 1 (어댑터 5종 + ingest 카테고리 metadata) 직후 같은 날 3번째 세션. Phase 2 는 범위가
넓어 (retrieve/compose/DB/sync/watchdog/just) M1 만 끊어 1세션 마감하기로 결정 — small_milestones
원칙 정합. 핵심 판단: 분석가 manifest 의 `canon_categories: [<dept>/<category>, ...]` 한 줄로
RAG·canon 둘 다 카테고리 단위 화이트리스트가 켜지는 1차 동작점. M3 분석가 분화 SPEC 본격
진입 전 검증 가능한 형태로 도착.

## 한 일

- `core/knowledge/retrieve.py` — `retrieve(dept, query, *, categories=None, top_k=3)` 시그니처 확장 + ChromaDB `where={"category": {"$in": [...]}}` 조건부 전달 + 빈 리스트는 falsy fallback
- `core/knowledge/compose.py` — `load_shared_canon(canon_categories=None)` 시그니처 확장 (canon_dir.rglob 결과를 `<dept>/<category>` prefix 매칭으로 필터) + `build_pipeline_prompt(..., canon_categories=None)` 인자 추가 + RAG 분기에서 `rag_dept` 와 매칭되는 카테고리만 추출해 `retrieve(categories=...)` 전달
- `core/inference/run_analyst.py` — `AnalystSpec.canon_categories: list[str]` 필드 추가 + `load_analyst_spec` 의 manifest 로드 + `run_analyst` / `run_analyst_stream` 두 함수의 `build_pipeline_prompt` 호출에 `canon_categories=spec.canon_categories or None` 전달
- `agents/analysts/wealth_strategist/manifest.yaml` — 검증용 `canon_categories: [wealth_compounding/macro_roadmap]` 1줄 추가 (M3 SPEC 정식 정의 시 6 카테고리 전체로 복귀 예정)
- `tests/test_retrieve_categories.py` (신규, 4 케이스) — fake collection monkeypatch 로 ChromaDB 호출 캡쳐, where 절 검증 / categories=None / 빈 리스트 fallback / collection 부재
- `tests/test_compose_canon_categories.py` (신규, 7 케이스) — load_shared_canon 4 + build_pipeline_prompt 3 (rag_dept 매칭 카테고리만 retrieve 에 전달, legacy 무필터, dept 불일치 시 None fallback)
- `docs/specs/KNOWLEDGE-SYNC-001-reference-canon-rag-sync.md` — Phase 2 M1 ✅ 완료 표시 + 검증 결과 (canon 18,726 → 3,935 chars, 79% 감소) 인용

## 검증 결과

- ✅ pytest **122 passed** in 41s (111 → +11, 회귀 0)
- ✅ 통합 검증: `wealth_strategist` system blocks 의 canon block = `framework_manifesto.md` 만 (3,935 chars), 전체(18,726 chars) 대비 **79% 감소**. RAG block = macro_roadmap 카테고리 청크만 (`Vol1-빅웨이브생존전략` 등)
- ✅ 1 commit + push (`7158cd0`)

## 의도적으로 안 한 것 (M2 보류)

- DB `knowledge_index_runs` 테이블 + `core/knowledge/sync.py` (delta → 어댑터 → 인덱싱 → run log)
- `core/knowledge/watcher.py` (watchdog 60s debounce) + server lifecycle 등록
- `scripts/knowledge_sync.py` + `justfile` 4 명령 (sync/watch/status/rollback)
- `since_run_id` 델타 모드 (DB 의존)
- xlsx sheet 별 분리 인덱싱 / png vision 활성화 — 별도 백로그

## 맥락 재진입 힌트

- **canon_categories 형식 = `<dept>/<category>`**: 한 분석가가 여러 dept 의 카테고리를 받을 수 있도록 설계. compose 가 RAG retrieve 호출 시 `rag_dept` 와 일치하는 항목만 추출 → ChromaDB 는 dept 별 collection 이라 카테고리는 단일 dept 안에서만 의미
- **빈 리스트 = 무필터**: `canon_categories: []` 또는 `categories=[]` → falsy 체크로 legacy 동작 (dept 전체). 안전 fallback
- **AnalystSpec.canon_categories 빈 리스트 시 None 전달**: `spec.canon_categories or None` 패턴 — manifest 에 키 없거나 빈 리스트면 None 으로 변환해 build_pipeline_prompt 가 무필터 모드로
- **compose 는 두 곳 모두 적용**: (1) `[0] Investment Knowledge` 블록의 canon md 필터 + (2) `[4] Retrieved References` 의 RAG retrieve 카테고리 인자. 한 manifest 변경으로 두 경로 동시 좁혀짐
- **검증 카테고리 macro_roadmap 선택 이유**: asset_classes 처음 골랐다가 canon md 0개 (filter chars 0) 발견 → `knowledge/canon/wealth_compounding/` 의 정제본 2 파일은 macro_roadmap (framework_manifesto) + crisis_signals (survival_imperatives) 에 분포. 의미있는 비교 위해 macro_roadmap 으로 변경
- **테스트의 importlib 우회**: `core/knowledge/__init__.py` 의 `from .retrieve import retrieve` 가 패키지 attribute 를 함수로 가로채서 `import core.knowledge.retrieve as X` 가 모듈이 아닌 함수 반환. `importlib.import_module("core.knowledge.retrieve")` 로 명시 import 필요
- **manifest 검증값 임시성**: `wealth_strategist` 의 `canon_categories: [wealth_compounding/macro_roadmap]` 는 검증용. 자산전략가는 거시 자산배분 frame 이라 본래 6 카테고리 전체 대상. M3 분석가 분화 SPEC 에서 정식 정의

## 다음에 이어서 할 작업 (우선순위)

1. **KNOWLEDGE-SYNC-001 Phase 2 M2** (~1 세션) — `core/db/schema.py` (또는 `schema.sql`) 에 `knowledge_index_runs` 테이블 추가 (run_id / dept / started_at / finished_at / sources_indexed / chunks_added / since_run_id) + `core/knowledge/sync.py` 작성 (reference 디렉토리 walk → 파일 hash 비교 → 변경분만 어댑터 디스패치 → 인덱싱 → run log insert). 종료 시 = "어떤 자료가 언제 색인되었는지" DB 추적 가능. M3 (watchdog + just 명령) 의 전제.
2. **KNOWLEDGE-SYNC-001 Phase 2 M3** (~1 세션) — `core/knowledge/watcher.py` watchdog 60s debounce + server lifecycle 등록 + `scripts/knowledge_sync.py` + `justfile` 4 명령 (sync/watch/status/rollback). 종료 시 = **사용자 reference push → 60s 자동 색인** = Phase 2 풀세트 동작점.
3. **M3 분석가 분화 SPEC 작성** (3~5 세션) — 9 페르소나 8-섹션 portable + 자료 0 시드 5명 PROPOSAL 흐름. Phase 2 풀세트 후 본격 진입 (페르소나의 `canon_categories` 동작 검증 가능 시점).

## 커밋 상태

- 1 commit: `7158cd0 feat(knowledge): KNOWLEDGE-SYNC-001 Phase 2 M1 — retrieve/compose 카테고리 화이트리스트` — push 완료 (`66125df..7158cd0`)
- wrap-up (이 파일 + RESUME + SESSIONS) 별도 commit 진행 예정
