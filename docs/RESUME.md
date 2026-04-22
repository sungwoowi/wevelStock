# RESUME — 작업 재진입 상태판

> 이 파일은 **항상 최신 상태**로 유지됩니다. 세션을 새로 열 때 `/resume` 만 치면 이 파일을 읽고 플랜모드로 브리핑합니다.
>
> 갱신 주기: 의미 있는 작업 완료 후 `/wrap-up` 실행 시 자동 갱신.
> 수동 편집도 자유 — 구조만 지키면 됩니다.

---

## 📍 지금 어디 있나

**현재 위치**: BRIEFING-ON-DEMAND-001 v1 **구현 완료** (30 tests passed, 텔레그램 봇 + REST API 4종 + DB cache guard). 이어서 v2 기획 완료 — BRIEFING-TIMEBASED-002 SPEC draft 작성. 다음 세션은 **Phase 0→3 순서로 3종 브리핑 구현**.

**마지막 작업일**: 2026-04-23
**마지막 세션 로그**: [2026-04-23_briefing-on-demand-v1-and-timebased-plan.md](c_worked/2026-04-23_briefing-on-demand-v1-and-timebased-plan.md)
**Git**: `main` 브랜치, 최신 커밋 `8ed8d64 fix(tests): isolate test env from real telegram API calls`. v1 3 커밋 fast-forward 머지됨. GitHub 원격 미연결

---

## 🎯 다음에 할 일 (Top 3)

우선순위 순. 마음에 드는 것 하나를 `/resume` 인터뷰에서 고르세요.

### 1. BRIEFING-TIMEBASED-002 구현 (Phase 0~3)
- **왜**: v1 이 단일 파이프라인 공용 플랫폼을 증명. v2 는 **컨텐츠 성격별 3종 브리핑**으로 실제 투자 판단 사이클을 완성. pre(준비) + now(관찰) + close(회고+RAG) 가 DB 에 누적되면 적중률 채점 + 도메인 고도화 기반이 갖춰짐.
- **SPEC**: [docs/specs/BRIEFING-TIMEBASED-002-timebased-briefings.md](specs/BRIEFING-TIMEBASED-002-timebased-briefings.md) (draft, 완료 기준 11개)
- **범위**:
  - Phase 0 (30분): `analyze.py` 프롬프트 경로 하드코딩 리팩터 + run_id 명명 규칙 문서화
  - Phase 1 (2~3h): `/briefing_pre` 09:00 이후 보관본 재전송 validation
  - Phase 2 (3~4h): `pipelines/market_briefing/` 신규 + 한국 시장 collectors 3종 + `/briefing_now`
  - Phase 3 (4~6h): `pipelines/close_briefing/` + RAG ingest 실장 + `/briefing_close` (가장 복잡)
- **예상**: 총 10~15h, **2~3 세션 분량**. Phase 3 은 독립 세션 권장.

### 2. knowledge/canon/ 내용 주입 인터뷰 (브리핑 퀄리티 직결)
- **왜**: 파이프라인 동작은 검증됐지만 LLM 판단이 일반론 — 사용자 투자관·섹터 관점·실패 교훈이 없어서. canon 을 채워야 "이 사용자의 에이전트" 가 됨. Phase 3 (RAG) 진입 전 채워두면 효과 즉시 체감.
- **범위**: `knowledge/canon/investment-principles.md`, `macro-framework.md`, `sector-insights.md`, `failure-lessons.md` 4파일의 TODO. 주제별 Q&A → 편집.
- **예상 산출**: 4 MD 파일 업데이트. 코드 변경 없음. 1.5~2h.

### 3. 기존 기술 부채 정리
- **왜**: 누적된 legacy 잔재가 점점 신규 작업 간섭. 한 번 정리.
- **범위**:
  - `tests/test_e2e.py` — legacy `teams.orchestrator` import. skip marker 또는 삭제
  - `docs/STRUCTURE.md` — 구버전 (teams/ 기준). pipelines/ 기반으로 재작성
  - `scripts/demo.py`, `server/api/demo.py` 의 teams.orchestrator 잔재
- **예상**: 1~1.5h.

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
- `pipelines/morning_pre/` — 8 stages, 실전 Gemini 검증 완료. 야간/거시/뉴스/포지션/원칙/분석/persist/notify
- `core/briefing/` — **NEW**. `render.py`(파이프라인별 렌더러 공용) + `parts_store.py`(briefing_parts upsert/get + age 기반 cross-process cache)
- `core/contracts/briefing_part.py` — **NEW**. `briefing-part-v1` Pydantic 계약
- `server/api/briefings_on_demand.py` — **NEW**. 4 엔드포인트 (`/latest`, `/latest/parts/{key}`, `/run`, `/resend`) + in-memory 60s TTL + DB 60s cache guard (다중 인스턴스·재기동 중복 방지)
- `server/telegram/` — **NEW**. `python-telegram-bot` long-polling + 3 명령어 + chat_id 화이트리스트
- `collectors/` — us_markets(+usdkrw) / kr_futures / news_rss / fear_greed(CNN 비공식 API)
- `core/db/schema.sql` **v3** — briefing_parts 추가 (pipeline_id/run_id/part_key 유니크, ON CONFLICT REPLACE)
- `core/config/loader.py` — **운영 개선**: `.env` 자동 탐색(find_dotenv 방식) + DB path 메인 worktree root 기준 절대화
- `core/logging/__init__.py` — httpx/httpcore/telegram.ext 로거 WARNING (토큰 URL 유출 차단)
- `pyproject.toml` — `python-telegram-bot>=21.0` 추가, `yfinance`/`fredapi` 기본 deps 승격
- `conftest.py` — 2중 test isolation: WEVELSTOCK_SKIP_DOTENV + notify autouse fake (실 텔레그램 호출 차단)
- 세션 연속성: RESUME.md / SESSIONS.md / c_worked/ / `/resume` + `/wrap-up` / CLAUDE.md 규칙
- Git: `main` 브랜치, 최신 `8ed8d64`. 세션별 커밋 축적 중 (로컬, GitHub 원격 미연결)
- SPEC 2종: **BRIEFING-ON-DEMAND-001** (implementing, v1 완료) + **BRIEFING-TIMEBASED-002** (draft, v2 설계)

### 미완 또는 의도적 공백
- **BRIEFING-TIMEBASED-002 구현 0줄** — SPEC draft 만. Phase 0~3 순서로 다음 세션 착수 (10~15h)
- `knowledge/canon/*.md` 의 TODO — 여전히 대기. Phase 3 (RAG) 전에 채우면 효과 즉시 체감
- `core/knowledge/retrieve.py` 는 Chroma 호출 skeleton 만. **ingest/embed 0** — Phase 3 에서 실장
- 종목명→ticker 정확도 본격 개선 (현재는 placeholder→`""` 정규화만). KOSPI/KOSDAQ 시총 시드 테이블 또는 KIS 마스터 연동이 follow-up
- `scripts/demo.py`, `tests/test_e2e.py`, `server/api/demo.py` 의 `teams.orchestrator` 잔재 — Top 3 #3 에 편입
- `docs/STRUCTURE.md` 구버전 (teams/ 기준, 실제는 pipelines/)
- 스케줄러의 scheduled run_id suffix 가 아직 `#sched-*` 패턴 아님 — Phase 0 에서 정리
- GitHub 원격 미연결 (프로토타입 단계, 나중에 결정)

### 꼭 알아둘 판단

**기초·불변 원칙**
- **파이프라인 구조는 "시간대별 독립 폴더"** (사용자가 "수정 간섭 최소화"를 명시함). 공통 수집은 `collectors/` 라이브러리로만 공유, 파이프라인 간 코드 import 금지.
- **수동 관심(`watch_positions`)과 AI 시뮬(`sim_positions` + `sim_trades`) 스키마 분리**. 사용자가 실제 매매를 그대로 따라하지 않으므로 평단/수량은 AI 시뮬에서만 추적.
- **텔레그램은 3분할 렌더링**. LLM은 1회만 호출되므로 판단 연속성 문제 없음.
- **`docs/a_wanted/user_want_spec.md` 는 매 세션 초반 필수 읽기**. 작업이 프로젝트 본질에서 이탈하지 않도록 기준점 역할.

**이번 세션에 굳힌 판단**
- **시간대별 브리핑은 "컨텐츠 성격별 3종 + 시간은 validation"**: `/briefing_pre`/now/close 가 각자 다른 내용·LLM 해석 비중. `/briefing_now` 의 "now" 는 시간대가 아닌 "현재 시장 스냅샷" 의미 — pre→now→close 시제 정렬로 일관성.
- **`/briefing` 통합은 안티패턴**: 과거 run 재조회 기능을 잃음. 3 명령어 독립이 맞음.
- **DB cache guard = cross-process dedup 의 정답**: in-memory TTL 은 프로세스 로컬이라 서버 재기동/다중 인스턴스 시 무력. DB 의 `created_at` 기반 age 판정이 모든 케이스 커버.
- **git worktree 불편함 해결법**: `.env` find_dotenv 탐색 + DB 경로 메인 worktree root 절대화 + logger mute. 매 worktree 복사 불필요.
- **봇 라이브러리 토큰 유출 주의**: `python-telegram-bot` 이 INFO 레벨로 호출 URL 찍음 → httpx/httpcore 로거를 WARNING 이상으로 강제해야 안전. 로거 설정은 `core/logging/__init__.py` 에 전역 적용.
- **테스트 환경 격리 2중 안전장치 필수**: (1) `.env` skip env flag + (2) notify autouse fake. 한쪽만 있으면 사고 (오늘 실제 발생).

**직전 세션에 굳힌 판단** (계속 유효)
- **LLM 환각 방지 = "모르는 값은 빈 문자열로 정직하게 표현"**: ticker placeholder(`000000`) 사례. 프롬프트 + 코드 양쪽에서 강제.
- **브리핑은 2뎁스 멘탈모델**: Level1=파이프라인 유형(장전/장시작/장중/장마감), Level2=파트(overnight/scenario/positions). 단일 레벨로 명령어 펼치면 산만. 텔레그램은 Level1만 노출, 파트는 API/웹앱.
- **온디맨드 기본은 "즉석 새 run"** (최신 데이터 우선), cache=true 로 재전송 옵션. 과거 날짜 조회는 v1 제외.
- **텔레그램 수신**: v1 **long-polling** (로컬 개발), v3 webhook push (공개 URL 배포 시점의 최종 목표).
- **정확한 용어 요구**: VIX(변동성)와 공포탐욕(CNN FGI)은 다른 지표. 한국어 설명을 괄호로 병기하는 패턴 선호.
- **서버 `--reload` 비신뢰**: 이 레이아웃에서 파일 변경 감지 취약 → 수정 시마다 수동 재시작이 안정.
- **`google-genai` 는 base dep**: runtime.yaml provider=gemini 인데 pyproject 선언 누락이었음 — 이번에 고침.

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
