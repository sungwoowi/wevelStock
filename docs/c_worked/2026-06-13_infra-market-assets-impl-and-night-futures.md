---
date: 2026-06-13
topic: INFRA-MARKET-ASSETS-002 구현 (야간자산 + 알림 영속 + KOSPI200 야간선물 실선물) + 간밤시황 정정/추가
status: implementing
plan_file: C:\Users\HOME\.claude\plans\wondrous-plotting-deer.md
---

# 2026-06-13 · INFRA-MARKET-ASSETS-002 구현 + KOSPI200 야간선물 실선물 + 간밤시황 정정

## 배경
PAPER-DESK-UX 지원 인프라(SPEC draft)를 구현. **핵심 반전**: 처음엔 "KOSPI200 야간선물 = KIS 한계로 백로그"라 결론했으나, 사용자 요청으로 야간 시간대 실측 → **KIS 연결선물 `101000`(최근월물 자동)이 실계좌에서 작동**(+5.16% 실측). 더불어 기존 텔레그램 간밤시황이 KOSPI200 야간선물로 **EWY ETF 대용(+11.48% 이상치)**을 띄우던 버그를 발견·교체. RIGHT-BRAIN 마감 단계 인프라 한 겹.

## 한 일
### Part A — 야간자산 4종 (us_macro 경로)
- `connectors/yfinance/client.py` — TRACKED_SYMBOLS에 wti(CL=F)·brent(BZ=F)·nq_futures(NQ=F)·es_futures(ES=F). **실 fetch 경로 정정**(SPEC v1이 가리킨 us_markets가 아님).
- `collectors/us_macro.py` — USMacroSnapshot 4필드 + _FETCH_NAMES + snapshot/upsert/restore. 한글 라벨 상수 `OVERNIGHT_ASSET_LABELS_KR`(WTI 원유/브렌트유/나스닥100 선물/S&P500 선물) + render 야간자산 줄 + `overnight_assets_payload` + metadata 노출.

### DB v16 마이그레이션
- `core/db/schema.sql` — us_macro 4컬럼 + market_macro `kospi200_night_change_pct` + notifications_log `notification_type`·`is_read` + idx + schema_version 16.
- `core/db/connection.py` — `_apply_migrations` v16 멱등 ALTER(v9 패턴, 7컬럼).

### Part B — 알림 영속
- `core/notification/service.py` — notify에 `notification_type`(team_id 휴리스틱) + is_read=0.
- `server/api/notifications.py` — recent 응답에 type·is_read·unread_count + `POST /mark-read`(멱등).

### Part C — KOSPI200 야간선물 (KIS 실선물 — 백로그 반전)
- `connectors/kis/client.py` — `index_futures_price(symbol)`(FHMIF10000000, MRKT_DIV=F). 야간 전용 시세 REST 부재라 일반 선물 시세 best-effort.
- `collectors/market_macro.py` — dataclass + `_fetch_kospi200_night_change_pct`(env 게이팅) + compute/upsert/restore.
- `.env`(로컬, gitignore) — `KIS_KOSPI200_FUTURES_SYMBOL=101000`.

### 간밤시황 정정/추가 (텔레그램)
- `collectors/kr_futures.py` — **KIS 실선물 1순위** → KM=F → EWY 폴백. EWY 대용을 진짜 야간선물로 교체.
- `core/briefing/render.py` — 🔮 야간선물 source_kr(실선물/CME/EWY 대용) 명시 + 🌃 미국 야간선물(NQ/ES, 현물과 "선물" 라벨 구분) + 브렌트유.
- `collectors/us_markets.py` — OVERNIGHT_SYMBOLS에 brent/nq_futures/es_futures(간밤시황 경로).
- `pipelines/market_briefing_pre/stages/collect_overnight_us.py` — split에 야간선물/브렌트 반영. `collect_night_futures.py` docstring.
- `collectors/market_view.py` — [7] 블록에 "코스피200 선물 (야간·전일 대비)" 라인(분석가·웹앱).

### 테스트·스크립트
- 신규: `tests/test_notifications_persistence.py`·`tests/test_kr_futures.py` / 확장: `tests/test_us_macro.py`·`tests/test_briefing_render.py`·`tests/test_snapshot_extend_db.py`.
- 신규 probe/send: `scripts/_kospi200_night_probe.py`·`_send_night_futures_telegram.py`·`_send_overnight_briefing_telegram.py` / 확장 `_us_macro_probe.py`.
- `docs/specs/INFRA-MARKET-ASSETS-002-*.md` — modifies 실경로 정정 + status draft→implementing.

## 검증 결과
- ✅ 전체 **1145 passed**(회귀 0). validate.py 0 errors.
- ✅ 라이브 probe: 야간자산 4종 실 yfinance 적재 + DB round-trip. **KOSPI200 야간선물 KIS 연결선물 101000 = +5.16% 실측**(야간장).
- ✅ 텔레그램 실발송 2회 성공(`telegram_ok=True`) — KOSPI200 야간선물 실선물 + 미국 야간선물(NQ/ES) + 브렌트 + 한글 라벨 반영 확인.

## 의도적으로 안 한 것
- `server/api/market.py` 자산군 와이어링 — PAPER-DESK-UX-001 generate 영역(아직 파일 부재). 데이터 백본만.
- 두 overnight fetch 경로(us_markets ↔ connectors.yfinance) 통합 — 범위 큼, 백로그.
- notify 트리거 3종(매수매도·계좌안심·위험발동) 배선.

## 기술 부채/미완
- **야간자산 중복 fetch**: wti/brent/nq/es를 `us_markets.OVERNIGHT_SYMBOLS`(간밤시황)와 `connectors.yfinance.TRACKED_SYMBOLS`(us_macro) 양쪽이 각각 yfinance 호출 — 재사용 가드(#11) 위반, 소비처 달라 분리 유지 중. 통합 백로그.
- **KOSPI200 야간선물 DB 적재 미반영**: `.env` 심볼은 박았으나 떠 있는 서버가 옛 환경 — 서버 재시작해야 다음 18:05 cron부터 `kospi200_night_change_pct` 자동 적재.

## 다음에 이어서 할 작업 (우선순위)
1. **PAPER-DESK-UX-001 구현 (RB-MS5)** — 이번 백엔드(야간자산·알림·KOSPI200 야간)를 소비하는 Next.js 화면. `server/api/market.py` generate + 시황·가상매매·계좌상세 3화면.
2. **두 overnight fetch 경로 통합** — us_markets ↔ connectors.yfinance 중복 fetch 제거(단일 소스). 재사용 가드 정합.
3. **서버 재시작 + 오른쪽 뇌 verified 게이트** — `.env` 반영(KOSPI200 야간 적재) + WEALTH 스냅샷 ≥5영업일/체결 ≥1/청산 ≥3 누적 모니터링.

## 커밋 상태
- 2커밋 예정: ① feat(INFRA-MARKET-ASSETS-002 구현 + 간밤시황) ② docs: wrap-up → main push.
