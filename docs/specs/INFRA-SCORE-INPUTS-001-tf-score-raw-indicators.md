---
spec_id: INFRA-SCORE-INPUTS-001
title: 점수 입력 배선 (T-Score / F-Score 원시 지표) — 결정론 지표 계산 → LLM 고차원 종합. collapse 점수는 advisory 강등
team: shared
type: feature
status: implementing
version: 1
owner: trader, flow_analyzer
generates:
  - collectors/technicals.py        # T-Score 원시 지표 (이격도·MACD·거래량비·R/R) compute + render_technicals_md (anchors.py 패턴)
  - collectors/flow_inputs.py       # F-Score 원시 지표 (60일 수급 momentum·inflow_speed) compute + render_flow_inputs_md (agreement 은 supply_demand_history 재사용)
  - collectors/theme_match.py       # SLOT S1 — theme_match 2-Stage 하이브리드 (classify_theme 결정론 후보+LLM+캐싱 / score_theme_match 결정론 / resolve_theme_match). anchors.py 패턴 mirror
  - config/score_inputs.yaml        # 원시 지표 → 0~10 축 매핑 임계 + advisory 가중 외부화 + flow.theme_authority/taxonomy/manual (하드코딩 금지, watchdog 반영)
  - tests/test_technicals.py        # 결정론 검증 (cutoff_date + 같은 입력 → 같은 출력 ±0)
  - tests/test_flow_inputs.py       # 결정론 검증
  - tests/test_theme_match.py       # theme_match 2-Stage 검증 (manual/LLM-mock/fallback + score 결정론 + 캐싱)
modifies:
  - core/inference/run_analyst.py   # _maybe_build_technicals_md (trader) + _maybe_build_flow_inputs_md (flow_analyzer) hook — _maybe_build_alpha_3tf_md mirror
  - core/knowledge/compose.py       # build_pipeline_prompt 에 technicals_md / flow_inputs_md 파라미터 신규 ([5] α block 인접)
  - collectors/scoring.py           # raw→축 0~10 매핑 helper 신설 (advisory base 용) + t_score/f_score docstring "advisory 강등" 명시
  - agents/analysts/trader/persona.md         # Inputs 에 원시 지표 + advisory T-Score 주입 / Doctrine "지표로 네가 판단, advisory override 가능"
  - agents/analysts/flow_analyzer/persona.md  # Inputs 에 원시 수급 지표 + advisory F-Score 주입 / 동일 doctrine
depends_on:
  - INFRA-CHART-DATA-001 (chart_ohlcv 종목 일봉 60+거래일 — T-Score 이격도/MACD/거래량비/R/R 산출 입력)
  - INFRA-SNAPSHOT-EXTEND-001 v1 (supply_demand_history 5주체 60일 + agreement_score — F-Score momentum/agreement 입력)
  - ANALYST-PERSONAS-001 v3 (collectors/scoring.py t_score/f_score home + trader/flow_analyzer 발행 권위)
  - WAVE-ALPHA-001 (α 배선 패턴 mirror — compute_alpha_3tf / render_alpha_3tf_md / run_analyst _maybe_build_alpha_3tf_md hook)
  - ARCHITECTURE-HYBRID-EXECUTIVE-001 (종합=LLM 판단 doctrine — collapse 점수 advisory 강등의 근거)
related:
  - prism-insight v2.13.0 (원시 지표 결정론 계산 → LLM 정성 판단 구조. 고정 가중 score collapse 안 함 = +244% 6개월 검증 구조. memory: project_prism_insight_borrowing)
  - feedback_backtest_essence (결정론 함수 = cutoff_date + 캐싱 default. 백테스팅 본체는 SLOT 분리)
  - feedback_llm_intuition_distribution (theme_match 등 직관축 = 결정론 candidate + LLM 선택 + 캐싱 2-Stage. SLOT)
  - SCREEN-RS-EXTENSION-001 (분리 경계 — rs 축(S-Score)·L 축(buy_score)은 SCREEN-RS, T/F 축은 본 SPEC. 공용 collector)
contracts:
  - name: score-inputs-v1
    version: "1.0"
    description: "render_technicals_md(ticker, cutoff_date=None) / render_flow_inputs_md(ticker, cutoff_date=None) 결과 = 원시 지표 md 블록(이격도·MACD·거래량비·R/R / momentum·inflow_speed·agreement) + advisory 점수(참고선, LLM override 가능) + source/cutoff 메타. team_outputs 저장 X (분석가 StandardOutput 이 판단 담당). α md 주입 패턴 동일."
---

# INFRA-SCORE-INPUTS-001 — T-Score / F-Score 원시 지표 배선

## 목적 (왜)

`collectors/scoring.py` 의 5 점수 함수 중 **α 만 live** (`collectors/anchors.py` 가 anchor → α 산출 → md 주입). **S/T/buy/F-Score 는 함수·테스트는 잠겨 있으나 input collector 가 0** — 분석가가 호출해도 축 값을 어디서 만드는지 없어 dormant. 본 SPEC 은 그중 **T-Score(trader) + F-Score(flow_analyzer)** 의 원시 지표를 배선한다 (MVP).

### 본질 재정의 (이 SPEC 의 핵심 결단)

면담 중 결정 — **점수를 기계가 매기는 것이 아니라, LLM 이 매길 수 있도록 원시 지표를 풍부하게 배선한다.** 근거 3 정렬:

1. **하이브리드 임원 PoC** (방금 main 머지, ARCHITECTURE-HYBRID-EXECUTIVE-001): "점수 합산식 종합"이 production UX 병목이었고, "doctrine 통합 추론(LLM 고차원)"으로 교체하니 prism 수준 도달. 기계적 게이트키핑이 품질을 죽였음.
2. **prism-insight** (+244% 6개월 실증): 코드는 원시 지표(급등 탐지·OHLCV·재무)를 모으고, **고정 가중 numeric score 로 collapse 하지 않음** — 다차원 지표를 LLM agent 가 정성 판단. 검증된 구조.
3. **CLAUDE.md 절대 원칙**: "판단은 LLM 이 하되, **데이터 수집·지표 계산은 순수 코드가 한다.**" → 선은 collapse 된 점수가 아니라 **원시 지표**에 긋는다.

### Doctrine 정련 (ANALYST-PERSONAS-001 v2 옵션 b 부분 정정)

ANALYST-PERSONAS-001 v2 는 "결정론 채점이 권위"(옵션 b)였으나, 본 SPEC 은 **T/F-Score 에 한해 정련**한다:

| 층 | 누가 | 산출 | 권위 |
|---|---|---|---|
| 원시 지표 계산 | 순수 코드 (collector) | 이격도 +12%, MACD 음전환, 거래량 1.8배, R/R 2.1, 60일 수급 turnaround, 일치도 +4 | 결정론·재현·백테스팅 친화 |
| **advisory 점수** | scoring.py collapse 함수 | t_score/f_score = 참고선 (md 에 "advisory" 라벨) | **비권위 — LLM override 가능** |
| **고차원 종합** | LLM (분석가) | "이 지표 묶음 + α + regime → 타점 강도 7, 단 손절 명확 조건" | **권위 (판단)** |

> collapse 함수(`t_score`/`f_score`)는 **삭제하지 않고 advisory 베이스라인으로 강등**한다 — 백테스팅·일관성 비교용 결정론 base 로 계산해 md 에 참고선으로 넣되, 분석가가 override. (사용자 결단 2026-05-30.)

## 경계 (Scope)

### 하는 것 (MVP)
- **T-Score 원시 지표** 4 축: 이격도(divergence)·MACD·거래량비(volume)·R/R. `chart_ohlcv` 일봉에서 결정론 계산. (α 는 이미 live — t_score 가 α override 적용하므로 anchors.py 산출값 재사용.)
- **F-Score 원시 지표** 결정론 3 축: momentum(60일 수급 turnaround)·inflow_speed(시총 정규화 자금 속도)·agreement(5주체 부호 일치도, `supply_demand_history.agreement_score` 재사용).
- 각 축 원시 지표 → md 블록 + advisory 점수 → trader/flow_analyzer 프롬프트 주입 (α 패턴 mirror).

### 안 하는 것 (후속 / SLOT)
- **S-Score(rs/supply_chain/alignment)·buy_score(CAN SLIM 7축)** — rs·L 축은 **SCREEN-RS-EXTENSION-001** 담당(분리 경계). 나머지는 후속 SPEC.
- **theme_match 직관축** (F-Score 0.4 가중, 최대 축) — 결정론 안 떨어짐. **2-Stage 하이브리드 SLOT** (위치만 잡고 MVP 는 neutral fallback). → SLOT S1.
- **collapse 가중치 정식화** — 균등/SPEC v2 placeholder 유지 (advisory 라 정밀도 비핵심). → ANALYST-PERSONAS-001 SLOT S7.
- **미장(US) 종목** — 후속.
- **백테스팅 본체** (성과 추적·승률) — 별도 SPEC.

### 다른 모듈과 겹침
- **SCREEN-RS-EXTENSION-001**: 분리. SCREEN-RS = 스크리닝(후보 풀 정규화, "어떤 종목") + rs/L 축. 본 SPEC = 종목별 T/F 원시 지표("무엇을 하라" 판단 입력). 둘 다 `chart_ohlcv` 소비하나 산출·용도 분리. 공용 지표(예: MA20)는 helper 공유 가능.
- **WAVE-ALPHA(α)**: α 는 본 SPEC 이 새로 만들지 않음 — anchors.py live 값 재사용 (t_score override 입력).

## 입력 (어디서 오나)
- `chart_ohlcv` (INFRA-CHART-DATA-001): 종목 일봉 60+거래일 (close, high, low, volume) — T-Score 전 축.
- `supply_demand_history` (INFRA-SNAPSHOT-EXTEND-001): 5주체 60일 시계열 + `agreement_score` helper — F-Score momentum/agreement.
- `collectors/anchors.py` `compute_alpha_3tf` 산출 α — t_score override 입력 (재사용).
- `config/score_inputs.yaml`: 원시→0~10 축 매핑 임계 + advisory 가중 + 윈도우.

## 출력 (형태)
- `collectors.technicals.render_technicals_md(ticker, cutoff_date=None)` → `score-inputs-v1` md 블록 (원시 지표 표 + advisory T-Score 참고선 + source/cutoff 메타).
- `collectors.flow_inputs.render_flow_inputs_md(ticker, cutoff_date=None)` → 동일 (원시 수급 지표 + advisory F-Score).
- `run_analyst` 가 trader 호출 시 technicals_md, flow_analyzer 호출 시 flow_inputs_md 를 [5] α 인접 블록으로 주입 (α `_maybe_build_alpha_3tf_md` mirror).
- **DB 저장 X** — 분석가 StandardOutput(team_outputs)이 판단 담당. md 주입은 α 패턴 동일 (lazy compute + 캐싱).

## 핵심 정의 (원시 지표 — 결정론)

### T-Score 4 축 (`collectors/technicals.py`)
- **divergence(이격도)**: `(close - ma20) / ma20 × 100` (%). MA20 대비 이격.
- **MACD**: 표준 MACD(12,26,9) — MACD선·signal선·histogram. 음전환/양전환·히스토그램 부호·크기.
- **volume(거래량비)**: `volume / mean(volume, N)` — 평균 대비 배율.
- **R/R**: 현재가 기준 (목표가 - 진입)/(진입 - 손절). 진입·손절·목표 산출 = SLOT (ATR·직전 스윙 등).

> 원시 지표는 **결정론 수학** (LLM X). 0~10 축 매핑(advisory 용)은 `config/score_inputs.yaml` 임계로 별도.

> **SLOT S2 (raw→0~10 축 매핑 임계)**: 이격도 %·MACD 크기·거래량 배율·R/R 을 0~10 으로 환산하는 임계. WAVE-ALPHA THRESHOLDS 패턴. config 외부화 + production 분포 튜닝. 초기값 placeholder.
<!-- SPEC:INTERVIEW-SLOT role="raw-to-axis-mapping" -->

> **SLOT S3 (R/R 진입·손절·목표 산출 규칙)**: ATR 기반 vs 직전 스윙 vs 전략가 위임. STRATEGY-TRACK-001 trailing 정합.
<!-- SPEC:INTERVIEW-SLOT role="rr-entry-stop-target" -->

### F-Score 결정론 3 축 (`collectors/flow_inputs.py`)
- **momentum(60일 수급 모멘텀)**: 외인·기관 누적 순매수 부호 turnaround (최근 vs 직전 구간 부호 전환·가속).
- **inflow_speed(자금 유입 속도)**: 순매수 금액 / 시가총액 — 시총 정규화 속도.
- **agreement(5주체 부호 일치도)**: `supply_demand_history.agreement_score` 재사용 (신설 X).

> **SLOT S1 (theme_match 직관축 — 2-Stage)** ✅ 구현됨 (2026-05-30, `collectors/theme_match.py`): 종목 테마 ↔ 권위 주체 매수 일치도. classify_theme = manual override → Stage1 결정론 후보(config theme_taxonomy 키) → Stage2 LLM 선택(`llm_call_cache` type='theme_match', TTL 30일, cache_key=`theme|ticker|taxonomy_ver`) → 실패/미분류 시 neutral fallback. score_theme_match = 권위 주체 net/(5주체 abs 합+1) → breakpoints 0~10. 사전 = `config/score_inputs.yaml` flow.theme_authority/taxonomy/manual. **⚠️ MVP 한계: net_sums 가 시장 레벨 프록시 — 종목 레벨 수급 collector 도입 후 입력만 교체(골격 재사용).** (feedback_llm_intuition_distribution)
<!-- SPEC:INTERVIEW-SLOT role="theme-match-2stage" -->

## advisory 점수 (collapse — 강등)
- scoring.py `t_score(div, macd, vol, rr, alpha)` / `f_score(theme, mom, inflow, agree)` 그대로 호출하되, raw→축 매핑(SLOT S2)으로 0~10 환산 후 입력.
- 결과는 md 에 **"advisory T-Score 6.5 (참고선 — 본인 판단 우선)"** 형태. 게이트키핑 X.
- t_score 의 α override(STRATEGY-TRACK-001)는 유지 — α 는 권위 지표라 advisory 안에서도 의미.

## 판단 로직
<!-- SPEC:INTERVIEW-SLOT role="judgment-logic" -->

## 백테스팅 친화 (feedback_backtest_essence 정합)
- 원시 지표·advisory 점수 함수 모두 순수 (같은 입력 → 같은 출력 ±0).
- `render_*_md(..., cutoff_date)`: 지정 시 그 시점까지 OHLCV/수급만 read → 과거 임의 시점 재현.
- 캐싱: α 패턴(llm_call_cache 또는 인메모리) 동일. 백테스팅 본체는 scope 밖.

## 엣지 케이스
<!-- SPEC:INTERVIEW-SLOT role="edge-cases" -->
- MA20 산출 불가(20일 미만) → divergence None, advisory 제외 + 사유.
- 거래정지·이상치(volume 0) → volume 축 neutral fallback.
- 수급 60일 부족(신규 상장) → momentum None, agreement 만.
- α 미발행(anchors fallback unavailable) → t_score α override 없이 base.
- theme_match 미배선(MVP) → neutral 5.0 + 명시.

## 완료 기준
- [ ] `collectors/technicals.py` 4 축 원시 지표 + render_technicals_md + cutoff_date.
- [ ] `collectors/flow_inputs.py` 3 축(momentum/inflow_speed/agreement 재사용) + render_flow_inputs_md + cutoff_date.
- [ ] `config/score_inputs.yaml` 외부화 (하드코딩 0, watchdog 반영).
- [ ] `run_analyst` _maybe_build_technicals_md(trader) + _maybe_build_flow_inputs_md(flow_analyzer) hook + compose 파라미터.
- [ ] scoring.py raw→축 매핑 helper + t_score/f_score docstring "advisory 강등" 명시.
- [ ] trader/flow_analyzer persona Inputs + doctrine ("지표로 네가 판단, advisory override").
- [ ] `tests/test_technicals.py` + `test_flow_inputs.py` 결정론 검증.
- [ ] `just validate` 통과 (frontmatter / generates 경로).

## SLOT 분리 (후속)
- **SLOT S1**: theme_match 2-Stage 하이브리드.
- **SLOT S2**: raw→축 0~10 매핑 임계 (config + production 튜닝).
- **SLOT S3**: R/R 진입·손절·목표 산출 규칙.
- **S-Score/buy_score 배선**: rs/L = SCREEN-RS-EXTENSION-001, 나머지 후속 SPEC (INFRA-SCORE-INPUTS-002 가칭).
- **백테스팅 본체**: 별도 SPEC.

## 영향 분석 (다른 모듈)
- DB 스키마 변경 **없음** (chart_ohlcv / supply_demand_history 기존 read).
- **ANALYST-PERSONAS-001 v2 옵션 b 정련**: "결정론 채점이 권위" → T/F-Score 는 "advisory + LLM 종합 권위". 본 SPEC 채택 시 ANALYST-PERSONAS 에 1줄 정정 노트 권고 (별 작업).
- trader/flow_analyzer manifest `status` 영향 없음 (persona 본문만).
- α(stock_analyst) 배선과 동형 → run_analyst hook 3개로 정렬(α/technicals/flow).
