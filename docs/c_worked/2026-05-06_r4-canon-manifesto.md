---
date: 2026-05-06
topic: R4 — 자산복리부 canon framework manifesto + survival imperatives 인터뷰 작성
status: completed
plan_file: C:\Users\HOME\.claude\plans\breezy-plotting-fog.md
---

# 2026-05-06 · R4 자산복리부 canon (01 framework + 02 imperatives) 인터뷰

## 배경

R3 (RAG ingest) 후 자산복리부 정제본 미작성. 박종훈 540K tokens 본체는 RAG 로 분리됐지만 자산전략가 **정체성**(canon, 매 LLM 호출 자동 주입) 이 비어있는 상태. R4 = 박종훈 framework + 사용자가 받아들인 시각을 ~2K tokens 압축본으로 손글 작성. 코드 변경 0, markdown Q&A. 인터뷰 중 `just knowledge-browse wealth_compounding "<키워드>"` 로 박종훈 단편 즉시 회수해 시각 정합 확인.

핵심 판단: **canon = 사용자가 받아들인 framework 만 압축** (박종훈 강의 전체가 아니라). 디테일은 RAG 가 동적 회수.

## 한 일

### 인터뷰 (3축 → 2축으로 축소)
- 1축 통화: 박종훈 4명제 회수 → 사용자 1·2·4 동의 (3 = 행동 룰이라 02 로 분리)
- 2축 사이클: 박종훈 단편 회수 + 웹검색(Ray Dalio·Howard Marks)으로 빠진 축 통찰 → 4(공포의 톱니바퀴, 사용자 명시 추가) + 5(빅 사이클 5단계, Dalio 통합) 보강
- 3축 위기 인식: 1·2축에 흡수됨 — **별도 3축 인터뷰 생략** (분할 너무 잘면 우선순위 흐려짐)
- 행동 룰 인터뷰: 박종훈 5룰 (I1~I5) + **사용자 추가 I6 (최근 3년 달러 평균가 이하 = 매수 타이밍, 평균가 빠르게 회귀 안 할 시 분할 매수)**

### 산출물
- `knowledge/canon/wealth_compounding/01-framework-manifesto.md` — **신규**. 통화 3 명제(M1·M2·M3) + 사이클 5 명제(C1~C5) + 자산전략가 활용 체크리스트. frontmatter `canon_id: wealth_compounding.framework_manifesto`. 박종훈 표현 그대로 + Dalio 5단계 통합.
- `knowledge/canon/wealth_compounding/02-survival-imperatives.md` — **신규**. 행동 룰 6개(I1~I6) + 활용 체크리스트. 톤 = "절대 imperative 가 아닌 메타 판단 가이드" (사용자 강조 "상황마다 판단 다름" 반영). 각 룰에 `상황 의존:` 단서 명시.
- `knowledge/canon/wealth_compounding/macro-framework.md` — **삭제** (`git rm`). placeholder 였음 (TODO 주석 + 빈 섹션 19줄).

### 인터뷰 보조 도구 사용
- `just knowledge-browse wealth_compounding "<키워드>"` 3 회 — 통화·사이클·행동 룰 단편 회수. BGE-m3 한국어 매칭 정확.
- `WebSearch` 2 회 — Ray Dalio 빅 사이클 5단계 + Howard Marks 심리 진자. 박종훈 외 시각으로 빠진 축 통찰 (사용자 동의 → 5단계 통합).

## 검증 결과
- ✅ `load_shared_canon()` 자동 주입 char 수: **15,772 → 19,166** (+3,394, 02 추가분)
- ✅ M1·I1·I6 모두 canon 문자열에 포함 (Windows utf-8 reconfigure 후 정확 검증)
- ✅ macro-framework placeholder 텍스트(`<!-- 사용자가 작성:`, `# 매크로 경제 프레임워크`) canon 에서 사라짐
- ✅ pytest 60 passed (회귀 없음)
- ✅ `git rm` 으로 macro-framework.md 삭제 추적, 새 02 파일 untracked 정상

## 의도적으로 안 한 것
- **3축 별도 framework** — 통화·사이클에 흡수됨. 강제 분할 시 분석가가 우선순위 혼란
- **M3 분석가 분화** — R4 끝나야 자산전략가 persona 가 framework 8명제 + 행동 룰 6개를 제대로 입력받음. 다음 세션
- **종목분석부 logchart ingest** — `rag_docs/logchart/` 후순위, 다음 세션 1~2h
- **박종훈 Vol 2/3 OCR** — 이미지 PDF 4 파일 0 chars 백로그 유지
- **`build_system_prompt` 등 legacy compose 함수 삭제** — R3 부터 deprecated mark, M3 또는 cleanup 세션
- **`KnowledgeChunk.team_id → dept_id` rename** — 회귀 리스크, M3 SPEC 에서 묶어 처리

## 이번에 굳힌 판단

- **canon = 사용자가 받아들인 framework 만 압축**, 박종훈 자료 전체가 아님. 540K tokens 통째로 canon 에 못 박음 → 토큰 비용 + 사용자 시각 매몰
- **framework manifesto vs survival imperatives 분리**: 01 = "어떻게 보는가" (불변 세계관), 02 = "어떻게 행동하는가" (상황 의존, 메타 가이드). **충돌 시 framework 우선**
- **3축 분할 X**: 위기 인식이 통화·사이클 framework 에 흡수. 분할 너무 잘면 분석가가 우선순위를 못 잡음. 명제 압축 단위는 인식틀 단위로
- **박종훈 표현 그대로** (사용자 선호) — 압축 시 의역하지 말 것. 사용자 본인 어조보단 출처 표현 유지
- **5단계 빅 사이클 (Ray Dalio) 통합** — 박종훈 J커브 단독 framework 의 비관 편향을 균형. 5단계 위치 인식이 자산전략가 의사결정의 가장 큰 입력
- **I6 사용자 추가 룰** (3년 달러 평균가 시그널) — 사용자가 진술한 박종훈 룰을 manifesto 에 명시. RAG 검색이 아닌 canon 에 박힐 만큼 자주 쓰는 룰

## 다음에 이어서 할 작업 (우선순위)

1. **M3 — 분석가 5명 페르소나 분화 + 매매일지 SPEC** (PC, 2~3h)
   - `analyst.md` 1 → 5 `agents/analysts/<id>/persona.md` split (원칙수호자·매매코치·자산전략가·종목분석가·뉴스큐레이터)
   - manifest `reads:` 매핑 → analyze stage 5 호출
   - 자산전략가의 `reads: [wealth_compounding]` 첫 가동 — R3 의 `rag_dept` 인자가 의미 가짐. canon 19K chars 가 자동 주입되는 첫 분석가
   - `BRIEFING-JOURNAL-001` 매매일지 SPEC 골격 (user_want_spec "AI 매매일지 + 피드백" 첫 진입)

2. **종목분석부 자료 ingest** (PC, 1~2h)
   - `rag_docs/logchart/` (5 md + 엘리엇 매뉴얼 + xlsx, ~288KB) 를 `knowledge/reference/stock-analysis/` 로 이전
   - `config/knowledge_sources.yaml` 항목 추가 + `just knowledge-sync stock-analysis` + `just knowledge-ingest stock-analysis`
   - R3 plugin 패턴 두 번째 검증 (자산복리부 외 첫 학습부)

3. **다른 학습부 자료 (실전부·뉴스부)** (가변)
   - 자료 출처 결정부터 필요. logchart 같은 즉시 가용 자료 없음
   - M3 와 병행 가능 (자료 작업 vs 페르소나 분화 독립)

## 맥락 재진입 힌트

- **canon 자동 주입 검증**: `uv run python -c "import sys; sys.stdout.reconfigure(encoding='utf-8'); from core.knowledge.compose import load_shared_canon; print(len(load_shared_canon()))"` → 19,166 가 base. 신규 학습부 정제본 추가 시 이 수치가 늘어남
- **Windows 콘솔 cp949 함정**: 한국어 검증 시 `sys.stdout.reconfigure(encoding='utf-8')` 필수. R3 의 `scripts/knowledge.py` 가 모듈 시작에서 이미 처리
- **canon 갱신 흐름**: 박종훈 신규 강의는 reference sync + RAG 재인덱싱으로 충분 (canon 미세 갱신 X). manifesto 갱신은 framework 자체가 변할 때만
- **02 의 톤**: 절대 imperative 아닌 메타 가이드. 룰 깰 때 이유 명시. M3 자산전략가 persona 작성 시 이 톤 그대로 가져갈 것

## 커밋 상태

이번 wrap-up 에서 2 커밋 + push 예정:
1. `feat(knowledge): R4 자산복리부 canon — framework manifesto + survival imperatives` (canon 3 파일)
2. `docs: wrap-up 2026-05-06 R4 canon manifesto + imperatives` (c_worked + RESUME + SESSIONS + memory)
