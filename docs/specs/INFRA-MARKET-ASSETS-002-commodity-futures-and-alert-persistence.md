---
spec_id: INFRA-MARKET-ASSETS-002
title: 자산군 수집 확장 + 알림 영속 — 야간자산(WTI·브렌트·NQ·ES·KOSPI200야간) 기존 스냅샷 컬럼 확장 + notifications_log read 확장 (PAPER-DESK-UX 시황·알림 백엔드)
team: shared
type: feature
status: draft
version: 1
level: implementation
parent: RIGHT-BRAIN-COMPLETION-001
owner: account_manager
# 확장 전용 SPEC — 신규 테이블·신규 collector 파일 0. 기존 us_macro/market_macro/notifications_log 컬럼 확장.
generates: []
modifies:
  - core/db/schema.sql                               # us_macro_snapshot(+wti·brent·nq_futures·es_futures change_pct) + market_macro_snapshot(+kospi200_night_change_pct) + notifications_log(+notification_type·is_read) + schema_version (16)
  - core/db/connection.py                            # _apply_migrations v16 멱등 ALTER 블록 (v9 distribution_count_25d 가드 패턴 재사용)
  - collectors/us_markets.py                         # OVERNIGHT_SYMBOLS 에 brent(BZ=F)·nq(NQ=F)·es(ES=F) 추가 (wti=CL=F 이미 있음)
  - collectors/us_macro.py                           # USMacroSnapshot dataclass + compute/upsert 에 4 야간자산 필드 스레딩 (fetch_overnight 이 이미 fetch)
  - collectors/market_macro.py                       # KOSPI200 야간선물 KIS 조회 → kospi200_night_change_pct (graceful null)
  - server/api/market.py                             # market-snapshot-v1 자산군 섹션 WTI·브렌트·야간선물 null → 실값 (PAPER-DESK-UX 생성 파일)
  - server/api/notifications.py                      # mark-read 엔드포인트 + recent 응답에 notification_type·is_read 노출
  - core/notification/service.py                     # notify() 발송 시 notification_type 기록 + is_read=0 default
  - tests/test_us_macro.py                           # 야간자산 컬럼 round-trip 테스트 확장
  - scripts/_us_macro_probe.py                       # 야간자산 라이브 probe 확장
depends_on:
  - RIGHT-BRAIN-COMPLETION-001 (소속 roadmap — PAPER-DESK-UX-001 지원 인프라)
  - PAPER-DESK-UX-001 (market-snapshot-v1 자산군 3종·알림 탭 read 자리 예약처 — line 37·102·149)
  - INFRA-US-MACRO-SNAPSHOT-001 (us_macro_snapshot 확장 대상 — gold·wti 가 이미 사는 야간 스냅샷)
  - INFRA-SNAPSHOT-EXTEND-001 (market_macro_snapshot 확장 대상 + v9 멱등 ALTER 전례)
contracts:
  - name: overnight-assets-v1
    version: "1.0"
    description: >
      야간자산 수집 = 신규 테이블 아님. 기존 일자 스냅샷 컬럼 확장.
      us_macro_snapshot(date PK)에 wti_change_pct·brent_change_pct·nq_futures_change_pct·es_futures_change_pct 추가
      (gold_change_pct 옆 — 동일 yfinance 야간 fetch 경로, WTI 는 이미 fetch 중이라 컬럼만).
      market_macro_snapshot(KOSPI 행)에 kospi200_night_change_pct 추가(KIS 야간 조회, 미지원 시 null).
      결정론 수집만(LLM 0), 기존 source 컬럼 graceful 폴백 그대로.
  - name: notification-persistence-v1
    version: "1.0"
    description: >
      알림 영속 확장(신규 테이블 아님 — notifications_log 확장). 추가 컬럼 notification_type∈
      {market_briefing,trade_signal,account_safety,flow_idea,risk_alert} + is_read(0|1, default 0).
      read 엔드포인트: GET /api/notifications/recent(notification_type·is_read 포함) + POST /api/notifications/mark-read(id[] 또는 전체).
      UI 알림 탭의 종 배지 미독 카운트·필터 소스. 미구현 notify 트리거 3종(매수매도·계좌안심·위험발동) 배선은 범위 밖.
---

# INFRA-MARKET-ASSETS-002 — 자산군 수집 확장 + 알림 영속

> **이 문서는 implementation-level SPEC 이다.** `RIGHT-BRAIN-COMPLETION-001` 의 지원 인프라 자식 — `PAPER-DESK-UX-001`(RB-MS5) 이 의도적으로 분리한 "신규 수집" 절반을 채운다.
>
> **확장 전용 — 신규 테이블·신규 collector 파일 0.** 야간자산(WTI·브렌트·NQ·ES)은 `us_macro_snapshot` 이 이미 담는 야간 스냅샷 카테고리(`gold`·`wti` 가 이미 거기 산다)다. 새 테이블을 만들지 않고 **컬럼만** 더한다. WTI(`CL=F`)는 `us_markets.py` 가 이미 매일 fetch 하나 컬럼이 없어 버려지던 값 — 이번에 영속처를 준다.
>
> **두 부분, 한 SPEC**: ① 야간자산 컬럼 확장(us_macro·market_macro) ② 알림 영속 확장(notifications_log type·is_read). 둘 다 PAPER-DESK-UX 가 read 만 하고 비워둔 자리를 메운다.

## 목적
- PAPER-DESK-UX-001 시황 화면의 자산군 카드(현 `WTI·브렌트·야간선물 = null`, line 102)를 **실값**으로 채운다 — 자산군 충실도 "거의 풀" 완성.
- 알림 탭(현 placeholder, line 76·149)이 **읽고 미독 배지를 그릴** 영속 토대를 만든다.
- **재사용 극대화**: 기존 `us_macro.py` DB-first 3단계 + `fetch_overnight()` + 18:05 cron 단일 호출점 + 멱등 ALTER 패턴을 전부 그대로 — 신규 수집 인프라 0.

## 재사용 영향도 (DATA-MAP 게이트 산출 — 절대원칙 #11)
신규 테이블·collector 0 으로 정정한 근거 ([[docs/DATA-MAP.md]] §1·§7):
- **야간자산 → 기존 home 있음**: `us_macro_snapshot`(§1)이 이미 미국 야간 스냅샷 도메인 — `gold`(상품선물)·`wti`(fetch만) 가 이미 거기 산다. `wti` 는 `collectors/us_markets.py` `OVERNIGHT_SYMBOLS` 가 매일 fetch 하나 컬럼이 없어 버려지던 값. → **컬럼 확장**(브렌트·NQ·ES), 신규 테이블 불가 입증(같은 date PK·같은 yfinance 야간 fetch·같은 source 폴백 — 쪼갤 관심사 없음).
- **KOSPI200 야간 → 기존 home 있음**: 국장 매크로 = `market_macro_snapshot`(§1, KOSPI 행) → 컬럼 1개.
- **알림 → 기존 home 있음**: `notifications_log`(§7) + `GET /api/notifications/recent` 이미 존재 → **컬럼 확장**(type·is_read) + mark-read, 신규 테이블 아님.
- **3층 파급**: DB = 컬럼 ALTER(connection.py 가드 + schema.sql). backend = us_macro/market_macro/notification 기존 경로에 필드. frontend = PAPER-DESK-UX 가 이미 잡은 `/api/market/snapshot` 자산군 자리·알림 탭에 값만 흐름(신규 화면 0). → **충돌·중복 0, 신규 파일 0**.

## 경계 (scope)
- **포함**:
  - **Part A 야간자산 컬럼 확장**: 브렌트(`BZ=F`)·NQ 야간선물(`NQ=F`)·ES 야간선물(`ES=F`) ticker 를 `OVERNIGHT_SYMBOLS` 에 추가(WTI 이미 있음) → `us_macro_snapshot` 4 컬럼. KOSPI200 야간선물(KIS) → `market_macro_snapshot.kospi200_night_change_pct`.
  - **Part B 알림 영속**: `notifications_log` 에 `notification_type`·`is_read` 컬럼(멱등 ALTER, v16) + `GET /recent` 응답 확장 + `POST /api/notifications/mark-read`.
- **제외 (별 작업/SPEC)**:
  - **신규 테이블 / 신규 collector 모듈** — 의도적 회피. 기존 스냅샷 컬럼 확장이 본질(과잉 분리 금지).
  - **미구현 notify 트리거 3종**(매수매도·계좌안심·위험발동) 배선 — verdict 생성은 되나 notify stage 없음. account_manager·guidance 도메인 건드림이라 별 작업.
  - 자산군 OHLCV 시계열·차트 — 일자 스냅샷 컬럼만.
  - 자산군 risk tilt·LLM 해석 발행 — 결정론 수집·영속만. (필요 시 후속 SLOT: 야간자산이 `risk_signal` 분류에 가중되는지)
- **일배치 기준**: 평일 18:05 cron 일 단위 — us_macro 와 동일 시점, 신규 schedule 0.
- **graceful 부분 발행**: yfinance/KIS 일부 실패 시 해당 컬럼 null, 기존 `source` 폴백 그대로 (us_macro 패턴).

## 소비 데이터 / 산출
| 영역 | 위치 | 상태 |
|---|---|---|
| 브렌트·NQ·ES 야간 시세 | `OVERNIGHT_SYMBOLS` + yfinance | ticker 3개 추가 (fetch 경로 기존) |
| WTI 야간 시세 | `OVERNIGHT_SYMBOLS.wti` | **이미 fetch 중** — 컬럼만 |
| KOSPI200 야간선물 | KIS 야간 조회 | **신규 (유일한 진짜 신규, source 결정점)** |
| 야간자산 영속 | `us_macro_snapshot`(+4) · `market_macro_snapshot`(+1) | **컬럼 확장 (신규 테이블 아님)** |
| 시황 자산군 카드 | `GET /api/market/snapshot` 자산군 섹션 | PAPER-DESK-UX 자리 → 본 SPEC 채움 |
| 알림 영속·미독 | `notifications_log`(+type·is_read) | **컬럼 확장** |
| 알림 read·mark-read | `GET /api/notifications/recent` · `POST /mark-read` | recent 기존 → 확장 + mark-read 신규 |

---

## 판단·구현 로직 (INTERVIEW-SLOT)

<!-- SPEC:INTERVIEW-SLOT role="overnight-asset-column-extension" -->
**야간자산 컬럼 확장 (overnight-assets-v1) — us_macro 경로 재사용.**
신규 테이블·신규 collector 금지. 기존 경로에 필드만 더한다:
- `collectors/us_markets.py` `OVERNIGHT_SYMBOLS` 에 `brent: "BZ=F"`·`nq_futures: "NQ=F"`·`es_futures: "ES=F"` 추가 (wti 이미 존재). `fetch_overnight()` 가 자동 포함.
- `collectors/us_macro.py` `USMacroSnapshot` dataclass + `compute_us_macro()`/`upsert_us_macro()` 에 `wti_change_pct·brent_change_pct·nq_futures_change_pct·es_futures_change_pct` 스레딩. 기존 `source`·graceful 폴백 그대로.
- `us_macro_snapshot` 컬럼 4개는 `gold_change_pct` 옆 — 동일 야간 카테고리.
> us_macro 가 이미 매일 도는 야간 스냅샷이라 신규 fetch·신규 upsert·신규 cron 0. 컬럼·필드만.
<!-- /SPEC:INTERVIEW-SLOT -->

<!-- SPEC:INTERVIEW-SLOT role="kospi200-night-futures-source" -->
**KOSPI200 야간선물 source 결정 (유일한 진짜 신규).**
yfinance 미지원 — KIS 야간 파생 조회. `collectors/market_macro.py`(KOSPI 행)에 `kospi200_night_change_pct` 컬럼으로 채운다. 구현 시 확정:
- KIS 야간선물 엔드포인트/종목코드(CME·EUREX 연계 야간장) 실측. NXT 미지원 전적([[project_nxt_integration_backlog]]) 유의.
- 조회 불가 시 **graceful null** — KOSPI200 만 빠지고 미국 야간자산은 정상 (전체 실패 금지).
- KIS rate limiter 인스턴스별 레이싱([[project_kis_rate_limit_backlog]]) — 기존 throttle 재사용, 신규 호출 최소.
> 미국 4종(yfinance, 컬럼만)이 MVP 코어. KOSPI200 은 best-effort — source 불가 판명 시 백로그 강등.
<!-- /SPEC:INTERVIEW-SLOT -->

<!-- SPEC:INTERVIEW-SLOT role="idempotent-column-migration-v16" -->
**v16 멱등 컬럼 마이그레이션 (신규 .sql 파일 아님).**
v9 `distribution_count_25d` 전례 그대로:
- `core/db/connection.py` `_apply_migrations()` 에 v16 가드 블록 — `_column_exists()` 체크 후 `ALTER TABLE ... ADD COLUMN` (us_macro 4개 + market_macro 1개 + notifications_log 2개).
- `core/db/schema.sql` 의 해당 CREATE 정의에 컬럼 추가(새 DB 처리) + `schema_version VALUES (16)`.
- cron 합류 불필요 — us_macro/market_macro 는 이미 `run_snapshot_macro_refresh()` 에 있음. 필드만 늘어 자동 적재.
> 마이그레이션 = 코드 가드(connection.py) + 정의(schema.sql) 2곳. migrations/*.sql 신규 파일 X (v8 이후 컨벤션).
<!-- /SPEC:INTERVIEW-SLOT -->

<!-- SPEC:INTERVIEW-SLOT role="market-snapshot-asset-wiring" -->
**market-snapshot-v1 자산군 섹션 채움 (`server/api/market.py`).**
PAPER-DESK-UX 가 자산군 카드에 `WTI·브렌트·야간선물 = null` 자리만 잡아둠(line 102) — `us_macro_snapshot`/`market_macro_snapshot` 오늘 row 의 신규 컬럼을 read 해 실값 주입.
- 결정론 DB read 만(LLM·fan-out 0), 미수집 자산군은 여전히 null partial.
- 응답 자산군 섹션 = 금·환율·금리·VIX(기존) + WTI·브렌트·NQ·ES·KOSPI200야간(본 SPEC).
> `market.py` 는 PAPER-DESK-UX 가 generate — 본 SPEC 은 자산군 섹션만 확장(cross-SPEC modify).
<!-- /SPEC:INTERVIEW-SLOT -->

<!-- SPEC:INTERVIEW-SLOT role="alert-persistence-extension" -->
**알림 영속 확장 (notification-persistence-v1).**
신규 테이블 아님 — `notifications_log`(기존 v1) 확장:
- v16 ALTER: `notification_type TEXT`(분류 = market_briefing·trade_signal·account_safety·flow_idea·risk_alert) + `is_read INTEGER DEFAULT 0` + `idx_notifications_is_read`.
- `core/notification/service.py` `notify()` 가 발송 시 `notification_type` 기록(호출부 전달, 미전달 시 team_id→type 매핑) + `is_read=0`.
- taxonomy 확정점: 5종 고정 vs 확장 enum. 기존 발송 2종(시황브리핑·투자흐름)부터 태깅, 나머지는 트리거 배선 때.
> 미구현 notify 트리거 3종 배선은 범위 밖 — 영속 스키마·read 만.
<!-- /SPEC:INTERVIEW-SLOT -->

<!-- SPEC:INTERVIEW-SLOT role="alert-read-mark-endpoints" -->
**알림 read·mark-read 엔드포인트 (`server/api/notifications.py`).**
- `GET /api/notifications/recent` 응답에 `notification_type`·`is_read` 노출(기존 limit 쿼리 유지) — UI 알림 탭 필터·미독 배지 소스.
- `POST /api/notifications/mark-read` — body `{ids:[...]}` 또는 `{all:true}` → `is_read=1` 갱신. 멱등.
- 미독 카운트 = `is_read=0` 집계(별 엔드포인트 vs recent 응답 헤더 — 구현 시 경량 택).
> UI 종 배지 = 미독 🔴+🟢 카운트(PAPER-DESK-UX line 134). 이 read 가 그 소스.
<!-- /SPEC:INTERVIEW-SLOT -->

## 검증 방법
- `scripts/_us_macro_probe.py`(확장) 라이브: yfinance 브렌트·NQ·ES + WTI 실값이 `us_macro_snapshot` 신규 컬럼에 멱등 적재, KOSPI200 야간(또는 graceful null) `market_macro_snapshot` 적재 확인.
- `GET /api/market/snapshot` 응답 자산군 섹션에 WTI·브렌트·NQ·ES 실값(미수집은 null) 포함 — PAPER-DESK-UX 시황 카드가 채워짐.
- v16 ALTER 멱등성: 기존 DB·새 DB 둘 다 `_apply_migrations` 후 컬럼 존재 + 기존 row 보존. 재실행 시 'duplicate column' 흡수.
- `notifications_log` 신규 발송에 `notification_type`·`is_read=0` 기록. `POST /mark-read` 후 `is_read=1` + recent 응답 반영.
- `TESTING=1 PYTHONIOENCODING=utf-8 uv run pytest tests/test_us_macro.py` — yfinance·KIS mock, 외부 실호출 0.
- `uv run python scripts/validate.py` frontmatter 통과 + `PYTHONIOENCODING=utf-8 uv run python scripts/project_status.py` 에서 RIGHT-BRAIN 자식으로 표시(미연결 drift 아님).

## 비목표
- **신규 테이블 / 신규 collector 모듈** — 의도적 회피 (과잉 분리 금지). 기존 스냅샷 컬럼 확장이 본질.
- 미구현 notify 트리거 3종(매수매도·계좌안심·위험발동) 배선 — 별 작업.
- 자산군 OHLCV 시계열·차트 — 일자 스냅샷 컬럼만.
- 자산군 LLM 해석·risk tilt 발행 — 결정론 수집·영속만.
- 알림 종류별 on/off 사용자 환경설정 테이블 — read·미독만 (후속).
- 실시간 틱/WebSocket — 18:05 일배치 + SWR 폴링.
