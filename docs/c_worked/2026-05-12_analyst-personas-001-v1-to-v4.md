---
date: 2026-05-12
topic: ANALYST-PERSONAS-001 SPEC 신설 + 자산전략가 페르소나 v1→v4 4 회 반복 (격자 양식 LLM 추종력 한계 드러남)
status: partial
plan_file: C:\Users\HOME\.claude\plans\stateful-cuddling-sphinx.md
---

# 2026-05-12 · ANALYST-PERSONAS-001 + 자산전략가 v1→v4 (LLM 추종력 한계)

## 배경

KNOWLEDGE-SYNC-001 Phase 2 풀세트 완료 직후. **9 분석가 중 1명(`wealth_strategist`)만 활성** 상태에서 본질 검증 시점 도달. 사용자가 Gemini Gems 페르소나 2개 (CIO+주도주, TACO 매매법) 예시를 던지며 **"진화적 agent 전문가 구조"** 의 차별점 추론 요구. SPEC 정식화 + 8-섹션 portable 양식 정의 + 자산전략가 첫 분석가로 검증이 목표.

핵심 판단: **페르소나 layer 만으로 격자 양식 분기 결정론 불가능** — 4 회 반복 패치 (v1→v2→v3→v4) 후 LLM (gemini-2.5-flash) 추종력 한계 노출. 본질 해결 = compose 분기 코드 변경 (다음 세션).

## 한 일

- `docs/specs/ANALYST-PERSONAS-001-nine-analyst-portable-personas.md` — **신설**. frontmatter (generates 16 + modifies 3 + depends_on KNOWLEDGE-SYNC-001) + 8-섹션 양식 정식 정의 + 9 분석가 ID·dept·canon_categories 매핑 표 + Outputs Task trigger 분기 룰 + 실시간 grounding 메타 원칙 + identity seed Phase A-B-C 흐름 + 마일스톤 세션 1~5 + 의사결정 SLOT (S5 미 매크로 collector / S6 LLM tool use 백로그)
- `agents/analysts/wealth_strategist/persona.md` — **4 회 재작성**:
  - v1: 5섹션 → 8섹션 portable (Identity / Domain Frame / Inputs / Outputs / Reasoning Doctrine / Knowledge Categories / Anti-patterns / Cross-Agent Boundaries)
  - v2: Outputs 에 격자 5 요소 (Cycle Position 3축 / Cycle Scenario 4분기 / Asset Implication / Citation / Yesterday Delta) 강제 추가
  - v3: 격자를 Task trigger 분기 (frame 핵심 분석 시만) + Inputs 우선순위 재조정 (snapshot 3순위 격상) + Anti-patterns 3 카테고리 분리 (분화 boundary / 책 인덱싱 / 추론 규율)
  - v4: 자연어 default 풍부 묘사 + 격자 양식 압축 + **negative trigger** ("뭐예요/뭔데/설명/짧게" 들어오면 격자 절대 금지) 명시
- `agents/analysts/wealth_strategist/manifest.yaml` — canon_categories 1개(검증 임시) → 6개(자산복리부 전체) 정렬 + response_rules 강화 (system [5] 블록에 분기 룰 강제 명시)
- `scripts/_check_embedding_04.py` — 박종훈 04-금리 반란의 시대.md (사용자 수동 drop) 의 RAG 임베딩 검증용 임시 스크립트. 42 chunks 정상 인덱싱 + 시맨틱 검색 hit 확인 후 **삭제**

## 검증 결과

- ✅ `TESTING=1 pytest tests/ -q` → **135 passed** (회귀 0, 4 회 재검증 모두 통과)
- ✅ v2 실 LLM 호출 (gemini-2.5-flash, "현재 미국 부채 사이클 + 자산 배분 함의?") → 격자 5 요소 정확. 단 **학습 데이터 수치 추정** ("미 부채 39조 → 45조 달러") 책 인덱싱 답 발견 → v3 grounding 원칙으로 차단
- ✅ v3 실 LLM "지금 사이클 어디 + 자산 비중?" → 격자 + snapshot 실시간 수치 인용 (KOSPI 7,822 / SK하이닉스 +11.51% / 환율 1,461.43 / WTI +3.19%) 정확. 학습 데이터 수치 추정 사라짐
- ✅ v4 CLI "J커브 진입이 뭔데?" → 격자 0 / 자연어만 / `cited: [C1]` 한 줄
- ✅ v4 CLI "지금 사이클 어디 표로 정리해줘" → 격자 5 요소 정확 (시나리오 합 100%)
- ❌ **v4 webapp 사용자 호출 "J커브가 뭔지 설명해줘"** → 격자 박힘. LLM 추종력 한계 노출. 사용자 webapp 응답에서 양식+자연어 둘 다 출력. negative trigger 무시
- ✅ 박종훈 04-금리 반란의 시대.md (사용자 수동 drop) → watchdog 자동 임베딩 42 chunks. `cited: [C1]` 등 실 호출에 정상 인용

## 의도적으로 안 한 것

- **compose 분기 코드 변경** — 사용자가 "이번 세션은 페르소나만" 결정. 9 분석가 공통 인프라라 별도 SPEC 으로 분리 (다음 세션 첫 작업)
- **8 분석가 신규 페르소나** — 양식 portable 검증 (v4 한계) 못 끝남, 본질 해결 후 진입
- **36 카테고리 `_category.yaml` 의 `target_analysts` 채우기** — 자료 있는 4 dept 페르소나 완성 후
- **미국 매크로 collector** — 옵션 비교 후 S5 SLOT 으로 백로그 (별도 SPEC 후보 `INFRA-US-MACRO-SNAPSHOT-001`)
- **04-금리 반란의 시대.md frontmatter 보강** — 사용자 결정 "1번 그대로 두기" (gitignored, frontmatter 없이도 RAG 정상)

## 맥락 재진입 힌트

- **LLM 추종력 한계는 페르소나 layer 의 본질 제약**: persona 안 격자 양식 텍스트가 존재하는 한 LLM (특히 gemini) 끌림 무한. 4 회 패치 (v1→v4) 시도 후 webapp 에서 다시 격자 박힘 = 페르소나만으로 100% 분기 결정론 불가능. 본질 해결 = **격자 양식을 persona/manifest 에서 완전 제거**, server `core/knowledge/compose.build_pipeline_prompt` 가 사용자 질문 keyword 검사로 격자 prompt 를 동적 주입
- **system prompt 의 [5] 블록 (response_rules) 영향력 ↑**: LLM 이 마지막에 본 instruction 이라 추종력 큼. 단 페르소나 [1] 블록 안 양식 텍스트가 같이 있으면 둘 다 따르려 함 → 양식 자체를 빼야 결정론
- **negative trigger ("뭐예요/뭔데/설명") 무시 경향**: gemini-2.5-flash 가 "절대 ~하지 말 것" 류 부정문 무시 잦음. Claude (anthropic) 가 instruction following 더 강함 — provider 강제 옵션도 임시 대안
- **prompt cache 영향**: persona/manifest 변경 시 system prompt hash 달라져 cache miss (정상). webapp 격자 재발은 cache 가 아닌 LLM 추종력 한계가 원인 (다른 질문에도 격자 박힘 확인)
- **`load_analyst_spec` 캐시 없음** (`run_analyst.py:63-89`): 매 호출 디스크 fresh read. **persona/manifest 변경은 server 재시작 불필요, 다음 호출부터 즉시 반영**
- **자산전략가 v4 격자 trigger CLI 에선 동작 OK / webapp 에선 LLM 따라 가변**: stochastic 동작. 100% 보장은 코드 분기만이 답

## 세션 중 실 비용

- 실 LLM 호출 5 회 (v2/v3 각 1, v4 CLI 2, 사용자 webapp 1 추정) ≈ $0.005 (gemini-2.5-flash, 평균 latency 13-23s)

## 다음에 이어서 할 작업 (우선순위)

1. **compose 분기 SPEC 신설 + 구현** (1.5~2 세션) — **본질 해결 핵심**. `core/knowledge/compose.build_pipeline_prompt` 에 사용자 질문 keyword 분기 로직 추가. positive trigger 감지 시 격자 prompt template 을 system 마지막에 동적 주입, negative trigger 또는 일반 질문 시 격자 텍스트 미주입. persona/manifest 에서 격자 양식 텍스트 통째 제거. LLM 추종력 의존 0 → 결정론 100%. **9 분석가 공통 인프라** — 한 번 만들면 모든 분석가 분기 일관. 새 SPEC ID 후보: `INFRA-PROMPT-TRIGGER-001` 또는 ANALYST-PERSONAS-001 modifies 확장.
2. **미국 매크로 collector SPEC 신설** (~1 세션) — `INFRA-US-MACRO-SNAPSHOT-001`. yfinance/FRED API 로 미 10년물 / 달러인덱스 / VIX / 미 부채 잔액. `collectors/snapshot.py` 확장하여 자동 주입. v3 의 "snapshot 외 수치 framework 밖" 룰의 grounding 인프라 보강. 자산전략가·시장상태분석가·트레이더가 책 인덱싱 답 못 하게 차단.
3. **나머지 8 분석가 페르소나 작성** (3~4 세션) — compose 분기 + 미 매크로 collector 완료 후 진입. principle_guardian / trader / stock_analyst (자료 있는 3명) 우선 → 자료 0 시드 5명. 각 분석가 frame 격자 1개 + 시나리오 분기 + Cross-Agent Boundaries 일관 적용 — 단 격자 양식 텍스트는 compose 분기 인프라가 관리.

## 커밋 상태

- 작업 트리: `knowledge/reference/**` 는 gitignored (사용자 수동 drop 04-금리 반란의 시대.md 포함 — repo 변경 0)
- 이번 세션 실 변경: SPEC 신설 (docs/specs/ANALYST-PERSONAS-001-*) + 자산전략가 persona/manifest 4 회 수정. 임시 검증 스크립트 _check_embedding_04.py 는 작성 후 삭제 — git 추적 없음
- wrap-up commit: 이 파일 + RESUME.md + SESSIONS.md 와 함께 1 commit 으로 묶어 push 진행
