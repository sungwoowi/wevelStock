---
date: 2026-05-23
topic: 아키텍처 본질 재평가 사이클 — 9 분석가 multi-agent 가능성 탐색 (6번째 세션)
status: completed
plan_file: C:\Users\HOME\.claude\plans\snoopy-booping-haven.md
---

# 2026-05-23 · 아키텍처 본질 재평가 — 9 분석가 multi-agent vs 단일 임원 vs 하이브리드 가능성 탐색

## 배경
5번째 세션 (mock fallback 차단 + principle frame 분리) 직후 INFRA-SCORE-INPUTS-001 SPEC 인터뷰 진입 시도. 그러나 사용자가 인터뷰 중간에 **9 분석가 multi-agent 본질 의문** 제기.

**사용자 발견 결함 6건**:
1. 분석가 응답이 점수화 위주, 시장·섹터·종목 흐름 자연어 맥락 X
2. 3줄 요약에서 "사/말/홀/분/매" 관점 빈약
3. 상황별 가중치 차별 안 됨 (수급·펀더·차트)
4. 9 응답 취합 시 맥락 생략
5. 전략가 = 멍청한 임원 (정량 평가만, 통찰 X)
6. 임원이 분석가에게 "이게 맞아?" 반문 X

**사용자 본질 재질문**: 9 분석가 데이터를 하나의 똑똑한 임원 LLM 이 받아 9 분석가 효과를 낼 수 있느냐. **가능성만 보고 싶다** (결정 X).

**사용자 추가 명시**:
- *"이 다음에 하이브리드 poc를 해보고 싶은데 아마도 이건 별도 feature 브랜치 따서 Poc 해봐야할 것 같아"* — PoC = 별도 브랜치 격리
- *"Chat opus api키는 없어서 제미나이 flash 모델로 해야할 것이다 이 점 유의해라"* — PoC 임원 LLM = Gemini Pro / Flash

## 한 일

### 1. SPEC 인터뷰 보류 결단 → 가능성 탐색 사이클로 전환
- INFRA-SCORE-INPUTS-001 SPEC 인터뷰 보류 (사용자 본질 의문 해소 전 진입 시 다음 세션 재발 위험)
- 본 세션 = **객관 평가 메모 + chat Opus 핑퐁 자료 작성** 사이클로 재정의

### 2. prism-insight `/evaluate` 실 패턴 확인 (WebFetch)
- GitHub `dragon1086/prism-insight` README + `docs/CLAUDE_AGENTS.md` 확인
- **결정적 발견**: prism 도 **13+ agent multi-agent** (단일 LLM 아님). 5 팀 = Macro(1) + Analysis(6, GPT-5) + Strategy(1) + Communication(3) + Trading(3) + Consultation(2)
- 실행 패턴 = **Sequential (rate limit friendly)** + Investment Strategist 통합 + Summary Optimizer 압축 + Quality Evaluator 반복 루프
- 환각 가드 = Quality Evaluator "iterative improvement loop until EXCELLENT rating"
- **prism 이 "빠르다" 의 본질**: 단일 LLM 아님. 4 요인 = (a) GPT-5 빠른 first-token (b) Summary Optimizer 400자 압축 (c) MCP 도구 직접 grounding (d) Market Analysis 캐싱

### 3. 객관 평가 메모 작성
- 경로: `idea_memo/2026-05-23-architecture-evaluation-by-claude-code.md` (~400 LOC)
- 구조:
  - § 1 사용자 본질 의문 (원문 quote)
  - § 2 발견 결함 6건
  - § 3 prism-insight `/evaluate` 실 패턴 (WebFetch 결과)
  - § 4 3 옵션 trade-off (옵션 1 = 단일 임원 / 옵션 2 = 하이브리드 / 옵션 3 = 현재 + 임원 deepening + Quality Evaluator)
  - § 5 옵션별 결함 6건 해소 매핑
  - § 6 추천 = **옵션 3 단계적 접근** (Phase 1 옵션 3 → 결함 #1·#4 미해소 시 옵션 2 escalation), 근거 5건
  - § 7 chat Opus 핑퐁 질문 5건 (v3.0 16 페르소나 vs 옵션 3 / 임원 doctrine / 반문 임계값 / Quality Evaluator 비용 / multi-agent 정합도)
  - § 8 PoC 진행 권장 (브랜치 전략 + scope 단계 + 검증 기준)
  - § 9 본 메모 작성자 입장
  - § 10 chat Opus 호출 메시지
- 모델 제약 frontmatter 명시 (Gemini Pro / Flash, 사용자 명시 Opus API 키 없음)

### 4. RESUME.md Top 3 재배치
- Top 1 = `INFRA-SCORE-INPUTS-001 SPEC 인터뷰` → **Top 1 = chat Opus 핑퐁 → 아키텍처 옵션 결단**
- Top 2 = `production UX 부분 답변 정직성` → **Top 2 = PoC SPEC 신설 + 브랜치 생성 (옵션 결단 직후)**
- Top 3 = `LLM-TIER-MIGRATION-001` → **Top 3 = (PoC 결과 따라) INFRA-SCORE-INPUTS-001 또는 production UX 부분 답변 재평가** ⏸️ (보류)
- "지금 어디 있나" 섹션 갱신 (6번째 세션 = 아키텍처 본질 재평가 사이클)

### 5. 사용자 prism 실 응답 샘플 + 추천 정정 (본 세션 후반)
- 사용자가 prism-insight 텔레그램 봇에 005930 직접 질의 → 응답 2건 (분석 리포트 + 후속 목표가) 가져옴
- 사용자 평가: *"환각이 있을 수 있지만 내용은 풍부하다. 위 수준 정도가 되면 좋겠다"* → **prism 응답 수준 = wevelStock 응답 품질 KPI**
- claude-code 가 prism 응답에서 발견한 5 패턴 추출:
  1. 5-layer 자연어 chain (데이터 → 풀이 → 의미 → 시나리오 → 권고)
  2. 시나리오 3 (긍정·중립·부정 + 각 가격 구간 + 행동 권고)
  3. "솔직히 말하면" 임원 톤 + 정량 + 자연어 동시 grounding
  4. 상황별 가중치 통합 ("외국인 매도지만 기관이 받쳐주고 있다")
  5. 컨텍스트 이어진 후속 질문 (300,000 저항 → 안착 조건)
- wevelStock 현재 응답이 prism 수준에 못 미치는 본질 3가지:
  1. 9 분석가 cited 자연어 풀이가 임원 통찰의 자리 차지
  2. 시나리오 3 같은 사용자 행동 가이드 doctrine 부재
  3. 종합 시 정량 가중치 합산 (상황별 통합 추론 X)
- **추천 정정**: 옵션 3 단계적 접근 → **옵션 2 (하이브리드) 직진**. prism 응답 5 패턴 = 옵션 2 가 도달 가능, 옵션 3 으로는 부분 도달만 (9 분석가 cited 자연어가 5-layer chain 차단)
- idea_memo § 2.5 신설 + § 6 추천 정정 + PoC scope 재조정 (최소 PoC = prism 응답 5 패턴 모두 시연, 검증 기준 = prism 005930 응답과 1:1 비교)

### 6. prism `/signal` (한국 시장 시그널) 2번째 샘플 분석 — 양식 모범 + 통찰 미달 (본 세션 최종 증분)
- 사용자가 prism `/signal` (케빈 워시 Fed 의장 + 미 국채 금리 regime → 한국 시장 영향 macro) 응답 가져옴. 사용자 평가: *"내 인사이트랑은 맞지 않아. 얕은 통찰의 환각 같긴 해"*
- claude-code 2 차원 분석:
  - **양식 (shell)** = ✅ 옵션 2 시연. 신규 양식 패턴 2건 (§ 2.5.1 5 패턴 → 7 패턴): ⑥ 수혜/피해 섹터·종목 매트릭스 ⑦ 과거 유사 사례 인용 (2013 테이퍼링 등)
  - **통찰 (substance)** = ❌ 얕음 + 환각. 본질 3: (1) 학부 거시 교과서 답안 (사용자 framework 부재) (2) 사실 환각 3건 (워시 의장 확정 / 30조 달러 국채 / 2013 외국인 3-4조원 순매도 수치) (3) 박종훈·변곡점 lens 부재
- **결정적 함의**: 옵션 2 의 성패 = "임원 LLM 양식 갖추기" 가 아니라 **"임원 doctrine 의 질"**. prism `/signal` 은 양식 모범 + doctrine(일반 거시 지식) 미달 → 사용자 즉시 간파
- idea_memo § 2.6 신설 + § 6.0.1 신설 (옵션 2 성패 = 임원 doctrine 질) + § 6.2 최소 PoC 최우선 작업 = 임원 doctrine 설계 (사용자 framework 흡수 + 환각 가드) 로 명문화

## 검증 결과
- ✅ 객관 평가 메모 작성 완료 (~400 LOC), chat Opus 가 받아서 핑퐁 가능한 객관성 + 미해결 질문 5건
- ✅ RESUME Top 3 재배치 = 옵션 결단 전 다른 SPEC 진입 차단 명시
- ✅ prism `/evaluate` 실 패턴 확인 = 옵션 1 (단일 LLM) 명분 약함, 옵션 2/3 정합 확인
- ✅ 코드 변경 0 = main 안전성 보존 (사용자 명시 PoC 별 브랜치 정합)

## 의도적으로 안 한 것
- **PoC 코드 작성** — 별 feature 브랜치에서 다음 세션
- **chat Opus 직접 호출** — 사용자가 직접 핑퐁 (사용자 명시 API 키 없음, chat 인터페이스 사용)
- **9 분석가 페르소나 수정** — 옵션 결단 전 변경 X
- **commit 자동화** — 사용자 명시 후 진행

## 기술 부채/미완
- **chat Opus 핑퐁 사이클 대기** = 사용자가 메모를 chat 으로 전달 → 응답 받음 → 다음 세션 시작
- **PoC scope 미확정** = 최소/중간/풀 PoC 중 어느 단계부터 시작할지 옵션 결단 직후 결정
- **v3.0 설계서 충돌 여부** = 본 메모 옵션 3 (10 페르소나) 가 v3.0 (16 페르소나) 의 부분 적용인지, 별도 경로인지 미해결 (Q5)

## 다음에 이어서 할 작업 (우선순위)

1. **(사용자 비동기)** chat Claude Opus 와 `idea_memo/2026-05-23-architecture-evaluation-by-claude-code.md` 핑퐁
2. **(다음 세션 시작 시)** chat Opus 응답 받았으면 아키텍처 옵션 결단 → `git checkout -b feature/hybrid-executive-poc` → SPEC 신설 → 최소 PoC 구현 (임원 페르소나 1개 + Track A + 005930 smoke)
3. **(PoC 결과 후)** main 머지 (성공) or 폐기·learnings 메모 (실패) → INFRA-SCORE-INPUTS-001 재평가 → 진행 결단

## 커밋 상태
- 코드 변경 0.
- commit 1 = `1e42c9d docs: cycle 6 architecture evaluation + prism response analysis (옵션 2 직진 추천)` (idea_memo + RESUME + c_worked 3 파일, 푸시 완료)
- commit 2 = prism `/signal` 증분 (idea_memo § 2.6/§ 6.0.1/§ 6.2 + c_worked 한 일 #6). 본 세션 재개 후 추가.

## 메모리 검토 결과
- **신설 후보 없음** — 본 사이클은 가능성 탐색 + 옵션 결단 대기 상태. PoC 결과·옵션 결단 후 영구 가치 패턴 발견 시 신설
- **기존 메모리 정합** — `feedback_external_reviewer_correction_workflow` (chat Opus 핑퐁 패턴) / `feedback_llm_tier_strategy` (Gemini 3 tier) / `feedback_ask_before_architecture_change` (아키텍처 결단 사용자 명시 후) 모두 본 사이클에 자연스럽게 적용됨
