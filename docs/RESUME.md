# RESUME — 작업 재진입 상태판

> 이 파일은 **항상 최신 상태**로 유지됩니다. 세션을 새로 열 때 `/resume` 만 치면 이 파일을 읽고 플랜모드로 브리핑합니다.
>
> 갱신 주기: 의미 있는 작업 완료 후 `/wrap-up` 실행 시 자동 갱신.
> 수동 편집도 자유 — 구조만 지키면 됩니다.

---

## 📍 지금 어디 있나

**현재 위치**: BRIEFING-TIMEBASED-002 **Phase 1 전체 완성** (M1~M6 + 부가 M3.5 force 재정의). pytest **44 passed**. 봇 `/briefing_pre` (기본=보관본) + `/briefing_pre_force` (09:00 이후 LLM 우회) 2 명령 + 이중 발송 방지 (`notify=false` 쿼리) 완료. 다음 세션은 **Phase 2** (`/briefing_now` + `market_briefing` 신규) 또는 canon 주입.

**마지막 작업일**: 2026-04-25
**마지막 세션 로그**: [2026-04-25_phase1-complete.md](c_worked/2026-04-25_phase1-complete.md)
**Git**: `main` 이번 세션 2 커밋 FF 머지. GitHub 원격 미연결

---

## 🎯 다음에 할 일 (Top 3)

우선순위 순. 마음에 드는 것 하나를 `/resume` 인터뷰에서 고르세요.

### 1. BRIEFING-TIMEBASED-002 Phase 2 — `/briefing_now` + `market_briefing` 신규
- **왜**: Phase 1 은 "장 시작 전" 만 담당. "장중 실시간 관찰" 은 별도 파이프라인이 SPEC 설계. 현재 `cmd_briefing_now` 는 v1 호환(morning_pre force) 상태 — Phase 2 에서 market_briefing force 로 의미 전환 필요.
- **SPEC**: [docs/specs/BRIEFING-TIMEBASED-002-timebased-briefings.md](specs/BRIEFING-TIMEBASED-002-timebased-briefings.md) Phase 2 섹션
- **범위**: `pipelines/market_briefing/` 신규 + KOSPI/KOSDAQ 지수·수급·섹터·주도주 collectors 3 종 + 최소 LLM 요약 (목표 비용 $0.0005) + `cmd_briefing_now` 재작성 + 09:00 이전 거부 / 09:00~09:19 경고 prefix validation
- **예상**: **4~6h, 독립 세션**.

### 2. knowledge/canon/ 4 파일 주입 인터뷰
- **왜**: 실 LLM scenario 가 일반론 수준 ("선물 하락 + 미국 혼조세로 하락 출발 가능성"). canon 이 채워져야 "이 사용자의 에이전트" 로 진화. Phase 3 (RAG) 진입 전 채우면 RAG 효과 즉시 체감.
- **범위**: `knowledge/canon/investment-principles.md` / `macro-framework.md` / `sector-insights.md` / `failure-lessons.md` 4 파일 TODO. 주제별 Q&A → MD 편집. **코드 변경 0**.
- **예상**: **1.5~2h**.

### 3. 남은 팀 레지스트리 완전 청산
- **왜**: `core/registry.py` + `core/memory/rollup.py::rollup_all_teams` + 스케줄러 no-op 잡 3종 + `GET /api/teams` + `scripts/{validate,scaffold}.py` + `pyproject.toml` L65·L69 + `core/config/schema.py::TeamsConfig` 가 여전히 teams/ 를 전제. 신규 pipelines/ 기반과 섞여 개발자 혼란 + `teams/registry.yaml: missing` warning 지속.
- **범위**: 8+ 파일 재작성/삭제, 서버 부팅 + 스케줄러 회귀 테스트 필수.
- **예상**: **2~4h, 회귀 리스크로 독립 세션 권장**.

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
- `pipelines/morning_pre/` — 8 stages, 실 LLM 실증 완료. **notify stage 가 `skip_notify` flag 존중** (M6)
- `core/briefing/parts_store.py` — **`get_last_run_before(pipeline_id, cutoff_iso, since_iso=None)` 신규** ([since, cutoff) 범위 조회, Phase 1 M1)
- `core/briefing/render.py` — 파이프라인별 렌더러 공용
- `core/contracts/briefing_part.py` — `briefing-part-v1`. **`BriefingResponse.note: str | None`** (Phase 1 M2)
- `server/api/briefings_on_demand.py` — 4 엔드포인트 + in-memory 60s TTL + DB 60s cache guard. **09:00 분기 (cache 앞, `and not force`) + `force` default False 재정의 (cache/snapshot 우회 + LLM 실시간) + `notify` 쿼리** (Phase 1 M3/M3.5/M6)
- `server/telegram/` — long-polling + `/briefing_pre` (기본=보관본) + `/briefing_pre_force` (09:00 우회) + `/briefing_now` (v1 호환) + `/help` 4 명령. **`⏰ 장 시작 전 데이터 기준 (HH:MM 생성)` prefix + `CHECKING_PRE_TEXT` 안내 + `notify=False`** (Phase 1 M4/M6)
- `collectors/` — us_markets(+usdkrw) / kr_futures(EWY proxy) / news_rss / fear_greed
- `core/db/schema.sql` v3 — briefing_parts (pipeline_id/run_id/part_key 유니크, ON CONFLICT REPLACE)
- `pipelines/_base.py::pipeline_prompts_dir()` — Phase 0 helper
- `justfile` 최상단 `export VIRTUAL_ENV` — 모든 worktree 메인 `.venv` 공유
- `core/config/loader.py` — `.env` 자동 탐색 + DB path 메인 root 절대화
- `conftest.py` — 2중 test isolation (skip_dotenv + notify autouse fake)
- **pytest 44 passed** (test_parts_store 신규 7 + test_briefing_validation 신규 5 + test_briefings_on_demand 확장)
- SPEC 2종: **BRIEFING-ON-DEMAND-001** (v1 완료) + **BRIEFING-TIMEBASED-002** (Phase 1 완료 / Phase 2~3 설계)

### 미완 또는 의도적 공백
- **Phase 2 (`/briefing_now` + market_briefing) 미착수** — 다음 Top 1. `cmd_briefing_now` 가 여전히 morning_pre force 호출 (v1 호환, Phase 2 에서 market_briefing 으로 의미 전환)
- **Phase 3 (`/briefing_close` + RAG) 미착수** — Phase 2 완료 후
- **knowledge/canon/*.md 4 파일 TODO** — 다음 Top 2
- **남은 팀 레지스트리 청산** — 다음 Top 3. 회귀 리스크로 독립 세션
- `core/knowledge/retrieve.py` skeleton, ingest/embed 0
- 종목명→ticker 정확도 본격 개선 대기
- 스케줄러 run_id suffix `#sched-*` 미적용
- "Unknown command" 원인 규명 — 텔레그램 클라이언트 캐시 추정, 내일 봇 채팅 재진입으로 자연 해소 예상
- GitHub 원격 미연결

### 꼭 알아둘 판단

**기초·불변 원칙**
- **파이프라인 구조는 "시간대별 독립 폴더"**. 공통 수집은 `collectors/` 로만 공유, 파이프라인 간 코드 import 금지
- **수동 관심(`watch_positions`)과 AI 시뮬(`sim_positions` + `sim_trades`) 스키마 분리**
- **텔레그램은 3분할 렌더링** (LLM 1회만 호출). 연속성 문제 없음
- **`docs/a_wanted/user_want_spec.md` 매 세션 초반 필수 읽기**. "뇌 이식 + 자동 수집 + 연속 판단" 이 본질

**이번 세션에 굳힌 판단 (2026-04-25)**
- **`force` 의미 = "cache/snapshot 우회 + LLM 실시간 실행"**: default False 로 뒤집음. 기본은 09:00 이후 보관본 모드, `force=true` 는 서버 다운·공휴일 등 복구 경로. 봇 2 명령어 (`/briefing_pre`, `/briefing_pre_force`) 분리.
- **09:00 분기는 cache 레이어 앞에 배치**: force=true 방금 run 이 60s cache 에 남아도 force=false 다음 호출은 보관본 분기 탐. 누수 원천 차단 (M3.5).
- **파이프라인 notify stage + 봇 `_send_briefing` 이중 발송은 v1 설계 결함**: `/run?notify=false` + `input_data={"skip_notify": True}` 로 해결. 봇은 항상 notify=False, scheduled cron 만 notify=True. 한 호출당 6건 → 3건 (M6).
- **Explore subagent 는 범위 불분명할 때만**: 파일 경로 알려진 탐색엔 직접 Read/Grep 병렬 (체감 속도 + 사용자 가시성). 피드백 → `feedback_small_milestones.md`.

**직전 세션들에 굳힌 판단** (계속 유효)
- **레거시 청산은 "명백한 ImportError" vs "동작 중 no-op" 구분**: 전자 단순 삭제 안전, 후자는 서버 부팅·스케줄러 회귀 리스크 → 별도 세션 필요 (다음 Top 3).
- **DB cache guard = cross-process dedup 정답**: in-memory TTL 은 프로세스 로컬. 재기동/다중 인스턴스 시 DB 공유 시각 기반만 신뢰.
- **정확한 용어 요구**: VIX ≠ 공포탐욕(CNN FGI). 영문 약어는 괄호에 한국어 병기.
- **서버 `--reload` 비신뢰**: 수정 시마다 수동 재시작.

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
