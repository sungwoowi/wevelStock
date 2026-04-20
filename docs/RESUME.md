# RESUME — 작업 재진입 상태판

> 이 파일은 **항상 최신 상태**로 유지됩니다. 세션을 새로 열 때 `/resume` 만 치면 이 파일을 읽고 플랜모드로 브리핑합니다.
>
> 갱신 주기: 의미 있는 작업 완료 후 `/wrap-up` 실행 시 자동 갱신.
> 수동 편집도 자유 — 구조만 지키면 됩니다.

---

## 📍 지금 어디 있나

**현재 위치**: morning_pre 실전 Gemini 호출 검증 완료 + 메시지 포맷 정제 + 세션 연속성 시스템 가동 중.
브리핑 온디맨드 플랫폼(BRIEFING-ON-DEMAND-001) SPEC 작성까지 끝남 — **첫 SPEC**.
다음 공백: SPEC 구현(텔레그램 봇 + 공통 API + DB v3) 또는 knowledge/canon 주입.

**마지막 작업일**: 2026-04-21
**마지막 세션 로그**: [2026-04-21_morning-pre-tuning-and-on-demand-spec.md](c_worked/2026-04-21_morning-pre-tuning-and-on-demand-spec.md)
**Git**: `main` 브랜치 (로컬), GitHub 원격 미연결 — 세션별 커밋 축적 중

---

## 🎯 다음에 할 일 (Top 3)

우선순위 순. 마음에 드는 것 하나를 `/resume` 인터뷰에서 고르세요.

### 1. BRIEFING-ON-DEMAND-001 구현 (SPEC → 코드)
- **왜**: SPEC 뼈대 완성. 이걸 구현하면 텔레그램에서 `/briefing`, `/briefing_now` 로 브리핑을 언제든 꺼내 쓰게 됨. 웹앱과 공용 REST API 라 향후 UI 확장 재료까지 준비됨.
- **범위**: SPEC의 `generates` 10개 + `modifies` 7개. DB v3 bump(`briefing_parts` 테이블) + 텔레그램 봇 long-polling(`python-telegram-bot`) + API 4종 + `core/briefing/render.py` 공용화.
- **방식**: "BRIEFING-ON-DEMAND-001 구현해줘" → SPEC 파일 읽고 순차 구현. 완료 기준 체크리스트는 SPEC 본문 참조.
- **예상**: 3~5h. 텔레그램 봇 long-polling 이 가장 큰 신규 컴포넌트.

### 2. knowledge/canon/ 내용 주입 인터뷰 (브리핑 퀄리티 직결)
- **왜**: 파이프라인 동작은 검증됐지만 LLM 판단이 일반론 — 사용자 투자관·섹터 관점·실패 교훈이 없어서. canon 을 채워야 "이 사용자의 에이전트" 가 됨.
- **범위**: `knowledge/canon/investment-principles.md`, `macro-framework.md`, `sector-insights.md`, `failure-lessons.md` 4파일의 TODO. 주제별 Q&A → 편집.
- **예상 산출**: 4 MD 파일 업데이트. 코드 변경 없음. 1.5~2h.

### 3. new_candidates ticker 정확도 개선 (작은 퀄리티 개선)
- **왜**: 오늘 Gemini 응답에서 신규 종목 ticker 를 `"000000"` placeholder 로 반환. 실전 사용 불가.
- **범위**: (a) 프롬프트에 "모르면 빈 문자열로 두세요" 지시 추가 — 15분, (b) 종목 마스터 테이블 로컬 시드 — 45분, (c) KIS API 연동 — 별도 SPEC.
- **방식**: 먼저 (a) 로 빠르게 안전장치만.

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
- `pipelines/morning_pre/` — 8 stages, **실전 Gemini 호출 검증 완료** (tokens_out=3521, cost≈$0.0015, JSON 완전 파싱)
- `collectors/` — us_markets(+usdkrw) / kr_futures / news_rss / **fear_greed**(CNN 비공식 API, User-Agent 위장)
- `core/db/schema.sql` v2 — watch_positions / sim_trades / sim_positions / predictions / news_items
- API: `/api/briefings/*`, `/api/positions/*`, `/api/pipelines/*` (+ config, notifications)
- 텔레그램 알림: HTML 볼드(`<b>`) + parse_mode=HTML + html.escape. 메시지 포맷 사용자 정제 완료(🇺🇸/🌐/글머리 `*`/괄호 한글 설명)
- 세션 연속성: RESUME.md / SESSIONS.md / c_worked/ / `/resume` + `/wrap-up` 슬래시 명령 / CLAUDE.md 규칙
- Git: `main` 브랜치, 세션별 커밋 축적 중 (로컬, GitHub 원격 미연결)
- `docs/specs/BRIEFING-ON-DEMAND-001-briefings-on-demand.md` — **프로젝트 첫 SPEC**. 스케줄 파이프라인 파트 조회/재실행/재전송 공통 플랫폼 설계

### 미완 또는 의도적 공백
- `knowledge/canon/*.md` 의 TODO (사용자 주입 대기) — **Top 후보**
- BRIEFING-ON-DEMAND-001 **구현**(SPEC 뼈대만 완료, 코드 0) — `generates` 10파일 + DB v3 bump
- `new_candidates[].ticker="000000"` placeholder 문제 (프롬프트 수정 미적용)
- `scripts/demo.py`, `tests/test_e2e.py`, `server/api/demo.py` 의 `teams.orchestrator` 잔재 (server/main.py 만 try/except 로 회피 중)
- `docs/STRUCTURE.md` 구버전 (teams/ 기준, 실제는 pipelines/)
- 09:30 / 13:00 / 16:00 / 19:00 파이프라인 미착수 — BRIEFING-ON-DEMAND v2 로드맵과 짝
- GitHub 원격 미연결 (프로토타입 단계, 나중에 결정)

### 꼭 알아둘 판단

**기초·불변 원칙**
- **파이프라인 구조는 "시간대별 독립 폴더"** (사용자가 "수정 간섭 최소화"를 명시함). 공통 수집은 `collectors/` 라이브러리로만 공유, 파이프라인 간 코드 import 금지.
- **수동 관심(`watch_positions`)과 AI 시뮬(`sim_positions` + `sim_trades`) 스키마 분리**. 사용자가 실제 매매를 그대로 따라하지 않으므로 평단/수량은 AI 시뮬에서만 추적.
- **텔레그램은 3분할 렌더링**. LLM은 1회만 호출되므로 판단 연속성 문제 없음.
- **`docs/a_wanted/user_want_spec.md` 는 매 세션 초반 필수 읽기**. 작업이 프로젝트 본질에서 이탈하지 않도록 기준점 역할.

**이번 세션에 굳힌 판단**
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
