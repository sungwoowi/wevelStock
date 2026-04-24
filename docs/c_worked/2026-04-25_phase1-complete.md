---
date: 2026-04-25
topic: BRIEFING-TIMEBASED-002 Phase 1 전체 완성 + force 재정의 + 이중 발송 수정
status: completed
plan_file: C:\Users\HOME\.claude\plans\twinkly-riding-stearns.md
---

# 2026-04-25 · Phase 1 전체 + M3.5 force 재정의 + M6 이중발송 수정

## 배경

Phase 0 (prompts helper + run_id 규약, `0a4e0b2`) 커밋 상태에서 Phase 1 백엔드 3 마일스톤 (M1~M3) 으로 시작. 진행 중 사용자 "보관본 없으면 LLM 호출해야 하는 거 아냐?" 질문 → SPEC 재검토 후 `force` 의미 재정의 (M3.5 추가). M4 텔레그램 핸들러 + M5 E2E 테스트까지 완성. 서버 실전 검증 중 **파이프라인 `notify` stage 와 봇 `_send_briefing` 의 이중 발송** (v1 부터 있던 설계 결함) 발견 → M6 긴급 수정.

핵심 판단: `force` 의미를 "cache/snapshot 우회 + LLM 실시간" 으로 재정의하고, 09:00 분기를 cache 레이어 **앞**에 배치해 force=true 직후 force=false 호출이 post-9am run 을 새는 것을 원천 차단.

## 한 일

### 백엔드 (Phase 1 core)
- `core/briefing/parts_store.py` — `get_last_run_before(pipeline_id, cutoff_iso, since_iso=None)` 신규 (`[since, cutoff)` 범위 조회)
- `core/briefing/__init__.py` — export 추가
- `core/contracts/briefing_part.py` — `BriefingResponse.note: str | None` 필드 + `build()` 파라미터
- `server/api/briefings_on_demand.py` — `_KST`/`_now_kst()` helper, 09:00 분기 (cache 앞, `and not force`), `force` default True→False 재정의, `notify: bool = Query(True)` 쿼리 + `runner.run(input_data={"skip_notify": not notify})`

### 텔레그램 봇 (M4 + M6)
- `server/telegram/commands.py` — `cmd_briefing_pre` + `cmd_briefing_pre_force` 신규, `_build_note_prefix` (⏰ prefix), `CHECKING_PRE_TEXT` + `NO_PRE_SNAPSHOT_TEXT`, 3 명령 모두 `notify=False`, **`cmd_briefing` 제거** (`/briefing_pre` 와 중복)
- `server/telegram/bot.py` — 핸들러 2개 등록 + `set_my_commands` 4개 (`/briefing` 제거)

### 파이프라인 (M6)
- `pipelines/morning_pre/stages/notify.py` — `ctx.data.get("skip_notify")` 시 early return

### SPEC
- `docs/specs/BRIEFING-TIMEBASED-002-timebased-briefings.md` — Validation 섹션 (force 재정의 반영), 요약표 각주, API pseudocode, 텔레그램 명령 표 (`/briefing_pre_force` 신규 + `notify=False` 주의 + `/briefing` 제거 표시)

### 테스트
- `tests/test_parts_store.py` 신규 — `get_last_run_before` 7 케이스
- `tests/test_briefings_on_demand.py` — autouse fixture `_now_kst` 08:00 고정 + Phase 1/M3.5/M6 테스트 6개 추가
- `tests/test_briefing_validation.py` 신규 — Phase 1 + M3.5 5 케이스 (08:30 실시간, 10:00 보관본/404/force 우회/cache 누수 방지)

## 검증 결과

- ✅ `pytest tests/` → **44 passed** (기존 26 → 44, 회귀 0)
- ✅ `curl /api/briefings/morning_pre/run?force=true` 실증: 보관본 없을 땐 404 "force=true 로 실시간 실행 가능" 힌트, mock 삽입 후 200 + `cache_hit=true, note="before_market_open"`
- ✅ `_build_note_prefix` 실측: `⏰ 장 시작 전 데이터 기준 (07:30 생성)`, short run_id `(? 생성)` fallback, note=None 빈 문자열
- ✅ `server.main` 부팅 26 routes, `build_application()` 토큰 없을 때 None
- ⚠️ 텔레그램 실전 시도 중 3 회 파이프라인 실행 + 9 건 발송 (M6 이전 + 당시 시각 01:xx KST = 09:00 이전이라 force 무관 실시간 실행이 SPEC 정답)

## 의도적으로 안 한 것

- **DB 과거 row 정리** — 기능 영향 0
- **`/briefing_now` 의미 재정의** — Phase 2 에서 market_briefing 으로 전환 예정. v1 호환 유지
- **09:00 이후 분기 실 환경 curl 검증** — E2E 5 케이스로 커버. 내일 07:00 cron 뒤 자연 재현 가능
- **"Unknown command" 근본 원인 규명** — 텔레그램 클라이언트 캐시 추정. 내일 봇 채팅 재진입으로 해소 예상

## 다음에 이어서 할 작업 (우선순위)

1. **Phase 2: `/briefing_now` + `market_briefing` 신규** — 장중 실시간 관찰용. KOSPI/KOSDAQ 지수·수급·섹터·주도주 collectors 3 종 + 최소 LLM 요약 (목표 비용 $0.0005 이하). `server/telegram/commands.py::cmd_briefing_now` 를 morning_pre force→market_briefing force 로 재작성. **4~6h**
2. **knowledge/canon/ 4 파일 주입 인터뷰** — `investment-principles.md`·`macro-framework.md`·`sector-insights.md`·`failure-lessons.md` Q&A 로 채움. 코드 변경 0, 실 LLM 해석이 "일반론 → 이 사용자의 에이전트" 로 전환. **1.5~2h**
3. **남은 팀 레지스트리 완전 청산** — `core/registry.py` + `core/memory/rollup.py::rollup_all_teams` + `server/schedulers/jobs/{daily,weekly,monthly}_rollup.py` + `GET /api/teams` + `scripts/validate.py`·`scripts/scaffold.py` + `pyproject.toml` L65·L69 + `core/config/schema.py::TeamsConfig`. 회귀 테스트 필수 **2~4h 독립 세션**

## 맥락 재진입 힌트

- `docs/specs/BRIEFING-TIMEBASED-002-timebased-briefings.md` — Phase 2/3 스펙 원문
- `server/api/briefings_on_demand.py::briefing_run` L190~ — Phase 2 market_briefing 조건 추가 지점
- `tests/test_briefing_validation.py` — Phase 2 추가 시 validation 표 기준 케이스 확장
- `C:\Users\HOME\.claude\plans\twinkly-riding-stearns.md` — 이번 세션 플랜 원본

## 커밋 상태

- 커밋 분리 예정: (1) Phase 1 code + tests (M1~M6 전부), (2) docs wrap-up (SPEC + c_worked + RESUME + SESSIONS)
- main FF merge 예정 (현재 main tip: `7bc47de`)

## 세션 중 실 비용

- LLM 호출 **4회** 이상 (M3 검증 mock 1건 + 텔레그램 실전 3건) — 각 ~$0.0015, 합 ~$0.006
- 텔레그램 발송 **총 12건** (M3 mock resend 3 + 실전 run 3×3 = 9, M6 이전 이중 발송 가능성 있었음)
