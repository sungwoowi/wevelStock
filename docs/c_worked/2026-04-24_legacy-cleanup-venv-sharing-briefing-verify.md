---
date: 2026-04-24
topic: 레거시 teams.orchestrator 청산 1단계 + worktree 공용 .venv + 브리핑 실 LLM 재검증
status: completed
plan_file: C:\Users\HOME\.claude\plans\cozy-crafting-flask.md
---

# 2026-04-24 · 레거시 teams.orchestrator 청산 1단계 + worktree 공용 .venv + 브리핑 실 LLM 재검증

## 배경

`/resume` 으로 재개 → RESUME Top 3 #3 "기존 기술 부채 정리" 선택. 사용자가 "데모 잔재는 지난 번에 청산된 줄 알았는데?" 라며 의문을 제기 → 실제 현황 검증 결과 여전히 3개 파일이 `teams.orchestrator` 에 의존 중(단 그 패키지는 이미 제거됨). 즉 "**산 것도 죽은 것도 아닌 ImportError 상태**" 로 남아 신규 작업 간섭. 오늘은 이걸 묻고, 그 과정에서 **텔레그램 브리핑 실동작 재검증**까지 하려다 **worktree 에서 google-genai 가 import 안 되는 이슈**를 발견해 함께 해결했다.

핵심 판단: 사용자가 마지막에 "레거시 구조 정리 다 된 거 맞아?" 물었을 때 정직히 조사해보니 **`core/registry`·스케줄러 rollup·`/api/teams` 엔드포인트·scaffold/validate·pyproject 등 광범위한 팀 레지스트리 시스템이 온존**. 오늘 치운 건 "명백히 터지는 조각" 뿐. 남은 청산은 회귀 리스크가 있어 별도 세션으로 미룸.

## 한 일

### 1. teams.orchestrator 죽은 파일 3종 제거
- `scripts/demo.py` — 삭제 (28줄 `from teams.orchestrator.src.agent import Agent`)
- `server/api/demo.py` — 삭제 (9줄 동일 import)
- `tests/test_e2e.py` — 삭제 (7줄 동일 import, pytest collect 단계에서 실패하던 상태)

### 2. 연쇄 정리
- `server/main.py` — demo 라우터 try/except 블록 제거(L117~123)
- `server/orchestration/__init__.py` — docstring "delegates to teams.orchestrator" → "reserved namespace for pipeline runner helpers"
- `justfile` — `demo` recipe 삭제, `test-team` → `test-pipeline name: uv run pytest pipelines/{{name}}/tests`, `test-cov`·`lint` 의 `teams` → `pipelines`
- `server/CLAUDE.md` — `teams/<id>/src/agent.py 만` → `pipelines/<id>/stages/ 만`, api 목록에서 demo 제거

### 3. 문서 재작성
- `docs/STRUCTURE.md` — **pipelines/ 기반으로 전면 재작성**. `collectors/`·`checkers/`·`connectors/` 최상위 폴더 반영, `manifest.yaml` 필드를 `stages` DAG(`depends_on`/`parallel_with`/`timeout_sec`)+`parts` 구조로 교체. teams/<id>/ 레이아웃 섹션 제거, 파이프라인 표준 레이아웃으로 대체

### 4. 공용 .venv 정책 (추가 작업)
발단: 텔레그램 발송 테스트 중 `llm_call_failed error="cannot import name 'genai' from 'google'"`. 원인은 worktree 에서 `uv sync` 가 엉뚱한 venv 에 설치(실제로는 site-packages/google/genai 디렉터리 생성 안 됨). 해결: `VIRTUAL_ENV="C:/Users/HOME/claude/wevelStock/.venv"` 명시 후 `uv pip install --force-reinstall google-genai` 하니 설치됨.

영구 대책:
- `justfile` 최상단 — `export VIRTUAL_ENV := \`git rev-parse --git-common-dir | sed 's,/\.git/*$,,'\` + "/.venv"` 추가. 이제 모든 worktree 의 `just install/server/test` 등이 자동으로 메인 `.venv` 를 가리킴. 지난 세션의 "`.env` 자동 탐색 + DB 경로 메인 루트 절대화" 와 동일 계열 정책.

### 5. 텔레그램 발송 실증 2회
- 1차 (`resend`): `POST /api/briefings/morning_pre/resend` → 어제 캐시(`2026-04-23T01:06:31#manual-ef3117`) 3파트 재전송. LLM 호출 없음. **이때 사용자가 "어제 정보잖아?" 라며 resend vs run 차이 명확화 요구**
- 2차 (`run?force=true`, google-genai 수정 후): `POST /api/briefings/morning_pre/run?force=true` → 신규 run `2026-04-24T21:33:57#manual-3d4b89` 생성. overnight/scenario/positions 3파트 모두 채움. scenario 의 `narrative` 가 "야간 코스피200 선물 -3.34% + 미국 혼조세로 하락 출발 가능성..." 식의 실제 LLM 해석 포함. 텔레그램 3건 발송, `morning_pre_notified llm_status=ok`

### 6. main 로컬 FF merge
- `git -C "C:/Users/HOME/claude/wevelStock" merge --ff-only claude/upbeat-kapitsa-db2c59` — **main tip `0a4e0b2` → `15fd09e`**. 새 worktree 부터 자동으로 VIRTUAL_ENV 정책·레거시 청산 적용됨.

## 검증 결과

- ✅ `pytest` → **26 passed** (기존 30 에서 test_e2e 3개 빠짐, 회귀 0)
- ✅ `scripts.validate` → **0 errors, 1 warning** (1 warning 은 `teams/registry.yaml: missing` — validate.py 가 teams/ 존재 전제, 남은 청산 대상)
- ✅ `grep "teams\.orchestrator|from teams\." --glob "*.py"` → **0 hits** (실행 코드에서 완전 제거)
- ✅ `server.main` 부팅 정상, `routes=26`
- ✅ `just --evaluate VIRTUAL_ENV` → `C:/Users/HOME/claude/wevelStock/.venv`
- ✅ `/resend` → `delivered:["telegram"]`, `notification_sent` 3 건 로그
- ✅ `/run?force=true` → `cache_hit:false`, `status:ok`, `scenario.non_empty=True`, `news_impact.count=20`, 텔레그램 3건 발송

## 의도적으로 안 한 것 (남은 팀 레지스트리 청산)

사용자가 "레거시 구조 정리 다 된 거 맞아?" 물어 정직히 조사한 결과 **다음은 이번 범위 밖**으로 유지:

### 🔴 실행 중이지만 no-op 으로 도는 코드
- `core/registry.py` — `TEAMS_DIR = REPO_ROOT / "teams"` + `list_all_teams`/`list_active_teams`/`refresh_registry_file` 10+ 함수. 서버 부팅·스케줄러가 import
- `core/memory/rollup.py::rollup_all_teams` — 스케줄러가 매일/매주/매월 호출하지만 teams 없어 빈 리스트 반환
- `server/schedulers/jobs/{daily,weekly,monthly}_rollup.py` — 위 함수 부르는 no-op 잡 3개 등록 중
- `GET /api/teams` (`server/api/teams.py` + `server/main.py:105,108`) — 항상 `{"teams": []}` 반환
- `core/contracts/spec_frontmatter.py:60~62` — `teams_root = root / "teams"` SPEC 탐색 경로
- `core/config/schema.py` — `TeamsConfig`, `include_teams: ["principles"]` 등

### 🟡 도구 체인 — 지금 쓰려 하면 작동 안 함
- `scripts/validate.py` — 팀 스캔 전제. `teams/registry.yaml: missing` warning 출력
- `scripts/scaffold.py:18` — `TEAMS_DIR = REPO_ROOT / "teams"`, `just new-team` 이 없는 폴더에 생성 시도
- `pyproject.toml:65` — `packages = ["core", "server", "teams", "scripts"]` (build target)
- `pyproject.toml:69` — `testpaths = ["tests", "teams"]`

### 🟢 문서 잔해 (기능 영향 0)
- `docs/CONTRACTS.md:299` — 예시 코드 `from teams.principles.src.agent import Agent`
- `server/CLAUDE.md:8` — api 목록의 "teams" 언급 (현재 /api/teams 가 살아 있으니 틀린 말은 아님)
- RESUME.md / c_worked/ — 과거 기록 유지

**이유**: 위 정리는 서버 부팅·스케줄러·config 스키마에 영향이 있어 실수하면 서버가 안 뜰 수 있음. 회귀 테스트를 신중히 설계해야 안전. 2~4h 별도 세션 필요.

### 기타 미실행
- BRIEFING-TIMEBASED-002 Phase 1~3 — 다음 세션 Top 1
- `knowledge/canon/*.md` 4 파일 주입 인터뷰

## 다음에 이어서 할 작업 (우선순위)

### 즉시 실용 가치
1. **BRIEFING-TIMEBASED-002 Phase 1 — `/briefing_pre` 09:00 이후 보관본 validation**
   - 왜: Phase 0 (prompts helper + run_id 규약) 은 이미 커밋됨(`0a4e0b2`). Phase 1 은 UX 상 가장 체감 큰 개선(09시 이후엔 아침 브리핑을 다시 새로 돌리지 말고 "오늘 아침에 봤던 그거" 재전송)
   - 범위: `server/api/briefings_on_demand.py` 의 `/run` 에 시간대 분기 추가, `core/briefing/parts_store.py` 에 `get_last_run_before(pipeline, hour)` 추가, `server/telegram/commands.py` 의 `/briefing_pre` 핸들러
   - 예상: 2~3h, 한 세션

2. **남은 팀 레지스트리 완전 청산 (Phase 2 정리)**
   - 왜: `core/registry.py`·rollup 잡 3종·`/api/teams`·scaffold·validate·pyproject 가 teams/ 를 전제 → 새 pipelines/ 기반 동료 개발자가 헷갈림 + `teams/registry.yaml: missing` 같은 warning 계속 출력. "산 것은 살리고 죽은 것은 묻는다" 의 두 번째 단계
   - 범위: `core/registry.py` 를 `pipelines/_registry.py` 에 흡수하거나 호환 레이어로 변환 / `rollup_all_teams` → `rollup_all_pipelines` 로 리네임 또는 제거 / `server/schedulers/jobs/*_rollup.py` 3개 재작성 or 비활성화 / `GET /api/teams` 철거 또는 pipelines 미러 / `scripts/validate.py`·`scripts/scaffold.py` 재작성 / `pyproject.toml` L65·L69 에서 `teams` 제거 / `core/config/schema.py` 의 `TeamsConfig`·`include_teams` 정리 / `docs/CONTRACTS.md:299` 예시 교체
   - 예상: 2~4h, 회귀 테스트 필수(서버 부팅/스케줄러)

3. **knowledge/canon/ 4 파일 주입 인터뷰**
   - 왜: 오늘 `/run?force=true` 에서 실 LLM scenario 판단이 나왔지만 일반론 수준. canon 이 채워지면 "이 사용자의 에이전트" 로 진화. Phase 3 (RAG) 진입 전에 채우면 RAG 효과 즉시 체감
   - 범위: `knowledge/canon/investment-principles.md`, `macro-framework.md`, `sector-insights.md`, `failure-lessons.md` 4파일의 TODO. 주제별 Q&A → MD 편집. 코드 변경 0
   - 예상: 1.5~2h

### 다음 단계 후보
4. TIMEBASED-002 Phase 2 — `pipelines/market_briefing/` 신규 + `/briefing_now` (3~4h)
5. TIMEBASED-002 Phase 3 — `pipelines/close_briefing/` + RAG ingest 실장 + `/briefing_close` (4~6h, 가장 복잡)
6. 종목명→ticker 정확도 본격 개선 (KOSPI/KOSDAQ 시총 시드 테이블 또는 KIS 마스터 연동)
7. GitHub 원격 연결 결정 (현재 미연결)

### 기술 부채 (Phase 2 정리에 흡수)
8. `core/config/schema.py::TeamsConfig` 의 `principles`·`daily_briefing`·`orchestrator` 필드 — 아직 참조하는 코드가 있는지 전수 검사
9. `server/schedulers/jobs/gap_filler.py` 가 팀 개념 참조하는지 확인 (오늘 검사 범위 밖)

## 맥락 재진입 힌트 (다음 세션이 열어볼 파일)

- `docs/specs/BRIEFING-TIMEBASED-002-timebased-briefings.md` — Phase 1~3 설계 원문
- `pipelines/morning_pre/stages/analyze.py` — `_read_prompt()` 가 `pipeline_prompts_dir()` 로 교체된 형태 (Phase 0 참조 기준)
- `core/briefing/parts_store.py` — Phase 1 에서 `get_last_run_before()` 추가 대상
- `server/api/briefings_on_demand.py` — Phase 1 분기 로직 들어갈 곳
- `core/registry.py` + `core/memory/rollup.py` — Phase 2 정리 핵심 파일
- `justfile` 최상단 — `VIRTUAL_ENV` export 참고 (다른 정책 추가 시 같은 위치)
- `C:\Users\HOME\.claude\plans\cozy-crafting-flask.md` — 오늘 플랜 파일

## 커밋 상태

- ✅ 2 커밋 완료 + 로컬 main FF merge
  - `93f30d2 chore(cleanup): purge legacy teams.orchestrator remnants + pipelines/-based STRUCTURE.md`
  - `15fd09e ops(dev-env): share main worktree .venv across all worktrees via VIRTUAL_ENV`
- main tip: `15fd09e` (새 worktree 즉시 적용)
- GitHub 원격 미연결 상태 유지

## 세션 중 실 비용

- LLM 호출 1회 (`/run?force=true` 두 번째 실행, 첫 번째는 google-genai import 실패로 scenario 비었음)
- 텔레그램 발송 총 6건 (resend 3 + run 3, 모두 사용자 지시)
