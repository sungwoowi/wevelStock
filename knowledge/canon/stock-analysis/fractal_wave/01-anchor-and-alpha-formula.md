---
canon_id: stock-analysis.fractal_wave.anchor_and_alpha_formula
analyst: stock_analyst
title: 프랙탈 파동 — anchor A·B·C + α 공식 (사용자 고유 파동분석)
source: docs/specs/WAVE-ALPHA-001-wave-alpha.md (cycle 14 SPEC frozen 2026-05-22)
distilled_at: 2026-05-22
---

# 프랙탈 파동 — anchor A·B·C + α 공식

> 사용자 고유 파동분석 framework. 박종훈 강의 인용 X.
> stock_analyst 가 종목별 verdict (confirmed_high_quality / confirmed_low_quality / inconclusive) 와
> holding_period (장기 / 중기 / 단기) 를 발행하는 핵심 인프라.

## 21 명제 구조

| 영역 | prefix | 명제 수 | 역할 |
|------|--------|---------|------|
| Anchor 정의 | **WA** | 5 | A·B·C·current 의미와 3 timeframe 적용 |
| Formula 시간 정규화 | **WF** | 4 | k₁ / k₂ / α 공식 + 외삽 메타 |
| Label + verdict + holding_period | **WL** | 4 | 5 단계 label + 매트릭스 + 매핑 |
| Edge cases | **WE** | 7 | E1~E7 처리 규칙 |
| Framework 본질 부록 | **WX** | 1 | 산출 방법론 + 백테스팅 친화 |
| **합계** | | **21** | |

**시퀀스**: 정의 (WA) → 계산 (WF) → 해석 (WL) → 엣지 처리 (WE) → 본질 (WX). 21 명제가 한 framework.

---

## WA — Anchor 정의 (5 명제)

### WA1 — A 정의: 1차 발산 시작점 ★★★★★

**한 줄**: **장기 횡보·바닥 후 첫 상승 추세 진입 직전 저점**.

**형식**: `A = (date, price)` 튜플.

**왜**:
- 첫 추세 (1차 발산) 의 출발점 = 후속 가속 비교의 기준점.
- 1차 발산 = k₁ = ln(B/A) / days(A→B) 의 base.
- A 가 명확하지 않으면 α 산출 자체가 무의미.

---

### WA2 — B 정의: 1차 발산 정점 ★★★★★

**한 줄**: **첫 추세의 최고가, 본격 되돌림 직전**.

**형식**: `B = (date, price)`.

**왜**:
- 1차 발산의 끝점 = k₁ 계산의 종점.
- B → C 사이 되돌림이 깊을수록 2차 발산의 가속이 의미 있음.

---

### WA3 — C 정의: 1차 되돌림 저점 = 2차 발산 시작점 ★★★★★

**한 줄**: **B 정점 이후 되돌림의 저점, 두 번째 상승 추세 진입 직전**.

**형식**: `C = (date, price)`.

**왜**:
- 2차 발산 (k₂) 의 출발점.
- C 가 A 보다 높으면 정상 상승 추세, A 보다 낮으면 추세 단절 (E3).
- 사용자 본질: "되돌림 깊이 → 2차 가속 잠재력" 의 핵심 변수.

---

### WA4 — current 정의: 2차 발산 진행 외삽 검증용 ★★★★

**한 줄**: **현재가 (date, price). α 가 얼마나 진행됐는지 외삽 검증**.

**왜**:
- α = ln(current/C) / days(C→current) ÷ k₁ 에서 current = 진행 시점.
- progress_to_b (current/B) 와 duration_ratio (2차/1차 시간) 로 외삽 신뢰도 자각.
- current 가 B 에 근접·돌파면 강한 신호, 멀면 잠재력 큼.

---

### WA5 — 3 timeframe 동시 적용 ★★★★★

**한 줄**: **daily / weekly / monthly 3 timeframe 각자 독립 anchor 산출**.

**왜**:
- daily = 트레이딩 (단기 ~수주), weekly = 복리 투자 (중기 3~12 개월), monthly = 시대적 황제주 (장기 6 개월~수년).
- 같은 종목도 timeframe 별로 anchor 좌표가 다름 — 각자 독립 산출.
- multi-timeframe sweet 시 가장 긴 timeframe 우선 (WL3 holding_period 매핑).

**TIMEFRAME_LIMITS** (구현 가드):

| timeframe | min_gap_days (A→B 최소 간격) | min_bars (최소 봉 수) | max_history_years |
|-----------|------------------------------|------------------------|---------------------|
| daily | 5 영업일 | 250 (1 년) | 3 |
| weekly | 35 일 (5 주) | 156 (3 년) | 5 |
| monthly | 180 일 (6 개월) | 60 (5 년) | 15 |

---

## WF — Formula 시간 정규화 (4 명제)

### WF1 — 1차 발산 일별 로그 변화율 k₁ ★★★★★

**공식**:

```python
k1 = ln(B.price / A.price) / (B.date - A.date).days
```

**왜**:
- 절대 수익률 (`B/A - 1`) 이 아닌 **로그 변화율** = 가격 비율의 자연로그.
- **일별 정규화** = 1차 발산이 6 개월이든 5 년이든 같은 단위로 비교 가능.
- 가격 0~∞ 의 비대칭 → log 로 대칭화.

---

### WF2 — 2차 발산 일별 로그 변화율 k₂ ★★★★★

**공식**:

```python
k2 = ln(current.price / C.price) / (current.date - C.date).days
```

**왜**:
- 2차 발산도 동일한 단위 (일별 로그 변화율) 로 산출.
- C → current 의 진행이 충분히 길어야 k₂ 안정 (WE1 anchor_too_close 가드).

---

### WF3 — α = k₂ / k₁ 무차원 비율 ★★★★★

**공식**:

```python
alpha = k2 / k1
```

**왜**:
- **무차원** = 종목·timeframe 무관 비교 가능.
- α = 1.0 = 두 발산이 같은 속도 (sweet 의 lower bound).
- α > 1.0 = 2차 가속 강화 (시대적 황제주 시그널).
- α < 1.0 = 2차 약화 (사이클 후반).
- α ≤ 0 = 추세 단절 (WE3 trend_broken).
- 시간 차이 반영 = "1차 5 년, 2차 1 년" 같은 비대칭 케이스에서 본질 (속도 비교) 정확.

---

### WF4 — 외삽 메타데이터 2 (progress_to_b + duration_ratio) ★★★★

**공식**:

```python
progress_to_b = current.price / B.price
# ≥ 1.0 = B 돌파 (강한 신호)
# 0.7~1.0 = B 근접 (sweet spot 근접)
# < 0.7 = 잠재력 큼 (아직 갈 길)

duration_ratio = (current.date - C.date).days / (B.date - A.date).days
# < 0.3 = 2차 너무 초기 (α 통계 약함, 외삽 신뢰도 낮음)
# 0.3~1.0 = 진행 중
# > 1.0 = 2차가 1차보다 길게 진행 (장기 추세 가능)
```

**왜**:
- α 단독 = 진행 정도 자각 못 함. progress_to_b + duration_ratio 가 외삽 검증.
- StandardOutput data § 각 alpha_* 객체에 동봉 발행 (자가 검증).

---

## WL — Label + verdict + holding_period (4 명제)

### WL1 — 5 단계 label (sweet spot + timeframe 차등 THRESHOLDS) ★★★★★

**THRESHOLDS**:

```python
THRESHOLDS = {
    'daily':   {'low': 0.5, 'sweet_lo': 1.0, 'sweet_hi': 4.0},
    'weekly':  {'low': 0.7, 'sweet_lo': 1.0, 'sweet_hi': 3.0},
    'monthly': {'low': 0.8, 'sweet_lo': 1.0, 'sweet_hi': 2.5},
}
```

**interpret_alpha(α, timeframe) → label**:

| label | 조건 | 의미 |
|-------|------|------|
| **trend_broken** | α ≤ 0 | 2차 발산이 하락 진행, 추세 단절 |
| **weak** | 0 < α < low | 2차가 1차 대비 매우 약함 (회피 zone) |
| **modest** | low ≤ α < sweet_lo | 2차 약화, inconclusive zone |
| **sweet** | sweet_lo ≤ α < sweet_hi | 진입 sweet spot ★ |
| **overheated** | α ≥ sweet_hi | 과열, 진입 늦음 위험 |

**왜 timeframe 별 차등**:
- daily 는 변동성이 커 sweet_hi 4.0 까지 허용.
- monthly 는 장기 안정성 본질, sweet_hi 2.5 면 충분히 강세.

---

### WL2 — verdict 분기 매트릭스 (long: / swing: / 중립) ★★★★★

**`long:` 호출 (Track A 중장기)** — weekly + monthly 우선:

| weekly | monthly | verdict |
|--------|---------|---------|
| sweet | sweet | confirmed_high_quality ★★ |
| sweet | modest | confirmed_high_quality ★ |
| sweet | overheated | confirmed_high_quality (단 "장기 시점 과열 경고" 메타) |
| modest | sweet | confirmed_high_quality ★ (monthly 강세) |
| sweet | weak | inconclusive (중장기 본질 흔들림) |
| weak | * | confirmed_low_quality |
| trend_broken | * | confirmed_low_quality |
| * | trend_broken | confirmed_low_quality |
| modest | modest | inconclusive |
| 그 외 | | inconclusive |

**`swing:` 호출 (Track B 단기)** — daily 우선:

| daily | weekly | verdict |
|-------|--------|---------|
| sweet | sweet | confirmed_high_quality ★★ |
| sweet | modest 이상 | confirmed_high_quality ★ |
| sweet | weak | inconclusive (중기 추세 흔들림) |
| modest | sweet | confirmed_high_quality (중기 강세 우선) |
| weak | * | confirmed_low_quality |
| trend_broken | * | confirmed_low_quality |
| daily=None (신생) | * | inconclusive |
| 그 외 | | inconclusive |

**중립 호출 (long:/swing: 없음)** — 보수적 OR 룰:
- 모든 valid timeframe 이 'sweet' 또는 'modest' 이상 → confirmed_high_quality
- 최소 1 timeframe 이 'weak' 또는 'trend_broken' → confirmed_low_quality
- 나머지 → inconclusive

---

### WL3 — holding_period 매핑 ★★★★★

verdict=confirmed_high_quality 일 때만 발행:

| 강세 timeframe (가장 긴 'sweet') | holding_period |
|---------------------------------|----------------|
| **monthly = sweet** | **장기 (6 개월 ~ 수년)** — 시대적 황제주 영역 |
| **weekly = sweet** (monthly 아님) | **중기 (3 ~ 12 개월)** — 복리 투자법 영역 |
| **daily = sweet** (weekly·monthly 아님) | **단기 (수일 ~ 수주)** — 트레이딩 영역 |

multi-timeframe sweet 시: **가장 긴 timeframe** 의 holding_period 우선.

**왜**:
- 가장 긴 timeframe 의 강세 = 본질적 추세, 단기 흔들림 무시 가능.
- 사용자 매매 본질 = "어느 시간축에서 이기는 종목인지" 의 정확한 답.

---

### WL4 — sweet spot 진입 가이드 ★★★★

**한 줄**: **sweet zone (1.0 ≤ α < sweet_hi) 이 본질 진입 영역, overheated 는 늦음 위험**.

**왜**:
- α < 1.0 (weak/modest) = 2차 발산이 아직 약함, 진입 위험.
- α = 1.0~sweet_hi (sweet) = 2차가 1차와 같거나 더 빠른 가속, 진입 sweet spot.
- α ≥ sweet_hi (overheated) = 가속이 비정상적 강함, 평균 회귀 임박 위험.
- timeframe 별 sweet_hi 차등 (daily 4.0 / weekly 3.0 / monthly 2.5) = 변동성 본질 반영.

---

## WE — Edge cases (7 명제)

| 코드 | 발생 조건 | 처리 | 명제 등급 |
|------|----------|------|-----------|

### WE1 — anchor_too_close (A→B 간격 부족) ★★★★

**조건**: `days(A→B) < TIMEFRAME_LIMITS[timeframe]['min_gap_days']`.

**처리**: `α = None, reason="anchor_too_close"`.

**왜**: A·B 가 너무 가까우면 k₁ 통계가 noise, 의미 있는 비교 불가.

---

### WE2 — k1_flat (1차 발산 평탄) ★★★★

**조건**: `|k₁| < 1e-6` (epsilon).

**처리**: `α = None, reason="k1_flat"`.

**왜**: 1차 발산이 평탄 (A ≈ B) → α 분모 0 근처, 무의미.

---

### WE3 — trend_broken (current ≤ C) ★★★★★

**조건**: `current.price ≤ C.price`.

**처리**: α 계산 가능 (음수 또는 0), label='trend_broken'. verdict 매트릭스에서 confirmed_low_quality.

**왜**: 2차 발산이 시작했어야 할 자리에서 도리어 하락 진행 = 추세 단절 명확 시그널.

---

### WE4 — insufficient_history (봉 부족) ★★★★

**조건**: `len(ohlcv) < TIMEFRAME_LIMITS[timeframe]['min_bars']`.

**처리**: `α = None, reason="insufficient_history"`.

**왜**: 최소 봉 수 미달 (monthly 60 봉 = 5 년 등) → anchor 산출 자체 불가.

---

### WE5 — ticker_too_young (신생 종목, 상장 < 1년) ★★★★

**조건**: 상장 후 250 봉 미만.

**처리**: daily 만 산출, weekly/monthly = None, reason="ticker_too_young".

**왜**: 신생 종목은 weekly/monthly anchor 의 base 자체가 없음. daily 만 의미.

---

### WE6 — llm_fallback_to_deterministic (Stage 2 실패) ★★★

**조건**: anchor 산출 2-Stage 의 Stage 2 (LLM Haiku 4.5) API 오류 / JSON parse 실패.

**처리**: 결정론 fallback = Stage 1 candidate 중 가장 최근 valid 시퀀스 (low → high → low). `data.alpha_*.source = "deterministic_fallback"` + reason="llm_fallback_to_deterministic".

**왜**: LLM 실패 시도 시스템은 작동해야 함. 결정론 fallback = 안전망.

---

### WE7 — cache cutoff 변경 (자동 무효화) ★★★

**조건**: 캐시 cutoff (daily=일자 / weekly=ISO 주 / monthly=월) 변경.

**처리**: 자동 무효화 (cache miss → Stage 2 재호출 → 새 entry).

**왜**: 시간 흐름에 따라 anchor 후보가 갱신되어야 함. cutoff 가 캐시 키 일부 → 자동 갱신.

---

## WX — Framework 본질 부록 (1 명제)

### WX1 — 사용자 고유 파동분석 영역 + 2-Stage 하이브리드 + 백테스팅 친화 ★★★★★

**한 줄**: **본 framework 는 사용자 고유 파동분석 영역 (박종훈 X). anchor 산출 = 결정론 candidate + LLM 직관 분포 + 캐싱 + manual override 4 층. 백테스팅 친화 설계 (cutoff_date 인자 + 결정론 + 캐싱)**.

**Anchor 산출 2-Stage 하이브리드**:

1. **Stage 1 (결정론 candidate)** = `extract_swing_candidates()` — percentile + 시간순 시퀀스 + min_gap 필터링. 100% 결정론, ms 단위, 비용 0.
2. **Stage 2 (LLM 직관 선택)** = Haiku 4.5 + temperature 0.0 + JSON 강제. candidate 5~10 개 중에서 A·B·C 3 점 선택. 인간 직관의 통계적 표준 분포 활용 (사용자 본질).
3. **3 단 캐싱** = cache_key `{ticker}|{timeframe}|{cutoff_date_or_period}`. daily 일 1회 / weekly 주 1회 / monthly 월 1회. 캐시 hit 률 90%+, 비용 ~$0.03/일 (100 종목 × 3 timeframe).
4. **manual override** = `manual_anchors` 테이블 (DB). 황제주 후보군 ~10 종목만 사용자 직접 박음. Stage 1+2 보다 우선.

**백테스팅 친화 설계**:
- `alpha(anchor_a, anchor_b, anchor_c, current)` 결정론 함수 + 캐싱 = 과거 시점 (cutoff_date) 재현 가능.
- 본 SPEC 의 alpha() 함수가 cutoff_date 인자 친화 = 백테스팅 본체 (SLOT S3 `WAVE-ALPHA-BACKTEST-001` 가칭) 의 base.
- 미래 성과 시뮬레이션 전 과거 데이터로 verdict 분기 + 성과 검증 가능 = 사용자 framework 진화 동력.

**왜 (사용자 본질)**:
- 프랙탈 + 로그함수 해석은 사용자 고유 영역. 박종훈 강의 직접 인용 X.
- anchor 추출은 인간 직관 영역, LLM 이 통계적 유사 답변으로 여러 사람 생각 취합한 표준 분포 역할 가능.
- 미래 성과 보기 전에 과거 백테스팅이 본 framework 의 질문 다 해소.

---

## 분석가 사용 가이드 (stock_analyst persona § 4·5·6·7 영역)

- α 산출 → WF1·WF2·WF3 인용
- label 해석 → WL1 인용
- verdict 매트릭스 → WL2 인용
- holding_period 매핑 → WL3 인용
- 엣지 케이스 처리 → WE1~WE7 인용
- 환각 가드 3 중 (cited 강제 + chart_data_md 출처 + anchor 출처) → 본 canon 21 명제 cited 강제

stock_analyst 의 StandardOutput cited 배열에 WA·WF·WL·WE·WX 중 사용한 명제 ID 박힘 강제 (persona.md v4 § 7 환각 가드 3 중).

## 향후 확장 (SLOT 분리)

- **S1** `WAVE-ALPHA-TARGETS-001` — target_prices 3 단 산출 룰
- **S2** `WAVE-ALPHA-WATCH-001` — 월봉 황제주 watchlist + 알림 cron
- **S3** `WAVE-ALPHA-BACKTEST-001` — 백테스팅 본체 (사용자 본질 영역)
- **S4** `WAVE-ALPHA-CANON-001` — 풀세트 canon W5+ 사용자 자가 정리
- **S5** anchor 자동 candidate fine-tuning (운영 6 개월 후)
- **S6** LLM Stage 2 prompt 튜닝 + Sonnet 4.6 업그레이드 (운영 3 개월 후)
