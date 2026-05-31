---
spec_id: SCREEN-RS-EXTENSION-001
title: 종목 스크리닝 RS + 과열도 — 오닐식 상대강도(후보 풀 정규화) + 과열도(ADR 정규화) + regime 가중 (prism v2.13.0 #289 차용)
team: shared
type: feature
status: implementing
version: 1
owner: stock_picker
generates:
  - collectors/screening.py                          # 후보 풀 RS + 과열도 랭킹 orchestrator (I/O 계층, sector_rs.py 패턴)
  - config/screening.yaml                            # regime 가중치 + RS/ADR 윈도우 외부화 (하드코딩 금지)
  - tests/test_screening_rs.py                       # 결정론 검증 (cutoff_date + 같은 입력 → 같은 출력 ±0)
modifies:
  - collectors/scoring.py                            # stock_rs_score / extension_score / screening_score 순수 함수 추가
  - agents/analysts/stock_picker/persona.md          # S-Score rs 축 + buy_score L(Leader) 축이 종목 RS·과열도 참조하도록
depends_on:
  - INFRA-CHART-DATA-001 v2 (chart_ohlcv 종목별 일봉 — 60일 close + MA20 + 일중 high/low 산출 입력)
  - ANALYST-PERSONAS-001 v3 (collectors/scoring.py 순수 함수 home + stock_picker S-Score rs / buy_score L 축 권위)
  - INFRA-SNAPSHOT-EXTEND-001 v1 (collectors/sector_rs.py 섹터 RS 패턴 — 본 SPEC 이 종목 레벨로 확장)
related:
  - prism-insight v2.13.0 #289 (오닐식 RS + extension 스크리닝 차용 출처. memory: prism-insight 차용 백로그 § v2.13.0 B)
  - feedback_backtest_essence (결정론 함수 = cutoff_date + 캐싱 default. 백테스팅 본체는 SLOT 분리)
  - STRATEGY-TRACK-001 v2 (Track A·B 진입 후보 = 본 스크리닝 상위 종목)
contracts:
  - name: screening-rank-v1
    version: "1.0"
    description: "collectors.screening.rank_candidates() 결과 = 종목별 {ticker, rs_score(0~10), extension_score(0~10), screening_score(0~10, regime 가중 합성), rank} 리스트. 모든 점수 0.5 단위. 결정론 함수 + cutoff_date 인자 = 백테스팅 친화 (과거 OHLCV 시뮬레이션 가능)."
---

# SCREEN-RS-EXTENSION-001 — 종목 스크리닝 RS + 과열도

## 목적

종목 후보 선정(스크리닝)을 **"당일 급등률"** 단일 기준에서 오닐(O'Neil)식 **"상대강도(RS) + 과열도(extension)"** 합성 기준으로 전환한다. 시장보다 **꾸준히 강한 진짜 주도주**를 위로, 이미 고점까지 치솟은 **과열(climax, 막판 불꽃) 종목**을 아래로 정렬한다.

prism-insight v2.13.0 #289 이 라이브에서 검증한 문제 — "당일 급등률로만 고르면 이미 고점까지 치솟은 과열 종목이 후보 상위에 올라오고, 매수 분석가가 정당하게 저점수로 거부 → 강세장 병목" — 을 우리 결정론 채점 인프라(`collectors/scoring.py` 순수 함수)로 흡수한다.

본 SPEC 산출물은 `stock_picker` 의 **S-Score `rs` 축**(주도주 점수)과 **buy_score `L`(Leader) 축**(CAN SLIM)의 결정론 base 가 된다. 현재 `collectors/sector_rs.py` 는 **섹터 레벨 RS 만** (KOSPI 대비 excess return) 제공 — 본 SPEC 이 **종목 레벨 RS(후보 풀 정규화) + 과열도** 를 신설한다.

## 배경 / 문제

### 현황 (2026-05-29)
- `collectors/sector_rs.py`: 14 섹터 ETF 의 60일 수익률을 KOSPI 대비 excess return 으로 환산 (섹터 레벨). 종목 레벨 RS 부재.
- `collectors/scoring.py`: `s_score(rs, supply_chain, alignment)` 의 `rs` 축, `buy_score(..., l, ...)` 의 `L` 축이 **입력 인자만 받고 산출 함수가 없음** — 호출부가 rs/L 점수를 어디서 만드는지 미정의 (placeholder).
- 종목 스크리닝(후보 풀 선정) 로직 자체가 아직 코드로 없음 — 본 SPEC 이 첫 정식화.

### prism v2.13.0 #289 라이브 관찰 (차용 근거)
> "NAVER 가 최고 모멘텀(0.662)이지만 약한 RS 로 3위, 대덕전자가 RS 1.000 으로 1위 — 오닐식 모멘텀 주도주 선정 의도 확인."

→ 당일 모멘텀(급등률)이 높아도 RS(60일 상대강도)가 약하면 하향, RS 가 꾸준히 강하면 상향. 본 SPEC 의 핵심 의도.

## 핵심 정의

### 1. RS Score (상대강도, 후보 풀 정규화) — `scoring.stock_rs_score`

오닐식 RS rating 의 본질 = **후보 풀 내 상대 순위**. 절대 수익률이 아니라 "같은 시점 다른 종목 대비 얼마나 강한가".

```
stock_return_60d = (close_t / close_{t-60} - 1) × 100        # 종목 60거래일 수익률 (%)
rs_score = 10 × percentile_rank(stock_return_60d, pool_returns_60d)   # 후보 풀 내 백분위 → 0~10
```

- `pool_returns_60d`: 같은 시점 후보 풀 전 종목의 60일 수익률 리스트.
- `percentile_rank`: 풀 내 백분위 (0.0~1.0). 풀 최강 = 1.0(10점) / 최약 = 0.0(0점) / 중앙값 = 0.5(5점).
- 0.5 단위 반올림, [0,10] clamp (scoring.py 공통 규약).
- 순수 함수: `(stock_return_60d, pool_returns_60d) → rs_score`. LLM 호출 X.

> **SLOT R1 (정규화 방식)**: percentile_rank(오닐 truest) vs KOSPI excess return(sector_rs 일관) vs z-score. production 검증 시 확정.
<!-- SPEC:INTERVIEW-SLOT role="rs-normalization-method" -->

### 2. Extension Score (과열도, ADR 정규화) — `scoring.extension_score`

종목이 MA20(20일 이평선) 위로 얼마나 떠 있는가를, 그 종목 **자체 변동성(ADR)** 단위로 정규화 → 막판 불꽃(climax) 페널티.

```
extension = (price - ma20) / ma20                            # MA20 대비 이격 (비율)
ADR = mean((high_i - low_i) / close_i  for i in last N days) # 평균 일중 변동폭 (Average Daily Range)
normalized_extension = extension / ADR                       # "ADR 몇 개분만큼 MA20 위인가" = 과열 정도
extension_score = clamp(10 - k × normalized_extension, 0, 10)  # 높을수록 건강(덜 과열) / 낮을수록 과열
```

- `extension_score` 는 **"건강도"** 방향 (높을수록 좋음) — RS Score 와 합성 시 부호 일관성 확보.
- ADR 정규화의 의도: 변동성 큰 종목은 MA20 위 이격이 커도 정상, 변동성 작은 종목이 크게 떠 있으면 과열. 종목별 변동성 차이 흡수.
- 순수 함수: `(price, ma20, adr) → extension_score`. LLM 호출 X.

> **SLOT R2 (스케일 계수 k + ADR 윈도우 N)**: prism 도 "extension/RS 임계는 라이브 분포 기준 튜닝 필요" 명시. k·N 은 `config/screening.yaml` 외부화 + production 분포로 정정. 초기값 k=1.0 / N=14 (placeholder).
<!-- SPEC:INTERVIEW-SLOT role="extension-scale-tuning" -->

### 3. Regime 가중 합성 — `scoring.screening_score`

시장 체제(`market_state_analyzer` 발행 6단계)별로 RS vs 과열도 가중을 달리한다. prism: "강세장은 RS 강조(0.30)·과열 페널티 약화(0.15), 약세·횡보는 반전."

```
screening_score = (w_rs × rs_score + w_ext × extension_score) / (w_rs + w_ext)   # 0~10
```

| 시장 체제 | w_rs | w_ext | 의도 |
|---|---|---|---|
| parabolic / strong_bull | 0.30 | 0.15 | RS(주도주) 강조, 강세장은 과열 어느 정도 허용 |
| moderate_bull | 0.25 | 0.20 | 균형 |
| sideways | 0.15 | 0.30 | 과열 페널티 강조 (횡보장 막판 불꽃 회피) |
| bear (moderate/strong) | 0.15 | 0.30 | 과열 페널티 강조 (또는 STRATEGY-TRACK-001 매매 중단 우선) |

- 가중치는 **`config/screening.yaml` 외부화** (절대 원칙 #8·#9 하드코딩 금지 / 재시작 없이 반영). 위 표는 prism 차용 초기값 = SLOT.
- 순수 함수: `(rs_score, extension_score, regime, weights) → screening_score`.

> **SLOT R3 (가중치 정식 확정)**: prism 초기값 직차용. production 분포 + 백테스팅 후 확정.
<!-- SPEC:INTERVIEW-SLOT role="regime-weight-finalize" -->

## 입력
- `chart_ohlcv` 테이블 (INFRA-CHART-DATA-001): 후보 풀 각 종목의 일봉 60+거래일 (close, high, low).
- 후보 풀 ticker 리스트 (스크리닝 대상 universe — 호출부 제공).
- 시장 체제 (`market_state_analyzer` team_outputs, 6단계 중 하나).
- `config/screening.yaml`: regime 가중치 + k + N + RS 윈도우(60).

## 출력
- `collectors.screening.rank_candidates(tickers, regime, cutoff_date=None)` → `screening-rank-v1` 리스트 (종목별 rs_score / extension_score / screening_score / rank).
- DB 저장 X — 호출 시점 chart_ohlcv read 만으로 충분 (lazy compute, sector_rs.py 패턴 동일).

## 판단 로직
<!-- SPEC:INTERVIEW-SLOT role="judgment-logic" -->

## 백테스팅 친화 (feedback_backtest_essence 정합)
- 모든 scoring 함수 순수 (같은 입력 → 같은 출력 ±0).
- `rank_candidates(..., cutoff_date)`: cutoff_date 지정 시 그 시점까지의 OHLCV 만 read → 과거 임의 시점 스크리닝 재현 (백테스팅 시뮬레이션).
- 백테스팅 본체(성과 추적·승률 검증)는 본 SPEC scope 밖 — 별도 SPEC.

## 엣지 케이스
<!-- SPEC:INTERVIEW-SLOT role="edge-cases" -->
- 후보 풀 1종목 (percentile 정의 불가) → rs_score = 5.0 (중립) fallback.
- 60일 미만 데이터 (신규 상장) → 해당 종목 rs_score = None, 랭킹 제외 + 사유 명시.
- ADR = 0 (거래 정지·이상치) → extension_score = 5.0 (중립) fallback, division-by-zero 가드.
- MA20 산출 불가 (20일 미만) → extension_score = None.

## 완료 기준
- [ ] `scoring.stock_rs_score / extension_score / screening_score` 순수 함수 + `tests/test_screening_rs.py` 결정론 검증 (같은 입력 → 같은 출력 ±0).
- [ ] `config/screening.yaml` 외부화 (하드코딩 0, watchdog 반영).
- [ ] `collectors/screening.py` rank_candidates + cutoff_date 백테스팅 인자.
- [ ] `stock_picker` persona 의 S-Score rs 축 + buy_score L 축이 본 함수 참조하도록 정합.
- [ ] `just validate` 통과 (frontmatter / generates 경로 / manifest).

## SLOT 분리 (본 SPEC scope 밖, 후속)
- **SLOT R1/R2/R3**: 정규화 방식·스케일 계수·가중치 production 확정 (위 INTERVIEW-SLOT).
- **백테스팅 본체**: `SCREEN-BACKTEST-NNN` (가칭) — 스크리닝 상위 종목의 후속 성과 추적·승률.
- **US 시장 스크리닝**: prism 도 US 는 본 재설계 제외(slot/sector cap 병목). 우리도 미장 도입 SPEC 후속.
