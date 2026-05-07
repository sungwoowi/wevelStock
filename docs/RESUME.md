# RESUME — 작업 재진입 상태판

> 이 파일은 **항상 최신 상태**로 유지됩니다. 세션을 새로 열 때 `/resume` 만 치면 이 파일을 읽고 플랜모드로 브리핑합니다.
>
> 갱신 주기: 의미 있는 작업 완료 후 `/wrap-up` 실행 시 자동 갱신.
> 수동 편집도 자유 — 구조만 지키면 됩니다.

---

## 📍 지금 어디 있나

**현재 위치**: **단계 1 자산전략가 톤 직설화 + LLM provider 선택 옵션 가동 완료** — persona.md 응답 원칙 L32 "명제 그대로 인용" → "명제 ID 인용 필수, 적용은 사용자 맥락 재구성" + L34 인접 명제 추론 허용, manifest temp 0.4→0.7. 도중 발견된 인프라 결함 3건 (Gemini 503 silent mock fallback, claude_code Windows cmdline 8K 한계, claude_code 무효 ANTHROPIC_API_KEY 상속) 동시 해결. 사용자 추가 요청으로 명시 provider 선택 (CLI `--provider` 플래그 / API `provider` 필드 / webapp 토글 3개 + `/api/config/llm` 동적 라벨) 까지 확장. 톤 비교 결과: Claude Code 직설·T-style / Gemini 구조적·다각적 분기 확인. **다음 세션 Top 1 = 단계 2 시장 스냅샷 자동 주입**.

**마지막 작업일**: 2026-05-08
**마지막 세션 로그**: [2026-05-08_analyst-tone-tweak-and-provider-selection.md](c_worked/2026-05-08_analyst-tone-tweak-and-provider-selection.md)
**Git**: `main` 3 ahead of origin/main (push 미실시). 최신: `a087744 feat(inference): provider 선택 옵션` / `af4f7e4 feat(llm): provider fallback chain + claude_code 안정화` / `db875e8 feat(wealth_strategist): 톤 직설화 + temp 0.7`. 이전: `2ffd351` 2026-05-07 wrap-up / `6a1d1c8` briefing now cron + UI / `56dd63b` M3 wrap-up / `e9a36f0` M3 추론부.

---

## 🎯 다음에 할 일 (Top 3)

우선순위 순. 마음에 드는 것 하나를 `/resume` 인터뷰에서 고르세요.

### 1. 단계 2 — 시장 스냅샷 자동 주입 (PC, 1~1.5h)
- **왜**: 단계 1 (톤 직설화 + temp 0.7) 으로 framework 명제 적용·재구성·인접 추론은 살아남. 그러나 실제 수치 (환율·VIX·수급) 부재 → 응답이 framework 적용에만 머물고 사용자 맥락에 진짜로 결합 안 됨. user_want_spec "오감 + 뇌" 본질 직결.
- **범위**: `collectors/snapshot.py` 신규 — `async def build_market_snapshot(*, kis, krx, max_age_seconds=300) -> tuple[dict, bool]` (8 collector 병렬 + 5분 인메모리 캐시 + cache_hit 반환). `core/knowledge/compose.py:build_pipeline_prompt` RAG 직전 새 블록. UX = 신선 콜 시 "[시장 스냅샷 수집 중... ~30s]" stderr / 캐시 히트 무표시. CLI/REPL/FastAPI/webapp 4 호출처 자동 적용.
- **예상**: 1~1.5h PC.

### 2. 나머지 4명 분석가 분화 (PC, 2~3h)
- **왜**: 단계 1 + provider 선택 패턴 검증 끝남. 같은 manifest+persona 패턴으로 4명 복사. 매매코치 추가하면 자산전략가와 응답 톤 비교로 분화 의미 즉시 입증 (자산전략가 = 거시·원론 / 매매코치 = 실전·시그널).
- **범위**: `agents/analysts/{principle_guardian, trade_coach, stock_analyst, news_curator}/{persona.md, manifest.yaml}` 4 set. 각 manifest 의 `reads:` 가 학습부별 다름. canon 19K 자동 주입은 5명 모두 공통. temp 0.7 + 인접 명제 추론 허용 패턴 디폴트 적용.
- **예상**: 2~3h. Top 1 단계 2 안정 후 진입.

### 3. claude_code cost 라벨 + analyst-chat SSR 깜빡임 (PC, 30분)
- **왜**: Pro/Max 구독은 호출당 추가 비용 0인데 metadata 가 토큰 환산 $0.14 표시 (오해 소지). 이전부터 누적된 SSR 첫 렌더 "분석가 메타 로드 실패" 빨간 텍스트도 묶어서.
- **범위**: `webapp/src/app/analyst-chat/page.tsx` MetadataBar 에서 `provider_used==claude_code` 면 `$0 (subscription)` 라벨. SSR 가드 (mount 후 첫 fetch 까지 메타 영역 비워두기 또는 placeholder).
- **예상**: 30분 PC.

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
- **`core/inference/run_analyst.py`** (M3) — 분석가 단일 호출 핵심 함수. 멀티턴 messages 배열 수용 + `build_pipeline_prompt` + `call_llm` + metadata (system char/RAG chunks/cache tokens/cost/latency/is_mock/upstream_error). CLI/REPL/FastAPI/webapp 4 인터페이스 모두 wrap
- **`scripts/{chat_analyst,ask_analyst}.py` + `just {chat,ask}` 레시피** (M3) — REPL 멀티턴 + 단일 턴 CLI. stdin/stdout utf-8 reconfigure + surrogate normalize + JSONL 자동 저장 (`data/analyst_queries/<id>/<dt>.jsonl`) + 누적 토큰 200K 가시화 + mock/upstream_error 라벨
- **`server/api/analyst_chat.py`** (M3) — `POST /api/analysts/{id}/chat` 멀티턴 endpoint + `GET /api/analysts/{id}` 메타
- **`webapp/src/app/analyst-chat/page.tsx`** (M3) — 멀티턴 채팅 페이지. mock 응답 시 ⚠ 뱃지 + upstream error 빨간 표시
- **`market_briefing_now` 자동 cron** (2026-05-07) — `30 9,12,14 * * 1-5` 평일 정규장 3회 (시초 정리 / 점심 / 마감 1시간 전). `pipeline::market_briefing_now::0` 등록 검증 + 18:37 임시 cron 발동 검증 통과
- **`core/briefing/parts_store.get_recent_runs()`** + **`core/briefing/render.render_pipeline()` dispatcher** + **`GET /api/briefings/{id}/recent?limit=N`** (2026-05-07) — 최근 N runs 의 (run_id, generated_at, parts, rendered 텔레그램 텍스트) 묶음 반환. 텔레그램 봇·webapp 공용 진입점
- **`webapp/src/components/BriefingPartsCard.tsx`** (2026-05-07) — 좌측 run 리스트 (날짜 그룹 + AUTO/BOT 뱃지 + 5초 polling) + 우측 텔레그램 텍스트 (가독성 ↑) + JSON 디버그 토글. 시계열 누적 가시화
- **`webapp/src/components/AlertList.tsx`** (2026-05-07) — "최근 자동 푸시 알림" 라벨 + 부제 (봇 응답은 브리핑 이력에 있음 명시)
- **render.py KRX 정규장 라벨 명시** (2026-05-07) — 국내지수·강세섹터·주도주 3군데 "KRX 정규장 전일 종가 대비" prefix. 키움 HTS 의 NXT 통합 가격과 혼동 회피
- **자산전략가 단계 1 톤 직설화** (2026-05-08) — `persona.md` L32 "명제 ID 인용 필수, 적용은 사용자 맥락 재구성" + L34 인접 명제 추론 허용 + manifest temp 0.4→0.7. cited 형식 + 금기 영역 유지
- **LLM provider fallback chain** (2026-05-08) — `core/llm/client.py` `_dispatch_provider` 가 gemini → claude_code → mock 자동 폴백. `provider` kwarg 지정 시 fallback X (명시 backend 만 시도, 에러 propagate)
- **claude_code Windows·OAuth 안정화** (2026-05-08) — `core/llm/claude_code_backend.py` 가 long system prompt 시 stdin `[SYSTEM]/[USER]` 결합 (cmd.exe 8K argv 우회) + `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` env strip (Pro/Max keychain OAuth 강제)
- **Provider 선택 옵션 (CLI/API/webapp)** (2026-05-08) — `--provider` 플래그 (`scripts/{ask,chat}_analyst.py`) + `ChatRequest.provider` API 필드 (`server/api/analyst_chat.py`) + webapp LLM 토글 3개 (`webapp/src/app/analyst-chat/page.tsx`) + `GET /api/config/llm` 동적 라벨 endpoint (`server/api/config.py`). 응답 metadata 에 `provider_requested`/`provider_used` 노출
- **pytest 60 passed** (M1, M2, R1, R3, R4, M3, 2026-05-07~05-08 회귀 모두 통과)
- SPEC 3종: **BRIEFING-ON-DEMAND-001** + **BRIEFING-TIMEBASED-002** + **INFRA-RAG-001**

### 미완 또는 의도적 공백
- **단계 2 시장 스냅샷 자동 주입** — 단계 1 톤 변화는 살아남았으나 응답이 framework 적용에만 머물고 실 수치 결합 X. **다음 세션 Top 1**. `collectors/snapshot.py` + 5분 캐시 + compose 블록 주입
- **claude_code cost 표시 misleading** — Pro/Max 구독 추가 비용 0인데 metadata 가 토큰 환산 $0.14 표시. webapp MetadataBar 라벨 보완 필요 (Top 3 와 묶음)
- **NXT 통합 시세 도입** — KIS API 가 명시 미지원 (`_AL`/`_NX` suffix 빈 응답, GitHub repo 0건). 키움은 suffix 패턴 지원하나 KIS 와 다름. KRX backend + 키움 OpenAPI 등 다중 source 결합 SPEC 필요 — 별도 백로그
- **daily_briefing legacy 잔재** (`core/registry.py`, `core/config/schema.py`, `config/defaults.yaml` 의 daily_briefing 섹션) — webapp 측 `BriefingCard` 는 2026-05-07 제거됨. server/config 측은 의존성 그래프 큰 cleanup 세션 백로그
- **analyst-chat SSR 깜빡임** — 첫 렌더 시 "분석가 메타 로드 실패" 빨간 텍스트. hydrate 후 fetch 가 채우는 정상 동작이지만 UX 백로그
- **KRX backend 정규장 종가 일치 검증** — KIS 일봉 vs KRX 공식 종가 100% 일치 추가 보강. 1분 작업, 보강 백로그
- **나머지 4명 분석가 분화** (원칙수호자·매매코치·종목분석가·뉴스큐레이터) — Top 1 패턴 안정 후 동일 패턴 복사 (Top 2)
- **JSONL 매월 폴더 분리 + 90일 retention cron** — 5K 파일 임계점 도달 전 도입 (분석가 5명 분화 직전, Top 3 와 묶음)
- **자동 컴팩트 (50+ turn 대화 압축)** — 1 conversation 50 turn 넘으면 요약 호출로 messages 압축. 백로그
- **텔레그램 `/ask` 명령 wrap** — `core/inference/run_analyst()` 에 텔레그램 핸들러 1개 wrap 만 추가하면 모바일 사용 가능. 1명 검증 후
- **배치 자동 트리거 (T2) + team_outputs DB 저장** — 시장 컨텍스트 자동 주입 + 일정 주기 분석가 호출 → DB 누적. user_want_spec 의 자동 흐름. 후속 단계
- **`KnowledgeChunk.team_id` 필드** 가 dept 값을 담음 (legacy 호환). 별도 cleanup 세션에서 `dept_id` 로 rename
- **`compose.py`의 legacy `build_system_prompt` / `load_canon` / `load_persona`** — `get_team` 의존, 호출처 0. cleanup 세션에서 삭제
- **chat REPL stdin pipe 자동화** — PowerShell here-string 한국어 인코딩 깨짐. 사용자 콘솔 직접 입력은 OK (stdin reconfigure 적용됨). 자동 검증 필요 시 별도 스크립트로 우회
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

**이번 세션에 굳힌 판단 (2026-05-08 자산전략가 톤 + provider 선택)**
- **단계 1 (persona 톤·temp) 만으론 부족 — 단계 2 시장 스냅샷 필요**: 톤 직설화·인접 명제 추론은 살아났으나 실 수치 부재로 framework 적용에 머묾. 다음 세션 Top 1
- **자동 fallback ≠ 명시 선택**: `provider` kwarg None = config + 자동 폴백 / 명시 = 그 backend 만 + 에러 propagate. 사용자가 톤 비교할 때는 명시 모드, 평소엔 자동
- **gemini → claude_code → mock 폴백 체인**: Gemini 503 (transient) 같은 일시 장애에 ANTHROPIC 키 없어도 Pro/Max 구독으로 응답 보존. raw 에 `fallback_used` 박힘
- **claude_code 는 OAuth 강제 경로**: subprocess env 에서 `ANTHROPIC_API_KEY`/`AUTH_TOKEN` strip → keychain OAuth fallthrough. API key auth 원하면 `provider=anthropic`. 두 경로 분리
- **Windows cmd.exe 8K argv 한계 = stdin 결합으로 우회**: 19K canon spawn 시 long system 은 `[SYSTEM]/[USER]` stdin payload 로 보냄. 짧으면 정식 argv 유지
- **톤 비교 결과**: Claude Code (Sonnet 4.6) 직설·단호·T-style — persona "결론 먼저, hedging 금지" 룰 직결 / Gemini (2.5 Flash) 구조적·다각적·인접 명제 추론 풍부. 용도별 분리 가능

**직전 세션 판단 (2026-05-07 브리핑 이력 UI + cron + KRX 라벨)**
- **3차원 분리 (SPEC 정합)**: 추론부 조회 (`run_analyst` + analyst_chat) / 알림 자동 푸시 (`notifications_log` + AlertList) / 브리핑 이력 (`briefing_parts` 시계열 + BriefingPartsCard). 봇 명령 응답은 `notify=False` 흐름이라 알림 X = 브리핑 이력
- **briefing_parts = run_id 단위 시계열 누적** (일자 단위 upsert X). 같은 날 force 여러 번 = 다른 run_id = 새 row
- **render dispatcher 1개 함수 → 모든 채널 wrap**: `render_pipeline(pipeline_id, parts, status)` 가 텔레그램 봇·webapp recent endpoint 동시 사용. 신 파이프라인 = `_PIPELINE_RENDERERS` 1줄 추가
- **KIS prdy_ctrt = KRX 정규장 종가 대비 정확** (검증). KIS API NXT 통합 미지원 → 라벨에 "KRX 정규장" 명시로 혼동 회피

**직전 세션 판단 (2026-05-06 M3)**
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
