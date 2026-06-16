---
date: 2026-06-16
topic: 관심종목 종목관리 페이지(트랙×단계 funnel) + 큐레이션 + 트레이드플랜 2단계 + 데스크 리뉴얼
status: completed
plan_file: C:\Users\HOME\.claude\plans\sleepy-growing-lampson.md
---

# 2026-06-16 · 관심종목 종목관리 페이지 + 큐레이션 + 트레이드플랜 2단계 (대형 세션)

## 배경
/resume 후 트레이드플랜 2단계로 시작 → 데스크 "지켜보는 권고" 점검 중 사용자가 **"무의미한 universe 덤프"**
라 진단 → **체계적 종목 관리** 재설계로 확장. 핵심 판단: **거래대금/거래량 상위 = 후보 바스킷(소스)일 뿐,
주축은 장기/단기 트랙 × 단계(관심→매수대기→진입), 종목별 매매 시계열 시나리오.** 신규 테이블 최소(가드 #11)
— `universe_membership` 1개로 두 리스트·종목명·일자·컨셉·거래량 흡수.

## 한 일
### 트레이드플랜 2단계(매수대기) + 데스크
- `core/signal/alpha_posture.py` — `enrich_conditional_entry`(진입존 후보=메뉴 지지선, 팩트만) + `FunnelStage`/`derive_funnel_stage`(관심/매수대기/진입 파생) + `watching_score_margin`.
- `core/signal/auto_signal.py` — funnel 배선(진입존 보강·재렌더·단계 파생·영속) + 거래량양봉 cadence 배선 + 종목명 resolver.
- `core/strategist/recommendation.py` — dedup 키 버그 수정((track,ticker) 최신) + `_from_mapping` 평탄 data 복원(round-trip 누수).
- `core/account/desk_view.py` — "지켜보는 권고" 단계 라벨·종목명 폴백·매수대기가·거래대금상위 일자 노출.
- `agents/strategists/track_a|track_b/persona.md` — 매수대기 시나리오 LLM 서술 지시.
- `webapp/.../DeskBoard.tsx`·`labels.ts` — 장기/단기 + 단계 그룹 리뉴얼.
### 종목 관리(관심종목 페이지)
- `core/db/schema.sql`+`connection.py` — `universe_membership`(date,market,ticker,**list_type**,name,rank,trade_amount,**volume**,change_pct,**concept**) PK 4-col. 마이그 v17(list_type)·v18(concept)·v19(volume).
- `collectors/universe_membership.py`(신규) — persist + get_list_members(10일 rolling)·get_stock_name·last_universe_date·days_since.
- `collectors/volume_bull.py`(신규) — 거래량 상위 양봉+3% (하이브리드: 장중 stock_price 실시간 / EOD chart_ohlcv).
- `collectors/universe_curation.py`(신규) — 잡주 floor(리스트별 차등·**상한가 포함**) + 정배열 + **컨셉 분류**(주도주/눌림/바닥, OHLCV 재사용).
- `collectors/screening.py` — fetch_universe_tickers 큐레이션+persist, load_curation_config.
- `core/watchlist_view.py`(신규) — 트랙×단계 + **관심 공용(컨셉별)** + 바스킷(날짜그룹·정렬·교집합 is_dual).
- `server/api/watchlist.py`(신규)+`main.py` — `/api/watchlist/funnel`.
- `webapp/.../watchlist/page.tsx`+`components/watchlist/WatchlistBoard.tsx`(신규)+`AppShell.tsx`(헤더 링크)+`api.ts`+`format.ts`(eokKR·volKR) — `/watchlist` 페이지.
- `scripts/cleanup_recommendations.py`·`_watching_tier_probe.py`(신규) — 종목명 백필·라이브 검증.
- `config/screening.yaml` — alpha_posture(watching_margin)·trade_plan·curation 섹션.
- docs: DATA-MAP(universe_membership)·AUTO-SIGNAL(관심종목 후속)·TRADE-PLAN(2단계 DONE).

## 검증 결과
- ✅ 전체 `uv run pytest -q` **1341 passed**(신규 ~50: alpha_posture·auto_signal·universe_membership·volume_bull·universe_curation·watchlist_view), 회귀 0. validate 0 errors.
- ✅ webapp `npm run build` tsc 0 (`/watchlist` 라우트).
- ✅ 라이브(실 Gemini/KIS): 매수대기 단계·진입존(환각 0), 거래량양봉 26→큐레이션 16, 거래대금 50→32, 정렬·교집합·컨셉(주도주20/눌림3/바닥2) 확인.

## 의도적으로 안 한 것
- 점수기반(S/RS) 컨셉 분류 = 보조 태그만(현재 권고 점수 None) — 차트 컨셉이 주 분류.
- 종목 상세 페이지 + 채팅 prefill 수신 = 인라인 시나리오 + `/chat?ticker=` 링크까지만(다음).

## 다음에 이어서 할 작업 (우선순위)
1. **종목 상세 페이지 + 채팅 이어가기** — `/watchlist/[ticker]` 근거자료+플랜 시계열 + `/chat` 종목 prefill 수신(현재 링크만 걸림).
2. **데스크 "지켜보는 권고" 섹션 개선** — 관심종목 페이지 자리잡았으니 actionable(매수대기+진입)만 남기고 관심은 /watchlist로(메모리 task).
3. **거래량 양봉·미분류 데이터 충실화** — chart_ohlcv 캐시 없는 중소형 → 컨셉/거래량 "—"; 장후 refresh_all_tickers 누적으로 해소되는지 확인 + 자율 cron 첫 실 발화 검증.

## 커밋 상태
- 세션 전체 미커밋(코드+신규모듈+docs) → 이 wrap-up이 feat(코드) + docs(wrap-up) 커밋 + push 예정.

## 맥락 재진입 힌트
- **종목관리 IA**: 바스킷(거래대금/거래량 상위, 큐레이션 소스) → 관심(공용·컨셉 분류) → 골라서 장기/단기 트랙별 매수대기/진입. 단계=`team_outputs.funnel_stage` 재사용, 멤버십=`universe_membership`.
- **dev 재시작 필요**: `rm -rf webapp/.next && npm run dev` (세션 중 .next CSS 404로 "깨짐" 발생 — 코드 무결).
- 라이브 LLM=Gemini만. KIS 토큰 1분당 1회 — 프로브는 단일 shared client 권장.
