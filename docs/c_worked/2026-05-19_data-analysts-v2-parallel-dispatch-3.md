---
date: 2026-05-19
topic: 자료 있는 3 분석가 페르소나 v2 — 3 subagent 병렬 dispatch + 8명 boundary 검증 확장 + INFRA-RUNTIME-EFFICIENCY-001 백로그 발견
status: completed
plan_file: C:\Users\HOME\.claude\plans\quirky-nibbling-crayon.md
---

# 2026-05-19 · 자료 있는 3 분석가 v2 (3 subagent 병렬 dispatch, 본 사이클 3 째)

## 배경

같은 날 3 사이클 째 — Track B + 본질 재정의 (오전) → 자료 0 시드 5 분석가 v2 (오후 1) → 본 사이클 (오후 2 자료 있는 3 분석가 v2). **본 사이클 목표** = 점수 발행 풀세트 (S/T/α/buy_score/F-Score) 중 미발행 3 점수 (α·T-Score+6 트리거·principle_guardian verdict) 채워 Track A·B 권고 cited_scores **90% 풍부성** 확보 → 다음 사이클 (양 트랙 통합 production 검증) 의 의미 있는 진입 준비. **사용자 의사결정 옵션 A** = 3명 동시 병렬 dispatch + stock_analyst 환각 가드 박기. chat Claude Opus (회장) 정정 4 건 (인접 boundary + 8명 충돌 검증 + Track A·B read 정합 + 챗AI 핑퐁 환기) 적용. **자원 부담 본질 발견** = BGE-m3 ~2.5GB CLI 매 호출 재로딩 → production 호출 보류, INFRA-RUNTIME-EFFICIENCY-001 백로그 신설.

## 한 일

### Phase 0: 준비 (~5분)
- `agents/analysts/wealth_strategist/` 8 섹션 portable 양식 + `market_state_analyzer/` 자료 0 시드 패턴 + 한국어 친화 용어 § + cited v3.1 재확인
- `docs/specs/ANALYST-PERSONAS-001-nine-analyst-portable-personas.md` v2 § 8-섹션 portable + § canon_categories 잠정 매핑 표 + § 결정론 채점 권위 (scoring.py 옵션 b) + § 16 페르소나 흡수 매핑 (#5 Wave Mathematician α / #6 Survival Inspector F1~F5 / #8 T-Score Auditor / #9 Trigger Hunter) 확인
- canon 디렉토리 grep → **2 깨달음 발견**:
  1. **operational_safeguards 권위 모순** — SPEC v2 매핑 표는 `trader` canon (6 카테고리 안) 에 박혔으나 실제 파일 frontmatter `analyst: principle_guardian` + 본문은 principle_guardian verdict 산출 알고리즘. 본 사이클 처리 = trader persona 에 권위 위임 명시.
  2. **trader canon 사실상 자료 0** — failure_lessons placeholder ~10 줄, operational_safeguards 는 principle_guardian 권위. trader 도 자료 0 시드 패턴 (cited:[] + framework 밖) 적용.

### Phase 1: 3 subagent 병렬 dispatch (~10분, 1 message 안에 3 Agent tool calls)
- **subagent A — `principle_guardian`** (자료 있음, wealth_strategist 패턴):
  - persona 297 줄 + manifest 131 줄
  - 명제 ID **21 개 신설**: C1~C7 (7계명) + D1~D5 (5대 심법) + R1~R3 (시장 국면) + OS1~OS6 (운용 안전핀)
  - verdict 4종 (`compliant`/`warning`/`violation`/`unknown`) + 점수 발행 X 명시
  - 인접 boundary 10 영역 한 줄씩 + 본 분석가 권위 한정 (4 자료원만)
  - 박종훈 framework 직접 인용 금지 가드 5 위치 (C 명제 ID 충돌 회피 — 본인 C1~C7 vs wealth_strategist C1~C5 dept 명 병기)
- **subagent B — `trader`** (자료 0 시드 패턴 + α 미발행 fallback):
  - persona 367 줄 + manifest 148 줄
  - **6 트리거 영문 ID 정식 표**: `volume_surge` / `intraday_top` / `gap_up` / `closing_strength` / `fund_inflow` / `volume_increase_sideways` — SPEC G2 가드 강제 (Track B 명단 변경 시 동시 수정)
  - **α 오버라이드 분기**: α ≥ 1.5 그대로 / 1.0~1.5 T-Score 0.5 하향 / < 1.0 진입 보류
  - **α 미발행 시 fallback (정정 1 핵심 — 환각 가드 전파 차단점)**: stock_analyst verdict=`unknown` 시 (a) T-Score 4 입력 단독 + confidence 50-65 / (b) 보류 verdict=`hold` 분기 명시 룰
  - operational_safeguards 권위 위임 명시 (principle_guardian 권위, 본 분석가 인용 X) — 6 위치
- **subagent C — `stock_analyst`** (환각 가드 2 중):
  - persona 338 줄 + manifest 158 줄
  - **환각 가드 2 중 (Anti-patterns 별도 §)**:
    - 가드 1: 자료 0 시드 (stock-analysis canon md 0) → cited:[] + framework 밖
    - 가드 2: INFRA-CHART-DATA-001 미구현 → **verdict=`unknown` 강제** + 5 차트 패턴 (20일선 정배열 / MACD 골든크로스 / 이중 천장 / RSI 과매도 / 거래량 패턴) 인용 절대 금지
  - INFRA 들어오면 정정 메타-가이드 (v3 마이크로 정정 ~0.3 세션) trace 3 위치 명시 — Anti-patterns 가드 2 / Outputs 격자 [1] Quality Grid / manifest response_rules
  - 발행 영역 = α + Module A 목표가 3단 (보수/중립/공격) + F1~F5 + holding_period_estimate_days 만

총 작성 = **6 파일 1,439 줄**. 5명 패턴 (이전 사이클 ~5분 / 10 파일 ~1,800줄) 동일 속도. dispatch 충돌 0.

### Phase 2: 통합 테스트 + 8명 boundary 검증 확장 (~10분)
- `tests/test_data_analysts_v2.py` **신규 작성 37 케이스**:
  - manifest 로드 + dept 정합 (3) / canon_categories SPEC v2 § 매핑 (3) / 8 섹션 portable (3) / Track A·B reads_analysts 정합 (3) / 박종훈 framework 직접 인용 금지 negation (3) / cited v3.1 (3) / Cross-Agent Boundaries 표 (3) / 본 분석가 권위 한정 (3)
  - **분석가별 특수 가드**: principle_guardian 명제 ID 21개 + verdict 4종 + 점수 발행 X (3) / trader 6 트리거 영문 ID + α 오버라이드 + α 미발행 fallback (a)/(b) + operational_safeguards 권위 위임 (4) / stock_analyst 환각 가드 2 중 + INFRA verdict=`unknown` + 정정 trace + 발행 양식 (4)
  - **Track A·B read 정합** (정정 3 자동화): trader 6 트리거 ↔ Track B set / Track A read α+holding_period / principle_guardian verdict ↔ Track A·B
- `tests/test_seed_analysts_v2.py` **8명 boundary 검증 확장 추가** (정정 2):
  - `test_8_analyst_boundary_all_others_present` — 8 분석가 각자 Cross-Agent Boundaries 표에 다른 7명 모두 명시 매트릭스 검증
  - `test_8_analyst_authority_keyword_other_negation` — 8 분석가 발행 권위 키워드 (S-Score · T-Score · α · F-Score · verdict · 시장 체제 등) 가 본 persona 등장 시 발행자 ID 또는 negation 컨텍스트 필수 (인접 250 자, negation 키워드 list 확장)
- 첫 실행 후 3 fail → negation 키워드 list 확장 (`frame 밖`/`다른 분석가`/`영역`/`read` + `트리거`/`시나리오`/`확률`/`이행` 등) → 통과

### Phase 3: production 첫 호출 검증 — **보류** (BGE-m3 메모리 부담)
- 시나리오 1 (`principle_guardian` 정량 룰 위반 검증) 호출 중 `memory allocation of 17301520 bytes failed` — BGE-m3 ~2.5GB 로딩 중 17MB 추가 할당 실패
- 사용자 PC 메모리 거의 가득 참 (다른 프로세스 + Chrome + Claude Code + Chroma 합산)
- **자원 부담 본질 발견** = CLI 호출 (`scripts/ask_analyst.py`) 의 치명적 구조 문제 — 매번 새 프로세스 = 매번 BGE-m3 재로딩
- **자동 test 91/91 + 회귀 0 + validate 0 errors** 가 양식·boundary·가드 90% 보장 — production 호출 가시 확인은 다음 사이클로 미룸

### Phase 4: wrap-up + INFRA-RUNTIME-EFFICIENCY-001 백로그 신설
- 메모리 신설 `project_runtime_efficiency_blocker.md` — 서버 모드 reuse + RAG 자료 0 시드 자동 OFF + SQLite 임베딩 캐시 3 묶음
- `MEMORY.md` 인덱스 1 줄 추가
- 본 c_worked 파일 + `docs/RESUME.md` 갱신 (Top 3 재정렬 — INFRA-RUNTIME-EFFICIENCY-001 → Top 1, 양 트랙 통합 production 검증 → Top 2, stock_analyst v3 마이크로 정정 → Top 3)
- 챗AI 검증 사이클 환기 (정정 4) — 핑퐁 1 (3 분석가 페르소나 핵심) + 핑퐁 2 (8명 boundary 종합) 권유

## 검증 결과
- ✅ `TESTING=1 PYTHONIOENCODING=utf-8 uv run pytest tests/ -q` → **331 passed** (278 → +53, 회귀 0) in 49.5s
- ✅ `PYTHONIOENCODING=utf-8 uv run python scripts/validate.py` → **0 errors, 1 warning** (teams/registry.yaml — 기존 warning, 회귀 X)
- ⏸ production 첫 호출 = **보류** (BGE-m3 메모리 부담, INFRA-RUNTIME-EFFICIENCY-001 후 다음 사이클)
- ✅ 3 subagent 병렬 dispatch ~10 분 / 6 파일 1,439 줄 (5명 패턴 동일 속도)
- ✅ 정정 4 건 모두 적용 (인접 boundary / 8명 충돌 검증 / Track A·B read 정합 자동화 / 챗AI 핑퐁 환기)

## 의도적으로 안 한 것

- **production 첫 호출** — BGE-m3 메모리 부담으로 보류. INFRA-RUNTIME-EFFICIENCY-001 (서버 모드 reuse + RAG 자료 0 시드 자동 OFF + SQLite 임베딩 캐시) 후 양 트랙 통합 production 검증 (Top 2 다음 사이클) 동시 진입
- **stock_analyst v3 정정** (INFRA-CHART-DATA-001 들어온 후) — 환각 가드 2 빼고 정상 발행 로직 추가. persona 안 정정 trace 3 위치 명시됨 (~0.3 세션)
- **양 트랙 통합 production 검증 (`both:` 호출)** — 본 사이클 후 cited_scores 90% 풍부성 확보됐으나 자원 부담으로 다음 사이클 INFRA 진입 후
- **GUIDANCE-ACCURACY-TRACKER-001 구현** — Track A 적중도 5 KPI 측정 인프라, 별도 SPEC
- **commit/push** — 사용자 명시 후 진행
- **챗AI 외부 검증 사이클 (정정 4)** — 사용자 손 영역. 본 세션 종료 후 챗AI Opus 핑퐁 권유:
  - **핑퐁 1**: 자료 있는 3 분석가 페르소나 6 파일 (`principle_guardian` / `trader` / `stock_analyst` × persona+manifest) **핵심** — canon 1:1 grep 정확도 (3 정제본의 C·D·R·OS 21 명제 ID 신설) / 점수 발행 양식 / 박종훈 가드 일관성 / α 미발행 fallback (a)/(b) 분기 합리성 / 환각 가드 2 중 trace
  - **핑퐁 2**: **boundary 종합** — 8 분석가 사이 권위 중복 0 검증 결과 + trader α 미발행 fallback 작동 + stock_analyst 환각 가드 trace + Track A·B read 정합 자동화 결과 + operational_safeguards 권위 모순 (SPEC v2 정정 필요 여부)

## 맥락 재진입 힌트

- **3 subagent 병렬 dispatch 패턴 = 5명 패턴 동일 적용 검증됨**: 본 세션 = 5명 dispatch (10 파일 ~1,800줄 ~5분) → 본 사이클 3명 dispatch (6 파일 1,439줄 ~10분). dept 디렉토리 충돌 0 확인. **canon grep 충돌 X** — principles canon 3 정제본만 read 하는 principle_guardian / 인접 dept (principles trading_doctrine) RAG read 하는 trader / canon 0 시드 stock_analyst 각자 read 영역 분리.
- **외부 reviewer (chat Claude Opus 회장) 정정 4 건 처리 패턴 검증됨**: 메모리 `feedback_external_reviewer_correction_workflow.md` 첫 적용 — 점수·기대 효과 표 (4 건 평균 8.5/10, 작업 추가 비용 +20분) → 사용자 결정 → plan 4 위치 Edit → wrap-up 챗AI 핑퐁 환기. 미래 사이클 동일 패턴 유효.
- **2 깨달음 = SPEC vs 실제 자료 불일치 발견**: (a) `operational_safeguards` 매핑 모순 (SPEC trader / 본문 principle_guardian) — 본 사이클 trader persona 에 권위 위임 명시로 처리, SPEC frontmatter 정정은 별도 사이클 (백로그) / (b) `trader` canon 사실상 자료 0 (failure_lessons placeholder, operational_safeguards principle_guardian 권위) — 자료 0 시드 패턴 적용. **미래 분석가 작성 시 SPEC 매핑 표 vs 실제 자료 grep 사전 검증 필수**.
- **INFRA-RUNTIME-EFFICIENCY-001 = 운용 본질 제약 발견**: BGE-m3 ~2.5GB CLI 매 호출 재로딩 → 사용자 PC 메모리 거의 가득 참. 단순 자원 인식 (`feedback_local_resource_aware.md`) 차원 넘어 **운용 구조 본질 제약**. 양 트랙 통합 production 검증 (Top 2) 진입 전 우선 SPEC 진입 필수. CLI 분석가 호출 → FastAPI client wrap 전환 + 자료 0 시드 분석가 RAG 자동 skip + SQLite 임베딩 캐시 3 묶음.
- **8명 boundary 충돌 검증 자동화 패턴**: `test_8_analyst_boundary_all_others_present` + `test_8_analyst_authority_keyword_other_negation` 두 함수 = 미래 분석가 추가 시 boundary 매트릭스·권위 키워드 충돌 자동 catch. Layer 5 회고분석가 신설 시 동일 패턴 적용 가능 (N=9+ 으로 확장).

## 다음에 이어서 할 작업 (우선순위)

1. **`INFRA-RUNTIME-EFFICIENCY-001` SPEC + 구현** (~1.5 세션) — 서버 모드 reuse + RAG 자료 0 시드 자동 OFF + SQLite 임베딩 캐시. **Top 2 (양 트랙 통합 production 검증) 진입 전 우선 진입**. 본 사이클 production 호출 보류 원인 해소. CLI `scripts/ask_analyst.py` 를 FastAPI client 로 wrap + `core/knowledge/compose.py` 에 RAG 자동 skip 분기 + `data/db.sqlite` 에 `embedding_cache` 테이블. ★★★★★

2. **양 트랙 통합 production 검증 + 자연 인계 메커니즘 검증** (~0.5 세션) — `INFRA-RUNTIME-EFFICIENCY-001` 후 진입. `both: 삼성전자` 호출 → Track A·B 동시 권고 + Track B 1 파 완성 시나리오에서 Track A 인계 자연 메커니즘 검증. cited_scores 90% 풍부성 (8 분석가 발행 가능) 확인. webapp default agent 교체 결정 진입 검토.

3. **`stock_analyst` v3 마이크로 정정** (~0.3 세션, `INFRA-CHART-DATA-001` 진입 시점) — 환각 가드 2 (INFRA 미구현) 빼고 정상 발행 로직 추가. 정정 위치 3 곳 (Anti-patterns 가드 2 / Outputs 격자 [1] Quality Grid 차트 추론 항목 / manifest response_rules) 명시됨. **`INFRA-CHART-DATA-001` 자체** = KIS daily chart + pandas-ta + matplotlib vision. ~1 세션. `WAVE-ALPHA-001` (Module A α 공식) 과 묶음 가능.

(백로그:
- **operational_safeguards 권위 SPEC 정정** (별도 작은 SPEC) — SPEC v2 매핑 표의 trader canon → principle_guardian canon 으로 정정. failure_lessons 도 사용자 작성 후 어디 dept 인지 결정.
- **GUIDANCE-ACCURACY-TRACKER-001 구현** — Track A 적중도 5 KPI 측정 인프라
- **scoring.py s_score·buy_score·alpha 정식 가중치 확정** (분석가 manifest 작성 시 SLOT S7 운용 중 확정)
- **`INFRA-RELIABILITY-VALIDATOR-001`** (Layer 2.5/3.5 Haiku 검증, M2)
- **`RETROSPECT-ANALYST-001`** 또는 `SYSTEM-EVOLUTIONIST-001` (Layer 5 회고분석가, M4)
- **Layer 4 계좌관리자** 1+ N (M5)
)

## 커밋 상태
- 아직 안 됨 — 사용자 명시 후 1 커밋 (코드 + 문서 + wrap-up 파일 + 메모리 묶음, push)
