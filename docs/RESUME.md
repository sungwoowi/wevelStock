# RESUME — 작업 재진입 상태판

> 이 파일은 **항상 최신 상태**로 유지됩니다. 세션을 새로 열 때 `/resume` 만 치면 이 파일을 읽고 플랜모드로 브리핑합니다.
>
> 갱신 주기: 의미 있는 작업 완료 후 `/wrap-up` 실행 시 자동 갱신.
> 수동 편집도 자유 — 구조만 지키면 됩니다.

---

## 📍 지금 어디 있나

**현재 위치**: **R4 자산복리부 canon 완료** — `01-framework-manifesto.md` (통화 3 + 사이클 5 명제, Ray Dalio 5단계 통합) + `02-survival-imperatives.md` (행동 룰 6개, I6 = 사용자 추가 3년 평균가 시그널). 박종훈 표현 그대로 손글, 톤 = "절대 imperative 아닌 메타 판단 가이드". canon 자동 주입 char 수 **15,772 → 19,166** (자산전략가 정체성 굳음). 박종훈 자료의 framework 압축 + RAG 디테일 회수 두 축 모두 가동 가능. **다음 세션 = M3 분석가 5명 페르소나 분화** — 자산전략가의 `reads: [wealth_compounding]` 첫 가동.

**마지막 작업일**: 2026-05-06
**마지막 세션 로그**: [2026-05-06_r4-canon-manifesto.md](c_worked/2026-05-06_r4-canon-manifesto.md)
**Git**: `main` push 완료. 최신: `docs: wrap-up 2026-05-06 R4 canon manifesto + imperatives` (이번 세션). 이전 5: `feat(knowledge): R4 자산복리부 canon` / `9698878` R3 RAG / `e23edbd` M1 / `1f0d556` M2 원칙부 / `37b640d` R1 wealth_compounding.

---

## 🎯 다음에 할 일 (Top 3)

우선순위 순. 마음에 드는 것 하나를 `/resume` 인터뷰에서 고르세요.

### 1. M3 — 분석가 5명 페르소나 분화 + 매매일지 SPEC (PC, 2~3h)
- **왜**: R4 canon 19K chars 가 비어있는 단일 `analyst.md` 위에 깔리는 중 — 분석가가 자기 학습부를 인식 못 함. 자산전략가의 `reads: [wealth_compounding]` 가 첫 가동되어야 R3 의 `rag_dept` 인자가 의미를 가짐. user_want_spec 의 "agent 간 긴밀한 소통" 본질에 직결.
- **범위**: `analyst.md` 1 → 5 `agents/analysts/<id>/persona.md` split (원칙수호자·매매코치·자산전략가·종목분석가·뉴스큐레이터) + manifest 의 `reads` 매핑 + analyze stage 5번 호출 + 매매일지 SPEC `BRIEFING-JOURNAL-001` 골격 (user_want_spec "AI 매매일지 + 피드백" 첫 진입).
- **예상**: **2~3h PC 단발**. R4 직후 진입 자연 — framework 8명제 + 행동 룰 6개가 자산전략가 persona 의 핵심 입력.

### 2. 종목분석부 자료 ingest (PC, 1~2h)
- **왜**: `rag_docs/logchart/` 차트 교육 자료 (5 md + 엘리엇 매뉴얼 + xlsx, ~288KB) 가 즉시 가용. R3 plugin 패턴 두 번째 검증 — 자산복리부 외 첫 학습부.
- **범위**: 케이스 A 흐름 — `rag_docs/logchart/` → `knowledge/reference/stock-analysis/` 이전 + `config/knowledge_sources.yaml` 한 줄 추가 + `just knowledge-sync stock-analysis` + `just knowledge-ingest stock-analysis`.
- **예상**: 1~2h. M3 와 병행 가능 (자료 ingest 와 페르소나 분화는 서로 독립).

### 3. 다른 학습부 자료 채우기 (실전부·뉴스부, 가변 시간)
- **왜**: 5 학습부 중 원칙부·자산복리부·종목분석부 채워지면 실전부·뉴스부만 남음. M2 패턴 plugin 검증됨.
- **범위**: 자료 출처·OneDrive 경로 결정부터 필요 (logchart 같은 즉시 가용 자료 없음). `knowledge_sources.yaml` 항목 + sync + ingest.
- **예상**: 가변. 자료 가용성에 따라 dept 별 1~2h.

---

## 🌱 이 프로젝트의 본질 (매 세션 반드시 참조)

- **[docs/a_wanted/user_want_spec.md](a_wanted/user_want_spec.md)** — **원 요구사항**. 이 프로젝트가 무엇을 위한 것인지 사용자가 직접 서술한 문서. 작업 방향이 본질에서 벗어나지 않도록 매 세션 초반에 반드시 읽고 내재화.

## 📂 활성 설계/계획 문서

- **[SPEC: BRIEFING-TIMEBASED-002](specs/BRIEFING-TIMEBASED-002-timebased-briefings.md)** — draft. 3종 브리핑 + RAG. **다음 세션 Top 1**
- **[SPEC: BRIEFING-ON-DEMAND-001](specs/BRIEFING-ON-DEMAND-001-briefings-on-demand.md)** — implementing. v1 구현 완료 (참조용)
- **[플랜: v1→v2 이행](../../../.claude/plans/nested-booping-dream.md)** — 2026-04-23 세션 최종 플랜
- **[파이프라인 재구성 플랜](b_plan/pipeline-restructure-plan.md)** — Phase 1~4 로드맵
- **[아키텍처 리뷰](b_plan/architecture-review-workflow-restructure.md)** — 하이브리드 6팀 3-Layer 결정

---

## 🧩 마지막 세션이 남긴 맥락 (바로 쓸 수 있도록)

### 완성된 자산
- `pipelines/market_briefing_pre/` (← morning_pre) — 8 stages, 실 LLM 실증 완료. notify stage `skip_notify` 존중
- `pipelines/market_briefing_now/` — 3 stages, KIS 22콜 + KRX 1콜 ~28s, LLM 없는 raw 발송
- `collectors/kr_{indices,sectors,leading_stocks,supply_demand,futures_supply_demand}.py` — 5주체 수급(KIS) + KOSPI200 선물 3주체(KRX)
- `connectors/{kis,krx}/client.py` — KIS 토큰자동·rate limit + KRX `getJsonData.cmd` POST helper
- `core/briefing/render.py` — 5주체 세로 나래비 + `[KOSPI200 선물]` 블록 + 백만원→억/조 helpers
- `server/api/briefings_on_demand.py` 4 엔드포인트 + `server/telegram/` 4 명령
- **5 학습부 폴더 + 5-Layer docs 등재** (M1) — `knowledge/canon/{principles,mechanics,wealth_compounding,stock-analysis,news}/`, `agents/` 위치 합의, STRUCTURE/RUNTIME/CLAUDE 5-Layer 표 정식 등재
- **`core/knowledge/compose.py`** — `load_shared_canon()` rglob 재귀 + README 자동 제외 + `build_pipeline_prompt(rag_dept=...)` 인자 (R3)
- **`knowledge/canon/principles/` 정제본 4 파일** (M2) — `01-philosophy-7-commandments.md` + `02-trading-doctrine.md` + `03-market-regime-rules.md` + `99-operational-safeguards.md`
- **`knowledge/canon/wealth_compounding/` 정제본 2 파일** (R4) — `01-framework-manifesto.md` (통화 3 + 사이클 5 명제, Ray Dalio 5단계 통합) + `02-survival-imperatives.md` (행동 룰 6개, I6 = 사용자 추가 3년 평균가 시그널). canon 자동 주입 char 수 **15,772 → 19,166**
- **`knowledge/reference/principles/` 원본 3** — 7계명·심법·거시 트레이딩 기준
- **`knowledge/reference/wealth_compounding/` 박종훈 24/29** (R2) — lectures 18 + materials 6 + ebooks 1(Vol 1). 541,627 chars (~540K tokens)
- **`scripts/sync_knowledge.py` + `config/knowledge_sources.yaml`** — OneDrive PDF 멱등 추출 sync. slugify(한글 보존) + 디자인 PDF 한글 글자공백 휴리스틱 정규화. `just knowledge-sync <dept>`
- **`core/knowledge/{embed,ingest,retrieve}.py` 5-Layer RAG** (R3) — BGE-m3 한국어 임베딩 wiring (Chroma collection EF 명시), `ingest(dept, *, force=False)` upsert + sha256 file_hash skip 멱등, `retrieve(dept, query, top_k)` lru_cache, `data/chroma/<dept>/`
- **`data/chroma/wealth_compounding/`** — 25 sources / 787 chunks 인덱싱 완료. 검증 4건 정확. 첫 인덱싱 ~55분, 멱등 재실행 17.7s (170배)
- **`scripts/knowledge.py`** — `ingest`/`browse` 단순 CLI + Windows utf-8 reconfigure
- **`docs/specs/INFRA-RAG-001-knowledge-rag.md`** — RAG SPEC + 한국어 임베딩 비교표 + 결정 근거
- **pytest 60 passed** (M1, M2, R1, R3, R4 회귀 모두 통과)
- SPEC 3종: **BRIEFING-ON-DEMAND-001** + **BRIEFING-TIMEBASED-002** + **INFRA-RAG-001**

### 미완 또는 의도적 공백
- **분석가 5명 페르소나 분화 (analyst.md 1 → 5)** — M3 단계 + 매매일지 SPEC 첫 골격. **canon 19K chars 가 자동 주입되는 첫 분석가가 자산전략가**
- **`KnowledgeChunk.team_id` 필드** 가 dept 값을 담음 (legacy 호환). M3 분석가 분화 SPEC 에서 `dept_id` 로 rename
- **`compose.py`의 legacy `build_system_prompt` / `load_canon` / `load_persona`** — `get_team` 의존, 호출처 0. M3 또는 cleanup 세션에서 삭제
- **분석가 manifest `reads:` 와 RAG dept 자동 매핑** — M3 정식 정의 (R3 에서는 인자만 추가, R4 에서도 첫 가동 안 함)
- **박종훈 Vol 2/3 OCR 미실행** (4 파일 0 chars, 이미지 PDF) — `ocrmypdf` + tesseract 도입 백로그. Vol 1 만으로 framework 핵심 충분
- **영문 글자 사이 공백 정규화** — RAG 검증 결과 BGE-m3 가 공백 무시하고 정확 매칭. 후순위
- **다른 학습부 자료 (실전·종목분석·뉴스) 미채움** — 종목분석부는 `rag_docs/logchart/` 즉시 가용 (Top 3 의 #2)
- **전략가 3 / 계좌관리자 / 출력 채널 확장** — M4~M6, 한참 후
- **선물 수급 3주체 → 5주체 확장** — KRX MDCSTAT bld 캡쳐, 백로그
- **Phase 3 `market_briefing_close`** — 5-Layer M3 이후 자연 진입
- **dead code 청산** (`market_investor_summary`/`foreign_institution_top`/`core/registry.py`/`rollup.py`) — 회귀 리스크 큰 별도 세션
- **KOSPI200 선물 정확 가격** — 지수(2001) 대체. 선물옵션 API 별도
- **`rag_docs/logchart/` (untracked, ~288KB)** — 차트 교육 자료. 종목분석부 학습부 첫 자료 후보, 케이스 A 흐름 (Top 3 의 #2)
- **`docs/KNOWLEDGE-WORKFLOW.md` 5케이스 가이드** — 자료 추가 흐름차트 미작성 (R3 의 5케이스 정리만 c_worked 에 있음)

### 꼭 알아둘 판단

**기초·불변 원칙**
- **파이프라인 구조 = "시간대별 독립 폴더"**. 공통 수집은 `collectors/` 로만 공유, 파이프라인 간 코드 import 금지
- **수동 관심(`watch_positions`)과 AI 시뮬(`sim_positions` + `sim_trades`) 스키마 분리**
- **텔레그램은 3분할 렌더링**. 연속성 문제 없음
- **`docs/a_wanted/user_want_spec.md` 매 세션 초반 필수 읽기**. "뇌 이식 + 자동 수집 + 연속 판단" 이 본질
- **`force` = "cache/snapshot 우회 + 새 실행"**: default False, `market_briefing_now` 09:00 fallback 도 force=true 면 우회
- **데이터 무결성 우선**: KIS API 의 응답 정렬·필드 의미는 항상 의심하고 직접 검증

**이번 세션에 굳힌 판단 (2026-05-06 R4)**
- **canon = 사용자가 받아들인 framework 만 압축**, 박종훈 자료 전체가 아님. 540K tokens 통째로 canon 에 못 박음 → 토큰 비용 + 사용자 시각 매몰. 디테일은 RAG 가 동적 회수
- **framework manifesto (01) vs survival imperatives (02) 분리**: 01 = "어떻게 보는가" (불변 세계관), 02 = "어떻게 행동하는가" (상황 의존, 메타 가이드). **충돌 시 framework 우선**. 02 톤 = "절대 imperative 가 아닌 메타 판단 가이드", 룰 깰 때 이유 명시
- **3축 분할 X — 위기 인식이 통화·사이클 framework 에 흡수**. 분할 너무 잘면 분석가 우선순위 흐려짐. 명제 압축 단위는 인식틀 단위로
- **박종훈 표현 그대로** (사용자 선호) — 압축 시 의역하지 말 것. 출처 표현 유지가 사용자 정체성 형성에 정합
- **Ray Dalio 빅 사이클 5단계 통합** — 박종훈 J커브 단독 framework 의 비관 편향을 균형. 5단계 위치 인식이 자산전략가 의사결정의 가장 큰 입력
- **I6 사용자 추가 룰** (3년 달러 평균가 시그널) — 사용자가 진술한 박종훈 룰을 02 에 명시. RAG 회수가 아닌 canon 에 박힐 만큼 자주 쓰는 룰

**직전 세션 판단 (2026-05-06 R3)**
- **R3 RAG 5-Layer 동작**: ingest 입력 `knowledge/reference/<dept>/`, 인덱스 `data/chroma/<dept>/`, collection name = dept. 학습부 = collection 1:1
- **한국어 임베딩 = BGE-m3 (로컬, 외부 호출 0)**: Chroma `embedding_function=` 명시 wiring 필수. 안 하면 영문 default 로 fallback (이전 코드의 잠복 버그였음). 첫 인덱싱 ~55분 CPU, 멱등 재실행 17.7s (170배)
- **연산 멱등성 = 파일 sha256 hash 비교**: `<rel_path>::0` 청크 metadata 의 `file_hash` 와 비교 → 일치 시 skip. legacy 인덱스는 자동 backfill
- **자료 추가 흐름 5케이스**: (A) 새 학습부 = yaml 한 줄 + sync + ingest, (B) 기존 학습부 정기 = sync + ingest, (C) 사용자 손글 framework = `canon/<dept>/` 직접 작성, (D) 외부 PDF framework 성격 = sync 후 손글 canon, (E) 외부 PDF 디테일 = sync + ingest (reference 만)
- **canon 자동화 절대 금지**: canon = 분석가 정체성. 자동 컴파일하면 정제·압축 품질 폭망 — 손글 유지
- **Windows 콘솔 cp949 함정**: `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` 패턴 적용

**직전 세션 판단 (2026-05-04)**
- **자산복리부(`wealth_compounding`) + 자산전략가(`wealth_strategist`) 명명**: "장기생존부" 가 단순 장기투자와 혼동 → 본질 = 10년·20년+ 생존 + 복리 자산 증식. 거시 framework 도 이 학습부 안에 흡수 (별도 거시분석가 X)
- **canon vs reference 분리 (옵션 D 채택)**: canon = 사용자 손글 압축 framework (1~2 파일, ~2~5K tokens, 매 호출 주입). reference = PDF 추출본 (LLM 비주입, RAG 인덱싱 대상). 자료가 늘어도 정제본은 잘 안 바뀜 — 갱신은 reference sync 만
- **자료 ≠ 추론 품질**: 자료 × 페르소나 × 피드백 = 곱셈. 자료에만 매몰되지 말고 페르소나·피드백 루프도 같은 무게로
- **RAG 우선순위 ↑ (M2.5)**: 박종훈 자료 540K tokens (Sonnet 200K의 270%) 가 RAG 의존. 기존 Phase 3 후순위 → R3 즉시 진입
- **NotebookLM/Gemini Gems 부적합**: 자동화 시스템에는 페르소나·메모리·스케줄·매매일지 통제가 본질. 우리 시스템 = 5 차원 곱셈 → 시중 솔루션과 비교 불가
- **sync 멱등 흐름이 정답**: OneDrive PDF 추가 → `just knowledge-sync <dept>` 1회. 디자인 PDF 한글 글자 공백은 휴리스틱 자동 감지·정규화. 사용자 부담 X
- **박종훈 자료 동적 추가**: 강의 진행 중, ~10+ PDF 추가 예정. canon 정제본 미세 갱신 X, reference sync + RAG 재인덱싱이 정상 흐름
- **평가 질문엔 hedging 금지**: 시스템·자료·결정 평가 시 직설적 결론 먼저, "다만/그러나" 우려 깔지 말 것

**직전 세션 판단 (2026-05-03)**
- **5-Layer 도메인 모델 합의**: 학습부 5 / 분석가 5 (1:1 매핑) / 전략가 3 (단타·스윙·중장기) / 계좌관리자 1 (4 계좌 + 자산배분 흡수) / 출력 채널. plugin 패턴, 분화는 trigger 시
- **분산투자 = 계좌관리자 흡수** (Layer 3 X, Layer 4 모드)
- **manifest list 기반** (`analysts: [...]` / `reads: [...]`) 시작 → 미래 1:N 확장 무비용
- **비용 신경 X**: 추정 월 1~3만원 (Sonnet 4 + cache). 토큰·비용 hook 만 둠

**기초·불변 원칙**
- **파이프라인 구조 = "시간대별 독립 폴더"**, 공통 수집은 `collectors/` 로만 공유, 파이프라인 간 코드 import 금지
- **수동 관심(`watch_positions`) vs AI 시뮬(`sim_positions` + `sim_trades`) 스키마 분리**
- **텔레그램 3분할 렌더링**, 연속성 문제 없음
- **`docs/a_wanted/user_want_spec.md` 매 세션 초반 필수 읽기**. "뇌 이식 + 자동 수집 + 연속 판단" 이 본질
- **`force` = "cache/snapshot 우회 + 새 실행"**: default False, `market_briefing_now` 09:00 fallback 도 force=true 면 우회
- **데이터 무결성 우선**: KIS API 의 응답 정렬·필드 의미는 항상 의심하고 직접 검증
- **시장 전체 vs 종목 단위 KIS 투자자 API 구분**: `inquire-investor-time-by-market` (FHPTJ04030000, 시장 전체 5주체) 만 시장 합계 신뢰
- **KIS OpenAPI 미제공 데이터는 KRX backend** (`data.krx.co.kr/comm/bldAttendant/getJsonData.cmd` POST + Referer/UA, `bld` 파라미터)
- **수급 표시 5주체 세로 나래비**: 개인→외인→기관→금융투자→연기금. 약자 X. 선물도 `[KOSPI200 선물]` 통일
- **`market_briefing_now` 는 LLM 없이 raw 발송** (장중 빈번 호출, 비용·지연 회피)
- **briefing_parts retention = 시계열 누적 + 90일 cleanup cron** (별도 작은 SPEC 백로그)
- **정확한 용어**: VIX≠공포탐욕(CNN FGI), 투신(투자신탁)≠금융투자(증권사 자기매매), 영문 약어는 괄호 한국어 병기
- **서버 `--reload` 비신뢰**: 수정 시마다 수동 재시작

---

## 🔑 재진입 치트시트

```bash
# 환경
.venv/Scripts/python.exe -m pytest pipelines/morning_pre/tests/ -v

# 파이프라인 조회
.venv/Scripts/python.exe -c "from pipelines._registry import list_all_pipelines; print([p.id for p in list_all_pipelines()])"

# 서버 부팅 확인
.venv/Scripts/python.exe -c "from server.main import app; print(len(app.routes))"

# 수동 실행 (서버 떠 있을 때)
curl -X POST http://localhost:8000/api/pipelines/morning_pre/run
```

---

## 🧠 세션 재진입 절차

### 케이스 A — 이전 세션 **그대로** 이어가기 (컨텍스트 보존)

```bash
cd C:\Users\HOME\claude\wevelStock
claude -r        # 세션 목록에서 선택
# 또는
claude -c        # 가장 최근 세션 자동 재개
```

- 내용 파악이 안 되면 에디터에서 [docs/SESSIONS.md](SESSIONS.md) 표를 먼저 확인
- 대화 이력이 그대로 복원되므로 `/resume` 추가로 칠 필요 없음

### 케이스 B — 새 세션에서 **맥락만** 이어받기

```bash
cd C:\Users\HOME\claude\wevelStock
claude
# 프롬프트 뜨면:
/resume
```

1. Claude가 `a_wanted/user_want_spec.md` + 이 파일 + 최신 c_worked 를 읽고 **플랜모드 진입**
2. "지난 세션에 X 했고, 다음 후보는 A/B/C 입니다. 오늘 뭐 하실래요?" 인터뷰
3. 답변 반영 → 플랜 확정 → ExitPlanMode → 구현
4. 마무리할 때 `/wrap-up` — c_worked + SESSIONS.md + 이 파일 자동 갱신

### 판단 기준
- 같은 주제 계속 파고들기 → **케이스 A**
- 다른 주제로 전환 / 오래 쉬었음 → **케이스 B**
