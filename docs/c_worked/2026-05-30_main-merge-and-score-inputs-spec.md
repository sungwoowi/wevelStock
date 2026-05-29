---
date: 2026-05-30
topic: 하이브리드 임원 PoC main 승격 머지 + INFRA-SCORE-INPUTS-001 SPEC (T/F-Score 원시 지표 배선)
status: completed
plan_file: C:\Users\HOME\.claude\plans\ancient-jumping-thunder.md
---

# 2026-05-30 · main 머지 + INFRA-SCORE-INPUTS-001 SPEC

## 배경
2026-05-29 하이브리드 임원 PoC 가 옵션 2(종합 레이어가 병목, 데이터 아님)를 확정했고, 사용자가 PoC 를 main 으로 정식 승격하기로 결단. 머지 후 "데이터 미배선" 해소를 위해 INFRA-SCORE-INPUTS-001(F/S/buy/T-Score input collector)을 재개 — 단 SPEC 부재라 SPEC 인터뷰가 한 세션 단위. **핵심 판단**: 면담 중 사용자가 "TS 를 너무 정량적으로 매기면 LLM 이 고차원 분석할 기회가 없는 거 아닌가?" 를 제기 → prism repo 확인 결과 prism(+244%)도 점수 collapse 안 하고 원시 지표만 LLM 주입 → SPEC 을 "기계가 점수 매김" → "LLM 이 매기게 원시 지표 배선"으로 재정의.

## 한 일
### Part A — main 머지 (git, 코드 무변경)
- `toggle_natural_language_command_search` (0바이트 잡티) `git rm` + chore 커밋 `389fd98`
- `feature/hybrid-executive-poc` → **main FF 머지** (8커밋, +2188/-61) + `git push origin main`
- 가져온 것: `agents/executive/` + `core/executive/synthesize.py` + Flash 스크러버(`core/intent/formatter.py`, `config/label_dictionary.yaml`) + prism v2.13.0 SPEC

### Part B — INFRA-SCORE-INPUTS-001 SPEC 인터뷰
- `docs/specs/INFRA-SCORE-INPUTS-001-tf-score-raw-indicators.md` — 신규 draft (5라운드 면담)
  - MVP = **T-Score + F-Score 먼저** (chart_ohlcv·supply_demand_history 로 계산 가능)
  - **SCREEN-RS-EXTENSION-001 분리** (rs 축·L 축은 SCREEN-RS, T/F 축은 본 SPEC, 공용 collector, 겹침 0)
  - 직관축(theme_match) = **2-Stage 하이브리드 SLOT** (MVP neutral fallback)
  - generates: `collectors/technicals.py` + `collectors/flow_inputs.py` + `config/score_inputs.yaml` + run_analyst/compose hook(α mirror) + scoring.py raw→축 매핑 helper

## 검증 결과
- ✅ pytest **629 passed** (회귀 0)
- ✅ `validate.py` **0 errors, 1 warning** (teams/registry.yaml 무관 pre-existing). cp949 크래시는 `PYTHONIOENCODING=utf-8` 우회
- ✅ FF 머지 + push 성공 (main = `389fd98`)

## 의도적으로 안 한 것
- **INFRA-SCORE-INPUTS-001 코드 구현** — SPEC frozen 후 다음 세션 (collector + hook + config + tests)
- **S-Score/buy_score 배선** — rs/L 은 SCREEN-RS, 나머지는 후속 SPEC
- **theme_match 2-Stage 구현** — MVP neutral fallback, SLOT S1
- **Pro 발동 라우팅 / 임원 frame_mode 배선** — 별 트랙 (대기)

## 기술 부채/미완
- **doctrine 정련 미반영**: ANALYST-PERSONAS-001 v2 옵션 b("결정론 채점 권위")는 T/F 한정으로 "advisory + LLM 권위"로 정련됨 — ANALYST-PERSONAS 에 1줄 정정 노트 권고 (별 작업, SPEC 영향분석에 기록)
- **validate.py cp949 크래시** — 마지막 `✓` print UnicodeEncodeError (로직 정상). print 인코딩 가드만 추가하면 됨 (여유 시)
- **KIS rate limiter 전역화** — 기존 백로그 유지

## 맥락 재진입 힌트
- SPEC 본질 = collapse 점수 advisory 강등 + 원시 지표만 LLM 주입. 메모리 `feedback_score_collapse_advisory` + `f-s-buy-t-score-input-collectors` 갱신본 참조.
- 배선 패턴은 α(`_maybe_build_alpha_3tf_md` in run_analyst.py + `render_alpha_3tf_md` in anchors.py) 그대로 mirror.

## 다음에 이어서 할 작업 (우선순위)
1. **INFRA-SCORE-INPUTS-001 코드 구현** — `collectors/technicals.py`(이격도·MACD·거래량비·R/R) + `collectors/flow_inputs.py`(momentum·inflow_speed·agreement 재사용) + `config/score_inputs.yaml` + run_analyst 2 hook + scoring.py raw→축 매핑 + tests. SLOT S2(매핑 임계)·S3(R/R 산출)·S1(theme_match)는 위치만.
2. **Pro 발동 라우팅(SLOT S7) + 다종목 검증** — "verdict ↔ 추세 프레임 충돌 시 Pro" 트리거 설계 + 005930 외 종목 smoke
3. **임원 frame_mode 결정론 배선(SLOT S1)** — Pro "분할 진입"이 7계명·손절선 가드 안에 머무는지 점검 (advisory 비결정성 하드닝)

## 커밋 상태
- Part A(머지+잡티 제거): `389fd98` main, push 완료
- Part B(SPEC) + 본 wrap-up 문서: 이 wrap-up 에서 커밋 + push 예정
