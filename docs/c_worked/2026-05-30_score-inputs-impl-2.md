---
date: 2026-05-30
topic: INFRA-SCORE-INPUTS-001 MVP 구현 — T/F-Score 원시 지표 배선 (TDD 6 마일스톤, 같은 날 2번째 세션)
status: completed
plan_file: C:\Users\HOME\.claude\plans\ancient-jumping-thunder.md
---

# 2026-05-30 · INFRA-SCORE-INPUTS-001 MVP 구현 (T/F-Score 원시 지표)

## 배경
같은 날 1번째 세션이 INFRA-SCORE-INPUTS-001 SPEC 을 작성(draft)했고, 이어서 MVP 코드를 구현. **핵심 본질**(사용자 질문 "TS 를 정량화하면 LLM 고차원 분석 기회가 없는 거 아닌가?" + prism repo 확인): 점수를 기계가 collapse 하지 않는다 — collector 가 원시 지표를 결정론 계산해 LLM 에 주입하고, **LLM 이 고차원 종합(판단=권위)**, 기존 collapse 점수(t_score/f_score)는 **advisory 참고선으로 강등**(override 가능). TDD 6 마일스톤으로 구현.

## 한 일
- `collectors/scoring.py` — `map_to_axis()` 순수 함수 신설 (구간 선형보간·V자·clamp·0.5단위, 모든 판단을 config breakpoints 로 위임) + `t_score`/`f_score` docstring "advisory 강등" 명시
- `config/score_inputs.yaml` 신규 — raw→0~10 축 매핑 breakpoints (technicals 4축 + flow 2축) + advisory 상수. SLOT S2 placeholder, watchdog 반영
- `collectors/score_inputs_config.py` 신규 — config 로더 (캐시+reload+get_breakpoints, label_dictionary 패턴 mirror)
- `collectors/technicals.py` 신규 — T-Score 원시 지표 (이격도·MACD·거래량비·R/R) compute(순수, charts.compute_indicators 재사용) + advisory t_score + render_technicals_md + build async(cutoff_date 백테스팅)
- `collectors/flow_inputs.py` 신규 — F-Score 원시 지표 (60일 외인·기관 momentum turnaround·inflow_speed·agreement[재사용]) + advisory f_score(theme_match 중립) + render + build async
- `core/inference/run_analyst.py` — `_maybe_build_technicals_md`(trader) + `_maybe_build_flow_inputs_md`(flow_analyzer) hook(α 패턴 mirror) + AnalystSpec `reads_technicals`/`reads_flow_inputs` 플래그 + run_analyst/stream 양쪽 배선 + metadata(advisory 점수 노출)
- `core/knowledge/compose.py` — build_pipeline_prompt 에 `technicals_md`/`flow_inputs_md` 파라미터 ([6b]/[6c] 블록, RAG 직전)
- `agents/analysts/trader/{manifest.yaml,persona.md}` — reads_technicals: true + Inputs 7번 항목(원시 지표 권위 + advisory override doctrine)
- `agents/analysts/flow_analyzer/{manifest.yaml,persona.md}` — reads_flow_inputs: true + Inputs 8번 항목(동일 doctrine)
- `docs/specs/INFRA-SCORE-INPUTS-001-...md` — status draft→implementing
- `tests/test_{score_mapping,score_inputs_config,technicals,flow_inputs,run_analyst_score_inputs}.py` 신규 — +38 케이스

## 검증 결과
- ✅ pytest **629 → 667 passed** (+38 신규, 회귀 0)
- ✅ `validate.py` **0 errors, 1 warning** (teams/registry.yaml 무관). cp949 우회 `PYTHONIOENCODING=utf-8`
- ✅ 커밋 + push: `be56c13` (main 직접, 솔로 프로젝트 — 사용자 결정)

## 의도적으로 안 한 것
- **라이브 smoke (005930 webapp 체감)** — 실 KIS 호출이라 자동 실행 X (TESTING=1 hook 차단 + 크리덴셜). 단위·hook 통합 테스트로 배선 결정론 검증. webapp `swing: 삼성전자` 호출 시 [5b]/[5c] 주입 육안 확인 = 별 시연 단위
- **SLOT S1/S2/S3** — theme_match 2-Stage / 매핑 임계 튜닝 / R/R 산출 규칙. 위치만 잡고 MVP 는 neutral·placeholder
- **S-Score/buy_score 배선** — rs/L 은 SCREEN-RS-EXTENSION-001, 나머지 후속 SPEC

## 기술 부채/미완
- **R/R 미산출** (SLOT S3) — build_technicals 가 rr=None 전달 → advisory 중립. 정직한 MVP (지어내기 X), md 에 "null (SLOT S3)" 표기
- **F-Score 종목 레벨 미배선** — MVP 는 시장 레벨(KOSPI/KOSDAQ) 프록시. 종목별 수급은 후속 gap
- **pytest_safety hook 오탐** — 커밋 메시지에 "pytest" 단어 있으면 차단 (실 호출 아닌데). 훅 정규식을 명령 시작 토큰만 보도록 좁히면 됨 (여유 시 백로그)
- **ANALYST-PERSONAS-001 옵션 b 정정 노트** — T/F 는 advisory+LLM 권위로 정련됨, persona 1줄 정정 권고 (별 작업, 기존 부채 유지)

## 맥락 재진입 힌트
- 본질 = 메모리 `feedback_score_collapse_advisory` (collapse 게이트키핑 금지) + `f-s-buy-t-score-input-collectors` (구현 상태).
- 배선 패턴 = α(`_maybe_build_alpha_3tf_md`) mirror. 새 축 추가 시 같은 3단(compute 순수 / render / build async + hook).
- 매핑 임계 조정 = `config/score_inputs.yaml` 만 수정 (코드 무판단, watchdog 반영).

## 다음에 이어서 할 작업 (우선순위)
1. **라이브 smoke + SLOT S3(R/R)** — 005930 webapp `swing:` 호출로 [5b]/[5c] 주입·advisory override 체감 확인 + R/R 산출 규칙(ATR vs 직전 스윙) 1개 구현해 4축 완성
2. **SLOT S1 theme_match 2-Stage** — 종목 테마↔권위 주체 결정론 candidate + LLM 선택 + 캐싱 (F-Score 최대 가중 0.4축 활성화)
3. **SLOT S2 매핑 임계 production 튜닝 + buy_score/S-Score 배선** — score_inputs.yaml breakpoints 실분포 정정 + 후속 SPEC(rs는 SCREEN-RS)

## 커밋 상태
- 코드 = `be56c13` (main, push 완료). 본 wrap-up 문서 = 별도 커밋 + push (main 직접).
