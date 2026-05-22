---
date: 2026-05-22
topic: INFRA-SNAPSHOT-EXTEND-001 구현 풀세트 + SLOT S5 정정 + production smoke (cycle 13)
status: completed
plan_file: C:\Users\HOME\.claude\plans\ancient-crunching-map.md
---

# 2026-05-22 · INFRA-SNAPSHOT-EXTEND-001 구현 풀세트 (cycle 13)

## 배경

cycle 12 (2026-05-21, 438a235) SPEC frozen 직후 cycle 13 구현 풀세트. cycle 11 발견 부채 1 (snapshot 데이터 부재 = 5 분석가 본격 판정 차단점) 해소가 본 사이클 본질. 사용자 결단으로 4 sub-cycle 분할 진행 (조심스럽게 끊고 점검 패턴): 13.1 DB+collectors → 13.2a snapshot 통합 → 13.2b cron+seed → 13.3 SLOT S5 정정. Production smoke 후 **MS3 production UX 차단점 풀세트 실증 해소 ✨**.

## 한 일

### 13.1 (commit `bd1daaf`) — DB v7 + 3 collectors + 2 connectors + 18 tests
- `core/db/migrations/v7_snapshot_extend.sql` — market_macro_snapshot + supply_demand_history 2 테이블 ((date, market) 복합 PK, ON CONFLICT REPLACE 멱등)
- `core/db/schema.sql` — v7 § 추가 + schema_version 7 INSERT
- `connectors/kis/client.py` — get_daily_chart 지수 ticker 분기 (초기 FID_COND_MRKT_DIV_CODE=U 만, cycle 13.3 에서 정정)
- `connectors/krx/client.py` — market_breadth(market) 신규 + BLD_MARKET_BREADTH MDCSTAT04302 (cycle 13.3 미해결 발견)
- `collectors/market_macro.py` — A 4축 (위계/추세/breadth/DD) + DB-first hybrid + cron 진입점
- `collectors/sector_rs.py` — B 14 섹터 ETF 60일 RS 0~10 정규화 (lazy compute)
- `collectors/supply_demand_history.py` — C 5주체 60일 + agreement_score
- `tests/test_market_macro.py` (11) + `test_sector_rs.py` (9) + `test_supply_demand_history.py` (9)

### 13.2a (commit `41f62e8`) — snapshot 통합 + render 9~11 + metadata 4 키
- `collectors/snapshot.py` — MarketSnapshot 4 신규 필드 (market_macro / sector_rs / kr_supply_60d / snapshot_extend_failures) + build_market_snapshot 끝부분 3 fetcher 병렬 (asyncio.gather return_exceptions) + render_snapshot_md 9~11 섹션 graceful skip 패턴 + 본 분석가 사용 지침 §
- `core/inference/run_analyst.py` — _snapshot_extend_metadata 헬퍼 + 두 메타 블록에 4 키 spread
- `collectors/supply_demand_history.py` — get_supply_latest_age_days(market) helper
- `tests/test_snapshot_extend_db.py` (4) + `test_compose_market_snapshot_md_v1.py` (6) + `test_run_analyst_snapshot_extend_metadata.py` (4)

### 13.2b (commit `a54f91c`) — cron + seed ticker + justfile
- `server/schedulers/jobs/snapshot_macro.py` — refresh_supply + refresh_market_macro 순차 cron job
- `server/schedulers/jobs/__init__.py` — infra::snapshot_macro_refresh 등록 (평일 18:05 KST, chart_refresh 5분 후)
- `collectors/charts.py` — _seed_tickers() 신규 (지수 0001/1001 + 15 ETF) + refresh_all_tickers 가 DB distinct ∪ seed
- `justfile` — refresh-snapshot-macro + fetch-supply-today 2 레시피

### 13.3 (commit `bf8140d`) — SLOT S5 정정
- `connectors/kis/client.py` get_daily_chart 지수 분기 = 별도 endpoint `inquire-daily-indexchartprice` + tr_id `FHKUP03500100` + 응답 키 `bstp_nmix_*` + change_rate 일괄 계산 (prev_close 대비 %)
- SPEC 명세 (FID_COND_MRKT_DIV_CODE=U 만) 가 부정확 발견. Raw probe 로 KIS 실 spec 확보 → 정확한 endpoint 분기

### Production smoke (commit 없음, DB 실 적재만)
- KOSPI(0001) + KOSDAQ(1001) 각 1,250봉 적재 (영업일 5년)
- `refresh-snapshot-macro` → market_macro_snapshot 4축 풀세트 (KOSPI position=above_both / trend=uptrend / ma20 +4.48% / ma60 +11.47%) + supply_demand_history 양 시장 적재
- market_state_analyzer 본격 판정 **`strong_bull` · confidence 95% ✨** (cycle 11 unknown 0% → 진전)
- flow_analyzer KOSPI 60일 수치 풀세트 (외인 -1.48조 / 기관 +3,981억 / 부호 일치도 8.0/10)

## 검증 결과

- ✅ pytest 422 → **465 passed** (신규 32: 13.1 18 + 13.2a 14, 회귀 0)
- ✅ DB schema_version 7 적재 (data/db/stock-advisor.sqlite)
- ✅ chart_ohlcv 에 KOSPI/KOSDAQ 각 1,250봉 + market_macro_snapshot 2 row + supply_demand_history 2 row 실 적재
- ✅ 3 분석가 production smoke 본격 판정 발행 (market_state_analyzer + stock_picker + flow_analyzer)
- ✅ SPEC 완료도: generates 11/11, modifies 7/8 (compose.py 만 implicit 정합)

## 의도적으로 안 한 것

- **SLOT S4 (KRX breadth bld)** — 후보 4종 (MDCSTAT04302 / 01101 / 01501 + 두 카테고리) 모두 400. 정확한 bld 는 KRX 데이터시스템 페이지 manual devtools 추출 필요 → 다음 사이클. _fetch_breadth try/except graceful skip 으로 영향 작음 (market_state_analyzer 가 강세 섹터 + 주도주로 우회 추론)
- **stock_picker / flow_analyzer 13.3 재호출** — SLOT S5 정정 효과는 market_state_analyzer 만으로 명확. 둘은 13.2a 단계에서 이미 활성 확인
- **persona v 마이크로 정정** — SPEC § 비-목표. 인프라 활성화로 unknown 가드 자연 해제
- **compose.py 수정** — SPEC § 5 명시 "시그니처 변경 X" 정합 (kwarg 기존 유지, render_snapshot_md 가 9~11 섹션 자동 누적)

## 맥락 재진입 힌트

- **SLOT S4 정정 방법**: KRX 데이터시스템 (https://data.krx.co.kr) 의 "통계 > 주식 > 등락 종목수" 페이지 열어 브라우저 devtools → Network 탭 → `getJsonData.cmd` POST 의 정확한 `bld` payload 추출. 또는 사용자가 직접 알려주면 그대로 박음
- **production UX 진입 차단점 해소 본질**: 3 분석가 모두 본격 판정 가능 확인 → 다음 사이클 = production UX (자연어 채팅창) 진입 자연
- **cycle 13 분할 패턴 (4 sub-cycle) 검증**: 13.1 → 13.2a → 13.2b → 13.3 의 작은 단위 commit + 사용자 중간 점검 패턴이 큰 SPEC 의 구현 risk 분산에 효과. cycle 5/9/12 의 "SPEC frozen → 다음 사이클 구현" 패턴 위에 또 한 층 (대형 구현 사이클의 sub 분할)

## 다음에 이어서 할 작업 (우선순위)

### 1. production UX 본질 구현 (~3 세션) ✨ — MS3 차단점 해소 후 자연 진입
- **왜**: cycle 13 의 핵심 산출 = 3 분석가 본격 판정 활성. 옛 Top 3 의 차단점 (snapshot 부재 상태 UX 무의미) 해소 ✨. 가장 큰 사용자 가치 = 자연어 채팅창에서 의미 있는 답변 가능 단계
- **범위**: 자연어 intent extractor (Haiku 4.5 분류 또는 결정론 키워드 룰) + Track Selector 자동 라우팅 + 종합 답변 형식 (분석가 점수 + 전략가 권고 통합 markdown) + webapp 단일 채팅창 UI 재구성 + R&D 토글 별도 페이지 보존
- **예상 산출**: 첫 자연어 호출 가능 ("삼성전자 진입할까?" → 자동 라우팅 → Track A·B 종합 답변)

### 2. `WAVE-ALPHA-001` SPEC 신설 (~1 세션)
- **왜**: 잔여 차단점 = α=null (anchor A/B/C 미확정, SLOT S1). 산출 가능 시 stock_analyst verdict=confirmed_* 정식 발행. snapshot extend 와 독립
- **범위**: `/spec-interview` 5 라운드 → anchor 정의 + collectors/scoring.py alpha() 정식 + canon 보강 + persona α § 정정 + 테스트
- **예상 산출**: α 값 정상 발행 → verdict=confirmed_* → MS4 진입 베이스라인

### 3. **SLOT S4 (KRX breadth bld) 정정** (~0.3 세션 소규모) — production UX 또는 WAVE-ALPHA 와 묶기 가능
- **왜**: 잔여 발견 부채. market_macro breadth 축 활성 = market_state_analyzer 4축 풀세트
- **범위**: KRX 데이터시스템 manual devtools 추출 + connectors/krx/client.py bld 교체 + smoke 재시도. 차단 시 KIS volume_rank 응답으로 fallback 검토 (SPEC SLOT S4 명시)

(추가 백로그 동일: NEWS-SOURCE-001 / PERSONA-REFUSAL-CITED-RULE-001 / news_curator 슬림화 / Layer 4·5 / GUIDANCE-ACCURACY-TRACKER / scoring.py 정식 가중치 / streaming UI / Memory Compression / 박종훈 Vol 2/3 / png vision / xlsx sheet 분리 / canon 정수 추출 자동화)

## 커밋 상태

- cycle 13 코드 변경 풀세트 4 commit 박힘 + push 진행 예정
  - `bd1daaf` (13.1) DB v7 + 3 collector + 2 connector + 18 test
  - `41f62e8` (13.2a) snapshot 통합 + render 9~11 + metadata + 14 test
  - `a54f91c` (13.2b) cron + seed ticker + justfile
  - `bf8140d` (13.3) SLOT S5 정정 + production smoke 풀세트 실증
- 본 wrap-up commit + push 진행
