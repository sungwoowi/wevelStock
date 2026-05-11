# RESUME — 작업 재진입 상태판

> 이 파일은 **항상 최신 상태**로 유지됩니다. 세션을 새로 열 때 `/resume` 만 치면 이 파일을 읽고 플랜모드로 브리핑합니다.
>
> 갱신 주기: 의미 있는 작업 완료 후 `/wrap-up` 실행 시 자동 갱신.
> 수동 편집도 자유 — 구조만 지키면 됩니다.

---

## 📍 지금 어디 있나

**현재 위치**: **KNOWLEDGE-SYNC-001 Phase 2 풀세트 완료** — M3 (watchdog + justfile 정리) 마감 = 프로토타입 1차 동작점 도달. `core/knowledge/watcher.py` (Observer + 60s debounce dept 단위 coalesce + `start_observer`/`stop_observer`/`run_forever`) + `core/knowledge/sync.py` 확장 (`sync_dept(force=True)` + `recent_runs()` + CLI `--force`/`--status`/`--limit`) + `server/main.py` lifespan 자동 등록 + `sync_all` fire-and-forget reconcile + `justfile` 5 명령 정리 (`knowledge-sync` delta / `-rebuild` force / `-status` DB log / `-watch` standalone / `-browse` 유지, 기존 3 명령 제거). 외부→reference 이동은 사용자 manual 결정. 수동 회로 검증 4단계 (add 1 / modify 1 / delete 1 / +baseline) 적재 정확. pytest **134 passed** (128 → +7 watcher). 다음 세션 Top 1 = M3 분석가 분화 SPEC = **프로토타입 가동의 핵심**.

**마지막 작업일**: 2026-05-11 (같은 날 두 번째 세션)
**마지막 세션 로그**: [2026-05-11_phase-2-m3-watchdog-and-just.md](c_worked/2026-05-11_phase-2-m3-watchdog-and-just.md)
**Git**: 2 commits + push — `3228eb5` (M3 코드 + 테스트 + SPEC), `c078541` (chore: sqlite-db MCP entry 제거, npm archived). wrap-up commit 1개 추가 예정.

---

## 🎯 다음에 할 일 (Top 3)

우선순위 순. 마음에 드는 것 하나를 `/resume` 인터뷰에서 고르세요.

### 1. M3 분석가 분화 SPEC 작성 (PC, 3~5 세션) — **프로토타입 가동 핵심**
- **왜**: Phase 2 풀세트(watchdog 자동 색인) 가동점에 도착. 다음 의미점은 **9 분석가 페르소나 작성으로 production 호출 가능** 분기. 페르소나의 `canon_categories: [<dept>/<category>, ...]` 가 자동 sync 흐름과 결합 동작 확인 가능. 자산전략가 1명만 활성 → 4명 (원칙수호자/트레이더/종목분석가/자산전략가) 으로 확장 + 자료 0 시드 5명 페르소나만으로 시작.
- **범위**: M3 SPEC 신설 + 9 페르소나 (8-섹션 portable: Identity / Domain Frame / Inputs / Outputs / Reasoning Doctrine / Knowledge Categories / Anti-patterns / Cross-Agent Boundaries) + identity seed PROPOSAL 흐름 (자료 0 시드 5명) + portable 검증 (다른 LLM 같은 페르소나 호출 → 일관성).
- **예상**: 3~5 세션.

### 2. stock-analysis dept 첫 인덱싱 + 검증 (PC, ~1 세션)
- **왜**: 어댑터 5종 (md/txt/pdf/xlsx/png) 다 굴리는 첫 사례. M3 자동 색인 가동 후 `just knowledge-sync stock-analysis` 또는 reference drop 자동 sync. xlsx 어댑터 sheet 별 분리 여부 실 자료 (`4.로그차트_advanced/`) 보고 결정.
- **범위**: 이미지 PDF 미실행 백로그 (OCR 도입 후), png 어댑터 vision 활성화 검토 (비용 가시화 후). 검증 = retrieve smoke 4건 정확 + 카테고리 분포 출력.
- **예상**: ~1 세션.

### 3. 사전 부채 보강: market_snapshot mixed 테스트 (~30min)
- **왜**: `tests/test_market_snapshot.py::test_render_data_source_line_mixed` 가 시간-의존 mock 누락으로 깨져 있어 베이스라인이 -1. M3 코드 무관하지만 회귀 비교 정합 위해 보강 필요.
- **범위**: `kr/us_threshold_seconds(now_kst)` cron 발동 시각을 freezegun 같은 mock 으로 freeze + DB latest part fixture 적재 → `미국=DB` 헤더 path 정확 진입. ~30분.
- **예상**: 별도 작은 백로그.

(추가 백로그: streaming 토글 UI + AbortController / streaming response cache 멱등성 / Memory Compression SPEC / Quality Eval SPEC / MCP 패턴 차용 / `9.프렉탈 구조 응용 - 실전분석2-2.pdf` 등 이미지 PDF OCR (`ocrmypdf`) / png 어댑터 vision 활성화 (비용 가시화 후) / xlsx 어댑터 sheet 별 분리 (SPEC 528행 SLOT) / canon 정수 추출 자동화 (Phase 3 PROPOSAL 흐름) / knowledge/reference/ Google Drive 운영 워크플로 / `wealth_strategist` manifest 의 canon_categories 검증값 → 6 카테고리 전체 복귀 (M3 SPEC))

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
- **claude_code cost 라벨 frontend 분기 + analyst-chat SSR 가드** (2026-05-08 오후) — `webapp/src/app/analyst-chat/page.tsx` 4 곳 수정. MetadataBar/누적 비용에서 `provider_used==="claude_code"` 시 `cost $0 (subscription)` 표기. `analystMeta` state 를 `undefined | null | object` 3-state 로 확장 → SSR 첫 렌더 빨간 깜빡임 제거
- **시장 스냅샷 DB-first hybrid (옵션 A)** (2026-05-09) — `collectors/snapshot.py` 가 `briefing_parts` DB 의 latest part 우선 + 시간대 인식 임계 (`kr/us_threshold_seconds(now_kst)` cron 발동 시각 기반, 정규장 중 ~3h / 장 마감 후 ~18h / 주말 ~66h) + 부분 fetch (stale 그룹만). `MarketSnapshot` 에 `source_map`/`db_run_ids`/`db_age_seconds` 필드 추가, 4 어댑터 (`_adapt_overnight/kr_indices/supply_sectors/leading_from_part`). `render_snapshot_md` 헤더에 "_데이터 출처: 미국=DB (X시간 전 적재)_" 라인. 인메모리 캐시 TTL 300s → 60s. 분석가 호출 cold fetch ~30s → 0.3s, 5-Layer 단방향 정합 회복
- **LLM token streaming (SSE) — INFRA-LLM-STREAM-001** (2026-05-09) — `core/llm/client.py:call_llm_stream()` async iterator + 4 provider stream (anthropic `messages.stream()` / gemini `aio.models.generate_content_stream` / claude_code CLI `--output-format stream-json --include-partial-messages` / mock 5글자 청크). fallback chain (첫 청크 전 실패만). `core/llm/claude_code_backend.py` 에 `_can_spawn_subprocess()` 사전 체크 — SelectorEventLoop 면 sync subprocess + asyncio.to_thread 의 batch_thread 직행 (warning 0). stdin 송신 background task (Windows pipe deadlock 회피) + subprocess `limit=10MB` (skill md 한 라인 64KB 초과). `core/inference/run_analyst.py:run_analyst_stream()` + `first_token_ms` metadata. `server/api/analyst_chat.py` 에 `POST /api/analysts/{id}/chat/stream` (StreamingResponse). `webapp/src/app/analyst-chat/page.tsx` 가 fetch ReadableStream + SSE 프레임 파싱 + 빈 assistant 메시지 점진 누적 + MetadataBar `(first XXXms)` 라벨
- **pytest 94 passed** (60 → 87 → 94, 신규 `test_market_snapshot.py` 19 + `test_llm_streaming.py` 7)
- SPEC 5종: **BRIEFING-ON-DEMAND-001** + **BRIEFING-TIMEBASED-002** + **INFRA-RAG-001** + **INFRA-LLM-STREAM-001** + **KNOWLEDGE-SYNC-001** (2026-05-10 신설, draft)
- **`docs/AGENT-ARCHITECTURE.md`** (2026-05-10) — hierarchical orchestration + DB read 절충 영구 본질 문서. 두 패턴 비교 10 측면 + 도메인 본질
- **5-Layer 모델 9명 확장** (2026-05-10) — 지식부 9 (market_macro / stock_selection / trading_journal / flow_analysis 신설, mechanics→trading) + 분석가 9 (1:1 매핑). `CLAUDE.md` 5-Layer 표 + 본문 갱신
- **9 지식부 × 36 카테고리 폴더 + `_category.yaml` 36** (2026-05-10 Phase 0) — `knowledge/canon/<dept>/<category>/` 3-tier 구조 완비. 자료 있는 4 dept (principles 3 / trading 6 / stock-analysis 5 / wealth_compounding 6) + 자료 0 시드 4 dept (market_macro 4 / stock_selection 4 / trading_journal 4 / flow_analysis 4). 자료 git mv 50+ + 초안 삭제 3
- **`core/knowledge/adapters/` Phase 1 어댑터 5종** (2026-05-10) — `_base.py` (Adapter Protocol + ExtractedDocument) + `markdown.py` (frontmatter wrap) + `text.py` (UTF-8 read + char_count) + `pdf.py` (sync_knowledge.py 의 extract + 한글 공백 휴리스틱 이관) + `xlsx.py` (openpyxl 단일 body) + `png.py` (`enabled_by_default=False` silent skip). `__init__.py` 의 `ADAPTERS` 레지스트리 + `get_adapter(ext)`. `pyproject.toml` openpyxl>=3.1
- **`core/knowledge/ingest.py` 재작성** (2026-05-10) — `_iter_reference_files(dept)` 어댑터 디스패치 + 카테고리 폴더 직속 탐색 + `_` prefix 모든 path part skip. `_load_category_meta(dept, category)` canon `_category.yaml` ground truth 로드. `_build_metadata` 가 frontmatter + extraction + category 3중 병합. 멱등 backfill = `(file_hash, category)` 동시 비교. chunk metadata 18 keys (category / category_title / category_description / when_to_inject / target_analysts / dept / file_hash / extracted_at / page_count / sheet_count / char_count / source_pdf / ...)
- **`tests/test_adapters.py` + `test_ingest_categories.py`** (2026-05-10) — 신규 17 (pytest 111 = 94 + 17). 어댑터 fixture 는 tmp_path 동적 생성 (xlsx 는 openpyxl write, pdf 는 PdfWriter blank page)
- **`data/chroma/wealth_compounding/` force re-index** (2026-05-10) — 25 sources / 787 chunks / 6 카테고리 분포 (asset_classes 30 / crisis_signals 224 / currency_pricing 150 / debt_rate_cycle 153 / macro_roadmap 38 / monetary_evolution 192). retrieve smoke ("인플레이션 통화 가치") top 3 정확 + category 라벨 노출 + score 0.59~0.64. Phase 0 git mv 로 인한 legacy chunk 동시 청산
- **Phase 2 M1: retrieve/compose 카테고리 화이트리스트** (2026-05-10) — `core/knowledge/retrieve.py` `retrieve(dept, query, *, categories=None, top_k=3)` + ChromaDB `where={"category": {"$in": [...]}}` 조건부 + 빈 리스트 falsy fallback. `core/knowledge/compose.py` `load_shared_canon(canon_categories=None)` 폴더 path prefix 매칭 필터 + `build_pipeline_prompt(..., canon_categories=None)` + RAG 분기에서 `rag_dept` 매칭 카테고리만 추출해 `retrieve(categories=)` 전달 (canon block + RAG block 둘 다 좁아짐). `core/inference/run_analyst.py` `AnalystSpec.canon_categories` 필드 + manifest 로드 + 두 run 함수에 전달. `wealth_strategist` manifest 검증값 `canon_categories: [wealth_compounding/macro_roadmap]` (M3 SPEC 정식 정의 시 6 카테고리 복귀 예정). `tests/test_retrieve_categories.py`(4) + `test_compose_canon_categories.py`(7) 신규 = pytest **122 passed** (111 → +11). 통합 검증: canon 18,726 → 3,935 chars (79% 감소), RAG block macro_roadmap 청크만 회수. 1 commit + push (`7158cd0`)
- **Phase 2 M2: sync run + DB run log + delta 인덱싱** (2026-05-11) — `core/db/schema.sql` 에 `knowledge_index_runs` (sync_id PK / dept / started_at / ended_at / status / files_{added,modified,deleted} / chunks_{upserted,deleted} / proposal_path / release_note_path / error) + `idx_kir_dept_started` 인덱스 + schema_version 4. `core/knowledge/sync.py` 신규 — `sync_dept(dept, *, since_run_id=None)` + `sync_all()`. ingest 의 `_iter_reference_files`/`_build_metadata`/`_chunk_text` 재사용. collection metadata 비교로 `source_id → file_hash` 맵 추출 → delta 분류 (added/modified/deleted) → upsert + hard delete (`where source_id`). modified 는 청크 수 감소 케이스 위해 pre-delete + upsert. `_allocate_sync_id` 분→초→ms PK fallback. CLI = `python -m core.knowledge.sync <dept>` (생략 시 8 dept). `tests/test_knowledge_sync.py`(6) 신규 = pytest **128 passed** (122 → +6). 4-단계 회로 검증 (add 1 / modify 1 / delete 1 / DB 4 row) 정확. 1 commit + push (`0aadf8a`)
- **Phase 2 M3: watchdog 자동 색인 + justfile 정리** (2026-05-11, 같은 날 두 번째 세션) — `core/knowledge/watcher.py` 신규 (watchdog Observer + `_Debouncer` threading.Timer dept 단위 coalesce + `_extract_dept` `_` prefix dept None + `_build_handler` `is_directory` skip / `moved` 시 src+dest 둘 다 처리 + `start_observer`/`stop_observer`/`run_forever` standalone + CLI `--reference-root`/`--debounce`). `core/knowledge/sync.py` 확장 (`sync_dept(force=False)` drop 직전 prev 카운트를 deleted 로 적재 → collection drop → 전체 added 재구축, `recent_runs(limit, dept)` helper, `_format_status_row` 1줄, CLI `--force`/`--status`/`--limit`, `_open_collection(drop_existing=)`). `server/main.py` lifespan startup 에 `start_observer()` 자동 등록 + `sync_all` fire-and-forget reconcile (BGE-m3 cold load 회피) / shutdown 에 reconcile_task cancel + `stop_observer`. `justfile` 정리 — 기존 3 명령 (`knowledge-sync` 구 OneDrive 추출 / `-ingest` / `-reingest`) 제거, 신규 5 명령 (`knowledge-sync` delta / `-rebuild` force / `-status` DB log / `-watch` standalone / `-browse` 유지). 외부→reference 이동은 사용자 manual 결정. `tests/test_knowledge_watcher.py`(7 cases: `_extract_dept` 3 + `_Debouncer` 3 + Observer 통합 1) 신규 = pytest **134 passed** (128 → +7, 회귀 0). 수동 회로 검증 4-단계 (add 1 +1/~0/-0 / modify 1 +0/~1/-0 / delete 1 +0/~0/-1) 적재 정확. server log: `watcher_started` + `knowledge_reconcile_done` 자동 등록 확인. 2 commits + push (`3228eb5` M3 코드 + `c078541` chore: sqlite-db MCP entry 제거).

### 미완 또는 의도적 공백
- **9 분석가 페르소나 작성 (M3 SPEC)** — 자료 있는 4 (원칙수호자/트레이더/종목분석가/자산전략가) + 자료 0 시드 5 (시장상태분석가/종목선정가/매매저널리스트/수급분석가/뉴스큐레이터). 8-섹션 portable 양식. Phase 2 풀세트 완료 후 본격 진입. **프로토타입 가동의 핵심**
- **KNOWLEDGE-SYNC-001 Phase 2~5 구현** — Phase 1 ✅ / Phase 2 M1 ✅ (retrieve 카테고리 필터 + compose canon_categories) / Phase 2 M2 ✅ (DB knowledge_index_runs + sync.py delta 인덱싱) / Phase 2 M3 ✅ (watchdog 60s debounce + justfile 5 명령 정리 + server lifespan 자동 등록) — **Phase 2 풀세트 = 프로토타입 1차 동작점** / Phase 3 canon 승격 PROPOSAL + release note LLM 자동 생성 (M3 분석가 분화 SPEC 후) / Phase 4 트리거 + 스킬 (`/knowledge-sync`, `/knowledge-review`) / Phase 5 풀 사이클 검증
- **사전 부채: `tests/test_market_snapshot.py::test_render_data_source_line_mixed`** — 시간-의존 mock 누락으로 `미국=DB` assert 실패. M3 작업 무관. 베이스라인 -1 (134/135). `kr/us_threshold_seconds(now_kst)` cron 시각 freezegun mock + DB latest part fixture 적재 보강 필요 (~30분)
- **다른 dept 재인덱싱** (principles / trading / stock-analysis 등) — Phase 2 sync 로 자동화 또는 수동 force re-index. stock-analysis 는 5형식 자료 풍부해 어댑터 검증 풍부 (백로그)
- **이미지 PDF OCR 미실행** — 박종훈 Vol 2/3 4 파일 + `9.프렉탈 구조 응용 - 실전분석2-2.pdf` 30페이지 0 chars. `ocrmypdf` + tesseract 백로그
- **png 어댑터 vision 활성화** — 비용 가시화 후 `enabled_by_default=True` flag + Anthropic vision API + extraction cache (`data/chroma/<dept>/_extraction_cache/<file_hash>.txt`). 현재 silent skip
- **xlsx 어댑터 sheet 별 분리 인덱싱** — 현재 단일 body (sheet header + tab-delimited). SPEC 528행 SLOT, 실제 자료 (4.로그차트_advanced/ xlsx) 보고 결정
- **streaming 토글 UI + AbortController** — webapp 의 streaming on/off 토글 + 응답 도중 cancel 버튼. default ON 유지하되 회귀 옵션 + 사용자가 응답 길어질 때 중단 가능. ~1.5h
- **streaming response cache (멱등성)** — `call_llm` 의 cache_lookup 패턴 streaming 용 미적용. text_delta 들을 모아 metadata 와 함께 저장하는 패턴 신규. 후속 백로그
- **claude_code 첫 토큰 ~12s 한계** — subprocess 부팅 + OAuth keychain handshake. CLI 자체 한계라 streaming 도입에도 단축 X. Anthropic SDK 직접 호출 (`provider="anthropic"`, ~2s) 가 답이지만 Pro/Max 무료 혜택 포기. 운영 합리적 타협으로 batch_thread fallback 채택
- **provider default = gemini 토글** — 5분 작업, 사용자가 매번 토글로 충분이라 미반영
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
- **자료 0 dept 5종** (market_macro / stock_selection / trading_journal / flow_analysis / news + trading 의 일부 카테고리) — Phase 0 시드 카테고리만, 자료 0. 페르소나만으로 추론 시작 (M3 SPEC 의 자료 0 시드 5명)
- **전략가 3 / 계좌관리자 / 출력 채널 확장** — M4~M6, 한참 후
- **선물 수급 3주체 → 5주체 확장** — KRX MDCSTAT bld 캡쳐, 백로그
- **Phase 3 `market_briefing_close`** — 5-Layer M3 완료 후 자연 진입
- **dead code 청산** (`market_investor_summary`/`foreign_institution_top`/`core/registry.py`/`rollup.py`) — 회귀 리스크 큰 별도 세션
- **KOSPI200 선물 정확 가격** — 지수(2001) 대체. 선물옵션 API 별도
- **`docs/KNOWLEDGE-WORKFLOW.md` 5케이스 가이드** — 자료 추가 흐름차트 미작성

### 꼭 알아둘 판단

**이번 세션에 굳힌 판단 (2026-05-11 Phase 2 M3)**
- **watcher 진입점 함수 1개 = 2곳 호출**: `start_observer()` 가 server lifespan + `just knowledge-watch` 둘 다에서 호출. "자동 등록 + standalone" 안 = 코드 비용 0 (함수 1개 정의 + 2 호출). 의사결정 시 "진입점 2군데" 처럼 보였으나 실제로는 동일 함수.
- **외부→reference 이동 = 사용자 manual**: `scripts/sync_knowledge.py` (OneDrive PDF 추출) 는 파일만 남기고 justfile 에서 제거. just 명령은 reference drop 이후 자동화만 담당. 의미 분리 + 명령 셋 간결화. 다음 세션 진입 시 헷갈리지 말 것
- **fire-and-forget reconcile (sync_all)**: server lifespan startup 에서 `asyncio.create_task(asyncio.to_thread(sync_all))`. BGE-m3 cold load 가 startup blocking 될 가능성이 있어 비동기. gap_filler 와 패턴 다름 (gap_filler 는 lightweight 라 await). 절전 후 fsevents 누락 안전망
- **logger keyword `event` 충돌**: `core.logging` 의 첫 positional 이 `event` 라 `log.debug("x", event=...)` 시 `_nop() got multiple values for argument 'event'`. `event_type=` 등 다른 이름 사용. 향후 logger keyword 신중

**직전 세션 판단 (2026-05-11 Phase 2 M2)**
- **delta baseline = collection metadata, DB = 운영 로그**: SoT 분리. `since_run_id` 인자는 인터페이스 호환성만 받고 실제 비교는 collection 의 `source_id → file_hash` 맵 단일 모드. 미래 cross-run 분석에 reserve
- **modified 의 pre-delete + upsert**: 본문 길이 감소로 청크 수 5→3 케이스 시 stale id 가 남으면 retrieve 가 빈 청크 hit. `where source_id` hard delete 후 upsert. modified 한정 안전망
- **PK 충돌 fallback (분→초→ms)**: `_allocate_sync_id` 가 sqlite IntegrityError 잡고 다음 fallback. 같은 분에 두 sync 떨어져도 안전
- **테스트 monkeypatch: ingest_mod + sync_mod 양쪽**: sync 가 ingest 헬퍼 직접 import 했으므로 `REFERENCE_ROOT` redirect 시 ingest_mod 도 함께 patch 필요. 비슷한 re-export 패턴 가진 다른 모듈도 동일

**직전 세션 판단 (2026-05-10 Phase 2 M1)**
- **canon_categories 형식 = `<dept>/<category>`**: 한 분석가가 여러 dept 의 카테고리를 받을 수 있도록 다 dept 친화 설계. compose 가 RAG retrieve 호출 시 `rag_dept` 와 일치하는 항목만 추출 — ChromaDB 는 dept 별 collection 이라 카테고리는 단일 dept 안에서만 의미 (cross-dept 카테고리 retrieve 는 multi-collection 호출이 미래 옵션)
- **빈 리스트 = 무필터 (legacy 동작)**: `canon_categories: []` 또는 `categories=[]` → falsy 체크로 dept 전체. `spec.canon_categories or None` 패턴으로 manifest 키 부재/빈 리스트 모두 None 변환. 회귀 안전망
- **compose 두 곳 동시 적용**: `[0] Investment Knowledge` 의 canon md prefix 매칭 필터 + `[4] Retrieved References` 의 RAG retrieve 카테고리 인자 — manifest 한 줄로 두 경로 동시 좁힘. system prompt 의 일관성 보장
- **테스트의 importlib 우회 패턴**: `core/knowledge/__init__.py` 의 `from .retrieve import retrieve` 가 패키지 attribute 를 함수로 가로채서 `import core.knowledge.retrieve as X` 가 모듈이 아닌 함수 반환. `importlib.import_module("core.knowledge.retrieve")` 로 우회. 비슷한 re-export 패턴 가진 다른 모듈 monkeypatch 시 동일하게 적용

**직전 세션 판단 (2026-05-10 Phase 1 코드)**
- **png default off + silent skip**: `enabled_by_default=False` flag 사전 체크 → log.debug. NotImplementedError 분기 안 탐. 환경 한계 silent fallback 원칙 정합
- **로컬 vs 클라우드 전략**: 로컬에서 끝까지 + 어댑터 패턴 추상화 + 24/7 봇 필요 시점에 작은 VM 1대로 통째 이전. chromadb.PersistentClient → HttpClient connection string 1줄

**직전 세션 판단 (2026-05-10 KNOWLEDGE-SYNC-001 SPEC + 9 분화)**
- **agent 통신 = hierarchical + DB read**: 분석가 간 직접 LLM 호출 X (시점 drift·frame 오염·debugging 지옥·비용 폭증). DB `team_outputs` row read 만. 본질·trade-off = `docs/AGENT-ARCHITECTURE.md`
- **카테고리 = 지식부 안의 LLM 인식 1차 단위**: agent 는 *갖는* 게 아니라 *선택해서 읽는* 단위. agent ↔ dept 1:1, dept ↔ category 1:N, agent ↔ category N:M (페르소나의 `canon_categories` 결정)

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
