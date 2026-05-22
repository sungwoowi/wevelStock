---
spec_id: WAVE-ALPHA-001
title: 프랙탈 파동 α — anchor 정의 + 시간 정규화 공식 + 3 timeframe 동시 산출 + verdict 분기 매트릭스
team: shared
type: feature
status: frozen
version: 1
owner: stock_analyst
generates:
  - knowledge/canon/stock-analysis/fractal_wave/01-anchor-and-alpha-formula.md
  - collectors/anchors.py
  - core/db/migrations/v8_wave_alpha.sql
  - tests/test_alpha.py
  - tests/test_anchors.py
modifies:
  - collectors/scoring.py
  - core/db/schema.sql
  - agents/analysts/stock_analyst/persona.md
  - agents/analysts/stock_analyst/manifest.yaml
  - core/inference/run_analyst.py
  - tests/test_data_analysts_v2.py
depends_on:
  - INFRA-CHART-DATA-001 v2 (chart_ohlcv 종목별 일봉 fetch 깊이 5~10년 확장 = monthly/weekly resample 가능. daily=1년 / weekly=3년 / monthly=5년)
  - ANALYST-PERSONAS-001 v2 (stock_analyst v3 persona § α 산출 § + verdict § + holding_period § 전면 재작성)
  - INFRA-SNAPSHOT-EXTEND-001 v1 (chart_ohlcv 적재 + run_analyst.py metadata 4 키 패턴 재사용)
contracts:
  - name: wave-alpha-v1
    version: "1.0"
    description: "stock_analyst StandardOutput data § 풀세트 = alpha_daily/weekly/monthly 3 timeframe + 5 단계 label (trend_broken/weak/modest/sweet/overheated) + 부수 메타데이터 (progress_to_b, duration_ratio) + verdict (confirmed_high_quality/confirmed_low_quality/inconclusive) + holding_period (장기/중기/단기) + 환각 가드 3 중 (WA·WF·WL·WE cited + chart_data_md 출처 + anchor 출처 명시). 결정론 함수 = 백테스팅 친화 (cutoff_date 인자 + 과거 OHLCV 시뮬레이션 가능)."
---

# WAVE-ALPHA-001 — 프랙탈 파동 α (anchor + 공식 + verdict 분기)

## 목적

`stock_analyst.verdict` 가 cycle 11 (2026-05-21) production 검증 후에도 `inconclusive` 에 머물러 있는 **잔여 차단점 1 개 = α 미산출** 을 해소한다. cycle 13 (`INFRA-SNAPSHOT-EXTEND-001` 풀세트, 2026-05-22) 으로 market_state_analyzer / stock_picker / flow_analyzer 3 분석가 본격 판정은 활성화되어 MS3 차단점 풀세트 실증 해소 ✨ 되었으나, **stock_analyst 만 α=null 잔존** = Track A (중장기) 권고 풀세트 (verdict=confirmed_high_quality / target_prices 3 단 / holding_period) 미발행 = MS4 (실 매매 시연) 베이스라인 부재.

본 SPEC = **사용자 고유 파동분석 영역 (프랙탈 + 로그 함수 해석, 박종훈 강의 X) 의 정식 인프라화**. 핵심 4 결단:

1. **anchor A·B·C 정의** (1차 발산 시작 / 정점 / 되돌림 저점=2차 발산 시작) + current (현재가, 2차 추세 진행도 검증)
2. **3 timeframe 동시 산출** (daily 트레이딩 / weekly 복리투자법 / monthly 시대적 황제주) + 입력 의도 (long: / swing:) 가중
3. **2-Stage 하이브리드 anchor 산출** (결정론 candidate + LLM 직관 선택 + 3 단 캐싱 + manual override)
4. **시간 정규화 공식** (k₁=ln(B/A)/days(A→B), k₂=ln(current/C)/days(C→current), α=k₂/k₁) + sweet spot 5 단계 label

Phase 1 완료 = stock_analyst verdict=confirmed_high_quality / confirmed_low_quality 정식 발행 + target_prices 3 단 산출 SLOT 활성 + holding_period 매핑 (장기/중기/단기) + MS4 진입 베이스라인.

## 배경 / 문제

### cycle 13 직후 잔여 차단점 (2026-05-22)

`docs/c_worked/2026-05-22_infra-snapshot-extend-impl.md` "미해결 부채" + RESUME.md Top 2:

| 분석가 | cycle 13 직후 상태 | 잔여 차단 |
|---|---|---|
| `market_state_analyzer` | strong_bull · 95% ✨ | 해소 |
| `stock_picker` | 시나리오 분포 활성 ✨ | 해소 |
| `flow_analyzer` | KOSPI 60일 수치 풀세트 ✨ | 해소 |
| **`stock_analyst`** | **α=null + verdict=inconclusive 고정** | **본 SPEC scope** |
| `wealth_strategist` | 거시 framework 인용 정상 | 해소 |
| `principle_guardian` | C·D·R·OS 21 명제 검증 정상 | 해소 |
| `trader` | T-Score + 6 트리거 정상 | 해소 |
| `trading_journalist` | Layer 4 의존 (별도 SPEC) | 별도 |
| `news_curator` | NEWS-SOURCE-001 의존 (별도 SPEC) | 별도 |

본 SPEC scope = **stock_analyst α 발행 풀세트 + verdict 분기 매트릭스 + holding_period 매핑**. target_prices 3 단 산출 룰은 SLOT S1 분리 (verdict=confirmed_high_quality 진입 후 별도 SPEC).

### 사용자 framework 본질 (라운드 1 결단)

본 α framework 는 **사용자 고유 파동분석 영역** 이다. 박종훈 강의 인용 X. 사용자가 "프랙탈 + 로그 함수 해석은 나의 고유 파동분석 영역" 으로 정정 (라운드 1 Q1-a). canon `knowledge/canon/stock-analysis/fractal_wave/` 채움은 사용자 자가 정리로만 진행 (W5+ 풀세트 = SLOT S4 분리 후속 SPEC).

### 백테스팅 본질 (라운드 1 Q1-d 발견)

사용자가 라운드 1 에서 강조한 본질 = **본 SPEC 의 α 함수가 백테스팅 친화** 여야 한다. 미래 성과 시뮬레이션 전에 과거 데이터로 verdict 분기 + 성과 검증 가능 = 사용자의 framework 진화 + 시스템 발전의 핵심 동력. 본 SPEC 의 결정론 함수 + 캐싱 + cutoff_date 인자 = 백테스팅 친화 설계. 백테스팅 본체는 SLOT S3 분리 (`WAVE-ALPHA-BACKTEST-001` 가칭).

## 핵심 정의

### § 1. anchor A·B·C + current

```
가격 (로그 스케일)
                                 *  ← current (현재가)
                                /
                               /
                              /
            B *──────┐       /
              /\      \     /
             /  \      \   /
            /    \      C*/   ← 2차 발산 시작 = 1차 되돌림 저점
           /      \    /
          /        \  /
         /          \/
        /
       /
      A *                       ← 1차 발산 시작 = 장기 바닥
      ↑ 1차 발산 (k₁)
                       ↑ 2차 발산 (k₂)
```

- **A** = **1차 발산 시작점** — 장기 횡보·바닥 후 첫 상승 추세 진입 직전 저점 (date, price)
- **B** = **1차 발산 정점** — 첫 추세의 최고가, 본격 되돌림 직전 (date, price)
- **C** = **1차 되돌림 저점 = 2차 발산 시작점** — 두 번째 상승 추세 진입 직전 (date, price)
- **current** = 현재가 (date, price) — 2차 추세가 얼마나 진행됐는지 외삽 검증용

### § 2. α 공식 (시간 정규화 기울기 비율)

```python
k1 = ln(B.price / A.price) / (B.date - A.date).days
k2 = ln(current.price / C.price) / (current.date - C.date).days
alpha = k2 / k1
```

- **k₁** = 1차 발산 일별 로그 변화율
- **k₂** = 2차 발산 일별 로그 변화율
- **α** = k₂ / k₁ — 무차원, α=1.0 = 두 발산 같은 속도
- 시간 차이 반영 = 1차 5년 / 2차 1년 같은 케이스에서 본질 (속도 비교) 정확

### § 3. 5 단계 label (sweet spot 임계 + timeframe 별 차등)

```python
THRESHOLDS = {
    'daily':   {'low': 0.5, 'sweet_lo': 1.0, 'sweet_hi': 4.0},
    'weekly':  {'low': 0.7, 'sweet_lo': 1.0, 'sweet_hi': 3.0},
    'monthly': {'low': 0.8, 'sweet_lo': 1.0, 'sweet_hi': 2.5},
}

def interpret_alpha(alpha: float, timeframe: str) -> str:
    t = THRESHOLDS[timeframe]
    if alpha is None or math.isnan(alpha):
        return None  # 엣지 케이스
    if alpha <= 0: return 'trend_broken'
    if alpha < t['low']: return 'weak'
    if alpha < t['sweet_lo']: return 'modest'
    if alpha < t['sweet_hi']: return 'sweet'
    return 'overheated'
```

- **trend_broken** (α≤0): 2차 발산이 하락 진행, 추세 단절
- **weak**: 2차가 1차 대비 매우 약함 (회피 zone)
- **modest** (0.5/0.7/0.8 ≤ α < 1.0): 2차 약화, inconclusive zone
- **sweet** (1.0 ≤ α < 2.5/3.0/4.0): 진입 sweet spot ★
- **overheated** (α ≥ 2.5/3.0/4.0): 과열, 진입 늦음 위험

### § 4. 부수 메타데이터 2 개 (current 외삽 검증)

```python
progress_to_b = current.price / B.price
# 1차 정점 대비 현재가 도달 비율
# ≥ 1.0 = B 돌파 (강한 신호)
# 0.7~1.0 = B 근접 (sweet spot 근접)
# < 0.7 = 잠재력 큼

duration_ratio = (current.date - C.date).days / (B.date - A.date).days
# 1차 발산 시간 대비 2차 진행 시간
# < 0.3 = 2차 너무 초기 (α 통계 약함)
# 0.3~1.0 = 진행 중
# > 1.0 = 2차가 1차보다 길게 진행 (장기 추세 가능)
```

### § 5. verdict 분기 매트릭스

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

### § 6. holding_period 매핑

verdict=confirmed_high_quality 일 때만 발행:

| 강세 timeframe (가장 긴 'sweet') | holding_period |
|---------------------------------|----------------|
| **monthly = sweet** | **장기 (6 개월 ~ 수년)** — 시대적 황제주 영역 |
| **weekly = sweet** (monthly 아님) | **중기 (3 ~ 12 개월)** — 복리 투자법 영역 |
| **daily = sweet** (weekly·monthly 아님) | **단기 (수일 ~ 수주)** — 트레이딩 영역 |

multi-timeframe sweet 시: **가장 긴 timeframe** 의 holding_period 우선.

### § 7. 엣지 케이스 7 건 (E1~E7)

| 코드 | 발생 조건 | 처리 |
|------|----------|------|
| **E1** | `days(A→B) < min_gap` (timeframe 별) | α = None, reason="anchor_too_close" |
| **E2** | `\|k₁\| < epsilon` (1e-6) — 1차 발산 평탄 | α = None, reason="k1_flat" |
| **E3** | current ≤ C — 2차 하락 진행 | α 계산 가능 (음수/0), label='trend_broken' |
| **E4** | `len(ohlcv) < min_bars` (timeframe 별) | α = None, reason="insufficient_history" |
| **E5** | 상장 < 1년 (신생 종목) | daily 만 산출, weekly/monthly = None, reason="ticker_too_young" |
| **E6** | LLM Stage 2 실패 (API 오류 / JSON parse 실패) | 결정론 fallback (가장 최근 valid candidate 시퀀스) + reason="llm_fallback_to_deterministic" |
| **E7** | 캐시 cutoff 변경 | 자동 무효화 (정상 처리) |

### § 8. timeframe 별 데이터 요구 + min_gap

```python
TIMEFRAME_LIMITS = {
    'daily':   {'min_gap_days': 5,   'min_bars': 250,  'max_history_years': 3},
    'weekly':  {'min_gap_days': 35,  'min_bars': 156,  'max_history_years': 5},
    'monthly': {'min_gap_days': 180, 'min_bars': 60,   'max_history_years': 15},
}
```

- daily: A→B 최소 5 영업일, 1년 history (250 봉)
- weekly: A→B 최소 5 주, 3년 history (156 봉)
- monthly: A→B 최소 6 개월, 5년 history (60 봉)

INFRA-CHART-DATA-001 v2 의 chart_ohlcv 적재 깊이 = 종목별 일봉 1년 → **5~10년 확장** 필요. weekly/monthly 는 일봉 resample 로 산출.

### § 9. anchor 산출 2-Stage 하이브리드

**Stage 1 (결정론 candidate)**:

```python
candidates = extract_swing_candidates(
    ohlcv,
    timeframe='weekly',
    n_periods=156,
    pct_threshold=0.15,
    min_gap_bars=TIMEFRAME_LIMITS[timeframe]['min_gap_days'] // 5,
)
# returns: [(date, price, type='high'|'low'), ...]  5~10 개
```

- percentile + 시간순 시퀀스 + min_gap 필터링
- 100% 결정론, ms 단위, 비용 0
- 모든 종목 일관

**Stage 2 (LLM 직관 선택)**:

```python
# Haiku 4.5 + temperature 0.0 + JSON 강제
prompt = f"""
다음은 {ticker} {timeframe} 차트의 swing 점 candidate {N} 개입니다:
[1] 2022-10-25 51,800 low
[2] 2023-01-15 65,200 high
...

이 candidate 중에서 본 종목의 1차 발산 시작 (A),
1차 정점 (B), 1차 되돌림 저점 = 2차 발산 시작 (C)
3 점을 골라주세요. JSON 으로 인덱스만 출력.
"""
# 응답: {"A_idx": 1, "B_idx": 4, "C_idx": 5, "reasoning": "..."}
```

- 인간 직관 stat. 분포 활용 (사용자 본질 직관 그대로 — "여러 사람 생각 취합한 표준 분포")
- 선택지가 candidate 5~10 개로 제한 → 결정론 흔들림 작음
- temperature 0.0 + JSON 강제 = 노이즈 차단

**3 단 캐싱**:

```python
cache_key = f"{ticker}|{timeframe}|{cutoff_date_or_period}"
# daily: cutoff = 일자 (예: 2026-05-22) — 일 1회만 LLM 호출
# weekly: cutoff = ISO 주 (예: 2026-W21) — 주 1회만
# monthly: cutoff = 월 (예: 2026-05) — 월 1회만
```

- llm_call_cache 테이블 활용 (기존)
- 캐시 hit 률 90%+ → LLM 호출 ~10%
- Haiku 4.5 호출당 ~$0.001 → 100 종목 × 3 timeframe × 10% hit ratio = $0.03/일

**manual override (DB)**:

```sql
CREATE TABLE manual_anchors (
    ticker TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    anchor_a_date TEXT NOT NULL,
    anchor_a_price REAL NOT NULL,
    anchor_b_date TEXT NOT NULL,
    anchor_b_price REAL NOT NULL,
    anchor_c_date TEXT NOT NULL,
    anchor_c_price REAL NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ticker, timeframe)
);
```

- 우선순위: manual_anchors 우선 → Stage 1+2 fallback
- 황제주 후보군 ~10 종목 (NVIDIA · SK하이닉스 · 삼성전자 · 미국 지수 등) 만 manual 박음
- 사용자 본인 직관 신뢰 시 자유

### § 10. StandardOutput data § 풀세트

```json
{
  "team_id": "stock_analyst",
  "verdict": "confirmed_high_quality",
  "confidence": 92,
  "data": {
    "alpha_daily":   {"value": 1.42, "label": "modest", "anchors": {...}, "progress_to_b": 0.89, "duration_ratio": 0.55, "reason": null, "source": "llm_stage2"},
    "alpha_weekly":  {"value": 1.62, "label": "sweet", "anchors": {...}, "progress_to_b": 0.94, "duration_ratio": 0.62, "reason": null, "source": "llm_stage2"},
    "alpha_monthly": {"value": null, "label": null, "reason": "ticker_too_young", "source": null},
    "verdict_reasoning": {
      "input_intent": "long",
      "weekly_label": "sweet",
      "monthly_label": null,
      "matrix_match": "weekly=sweet, monthly=None → confirmed_high_quality (weekly 단독 강세)"
    },
    "holding_period": "중기 (3~12 개월)",
    "target_prices": null,
    "target_prices_reason": "SLOT_S1_separated"
  },
  "cited": ["WA1", "WA2", "WA3", "WF1", "WF2", "WF3", "WL1", "WL2", "WL3", "WE5"],
  "contract_version": "wave-alpha-v1"
}
```

### § 11. 환각 가드 3 중 (persona 정정 영역)

| 가드 | 현재 (cycle 12 이전) | WAVE-ALPHA-001 정정 |
|------|---------------------|---------------------|
| **가드 1** | "stock-analysis canon md=0 → cited=[] + principles 풀어쓰기" | **WA·WF·WL·WE 21 명제 cited 강제** (canon `01-anchor-and-alpha-formula.md` 추가됨) |
| **가드 2** | chart_data_md `[4]` 블록 출처 명시 | 유지 |
| **가드 3 (신설)** | (없음) | **anchor 출처 명시 강제**: `data.alpha_*.source` 가 manual/llm_stage2/deterministic_fallback 중 어느 것 메타 인용 강제 |

## 라운드 결단 14 건 (영구 권위)

### 라운드 1 — 본질 5 건

| ID | 결단 |
|----|------|
| **R1-1** | anchor A·B·C 정의 = 후보 ① (1차 발산 시작 / 정점 / 되돌림 저점). 사용자 **고유 파동분석 영역** (박종훈 X) |
| **R1-2** | 3 timeframe (daily/weekly/monthly) 동시 산출. 월봉 황제주 알림 cron 은 SLOT S2 분리 (`WAVE-ALPHA-WATCH-001` 가칭) |
| **R1-3** | anchor 산출 = 2-Stage 하이브리드 (결정론 candidate + LLM 직관 + 3 단 캐싱 + manual override) |
| **R1-4** | 부재 시 불편 = verdict=inconclusive 막힘 + **백테스팅 본질** (SLOT S3 분리 `WAVE-ALPHA-BACKTEST-001` 가칭). 본 SPEC alpha() 는 cutoff_date 인자 + 결정론 = 백테스팅 친화 설계 |
| **R1-5** | 출력 surface = Layer 2 발행만 + webapp 자연어 포맷 가이드 부록. webapp 자연어 변환은 Top 1 production UX SPEC 본체 |

### 라운드 2 — 공식 + 외삽 4 건

| ID | 결단 |
|----|------|
| **R2-1** | 정식 공식 = 시간 정규화 기울기 비율: `k₁=ln(B/A)/days(A→B), k₂=ln(current/C)/days(C→current), α=k₂/k₁` |
| **R2-2** | 5 단계 label (trend_broken / weak / modest / sweet / overheated) + timeframe 별 차등 임계 테이블 (THRESHOLDS dict) |
| **R2-3** | current 외삽 검증 메타데이터 2 개 (progress_to_b + duration_ratio) 자동 발행 |
| **R2-4** | 엣지 케이스 7 건 (E1~E7) + TIMEFRAME_LIMITS 권고 테이블 |

### 라운드 3 — canon 2 건

| ID | 결단 |
|----|------|
| **R3-1** | 명제 ID 체계 = **WA/WF/WL/WE** (영역별 prefix). principle_guardian 의 C·D·R·OS 21 명제 패턴과 정합 |
| **R3-2** | canon 범위 = 본 SPEC 은 WA·WF·WL·WE 21 명제 1 장 (`01-anchor-and-alpha-formula.md`) 만. 풀세트 canon (W5+ 사용자 자가 정리 + 양질도 10 점) = SLOT S4 분리 (`WAVE-ALPHA-CANON-001` 가칭) |

### 라운드 4 — persona § 3 건

| ID | 결단 |
|----|------|
| **R4-1** | verdict 분기 매트릭스 = long: (weekly+monthly 우선) / swing: (daily 우선) / 중립 (보수적 OR). 3 매트릭스 명시 |
| **R4-2** | holding_period 매핑 = monthly sweet → 장기 / weekly sweet → 중기 / daily sweet → 단기. multi-timeframe sweet 시 가장 긴 timeframe 우선 |
| **R4-3** | persona § 정정 = 가드 2 중 → **3 중** (가드 1 갱신 + 가드 2 유지 + 가드 3 신설 anchor 출처). α 산출 § / verdict § 전면 재작성. target_prices 산출 룰은 SLOT S1 분리 |

### 라운드 5 — 테스트/SLOT/구현 3 건

| ID | 결단 |
|----|------|
| **R5-1** | 테스트 풀세트 ~60 케이스 (정량 UT 56 + 통합 5). 회귀 안전 두꺼움. 422 → ~480 |
| **R5-2** | SLOT 6 건 (S1 target_prices / S2 watch 알림 / S3 backtest / S4 canon-full / S5 anchor fine-tune / S6 LLM prompt 튜닝) |
| **R5-3** | 구현 순서 = sub-cycle 분할 14.1/14.2/14.3 (cycle 13 패턴 재현). 중간 점검 + risk 분산 |

## SLOT (미확정 후속, 본 SPEC 외)

| ID | 항목 | 후속 SPEC 가칭 | 분리 이유 |
|----|------|---------------|----------|
| **S1** | target_prices 3 단 산출 룰 | `WAVE-ALPHA-TARGETS-001` 또는 기존 SPEC 확장 | verdict=confirmed_high_quality 시 발행 — 룰 별도 |
| **S2** | 월봉 황제주 watchlist + 알림 cron | `WAVE-ALPHA-WATCH-001` | 다른 surface (cron + telegram + watchlist DB) |
| **S3** | 백테스팅 본체 (과거 시점 시뮬레이션 → 성과 평가) | `WAVE-ALPHA-BACKTEST-001` | 사용자 라운드 1 강조 본질, 별 차원 작업. 본 SPEC alpha() 는 cutoff_date 인자로 친화 설계 |
| **S4** | 풀세트 canon W5+ 자료 + 양질도 10 점 | `WAVE-ALPHA-CANON-001` | 사용자 직관 정리 + chat Claude Opus 핑퐁 워크플로우 |
| **S5** | anchor 자동 candidate 알고리즘 fine-tuning | 운영 6 개월 후 회고 SPEC | 운영 데이터 필요 |
| **S6** | LLM Stage 2 prompt 튜닝 + Sonnet 4.6 업그레이드 검토 | 운영 3 개월 후 | 운영 데이터 필요 |

## 구현 순서 (다음 사이클 14, sub-cycle 분할)

### Sub-cycle 14.1 — canon + DB + scoring (commit 1)

1. **canon W 명제 21 건 Write**: `knowledge/canon/stock-analysis/fractal_wave/01-anchor-and-alpha-formula.md` 신규. WA1~WA5 + WF1~WF4 + WL1~WL4 + WE1~WE7 = 20 + 부록 1 = 21 명제. 라운드 1~4 결단 그대로 마크다운 변환
2. **DB v8 마이그레이션**: `core/db/migrations/v8_wave_alpha.sql` 신규. manual_anchors 테이블 (ticker, timeframe, A·B·C 날짜+가격 6 컬럼) + llm_call_cache 에 type='anchor_selection' 추가. schema_version 8 INSERT
3. **`collectors/scoring.py` alpha() 정식 + label() + interpret_alpha()**: 현 placeholder 시그니처 `alpha(anchor_a, anchor_b, anchor_c, current) -> float` → 신 시그니처 `alpha(anchor_a: tuple[date, float], anchor_b: tuple[date, float], anchor_c: tuple[date, float], current: tuple[date, float]) -> float`. THRESHOLDS dict + interpret_alpha() 신규 + progress_to_b + duration_ratio helper

### Sub-cycle 14.2 — anchors + 통합 (commit 2)

4. **`collectors/anchors.py` 신규**: extract_swing_candidates() (Stage 1 결정론) + select_anchors_via_llm() (Stage 2 LLM) + 3 단 캐싱 룰 (cache_key 정의) + manual override (DB SELECT) + E6 fallback (가장 최근 valid candidate 시퀀스)
5. **α 3 timeframe 통합**: `core/inference/run_analyst.py` 의 stock_analyst 호출 직전 hook 또는 `collectors/snapshot.py` 의 종목별 호출 직전. data.alpha_daily/weekly/monthly + verdict_reasoning + holding_period 자동 주입

### Sub-cycle 14.3 — persona + manifest + 테스트 + smoke + wrap-up (commit 3)

6. **`agents/analysts/stock_analyst/persona.md` § 정정**: § 4 (α 산출) 전면 재작성 = R2~R4 결단 인용 / § 5 (verdict) 매트릭스 추가 / § 6 (holding_period) 매핑 추가 / § 7 (환각 가드) 2 중 → 3 중. v3 → v4 버전 bump
7. **`agents/analysts/stock_analyst/manifest.yaml` reads 갱신**: `reads: [stock_analysis, fractal_wave]` (현 `stock_analysis` 단일 → `fractal_wave` 추가)
8. **테스트 ~60 케이스**:
   - `tests/test_alpha.py` 신규 — 정상 + 시간 정규화 + E1~E5 + 경계값 (~25 케이스)
   - `tests/test_anchors.py` 신규 — Stage 1 candidate + Stage 2 LLM mock + 3 단 캐싱 + E6 fallback + manual override (~30 케이스)
   - `tests/test_data_analysts_v2.py` 확장 — stock_analyst 통합 (~5 케이스)
9. **smoke test**: 삼성전자 (005930) + NVIDIA (NVDA) + KOSPI 지수 (0001) 으로 α 3 timeframe 산출 + verdict 발행 + holding_period 매핑 검증. DB manual_anchors 1 종목 박아 override 검증
10. **wrap-up commit + push**: `docs+spec: WAVE-ALPHA-001 implemented + sub-cycle 14.1/14.2/14.3 (cycle 14)`. `docs/c_worked/2026-05-2?_wave-alpha-impl.md` + RESUME.md 갱신

## 부록 A — webapp 자연어 포맷 가이드 (Top 1 production UX SPEC 이 활용)

본 SPEC 의 StandardOutput data § 풀세트를 webapp 채팅창 자연어로 변환할 때 사용 가능한 사전:

| 코드 | 자연어 변환 (예시) |
|------|-------------------|
| `alpha_weekly.label='sweet'` | "주봉 기준 2차 발산이 1차보다 강하게 진행 중" |
| `alpha_monthly.label='sweet'` | "월봉 기준 시대적 추세 강화 신호" |
| `alpha_daily.label='overheated'` | "단기로는 과열, 진입 늦었을 가능성" |
| `progress_to_b > 0.9` | "1차 정점 돌파 직전" |
| `duration_ratio < 0.3` | "2차 추세 초기 단계 (통계 약함)" |
| `holding_period='장기'` | "6 개월 이상 보유 권장 — 시대적 황제주 영역" |
| `holding_period='중기'` | "3~12 개월 보유 권장 — 복리 투자법 영역" |
| `verdict='confirmed_high_quality'` | "진입 가능한 종목으로 판단됨" |
| `data.alpha_*.source='manual'` | "사용자가 직접 박은 anchor 기준" |

좋은 답변 예시 (production UX SPEC 본체에서 구현):
> 삼성전자, 진입 가능합니다. 주봉 기준 2차 발산이 1차보다 60% 강하게 진행 중이고, 1차 정점 돌파 직전입니다. 3~12개월 보유 권장. 외인 수급도 5일 연속 순매수입니다.

피해야 할 답변 (코드 라벨 노출):
> 삼성전자 α_weekly=1.62, verdict=confirmed_high_quality, target_prices=[72000,80000,88000]

## 부록 B — depends_on 의존 상세

### INFRA-CHART-DATA-001 v2 (chart_ohlcv 깊이 확장)

현재 chart_ohlcv 종목별 일봉 적재 깊이 = 1년 (250 봉). 본 SPEC 의 monthly α (`min_bars=60, max_history_years=15`) + weekly α (`min_bars=156, max_history_years=5`) 요구 충족하려면 **종목별 일봉 5~10년** 필요. KIS API `inquire-daily-itemchartprice` 의 페이징 호출 2~3 회로 확보 가능. INFRA-CHART-DATA-001 v3 마이크로 정정 또는 본 SPEC sub-cycle 14.1 에서 동시 처리 결정.

### ANALYST-PERSONAS-001 v2 (stock_analyst v3 → v4)

본 SPEC sub-cycle 14.3 단계 6 = `persona.md` § 4·5·6·7 전면 재작성 + version v3 → v4. ANALYST-PERSONAS-001 의 v 버전 bump 패턴 그대로.

### INFRA-SNAPSHOT-EXTEND-001 v1 (chart_ohlcv + metadata 패턴 재사용)

cycle 13 의 chart_ohlcv 적재 패턴 + run_analyst.py metadata 4 키 패턴 (`snapshot_age_seconds` / `fetch_seconds` / `cache_hit` / `failures`) 그대로 재사용. 본 SPEC 의 α metadata 도 동일 4 키 + alpha_* 3 키 확장.

## 확정 ✨ (2026-05-22 cycle 14 SPEC frozen)

본 SPEC = 5 라운드 면담 결단 14 건 영구 권위. 다음 사이클 14 = sub-cycle 14.1 → 14.2 → 14.3 분할 구현 풀세트. 본 SPEC frozen 후 cycle 14 구현 시 본 § 들이 변경 불가 권위로 작동 (라운드 결단 14 건이 SPEC § 본문에 1:1 박힘).
