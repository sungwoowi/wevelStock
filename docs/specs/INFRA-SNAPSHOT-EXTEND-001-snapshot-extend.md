---
spec_id: INFRA-SNAPSHOT-EXTEND-001
title: 시장 스냅샷 확장 인프라 — A 시장매크로 + B 섹터 RS + C 5주체 수급 60일 + market-snapshot-md-v1 정식 계약
team: shared
type: feature
status: draft
version: 1
owner: platform
generates:
  - collectors/market_macro.py
  - collectors/sector_rs.py
  - collectors/supply_demand_history.py
  - core/db/migrations/v7_snapshot_extend.sql
  - server/schedulers/jobs/snapshot_macro.py
  - tests/test_market_macro.py
  - tests/test_sector_rs.py
  - tests/test_supply_demand_history.py
  - tests/test_snapshot_extend_db.py
  - tests/test_compose_market_snapshot_md_v1.py
  - tests/test_run_analyst_snapshot_extend_metadata.py
modifies:
  - collectors/snapshot.py
  - core/db/schema.sql
  - core/knowledge/compose.py
  - core/inference/run_analyst.py
  - server/schedulers/jobs/__init__.py
  - justfile
  - connectors/kis/client.py
  - connectors/krx/client.py
depends_on:
  - INFRA-CHART-DATA-001 v2 (chart_ohlcv 재사용 = 지수·섹터 ETF ticker 추가 + KIS get_daily_chart 의 지수 ticker (0001 KOSPI / 1001 KOSDAQ) 지원 확장)
  - ANALYST-PERSONAS-001 v2 (5 분석가 § Inputs unknown 가드 자연 해제 — market_state_analyzer / stock_picker / flow_analyzer 의 새 시그니처 read 가능, persona 정정은 cycle 13 구현 풀세트 시 동시)
contracts:
  - name: market-snapshot-md-v1
    version: "1.0"
    description: "compose.build_pipeline_prompt 의 [3] 블록 시장 스냅샷 markdown 표 정식 명문화 (cycle 1~2 ad-hoc 의 SPEC 그라운딩). 11 섹션 풀세트 = 기존 US 4 (지수·환율금리원자재·공포탐욕) + 기존 KR 4 (지수·5주체·선물·주도주) + 신규 3 (시장매크로 통계·섹터 RS·5주체 60일 누적)"
---

# INFRA-SNAPSHOT-EXTEND-001 — 시장 스냅샷 확장 인프라

## 목적

`market_state_analyzer` / `stock_picker` / `flow_analyzer` 3 분석가의 본격 판정이 **snapshot 데이터 부재** 로 막혀 있다. cycle 11 (2026-05-21) 자료 0 시드 5 분석가 production 검증 결과, **5 분석가 모두 unknown / insufficient_data / 점수 null 발행** → Track Selector verdict 가 항상 wait. cycle 6 (INFRA-CHART-DATA-001) + cycle 10 (INFRA-FUNDAMENTAL-DATA-001) 으로 종목 단위 인프라 (chart_ohlcv + fundamentals) 는 완비되어 MS3 완전 도달했으나 **시장 단위·섹터 단위·수급 시계열 인프라 부재** = production UX 진입 차단점. 본 SPEC = **A 시장매크로 (지수 위계·breadth·MA·Distribution Day) + B 섹터 RS + C 5주체 수급 60일** 의 3 카테고리 6 신규 필드 + 신규 DB 2 테이블 + 통합 cron 1개 + `market-snapshot-md-v1` 정식 계약 + `[3]` 블록 확장. Phase 1 완료 = market_state_analyzer / stock_picker / flow_analyzer 본격 판정 가능 = Track Selector verdict=ok 발행 가능 = production UX 답변 의미 회복.

## 배경 / 문제

### cycle 11 진단 (2026-05-21 자료 0 시드 5 분석가 production 검증)

`docs/c_worked/2026-05-21_seed-analysts-production-verification.md` 의 발견 부채 #1 = **snapshot 데이터 미주입 (최우선 부채)**. 5 분석가 모두 본격 판정 불가:

| 분석가 | 부재 데이터 | 발행 결과 |
|---|---|---|
| `market_state_analyzer` | KOSPI 36/60월선 위계 / 20일·60일 MA 기울기 / breadth (상승·하락 비율) / Distribution Day (25 거래일 윈도우) | verdict=`unknown` + confidence=0 |
| `stock_picker` | 섹터 RS / 종목 정배열 / 52주 신고가 / CAN SLIM 7축 | S-Score=null + buy_score=null |
| `flow_analyzer` | 5 주체 일별·60일 누적 net 매수액 (외인·기관·개인·금융투자·연기금) | verdict=`insufficient_data` + confidence=20 |
| `trading_journalist` | Layer 4 계좌관리자 매매 결과 (별도 SPEC) | 자가 진단 거부 |
| `news_curator` | 뉴스 자료원 (NEWS-SOURCE-001 별도 SPEC) | 자가 진단 거부 |

본 SPEC scope = **A·B·C 3 카테고리 = market_state_analyzer + stock_picker + flow_analyzer 본격 판정 활성화**. D (trading_journalist) = Layer 4 계좌관리자 의존 → 별도 SPEC. E (news_curator) = `NEWS-SOURCE-001` 별도 SPEC.

### 5 분석가 차단 = production UX 진입 차단점

Track Selector (`core/strategist/track_selector.py`) 가 양 트랙 (Track A / Track B) 권고 시 9 분석가 점수 read 의 5 분석가 점수가 null/unknown → Track Selector verdict 항상 wait. RESUME Top 1 (옛 production UX 본질 구현) 의 차단점: UX 라우팅 받은 분석가가 항상 wait/unknown 발행 시 사용자가 받는 답변이 무의미 → snapshot extend 가 UX 진입 전 우선 해소 필연.

## 핵심 정의

| 용어 | 의미 |
|---|---|
| **시장매크로 (A)** | KOSPI·KOSDAQ 지수 단위 매크로 통계. 지수 위계 (36/60월선) / 등락 추세 (20일·60일 MA 기울기) / breadth (상승·하락 종목 비율) / Distribution Day (25 거래일 윈도우 카운트). |
| **섹터 RS (B)** | 섹터 ETF 의 60일 수익률 vs KOSPI 지수 60일 수익률 의 비. 0~10 점수화. KODEX/TIGER 등 14 섹터 ETF (이미 fetch 중). |
| **5주체 수급 60일 (C)** | 외인·기관·개인·금융투자·연기금 일별 net 매수액 시계열 + 60일 누적 합산. KOSPI / KOSDAQ 각각. flow_analyzer F-Score 4축 base (테마-주체 매칭 + 60일 모멘텀 + 자금 유입 속도 + 부호 일치도). |
| **chart_ohlcv 재사용** | cycle 6 INFRA-CHART-DATA-001 의 `chart_ohlcv` 테이블에 지수 ticker (KOSPI=`0001`, KOSDAQ=`1001`) + 14 섹터 ETF ticker 추가. 종목 단위 (정배열·52주 신고가) 는 분석가가 chart_ohlcv 직접 read 위임 (snapshot 미적재). |
| **market-snapshot-md-v1** | `compose.build_pipeline_prompt` 의 `[3]` 블록 markdown 표 정식 계약. cycle 1~2 ad-hoc 구현의 SPEC 그라운딩. 11 섹션 풀세트 (기존 8 + 신규 3). |
| **briefing_parts 보조 활용** | 본 SPEC 의 정규 cron 외, 기존 `market_briefing_now` (평일 09:30/12:30/14:30) 의 정점 누적치 차분으로 intraday 자금 유입 속도 계산 가능 (flow_analyzer F-Score 0.2 가중 축). 단 retention 90일 한계. |

## Phase 분리

### Phase 1 (본 SPEC) — A 시장매크로 + B 섹터 RS + C 5주체 수급 60일

- 자료 source = KIS API (지수·섹터 ETF chart) + KRX backend (breadth) + KIS 5주체 수급 API (일별 누적)
- 6 신규 필드 (시장매크로 4 + 섹터 RS 1 + 수급 60일 1)
- 신규 DB 2 테이블 (`market_macro_snapshot` + `supply_demand_history`)
- 통합 cron 1개 (`snapshot_macro_refresh` 평일 18:00 KST)
- `market-snapshot-md-v1` 정식 계약 + `[3]` 블록 확장 (9~11 섹션 추가)
- Phase 1 검증 통과 = 3 분석가 본격 판정 활성화 = Track Selector verdict=ok 발행 가능

### Phase 2 (별도 SPEC, 후속) — D + E + 종목 단위 alignment

- **D 실 매매 데이터**: Layer 4 계좌관리자 의존 (`ACCOUNT-MANAGER-001` 가칭). trading_journalist 입력 활성화.
- **E 뉴스 자료원**: `NEWS-SOURCE-001` 가칭 (Perplexity MCP + 유튜브 요약 + 시간축 라벨링 + 학습부 DB + UX/UI). news_curator 입력 활성화.
- **종목 단위 alignment snapshot 적재**: 본 SPEC = 종목 단위 chart_ohlcv read 위임. snapshot 에 `ticker_alignment` 박는 안은 `INFRA-SNAPSHOT-TICKER-001` 가칭 별도 SPEC (호출당 ticker target 의 월·주·일 7MA 위치 미리 계산).

## 명세

### 1. A 시장매크로 4 필드 schema

| 필드 | 형식 | 산출 방식 | 분석가 사용처 |
|------|------|----------|--------------|
| `kr_index_hierarchy` | `{"KOSPI": {"ma_36m": float, "ma_60m": float, "current": float, "position": "above_both" \| "between" \| "below_both"}, "KOSDAQ": {...}}` | chart_ohlcv 의 KOSPI (`0001`) / KOSDAQ (`1001`) 월봉 36/60 평균 + 현재가 비교 | market_state_analyzer 지수 위계 축 |
| `kr_breadth` | `{"KOSPI": {"advancing": int, "declining": int, "unchanged": int, "ratio": float}, "KOSDAQ": {...}}` | KRX backend `MKD/04/0402` (상승/하락/보합 종목 카운트) | market_state_analyzer breadth 축 |
| `kr_ma_trend` | `{"KOSPI": {"ma20_slope_pct_5d": float, "ma60_slope_pct_20d": float, "trend": "uptrend" \| "sideways" \| "downtrend"}, "KOSDAQ": {...}}` | chart_ohlcv 일봉 20/60 MA 의 최근 5일·20일 기울기 % | market_state_analyzer 등락 추세 축 |
| `distribution_days` | `{"KOSPI": {"count_25d": int, "recent_days": [{"date": "...", "change_pct": float, "volume_change_pct": float}]}, "KOSDAQ": {...}}` | chart_ohlcv 25 거래일 윈도우에서 "지수 -0.2% 이상 + 거래량 전일 대비 증가" 카운트 | market_state_analyzer kill switch 발동 판정 |

### 2. B 섹터 RS 1 필드 schema

| 필드 | 형식 | 산출 방식 | 분석가 사용처 |
|------|------|----------|--------------|
| `sector_rs` | `[{"sector": "AI반도체", "etf_ticker": "390390", "rs_score": float (0~10), "return_60d": float, "kospi_return_60d": float, "rs_ratio": float}, ...]` 14 섹터 (강세·약세 모두) | chart_ohlcv 의 섹터 ETF (KODEX/TIGER 14종) 60일 수익률 / KOSPI 60일 수익률. clamp + 0~10 정규화. | stock_picker S-Score `rs` 축 + buy_score `L` (Leader) 축 |

`config/runtime.yaml` 에 14 섹터 ETF ticker list 박음 (현재 `kr_sectors.py` 의 하드코드 list 와 동일).

### 3. C 5주체 수급 60일 1 필드 schema

| 필드 | 형식 | 산출 방식 | 분석가 사용처 |
|------|------|----------|--------------|
| `kr_supply_60d` | `{"KOSPI": {"foreign_net_60d": int (백만원), "institution_net_60d": int, "individual_net_60d": int, "financial_inv_net_60d": int, "pension_net_60d": int, "agreement_score_60d": float (0~10)}, "KOSDAQ": {...}}` | `supply_demand_history` 테이블의 KOSPI/KOSDAQ 일별 5주체 net 매수액 60일 합산. agreement_score = 5 주체 부호 일치도 (5/5 = 10, 4/5 = 8, ..., 0/5 = 0) | flow_analyzer F-Score 4축 base (테마-주체 매칭 + 60일 모멘텀 + 자금 유입 속도 + 부호 일치도) |

### 4. DB schema (`core/db/migrations/v7_snapshot_extend.sql`)

```sql
-- A 시장매크로 일별 적재 (cron snapshot_macro_refresh 가 매일 18:00 KST 1 row insert)
CREATE TABLE IF NOT EXISTS market_macro_snapshot (
    date            TEXT NOT NULL,           -- "2026-05-21" (KST)
    market          TEXT NOT NULL,           -- "KOSPI" | "KOSDAQ"
    -- 지수 위계
    index_close     REAL NOT NULL,
    ma_36m          REAL,
    ma_60m          REAL,
    position        TEXT,                    -- "above_both" | "between" | "below_both"
    -- 등락 추세
    ma_20d          REAL,
    ma_60d          REAL,
    ma20_slope_pct_5d  REAL,
    ma60_slope_pct_20d REAL,
    trend           TEXT,                    -- "uptrend" | "sideways" | "downtrend"
    -- breadth
    advancing       INTEGER,
    declining       INTEGER,
    unchanged       INTEGER,
    breadth_ratio   REAL,
    -- Distribution Day (당일 발동 여부)
    is_distribution_day  INTEGER NOT NULL DEFAULT 0,
    change_pct      REAL,
    volume_change_pct REAL,
    PRIMARY KEY (date, market)
);

CREATE INDEX IF NOT EXISTS idx_macro_date ON market_macro_snapshot(date);
CREATE INDEX IF NOT EXISTS idx_macro_dd ON market_macro_snapshot(market, is_distribution_day);

-- C 5주체 수급 일별 시계열
CREATE TABLE IF NOT EXISTS supply_demand_history (
    date            TEXT NOT NULL,           -- "2026-05-21" (KST)
    market          TEXT NOT NULL,           -- "KOSPI" | "KOSDAQ"
    foreign_net     INTEGER NOT NULL,        -- 백만원 (음수 = 순매도)
    institution_net INTEGER NOT NULL,
    individual_net  INTEGER NOT NULL,
    financial_inv_net INTEGER NOT NULL,
    pension_net     INTEGER NOT NULL,
    source          TEXT NOT NULL DEFAULT 'kis',
    PRIMARY KEY (date, market)
);

CREATE INDEX IF NOT EXISTS idx_supply_history_date ON supply_demand_history(date);
```

`schema_version` 6 → 7 갱신 + `core/db/schema.sql` 풀스키마에 add.

### 5. market_snapshot_md `[3]` 블록 확장 (`market-snapshot-md-v1` 계약)

`compose.build_pipeline_prompt` 시그니처 변경 **X** (`market_snapshot_md` kwarg 기존 유지). `render_snapshot_md(snapshot)` 가 9~11 신규 섹션을 자동 누적.

#### 형식 (markdown — 9~11 신규 섹션만 발췌)

```
## 9. 시장 매크로 통계 (INFRA-SNAPSHOT-EXTEND-001)

### KOSPI
- 지수 위계: 2,673 (36월선 2,540 위 / 60월선 2,418 위) — **above_both** ✅
- 등락 추세: ma20 기울기 +1.2% (5일) / ma60 기울기 +0.8% (20일) — **uptrend**
- Breadth: 상승 552 / 하락 327 / 보합 41 = 60.1% (확장)
- Distribution Day (25 거래일): 2 회 — kill switch 안전 (4+ 시 발동)

### KOSDAQ
- 지수 위계: 782 (36월선 845 아래 / 60월선 832 아래) — **below_both** ⚠
- 등락 추세: ma20 기울기 -0.3% / ma60 기울기 -1.1% — **downtrend**
- Breadth: 상승 380 / 하락 1,124 / 보합 60 = 24.3% (축소)
- Distribution Day: 5 회 — **kill switch 발동** 🔴

## 10. 섹터 RS (60일 수익률 vs KOSPI)

| 순위 | 섹터 ETF | rs_score | 섹터 60일 | KOSPI 60일 | rs_ratio |
|------|---------|---------|----------|-----------|----------|
| 1 | KODEX AI반도체 (390390) | 9.2 | +18.4% | +3.1% | 5.93 |
| 2 | TIGER K방산&우주 | 8.7 | +15.2% | +3.1% | 4.90 |
| 3 | KODEX 방산TOP10 | 8.3 | +13.8% | +3.1% | 4.45 |
| ... | ... | ... | ... | ... | ... |
| 14 | KODEX 바이오 | 1.8 | -7.4% | +3.1% | -2.39 |

## 11. 5주체 수급 60일 누적

### KOSPI (백만원, 음수=순매도)
- 외인: **+8,420,000** (60일 매수 우세)
- 기관: -2,150,000
- 개인: -5,840,000
- 금융투자: -1,200,000
- 연기금: **+770,000**
- 부호 일치도: 5/5 부호 다양 → agreement_score 4.0

### KOSDAQ
- 외인: -1,830,000 (60일 매도)
- 기관: +420,000
- 개인: +1,840,000
- 금융투자: -180,000
- 연기금: -250,000
- agreement_score: 3.0

### 본 분석가 사용 지침
- **market_state_analyzer**: 지수 위계·등락 추세·Breadth·Distribution Day 4축 종합 → 6 단계 체제 판정 (강세장 / 약세장 / 횡보장 / 변동성 / 분배기 / 전환기). Distribution Day 4+ 시 kill switch 강제 발동.
- **stock_picker**: sector_rs Top 3 = 후보 섹터 + buy_score `L` (Leader) 축 산출. 시장 체제 (M 축) read 동시.
- **flow_analyzer**: kr_supply_60d 4축 합 (테마-주체 매칭 0.4 + 60일 모멘텀 0.3 + 자금 유입 속도 0.2 + 부호 일치도 0.1) = F-Score.
```

#### contract `market-snapshot-md-v1` 정식 명문화

- cycle 1~2 ad-hoc 구현 (`render_snapshot_md` 8 섹션) 의 SPEC 그라운딩 = v1.0 = **기존 8 섹션 + 신규 3 섹션 (9·10·11) = 11 섹션 풀세트**.
- v1.0 frozen 후 추가 섹션 (예: 종목 단위 alignment) 은 v1.1 또는 별도 contract.

### 6. collectors/market_macro.py (신규)

#### 핵심 함수
```python
@dataclass
class MarketMacro:
    date: str            # "2026-05-21" KST
    market: str          # "KOSPI" | "KOSDAQ"
    index_close: float
    ma_36m: float | None
    ma_60m: float | None
    position: str        # "above_both" | "between" | "below_both"
    ma_20d: float | None
    ma_60d: float | None
    ma20_slope_pct_5d: float | None
    ma60_slope_pct_20d: float | None
    trend: str           # "uptrend" | "sideways" | "downtrend"
    advancing: int | None
    declining: int | None
    unchanged: int | None
    breadth_ratio: float | None
    distribution_count_25d: int
    recent_distribution_days: list[dict]

async def compute_market_macro(market: str, *, force_refresh: bool = False) -> MarketMacro:
    """DB-first hybrid.
    1. market_macro_snapshot 의 today row 있으면 그대로 반환.
    2. 없으면 chart_ohlcv 의 KOSPI(0001)/KOSDAQ(1001) read + KRX backend breadth fetch + 4축 계산 → upsert.
    """

async def refresh_market_macro_all() -> dict:
    """KOSPI + KOSDAQ 양쪽 compute_market_macro 호출 + upsert. cron 진입점."""
```

### 7. collectors/sector_rs.py (신규)

#### 핵심 함수
```python
@dataclass
class SectorRS:
    sector: str          # "AI반도체"
    etf_ticker: str      # "390390"
    rs_score: float      # 0~10
    return_60d: float    # 섹터 ETF 60일 수익률
    kospi_return_60d: float
    rs_ratio: float

async def compute_sector_rs() -> list[SectorRS]:
    """14 섹터 ETF + KOSPI(0001) chart_ohlcv 의 60일 close 시계열 read → rs 계산.
    config/runtime.yaml sector_etf_tickers 14 list 활용.
    DB 저장 X — 호출 시점 chart_ohlcv read 만으로 충분 (lazy compute).
    """
```

### 8. collectors/supply_demand_history.py (신규)

#### 핵심 함수
```python
async def refresh_supply_demand_today() -> dict:
    """오늘 KST EOD 18:00 시점 KOSPI/KOSDAQ 5주체 net 매수액 fetch + upsert.
    KIS API inquire-investor-time-by-market (FHPTJ04030000, 시장 전체) 사용.
    cron 진입점.
    """

async def get_supply_60d(market: str = "KOSPI") -> dict:
    """supply_demand_history 의 최근 60 거래일 (KOSPI 또는 KOSDAQ) 5 주체 net 매수액 합산 + agreement_score 계산.
    snapshot.py 가 호출.
    """
```

### 9. snapshot.py 통합 (`collectors/snapshot.py` 수정)

#### MarketSnapshot dataclass 신규 필드 6 추가
```python
@dataclass
class MarketSnapshot:
    # 기존 필드 (cycle 1~2 ad-hoc) 그대로 유지
    fetched_at: float
    fetched_at_iso: str
    overnight: dict
    fear_greed: dict
    kr_indices: dict
    kr_supply: dict
    kr_futures_supply: dict
    kr_sectors: dict
    kr_leading: dict
    failures: list[str]
    source_map: dict
    db_run_ids: dict
    db_age_seconds: dict
    # 신규 필드 (본 SPEC) — A·B·C 각각 1 필드 (A는 4축이 dict 안에 박힘)
    market_macro: dict       # A: {"KOSPI": {...}, "KOSDAQ": {...}}
    sector_rs: list          # B: [SectorRS dict, ...] 14 섹터
    kr_supply_60d: dict      # C: {"KOSPI": {...}, "KOSDAQ": {...}}
```

#### `build_market_snapshot` 신규 fetcher 3 추가
- `compute_market_macro("KOSPI")` + `compute_market_macro("KOSDAQ")` 병렬 호출 (asyncio.gather)
- `compute_sector_rs()` lazy compute
- `get_supply_60d("KOSPI")` + `get_supply_60d("KOSDAQ")` 병렬

DB-first hybrid 패턴 1:1 미러 — `market_macro_snapshot` 의 today row 있으면 그대로 read, 없으면 compute. 5분 인메모리 캐시 + 60s TTL 동일.

#### `render_snapshot_md` 9~11 섹션 신규 누적
- 기존 1~8 섹션 그대로 유지
- 9. 시장 매크로 통계 (KOSPI / KOSDAQ 각 4축)
- 10. 섹터 RS (Top 14 표)
- 11. 5주체 수급 60일 누적 (KOSPI / KOSDAQ)
- 본 분석가 사용 지침 (3 분석가 매핑)

### 10. APScheduler cron (`server/schedulers/jobs/snapshot_macro.py`)

- cron expression: `0 18 * * 1-5` (평일 18:00 KST, 정규장 종료 후)
- 작업 = 순차 호출:
  1. `refresh_supply_demand_today()` — KIS 5주체 EOD fetch + upsert (`supply_demand_history` 1 row × 2 market = 2 row)
  2. `refresh_market_macro_all()` — KOSPI + KOSDAQ 시장매크로 4축 계산 + upsert (`market_macro_snapshot` 2 row)
- 35 회/주 × ~5s = ~3 분 소요 (인메모리 lock X)
- 실패 시 server log `snapshot_macro_refresh_failed` + 다음 평일 재시도 (idempotent — PRIMARY KEY 중복 시 ON CONFLICT REPLACE)
- `register_infra_jobs` 등록

### 11. briefing_parts 보조 활용 (intraday 흐름·breadth)

본 SPEC 의 정규 cron + DB 외, 기존 `market_briefing_now` (평일 09:30/12:30/14:30 KST) briefing_parts 의 누적치 차분으로 **intraday 자금 유입 속도** 활용 가능 (별도 collector X, snapshot.py read-only):
- `parts_store.get_recent_runs("market_briefing_now", limit=3)` → 3 시점 5주체 누적치 차분 → flow_analyzer 의 0.2 자금 유입 속도 축 정합 (옵션)
- `market_briefing_now` 의 신규 part `breadth` (KRX backend fetch) 적재 = 별도 stage 후속 (본 SPEC = market_macro_snapshot EOD 적재만, intraday breadth 는 후속)

본 SPEC 의 직접 산출 = `snapshot.kr_supply_60d` (EOD 60일 시계열). intraday 흐름·breadth 는 보조 source.

### 12. 에러 처리 — 3-tier fallback

#### Tier 1: chart_ohlcv 의 지수 ticker (0001/1001) 데이터 없음 (cycle 6 KIS get_daily_chart 가 지수 endpoint 미지원)
- `connectors/kis/client.py` 의 `get_daily_chart` 가 지수 ticker 지원하도록 확장 (`FID_COND_MRKT_DIV_CODE=U`) — 본 SPEC 의 `modifies` 항목
- KIS 지수 chart 실패 시 KRX backend `MKD/04/0402` fallback (cycle 4 KRX helper 패턴)
- 둘 다 실패 → `market_macro = None` + metadata `snapshot_extend_failures=["index_chart_unavailable"]`

#### Tier 2: KRX backend breadth fetch 실패 (네트워크·차단)
- 직전 거래일 `market_macro_snapshot` row 의 breadth read 로 fallback (stale 1일 허용)
- 직전 거래일도 없으면 `breadth=None` + metadata `snapshot_extend_failures=["breadth_unavailable"]`

#### Tier 3: KIS 5주체 수급 API 일시 실패
- `supply_demand_history` 의 직전 거래일 row 그대로 (stale 1일 허용)
- 직전 거래일 없으면 `kr_supply_60d` 의 해당 market 만 partial (다른 market 정상 발행)
- snapshot.failures 에 `"supply_60d_<market>_stale"` 라벨

### 13. run_analyst metadata 신규 키 (`core/inference/run_analyst.py` 수정)

- `snapshot_extend_failures: list[str]` (snapshot.failures 와 별개, 본 SPEC 신규 collector 실패만)
- `market_macro_source: "db" | "compute" | "stale" | "unknown"` (KOSPI/KOSDAQ 통합 우세 source)
- `sector_rs_count: int` (정상 발행 섹터 수, 정상 = 14)
- `supply_60d_age_days: int` (KOSPI 기준 supply_demand_history latest row age, 정상 ≤ 1)

### 14. 테스트 케이스 (6 신규 파일, ~25 케이스)

| 파일 | 케이스 |
|------|-------|
| `tests/test_market_macro.py` | compute_market_macro 의 DB hit / chart_ohlcv compute / position 분기 (above_both / between / below_both) / trend 분기 (uptrend / sideways / downtrend) / Distribution Day 카운트 (4+ kill switch) (5 케이스) |
| `tests/test_sector_rs.py` | 14 섹터 rs_score 정규화 / KOSPI 수익률 = 0 edge case / 섹터 ETF chart 누락 시 partial / Top 3 sorting (4 케이스) |
| `tests/test_supply_demand_history.py` | refresh_supply_demand_today upsert / 60일 누적 sum / agreement_score 계산 (5/5 = 10, 0/5 = 0) / KOSPI / KOSDAQ 분리 (4 케이스) |
| `tests/test_snapshot_extend_db.py` | v7 migration / schema_version 6→7 갱신 / market_macro_snapshot upsert / supply_demand_history upsert / PRIMARY KEY 중복 ON CONFLICT REPLACE (4 케이스) |
| `tests/test_compose_market_snapshot_md_v1.py` | render_snapshot_md 9 섹션 정합 / 10 섹션 정합 / 11 섹션 정합 / 신규 필드 None 시 graceful skip / 11 섹션 모두 정상 발행 시 통합 표시 (5 케이스) |
| `tests/test_run_analyst_snapshot_extend_metadata.py` | snapshot_extend_failures key 노출 / market_macro_source 분기 / sector_rs_count = 14 정상 / supply_60d_age_days ≤ 1 (4 케이스) |

총 ~25 케이스. pytest 385 → ~410+ passed 예상.

## non-goals (7 종)

1. **종목 단위 alignment snapshot 적재** — chart_ohlcv read 위임. 별도 SPEC `INFRA-SNAPSHOT-TICKER-001` 가칭 (호출당 target_ticker 의 월·주·일 7MA 위치 미리 계산).
2. **D 실 매매 데이터** — Layer 4 계좌관리자 의존 (`ACCOUNT-MANAGER-001` 가칭). trading_journalist 활성화는 후속.
3. **E 뉴스 자료원** — `NEWS-SOURCE-001` 별도 SPEC (Perplexity MCP + 유튜브 + 시간축 라벨링 + 학습부 DB).
4. **분봉/틱봉 intraday 매크로** — 본 SPEC = EOD 18:00 적재. 분봉 = `INFRA-INTRADAY-DATA-001` 후속.
5. **미주 시장매크로** — 본 SPEC = KOSPI/KOSDAQ 만. 미주 (S&P500·NASDAQ·NYSE) = `INFRA-US-MACRO-SNAPSHOT-001` 후속.
6. **테마-주체 매핑 dictionary (SLOT S8)** — `config/runtime.yaml flow_analysis.theme_authority` 의 정식 정의는 별도. 본 SPEC = supply_60d 시계열만, F-Score 산출 dict 는 flow_analyzer manifest + runtime.yaml SLOT 후속.
7. **5 분석가 persona 마이크로 정정** — 본 SPEC = 인프라 신설. persona unknown 가드 해제는 cycle 13 (본 SPEC 구현 풀세트) 시 동시 진행 (chart v3 / fundamental v4 정정 패턴 미러).

## SLOT (5) — 본 SPEC 미확정 후속 시점

<!-- SPEC:INTERVIEW-SLOT -->

| # | SLOT | 결단 시점 |
|---|------|----------|
| **S1** | Distribution Day 임계값 정밀 (-0.2% vs -0.5%? 거래량 +5% vs +10%?) | cycle 13 production 검증 + 회고분석가 PROPOSAL |
| **S2** | sector_rs score 정규화 공식 (clamp 범위 / 비선형 변환) | cycle 13 production 검증 시 사용자 운용 데이터 |
| **S3** | agreement_score 5/5 vs 4/5 가중치 (선형 vs 비선형) | flow_analyzer manifest 작성 시 동시 결정 |
| **S4** | KRX backend `MKD/04/0402` breadth bld 안정성 검증 + alternate source | Phase 1 production 검증 시 (차단 시 KIS 종목 list iterate fallback) |
| **S5** | KIS 지수 chart endpoint (`FID_COND_MRKT_DIV_CODE=U`) 의 정확한 spec | cycle 13 구현 시 connectors/kis/client.py 확장 검증 |

## 영향 SPEC

1. **INFRA-CHART-DATA-001 v2** — `chart_ohlcv` 테이블 + `connectors/kis/client.py get_daily_chart` 가 본 SPEC 의 핵심 base. KIS get_daily_chart 의 지수 ticker 지원 확장은 본 SPEC 의 `modifies` 항목 (cycle 13 구현 시).
2. **ANALYST-PERSONAS-001 v2** — market_state_analyzer / stock_picker / flow_analyzer 의 § Inputs 갱신 (snapshot 의 신규 필드 정합) + manifest `reads_snapshot_extend` 플래그 신설 가능성. persona 정정은 cycle 13 구현 풀세트 시 동시 (chart v3 / fundamental v4 패턴 미러).
3. **STRATEGY-TRACK-001 v2** — Track Selector 의 verdict 산출이 9 분석가 점수 read 의 5 분석가 점수가 정상 발행되어야 verdict=ok 가능. 본 SPEC 활성화로 자연 해소.
4. **GUIDANCE-ACCURACY-TRACKER-001 (백로그)** — market_macro_snapshot 의 시계열 적재 = 5 KPI 추적 시 시장 체제 라벨링 base.

## 구현 순서 (15 단계, 별도 사이클 cycle 13)

본 사이클 = SPEC frozen 만. 실제 구현은 다음 사이클 cycle 13 (예상 ~2 세션):

1. `core/db/migrations/v7_snapshot_extend.sql` 신규 + `core/db/schema.sql` schema_version 6→7
2. `connectors/kis/client.py` `get_daily_chart` 의 지수 ticker (`FID_COND_MRKT_DIV_CODE=U`) 지원 확장
3. `connectors/krx/client.py` `MKD/04/0402` breadth helper 추가
4. `collectors/market_macro.py` 신규 (MarketMacro + compute_market_macro + refresh_market_macro_all)
5. `tests/test_market_macro.py` 신규 (5 케이스)
6. `collectors/sector_rs.py` 신규 (SectorRS + compute_sector_rs)
7. `tests/test_sector_rs.py` 신규 (4 케이스)
8. `collectors/supply_demand_history.py` 신규 (refresh_supply_demand_today + get_supply_60d)
9. `tests/test_supply_demand_history.py` 신규 (4 케이스)
10. `tests/test_snapshot_extend_db.py` 신규 (4 케이스)
11. `collectors/snapshot.py` 의 `MarketSnapshot` 신규 필드 3 + `build_market_snapshot` 신규 fetcher 3 + `render_snapshot_md` 9~11 섹션 누적
12. `core/inference/run_analyst.py` metadata 신규 4 키
13. `tests/test_compose_market_snapshot_md_v1.py` + `tests/test_run_analyst_snapshot_extend_metadata.py` 신규 (9 케이스)
14. `server/schedulers/jobs/snapshot_macro.py` + `register_infra_jobs` 등록 + `justfile` 레시피 (`refresh-snapshot-macro` + `fetch-supply-today`)
15. **Production smoke**: `ask_analyst market_state_analyzer "지금 시장 체제 어디?"` + `ask_analyst stock_picker "지금 매수 후보"` + `ask_analyst flow_analyzer "005930 수급 분석"` → 3 분석가 본격 판정 발행 확인 + Track Selector `long: 005930` verdict=ok 발행 → **Production UX 진입 차단점 해소 ✨**

## 본 사이클 (cycle 12) — SPEC only

본 사이클 산출물:
- `docs/specs/INFRA-SNAPSHOT-EXTEND-001-snapshot-extend.md` 신설 (본 파일)
- `scripts/validate.py` frontmatter 통과 검증
- `docs/c_worked/2026-05-21_infra-snapshot-extend-spec.md` 신규 (wrap-up)
- `docs/RESUME.md` Top 3 갱신 (Top 1 = INFRA-SNAPSHOT-EXTEND-001 구현 cycle 13 / Top 2·3 재배치)
- `docs/SESSIONS.md` 행 추가
- 메모리 신규: `project_snapshot_extend_spec.md` (가칭)

코드 변경 0. 다음 사이클 cycle 13 = 본 SPEC 의 15 단계 구현 풀세트.
