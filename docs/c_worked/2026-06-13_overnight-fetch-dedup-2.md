---
date: 2026-06-13
topic: 두 overnight fetch 경로 통합 (중복 fetch 부채 상환)
status: completed
plan_file: C:\Users\HOME\.claude\plans\wondrous-plotting-deer.md
---

# 2026-06-13 · 두 overnight fetch 경로 통합 (중복 fetch 부채 상환)

## 배경
직전 세션(같은 날)이 자가 발견한 부채 상환. 야간자산(미국 지수·환율·금리·원유·선물)을 **두 경로가 코드 중복**으로 yfinance에서 가져왔다 — `collectors/us_markets.py`(자체 `_fetch_sync`+`OVERNIGHT_SYMBOLS`)와 `connectors/yfinance/client.py`(`_fetch_sync`+`TRACKED_SYMBOLS`)가 동일 로직을 두 벌. 재사용 가드(CLAUDE.md #11) 위반. **핵심 판단**: connectors/yfinance를 단일 소스로 두고 us_markets.fetch_overnight()을 얇은 위임 래퍼로 축소 → 소비처 수정 0.

## 한 일
- `connectors/yfinance/client.py` — `TRACKED_SYMBOLS`에 `usdkrw: "KRW=X"` 추가(간밤시황이 환율 필요). 단일 `_fetch_sync` 유지.
- `collectors/us_markets.py` — 자체 `_fetch_sync`(중복)·`OVERNIGHT_SYMBOLS` **삭제**. `fetch_overnight()`을 `get_indices(names=...)` **위임 래퍼**로 축소 + `_OVERNIGHT_NAME_MAP`(로컬 키→TRACKED_SYMBOLS 키, `sox`↔`philly_semi` 한 건만 rename). 시그니처·반환 형식 그대로(소비처 무수정). docstring "Backed by connectors.yfinance"가 실제가 됨.

## 검증 결과
- ✅ 타겟 회귀: `test_market_snapshot`·`test_us_macro`·`test_briefing_render`·`test_kr_futures` 56 passed.
- ✅ 전체 **1145 passed**(회귀 0).
- ✅ 라이브: `fetch_overnight()` 위임이 12개 키 전부 정상(sox=^SOX rename·usdkrw=KRW=X 포함, error 0).
- ✅ `_fetch_sync` 야간자산 경로에 **1개로 수렴**(connectors/yfinance). 소비처(snapshot·collect_overnight_us·send script·us_macro) 무수정 확인.

## 의도적으로 안 한 것
- **런타임 단일 fetch(캐싱/공유)** — 이번은 *코드 중복* 제거(두 _fetch_sync→1). 같은 날 중복 호출은 양쪽 다 DB-first라 이미 억제. 런타임 1회 수렴은 별 SLOT.
- **키 이름 전면 통일**(sox vs philly_semi 소비처 전수 변경) — 리스크 대비 실익 적어 위임 래퍼 rename으로 흡수.
- **`collectors/kr_futures.py`의 _fetch_sync** — 같은 5d-history 로직이나 KM=F/EWY **폴백 전용**(2심볼, KIS 실선물 1순위 뒤)이라 별개. 통합 실익 적어 그대로.

## 다음에 이어서 할 작업 (우선순위)
1. **PAPER-DESK-UX-001 구현 착수 (RB-MS5)** — 오른쪽 뇌 마지막 화면 차단점. `server/api/market.py` generate(야간자산 와이어링) → 시황·가상매매·계좌상세 3화면 + 5탭 셸. 무게중심=프론트.
2. **서버 재시작 + 오른쪽 뇌 verified 게이트 (organic)** — `.env` KOSPI200 야간 심볼 반영(서버 재시작해야 18:05 cron 적재) + WEALTH 스냅샷 ≥5영업일/체결 ≥1/청산 ≥3 누적.
3. **kr_futures _fetch_sync 통합 (소규모, 여유 시)** — KM=F/EWY 폴백도 connectors.yfinance 단일 소스로(세 번째 중복 제거).

## 커밋 상태
- 2커밋 예정: ① feat/refactor(overnight fetch dedup) ② docs: wrap-up → main push.
