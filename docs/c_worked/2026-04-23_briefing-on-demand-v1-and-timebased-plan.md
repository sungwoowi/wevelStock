---
date: 2026-04-23
topic: BRIEFING-ON-DEMAND-001 v1 구현 + DB cache guard + BRIEFING-TIMEBASED-002 기획
status: completed
plan_file: C:\Users\HOME\.claude\plans\nested-booping-dream.md
---

# 2026-04-23 · BRIEFING-ON-DEMAND v1 구현 + v2 기획

## 배경

RESUME.md Top 1 로 `/resume` 으로 시작 — BRIEFING-ON-DEMAND-001 SPEC 이 뼈대만 있고 코드는 0이었음. 오늘 v1 MVP 를 완성해 텔레그램 봇 + 공용 REST API 를 구축하고, 이어 v2 (장전/장중/장후 3종 브리핑) 의 SPEC draft 까지 작성했다.

## 한 일

### 1. BRIEFING-ON-DEMAND-001 v1 구현 (Phase A/B/C)
- **DB v3 bump**: `briefing_parts` 테이블 + migration 파일 + schema.sql 양쪽 업데이트
- **core/contracts/briefing_part.py**: `briefing-part-v1` Pydantic 계약
- **core/briefing/**: `render.py`(파트별 공용 렌더) + `parts_store.py`(upsert/get)
- **pipelines/morning_pre 리팩터**: `persist.py` 에 briefing_parts 3파트 upsert, `notify.py` 가 `render_morning_pre()` 사용 (기존 `_build_msg_*` 이동)
- **server/api/briefings_on_demand.py**: 4 엔드포인트 (`/latest`, `/latest/parts/{key}`, `/run`, `/resend`) + 60초 in-memory TTL
- **server/telegram/**: `python-telegram-bot>=21.0` 기반 long-polling + 3 명령어 (`/briefing`, `/briefing_now`, `/help`)
- **lifespan 통합**: `server/main.py` 에서 봇을 `asyncio.create_task` 로 기동 + graceful cancel
- **SPEC frontmatter 수정**: `status: scaffolded` → `implementing`, `contracts` 를 dict 형태로

### 2. A 기능 — DB 레벨 중복 방지 캐시
중간 발견: 서버 재기동 중 사용자 `/briefing_now` 가 두 서버에 배달되어 **LLM 2회 호출** 사고 (비용 ~$0.003). in-memory 캐시는 프로세스별이라 cross-process 에선 무력.

- `core/briefing/parts_store.py::get_latest_parts_with_age()` 신규 — DB 의 `datetime('now') - created_at` 기반 age 계산
- `server/api/briefings_on_demand.py::_db_cache_get()` 추가 — 60초 이내 최근 run 있으면 `cache_hit=True` 로 반환, 파이프라인 실행 건너뜀
- 검증: 실서버에서 `/run?force=true` 연속 2회 → 2차가 1초 + 같은 run_id + LLM/notify 로그 0회

### 3. 운영 개선 (근본 원인 해결)
매 worktree 작업마다 반복되던 3가지 불편함을 한 번에 해결:
- **`.env` 자동 탐색**: `core/config/loader.py::_resolve_env_file()` — 현재 worktree 에 없으면 메인 worktree 의 `.env` 자동 로드
- **공용 DB 경로**: `database.path` 가 상대경로일 때 메인 worktree root 기준 절대화 → 모든 worktree 가 같은 SQLite 파일 공유
- **httpx 로거 mute**: python-telegram-bot 이 INFO 레벨로 호출 URL 을 찍어 `TELEGRAM_BOT_TOKEN` 이 서버 로그에 유출되던 문제 차단 (`core/logging/__init__.py`)
- **yfinance/fredapi 기본 deps 승격**: 원래 `[optional-dependencies].market` 이었는데 morning_pre 의 9/10 지표가 이걸 쓰므로 오분류. `dependencies` 로 이동

### 4. 사고 복구 — 테스트 환경 실 텔레그램 차단
`.env` 자동 탐색이 pytest 세션에서도 작동해 실 `TELEGRAM_BOT_TOKEN` 이 주입되는 부작용 발생. `/resend` 테스트 2개가 실제 텔레그램에 4개 메시지 발송됨.

2중 안전장치:
- `conftest.py`: `TELEGRAM_BOT_TOKEN` 을 강제 빈값 + `WEVELSTOCK_SKIP_DOTENV=1`
- `loader.py`: 해당 env 감지 시 `load_dotenv` 스킵
- `autouse fixture`: `core.notification.service.notify()` 를 fake 로 교체 (HTTP 호출 자체 차단)

### 5. BRIEFING-TIMEBASED-002 기획 + SPEC draft
v1 이 단일 파이프라인 증명이었다면, v2 는 **컨텐츠 성격별 3종 브리핑**:
- `/briefing_pre` (morning_pre 확장, 09:00 이후 보관본 재전송)
- `/briefing_now` (market_briefing 신규, 실시간 시장 관찰)
- `/briefing_close` (close_briefing 신규, 예상 vs 실제 + RAG 해석)

핵심 인사이트: "시간대별 라우팅" 이 아니라 "컨텐츠 성격별 3종 + 시간은 validation". `/briefing_now` 의 "now" 는 시간대가 아니라 "현재 시장 스냅샷" 의미로 pre→now→close 시제 정렬.

## 검증 결과

- ✅ pytest **30 passed** (render 9 + on-demand API 17 + morning_pre smoke 4)
- ✅ `just validate` **0 errors** (1 warning 은 legacy `teams/registry.yaml`)
- ✅ 실서버 `/run` x2 smoke → 2차가 1초 + cache_hit=True + 로그에 LLM/notify 0회
- ✅ 텔레그램 봇 polling 실동작 — `telegram_bot_started` + `/help` 응답 확인
- ⚠️ 실 LLM 호출 총 비용 ~$0.003 (사고 + 정상 검증 합)
- ⚠️ 사용자 텔레그램에 테스트 fixture 데이터 4건 전송됨 (conftest 수정으로 재발 방지)

## 의도적으로 안 한 것
- **`/briefing_now` 통합안 철회**: 사용자 추가 고민 후 "/briefing_pre, now, close 3 명령이 컨텐츠 성격별로 독립" 결정. 이는 BRIEFING-TIMEBASED-002 의 핵심 판단
- **BRIEFING-TIMEBASED-002 구현**: SPEC draft 만. 구현은 다음 세션 Phase 0~3
- **test_e2e.py legacy import 수정**: 기존 RESUME.md 에 기록된 기술 부채, 이번 범위 밖
- **GitHub 원격 push**: 원격 미연결 상태 유지. 로컬 main fast-forward 만

## 커밋 상태
- ✅ 3 커밋 + main fast-forward 머지 완료 (로컬만)
  - `cf559ed` feat(briefings): BRIEFING-ON-DEMAND-001 v1 — parts API + telegram bot
  - `3078d9f` ops(dev-env): shared .env discovery + shared DB path + logger hygiene
  - `8ed8d64` fix(tests): isolate test env from real telegram API calls
- 이후 별도 커밋 예정:
  - SPEC draft 커밋: `docs(spec): BRIEFING-TIMEBASED-002 draft`
  - Wrap-up 커밋: `docs: wrap-up 2026-04-23`

## 다음에 이어서 할 작업 (우선순위)

### 1. BRIEFING-TIMEBASED-002 Phase 0~3 구현 (다음 세션 Top 1)
- **Phase 0** (선행, 30분): `pipelines/morning_pre/stages/analyze.py:42` 의 `_read_prompt("briefing.md")` 하드코딩 제거 — 파이프라인별 prompts 디렉토리 자동 해결. `run_id` 명명 규칙 문서화 (`#sched-<hex>` vs `#manual-<hex>`)
- **Phase 1** (2~3h): `/briefing_pre` validation (09:00 이후 보관본). `server/api/briefings_on_demand.py` 분기 + `server/telegram/commands.py` 핸들러 + `parts_store` 의 `get_last_run_before()` 추가
- **Phase 2** (3~4h): `pipelines/market_briefing/` 신규 + collectors 3종 (kr_indices, kr_sectors, kr_leading_stocks) + `/briefing_now` 핸들러 + render_market_briefing
- **Phase 3** (4~6h, 가장 큼): `pipelines/close_briefing/` + `core/knowledge/ingest.py` 실장 + RAG retrieve + 종합 프롬프트 + `/briefing_close` + 15:30 validation
- 총 10~15h, **2~3 세션 분량**

### 2. knowledge/canon 내용 주입 인터뷰
- 4 파일 TODO (investment-principles / macro-framework / sector-insights / failure-lessons)
- 주제별 Q&A → 편집. 1.5~2h
- Phase 3 (RAG) 진입 전에 canon 이 채워져 있으면 RAG 효과 즉시 체감

### 3. 기존 기술 부채 정리
- `tests/test_e2e.py` — legacy `teams.orchestrator` import. skip marker 또는 삭제
- `docs/STRUCTURE.md` — 구버전 (teams/ 기준). pipelines/ 기반으로 재작성

## 맥락 재진입 힌트 (다음 세션이 열어볼 파일)
- `docs/specs/BRIEFING-TIMEBASED-002-timebased-briefings.md` — draft, 전체 설계
- `C:\Users\HOME\.claude\plans\nested-booping-dream.md` — 이번 세션 최종 플랜
- `docs/specs/BRIEFING-ON-DEMAND-001-briefings-on-demand.md` — v1 참조 (implementing 상태)
- `pipelines/morning_pre/stages/analyze.py` — Phase 0 리팩터 대상 (프롬프트 경로 하드코딩)
- `server/api/briefings_on_demand.py:_db_cache_get` — v2 에서도 자동 적용되는 중복 방지 로직
- `core/knowledge/retrieve.py` — Phase 3 에서 완성 필요 (현재 skeleton)
