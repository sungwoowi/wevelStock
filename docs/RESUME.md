# RESUME — 작업 재진입 상태판

> 이 파일은 **항상 최신 상태**로 유지됩니다. 세션을 새로 열 때 `/resume` 만 치면 이 파일을 읽고 플랜모드로 브리핑합니다.
>
> 갱신 주기: 의미 있는 작업 완료 후 `/wrap-up` 실행 시 자동 갱신.
> 수동 편집도 자유 — 구조만 지키면 됩니다.

---

## 📍 지금 어디 있나

**현재 위치**: **Top 2 (cost 라벨 + SSR 가드) 완료 + 시장 스냅샷 DB-first 중복 발견** — `webapp/src/app/analyst-chat/page.tsx` 단일 파일 4 곳 수정 (claude_code provider 시 cost 라벨 `$0 (subscription)` + 누적 비용 제외 + analystMeta 3-state `undefined|null|object` 로 SSR 첫 렌더 빨간 깜빡임 제거). 검증 4건 통과. 검증 도중 사용자가 "외부 LLM 응답 자체가 느리다 (~40s)" 본질 제기 → `collectors/snapshot.py` 7 collector 가 `pipelines/market_briefing_{now,pre}/stages/collect_*` 와 동일 함수 호출 (100% 중복) 임을 식별. **옵션 A (DB-first hybrid) 결정** + 백로그 등재. 다음 세션 Top 1 = 옵션 A 구현 (분화 직전), Top 2 = 4명 분석가 분화 + canon 분기.

**마지막 작업일**: 2026-05-08
**마지막 세션 로그**: [2026-05-08_cost-label-ssr-guard-and-db-first-backlog.md](c_worked/2026-05-08_cost-label-ssr-guard-and-db-first-backlog.md)
**Git**: 이번 세션 push 완료 (`cf7eeb9..1e65c69`). 최신: `1e65c69 docs(resume): 옵션 A 백로그` / `53e657b feat(webapp): claude_code cost 라벨 + SSR 가드`. 이전: `cf7eeb9 docs: wrap-up 2026-05-08 단계 2 시장 스냅샷` / `1debbe6 feat(inference): 단계 2 시장 스냅샷` / `75cf1a0` 자산전략가 톤 + provider 선택 wrap-up. 본 wrap-up 커밋 후 push 는 사용자 요청 시.

---

## 🎯 다음에 할 일 (Top 3)

우선순위 순. 마음에 드는 것 하나를 `/resume` 인터뷰에서 고르세요.

### 1. 시장 스냅샷 DB-first hybrid (옵션 A, PC, 1.5~2h) — 분화 직전 처리
- **왜**: `collectors/snapshot.py` 7 collector 가 `pipelines/market_briefing_{now,pre}/stages/collect_*` 와 **동일 함수 호출** (100% 중복). 분석가 호출마다 cold fetch ~30s + 5-Layer "수집팀 → 분석팀" 단방향 위반. 분석가 응답 latency 40s (cold) → ~5s (gemini) / ~15s (claude_code).
- **범위**: `collectors/snapshot.py:build_market_snapshot()` 가 `parts_store.get_latest_parts_with_age()` 우선 → 신선도 임계 (한국 6h / 미국 24h) 초과 또는 부재 시 collector fallback. `briefing_parts.data_json` → snapshot dict 어댑터. `market_briefing_pre` overnight part 형식 (raw vs LLM 가공) 확인 필요.
- **예상**: 1.5~2h PC. Top 2 (분화) 직전 또는 같이.

### 2. 4명 분석가 분화 + canon 분기 (옵션 B) 묶음 (PC, 3~4h)
- **왜**: 자산전략가 통합 canon 답변이 영역 침범 (7계명·심법·박종훈 모두 인용). 5-Layer 1:1 매핑 정합 위해 분화 + canon 분기 함께 처리. 자산전략가 1명만 좁히면 검증 답변 퀄리티만 깎임 → 묶음 처리가 정합. 매매코치 추가하면 자산전략가와 톤 비교로 분화 의미 즉시 입증.
- **범위**: `agents/analysts/{principle_guardian, trade_coach, stock_analyst, news_curator}/{persona.md, manifest.yaml}` 4 set + `core/knowledge/compose.py:load_shared_canon()` 가 manifest `reads:` 받아 해당 학습부 canon 만 합치도록 분기 + `run_analyst.py` 가 spec.reads 패스. temp 0.7 + 인접 명제 추론 허용 패턴 디폴트.
- **예상**: 3~4h PC.

### 3. 종목분석부 자료 첫 ingest (PC, 1h)
- **왜**: `rag_docs/logchart/` (untracked, ~288KB) 차트 교육 자료 가용. 종목분석가 분화 시 RAG 즉시 활용. 5 학습부 중 종목분석부가 마지막 미채움.
- **범위**: `knowledge/reference/stock_analysis/` 로 이동 + `just knowledge-sync stock_analysis` (또는 `knowledge.py ingest`) + 검증 회수.
- **예상**: 1h PC. Top 2 (분화) 진입 전 또는 같이 묶음.

(추가 백로그: streaming SSE 도입 = FE/BE 양쪽, ~3-4h. provider default = gemini 토글 5분.)

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
- **단계 2 시장 스냅샷 자동 주입** (2026-05-08) — `collectors/snapshot.py` 신규 (7 collector 병렬 + 5분 인메모리 캐시 + `asyncio.gather(return_exceptions=True)` partial-failure + cold call stderr 진행 표시 + `MarketSnapshot` dataclass + `render_snapshot_md` 안전 렌더). `compose.build_pipeline_prompt` 의 RAG 직전 [3] 블록 (`market_snapshot_md` kwarg, `cache_control` 없음 — 5분 갱신). `run_analyst` metadata 4키 (`snapshot_age_seconds`/`fetch_seconds`/`cache_hit`/`failures`). 모든 분석가 자동 공유 (옵션 A 풀세트). 5-Layer 분석가 모두 동일 raw 베이스
- **claude_code cost 라벨 frontend 분기 + analyst-chat SSR 가드** (2026-05-08 오후) — `webapp/src/app/analyst-chat/page.tsx` 4 곳 수정. MetadataBar/누적 비용에서 `provider_used==="claude_code"` 시 `cost $0 (subscription)` 표기 (Pro/Max 구독 호출당 추가 비용 0 정합). `analystMeta` state 를 `null` → `undefined | null | object` 3-state 로 확장 (undefined 면 회색 "분석가 메타 로딩…" placeholder, null 만 빨간 "로드 실패") → SSR 첫 렌더 빨간 깜빡임 제거. 백엔드 `total_cost_usd` 메타 의미는 유지 (표시 책임만 frontend 분리)
- **분석가 응답에 실 수치 결합 검증** (2026-05-08) — Claude Code 호출에서 "현재 1,456원이니 사실상 지금이 그 시점이다", "3년 달러 평균가가 1,370원이고 지금 1,456원이면 이미 평균 위다" 처럼 framework 명제 + I6 시그널 + 실 USDKRW 결합. cache hit (read 14,795 토큰), prompt 25,988 chars, latency 40.1s, $0.16
- **pytest 68 passed** (기존 60 + 신규 `tests/test_market_snapshot.py` 8 테스트)
- SPEC 3종: **BRIEFING-ON-DEMAND-001** + **BRIEFING-TIMEBASED-002** + **INFRA-RAG-001**

### 미완 또는 의도적 공백
- **시장 스냅샷 DB-first hybrid (옵션 A)** — `collectors/snapshot.py` 7 collector 가 `briefing_now/pre` stages 와 100% 중복. 분석가 호출마다 cold fetch 30s + 5-Layer 단방향 위반. **다음 세션 Top 1** (분화 직전). `parts_store.get_latest_parts_with_age()` 우선 → stale 시 collector fallback. 효과: 응답 latency 40s → 5~15s
- **4명 분석가 분화 + canon 분기 (옵션 B) 묶음** — 자산전략가 통합 canon 답변이 영역 침범 (7계명·심법까지). **다음 세션 Top 2**. `agents/analysts/{principle_guardian, trade_coach, stock_analyst, news_curator}/{persona, manifest}` 4 set + `compose.load_shared_canon()` reads 분기 + run_analyst 패스. 단독 persona 가드는 시기상조라 의도적 미적용
- **streaming (SSE) 미도입** — 동일 모델도 체감 latency 5~10배 차이 (ChatGPT/Claude.ai 가 안 느린 이유 = 직접 SDK + streaming). FE/BE 양쪽 SSE 손, ~3-4h 별도 SPEC. 분석가는 챗봇이 아니라 알림 Agent (user_want_spec) 라 자동 호출은 무관, webapp 채팅 검증/디버그 UX 만 영향
- **provider default = gemini 토글** — 5분 작업, 옵션 A 와 묶지 않고 보류
- **Layer 3 종합 판단부 (단타·스윙·중장기 전략가 3종)** — CLAUDE.md L100-105 에 이미 설계 (M4 마일스톤). 단타전략가 (종목분석가+뉴스큐레이터) / 스윙전략가 (종목분석가+자산전략가+매매코치) / 중장기전략가 (자산전략가+종목분석가+원칙수호자). 분석가 5명 분화 후 자연 진입
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

**이번 세션에 굳힌 판단 (2026-05-08 오후 cost 라벨 + DB-first 발견)**
- **분석가 collector 직호출 = 5-Layer 단방향 위반**: snapshot.py 7 collector 가 briefing_{now,pre} stages 와 100% 중복 함수 호출. 본질은 "수집팀 (briefing) 이 cron 으로 raw 적재 → 분석팀 (분석가) 이 DB 에서 읽기" (user_want_spec 의 "수집팀 = 오감 / 분석팀 = 뇌"). 옵션 A 가 본질 정합 + cold fetch 30s 제거 동시 해결
- **cost 표시 책임 분리**: 백엔드 metadata 의 토큰 환산 가격은 유지 (다른 비교에 활용 여지), frontend 에서만 provider 별 라벨 가공. 백엔드 `total_cost_usd` 를 0 으로 강제하지 않음
- **analystMeta 3-state 패턴**: `null` 단일 상태로는 "로딩 중" 과 "fetch 실패" 구분 불가. `undefined | null | object` 3-state 가 BriefingPartsCard 의 SWR `isLoading` 패턴 등가 (raw fetch 직접 구현). 다른 raw fetch 컴포넌트도 동일 패턴 적용 가능
- **claude_code latency 본질**: subprocess + OAuth keychain 오버헤드 ~10s + streaming 미사용. ChatGPT/Claude.ai 가 빠른 이유 = 직접 SDK + streaming. wevelStock 분석가는 챗봇이 아니라 알림 Agent (user_want_spec) — 자동 호출 시 무관, webapp 채팅은 검증/디버그 UX

**직전 세션 판단 (2026-05-08 단계 2 시장 스냅샷)**
- **canon 통합 vs 분화 모순**: `load_shared_canon()` 5 학습부 통합 (5-Layer 베이스 = "통합 두뇌") 와 `manifest.reads:` 1:1 매핑 (분석가별 영역) 사이 불일치. 4명 분화 + 옵션 B (canon 분기) 로 동시 해소
- **시기 묶음 처리**: 자산전략가 1명 검증 단계에 옵션 B 단독 도입은 시기상조 — 4명 분화 (Top 2) 와 묶음. 분화 직전엔 임시 봉합 X
- **Layer 3 = "투자 종합 판단부"**: CLAUDE.md L100-105 이미 설계 (M4). 단타·스윙·중장기 전략가 3종, 분석가 manifest `analysts:` 라우팅. "자산전략가" 명칭은 Layer 2 분석가 (자산 도메인 1명) — Layer 3 의 단타/스윙/중장기 전략가 3종과 다름
- **시장 스냅샷 = 캐시 분리선 뒤**: canon/persona/memory 는 cache_control ephemeral / snapshot/RAG/rules 는 비캐시. 5분마다 스냅샷 갱신 → 캐시 효율 손해 없음
- **partial failure = 7계명 #6 정합**: `asyncio.gather(return_exceptions=True)` + `[수집 실패 - 사유]` 표기. 분석가가 데이터 부재를 인지해야 추측 회피

**직전 세션 판단 (2026-05-08 자산전략가 톤 + provider 선택)**
- **자동 fallback ≠ 명시 선택**: `provider` kwarg None = config + 자동 폴백 / 명시 = 그 backend 만 + 에러 propagate. 톤 비교용은 명시, 평소엔 자동
- **gemini → claude_code → mock 폴백 체인**: Gemini 503 일시 장애 시 ANTHROPIC 키 없어도 Pro/Max 구독으로 응답 보존. raw 에 `fallback_used` 박힘
- **claude_code OAuth 강제 경로**: subprocess env 에서 `ANTHROPIC_API_KEY`/`AUTH_TOKEN` strip → keychain OAuth. API key auth 는 `provider=anthropic`
- **Windows cmd.exe 8K argv 한계 = stdin 우회**: 19K canon spawn 시 long system 은 `[SYSTEM]/[USER]` stdin payload. 짧으면 정식 argv

**직전 세션 판단 (2026-05-07 브리핑 이력 UI + cron + KRX 라벨)**
- **3차원 분리 (SPEC 정합)**: 추론부 조회 (`run_analyst`) / 알림 자동 푸시 (`notifications_log`) / 브리핑 이력 (`briefing_parts` 시계열). 봇 명령 응답은 `notify=False` 라 알림 X = 브리핑 이력
- **briefing_parts = run_id 단위 시계열 누적** (일자 단위 upsert X). 같은 날 force 여러 번 = 다른 run_id
- **render dispatcher 1개 함수 → 모든 채널 wrap**: `render_pipeline()` 가 텔레그램 봇·webapp recent endpoint 동시 사용

**직전 세션 판단 (2026-05-06 M3)**
- **추론부 조회 ≠ 알림 파이프라인**: 분석가는 별도 호출 흐름 (CLI/REPL/FastAPI/webapp)
- **인터페이스 = 핵심 함수 1개 wrap**: `run_analyst()` 가 manifest+persona+canon+RAG+memory+messages → 호출 → metadata 한 묶음
- **검증 우선 → 점진 확산**: 5명 일괄 분화 X. 자산전략가 1명 가동 → 패턴 안정 → 4명 적용
- **JSONL retention A (그대로) → B (매월 폴더 + 90일) → C (SQLite)**: 임계는 5K (분화 직전) / 50K
- **응답 원론·반복 패턴 발견**: canon 19K 압도 + 시장 데이터 부재 + temp 0.4 → 추상 명제 인용 반복. 단기 톤·temp → 중기 시장 스냅샷 (이번 세션 단계 2 로 해소)

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
