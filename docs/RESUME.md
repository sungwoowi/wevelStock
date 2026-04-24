# RESUME — 작업 재진입 상태판

> 이 파일은 **항상 최신 상태**로 유지됩니다. 세션을 새로 열 때 `/resume` 만 치면 이 파일을 읽고 플랜모드로 브리핑합니다.
>
> 갱신 주기: 의미 있는 작업 완료 후 `/wrap-up` 실행 시 자동 갱신.
> 수동 편집도 자유 — 구조만 지키면 됩니다.

---

## 📍 지금 어디 있나

**현재 위치**: BRIEFING-TIMEBASED-002 **Phase 0 완료** (`0a4e0b2`). 오늘 세션은 **레거시 teams.orchestrator 1단계 청산 + worktree 공용 .venv 정책 + 실 LLM 브리핑 재검증**(`/run?force=true` → scenario.non_empty=True, 텔레그램 3건 실전 발송). 다음 세션은 **Phase 1 (`/briefing_pre` 09:00 이후 보관본 validation)** 부터.

**마지막 작업일**: 2026-04-24
**마지막 세션 로그**: [2026-04-24_legacy-cleanup-venv-sharing-briefing-verify.md](c_worked/2026-04-24_legacy-cleanup-venv-sharing-briefing-verify.md)
**Git**: `main` 최신 커밋 `15fd09e ops(dev-env): share main worktree .venv across all worktrees via VIRTUAL_ENV`. 오늘 2 커밋 fast-forward 머지됨. GitHub 원격 미연결

---

## 🎯 다음에 할 일 (Top 3)

우선순위 순. 마음에 드는 것 하나를 `/resume` 인터뷰에서 고르세요.

### 1. BRIEFING-TIMEBASED-002 Phase 1 — `/briefing_pre` 09:00 이후 보관본 validation
- **왜**: Phase 0 은 이미 커밋(`0a4e0b2` — prompts helper + run_id 규약). Phase 1 이 UX 체감 제일 큼 — 09시 이후엔 새로 돌리지 말고 "오늘 아침 그거" 재전송(LLM 비용 0 + 연속성).
- **SPEC**: [docs/specs/BRIEFING-TIMEBASED-002-timebased-briefings.md](specs/BRIEFING-TIMEBASED-002-timebased-briefings.md)
- **범위**: `core/briefing/parts_store.py` 에 `get_last_run_before(pipeline, hour)` 추가 / `server/api/briefings_on_demand.py` `/run` 에 09:00 분기 / `server/telegram/commands.py` `/briefing_pre` 핸들러 validation
- **예상**: 3 파일 편집 + 테스트 2~3개. **2~3h, 한 세션 분량**.

### 2. 남은 팀 레지스트리 완전 청산 (Phase 2 정리)
- **왜**: 오늘 `teams.orchestrator` 죽은 파일 3종만 치웠고 **팀 레지스트리 시스템(core/registry·rollup·/api/teams·scaffold·validate·pyproject)은 온존**. 서버 스케줄러가 no-op 잡 3개 매일/매주/매월 돌리는 중. 새 pipelines/ 기반과 섞여 신규 개발자 혼란 + `teams/registry.yaml: missing` warning 지속.
- **범위**: `core/registry.py` pipelines 기반 재작성 or 호환 레이어 / `core/memory/rollup.py::rollup_all_teams` 정리 / `server/schedulers/jobs/{daily,weekly,monthly}_rollup.py` 재작성 or 비활성화 / `GET /api/teams` 철거 / `scripts/validate.py`·`scripts/scaffold.py` 재작성 / `pyproject.toml` L65·L69 의 `teams` 제거 / `core/config/schema.py::TeamsConfig` 정리
- **예상**: **2~4h. 회귀 테스트 필수** (서버 부팅/스케줄러). 독립 세션 권장

### 3. knowledge/canon/ 4 파일 주입 인터뷰
- **왜**: 오늘 `/run?force=true` 에서 실 LLM 해석이 나왔지만 일반론 수준("선물 하락 + 미국 혼조세로 하락 출발 가능성"). canon 이 채워져야 "이 사용자의 에이전트" 로 진화. Phase 3 (RAG) 진입 전 채우면 효과 즉시 체감
- **범위**: `knowledge/canon/investment-principles.md`, `macro-framework.md`, `sector-insights.md`, `failure-lessons.md` 4파일 TODO. 주제별 Q&A → MD 편집
- **예상**: 4 MD 파일 업데이트. 코드 변경 0. **1.5~2h**.

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
- `pipelines/morning_pre/` — 8 stages, **오늘 실 LLM(Gemini 1.73) 호출까지 실증**. overnight/scenario/positions 3 파트 정상 생성 + 텔레그램 전송 확인 (`2026-04-24T21:33:57#manual-3d4b89`)
- `core/briefing/` — `render.py` 파이프라인별 렌더러 공용 + `parts_store.py` (briefing_parts upsert/get + age 기반 cross-process cache)
- `core/contracts/briefing_part.py` — `briefing-part-v1` Pydantic 계약
- `server/api/briefings_on_demand.py` — 4 엔드포인트 (`/latest`, `/latest/parts/{key}`, `/run`, `/resend`) + in-memory 60s TTL + DB 60s cache guard
- `server/telegram/` — `python-telegram-bot` long-polling + 3 명령어 + chat_id 화이트리스트
- `collectors/` — us_markets(+usdkrw) / kr_futures(EWY proxy) / news_rss / fear_greed
- `core/db/schema.sql` **v3** — briefing_parts (pipeline_id/run_id/part_key 유니크, ON CONFLICT REPLACE)
- `pipelines/_base.py::pipeline_prompts_dir()` — Phase 0 helper (analyze.py 하드코딩 제거)
- `docs/CONTRACTS.md` — run_id 명명 규약 (`#sched-<6hex>` vs `#manual-<6hex>`)
- `justfile` 최상단 `export VIRTUAL_ENV` — **NEW**. 모든 worktree 가 메인 `.venv` 자동 공유. `git rev-parse --git-common-dir` 로 크로스 플랫폼
- `docs/STRUCTURE.md` — **pipelines/ 기반 전면 재작성**. collectors/checkers/connectors 최상위 반영, stages DAG + parts 필드
- `core/config/loader.py` — `.env` 자동 탐색(find_dotenv) + DB path 메인 worktree root 절대화
- `core/logging/__init__.py` — httpx/httpcore/telegram.ext 로거 WARNING (토큰 유출 차단)
- `conftest.py` — 2중 test isolation: WEVELSTOCK_SKIP_DOTENV + notify autouse fake
- 세션 연속성: RESUME.md / SESSIONS.md / c_worked/ / `/resume` + `/wrap-up` / CLAUDE.md 규칙
- Git: `main` 최신 `15fd09e`. 오늘 2 커밋 FF merge. GitHub 원격 미연결
- SPEC 2종: **BRIEFING-ON-DEMAND-001** (implementing, v1 완료) + **BRIEFING-TIMEBASED-002** (draft, v2 설계, Phase 0 완료)

### 미완 또는 의도적 공백
- **BRIEFING-TIMEBASED-002 Phase 1~3 미착수** — Phase 0 만 완료. 다음 Top 1
- **남은 팀 레지스트리 청산** — `core/registry.py` / `rollup_all_teams` / `server/schedulers/jobs/{daily,weekly,monthly}_rollup.py` / `GET /api/teams` / `scripts/validate.py` / `scripts/scaffold.py` / `pyproject.toml` L65·L69 / `core/config/schema.py::TeamsConfig`. 다음 Top 2. 회귀 리스크로 별도 세션
- `knowledge/canon/*.md` 4 파일 TODO — 다음 Top 3. Phase 3 (RAG) 전에 채우면 효과 즉시 체감
- `core/knowledge/retrieve.py` 는 Chroma 호출 skeleton 만. **ingest/embed 0** — Phase 3 에서 실장
- 종목명→ticker 정확도 본격 개선 (현재는 placeholder→`""` 정규화만). KOSPI/KOSDAQ 시총 시드 또는 KIS 마스터 연동
- 스케줄러의 scheduled run_id suffix 가 아직 `#sched-*` 패턴 아님 — Phase 0 의 후속
- `docs/CONTRACTS.md:299` 예시 코드가 `from teams.principles.src.agent import Agent` (비영향, Phase 2 에서 정리)
- GitHub 원격 미연결 (프로토타입 단계)

### 꼭 알아둘 판단

**기초·불변 원칙**
- **파이프라인 구조는 "시간대별 독립 폴더"**. 공통 수집은 `collectors/` 로만 공유, 파이프라인 간 코드 import 금지
- **수동 관심(`watch_positions`)과 AI 시뮬(`sim_positions` + `sim_trades`) 스키마 분리**
- **텔레그램은 3분할 렌더링** (LLM 1회만 호출). 연속성 문제 없음
- **`docs/a_wanted/user_want_spec.md` 매 세션 초반 필수 읽기**. "뇌 이식 + 자동 수집 + 연속 판단" 이 본질

**이번 세션에 굳힌 판단**
- **`uv sync` 는 worktree 안에서 VIRTUAL_ENV 미지정이면 엉뚱한 곳에 설치**. `pyproject` 에 선언만 했지 실제 설치는 안 된 상태로 장기간 방치됐을 수 있음 → justfile 최상단 `export VIRTUAL_ENV := <git-common-dir 기반>/.venv` 패턴이 해결책. `.env` 자동 탐색·DB 경로 메인 루트 절대화와 같은 계열 정책
- **"pyproject 선언 ≠ 실제 .venv 설치"**: 커밋만으론 의존성 해결 안 됨. 재현 방지는 justfile 에 박는 게 유일. 문서 경고는 잊힘
- **"resend vs run 은 근본적으로 다른 경로"**: resend = DB 캐시 재렌더(LLM 비용 0), run?force=true = 파이프라인 풀 실행(LLM 호출 + 새 run_id). 사용자가 "잘 동작하는지" 요청 시 무엇을 원하는지 명확화 필요. 이번에 resend 로 오해 발생
- **레거시 청산은 "명백한 ImportError" 와 "동작 중 no-op" 을 구분해야 한다**: 전자는 단순 삭제로 안전(오늘 완료), 후자는 서버 부팅·스케줄러·config 스키마에 연쇄 영향 → 회귀 테스트 있는 별도 세션 필요

**직전 세션들에 굳힌 판단** (계속 유효)
- **시간대별 브리핑은 "컨텐츠 성격별 3종 + 시간은 validation"**: `/briefing_pre`/now/close 독립. "now" = 시간대 아닌 현재 시장 스냅샷
- **DB cache guard = cross-process dedup 의 정답**: in-memory TTL 은 프로세스 로컬이라 재기동/다중 인스턴스 시 무력
- **봇 라이브러리 토큰 유출 주의**: python-telegram-bot INFO 로그에 호출 URL 나옴 → httpx/httpcore 로거 WARNING 강제
- **LLM 환각 방지 = "모르는 값은 빈 문자열"**: ticker placeholder 사례. 프롬프트 + 코드 양쪽 강제
- **브리핑은 2뎁스 멘탈모델**: Level1=파이프라인 유형, Level2=파트. 텔레그램은 Level1만 노출, 파트는 API/웹앱
- **정확한 용어 요구**: VIX ≠ 공포탐욕(CNN FGI). 한국어 설명 괄호 병기
- **서버 `--reload` 비신뢰**: 수정 시마다 수동 재시작이 안정

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
