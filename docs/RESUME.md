# RESUME — 작업 재진입 상태판

> 이 파일은 **항상 최신 상태**로 유지됩니다. 세션을 새로 열 때 `/resume` 만 치면 이 파일을 읽고 플랜모드로 브리핑합니다.
>
> 갱신 주기: 의미 있는 작업 완료 후 `/wrap-up` 실행 시 자동 갱신.
> 수동 편집도 자유 — 구조만 지키면 됩니다.

---

## 📍 지금 어디 있나

**현재 위치**: BRIEFING-TIMEBASED-002 **Phase 2 전체 완성** + 파이프라인 ID 리네이밍. pytest **64 passed**. `market_briefing_now` 신규 (LLM 없는 raw 데이터 발송), 봇 `/briefing_now` 정식 가동, 09:00 이전 fallback (DB latest 우선·`force=true` 우회), KIS volume_rank 정렬 버그 fix (`FID_BLNG_CLS_CODE` 0→3), `morning_pre`→`market_briefing_pre` / `market_briefing`→`market_briefing_now` / `morning_briefing` 삭제. 다음 세션은 **KOSDAQ limit 확대** 또는 **canon 4 파일 주입** 또는 **Phase 3 close_briefing+RAG**.

**마지막 작업일**: 2026-04-30
**마지막 세션 로그**: [2026-04-30_phase2-market-briefing-now.md](c_worked/2026-04-30_phase2-market-briefing-now.md)
**Git**: `main` 이번 세션 2 커밋 + push (사용자 명시 요청)

---

## 🎯 다음에 할 일 (Top 3)

우선순위 순. 마음에 드는 것 하나를 `/resume` 인터뷰에서 고르세요.

### 1. KOSDAQ 주도주 limit=5 → 7~10 증가
- **왜**: KIS 거래대금 정렬 fix 후 KOSDAQ 5%+ 충족 종목이 5개 초과 자주 발생 (2026-04-30 검증 시 채비/LS머트리얼즈/제룡산업/서진시스템/세명전기/제일일렉트릭/고영 등 7개+). 현 limit=5 라 짤림. KOSPI 도 동일 검토.
- **범위**: `collectors/kr_leading_stocks.py::fetch_kr_leading_stocks` 의 `kospi_limit/kosdaq_limit` 기본값 + 텔레그램 메시지 길이 4096 자 한계 확인 + 테스트 케이스 갱신
- **예상**: **30분**

### 2. knowledge/canon/ 4 파일 주입 인터뷰
- **왜**: 실 LLM scenario (`market_briefing_pre` analyze) 가 일반론 수준. canon 이 채워져야 "이 사용자의 에이전트" 로 진화. Phase 3 (RAG) 진입 전 채우면 RAG 효과 즉시 체감.
- **범위**: `knowledge/canon/investment-principles.md` / `macro-framework.md` / `sector-insights.md` / `failure-lessons.md` 4 파일 TODO. 주제별 Q&A → MD 편집. **코드 변경 0**.
- **예상**: **1.5~2h**.

### 3. Phase 3 — `market_briefing_close` 신규 + RAG
- **왜**: SPEC L134~ Phase 3 — 장 마감 후 (`/briefing_close`) 예상 vs 실제 채점 + RAG 해석. 적중률 누적 → 도메인 고도화 Agent 의 입력. 3종 브리핑 사이클 완성.
- **범위**: `pipelines/market_briefing_close/` 신규 (5 stages 중 `load_today_briefings` 신규) + `core/knowledge/{ingest,retrieve}.py` 완성 + canon → Chroma 인덱싱 + `cmd_briefing_close` 봇 핸들러 + 15:30 validation + render
- **예상**: **4~6h, 독립 세션**.

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
- `pipelines/market_briefing_now/` (신규) — 3 stages (collect_kr_market → persist → notify), LLM 없는 raw 발송, KIS 22콜 ~26s
- `collectors/kr_{indices,sectors,leading_stocks,supply_demand}.py` — KOSPI/KOSDAQ/KOSPI200 + 15종 섹터 ETF + 거래대금 풀 30 + 외인/기관/투신/연기금 (KIS 단일)
- `connectors/kis/client.py` — token 자동관리 + rate limit 1.1s + retry. **`volume_rank` 정렬 정확** (`FID_BLNG_CLS_CODE=3` 거래금액). `foreign-institution-total` summary 에 `pension_net_amount_m_sum` 포함
- `core/briefing/parts_store.py` — `get_last_run_before(pipeline_id, cutoff_iso, since_iso=None)` (Phase 1 M1)
- `core/briefing/render.py` — `render_morning_pre` + `render_market_briefing` (파트 3종: 시장개요+KOSPI200/수급+강세섹터/주도주). 백만원→억/조 단위 변환 helpers
- `core/contracts/briefing_part.py` — `BriefingResponse.note: str | None`
- `server/api/briefings_on_demand.py` — 4 엔드포인트 + cache guards. **`market_briefing_pre` 09:00 보관본 분기** + **`market_briefing_now` 09:00 fallback (force=true 우회) + `market_closed`/`market_briefing_early` note**
- `server/telegram/` — `/briefing_pre` + `/briefing_pre_force` + `/briefing_now` (장중 KIS raw, force=True notify=False) + `/help`. `_PIPELINE_RENDERERS` dispatch + 3 prefix 케이스 (`before_market_open`/`market_closed`/`market_briefing_early`)
- `core/db/schema.sql` v3 — briefing_parts (pipeline_id/run_id/part_key 유니크, ON CONFLICT REPLACE)
- **pytest 64 passed** (test_market_briefing 신규 9 + test_briefings_on_demand market_briefing_now 6 추가)
- SPEC 2종: **BRIEFING-ON-DEMAND-001** + **BRIEFING-TIMEBASED-002** (Phase 1·2 완료, Phase 3 설계만)

### 미완 또는 의도적 공백
- **KOSDAQ 주도주 limit=5 짤림** — 다음 Top 1. KIS volume_rank fix 후 5%+ 충족 종목이 자주 5+
- **knowledge/canon/*.md 4 파일 TODO** — 다음 Top 2
- **Phase 3 (`market_briefing_close` + RAG) 미착수** — 다음 Top 3
- **남은 팀 레지스트리 청산** (`core/registry.py`, `rollup.py`, scaffold scripts 등) — 별도 회귀 리스크 큰 세션
- **개인 수급 표시 안 됨** — KIS 별도 API 필요. 현재 외인/기관/투신/연기금 4종
- **KOSPI200 선물 정확 가격 안 받음** — 지수(2001) 로 대체. 선물옵션 API 별도
- **docs SPEC/STRUCTURE/pipeline-restructure-plan/wrap-up.md 의 morning_pre 텍스트 갱신 안 됨** — 코드 동작 무관, 다음 wrap-up 시
- 함수명 `render_morning_pre` 의도적 유지 (내부 함수명, 사용자 명시 안 함)
- GitHub 원격 = 사용자 push 명시 시점에 새로 연결 (이번 세션)

### 꼭 알아둘 판단

**기초·불변 원칙**
- **파이프라인 구조 = "시간대별 독립 폴더"**. 공통 수집은 `collectors/` 로만 공유, 파이프라인 간 코드 import 금지
- **수동 관심(`watch_positions`)과 AI 시뮬(`sim_positions` + `sim_trades`) 스키마 분리**
- **텔레그램은 3분할 렌더링**. 연속성 문제 없음
- **`docs/a_wanted/user_want_spec.md` 매 세션 초반 필수 읽기**. "뇌 이식 + 자동 수집 + 연속 판단" 이 본질
- **`force` = "cache/snapshot 우회 + 새 실행"**: default False, `market_briefing_now` 09:00 fallback 도 force=true 면 우회
- **데이터 무결성 우선**: KIS API 의 응답 정렬·필드 의미는 항상 의심하고 직접 검증

**이번 세션에 굳힌 판단 (2026-04-30)**
- **`market_briefing_now` 는 LLM 없이 raw 데이터만 발송**: 장중 9:30/12:00/14:00 등 빈번 호출 → LLM 비용·지연 회피. 객관 사실 (지수·수급·섹터·주도주) 표시로 충분. analyze stage 미생성
- **KIS `volume_rank` 정렬 = `FID_BLNG_CLS_CODE`** (0:평균거래량 / 3:거래금액). docs 의 `FID_COND_SCR_DIV_CODE` 는 화면 ID 일 뿐. 다른 KIS 순위 API 도 비슷한 quirk 가능 → 직접 검증 필수
- **봇 `cmd_briefing_now` 는 항상 force=True**: 09:00 이전이라도 사용자가 명시 호출하면 새 KIS run. fallback 분기에 `not force` 추가로 차별화
- **briefing_parts retention = A 방향** (시계열 누적 + 90일 cleanup cron). last-wins 단순화 안 함 (Phase 3 channel close_briefing 이 시계열 입력 필요). 별도 작은 SPEC 백로그
- **파이프라인 ID 명명 = `market_briefing_{pre,now,close}` 시간대 일관**: `morning_pre`→`market_briefing_pre`, `morning_briefing` 삭제, `market_briefing`→`market_briefing_now`. DB row + 코드 string + 봇 핸들러 일괄 마이그레이션

**직전 세션들에 굳힌 판단** (계속 유효)
- **레거시 청산 = "명백한 ImportError" vs "동작 중 no-op" 구분**: 후자는 회귀 리스크 → 별도 세션
- **DB cache guard = cross-process dedup 정답**: 재기동/다중 인스턴스 시 DB 공유 시각 기반만 신뢰
- **정확한 용어 요구**: VIX≠공포탐욕(CNN FGI), 투신(투자신탁)≠금융투자(증권사 자기매매). 영문 약어는 괄호에 한국어 병기
- **서버 `--reload` 비신뢰**: 수정 시마다 수동 재시작

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
