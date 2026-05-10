---
date: 2026-05-10
topic: KNOWLEDGE-SYNC-001 SPEC + 5-Layer 분석가 9명 분화 + agent 아키텍처 영구화 + Phase 0 마이그레이션
status: completed
plan_file:
---

# 2026-05-10 · KNOWLEDGE-SYNC-001 + 분석가 9명 + Phase 0

## 배경

사용자가 `knowledge/reference/**` 자료 추가·수정 시 RAG 인덱싱 + canon 승격이 자동으로 반영되도록 자동화 필요성 제기. `/spec-interview` 진행 중 5-Layer 모델 자체가 진화 (분석가 5 → 9). prism-insight 오픈소스 비교 분석으로 Trading Journal Agent 패턴 차용. agent 통신 패턴 (분석가 간 직접 호출 X / DB read 절충) 본질을 영구 문서화. Phase 0 폴더 마이그레이션 즉시 실행.

## 한 일

### SPEC + 핵심 문서
- `docs/specs/KNOWLEDGE-SYNC-001-reference-canon-rag-sync.md` (신설, draft) — reference 델타 인덱싱 + canon 승격 PROPOSAL + release note + 카테고리 단위 인식 + 카테고리 라우팅 정책 + 자료 형식 5종 어댑터 (md/txt/pdf/xlsx/png) + 스킬 2개 (`/knowledge-sync`, `/knowledge-review`)
- `docs/AGENT-ARCHITECTURE.md` (신설) — hierarchical orchestration + DB-mediated 약한 협업. 두 패턴 비교 10 측면 + 도메인 본질 (시점 일관성·frame 응집)
- `CLAUDE.md` — 학습부 → 지식부, 매매코치 → 트레이더, dept 5→9 (5-Layer 표 + 본문), 절대 원칙 1번에 AGENT-ARCHITECTURE 링크 추가

### Phase 0 폴더 마이그레이션 (별도 commit)
- 9 지식부 폴더 (4 신설: market_macro / stock_selection / trading_journal / flow_analysis 모두 자료 0 시드, mechanics → trading rename)
- 36 카테고리 폴더 + 36 `_category.yaml` 작성
- canon git mv 7 (principles 3 + trading 1 failure_lessons + operational_safeguards 이동 + wealth_compounding 2)
- reference mv/git mv 43 (principles 3 + stock-analysis 12 + wealth_compounding 28)
- 삭제: `canon/stock-analysis/sector-insights.md` (초안) + 박종훈_기자 ebooks 2 (소장 버전 중복)
- 빈 폴더 정리 (technical_analysis 트리 / lectures / ebooks / materials)

### 메모리 갱신
- `agent_architecture_pattern.md` (신설) — hierarchical + DB read 패턴
- `project_5layer_model.md` (rewrite) — 지식부 9 / 분석가 9 / 분화 이력
- `project_knowledge_workflow.md` (rewrite) — KNOWLEDGE-SYNC-001 scope 정정 (canon = 자료 정수만, 페르소나는 M3)
- `project_prism_insight_borrowing.md` (신설) — Trading Journal 차용 + Memory Compression / Quality Eval / MCP 백로그
- `project_m3_analyst_differentiation_backlog.md` (신설) — 9 분석가 페르소나 작성 SPEC 백로그, 8-섹션 양식 portable
- `MEMORY.md` 인덱스 갱신 (3 줄 추가, 1 줄 갱신)

### idea_memo (사용자 개인 백로그)
- `idea_memo/prism-insight-비교차용.md` (사용자 작성)
- `idea_memo/개발방법론-회고-a-to-z.md` (사용자 작성)

## 검증 결과

- ✅ `find knowledge/canon -name "_category.yaml" | wc -l` → 36
- ✅ `git status --short` 검증 — 모든 git mv 정상, 빈 폴더 정리 완료
- ✅ 2 commit 분리 + push (`git log --oneline -3`):
  - `908770d` Phase A (5-Layer 9 + KNOWLEDGE-SYNC-001 SPEC + agent 아키텍처)
  - `a8f9c2c` Phase 0 (9 지식부 × 36 카테고리)

## 의도적으로 안 한 것

- **Phase 1~2 코드 구현** — 어댑터 5종 + ingest/retrieve/compose 카테고리 확장 + DB 테이블 + watchdog. 다음 세션
- **M3 분석가 페르소나 9 작성** — 별도 SPEC 백로그
- **`technical_analysis/1.프렉탈파동_basic/` 20+ PDF 마이그레이션** — 사용자가 추가한 자료, 이번 인터뷰에 인지 못함. 다음 세션 첫 작업
- **`technical_analysis/4.로그차트_advanced/` PNG/xlsx/txt** — 같은 이유
- **`주식 기술적 분석 총람.txt`** — 같은 이유
- **자료 0 학습부의 doctrine seed 작성** — 페르소나 영역, M3 SPEC

## 다음에 이어서 할 작업 (우선순위)

1. **추가 자료 마이그레이션** — `reference/stock-analysis/technical_analysis/` 안 미처리 자료를 적절한 카테고리로 이동. 1.프렉탈파동_basic 20+ PDF → fractal_wave/ 보강, 4.로그차트_advanced PNG/xlsx/txt → log_chart/, 주식 기술적 분석 총람.txt → technical_basics/ 또는 별 카테고리. ~30min
2. **Phase 1~2 구현 시작** — `core/knowledge/adapters/{markdown,text,pdf,xlsx,png}.py` 5종 + `ingest.py` 카테고리 metadata 채움 + 델타 모드 + `retrieve.py` 카테고리 필터 + `compose.py` `canon_categories` 기반 선택 주입 + `core/db/schema.py` `knowledge_index_runs` 테이블 + `core/knowledge/sync.py` (delta 발견 → 어댑터 → 인덱싱 → run log) + watchdog. 2~4 세션
3. **M3 분석가 분화 SPEC 작성** — 9 분석가 페르소나 양식 (8-섹션 portable: Identity / Domain Frame / Inputs / Outputs / Reasoning Doctrine / Knowledge Categories / Anti-patterns / Cross-Agent Boundaries) + identity seed PROPOSAL 흐름 (자료 0 분석가 5명 시드). KNOWLEDGE-SYNC-001 Phase 1~2 완료 후 본격 진입. 3~5 세션

## 맥락 재진입 힌트

- KNOWLEDGE-SYNC-001 SPEC 의 Phase 1~2 종료 = "사용자가 reference push → 60s 자동 인덱싱 + `just knowledge-browse <dept> "<query>"` 추론 검증" 가능 시점. 프로토타입 1차 동작 = M3 페르소나 작성 후 분석가 production 호출 가능
- 9 분석가 cohesion 우려는 운영 규율 (페르소나의 anti-patterns + cross-agent boundaries + Layer 3 통합 agent + StandardOutput 표준 + DB read 패턴) 로 해소. 본질적 무리 X (prism-insight 13+ 검증)
- canon vs 페르소나 분리: canon = 자료 정수 (자료에서 추출한 한 줄), 페르소나 = agent identity·doctrine·boundaries (자료 0 분석가도 페르소나만으로 추론 시작)
- prism-insight 차용 4 (Trading Journal 직접 / Memory Compression 후속 / Quality Eval 후속 / MCP 패턴 후속) 중 Trading Journal 만 본 세션 적용

## 커밋 상태

이번 세션 3 commit + push 완료 (정확한 hash 는 `git log` 로):
- Phase A: 5-Layer 9 + KNOWLEDGE-SYNC-001 SPEC + agent 아키텍처 영구화
- Phase 0: 카테고리 폴더 마이그레이션 (9 지식부 × 36 카테고리, canon 만 push)
- wrap-up: c_worked + RESUME + SESSIONS

**knowledge/reference/ .gitignore 처리**:
- 사용자 자료 (PDF 다수, 최대 244MB, GitHub 100MB 제한 위반) 는 repo 외부 보관
- 사용자 의견 (2026-05-10): Google Drive 등 CDN 에 올린 후 받아와서 작업. 후속 SPEC 백로그
- canon 정수만 push, reference 원본은 사용자 로컬에서 RAG 인덱싱 (`data/chroma/` 도 .gitignore)

**최초 push 시도 시 차단** (Phase 0 의 1.프렉탈파동_basic/ PDF 6 파일 100MB 초과) → reset --soft + .gitignore 추가 + reference 제거 + 재 commit 으로 해소.
