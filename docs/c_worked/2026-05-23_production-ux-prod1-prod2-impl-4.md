---
date: 2026-05-23
topic: PRODUCTION-UX-001 PROD-UX-1+2 풀세트 + 분석가 협동 위계 정합 (sub-task + 시나리오 축약, 같은 날 4번째 세션)
status: completed
plan_file: C:\Users\HOME\.claude\plans\compiled-booping-blum.md
---

# 2026-05-23 · PRODUCTION-UX-001 PROD-UX-1+2 구현 + 사이클 3 사용자 진단 해소

## 배경

같은 날 직전 세션 (`2026-05-23_production-ux-spec-interview-3.md`) 산출 = SPEC frozen `status: approved`. 본 세션 = **PROD-UX-1 → PROD-UX-2 풀세트 구현 + 사용자 시연 후 본질 진단 발견 (분석가 회피 + 위계 부재) → 사이클 3 (sub-task decomposition + 시나리오별 축약) 추가**. 사용자 자율 권한 위임 (`소스코드 권한 묻지 말고 다 완성`) → 4 commit 한 호흡.

## 한 일

### Cleanup (`eec126a`)
- `docs/specs/WAVE-ALPHA-001-wave-alpha.md` line 6: `status: frozen` → `status: implemented` (enum 정합)

### PROD-UX-1 (`af1568c`) — Intent Classifier + Routing + 기본 채팅
- `core/intent/{__init__, classifier, cache, router, system_prompt.md}` 신규 — 2-Stage 하이브리드 (결정론 keyword + LLM Flash-lite + 30일 캐시)
- `config/scenario_keywords.yaml` — 시나리오 1~11 Stage 1 룰 (hot reload)
- `core/llm/tiers.py` + `core/config/schema.py` LLMTiers/LLMAreas — 3 계층 (FAST/BALANCED/DEEP) Gemini-Anthropic 1:1 mirror
- `config/runtime.yaml` tiers/areas 신규
- `server/api/production_chat.py` — `POST /api/chat/production` + `/stream` (SSE)
- `webapp/src/app/production-chat/page.tsx` 신규 라우트 + 메인 페이지 카드 링크
- `tests/intent/{test_classifier_golden.py, test_router.py}` 신규 — 45 골든 + 12 router = 31 신규

### PROD-UX-2 (`d30cafd`) — 옵션 A 협동 + 자연어 포맷터 + 근거 토글
- `core/intent/formatter.py` 신규 (~250 LOC) — FAST tier LLM 1콜로 raw → 1~3줄 결론 + 3요소 근거
- `config/label_dictionary.yaml` 신규 — 시드 14종 (α / F-Score / S-Score / verdict / cited 등)
- `core/intent/router.py` — `_prefetch_analysts_for_tracks` 추가 (reads_analysts 합집합 asyncio.gather 동시 호출)
- `core/strategist/run_strategist.py` — `prefetched_analyst_outputs` 인자 + `render_prefetched_analyst_outputs` 블록 (DB read 우회)
- `server/api/production_chat.py` — formatter 통합 + SSE `type=formatted` 이벤트 + agent text buffer
- `webapp/src/app/production-chat/page.tsx` — FormattedAnswerCard default 노출 + 점진 갱신
- `webapp/src/app/production-chat/components/{EvidenceToggle, IntentFallback}.tsx` 신규
- `tests/intent/test_formatter.py` 신규 (8건) + test_router.py prefetch assertion 갱신

### 사이클 3 (`6de001c`) — 사용자 진단 해소 (sub-task + 시나리오 축약)
사용자 시연 결과: 분석가 6명이 "내 영역 아님" 회피 → 전략가 raw 빵꾸 → wait 도미노. 진단 = **사용자 발화 forward** 가 아니라 **분야별 sub-task decomposition** 필요.

- `config/analyst_subtasks.yaml` 신규 — 9 분석가 prompt template + `common_directives` (회피 차단 강제 룰)
- `config/scenario_analyst_routing.yaml` 신규 — 시나리오 1~10 별 분석가 축약 매핑 (예: 시나리오 1 = 3명, 7 = 2명)
- `core/intent/router.py` — `_resolve_analyst_ids_for_scenario` + `_build_subtask_prompt` helper. `_prefetch_analysts_for_tracks` 가 classification 인자 받음 + 마지막 user message 를 sub-task prompt 로 치환
- `tests/intent/test_router.py` — `TestSubtaskDecomposition` (4건) + `TestScenarioRouting` (5건) 신규

### 본질 통찰 (사용자 + prism-insight 비교)
- prism-insight 패턴 = **Orchestrator pass-through** (raw text 직접 다음 agent prompt 주입) + Sequential — wevelStock 의 asyncio.gather 병렬이 한 단계 우월
- "LLM 하나 + 작은 페르소나" vs "분리" = 분리 유지 + sub-task 분해가 정답. canon RAG 분리·깊이 보존
- **데이터 인프라 빈공간** = F-Score 4축 / S-Score / buy_score / T-Score input collector 부재. prompt + 위계만으론 "unknown 명시 + 부분 분석" 까지만. **별도 SPEC `INFRA-SCORE-INPUTS-001` 필요** (~5 세션)

## 검증 결과

- ✅ pytest **542 → 590** (+48: PROD-UX-1 31 + PROD-UX-2 8 + 사이클 3 9, 회귀 0)
- ✅ `uv run python scripts/validate.py` 0 errors
- ✅ `webapp tsc --noEmit` 0 errors
- ✅ 4 commits 모두 push 완료 (`eec126a` → `af1568c` → `d30cafd` → `6de001c`)
- ⚠️ 실 서버 시연 시 분석가 raw 발행 품질은 sub-task 적용 후 즉시 향상 예상이나 데이터 인프라 부재로 점수 실 발행은 여전히 unknown

## 의도적으로 안 한 것

- **PROD-UX-3 (사용자 인수 시연)** — 사용자가 외출 + 사이클 3 본질 진단 후 다음 세션 보완점 제보 예정으로 보류
- **INFRA-SCORE-INPUTS-001 SPEC 신설** — 별도 사이클 (~5 세션), 본 사이클 scope 초과
- **모든 frozen SPEC `status` enum 일괄 정정** — WAVE-ALPHA-001 만 정정. 나머지 cleanup 은 별도 작업

## 다음에 이어서 할 작업 (우선순위)

### 1. 사용자 보완점 제보 대응 (다음 세션 시작 후 인터뷰) ✨
- **왜**: 사용자가 명시 "보완점 이 많이 보이는데 이건 다른 세션에서 제보"
- 사이클 3 sub-task + 축약 적용 후 실 시연에서 발견된 추가 회피·환각·부자연 케이스 정리 → 핀포인트 정정 또는 sub-task template 강화
- 범위 = 사용자 발견 N 건 항목별 (각 분석가 manifest response_rules 또는 sub-task template 정정)
- 예상 산출 = `config/analyst_subtasks.yaml` 정정 + 일부 분석가 manifest response_rules 강화 + 회귀 테스트 골든 케이스 추가

### 2. INFRA-SCORE-INPUTS-001 SPEC 신설 (~5 세션 별도 사이클)
- **왜**: 데이터 인프라 빈공간 본질 해소. F-Score 4축 / S-Score / buy_score / T-Score 의 input collector 부재로 점수 실 발행 불가
- 범위 = `/spec-interview INFRA-SCORE-INPUTS-001` 5 라운드 면담 → SPEC frozen → 영역별 1 collector 씩 점진 구현 (테마-주체 매칭 / 수급망 일치도 / CAN SLIM 7축 / 실시간 호가)
- 예상 산출 = `docs/specs/INFRA-SCORE-INPUTS-001-score-inputs.md` + `collectors/{flow_inputs, picker_inputs, fundamentals_qoq, trader_inputs}.py` × 5 세션

### 3. LLM-TIER-MIGRATION-001 SPEC 신설 (~0.5 세션 microcycle)
- **왜**: anchors.py Stage 2 + 분석가 9 + 전략가 영역별 LLM 3계층 점진 마이그레이션. PROD-UX-1 적용 범위 D 점진 결단의 후속
- 범위 = 영역별 1 PR 점진 (`anchors_stage2: balanced → fast` 등) + 회귀 검증
- 예상 산출 = SPEC + 영역별 commit 4~5건

(추가 백로그: PROD-UX-3 (사용자 인수 시연 + 발화 로그 일일 리포트) / WAVE-ALPHA SLOT S1·S2·S3·S4 후속 SPEC / Layer 4 계좌관리자 (M5) / Layer 5 회고분석가 (M4) / `INFRA-TICKER-RESOLVER-001` (30 종목 한계 해소) / `NEWS-SOURCE-001`)

## 맥락 재진입 힌트

- **사용자 자율 권한 명시 정합**: 본 세션에서 `소스코드 수정 권한 묻지 말고 다 완성` 강조 → memory `feedback_session_autonomy_signals.md` 정합. 본질·architecture 결정만 묻기.
- **prism-insight 차용 패턴 확정**: Orchestrator pass-through (raw 직접 주입) + wevelStock 의 병렬. 향후 multi-agent orchestration 에서 동일 패턴 default. 사용자 본인 직관 ("LLM 협동해야") 와 1:1 정합.
- **sub-task decomposition 본질**: 분석가 분리의 가치는 canon RAG 분리·깊이. 사용자 발화 forward 가 회피 원인 = 라우터가 분야별 prompt 로 분해해야. 향후 모든 분석가 호출 패턴의 기본.
- **데이터 인프라 빈공간 권위**: 본 사이클은 prompt + 위계만 해소. 점수 실 발행은 별도 SPEC 영역. 분석가들이 "unknown 명시 + 부분 분석" 발행하는지가 본 사이클 인수 기준.

## 커밋 상태

- 본 세션 4 commits + push 완료:
  - `eec126a` chore: WAVE-ALPHA-001 status enum cleanup
  - `af1568c` feat: PROD-UX-1 = Intent Classifier + Routing
  - `d30cafd` feat: PROD-UX-2 = 분석가 협동 + 포맷터 + 근거 토글
  - `6de001c` feat: sub-task decomposition + 시나리오별 축약
- 본 wrap-up commit + push 진행 예정
