---
date: 2026-05-18
topic: Track A persona + 외부 리뷰 5 항목 정합 + Layer 3 production 사이클 가시화 + 첫 실 호출 검증
status: completed
plan_file: C:\Users\HOME\.claude\plans\eager-percolating-teacup.md
---

# 2026-05-18 · Track A persona + Layer 3 production 사이클 가시화

## 배경
직전 세션 (2026-05-17 두 번째) 이 `collectors/scoring.py` 시그니처 잠금만 (production 변화 0) 끝남. 본 세션 = Track A persona 작성 → 외부 R&D 리뷰 5 항목 정합 → Layer 3 production 풀스택 (CLI + FastAPI + webapp) → 첫 실 호출 검증까지 한 사이클에 통합. **핵심 판단**: 사용자가 인터뷰에서 Top 1 = persona·manifest 까지로 범위 한정 → 추천 순서 (1 CLI → 2 FastAPI → 3 webapp 토글) 가 사용자 채택 → production 사이클 가시화의 첫 마일스톤 달성. 마지막에 사용자 webapp 호출 1 회로 환각 차단 (cited_scores 다 null + verdict=wait) 확인.

## 한 일

### Track A 페르소나 + manifest (commit `ba04313`)
- `agents/strategists/track_a/persona.md` — 8 섹션 portable. 부동산 임대업 비유 + 6 분석가 team_outputs read + strategist-recommendation-v1 권고 양식 + 한국어 친화 용어 강제 + cited 풀이 v3.1
- `agents/strategists/track_a/manifest.yaml` — id/track/reads_analysts 6/canon_categories 9 dept framework 6개/input_routing/llm.temperature=0.4/response_rules
- `docs/specs/ANALYST-PERSONAS-001-...md` 격자 예시 frame 정정 (line 207-209/225/228) — canon 1:1 grep: 부채 사이클 후반(C3) → 부채 진행 J커브 가속(C1) / 통화 가치 침식(M2) → 원화 구조 구조적 약세(M2) / Dalio 5단계(위기) → 4단계(부채 축소)

### 외부 리뷰 5 항목 정합 (commit `ba04313` 안 포함)
- #2 α 오버라이드 표 상단 가드 한 줄 (stock_analyst·trader 책임 / Track A read 만)
- #3 Output 양식 분기 룰 (권고 YAML 발행 trigger + 자연어 응답 분기 — wealth_strategist 격자 trigger 패턴 미러)
- #4 `yesterday_verdict_delta` 강제 필드 (시점 일관성 자각, 격자 [5] Yesterday Delta 권고 양식 미러)
- #5 input_routing 임계값 운용 슬롯 코멘트 (Layer 5 회고분석가 PROPOSAL 영역)
- #6 옵션 A 확정 — `holding_period_estimate_days` 산출 책임 = stock_analyst 발행 위임 (persona.md § Inputs L44 + Anti-patterns 한 줄)

### Layer 3 production 풀스택 (commit `e8fc71f`)
- `core/strategist/{__init__.py, run_strategist.py}` — Layer 3 호출 엔진. `StrategistSpec` / `load_strategist_spec` / `gather_analyst_scores(target)` / `render_analyst_scores_block` / `_insert_analyst_scores_block` / `run_strategist` (async) / `run_strategist_stream`. metadata 신규 키: track / target / analyst_published/missing_count / missing_ids
- `scripts/{ask,chat}_strategist.py` — CLI 단발 + 멀티턴 REPL. `--target` 인자 + `/target <ticker>` 명령 (chat 중 변경)
- `justfile` — `ask-strategist` / `chat-strategist` 2 레시피
- `server/api/strategist_chat.py` — `POST /api/strategists/{id}/chat` + `/chat/stream` (SSE) + `GET /api/strategists/{id}` 메타. ChatRequest 에 `target: str = "global"` 필드
- `server/main.py` — strategist_chat 라우터 import + include_router
- `webapp/src/app/analyst-chat/page.tsx` — Layer 2/3 토글 + target 입력 (strategist 일 때만) + AgentMeta 유니온 + MetadataBar scores X/Y 라벨
- `tests/test_run_strategist.py` 11 cases + `tests/test_strategist_chat.py` 9 cases
- `.gitignore` 에 `data/strategist_queries/` 추가

### 메모리
- `feedback_webapp_production_ux.md` 신설 — production UX 본질 = 하나의 LLM 채팅창, 백단 0 노출. 현재 webapp 의 Layer 토글/agent_id/target 입력은 R&D 검증용 임시. 향후 자동 라우팅 (intent + 종목명 매핑 + Track Selector) 필요

## 검증 결과
- ✅ `TESTING=1 PYTHONIOENCODING=utf-8 uv run pytest tests/ -q` → **215 passed** (195 → +20, 회귀 0)
- ✅ `PYTHONIOENCODING=utf-8 uv run python scripts/validate.py` → 0 errors
- ✅ `npx tsc --noEmit` (webapp) → exit=0
- ✅ **production 첫 호출** (gemini-2.5-flash, $0.0019, 15.2s first 11142ms): Track A 가 분석가 6명 미발행 상태에서 `verdict=wait` + `confidence=10` + `cited_scores` 모두 null + `yesterday_verdict_delta="first run"` 정직 발행. cited 풀이 v3.1 + 한국어 친화 용어 정확. **결정론 시그니처 잠금 + Anti-patterns 환각 차단 production 작동 검증**

## 의도적으로 안 한 것
- **Track B persona + track_selector.py** — 본 세션 범위 (사용자 Top 1 = persona·manifest 까지). 다음 마일스톤
- **team_outputs DB 적재** — 호출처 0, GUIDANCE-ACCURACY-TRACKER-001 SPEC 후속
- **9 분석가 페르소나 v2** — cron 자동 호출 인프라도 필요 (T2 백로그)
- **webapp production UX** (백단 0 노출) — `feedback_webapp_production_ux.md` 박힘, 별도 사이클
- **target 한글 종목명 → ticker 자동 매핑** — 종목 자동완성·intent extractor 백로그

## 맥락 재진입 힌트
- **외부 R&D (chat AI Opus) ↔ Claude Code 인수인계 패턴**: 본 사이클 = 외부 5 항목 피드백 받아 정확한 위치에 grep+edit. 답변 시 "1:1 차용" 같은 모호한 용어는 사용자 의문 가능 → 사용자가 모르는 용어 등장 시 짧게 정의 (회사 비유 + 예시) 후 작업
- **plan 모드 안에서 마이크로 정정 사이클**: 외부 리뷰 받고 plan 파일 통째 새로 쓰는 패턴 효과적 (Edit 대신 Write 로 갱신). ExitPlanMode 후 task list + 정합 작업
- **production 첫 호출 = 환각 차단 검증의 골든 모먼트**: 분석가 미발행 상태가 LLM 환각 시험 최적 — Anti-patterns 잘 박혀있으면 정직하게 wait. 이번 호출 1 회로 모든 양식 정합 (cited 풀이 v3.1 / 한국어 용어 / yesterday_verdict_delta / verdict 매핑) 동시 검증
- **사용자 의도 "하나의 LLM 화면, 백단 0 노출"** = 메모리 영구화. 다음 webapp 작업 시 즉시 인지

## 다음에 이어서 할 작업 (우선순위)

1. **Track B persona + manifest + `core/strategist/track_selector.py`** (~1.5 세션) — 이원 트랙 완성. Track B = 자본 20-30% 인컴 (R/R 1.5:1+, 6 트리거 + Distribution kill switch). Track Selector = manifest `input_routing` 동적 라우팅 (명시 단축어 `long:`/`swing:`/`both:` > auto > fallback). Track A 의 manifest 패턴 그대로 + Track B 특유 필드 (반대 트랙). 동시 호출 (`both:`) 지원.

2. **자료 있는 3 분석가 페르소나 v2** (PC, ~3 세션, 1명/세션) — `principle_guardian` / `trader` / `stock_analyst`. `team_outputs` 빈 상태 해소 → Track A·B 권고가 cited_scores 채워서 풍부성 ↑. v2 양식 = 8 섹션 portable + 한국어 친화 용어 § + 결정론 채점 발행 매핑 (S/T/α/buy_score). canon 1:1 grep 패턴 동일 적용. `stock_analyst` 작성 직전 = `INFRA-CHART-DATA-001` blocker 검토 (차트 데이터 부재 시 환각).

3. **`INFRA-CHART-DATA-001` SPEC** — KIS daily chart API (`inquire-daily-itemchartprice`, 무료) + pandas-ta 사전 지표 계산 + matplotlib 차트 이미지 (vision). `stock_analyst` 의 "20일선 정배열" "MACD 골든크로스" 같은 차트 추론 항목이 환각 안 되도록 시계열 인프라 사전 구축. `WAVE-ALPHA-001` (Module A α 공식) 과 묶음 가능.

## 커밋 상태
- 2 commits + 1 push 완료
  - `ba04313` feat+docs: Track A persona + manifest + 외부 리뷰 5 항목 정합 + SPEC 격자 frame 정정
  - `e8fc71f` feat: Layer 3 전략가 production 사이클 가시화 — core/strategist/ + CLI + FastAPI + webapp Layer 2/3 토글
- wrap-up commit 진행 예정 (본 c_worked + RESUME.md + SESSIONS.md)
