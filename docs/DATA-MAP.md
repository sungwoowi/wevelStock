# DATA-MAP — 데이터 도메인 지도 (재사용 가드)

> **목적**: 신규 테이블·collector·엔드포인트를 만들기 **전에**, 같은 도메인을 이미 담는 곳이 있는지 **한눈에** 보게 한다. AI 개발의 기본값("안 보이면 새로 만든다")을 차단하는 토대.
>
> **언제 읽나**: SPEC 의 `generates`/`modifies` 에 신규 `*_snapshot`/`*_log` 테이블, 신규 `collectors/*.py`·`connectors/*.py`, 신규 API 라우트를 넣기 직전. (`docs/WORKFLOW.md` SDD + `.claude/commands/spec-interview.md` 재사용 게이트가 이 문서 확인을 강제.)
>
> **판단 규칙**: 같은 도메인 테이블이 이미 있으면 → **컬럼 확장**(신규 테이블 금지). 같은 카테고리 collector 가 이미 그 source 를 fetch 하면 → **필드 확장**(신규 모듈 금지). 신규를 택하려면 SPEC 본문 "재사용 영향도" 에 **왜 확장이 불가한지** 입증.
>
> **전례 (2026-06-12)**: `commodity_futures_snapshot` 신규 테이블을 제안했다가, `us_macro_snapshot` 이 이미 `gold`(상품선물)·`wti` 를 담고 같은 yfinance 야간 fetch 경로를 쓰는 걸 발견 → 컬럼 확장으로 정정. 이 지도가 있었으면 즉시 보였을 미스.
>
> **갱신**: 신규 테이블/엔드포인트가 SPEC 으로 추가되면 이 표에 1행 추가. 컬럼은 정확한 스키마(`core/db/schema.sql`)를 정본으로 — 이 표는 **소유·파급 지도**(어떤 컬럼이 정확히 있는지가 아니라, 어느 도메인이 어디서 쓰이고 읽히는지).

읽는 법: **write**(누가 채우나) → **backend read**(누가 소비하나) → **frontend·API**(화면 노출 경로) → **도메인**(이 테이블의 본질). 신규를 고민하는 데이터가 어느 행의 도메인과 겹치면, 그 테이블을 확장하는 게 1순위.

---

## 1. 시장·매크로 스냅샷 (일자 스냅샷 — **중복 잘 나는 곳, 확장 우선**)

| 테이블 | write | backend read | frontend·API | 도메인 / 핵심 |
|---|---|---|---|---|
| `us_macro_snapshot` | `collectors/us_macro.py` | `us_macro.py`(DB-first) · `collectors/market_view.py` | (market_view 경유 간접) | **미국 야간 스냅샷** — nasdaq·sp500·sox·vix·dxy·us_10y·**gold**·**wti(fetch만)** + risk-on/off. date(KST) PK. ※ 야간 자산군(브렌트·NQ·ES)은 **여기 컬럼 확장** |
| `market_macro_snapshot` | `collectors/market_macro.py` | `market_macro.py`(DB-first) · `market_view.py` · `core/guidance/kpi.py` | (market_view 경유) | **국장 매크로** — 지수 위계·추세·breadth·Distribution. (date, market) PK. ※ KOSPI200 야간선물은 여기 컬럼 |
| `sector_rs_snapshot` | `collectors/sector_rs.py` | `sector_rs.py` · `market_view.py`(rotation) | (간접) | **섹터 RS 일자** — (date, market, sector) PK, rs_score 0~10 |
| `market_view_snapshot` | `collectors/market_view.py` | `market_view.py`(DB-first) · 포맷터 | (분석 기초, 직접 노출 X) | **시장관 종합** — regime·rotation·entry_posture·one_liner. (date, market) PK |
| `daily_macro` | — (DEPRECATED 미사용) | — | 없음 | 레거시 스켈레톤. 신규 매크로는 위 4개 확장 |

> **야간 매크로/자산군은 거의 다 `us_macro_snapshot`(미국) 또는 `market_macro_snapshot`(국장)에 들어간다.** 새 "snapshot" 테이블 만들기 전에 반드시 이 두 행 확인.

## 2. 수급 시계열 (history)

| 테이블 | write | backend read | frontend·API | 도메인 / 핵심 |
|---|---|---|---|---|
| `supply_demand_history` | `collectors/supply_demand_history.py` | 동 collector · `core/inference/run_analyst.py`(flow 입력) | (간접) | **시장 5주체 수급 일별** — (date, market) PK |
| `stock_supply_history` | `collectors/stock_supply.py` | 동 collector | (간접) | **종목 5주체 수급 일별** — (ticker, date) PK (KIS 3주체) |

## 3. 종목 데이터 (계산 입력)

| 테이블 | write | backend read | frontend·API | 도메인 / 핵심 |
|---|---|---|---|---|
| `chart_ohlcv` | `collectors/charts.py` | `charts.py` · `market_macro.py` · `sector_rs.py` · `core/account/holdings.py`·`desk.py` | 없음(내부 계산) | **KIS 일봉 OHLCV 5년 캐시** — (ticker, date) PK |
| `fundamentals` | `collectors/fundamentals.py` | `fundamentals.py` | 없음 | **yfinance 펀더멘털 8필드 + 분기 5** — ticker PK, 24h TTL |
| `manual_anchors` | (테스트만, 실 write 미구현) | `collectors/anchors.py` | 없음 | 사용자 직접 앵커 — (ticker, timeframe) PK |
| `universe_membership` | `collectors/universe_membership.py`(거래대금) · `collectors/volume_bull.py`(거래량양봉) | `universe_membership.py`(get_stock_name·get_list_members·days_since) · `core/watchlist_view.py` · `core/account/desk_view.py` | `/api/watchlist/funnel` | **관심종목 리스트 일자별 멤버십** — (date, market, ticker, **list_type**) PK. list_type=trade_value\|volume_bull. 종목명 소스 + "며칠 전 상위" + funnel 멤버십(team_outputs.funnel_stage 와 조인). **거래대금 상위 신규 list 만들기 전 여기 확장** |

## 4. 뉴스

| 테이블 | write | backend read | frontend·API | 도메인 / 핵심 |
|---|---|---|---|---|
| `news_source_items` | `collectors/news_source.py` | `news_source.py`(filtered) | (digest 경유) | **수집 뉴스 + LLM 분류 영속 자료층** — url PK 멱등 |
| `news_digest_snapshot` | `collectors/news_source.py` | `news_source.py` · `core/briefing/render.py` | (briefing data_json) | **뉴스 집계 일자** — (scope, date) PK, tone·category·themes |
| `news_items` | `pipelines/market_briefing_pre/stages/persist.py` | `server/api/briefings.py` | GET `/api/briefings/{run_id}` | **레거시 run-scoped 뉴스** — run_id 기반(news_source_items 가 후속 정본) |

## 5. 가상 계좌 (오른쪽 뇌 — 책임 추적)

| 테이블 | write | backend read | frontend·API | 도메인 / 핵심 |
|---|---|---|---|---|
| `account_state` | `core/account/portfolio.py` | `portfolio.py` · `server/api/accounts.py` · `guidance/kpi.py` | GET `/api/accounts` | **가상 4계좌 상태** — account_id PK, seed·deployed_weight |
| `account_positions` | `core/account/paper_trading.py` | `holdings.py` · `paper_trading.py` · `guidance/kpi.py` | GET `/api/accounts/{id}/holdings` | **계좌×종목 보유** — (account_id, ticker) PK, avg_price·shares·weight |
| `account_fills` | `core/account/paper_trading.py` | `holdings.py` · `compounding.py` · `guidance/kpi.py` | GET `/api/guidance/kpi`·`/retrospective` | **가상 체결** — (recommendation_id, account_id, side, leg) PK, realized_pnl_krw |
| `account_equity_snapshot` | `core/account/compounding.py` | `compounding.py` | GET `/api/wealth/curve`·`/progress` | **일별 계좌 자산 스냅샷** — (date, account_id) PK, equity·realized·unrealized |
| `sim_trades` / `sim_positions` | `pipelines/market_briefing_pre/stages/persist.py` | `server/api/positions.py` | GET `/api/positions/sim` | **AI 시뮬레이션 매매**(브리핑 파이프라인 계열, account_* 와 별 계보) |
| `watch_positions` | `server/api/positions.py` · 브리핑 persist | `server/api/positions.py` | GET/POST/PATCH/DELETE `/api/positions/watch` | **사용자 수동 관심/홀딩** — ticker·status·watch_price·signal_cnt |

## 6. 분석·메모리·캐시 인프라 (내부)

| 테이블 | write | backend read | frontend·API | 도메인 / 핵심 |
|---|---|---|---|---|
| `team_outputs` | `core/outputs.py` | `guidance/kpi.py` · `server/api/briefings.py` · `core/strategist/recommendation.py` | GET `/api/briefings/feed`·`/{run_id}` | **팀 판단 표준 저장소** — run_id·team_id·verdict·data_json (분석가↔전략가 통신 정본) |
| `team_memory` | `core/memory/loader.py`·`cleanup.py` | `core/memory/rollup.py` | 없음 | LLM 팀 판단 메모리 원본 — (date, team_id, target) |
| `memory_rollup` | `core/memory/rollup.py` | 스케줄러 rollup | 없음 | 일/주/월 요약 — period_key·summary_md |
| `llm_call_cache` | `collectors/anchors.py`·`market_view.py`·`news_source.py` · `core/memory/cache.py`·`core/intent/cache.py` | `core/memory/cache.py` | 없음 | **LLM 멱등 캐시** — input_hash·response_json·tokens·cost |
| `predictions` | 브리핑 persist | briefing_parts 집계 | (briefing 경유) | 시나리오 예측 + AI 매매일지 |
| `knowledge_index_runs` | `core/knowledge/sync.py` | `core/knowledge/sync.py` | 없음 | KNOWLEDGE-SYNC 운영 로그 |

## 7. 브리핑·알림 출력

| 테이블 | write | backend read | frontend·API | 도메인 / 핵심 |
|---|---|---|---|---|
| `briefing_parts` | `core/briefing/parts_store.py` | `parts_store.py` | GET `/api/briefings/{pipeline_id}/latest/parts/{key}` · POST `/run` | **브리핑 파트 구조화** — (pipeline_id, run_id, part_key) |
| `notifications_log` | `core/notification/service.py` | (read only) | GET `/api/notifications/recent` | **알림 발송 이력** — team_id·level·title·delivered. ※ 알림 영속 확장(type·is_read)은 **여기 컬럼** |

## 8. 레거시·미사용 (DEPRECATED — 신규 데이터를 여기 두지 말 것)

| 테이블 | 상태 |
|---|---|
| `scheduler_runs` · `portfolio_log` · `watchlist` · `daily_macro` | Phase 2-4 스켈레톤, 실 write 없음. 신규는 위 활성 테이블로 |
| `schema_version` | 마이그레이션 버전 레지스트리(현 15). 신규 컬럼 = `core/db/connection.py` `_apply_migrations()` 가드 + schema.sql CREATE + `VALUES (N)` |

---

## 부록 — 마이그레이션 패턴 (신규 .sql 파일 금지, v8 이후)

기존 테이블에 컬럼 추가 = **2곳만 수정** (멱등):
1. `core/db/connection.py` `_apply_migrations()` 에 `_column_exists()` 가드 + `ALTER TABLE ... ADD COLUMN` 블록 (v9 `distribution_count_25d` 전례).
2. `core/db/schema.sql` 의 해당 `CREATE TABLE` 정의에 컬럼 추가(새 DB 처리) + `schema_version VALUES (N)`.

`migrations/*.sql` 신규 파일은 만들지 않는다 (v8 까지만 존재하는 레거시 방식).
