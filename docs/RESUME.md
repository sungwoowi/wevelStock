# RESUME — 작업 재진입 상태판

> 이 파일은 **항상 최신 상태**로 유지됩니다. 세션을 새로 열 때 `/resume` 만 치면 이 파일을 읽고 플랜모드로 브리핑합니다.
>
> 갱신 주기: 의미 있는 작업 완료 후 `/wrap-up` 실행 시 자동 갱신.
> 수동 편집도 자유 — 구조만 지키면 됩니다.

---

## 📍 지금 어디 있나

**현재 위치**: Phase 2(morning_pre 파이프라인 기계적 뼈대) 완료 직후.
Phase 3(두뇌 이식 = knowledge/canon 채우기)이 최대 공백.

**마지막 작업일**: 2026-04-19
**마지막 세션 로그**: [2026-04-19_morning-pre-pipeline.md](c_worked/2026-04-19_morning-pre-pipeline.md)

---

## 🎯 다음에 할 일 (Top 3)

우선순위 순. 마음에 드는 것 하나를 `/resume` 인터뷰에서 고르세요.

### 1. knowledge/canon/ 내용 주입 (브리핑 퀄리티 직결)
- **왜**: 파이프라인은 완성됐으나 페르소나/지식이 빈 상태라 LLM 판단이 일반론에 머뭄.
- **범위**: `knowledge/canon/investment-principles.md`, `macro-framework.md`, `sector-insights.md`, `failure-lessons.md` 4파일의 TODO 구간을 사용자 실제 관점으로 채움.
- **방식**: 인터뷰 — 주제별 Q&A → 내용 편집.
- **예상 산출**: 4 MD 파일 업데이트. 코드 변경 없음.

### 2. morning_pre 실전 실행 + 결과 기반 튜닝
- **왜**: 실제 LLM 결과를 보고 프롬프트·스키마를 미세조정해야 완성도 올라감.
- **범위**: `POST /api/pipelines/morning_pre/run` 1회 → `data/notifications/YYYY-MM-DD.jsonl` 확인 → `pipelines/morning_pre/prompts/briefing.md` 조정.
- **전제**: `ANTHROPIC_API_KEY` 설정됨, watch_positions 에 종목 1개 이상 등록.

### 3. 16:00 마감 후 파이프라인 신규 구축 (인터뷰 필요)
- **왜**: predictions 테이블의 07:00 예측을 채점할 수 있어 "적중률 사이클"이 완성됨.
- **범위**: `pipelines/close_review/` 신규 + stages (5~7개) + 채점 로직.
- **방식**: morning_pre 때처럼 시간대 인터뷰 → 플랜 승인 → 구현.

---

## 🌱 이 프로젝트의 본질 (매 세션 반드시 참조)

- **[docs/a_wanted/user_want_spec.md](a_wanted/user_want_spec.md)** — **원 요구사항**. 이 프로젝트가 무엇을 위한 것인지 사용자가 직접 서술한 문서. 작업 방향이 본질에서 벗어나지 않도록 매 세션 초반에 반드시 읽고 내재화.

## 📂 활성 설계/계획 문서

- **[플랜: 07:00 브리핑 고도화](../../../.claude/plans/cheeky-kindling-tome.md)** — 승인 완료, 실행 완료.
- **[파이프라인 재구성 플랜](b_plan/pipeline-restructure-plan.md)** — Phase 1~4 로드맵.
- **[아키텍처 리뷰](b_plan/architecture-review-workflow-restructure.md)** — 하이브리드 6팀 3-Layer 결정.

---

## 🧩 마지막 세션이 남긴 맥락 (바로 쓸 수 있도록)

### 완성된 자산
- `pipelines/morning_pre/` — 8 stages 전부 구현, 스모크 테스트 3/3 통과
- `collectors/` — us_markets / kr_futures / news_rss (pipeline 간 공유)
- `core/db/schema.sql` — 5 신규 테이블: watch_positions / sim_trades / sim_positions / predictions / news_items
- API: `/api/briefings/*`, `/api/positions/*` (+ pipelines, teams, config, notifications)

### 미완 또는 의도적 공백
- `knowledge/canon/*.md` 의 TODO 구간 (사용자 주입 대기)
- `scripts/demo.py`, `tests/test_e2e.py` 의 `teams.orchestrator` 잔재 (서버는 try/except 로 회피 중)
- `docs/STRUCTURE.md` 구버전 (teams/ 기준)
- 09:30 / 13:00 / 16:00 / 19:00 파이프라인 미착수

### 꼭 알아둘 판단
- **파이프라인 구조는 "시간대별 독립 폴더"** (사용자가 "수정 간섭 최소화"를 명시함). 공통 수집은 `collectors/` 라이브러리로만 공유, 파이프라인 간 코드 import 금지.
- **수동 관심(`watch_positions`)과 AI 시뮬(`sim_positions` + `sim_trades`)은 스키마 분리**. 사용자가 실제 매매를 그대로 따라하지 않으므로 평단/수량은 AI 시뮬에서만 추적.
- **텔레그램은 3분할 렌더링**. LLM은 1회만 호출되므로 판단 연속성 문제 없음.

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
