---
spec_id: INFRA-STOCK-SUPPLY-001
title: 종목 레벨 5주체 수급 collector — F-Score 세 축(theme_match·momentum·inflow_speed)을 시장 프록시 → 종목 실측 승급
team: shared
type: feature
status: approved
version: 1
owner: flow_analyzer
generates:
  - collectors/stock_supply.py        # 종목별 5주체 수급 collector (fetch_stock_supply KRX + upsert + load_stock_supply_window + get_stock_supply_60d). supply_demand_history.py 1:1 mirror + ticker 축
  - tests/test_stock_supply.py        # 멱등 upsert + load window 정순 + 60일 백필 + 당일 재-fetch + agreement 재사용 + cutoff_date 결정론
modifies:
  - core/db/schema.sql                # stock_supply_history 테이블 신설 (PK (ticker, date), 5주체 net + source) + schema_version bump + 멱등 migration
  - connectors/krx/client.py          # 종목별 투자자별 거래실적 backend helper (getJsonData.cmd) — 5주체 net + 단위 정규화(→백만원)
  - connectors/kis/client.py          # 단일 종목 market_cap helper (inflow_speed 분모) — 기존 market_cap_rank 는 top-N 이라 단건 조회 신설/재사용
  - collectors/flow_inputs.py         # build_flow_inputs 의 net_sums 소스 = 종목 우선 → 미가용 시 시장 supply_demand_history fallback(source 라벨) + market_cap 주입 배선
depends_on:
  - INFRA-SCORE-INPUTS-001 (flow_inputs F-Score 원시 지표 배선 + theme_match 2-Stage 골격 — net_sums 입력만 교체하면 score_theme_match 무수정 재사용)
  - INFRA-SNAPSHOT-EXTEND-001 v1 (supply_demand_history 시장 레벨 5주체 + agreement_score 순수 함수 — fallback 소스 + 재사용)
related:
  - reference_krx_backend (KIS 가 못 주는 종목별 5주체 = data.krx.co.kr getJsonData.cmd POST backend)
  - feedback_backtest_essence (cutoff_date + 캐싱 default. 배치 cron 본체는 SLOT 분리)
  - feedback_llm_intuition_distribution (theme_match 골격 = 데이터 소스 무관, net_sums 입력만 교체)
  - INFRA-SCORE-INPUTS-001 SLOT S2 (stock-level breakpoints·theme_authority production 튜닝은 실분포 누적 후)
contracts:
  - name: stock-supply-v1
    version: "1.0"
    description: "get_stock_supply_60d(ticker, cutoff_date=None) → {ticker, actual_days, foreign_net_60d, institution_net_60d, individual_net_60d, financial_inv_net_60d, pension_net_60d, agreement_score_60d, market_cap, source}. build_flow_inputs(ticker=) 가 이 net 을 theme_match/momentum/inflow_speed 입력으로 사용. 종목 미가용 시 source='market_proxy' 로 시장 레벨 fallback. team_outputs 저장 X (flow_analyzer StandardOutput 이 판단)."
---

# INFRA-STOCK-SUPPLY-001 — 종목 레벨 5주체 수급 collector

## 목적 (왜)

INFRA-SCORE-INPUTS-001 로 F-Score(수급 점수) 원시 지표가 라이브에 올랐으나, **세 데이터 축(theme_match·momentum·inflow_speed)이 전부 시장 레벨(KOSPI/KOSDAQ 집계) 프록시**다. 2026-05-31 라이브 검증에서 005930 theme_match 가 분류는 정확(AI_semiconductor)했으나 **점수가 중립 근처(4.5)** — 시장 전체 5주체 net 으로 채점하니 종목 변별력이 0이기 때문. 본 SPEC 은 종목 레벨 5주체 수급을 수집해 **F-Score 세 축을 한꺼번에 시장 → 종목 실측으로 승급**한다.

### 본질 (이 SPEC 의 핵심 구조)

theme_match 골격(`score_theme_match`)은 설계 때부터 **분류(LLM 직관) ⊥ 채점(결정론) 분리** — 채점은 `net_sums` 만 받는다. 따라서 **데이터 소스를 시장 → 종목으로 갈아끼우는 것이 전부**이고 분류·채점 로직은 무수정 재사용된다. 같은 종목 net 이 momentum·inflow_speed 두 축도 동시에 종목 실측으로 올린다.

## 면담 확정 결단 (영구 권위)

| # | 결단 | 근거 |
|---|---|---|
| R1-a | **데이터 소스 = KRX 풀 5주체** (getJsonData.cmd 종목별 투자자별 거래실적) | 시장 테이블 5주체와 정합 → `theme_authority` 의 pension·financial_inv 매핑 테마(예 defense_nuclear)도 살아남 + `score_theme_match` 무수정 재사용. KIS `investor_trend` 는 3주체뿐이라 탈락 |
| R1-b | **수집 트리거 = 질의 종목 on-demand + 캐시** | API 부하 최소 + 백테스팅 친화. theme_match 캐시 패턴과 동일 철학. flow_inputs 흐름에 자연 결합 |
| R1-c | **백필 = 최초 질의 시 60일 1회** | momentum(60일)·inflow_speed 즉시 산출. 이후 당일분만 증분 |
| R2-a | **미가용 시(KRX 실패·신규·미장) 시장 프록시 fallback** | 크래시 0 + 시장 신호 보존. source='market_proxy' 라벨로 정직 표기 |
| R2-b | **market_cap 같이 배선** (KIS 단건 시총) | inflow_speed = (외인+기관 60일 순매수액) / 시총 × 10000 bp. 분모 없으면 축 미산출. F-Score 3축 완전 승급 |
| R2-c | **MVP 1차 = on-demand 단일종목 풀세트** | KRX 5주체 + 60일 백필 + flow_inputs 교체 + market_cap. 배치 cron·미장은 SLOT 후속 |
| R3-a | **당일(today) row 항상 재-fetch, 과거는 멱등 고정** | 장중 수급 변화 반영 + 과거 ON CONFLICT REPLACE 안정 |
| R3-b | **cutoff_date 백테스팅 param 지원** | flow_inputs/anchors 와 동일. 그 시점까지 수급만 |
| R3-c | **국장 only / 일 단위** | KRX 종목별 = 국내 전용. 미장 종목 수급은 별 소스 SLOT |
| R3-d | **agreement_score() 순수 함수 + supply_demand_history fallback 재사용** (신설 0) | DRY |

## 입출력 (I/O)

**입력**: ticker (질의 종목) → KRX getJsonData.cmd 종목별 투자자별 거래실적 (최근 60거래일) + KIS 단건 market_cap.
**저장**: `stock_supply_history` (PK `(ticker, date)`, 5주체 net 백만원 + source). ON CONFLICT REPLACE 멱등.
**출력**: `get_stock_supply_60d(ticker, cutoff_date=None)` → 5주체 60일 net 합 + agreement + market_cap + source. `build_flow_inputs(ticker=)` 가 소비.
**소비자**: flow_analyzer (F-Score 세 축). team_outputs 저장 X — 분석가 StandardOutput 이 판단 담당.

## 아키텍처 (supply_demand_history.py mirror)

```
collectors/stock_supply.py
  ├─ StockSupplyRow (dataclass: ticker, date, 5주체 net, source)
  ├─ fetch_stock_supply(ticker, *, days=60, cutoff_date=None)   # KRX backend → 행 리스트 (당일 재-fetch / 과거 멱등)
  ├─ upsert_stock_supply_row(row)                               # ON CONFLICT (ticker,date) REPLACE
  ├─ load_stock_supply_window(ticker, *, days=60)               # 정순 시계열 (load_supply_window mirror)
  └─ get_stock_supply_60d(ticker, *, cutoff_date=None)          # 60일 net 합 + agreement_score() 재사용 + market_cap
```

`collectors/flow_inputs.py::build_flow_inputs` 변경:
- ticker 있으면 `get_stock_supply_60d(ticker)` 시도 → net_sums = 종목 net (source='stock_krx').
- 실패/빈 데이터 → 기존 `load_supply_window(market)` 시장 프록시 fallback (source='market_proxy').
- market_cap 주입 → inflow_speed 산출.
- net_sums 가 theme_match `resolve_theme_match` 채점 입력으로도 흐름 (이미 배선됨, 입력만 종목으로).

## 판단 로직 / 엣지 케이스

<!-- SPEC:INTERVIEW-SLOT
- ⚠️ KRX bld 미해소 (2026-05-31 구현 smoke): `MDCSTAT02401` + {isuCd:6자리, strtDd, endDd, trdVolVal, askBid} → **400 Bad Request**. 유력 가설 = (1) KRX 는 `isuCd` 에 **풀 ISIN**(KR7005930003) 요구(6자리 X — ticker→ISIN 매핑 필요) (2) bld 는 일별추이 = `MDCSTAT02403`(기간합계는 02401) (3) params 에 `mktId`(STK/KSQ) + `inqTpCd` 누락. **다음: data.krx.co.kr [개별종목 투자자별 거래실적] 페이지 devtools 로 실 POST 검증** (pykrx 소스 참고 가능). 현재 graceful market_proxy fallback 로 비차단.
- 응답 5주체 컬럼 매핑(`_STOCK_INVESTOR_COLS`) + 단위 정규화(원→백만원, 현재 //1e6) 도 실 응답으로 정정. connectors/krx/client.py 기존 getJsonData helper 재사용.
- KRX 5주체 ↔ 시장 테이블 5주체 key 정합 (financial_inv=금융투자, institution=기관계 정의 일치 검증 — KRX 는 금융투자/보험/투신/사모/은행/연기금 등 세분, 5주체로 집계하는 규칙 명시).
- KIS 단건 market_cap: 기존 market_cap_rank(top-N) 외 단건 시총 조회 API(현재가 시세 inquire-price 의 시총 필드 등) 확정 + 단위(억→백만원) 정규화.
- 당일 재-fetch 판정: load 결과의 MAX(date) == today_kst 면 today row 만 재요청, 아니면 60일 백필.
- 백테스팅 cutoff_date: fetch 시점에 cutoff 이후 행 제외 + 캐시는 과거행 멱등이라 안전.
- 미가용 fallback 시 source 라벨 전파 → render_flow_inputs_md 에 "출처: 종목 수급(KRX)" vs "시장 프록시" 명시 (정직성).
- stock_supply_history 무한 누적 방지: 종목 수 × 60일. retention 은 SLOT (작음).
SPEC:INTERVIEW-SLOT -->

## 테스트 (tests/test_stock_supply.py)

- 멱등 upsert (같은 (ticker,date) 2회 → 1행) / load window 정순 / 60일 백필 행 수 / 당일 재-fetch 시 과거행 보존 / agreement_score 재사용 일치 / cutoff_date 결정론 (같은 입력 → 같은 출력) / KRX·KIS mock 필수 (실 API 금지, TESTING=1) / fallback 경로 (빈 데이터 → market_proxy).
- 회귀 0 (기존 flow_inputs/theme_match 테스트 통과 유지).

## SLOT (후속 SPEC/사이클)

- **S1** 거래대금/시총 상위 N 종목 배치 cron 선적재 (장마감 후) — 질의 즉시 응답.
- **S2** stock-level breakpoints·theme_authority production 튜닝 (실분포 누적 후, INFRA-SCORE-INPUTS-001 SLOT S2 와 합).
- **S3** 미장 종목 수급 (별 소스).
- **S4** stock_supply_history retention cron.

## 인수 기준

- 005930 질의 시 theme_match 가 **종목 net 기반 실값**(중립 5.0 아님) + momentum·inflow_speed 종목 실측 산출. source='stock_krx' 라이브 확인.
- KRX 미가용 종목은 source='market_proxy' fallback, 크래시 0.
- pytest 전체 green (회귀 0), validate.py 0 errors.
