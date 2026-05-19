---
spec_id: INFRA-CHART-DATA-001
title: 차트 데이터 인프라 — KIS daily OHLCV + on-demand snapshot + Default 6 지표
team: shared
type: feature
status: implemented
version: 2
owner: platform
generates:
  - collectors/charts.py
  - core/db/migrations/v5_chart_ohlcv.sql
  - server/schedulers/jobs/charts.py
  - tests/test_charts.py
  - tests/test_charts_indicators.py
  - tests/test_chart_ohlcv_db.py
  - tests/test_compose_chart_data_md.py
  - tests/test_run_analyst_chart_injection.py
  - tests/test_stock_analyst_v3_persona.py
modifies:
  - connectors/kis/client.py
  - core/db/schema.sql
  - core/knowledge/compose.py
  - core/inference/run_analyst.py
  - agents/analysts/stock_analyst/persona.md
  - agents/analysts/stock_analyst/manifest.yaml
  - server/schedulers/jobs/__init__.py
  - justfile
depends_on:
  - INFRA-RUNTIME-EFFICIENCY-001 v2 (server mode reuse 패턴 미러)
  - ANALYST-PERSONAS-001 v2 (stock_analyst persona v3 정정 트레이스 3 위치)
contracts:
  - name: chart-data-md-v1
    version: "1.0"
    description: "compose.build_pipeline_prompt 의 [4] 차트 데이터 블록 markdown 표 형식"
---

> **v2 (2026-05-20 cycle 6 구현 완료)**: Phase 1 (텍스트 지표) 풀세트 구현 완료. KIS `inquire-daily-itemchartprice` 페이징 fetch + on-demand snapshot 7 필드 + Default 6 지표 (pandas 기본 rolling/ewm — pandas-ta 미사용, numpy 호환성 위험 회피) + `chart_data_md` `[4]` 블록 자동 주입 + stock_analyst v3 마이크로 정정 3 위치 (환각 가드 2 해제, chart_data_md 출처 명시 강제) + 평일 18:00 KST APScheduler cron + `just refresh-charts` 수동 백업. pytest 341 → 376 passed (회귀 0). production 호출 시 stock_analyst manifest 의 `reads_chart_data: true` + `target_ticker` 명시 시 chart 블록 자동 주입.

# INFRA-CHART-DATA-001 — 차트 데이터 인프라

## 목적

`stock_analyst` 분석가의 α·F1·F4·F5·목표가 3 단 결정론 산출이 차트 데이터 부재로 막혀 있다. 본 SPEC = **KIS API 기반 daily OHLCV historical + on-demand snapshot + pandas-ta 지표 6 default 카탈로그 + `compose.build_pipeline_prompt` 의 `[4] 차트 데이터` 블록 자동 주입**. Phase 1 완료 시 stock_analyst 환각 가드 2 (INFRA 미구현) 해제 = **MS3 부분 도달** (F5 분기 실적만 잔존, `INFRA-FUNDAMENTAL-DATA-001` 후속).

## 배경 / 문제

### cycle 3 진단 (2026-05-19 자료 있는 3 분석가 v2 작업 직후)

`agents/analysts/stock_analyst/persona.md` v2 작성 시점, 차트 데이터 인프라 미진입으로 다음 가드 2 박음:

1. **§ Anti-patterns 가드 2: INFRA-CHART-DATA-001 미구현 → 차트 추론 환각 차단** (persona.md:289-307)
   - 차트 데이터 부재 시 `verdict=unknown` 강제 + `cited:[]` + reasons "INFRA-CHART-DATA-001 미구현, α·목표가 3 단·F1~F5 결정론 산출 불가"
   - LLM 학습 데이터 시점의 차트 패턴 ("20 일선 정배열" / "MACD 골든크로스" / "이중 천장" / "헤드 앤 숄더") 인용 금지

2. **§ Outputs 격자 [1] Quality Grid 의 α·F1 unknown 강제** (persona.md:117-118, 135, 223, 241)
   - α (가속계수, scoring.alpha 결정론) = `unknown` + reasons "INFRA-CHART-DATA-001 (미비 시 unknown)"
   - F1 (장기 추세 — 월봉/주봉 추세 유효성) = `unknown`
   - 목표가 3 단 = `[null, null, null]` + reasons "anchor 산출 불가"

3. **manifest.yaml response_rules 가드 2 본문** (manifest.yaml:84-91, 117, 133, 143)
   - `infra_blocker = "INFRA-CHART-DATA-001 미구현"` 명시

본 SPEC 의 Phase 1 (텍스트 지표 활성화) 완료 = 위 3 위치 v3 마이크로 정정으로 가드 해제 = α·F1·목표가 3 단 정상 발행 로직 활성화.

### α 산출 차단 = MS3 도달 차단

`stock_analyst` 의 α 산출 알고리즘 자체가 차트 데이터의 anchor A·B·C 수치를 결정론으로 분기 (persona.md:66). INFRA 부재 = α 함수 입력 부재 = MS3 (양 트랙 자연 인계 완성) 차단점.

## 핵심 정의

| 용어 | 의미 |
|---|---|
| **historical OHLCV** | KIS `inquire-daily-itemchartprice` API 의 5 년 1825 봉 daily 데이터. pandas resample 로 주봉·월봉 인메모리 변환. |
| **on-demand snapshot** | KIS `inquire-price` API 의 현재 시점 단발 시세 6 필드. 60s TTL 인메모리 캐시. continuous streaming push 와 구분. |
| **수정주가** | 권리락·증자·액면분할 조정 반영. KIS API 의 `org_adj_prc` 토글, 본 SPEC default = 수정주가 (α anchor 정합 보장). |
| **Default 6 지표** | 본 SPEC 즉시 활성화 = 월봉 7·20MA + 주봉 10·20·60MA + 일봉 4·7·20·60·120MA + MACD (12-26-9) + 거래량 20일 이평 spike + 52주 고저. |
| **SLOT 2 지표** | RSI (14) + 볼린저 밴드 (20, 2σ). WAVE-ALPHA-001 α 공식 결단 후 활성화. |
| **chart_data_md** | `core/knowledge/compose.build_pipeline_prompt` 의 새 kwarg. RAG 블록 직후 `[4] 차트 데이터` 블록 (markdown 표 풀세트). |
| **stock_analyst 환각 가드 2 해제 위치 3** | (a) § Anti-patterns 가드 2 / (b) § Outputs 격자 [1] Quality Grid 차트 추론 / (c) manifest response_rules. |

## Phase 분리

### Phase 1 (본 SPEC) — 텍스트 지표 활성화

- KIS daily OHLCV + on-demand snapshot fetch
- pandas-ta 지표 6 default 계산
- markdown 표 형식 `chart_data_md` 생성 → `[4]` 블록 주입
- stock_analyst 환각 가드 2 해제 (v3 마이크로 정정)
- **MS3 부분 도달** (F5 분기 실적만 잔존)

### Phase 2 (별도 SPEC `INFRA-CHART-VISION-001`, 후속) — vision 활성화

- matplotlib png 렌더
- vision API 통합 (provider 호환성 검증: gemini / claude / openai vision)
- LLM 이 차트 이미지 시각 패턴 직접 read

본 SPEC = **Phase 1 만**. Phase 2 진입 의사결정은 Phase 1 production 안정화 + vision provider 비교 후.

## 명세

### 1. historical OHLCV schema + 기간 범위

| 항목 | 정의 |
|---|---|
| 기간 | KIS daily 1825 봉 (5 년) 1 회 fetch → 인메모리 pandas resample 로 주봉·월봉 자동 변환 |
| 수정주가 | KIS API `org_adj_prc=Y` (default), 권리락·증자·액면분할 조정 반영 |
| 컬럼 | **8 컬럼**: `date` / `open` / `high` / `low` / `close` / `volume` / `change_rate` / `value` (거래대금) |

```python
# collectors/charts.py 시그니처 (예시)
def get_daily_ohlcv(
    ticker: str,
    *,
    period_days: int = 1825,
    adjust: bool = True,
) -> pd.DataFrame:
    """5 년 daily OHLCV. DB cache hit → KIS fetch → DB persist. lru_cache 인메모리."""
    ...
```

리턴 = `pd.DataFrame` (인덱스 = `date`, 컬럼 = 위 8).

### 2. on-demand snapshot schema

KIS `inquire-price` 응답 기반 **7 필드**:

| 필드 | 의미 |
|---|---|
| `current_price` | 현재가 |
| `open_price` | 시가 (당일) |
| `high_price` | 일중 고가 |
| `low_price` | 일중 저가 |
| `change_rate` | 일중 등락률 (vs 전일종가) |
| `volume_today` | 일중 누적 거래량 |
| `value_today` | 일중 누적 거래대금 |

```python
def get_current_snapshot(ticker: str) -> dict:
    """현재 시점 snapshot 7 필드. 60s TTL 인메모리 캐시."""
    ...
```

호가창 (매수/매도 5호가) **미포함** — 별도 API (`inquire-asking-price-exp-ccn`) 필요, 후속 SPEC `INFRA-INTRADAY-DATA-001` (trader 분봉 트리거와 묶음).

### 3. pandas-ta 지표 카탈로그

#### Default 6 (본 SPEC 즉시 활성화)

| # | 지표 | 산출 frame | stock_analyst 정합 |
|---|---|---|---|
| 1 | 월봉 7MA / 20MA | resample('M') | F1 장기 추세선 (월봉 정배열·이탈 판정) |
| 2 | 주봉 10MA / 20MA / 60MA | resample('W') | F2 중기 추세 |
| 3 | 일봉 4MA / 7MA / 20MA / 60MA / 120MA | daily 그대로 | F3 단기 트레일 + 정배열 판정 |
| 4 | MACD (12-26-9) | daily (옵션 weekly) | persona L58. 일봉/주봉 추세 전환 |
| 5 | 거래량 20일 이평 + spike 비율 | daily | persona L58 "거래량 패턴". trader volume_surge 공유 잠재 |
| 6 | 52주 고저 | daily | F1 추세 + buy_score 모멘텀 정합 |

```python
def compute_indicators(ohlcv: pd.DataFrame) -> dict:
    """Default 6 지표 dict. resample 자동. NaN 케이스 부분 발행 허용."""
    return {
        "monthly_ma_7": ...,
        "monthly_ma_20": ...,
        "weekly_ma_10": ...,
        # ... (Default 6 전부)
    }
```

#### SLOT 2 (본 SPEC 미활성, 후속)

| SLOT | 지표 | 활성화 시점 |
|---|---|---|
| S2-a | RSI (14) | WAVE-ALPHA-001 α 공식 결단 후 |
| S2-b | 볼린저 밴드 (20, 2σ) | WAVE-ALPHA-001 직후 |

#### 미포함 (사용 빈도 낮음, non-goal)

OBV / ATR / 스토캐스틱 / Ichimoku 등.

### 4. 분석가 LLM 주입 방식 (`chart_data_md` kwarg)

`core/knowledge/compose.build_pipeline_prompt` 에 새 kwarg `chart_data_md=None` 추가. RAG 블록 (`[3]`) 직후 `[4] 차트 데이터` 블록 신설. `market_snapshot_md` (`[3]` 블록, 2026-05-08 단계 2) 패턴 미러.

```python
# core/knowledge/compose.py 시그니처 변경
def build_pipeline_prompt(
    *,
    persona_md: str,
    canon_md: str,
    market_snapshot_md: str = "",
    chart_data_md: str = "",   # <-- 신규
    rag_chunks: list[Chunk] = (),
    rag_dept: str | None = None,
    canon_categories: list[str] | None = None,
) -> str:
    """
    System prompt 블록 순서:
      [1] persona_md
      [2] canon_md
      [3] market_snapshot_md
      [4] chart_data_md  (신규)
      [5] rag_chunks
    """
```

#### `chart_data_md` 형식 (chart-data-md-v1 계약)

markdown 표 풀세트 (5-Layer 분석가 공용 raw 베이스 미러):

```markdown
## [4] 차트 데이터 (INFRA-CHART-DATA-001)

**Ticker**: 005930 (삼성전자) | **As of**: 2026-05-20 14:30 KST | **수정주가 기준**

### 현재 시점 snapshot
| 필드 | 값 |
|---|---|
| current_price | 82,000 |
| open_price | 80,500 |
| high_price | 82,300 |
| low_price | 80,200 |
| change_rate | +1.86% |
| volume_today | 15,234,567 |
| value_today | 1,248,123,456,000 (1.25조) |

### 월봉 추세
| 지표 | 값 | 현재가 대비 |
|---|---|---|
| 월봉 7MA | 78,500 | +4.46% |
| 월봉 20MA | 72,300 | +13.4% |

### 주봉 추세
| 지표 | 값 | 현재가 대비 |
|---|---|---|
| 주봉 10MA | 80,100 | +2.37% |
| 주봉 20MA | 77,800 | +5.40% |
| 주봉 60MA | 71,200 | +15.2% |

### 일봉 추세
| 지표 | 값 | 현재가 대비 |
|---|---|---|
| 일봉 4MA | 81,200 | +0.99% |
| 일봉 7MA | 80,500 | +1.86% |
| 일봉 20MA | 78,300 | +4.72% |
| 일봉 60MA | 73,100 | +12.2% |
| 일봉 120MA | 68,800 | +19.2% |

### MACD (12-26-9, daily)
| 컴포넌트 | 값 |
|---|---|
| MACD | 1,234 |
| Signal | 980 |
| Histogram | +254 (양선 확장) |

### 거래량 패턴
| 지표 | 값 |
|---|---|
| 20일 이평 거래량 | 12,500,000 |
| 오늘 거래량 / 20일 이평 | 1.22× (spike +22%) |

### 52주 고저
| 지표 | 값 | 현재가 위치 |
|---|---|---|
| 52주 고가 | 85,400 (2026-04-12) | -3.98% |
| 52주 저가 | 65,200 (2025-08-30) | +25.8% |

(부분 발행 케이스: 데이터 부족 지표는 `null` + reasons "데이터 부족 (상장 후 N 일)")
```

#### 주입 결정 (stock_analyst 만)

`AnalystSpec` 에 `reads_chart_data: bool` 필드 신설 (default `False`). stock_analyst manifest 만 `True`.

`run_analyst.py` 가 분석가 호출 시:
1. `analyst_spec.reads_chart_data == True` AND target ticker 추출 가능 → `get_daily_ohlcv(ticker)` + `get_current_snapshot(ticker)` + `compute_indicators` + `render_chart_data_md` → `build_pipeline_prompt(chart_data_md=...)`.
2. 나머지 (False / ticker 부재) → `chart_data_md=""` 미주입.

토큰 비용: chart_data_md ≈ 2~3K tokens. Sonnet 200K 한계 vs 기존 RAG (18K canon + 9K snapshot) + chart (3K) = 30K. 여유 충분.

### 5. 캐시 메커니즘 + DB schema

#### `chart_ohlcv` 테이블 (신규, `core/db/schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS chart_ohlcv (
    ticker         TEXT NOT NULL,
    date           TEXT NOT NULL,  -- YYYY-MM-DD
    open           REAL NOT NULL,
    high           REAL NOT NULL,
    low            REAL NOT NULL,
    close          REAL NOT NULL,
    volume         INTEGER NOT NULL,
    change_rate    REAL NOT NULL,  -- 등락률 (%)
    value          INTEGER NOT NULL,  -- 거래대금 (원)
    adjusted       INTEGER NOT NULL DEFAULT 1,  -- 수정주가 여부 (1=adj, 0=원주가)
    fetched_at     TEXT NOT NULL,  -- ISO8601 적재 시각
    PRIMARY KEY (ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_chart_ohlcv_ticker_date
    ON chart_ohlcv (ticker, date DESC);
CREATE INDEX IF NOT EXISTS idx_chart_ohlcv_fetched
    ON chart_ohlcv (fetched_at DESC);
```

`schema_version` **4 → 5** bump. migration 파일 = `core/db/migrations/v5_chart_ohlcv.sql`.

#### 캐시 정책

| 데이터 | 정책 |
|---|---|
| historical OHLCV (1825 봉) | DB 적재 `chart_ohlcv` (ON CONFLICT REPLACE 멱등) + 인메모리 `lru_cache(ticker)` (server 안에서 share). daily refresh cron 18:00 KST 평일. |
| on-demand snapshot | 인메모리 TTL **60s** (5 분 압도). `(ticker, fetched_at)` 키. server 안 lru_cache share. |

**server mode reuse 정합**: `INFRA-RUNTIME-EFFICIENCY-001 v2 Phase 2 (a)` 패턴 미러 — server 안 lru_cache 가 같은 process 내 공유. CLI 호출 시 httpx wrap (`POST /api/analysts/{id}/chat`) 으로 server 경유 시 캐시 hit.

### 6. KIS API 통합 (기존 `connectors/kis/client.py` 재사용)

신규 모듈 만들지 X. 기존 `connectors/kis/client.py` 에 두 메서드 추가:

```python
# connectors/kis/client.py 신규 메서드
async def get_daily_chart(
    self,
    ticker: str,
    *,
    period_days: int = 1825,
    adjust: bool = True,
) -> list[dict]:
    """inquire-daily-itemchartprice 호출. 5 년 daily 1825 봉."""
    ...

async def get_current_price(self, ticker: str) -> dict:
    """inquire-price 호출. 현재 시점 7 필드."""
    ...
```

기존 토큰 자동 갱신 + 100ms rate limit + 분당 20 req 한도 + 인증 헤더 그대로 활용. 본 SPEC 신규 호출 빈도:
- daily fetch = 1 회/일 (cron) + 신규 ticker ad-hoc 시 1 회
- snapshot = 60s TTL 압도, 실 호출 매우 적음

### 7. daily refresh cron + 수동 task

#### APScheduler in-server (server/main.py lifespan)

기존 `market_briefing_now` cron 미러:

```python
# server/main.py lifespan
scheduler.add_job(
    func=refresh_chart_ohlcv,
    trigger="cron",
    day_of_week="mon-fri",
    hour=18,
    minute=0,
    timezone="Asia/Seoul",
    id="chart_ohlcv_refresh",
    replace_existing=True,
)
```

`refresh_chart_ohlcv()` = `chart_ohlcv` 테이블에 적재된 distinct ticker 목록 → 각각 `get_daily_chart()` 호출 → DB upsert. **watchlist 별도 SPEC (Layer 4 계좌관리자, M5) 진입 후 확장**. 초기 = 사용자 ad-hoc 호출로 DB 적재된 ticker 만 자동 refresh.

#### 수동 백업 (justfile)

```just
# justfile 신규 task
refresh-charts:
    uv run python -m collectors.charts refresh
```

cron 미발동 시 백업 + 디버깅용. `collectors/charts.py` 의 `__main__` 진입점 (argparse `refresh`).

### 8. 에러 처리 — 3-tier fallback

#### Tier 1: KIS API fetch 실패 (네트워크 / 503 / 인증 만료)

- DB last cache 사용 + log warning `chart_ohlcv_fetch_failed_using_cache(ticker, last_fetched_at, stale_hours)`
- stale 허용 **5 영업일** (`stale_hours <= 120h` 주말 포함). 초과 시 → `verdict=unknown` + reasons "INFRA-CHART-DATA-001: stale > 5 영업일"
- DB cache 부재 (신규 ticker 첫 호출 + fetch 실패) → `verdict=unknown` + reasons "ticker 첫 호출, cache 없음"

#### Tier 2: pandas-ta 지표 계산 실패 (NaN / 데이터 부족 / 신규 상장)

- **부분 발행 허용**: 계산 실패 지표만 `null` + reasons 명시. 나머지 지표는 정상 발행
- 예: 상장 1 개월 종목 → 일봉 4·7MA·20MA OK / 월봉 7·20MA·60MA·120MA·52주 고저 = `null` + reasons "데이터 부족 (상장 후 N 일)"

#### Tier 3: snapshot 60s TTL + API 실패

- fallback = last 60s cache 사용 + log warning. 다음 호출 시 재시도

#### yfinance backup 미포함

본 SPEC non-goal. 별도 SPEC `INFRA-FALLBACK-DATA-001` 후속 (미장 SPEC 진입 시 함께 검토). 사유: KIS 안정성 5 영업일 stale 허용으로 충분 + yahoo 국장 데이터 품질·갱신 KIS 대비 열위.

## non-goals (8 종)

| # | 배제 | 후속 SPEC |
|---|---|---|
| 1 | 분봉 / 틱봉 | `INFRA-INTRADAY-DATA-001` (trader v3 정정 시점) |
| 2 | 미장 (KIS 국장만) | `INFRA-US-CHART-DATA-001` (미장 진입 시) |
| 3 | 옵션 / 선물 차트 (KOSPI200 선물 수급은 별도 collector 이미 있음) | — |
| 4 | chart drawing UI (TradingView 류) | — |
| 5 | continuous streaming push (websocket realtime tick) | `INFRA-REALTIME-STREAM-001` |
| 6 | 재무 / 실적 데이터 (분기 매출·EPS·ROE·F5 trigger) | `INFRA-FUNDAMENTAL-DATA-001` |
| 7 | 5 주체 수급 (외인·기관·금융투자·연기금·개인) | 이미 `collectors/kr_supply_demand.py` |
| 8 | 테마 / 섹터 분류 데이터 | 별도 데이터원 SPEC |

## SLOT (7) — 본 SPEC 미확정 후속 시점

<!-- SPEC:INTERVIEW-SLOT -->

| SLOT | 미확정 사항 | 후속 시점 |
|---|---|---|
| **S1** | α anchor A·B·C 공식 (Module A 결정론) | WAVE-ALPHA-001 SPEC 또는 stock_analyst v3 정정 시점 |
| **S2** | RSI (14) / 볼린저 밴드 (20, 2σ) 활성화 | WAVE-ALPHA-001 α 공식 결단 후 default 카탈로그 정합 |
| **S3** | watchlist (cron batch ticker 목록) | Layer 4 계좌관리자 SPEC (M5) 진입 시 |
| **S4** | yfinance fallback (국장 + 미장 backup) | `INFRA-FALLBACK-DATA-001` (미장 SPEC 진입 시) |
| **S5** | 호가창 (매수/매도 5호가) | `INFRA-INTRADAY-DATA-001` (trader 분봉 트리거와 묶음) |
| **S6** | 분기 실적 데이터 (F5 trigger 활성화) | `INFRA-FUNDAMENTAL-DATA-001` |
| **S7** | Phase 2 vision (matplotlib + LLM vision API) | `INFRA-CHART-VISION-001` (Phase 1 production 안정화 후) |

## 다른 SPEC 영향 (4)

| SPEC | 영향 | 수정 필요 |
|---|---|---|
| `INFRA-RUNTIME-EFFICIENCY-001 v2` | server 안 lru_cache 패턴 미러 | X (패턴 차용만) |
| `ANALYST-PERSONAS-001 v2` | stock_analyst persona v3 정정 (3 위치) | **persona.md + manifest.yaml 정정 본 SPEC modifies 에 포함** |
| `STRATEGY-TRACK-001` | Track A 의 stock_analyst α·F1 read → MS3 도달 후 자연 인계 활성화 | X (인계 룰 이미 박힘) |
| `GUIDANCE-ACCURACY-TRACKER-001` | 권고 발행 시 `target_prices` 3 단 정상 적재 가능 | X (계약 이미 박힘) |

**DB 스키마 변경**: `schema_version` 4 → 5 (`chart_ohlcv` 테이블 추가).

## 구현 순서 (15 단계)

### 본 SPEC Phase 1 코드 진입 순서 (다음 세션)

1. **DB 마이그레이션** — `core/db/schema.sql` 에 `chart_ohlcv` 테이블 추가 + `schema_version` 4 → 5 bump + `core/db/migrations/v5_chart_ohlcv.sql`
2. **KIS client 메서드 추가** — `connectors/kis/client.py` 의 `get_daily_chart(ticker, period_days=1825, adjust=True)` + `get_current_price(ticker)`
3. **`collectors/charts.py` 신규** — `get_daily_ohlcv` (DB cache → KIS → DB persist) + `get_current_snapshot` (60s TTL) + `compute_indicators` (pandas-ta 6 default) + `render_chart_data_md` (markdown 표) + `__main__` (refresh 진입점)
4. **테스트 묶음 A** — `tests/test_charts.py` (~12) + `tests/test_charts_indicators.py` (~6) + `tests/test_chart_ohlcv_db.py` (~3) = **~21 케이스**
5. **`core/knowledge/compose.py` 수정** — `build_pipeline_prompt(..., chart_data_md=None)` kwarg 추가 + RAG 직후 `[4]` 블록 신설
6. **테스트** — `tests/test_compose_chart_data_md.py` (~4)
7. **`core/inference/run_analyst.py` 수정** — `AnalystSpec.reads_chart_data: bool` 필드 + stock_analyst 호출 시 target ticker 자동 인식 → fetch + 주입
8. **테스트** — `tests/test_run_analyst_chart_injection.py` (~3)
9. **`agents/analysts/stock_analyst/persona.md` v3 정정** — 환각 가드 2 의 3 위치 정정 (§ Anti-patterns 가드 2 / § Outputs 격자 [1] Quality Grid 의 α·F1 unknown 강제 해제 / v3 미래 정정 메타-가이드 트레이스 제거)
10. **`agents/analysts/stock_analyst/manifest.yaml` 정정** — `reads_chart_data: true` + response_rules 정정 + `infra_blocker` 키 제거
11. **테스트** — `tests/test_stock_analyst_v3_persona.py` (~5)

### 운영 단계 (12-15)

12. **`server/main.py` lifespan** — APScheduler `0 18 * * 1-5` cron 등록 (`refresh_chart_ohlcv`)
13. **`justfile`** — `refresh-charts` task 신규
14. **production 첫 검증** — `just ask stock_analyst "삼성전자 분석"` → `[4]` 블록 LLM read 확인 + α / F1 / 목표가 3 단 정상 발행 + `verdict ≠ unknown` + F5 만 잔존 unknown
15. **`scripts/validate.py` 통과** — SPEC frontmatter `generates` 경로 정합 + 회귀 0

## 테스트 전략

### 안전 규칙 (CLAUDE.md 준수)

- **실 KIS API 호출 절대 금지**. `tests/conftest.py` 에 KIS mock fixture 추가 (기존 mock 패턴 미러)
- pytest 실행 시 `TESTING=1` env 명시 (`.claude/hooks/pytest_safety.ps1` PreToolUse hook 차단)
- PowerShell: `$env:TESTING='1'; pytest ...` / POSIX: `TESTING=1 pytest ...`

### 6 묶음 ~33 신규 케이스

| # | 파일 | 케이스 | 핵심 검증 |
|---|---|:---:|---|
| 1 | `tests/test_charts.py` | ~12 | OHLCV 8 컬럼 / 수정주가 토글 / resample 주봉·월봉 / 6 default 지표 dispatch / 부분 발행 (상장 1 개월) / 60s TTL hit (mock 호출 카운터) / 5 영업일 stale + cache 사용 / 6 영업일 stale → unknown |
| 2 | `tests/test_charts_indicators.py` | ~6 | 6 default 지표 계산 정확성 (알려진 OHLCV fixture 결정론) — 월봉 7·20MA / 주봉 10·20·60MA / 일봉 4·7·20·60·120MA / MACD 12-26-9 / 거래량 spike / 52주 고저 |
| 3 | `tests/test_compose_chart_data_md.py` | ~4 | `chart_data_md` kwarg `[4]` 블록 주입 / target ticker 부재 시 미주입 / RAG 블록 직후 위치 / market_snapshot_md 패턴 미러 정합 |
| 4 | `tests/test_run_analyst_chart_injection.py` | ~3 | stock_analyst 자동 주입 (target ticker 있음) / 다른 분석가 (principle_guardian) 자동 주입 X / ticker 부재 시 미주입 |
| 5 | `tests/test_chart_ohlcv_db.py` | ~3 | ON CONFLICT REPLACE 멱등성 / `schema_version` 5 migration 적용 / refresh cron 진입 시 DB ticker 자동 적재 |
| 6 | `tests/test_stock_analyst_v3_persona.py` | ~5 | persona v3 정정 후 환각 가드 2 해제 / Anti-patterns 위치 변경 / Outputs Quality Grid 차트 추론 활성화 / manifest response_rules 정정 / 8명 boundary 매트릭스 회귀 0 |

**합계**: ~33 신규. 기존 **341 → 374 passed** 예상 (회귀 0).

### 회귀 보장 (영향 받을 기존 테스트 3)

- `tests/test_data_analysts_v2.py` (cycle 3 자료 있는 3 분석가 페르소나 자동 검증) — stock_analyst v3 정정 후 8명 boundary 통과
- `tests/test_seed_analysts_v2.py` (cycle 2 자료 0 시드 5 분석가) — 회귀 0
- `tests/test_market_snapshot.py` — chart_data_md 가 같은 `compose.build_pipeline_prompt` 진입, 인접 회귀 자각

## 완료 기준 (단계 14 production 첫 검증)

`just ask stock_analyst "삼성전자 분석"` 호출 시:

- ✅ `[4] 차트 데이터` 블록 LLM read 확인 (response metadata 의 system char 증가)
- ✅ α (가속계수, scoring.alpha 결정론) 정상 발행 (`null` 아님)
- ✅ F1 (장기 추세 — 월봉/주봉 추세 유효성) 정상 발행 (`unknown` 아님)
- ✅ 목표가 3 단 (`target_prices: [v1, v2, v3]`) 정상 발행
- ✅ `verdict` ∈ {`confirmed_high_quality`, `confirmed_low_quality`, `inconclusive`} (`unknown` 강제 해제)
- ⚠️ F5 (분기 실적) 만 잔존 `unknown` — `INFRA-FUNDAMENTAL-DATA-001` 후속

이 검증 통과 = **MS3 부분 도달**. MS3 완전 도달 = `INFRA-FUNDAMENTAL-DATA-001` 후 F5 활성화.

### 장중 호출 가시 검증 (보조)

`just ask stock_analyst "지금 삼성전자 어때?"` (14:30 호출) → snapshot 60s TTL 활용, 현재가 / 일중 등락률 / 일중 고저 read 확인.

## 변경 파일 요약

### 신규 (`generates`)

- `collectors/charts.py`
- `core/db/migrations/v5_chart_ohlcv.sql`
- `tests/test_charts.py`
- `tests/test_charts_indicators.py`
- `tests/test_chart_ohlcv_db.py`
- `tests/test_compose_chart_data_md.py`
- `tests/test_run_analyst_chart_injection.py`
- `tests/test_stock_analyst_v3_persona.py`

### 수정 (`modifies`)

- `connectors/kis/client.py` — `get_daily_chart` + `get_current_price` 메서드 추가
- `core/db/schema.sql` — `chart_ohlcv` 테이블 + `schema_version` 4 → 5
- `core/knowledge/compose.py` — `build_pipeline_prompt(..., chart_data_md=None)` + `[4]` 블록
- `core/inference/run_analyst.py` — `AnalystSpec.reads_chart_data` + chart_data 자동 fetch·주입
- `agents/analysts/stock_analyst/persona.md` — v3 마이크로 정정 (가드 2 해제, 3 위치)
- `agents/analysts/stock_analyst/manifest.yaml` — `reads_chart_data: true` + response_rules 정정
- `server/main.py` — APScheduler cron `chart_ohlcv_refresh` 등록
- `justfile` — `refresh-charts` task 신규
- `pyproject.toml` — `pandas-ta` 의존성 추가
