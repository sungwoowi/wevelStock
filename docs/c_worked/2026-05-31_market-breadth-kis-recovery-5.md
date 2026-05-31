---
date: 2026-05-31
topic: KRX 5주체 조사(Akamai 벽 확정) → market_breadth KIS 업종지수 소스로 복구
status: completed
plan_file: C:\Users\HOME\.claude\plans\pure-wobbling-hammock.md
---

# 2026-05-31 · market_breadth KIS 복구 (KRX 5주체 Akamai 벽 확정)

## 배경
RESUME Top 1 = KRX 5주체 복구였으나, 사용자가 "data.krx devtools가 막혀 캡처 불가, 공식 API나 다른 방법?"을 물음. 조사 결과 **KRX STAT 통계 전체가 Akamai Bot Manager 차단**임을 실증으로 확정 → 5주체는 포기(실익 ≈ 0)하고, 대신 같은 벽에 막혀있던 **가치 있는 market_breadth를 KIS 업종지수 소스로 복구**. 핵심 판단: pykrx도 이 벽 못 뚫음(OHLCV만 몰래 네이버 우회), devtools도 무의미(Akamai 토큰=브라우저 센서 바인딩).

## 한 일
- `connectors/kis/client.py` — `market_breadth(market)` 신규 + `_BREADTH_INDEX_CODE`. `inquire-index-price`(FHPUP02100000)의 `ascn/down/stnr/uplm/lslm_issu_cnt` → 전체 시장 등락 종목수 파싱. rt_cd≠0 시 source="unavailable".
- `collectors/market_macro.py` — `_fetch_breadth` 체인 **KIS-index 1순위**로 재배선(구 KRX-first 제거) → 빈/0 시 KIS volume_rank top30 대용 강등. KRXClient import 제거 + 톱 docstring 갱신.
- `connectors/krx/client.py` — `market_breadth`·`BLD_STOCK_INVESTOR` **Akamai 폐기 주석**(휴면 보존, 미래 세션 재시도 방지). 5주체=KIS 3주체 확정 명시.
- `tests/test_market_macro.py` — breadth 테스트 +5 (KIS 파싱·index_code 매핑·error unavailable·체인 1순위·fallback 강등).
- (pyproject) — pykrx add→remove 상쇄, net 무변경.

## 검증 결과
- ✅ pytest **714 → 719 passed (+5, 회귀 0, TESTING=1)**.
- ✅ **라이브 breadth GREEN**: KOSPI 206↑/688↓/보합28/상한4 (ratio 0.23) · KOSDAQ 309↑/1392↓/보합39 (ratio 0.18). 둘 다 전체 시장 `source=kis_index`.
- ✅ 조사 실증: KRX getJsonData STAT(02303 일별추이/02401 기간합/01701 OHLCV/04302 breadth) 전부 "400 LOGOUT", OTP→download.cmd 403 Akamai. MAIN bld(선물)만 200 정상. pykrx OHLCV 작동=`adjusted=True` 시 네이버 우회 확인.

## 의도적으로 안 한 것
- **KRX 5주체 복구 포기** — Akamai 엔터프라이즈 봇차단(HTTP/pykrx/devtools 전부 불가). 금융투자=테마 0개·연기금=1개(institution 우회 정상) → 실익 ≈ 0. headless 브라우저(Playwright)는 고비용·저실익이라 제외(사용자 결정).
- **네이버 투자자(2주체) 채택 안 함** — KIS 3주체보다 적어 후퇴.

## 기술 부채/미완
- **종목 5주체는 KIS 3주체로 영구 확정** — financial_inv/pension은 항상 0. theme_authority는 institution 우회 유지.
- **시스템 날짜 2026-05-31 = 실제 KRX 날짜** (MAIN bld가 20260529 실데이터 반환). 기존 "KIS sim 미래" 가정은 KIS 모의계좌 한정일 수 있음 — 추후 KRX/KIS 날짜 정합 점검 권장.
- breadth top30 fallback은 KIS index 실패 시에만 — 정상 경로는 항상 kis_index.

## 맥락 재진입 힌트
- KRX STAT은 Akamai 벽 = 영구. 새 KRX 데이터 욕심나면 MAIN bld(getJsonData)만 가능, STAT은 포기. 휴면 helper(market_breadth/stock_investor_supply) 재호출 금지(주석 박힘).
- breadth source 라벨: kis_index(정확·전체시장) / kis_volrank_top30(대용) / unavailable. market_state_analyzer가 breadth_source로 한계 식별.

## 다음에 이어서 할 작업 (우선순위)
1. **buy_score·S-Score 후속 배선** — `collectors/scoring.py` s_score·buy_score 정식 가중치(SLOT S7) + SCREEN-RS-EXTENSION-001(rs 축, prism #289 draft) + run_analyst hook. 5점수 체계(S/T/α/buy/F) 완성.
2. **F-Score breakpoint 운용 재튜닝** — 직전 S2는 13종 1일 스냅샷 1차 캘리브레이션. `scripts/flow_distribution.py` 재실행으로 다일·다종목 누적 후 중간점 정밀화.
3. **KIS/KRX 날짜 정합 점검** — KIS sim(미래?) vs KRX 실날짜 혼선 가능성. snapshot/breadth 시점 일관성 확인.

## 커밋 상태
- 코드 1 커밋(market_breadth KIS 복구) + wrap-up docs 1 커밋, 사용자 요청으로 push 예정. main 직접(솔로).
