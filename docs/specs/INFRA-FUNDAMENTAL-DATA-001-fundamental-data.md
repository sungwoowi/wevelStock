---
spec_id: INFRA-FUNDAMENTAL-DATA-001
title: 분기 실적·EPS·매출 추세 fundamental 데이터 인프라 — yfinance Default 8 필드 + DB cache + 주 1회 cron
team: shared
type: feature
status: implemented
version: 2
owner: platform
generates:
  - collectors/fundamentals.py
  - connectors/yfinance/__init__.py
  - connectors/yfinance/client.py
  - core/db/migrations/v6_fundamentals.sql
  - server/schedulers/jobs/fundamentals.py
  - tests/test_fundamentals.py
  - tests/test_fundamentals_db.py
  - tests/test_compose_fundamental_data_md.py
  - tests/test_run_analyst_fundamental_injection.py
  - tests/test_stock_analyst_v4_persona.py
modifies:
  - core/db/schema.sql
  - core/knowledge/compose.py
  - core/inference/run_analyst.py
  - agents/analysts/stock_analyst/persona.md
  - agents/analysts/stock_analyst/manifest.yaml
  - server/schedulers/jobs/__init__.py
  - justfile
  - pyproject.toml
depends_on:
  - INFRA-CHART-DATA-001 v2 (compose.build_pipeline_prompt 의 [4] 차트 직후 [5] fundamental 블록 직렬 추가)
  - ANALYST-PERSONAS-001 v2 (stock_analyst persona v4 정정 트레이스 3 위치 — chart v3 패턴 미러)
contracts:
  - name: fundamental-data-md-v1
    version: "1.0"
    description: "compose.build_pipeline_prompt 의 [5] 펀더멘털 데이터 블록 markdown 표 형식 (분기 4 분기 매출·영업이익·EPS QoQ·YoY + 5 ratio TTM)"
---

# INFRA-FUNDAMENTAL-DATA-001 — 분기 실적 fundamental 데이터 인프라

## 목적

`stock_analyst` 분석가의 **F5 (실적 모멘텀) + F2 (펀더멘털 양호도)** 발행이 분기 실적 데이터 부재로 막혀 있다. cycle 6 의 INFRA-CHART-DATA-001 풀세트 구현으로 α·F1·F4 활성화 + MS3 부분 도달 달성했으나 **F5·F2 만 잔존 unknown** = MS3 완전 도달 차단. 본 SPEC = **yfinance Default 8 필드 + DB-first 24h TTL + 주 1회 cron + `compose.build_pipeline_prompt` 의 `[5] 펀더멘털 데이터` 블록 자동 주입 + stock_analyst persona v4 마이크로 정정 3 위치**. Phase 1 완료 시 stock_analyst F5·F2 unknown 가드 동시 해제 = **MS3 완전 도달**.

## 배경 / 문제

### cycle 6 진단 (2026-05-20 INFRA-CHART-DATA-001 구현 풀세트 직후)

`agents/analysts/stock_analyst/persona.md` v3 작성 시점, fundamental 데이터 인프라 미진입으로 다음 가드 박음:

1. **§ Reasoning Doctrine F1~F5 정의 표** (persona.md:227-235)
   - F2 (펀더멘털 양호도) = "INFRA-FUNDAMENTAL-DATA-001 후속"
   - F5 (실적 모멘텀) = "분기 실적 QoQ·YoY 가속·둔화. 2 분기 연속 둔화 시 청산. INFRA-FUNDAMENTAL-DATA-001 후속"
2. **§ Outputs 격자 [1] Quality Grid F5 row unknown 강제** (persona.md:123)
3. **manifest.yaml response_rules 의 F5·F2 unknown 가드 본문** (manifest L?, 후속 grep)

본 SPEC 의 Phase 1 (yfinance Default 8 필드 활성화) 완료 = 위 3 위치 v4 마이크로 정정으로 가드 해제 = F5·F2 정상 발행 로직 활성화.

### F5·F2 산출 차단 = MS3 완전 도달 차단

`stock_analyst` 의 verdict 산출 로직: chart_data_md 있고 fundamental_data_md 부재 → verdict=`inconclusive` + confidence 50-70 (persona.md:183 "F2·F5 만 잔존 unknown 시 50-70"). MS3 = 양 트랙 (Track A 중장기 + Track B 단기) 자연 인계 완성 = stock_analyst 의 F1~F5 풀세트 활성화가 본질 차단점. F5 활성화 = MS3 완전 도달.

## 핵심 정의

| 용어 | 의미 |
|---|---|
| **yfinance** | Yahoo Finance scraping 기반 Python 라이브러리. `pip install yfinance` 만으로 사용. 미·한 종목 모두 커버 (한국 = `<ticker>.KS` for KOSPI / `.KQ` for KOSDAQ). API 키 불필요. |
| **TTM** | Trailing Twelve Months. 최근 4 분기 합산 (rolling sum). EPS·revenue 기본 단위. |
| **Default 8 필드** | 본 SPEC 즉시 활성화 = (1) EPS TTM (2) PE 현재 (3) ROE (4) operating margin (5) debt/equity (6) 분기 매출 4 분기 (7) 분기 영업이익 4 분기 (8) 분기 EPS 4 분기. |
| **SLOT 4 필드** | forward EPS / forward PE / 배당수익률 / 현금흐름. Phase 2 또는 사용자 의사결정 후 활성화. |
| **fundamental_data_md** | `core/knowledge/compose.build_pipeline_prompt` 의 새 kwarg. chart_data_md `[4]` 직후 `[5] 펀더멘털 데이터` 블록 (markdown 표 풀세트). |
| **stock_analyst v4 정정 위치 3** | (a) § Reasoning Doctrine F1~F5 정의 표 F2/F5 row / (b) § Outputs 격자 [1] Quality Grid F5/F2 unknown 강제 해제 / (c) manifest response_rules 가드 2 본문 + `reads_fundamental_data: true` 플래그. |
| **fetched_at 24h TTL** | DB cache 적재 시점 기준 24 시간 신선도. stale 시 yfinance 재호출 + DB upsert. |

## Phase 분리

### Phase 1 (본 SPEC) — yfinance Default 8 필드 활성화

- 자료 source = yfinance 단독 (Phase 1)
- 8 필드 catalog
- DB-first + 24h TTL + 주 1회 cron (일요일 18:00 KST)
- `fundamental_data_md` `[5]` 블록 + stock_analyst persona v4 정정
- Phase 1 검증 통과 = **MS3 완전 도달** (F5·F2 활성화)

### Phase 2 (별도 SPEC `INFRA-FUNDAMENTAL-CROSS-VALIDATE-001`, 후속) — DART 이중 검증

- 한국 종목 DART OpenDART API 추가 → yfinance 와 결합 (불일치 시 DART 우선)
- 미주 종목 = yfinance 단독 유지
- SLOT 4 필드 활성화 (forward EPS·forward PE·배당수익률·현금흐름)
- 분기 자동 발표 trigger (DART 공시 webhook 또는 polling) — Phase 2 의사결정

## 명세

### 1. yfinance Default 8 필드 schema

| # | 필드 | yfinance 추출 경로 | 단위 | 본 분석가 사용처 |
|---|------|---------------------|------|----------------|
| 1 | `eps_ttm` | `Ticker.info["trailingEps"]` | KRW (한국) / USD (미주) | F2 (펀더멘털) base |
| 2 | `pe_ratio` | `Ticker.info["trailingPE"]` | 배수 | F2 밸류에이션 |
| 3 | `roe` | `Ticker.info["returnOnEquity"]` | 0~1 (15% = 0.15) | F2 펀더멘털 양호 |
| 4 | `operating_margin` | `Ticker.info["operatingMargins"]` | 0~1 | F2 수익성 |
| 5 | `debt_to_equity` | `Ticker.info["debtToEquity"]` | % (100 기준) | F2 안전성 |
| 6 | `quarterly_revenue` | `Ticker.quarterly_financials.loc["Total Revenue"]` 최근 4 분기 | KRW / USD | F5 QoQ·YoY 모멘텀 |
| 7 | `quarterly_operating_income` | `Ticker.quarterly_financials.loc["Operating Income"]` 최근 4 분기 | KRW / USD | F5 영업이익 추세 |
| 8 | `quarterly_eps` | `Ticker.quarterly_earnings["EPS"]` 최근 4 분기 | KRW / USD | F5 EPS 모멘텀 |

### 2. DB schema (`core/db/migrations/v6_fundamentals.sql`)

```sql
CREATE TABLE IF NOT EXISTS fundamentals (
    ticker          TEXT NOT NULL,           -- "005930" (한국 6자리) / "AAPL" (미주)
    market          TEXT NOT NULL,           -- "KS" | "KQ" | "US"
    fetched_at      INTEGER NOT NULL,        -- unix epoch (UTC)
    eps_ttm         REAL,                    -- 5 ratio TTM
    pe_ratio        REAL,
    roe             REAL,
    operating_margin REAL,
    debt_to_equity  REAL,
    quarterly_data  TEXT NOT NULL,           -- JSON: {"revenue": [q4, q3, q2, q1], "operating_income": [...], "eps": [...], "quarter_labels": ["2025Q4", ...]}
    source          TEXT NOT NULL DEFAULT 'yfinance',
    PRIMARY KEY (ticker)
);

CREATE INDEX IF NOT EXISTS idx_fundamentals_fetched_at ON fundamentals(fetched_at);
```

`schema_version` 5 → 6 갱신 + `core/db/schema.sql` 의 풀스키마 add.

### 3. fundamental_data_md `[5]` 블록 (`fundamental-data-md-v1` 계약)

`compose.build_pipeline_prompt(fundamental_data_md=)` kwarg 신설. chart_data_md `[4]` 블록 직후 + RAG 직전 자동 주입. stock_analyst manifest `reads_fundamental_data: true` 시만 주입.

#### 형식 (markdown)

```
## [5] 펀더멘털 데이터 (INFRA-FUNDAMENTAL-DATA-001)

### 종목 메타
- 종목명: 삼성전자 (005930.KS)
- 자료 source: yfinance (fetched 2026-05-20T18:00:00Z, 6h ago)
- 분기 라벨: 2026Q1 (최신) / 2025Q4 / 2025Q3 / 2025Q2

### TTM 5 ratio (F2 입력)
| 지표 | 값 | 본 분석가 해석 가이드 |
|------|-----|---------------------|
| EPS TTM | 9,512 KRW | F2 base — 양수/음수 |
| PE (현재) | 12.4x | F2 밸류에이션 — 업종 평균 대비 |
| ROE | 14.2% | F2 펀더멘털 양호도 — 15%+ = 우수 |
| Operating Margin | 18.7% | F2 수익성 — 업종 비교 |
| Debt/Equity | 45.3% | F2 안전성 — 100% 미만 안전 |

### 분기 실적 4 분기 (F5 입력)
| 분기 | 매출 (조원) | 영업이익 (조원) | EPS (KRW) |
|------|-----------|---------------|----------|
| 2026Q1 | 79.8 | 6.7 | 998 |
| 2025Q4 | 75.2 | 6.4 | 935 |
| 2025Q3 | 72.5 | 5.9 | 873 |
| 2025Q2 | 67.4 | 5.2 | 781 |

### QoQ·YoY (F5 모멘텀 산출 base)
- 매출 QoQ (2026Q1 vs 2025Q4): **+6.1%** (가속)
- 매출 YoY (2026Q1 vs 2025Q1): **+18.4%** (가속)
- 영업이익 QoQ: +4.7% / YoY: +28.8%
- EPS QoQ: +6.7% / YoY: +27.8%

### 본 분석가 사용 지침
- **F5 (실적 모멘텀)**: QoQ·YoY 양쪽 양수 = 가속 / 양수+음수 혼합 = 정체 / 양쪽 음수 = 둔화. **2 분기 연속 둔화 시 청산 시그널**.
- **F2 (펀더멘털 양호도)**: 5 ratio 동시 평가. PE < 업종 평균 + ROE > 15% + Operating Margin > 10% + Debt/Equity < 100% = 양호 / 1 개라도 위반 = 경고 / 다수 위반 = 약화.
- 학습 데이터 시점 수치 인용 X — 본 블록의 fetched_at 시점 수치만 인용.
```

### 4. yfinance 통합 (`connectors/yfinance/`)

#### 모듈 구조
- `connectors/yfinance/__init__.py` — `YFinanceClient` export
- `connectors/yfinance/client.py` — `YFinanceClient` class + 핵심 메서드 3:
  - `async def fetch_info(ticker_with_market: str) -> dict`  # `Ticker.info` 의 5 ratio
  - `async def fetch_quarterly(ticker_with_market: str) -> dict`  # quarterly_financials + quarterly_earnings
  - `async def fetch_full(ticker: str, market: str) -> dict`  # 위 2 결합 + 표준 dict 반환

#### Ticker 변환 룰
- 한국 KOSPI: `005930` → `005930.KS`
- 한국 KOSDAQ: `247540` → `247540.KQ`
- 미주: `AAPL` → `AAPL` (suffix X)
- `_to_yf_ticker(ticker: str, market: str) -> str` helper

#### Rate limit + 에러 처리
- yfinance 의 내부 rate limit (분당 ~60 호출). DB-first 패턴이라 사용자 호출 burst 흡수.
- `Ticker.info` 빈 dict 반환 시 (delisted / 잘못된 ticker) → `FundamentalNotAvailable("yfinance returned empty info")` raise. caller (collectors) 가 catch + cache 적재 skip.
- network timeout 30s. 30s 초과 시 RuntimeError. yfinance 내부 timeout 조정 불가 → asyncio.wait_for wrap.

### 5. collectors/fundamentals.py

#### 핵심 함수
```python
async def get_fundamentals(
    ticker: str,
    market: str = "KS",
    *,
    force_refresh: bool = False,
) -> Fundamentals | None:
    """DB-first hybrid + 24h TTL.

    1. DB cache hit 확인 (fetched_at < 24h before now) → 그대로 반환
    2. stale 또는 force_refresh=True → yfinance 호출 → DB upsert → 반환
    3. yfinance 호출 실패 + DB stale 데이터 있음 → stale 반환 (degraded mode)
    4. yfinance 호출 실패 + DB hit X → None 반환 (caller 가 unknown 처리)
    """

async def refresh_all_tickers(*, tickers: list[str] | None = None) -> dict:
    """사용자 등록 종목 일괄 refresh — APScheduler cron + just refresh-fundamentals.

    tickers=None 이면 `KR_NAME_TO_TICKER` (35 종) + 사용자 추가 watchlist 자동 조회.
    각 종목 0.5s 간격 (yfinance rate limit 안전 여유).
    반환 = {"refreshed": N, "failed": [tickers], "skipped_fresh": M}
    """
```

#### `Fundamentals` dataclass
```python
@dataclass
class Fundamentals:
    ticker: str
    market: str
    fetched_at: datetime
    eps_ttm: float | None
    pe_ratio: float | None
    roe: float | None
    operating_margin: float | None
    debt_to_equity: float | None
    quarterly_revenue: list[float]    # 최근 4 분기 (recent first)
    quarterly_operating_income: list[float]
    quarterly_eps: list[float]
    quarter_labels: list[str]         # ["2026Q1", "2025Q4", "2025Q3", "2025Q2"]
    source: str                       # "yfinance" / "yfinance_stale" / future "dart"
```

#### markdown render (`render_fundamental_data_md`)
- 위 § 3 의 형식대로 표 풀세트 markdown 생성.
- QoQ·YoY 자동 계산 + 가속/둔화/정체 자동 라벨링 (text only, 본 분석가의 verdict 산출은 LLM 의 추론 영역).

### 6. compose 통합 (`core/knowledge/compose.py`)

`build_pipeline_prompt(fundamental_data_md=)` kwarg 신설:
- system 블록 구조: `[1] persona / [2] memory / [3] snapshot / [4] chart_data / [5] fundamental_data / [6] RAG / [7] response_rules`
- 본 SPEC = `[5]` 자리 정식 정의 (cycle 6 = `[4]` chart). RAG 가 `[5]` → `[6]` 으로 자동 shift.
- `cache_control` 없음 (24h TTL 갱신 빈도 낮음, system block cache 적중률 보호 위해 marker 없이 추가).

### 7. run_analyst 통합 (`core/inference/run_analyst.py`)

#### `AnalystSpec.reads_fundamental_data` 필드 신설
- manifest `reads_fundamental_data: true|false`. default = `false`. stock_analyst 만 `true`.

#### `_maybe_build_fundamental_data_md(spec, target_ticker)` 헬퍼
- 패턴 = cycle 6 의 `_maybe_build_chart_data_md` 1:1 미러.
- spec.reads_fundamental_data 가 false → None 반환 (skip)
- target_ticker 미주어짐 → None + metadata `fundamental_failures=['no_target_ticker']`
- resolve_ticker (cycle 6.5 의 KR_NAME_TO_TICKER 35종) 통과 → `get_fundamentals(ticker, market)` 호출
- 결과 unknown → `fundamental_failures=['no_fundamental_data']`
- 정상 → `render_fundamental_data_md(...)` 반환

#### run_analyst metadata 신규 7 키
- `fundamental_source` (db / yfinance / stale_cache / unknown)
- `fundamental_fetched_at` (datetime)
- `fundamental_age_seconds`
- `fundamental_failures` (list)
- `fundamental_quarter_count` (4 or less)
- `fundamental_ratios_count` (5 or less, 누락 가능)
- `fundamental_ticker_used` (resolved ticker)

### 8. APScheduler cron (`server/schedulers/jobs/fundamentals.py`)

- cron expression: `0 18 * * 0` (일요일 18:00 KST)
- 작업 = `refresh_all_tickers()` 호출. 모든 사용자 watchlist 종목 fundamental fetch + DB upsert.
- 35 종목 × 0.5s 간격 = ~18s 소요 (인메모리 lock 안 잡음, 다른 cron 과 무관).
- 실패 시 server log `fundamental_refresh_failed` + 다음 주 재시도 (idempotent — fetched_at 24h TTL 안에 있으면 skip).
- `register_infra_jobs` 등록.

### 9. justfile 레시피
```
refresh-fundamentals:
    uv run python -m collectors.fundamentals refresh

fetch-fundamental ticker market="KS":
    uv run python -m collectors.fundamentals fetch {{ticker}} --market {{market}}
```

### 10. 에러 처리 — 3-tier fallback

#### Tier 1: yfinance API 호출 실패 (네트워크 / scraping 차단)
- DB stale cache (24h+ 지난 데이터) 가 있으면 그대로 반환 + metadata `fundamental_source="stale_cache"`
- 없으면 None 반환 + `fundamental_failures=["yfinance_unavailable"]`

#### Tier 2: yfinance 응답 일부 필드 누락 (예: ROE = None, debt/equity = None)
- 누락 필드만 None + 나머지 그대로. metadata `fundamental_ratios_count` 에 정상 카운트.
- render 시 누락 필드 = "N/A" 표기. LLM 이 가용 ratio 만으로 F2 판정.

#### Tier 3: quarterly_financials 빈 DataFrame (신규 상장 / 데이터 없음)
- `quarterly_revenue=[]` 등 빈 list. render 시 "분기 데이터 없음 (신규 상장 가능)" 명시.
- F5 모멘텀 산출 불가 → stock_analyst 가 F5=unknown 발행 (가드 1 — 새 데이터 0 자각).

### 11. stock_analyst persona v4 마이크로 정정 3 위치

#### (a) § Reasoning Doctrine F1~F5 정의 표 (persona.md:227-235)
- F2 (펀더멘털) row: "INFRA-FUNDAMENTAL-DATA-001 후속" → "5 ratio TTM (EPS·PE·ROE·operating margin·debt/equity) 동시 평가. PE < 업종 평균 + ROE > 15% + Op.Margin > 10% + Debt/Eq < 100% = 양호 / 1 개 위반 = 경고 / 다수 위반 = 약화"
- F5 (실적 모멘텀) row: "INFRA-FUNDAMENTAL-DATA-001 후속" → "분기 매출·영업이익·EPS QoQ·YoY 가속·둔화. **2 분기 연속 둔화 시 청산 시그널**"

#### (b) § Outputs 격자 [1] Quality Grid (persona.md:123)
- F5 row 의 `unknown` 강제 제거 → 정상 분기 (`<가속·둔화·정체·unknown>` — chart_data_md 정합)
- F2 row 의 unknown 강제 제거 → 정상 분기 (`<양호·경고·약화·unknown>`)
- "v3 단계 = α·F1·F4 = chart_data_md [4] 주입 시 활성, F2·F5 = INFRA-FUNDAMENTAL-DATA-001 후속까지 unknown" → "v4 단계 = α·F1~F5 풀세트 = chart_data_md + fundamental_data_md 둘 다 주입 시 활성"

#### (c) manifest.yaml response_rules + reads_fundamental_data
- `reads_fundamental_data: true` 플래그 신설
- response_rules 가드 2 (F5·F2 unknown 강제) 제거 + 정상 발행 로직 명시

### 12. 테스트 케이스 (5 신규 파일)

| 파일 | 케이스 |
|------|-------|
| `tests/test_fundamentals.py` | get_fundamentals DB hit / 24h stale 재호출 / yfinance 실패 + stale fallback / force_refresh / None 반환 (5 케이스) |
| `tests/test_fundamentals_db.py` | v6 마이그레이션 / fundamentals 테이블 upsert / quarterly_data JSON round-trip (3 케이스) |
| `tests/test_compose_fundamental_data_md.py` | fundamental_data_md=None skip / 정상 주입 [5] 블록 / 차트 + 펀더멘털 동시 주입 시 [4]→[5] 순서 (3 케이스) |
| `tests/test_run_analyst_fundamental_injection.py` | reads_fundamental_data=true 시 자동 주입 / false 시 skip / target_ticker 미주어짐 시 failures / resolve_ticker 통과 후 fetch (4 케이스) |
| `tests/test_stock_analyst_v4_persona.py` | persona v4 의 F5·F2 unknown 가드 해제 검증 / 격자 [1] Quality Grid 갱신 검증 / manifest reads_fundamental_data:true 검증 / canon_categories 정합 (4~5 케이스) |

총 ~18~20 케이스. pytest 395 → ~413+ passed 예상.

## non-goals (7 종)

1. **DART OpenDART 통합** — Phase 2 별도 SPEC (`INFRA-FUNDAMENTAL-CROSS-VALIDATE-001`).
2. **미주 종목 (US) 본격 지원** — yfinance 가 자동 처리하나 본 SPEC 검증 범위는 한국 (KOSPI/KOSDAQ) 만. 미주 분석은 사용자 등록 시 자연 활성.
3. **forward EPS / forward PE / 배당수익률 / 현금흐름** (SLOT 4 필드) — Phase 2.
4. **연결재무제표 vs 별도재무제표 구분** — yfinance default = 연결. 본 SPEC 명시 분기 X.
5. **분기 발표 webhook / push** — 본 SPEC = polling (주 1회 cron). webhook 은 별도 SPEC.
6. **stock_picker / wealth_strategist 등 다른 분석가 read** — 본 SPEC = stock_analyst 단독 read. 다른 분석가 활용은 별도 SPEC.
7. **재무비율 정의 차이 (yfinance vs DART)** — Phase 2 cross-validate 시 마저 정리. Phase 1 = yfinance 정의 그대로.

## SLOT (5) — 본 SPEC 미확정 후속 시점

<!-- SPEC:INTERVIEW-SLOT -->

| # | SLOT | 결단 시점 |
|---|------|----------|
| **S1** | F2 양호도 임계값 정밀 (PE 업종 평균 / ROE 15% / Op.Margin 10% / Debt/Eq 100%) 정량화 | Phase 1 production 검증 시 사용자 운용 데이터 기반 |
| **S2** | F5 "2 분기 연속 둔화" 임계 정의 (QoQ -5% 이상? 절대값?) | Phase 1 운용 + 회고분석가 PROPOSAL |
| **S3** | yfinance scraping 차단 시 backup (Investing.com / 네이버금융 scraping 등) | Phase 2 또는 발생 시 |
| **S4** | forward EPS·PE 통합 (yfinance `forwardEps` / `forwardPE`) | Phase 2 사용자 결단 |
| **S5** | 배당수익률 + 배당 이력 (Track A 의 자산복리 관점) | wealth_strategist 가 read 결정 시 |

## 영향 SPEC

1. **ANALYST-PERSONAS-001 v2** — stock_analyst manifest `reads_fundamental_data: true` + persona v4 3 위치 정정. v2 매핑 표는 그대로 (canon_categories 추가 없음, 본 인프라는 별도 데이터 source).
2. **INFRA-CHART-DATA-001 v2** — `compose.build_pipeline_prompt` 의 system 블록 번호 = chart `[4]` 직후 fundamental `[5]` → RAG 블록 번호 자동 shift. 본 SPEC 가 직접 갱신.
3. **GUIDANCE-ACCURACY-TRACKER-001 (백로그)** — F5 활성화 후 stock_analyst verdict 의 적중률 추적 시 fundamental 인용 정합성 검증 가능. 별도 SPEC 후속.

## 구현 순서 (15 단계, 별도 사이클)

본 사이클 = SPEC frozen 만. 실제 구현은 다음 사이클 cycle 10 (예상 ~2 세션):

1. `pyproject.toml` 에 `yfinance>=0.2.0` 추가
2. `core/db/migrations/v6_fundamentals.sql` 신규 + `core/db/schema.sql` schema_version 5→6 갱신
3. `connectors/yfinance/__init__.py` + `connectors/yfinance/client.py` 신규 (YFinanceClient)
4. `collectors/fundamentals.py` 신규 (Fundamentals dataclass + get_fundamentals + refresh_all_tickers + render_fundamental_data_md)
5. `tests/test_fundamentals.py` 신규 (5 케이스)
6. `tests/test_fundamentals_db.py` 신규 (3 케이스)
7. `core/knowledge/compose.py` 의 `build_pipeline_prompt(fundamental_data_md=)` kwarg 추가 + `[5]` 블록 + RAG shift
8. `tests/test_compose_fundamental_data_md.py` 신규 (3 케이스)
9. `core/inference/run_analyst.py` 의 `AnalystSpec.reads_fundamental_data` + `_maybe_build_fundamental_data_md` 헬퍼 + run_analyst 양쪽 통합 + metadata 7 키
10. `tests/test_run_analyst_fundamental_injection.py` 신규 (4 케이스)
11. `agents/analysts/stock_analyst/persona.md` v4 마이크로 정정 3 위치
12. `agents/analysts/stock_analyst/manifest.yaml` `reads_fundamental_data: true` + response_rules 가드 2 정리
13. `tests/test_stock_analyst_v4_persona.py` 신규 (4~5 케이스)
14. `server/schedulers/jobs/fundamentals.py` + `register_infra_jobs` 등록 + `justfile` 2 레시피
15. **Production smoke**: `ask_analyst stock_analyst "삼성전자 분석" --provider claude_code --target 005930` → `[5]` 블록 LLM read 확인 + F5·F2 정상 발행 + verdict = inconclusive 해제 → **MS3 완전 도달 ✨**

## 본 사이클 (cycle 9) — SPEC only

본 사이클 산출물:
- `docs/specs/INFRA-FUNDAMENTAL-DATA-001-fundamental-data.md` 신설 (본 파일)
- `scripts/validate.py` frontmatter 통과 검증
- `docs/c_worked/2026-05-20_infra-fundamental-data-spec.md` 신규 (wrap-up)
- `docs/RESUME.md` Top 3 갱신 (Top 1 = INFRA-FUNDAMENTAL-DATA-001 구현 cycle 10 / Top 2·3 재배치)
- `docs/SESSIONS.md` 행 추가

코드 변경 0. 다음 사이클 cycle 10 = 본 SPEC 의 15 단계 구현 풀세트.
