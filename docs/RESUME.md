# RESUME — 작업 재진입 상태판

> 이 파일은 **항상 최신 상태**로 유지됩니다. 세션을 새로 열 때 `/resume` 만 치면 이 파일을 읽고 플랜모드로 브리핑합니다.
>
> 갱신 주기: 의미 있는 작업 완료 후 `/wrap-up` 실행 시 자동 갱신.
> 수동 편집도 자유 — 구조만 지키면 됩니다.

---

## 📍 지금 어디 있나

**현재 위치**: **M3 자산전략가 1명 추론부 조회 인터페이스 가동** — `agents/analysts/wealth_strategist/{persona.md, manifest.yaml}` + `core/inference/run_analyst.py` + CLI(`just chat`/`just ask`) + FastAPI endpoint + Next.js webapp 데모 페이지. 핵심 함수 1개를 4 인터페이스가 wrap. 자산전략가 first call 성공 (canon M1·M2·M3 / C1·C3·C4·C5 / I2~I6 정확 인용, "펀치 카드"·"공포의 톱니바퀴" 박종훈 표현 그대로). 사용자 직접 검증 결과 **응답이 원론·반복 패턴** — canon 19K 압도 + 시장 데이터 부재가 원인. **다음 세션 = 응답 품질 개선 (페르소나 톤 + 시장 데이터 주입) → 나머지 4명 분석가 분화**.

**마지막 작업일**: 2026-05-06
**마지막 세션 로그**: [2026-05-06_m3-wealth-strategist-trial.md](c_worked/2026-05-06_m3-wealth-strategist-trial.md)
**Git**: `main` push 완료. 최신: `docs: wrap-up 2026-05-06 M3 자산전략가 추론부 trial` (이번 세션). 이전: `feat(inference): M3 자산전략가 추론부 조회 인터페이스` / `eca07ef` R4 wrap-up / `feat(knowledge): R4 자산복리부 canon` / `9698878` R3 RAG / `e23edbd` M1 / `1f0d556` M2 원칙부.

---

## 🎯 다음에 할 일 (Top 3)

우선순위 순. 마음에 드는 것 하나를 `/resume` 인터뷰에서 고르세요.

### 1. 분석가 응답 원론·반복 패턴 개선 (PC, 1.5~2.5h)
- **왜**: 사용자 직접 검증 결과 응답이 framework 명제 인용만 반복 — canon 19K 압도 + persona "framework 우선" 톤 + 시장 데이터 부재 + temp 0.4 결합 효과. 실전 투자에 도움이 될지 의구심. user_want_spec "분석팀에 도움이 되는 raw data" 본질 직결.
- **범위**: 단계 1 (5분) — persona 톤 직설화 + response_rules 의 cited 강제 제거 + temp 0.4 → 0.7 → 같은 질문 재시도. 단계 2 (1~1.5h) — `collectors/` (KIS/KRX 환율·지수·VIX·수급) 스냅샷을 user 또는 system 컨텍스트에 자동 첨부 → framework × 실시간 데이터 결합. 단계 1 만으로 부족하면 단계 2 진입.
- **예상**: **1.5~2.5h PC**. 자산전략가 1명만 가지고 진행. 패턴 성공 시 다음 4명에도 동일 적용.

### 2. 나머지 4명 분석가 분화 (PC, 2~3h)
- **왜**: 1명 검증된 패턴 (`agents/analysts/<id>/persona.md` + `manifest.yaml`) 을 4명에 복사. 매매코치 추가하면 자산전략가와 응답 톤 비교로 분화 의미 즉시 입증 (자산전략가 = 거시·원론 / 매매코치 = 실전·시그널).
- **범위**: `agents/analysts/{principle_guardian, trade_coach, stock_analyst, news_curator}/{persona.md, manifest.yaml}` 4 set. 각 manifest 의 `reads:` 가 학습부별 다름. canon 19K 자동 주입은 5명 모두 공통.
- **예상**: 2~3h. Top 1 패턴 안정 후 진입.

### 3. 종목분석부 자료 ingest + JSONL 매월 폴더 도입 (PC, 1.5h)
- **왜**: `rag_docs/logchart/` (~288KB) 즉시 가용 — 종목분석가 `reads:[stock-analysis]` 의 RAG 기반. 동시에 분석가 5명 분화 직전 = JSONL 폭발 임계점 (5K 파일) 진입 — 매월 폴더 + 90일 retention cron 도입 적기.
- **범위**: (a) `rag_docs/logchart/` → `knowledge/reference/stock-analysis/` + `config/knowledge_sources.yaml` + `just knowledge-sync` + `just knowledge-ingest`. (b) `data/analyst_queries/<id>/<YYYY-MM>/` 폴더 분리 + retention cron 추가.
- **예상**: 1.5h. Top 2 와 묶어 하면 자연스러움.

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
- **`agents/analysts/wealth_strategist/{persona.md, manifest.yaml}`** (M3) — Layer 2 첫 분석가. R4 canon 톤 그대로 + `reads:[wealth_compounding]` + max_tokens 4000 + temp 0.4
- **`core/inference/run_analyst.py`** (M3) — 분석가 단일 호출 핵심 함수. 멀티턴 messages 배열 수용 + `build_pipeline_prompt` + `call_llm` + metadata (system char/RAG chunks/cache tokens/cost/latency). CLI/REPL/FastAPI/webapp 4 인터페이스 모두 wrap
- **`scripts/{chat_analyst,ask_analyst}.py` + `just {chat,ask}` 레시피** (M3) — REPL 멀티턴 + 단일 턴 CLI. stdin/stdout utf-8 reconfigure + surrogate normalize + JSONL 자동 저장 (`data/analyst_queries/<id>/<dt>.jsonl`) + 누적 토큰 200K 가시화
- **`server/api/analyst_chat.py`** (M3) — `POST /api/analysts/{id}/chat` 멀티턴 endpoint + `GET /api/analysts/{id}` 메타. main.py router include
- **`webapp/src/app/analyst-chat/page.tsx` + 메인 페이지 카드** (M3) — textarea + Ctrl+Enter + 멀티턴 누적 + 매 턴 metadata 박스 + `/clear` + 누적 토큰·비용. Next.js build 성공 (2.63 kB)
- **pytest 60 passed** (M1, M2, R1, R3, R4, M3 회귀 모두 통과)
- SPEC 3종: **BRIEFING-ON-DEMAND-001** + **BRIEFING-TIMEBASED-002** + **INFRA-RAG-001**

### 미완 또는 의도적 공백
- **분석가 응답 원론·반복 패턴** — M3 검증 결과: canon 19K 압도 + persona "framework 우선" 톤 + 시장 데이터 부재 + temp 0.4 결합. **다음 세션 Top 1**
- **나머지 4명 분석가 분화** (원칙수호자·매매코치·종목분석가·뉴스큐레이터) — Top 1 패턴 안정 후 동일 패턴 복사 (Top 2)
- **JSONL 매월 폴더 분리 + 90일 retention cron** — 5K 파일 임계점 도달 전 도입 (분석가 5명 분화 직전, Top 3 와 묶음)
- **자동 컴팩트 (50+ turn 대화 압축)** — 1 conversation 50 turn 넘으면 요약 호출로 messages 압축. 백로그
- **텔레그램 `/ask` 명령 wrap** — `core/inference/run_analyst()` 에 텔레그램 핸들러 1개 wrap 만 추가하면 모바일 사용 가능. 1명 검증 후
- **배치 자동 트리거 (T2) + team_outputs DB 저장** — 시장 컨텍스트 자동 주입 + 일정 주기 분석가 호출 → DB 누적. user_want_spec 의 자동 흐름. 후속 단계
- **`KnowledgeChunk.team_id` 필드** 가 dept 값을 담음 (legacy 호환). 별도 cleanup 세션에서 `dept_id` 로 rename
- **`compose.py`의 legacy `build_system_prompt` / `load_canon` / `load_persona`** — `get_team` 의존, 호출처 0. cleanup 세션에서 삭제
- **chat REPL stdin pipe 자동화** — PowerShell here-string 한국어 인코딩 깨짐. 사용자 콘솔 직접 입력은 OK (stdin reconfigure 적용됨). 자동 검증 필요 시 별도 스크립트로 우회
- **ANTHROPIC_API_KEY 있어도 Gemini auto-fallback 발생** — config provider 흐름 검증 필요할 수도. 비용 더 저렴해서 일단 무관
- **박종훈 Vol 2/3 OCR 미실행** (4 파일 0 chars, 이미지 PDF) — `ocrmypdf` + tesseract 도입 백로그
- **다른 학습부 자료 (실전·종목분석·뉴스) 미채움** — 종목분석부는 `rag_docs/logchart/` 즉시 가용 (Top 3)
- **전략가 3 / 계좌관리자 / 출력 채널 확장** — M4~M6, 한참 후
- **선물 수급 3주체 → 5주체 확장** — KRX MDCSTAT bld 캡쳐, 백로그
- **Phase 3 `market_briefing_close`** — 5-Layer M3 완료 후 자연 진입
- **dead code 청산** (`market_investor_summary`/`foreign_institution_top`/`core/registry.py`/`rollup.py`) — 회귀 리스크 큰 별도 세션
- **KOSPI200 선물 정확 가격** — 지수(2001) 대체. 선물옵션 API 별도
- **`rag_docs/logchart/` (untracked, ~288KB)** — 차트 교육 자료. 종목분석부 학습부 첫 자료 후보 (Top 3)
- **`docs/KNOWLEDGE-WORKFLOW.md` 5케이스 가이드** — 자료 추가 흐름차트 미작성

### 꼭 알아둘 판단

**기초·불변 원칙**
- **파이프라인 구조 = "시간대별 독립 폴더"**. 공통 수집은 `collectors/` 로만 공유, 파이프라인 간 코드 import 금지
- **수동 관심(`watch_positions`)과 AI 시뮬(`sim_positions` + `sim_trades`) 스키마 분리**
- **텔레그램은 3분할 렌더링**. 연속성 문제 없음
- **`docs/a_wanted/user_want_spec.md` 매 세션 초반 필수 읽기**. "뇌 이식 + 자동 수집 + 연속 판단" 이 본질
- **`force` = "cache/snapshot 우회 + 새 실행"**: default False, `market_briefing_now` 09:00 fallback 도 force=true 면 우회
- **데이터 무결성 우선**: KIS API 의 응답 정렬·필드 의미는 항상 의심하고 직접 검증

**이번 세션에 굳힌 판단 (2026-05-06 M3)**
- **추론부 조회 ≠ 알림 파이프라인**: 분석가는 별도 호출 흐름 (CLI/REPL/FastAPI/webapp). 기존 `market_briefing_pre`/`market_briefing_now` 알림 파이프라인 안에 분석가 끼워넣지 않음
- **인터페이스 = 핵심 함수 1개 wrap**: `core/inference/run_analyst.py` 가 manifest+persona+canon+RAG+memory+messages → Anthropic 호출 → metadata 한 묶음. CLI(`just chat`/`just ask`), REPL, FastAPI endpoint, webapp 페이지 모두 wrap. 텔레그램·MCP 도 같은 패턴
- **검증 우선 → 점진 확산**: 5명 일괄 분화 X. 자산전략가 1명 가동 → 패턴 안정 → 4명 적용. 같은 패턴 복사가 안전
- **메모리 두 차원 분리**: 대화 메모리 (한 conversation 안 multi-turn messages, REPL 누적 + JSONL 디스크) vs 에이전트 시계열 메모리 (`core/memory/` SQLite, system prompt 자동 주입). API 서버는 stateless — 모든 대화 통제권 = 로컬
- **JSONL retention 단계 점진 도입**: A (그대로, 1년 22MB) → B (매월 폴더 + 90일 retention, 5K 파일 임계 = 분석가 5명 분화 직전) → C (SQLite 마이그, 50K 임계). 검증 단계엔 A 면 충분
- **응답 원론·반복 패턴 발견**: canon 19K 압도 + persona "framework 우선" 톤 + 시장 데이터 부재 + temp 0.4 → 추상 명제 인용 반복. 단기 (톤·temp) → 중기 (시장 데이터 자동 주입) 두 갈래로 풀 것

**직전 세션 판단 (2026-05-06 R4)**
- **canon = 사용자가 받아들인 framework 만 압축**, 박종훈 자료 전체가 아님. 540K tokens 통째로 canon 에 못 박음 → 토큰 비용 + 사용자 시각 매몰. 디테일은 RAG 가 동적 회수
- **framework manifesto (01) vs survival imperatives (02) 분리**: 01 = "어떻게 보는가" (불변 세계관), 02 = "어떻게 행동하는가" (상황 의존, 메타 가이드). **충돌 시 framework 우선**
- **3축 분할 X — 위기 인식이 통화·사이클 framework 에 흡수**. 분할 너무 잘면 분석가 우선순위 흐려짐
- **박종훈 표현 그대로** (사용자 선호) — 압축 시 의역하지 말 것. 출처 표현 유지가 사용자 정체성 형성에 정합
- **Ray Dalio 빅 사이클 5단계 통합** — 박종훈 J커브 단독 framework 의 비관 편향을 균형
- **I6 사용자 추가 룰** (3년 달러 평균가 시그널) — RAG 회수가 아닌 canon 에 박힐 만큼 자주 쓰는 룰

**직전 세션 판단 (2026-05-06 R3)**
- **R3 RAG 5-Layer 동작**: ingest 입력 `knowledge/reference/<dept>/`, 인덱스 `data/chroma/<dept>/`, collection name = dept
- **한국어 임베딩 = BGE-m3 (로컬, 외부 호출 0)**: Chroma `embedding_function=` 명시 wiring 필수. 첫 인덱싱 ~55분, 멱등 재실행 17.7s (170배)
- **연산 멱등성 = 파일 sha256 hash 비교**: `file_hash` metadata. legacy 인덱스 자동 backfill
- **자료 추가 흐름 5케이스**: (A) 새 학습부 / (B) 기존 정기 / (C) 손글 canon / (D) PDF framework 성격 / (E) PDF 디테일
- **canon 자동화 절대 금지**: canon = 분석가 정체성. 자동 컴파일하면 정제·압축 품질 폭망 — 손글 유지
- **Windows 콘솔 cp949 함정**: stdin/stdout/stderr 모두 `reconfigure(encoding='utf-8', errors='replace')`

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
