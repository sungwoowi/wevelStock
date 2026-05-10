---
date: 2026-05-11
topic: KNOWLEDGE-SYNC-001 Phase 2 M2 — sync run + DB run log + delta 인덱싱
status: completed
plan_file: C:\Users\HOME\.claude\plans\eager-honking-anchor.md
---

# 2026-05-11 · KNOWLEDGE-SYNC-001 Phase 2 M2 (sync + DB)

## 배경

Phase 2 M1 (retrieve/compose 카테고리 화이트리스트, 2026-05-10) 직후 같은 흐름으로 진입.
M2 = "어떤 자료가 언제 색인되었는지" DB 추적 + delta 인덱싱. M3 (watchdog + just) 의 전제.
종료 시 = 수동 sync 가능 (`uv run python -m core.knowledge.sync <dept>`) + DB 운영 로그.
핵심 판단: M2 만 끊어 1세션 마감 — small_milestones 정합. 이후 M3 (자동 트리거) 와 분리해 검증 가능 형태로 도착.

## 한 일

- `core/db/schema.sql` — `knowledge_index_runs` 테이블 (sync_id PK / dept / started_at / ended_at / status / files_{added,modified,deleted} / chunks_{upserted,deleted} / proposal_path / release_note_path / error) + `idx_kir_dept_started` 인덱스 + schema_version 4 추가
- `core/knowledge/sync.py` 신규 — `sync_dept(dept, *, since_run_id=None)` + `sync_all()`. ingest 의 `_iter_reference_files`/`_build_metadata`/`_chunk_text` 재사용. collection metadata 비교로 source_id → file_hash 맵 추출 → delta 분류 (added/modified/deleted) → upsert + hard delete (`where={"source_id": ...}`). modified 는 청크 수 감소 케이스 위해 pre-delete 후 upsert. `_allocate_sync_id` 가 분 단위 → 초 단위 → ms 단위 PK 충돌 fallback. CLI 진입점 `python -m core.knowledge.sync <dept>` (생략 시 8 dept 전체)
- `tests/test_knowledge_sync.py` 신규 — 6 케이스 (first sync 2 added / no-op 0 delta / modified 1 / deleted 1 + chunks_deleted / DB row 적재 / missing dept failed). FakeCollection in-memory dict (get/upsert/delete where source_id) + tmp DB redirect
- `docs/specs/KNOWLEDGE-SYNC-001-reference-canon-rag-sync.md` — Phase 2 M2 ✅ 완료 표시 + 검증 결과 인용

## 검증 결과

- ✅ pytest **128 passed** in 96s (122 → +6, 회귀 0)
- ✅ 첫 실 호출 (변경 없음): `uv run python -m core.knowledge.sync wealth_compounding` → status=success, files_{added,modified,deleted}=0, chunks_{upserted,deleted}=0 (M1 까지 인덱싱된 25 sources / 787 chunks 그대로)
- ✅ 4-단계 회로 검증 (사용자 요청, `knowledge/reference/wealth_compounding/macro_roadmap/m2-verification.md` 임시 자료):
  - Step 1 (add): files_added=1, chunks_upserted=1
  - Step 2 (modify): files_modified=1, chunks_upserted=1
  - Step 3 (delete): files_deleted=1, chunks_deleted=1, collection 에서 사라짐
  - Step 4 (DB 확인): `knowledge_index_runs` 4 row (어제 0 delta + 오늘 3 회로) 정확 적재
- ✅ 1 commit + push (`0aadf8a`, `9fac2e9..0aadf8a`)

## 의도적으로 안 한 것 (M3 보류)

- `core/knowledge/watcher.py` (watchdog 60s debounce) — M3
- `scripts/knowledge_sync.py` + `justfile` 4 명령 (sync/watch/status/rollback) — M3 (M2 검증은 `python -m core.knowledge.sync` 직접 실행)
- PROPOSAL / release note LLM 호출 — Phase 3 (M3 분석가 분화 SPEC 후)
- `since_run_id` 의 적극 활용 — collection metadata 단일 baseline (DB 는 운영 로그만). 인자만 받고 분기 후속

## 맥락 재진입 힌트

- **delta baseline = collection metadata, DB = 운영 로그**: SoT 분리. SPEC L488-489 그대로. since_run_id 인자는 인터페이스 호환성만 받고 미래 cross-run 분석에 reserve
- **modified 의 pre-delete + upsert**: 본문 길이 감소로 청크 수 5→3 케이스 시 stale id (3,4) 가 남으면 retrieve 가 빈 청크 hit. `where source_id` hard delete 후 upsert 로 안전. ingest.py 의 멱등 upsert 와 다른 점
- **PK 충돌 fallback (분→초→ms)**: 같은 분에 두 sync 가 떨어져도 안전. 동시 호출은 sqlite WAL 기준 race 가능성 있으나 현 운영 (수동 트리거) 에선 비현실
- **파일명 `_` prefix skip 은 ingest 정책**: 검증 자료는 `m2-verification.md` 처럼 일반 이름 필요. `_TEST.md` 는 ingest 가 무시
- **테스트 `_open_collection` monkeypatch**: 실 chromadb / BGE-m3 로드 회피. ingest_mod 와 sync_mod 양쪽의 `REFERENCE_ROOT` redirect 모두 필요 (sync 가 ingest 헬퍼 직접 import 했으므로 ingest_mod 도 함께 redirect)
- **실 호출 ~65s/회**: BGE-m3 모델 로드 + 787 chunks metadata scan. delta 0 케이스도 모델 로드는 회피 불가 (collection 핸들 생성 시 EF 매칭 필수)

## 세션 중 실 비용

- LLM 호출 0회 (M2 는 인덱싱 + DB, LLM 영역 외)
- 임베딩 호출 0회 (delta 시나리오에서 add 1·modify 1 = 청크 2개 임베딩, 무시 수준)

## 다음에 이어서 할 작업 (우선순위)

1. **KNOWLEDGE-SYNC-001 Phase 2 M3** (~1 세션) — `core/knowledge/watcher.py` (watchdog 60s debounce) + server lifecycle 등록 + `scripts/knowledge_sync.py` + `justfile` 4 명령 (sync/watch/status/rollback). 종료 시 = **사용자 reference push → 60s 자동 색인** = Phase 2 풀세트 동작점 (= 프로토타입 1차 동작점). M2 의 `sync_dept` 를 wrap 만 하면 됨.
2. **M3 분석가 분화 SPEC 작성** (3~5 세션) — 9 페르소나 8-섹션 portable + 자료 0 시드 5명 PROPOSAL 흐름 + 자료 있는 4명 + portable 검증. Phase 2 풀세트 후 본격 진입 (페르소나 `canon_categories` 가 자동 sync 흐름과 결합 동작 확인 가능 시점). 프로토타입 가동의 핵심.
3. **stock-analysis dept 첫 인덱싱 + 검증** (~1 세션) — 어댑터 5종 다 굴리는 첫 사례 (md/txt/pdf/xlsx/png). Phase 2 풀세트 도착 후 `python -m core.knowledge.sync stock-analysis` 또는 watchdog 자동 트리거. xlsx 어댑터 sheet 분리 여부 결정도 이 시점.

## 커밋 상태

- 1 commit: `0aadf8a feat(knowledge): KNOWLEDGE-SYNC-001 Phase 2 M2 — sync run + DB run log + delta 인덱싱` — push 완료 (`9fac2e9..0aadf8a`)
- wrap-up (이 파일 + RESUME + SESSIONS) 별도 commit 진행 예정
