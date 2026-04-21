---
date: 2026-04-21
topic: morning_pre new_candidates ticker placeholder 안전장치 (LLM 환각 차단)
status: completed
plan_file: C:\Users\HOME\.claude\plans\graceful-stargazing-dolphin.md
---

# 2026-04-21 · morning_pre ticker placeholder 안전장치

## 배경
직전 세션(`2026-04-21_morning-pre-tuning-and-on-demand-spec`) 의 실전 Gemini 호출에서 `new_candidates[].ticker` 가 `"000000"` 같은 placeholder 로 반환되었음. 한국 종목코드는 `005930(삼성전자)` 같은 **실제 매매 식별자**라, placeholder 가 들어오면 향후 KIS 시세 조회·매매 시뮬·알림 표시에 직접 영향. RESUME.md Top 3 #3 ("15분 빠른 패치") 항목 처리.

본질(데이터 신뢰성 · LLM 환각 방지) 측면에서 **"모르면 정직하게 빈 문자열"** 강제.

## 한 일

### 프롬프트 가이드 보강
- `pipelines/morning_pre/prompts/briefing.md` — 작성 가이드 #5 에 "ticker 를 확실히 모르면 빈 문자열 `""`, 절대로 `"000000"`/`"00000"`/`"------"` 같은 placeholder 금지" 한 문장 추가. `name`/`sector` 만으로 식별 허용 명시.

### 응답 정규화 (코드)
- `pipelines/morning_pre/stages/analyze.py`
  - `_sanitize_new_candidates(parsed)` 신규 — `parsed["new_candidates"]` 순회, `0/-/_/?/x/X/공백` 만으로 구성된 ticker 를 빈 문자열로 정규화. `name` 이 비어 있으면 항목 자체 drop. in-place 변경.
  - `_parse_llm_response` 직후, `_normalize_verdict` 호출 직전에 한 줄 호출 추가.

### 단위 테스트
- `pipelines/morning_pre/tests/test_smoke.py` — `test_sanitize_new_candidates_strips_placeholder_tickers` 추가. 5 케이스 (000000 placeholder / `------` placeholder / 정상 ticker 보존 / name 없으면 drop / 공백 ticker → 빈 문자열).

## 검증 결과
- ✅ pytest 4/4 통과 (`pipelines/morning_pre/tests/test_smoke.py`)
- ✅ 변경 라인 47줄 (3 파일, 30 LOC 이내 목표 약간 초과 — 테스트 22줄 포함)
- ✅ 정상 ticker 보존 + placeholder → `""` 변환 + name 없는 항목 drop 모두 검증
- ⏭ morning_pre 풀 재실행은 LLM 비용·시간 절감 위해 스킵 (단위 테스트로 충분 판단)

## 의도적으로 안 한 것
- **종목명→ticker 로컬 시드 테이블** — RESUME Top 3 #3 의 (b) 옵션. 45분~. 이번 패치는 안전장치만, 정확도 개선은 별도 follow-up.
- **KIS API 종목 마스터 연동** — (c) 옵션, 별도 SPEC 가치.
- **morning_pre 풀 재실행** — Gemini 호출 비용·시간. 단위 테스트로 정규화 로직 충분 검증.

## 다음에 이어서 할 작업 (우선순위)

### 즉시 실용 가치 (보류된 큰 후보 → 다음 세션에서 본격 시작)
1. **BRIEFING-ON-DEMAND-001 구현 (SPEC → 코드)** — SPEC 뼈대 완료 (`docs/specs/BRIEFING-ON-DEMAND-001-briefings-on-demand.md`). generates 10 / modifies 7. DB v3 bump(`briefing_parts` 테이블) + 텔레그램 봇 long-polling(`python-telegram-bot`) + API 4종 + `core/briefing/render.py` 공용화. 예상 3~5h. 가장 큰 신규 컴포넌트는 봇.
2. **knowledge/canon/*.md 인터뷰** — 4파일 TODO (`investment-principles.md`, `macro-framework.md`, `sector-insights.md`, `failure-lessons.md`). 사용자 투자관 Q&A → 편집. 코드 변경 없음. 1.5~2h. 효과: LLM 판단이 일반론 → "이 사용자의 에이전트".
3. **16:00 close_review 파이프라인 신규** — predictions 채점 → 적중률 사이클 완성. 본질의 "적중률 기반 고도화" 핵심. briefings-on-demand v2 manifest `parts:` 추가만으로 자연 합류.

### 다음 단계 후보
4. **종목명→ticker 로컬 시드 테이블** — 이번 패치의 follow-up. KOSPI/KOSDAQ 시총 상위 N개를 `data/seeds/tickers.json` 또는 SQLite seed table 로 시드. analyze 단계에서 LLM 응답의 `name` 으로 ticker 보강. 45분~
5. **09:30 market_open 파이프라인** — 07:00 시나리오 검증용
6. **Gemini retry/fallback** — 503 high demand 시 지수 백오프 2~3회 → anthropic fallback (현재는 즉시 mock)

### 기술 부채
7. legacy `teams.orchestrator` 잔재 정리 (`scripts/demo.py`, `tests/test_e2e.py`, `server/api/demo.py` — `server/main.py` 만 try/except 회피 중)
8. `docs/STRUCTURE.md` 를 `pipelines/` 기반으로 재작성 (현재 `teams/` 기준 구버전)
9. `_sanitize_new_candidates` charset 확장 — 새 placeholder 패턴 발견 시 `{"0", "-", "_", "?", "x", "X", " "}` 에 추가

## 맥락 재진입 힌트 (다음 세션이 열어볼 파일)
- `docs/specs/BRIEFING-ON-DEMAND-001-briefings-on-demand.md` — 다음 큰 작업 SPEC 전체
- `pipelines/morning_pre/stages/analyze.py:93~111` — `_sanitize_new_candidates` 패턴 (다른 LLM 출력 정규화 시 참고)
- `pipelines/morning_pre/prompts/briefing.md:79` — LLM 환각 방지 프롬프트 패턴 (모르면 빈값 명시 사례)
- `knowledge/canon/*.md` — TODO 4파일

## 커밋 상태
- ✅ 커밋: `1202c16 fix(morning_pre): strip placeholder tickers from new_candidates` (worktree branch `claude/loving-hugle-1aedac`)
- ✅ main 머지: fast-forward `3ca2554..1202c16` (메인 worktree `C:/Users/HOME/claude/wevelStock`)
- GitHub 원격 미연결 — push 없음
