---
date: 2026-06-02
topic: extension 천장 포화 = C floor (k 오진 정정) + universe 백필 + macro round-trip + MA-ride 주도강도 위계
status: completed
plan_file: C:\Users\HOME\.claude\plans\logical-tickling-flamingo.md
---

# 2026-06-02 · extension floor(C) + universe 백필 + macro round-trip + MA-ride 위계

## 배경
직전 베이스라인이 "extension_score median=10.0 천장 포화 = k=1.0 약함"을 1순위로 지목했으나, 진단 도구에
계측을 붙이자 **오진** 판명: 포화 7종 **100%가 ma20-아래**라 `clamp(10-k·ext/ADR)`서 무조건 10 clamp =
**k 무관**. k 스윕은 무효. 사용자 결정 C = ma20-아래 거리비례 감점 floor. 동시에 캘리브레이션 다일 누적의
전제인 universe 백필 + macro 캐시 충실도(Top 1+2 묶음)도 처리. 세션 중 사용자가 추세추종 doctrine(빠른
이평 타는 주도강도)을 제시 → alignment 일봉 위계로 추가 구현. **핵심 판단: 점수가 안 맞는 원인을 계측으로
분리 검증한 뒤 lever를 바꿈 — 직전 진단을 맹신하지 않음.**

## 한 일
- `collectors/scoring.py` — `extension_score` 양방향 재설계: ma20 위=기존 과열(불변), ma20 아래=`excess=|norm|-deadband` 넘으면 `10-k_below·excess` 감점, deadband 안 얕은 눌림=10. 인자 `k_below`/`below_deadband_adr` 추가
- `collectors/screening.py` — `rank_candidates`에 `k_below_override`/`deadband_override` + raw 노출(extension_pct/adr/normalized) + `get_k_below`/`get_below_deadband_adr`/`get_universe_limits`/`get_universe_max_tickers`/`fetch_universe_tickers` 신설
- `collectors/screening_inputs.py` — `compute_alignment` 일봉 컴포넌트 이진→**graded MA-ride 위계**(`_daily_leadership`: riding_ma4=3/ma7=2.5/uptrend=2/above=1.5/below=0) + detail `daily_leadership` + render 한국어 라벨
- `collectors/charts.py` — `_select_refresh_tickers` 신설(seed+당일 universe 항상+누적 DB fetched_at 최신순 cap, KIS 실패 graceful) + `refresh_all_tickers` union 확장
- `collectors/market_macro.py` — `upsert_market_macro`/`_get_today_macro` 에 `distribution_count_25d`/`breadth_source` round-trip
- `core/db/schema.sql` + `core/db/connection.py` — `market_macro_snapshot` 2컬럼(v9) + 멱등 ALTER 마이그레이션
- `config/screening.yaml` — `k_below`/`below_deadband_adr`(1.0/1.0 보수적 SLOT) + `universe`(kospi 30/kosdaq 20/max 200)
- `scripts/screening_distribution.py` — 계측 보강(raw ext%/normalized + ma20-아래 포화 원인 분리) + `--k`/`--k-below`/`--deadband` 스윕 CLI
- `knowledge/canon/stock_selection/momentum_leaders/01-ma-ride-leadership.md` — **신규** 사용자 추세추종 doctrine(4일선=초강세/7일선=강세/월봉7MA=시대적 장기/시간축 매핑)
- `tests/test_universe_backfill.py`(신규 5) + `test_screening_rs.py`(+7 floor) + `test_screening_inputs.py`(MA-ride 위계) + `test_snapshot_extend_db.py`(round-trip)

## 검증 결과
- ✅ 회귀 `TESTING=1 pytest` **829 passed** (직전 813 → +16 신규), 0 깨짐
- ✅ `validate.py` 0 errors (1 warning = 기존 teams/registry.yaml, 무관)
- ✅ extension floor 라이브: broken(한미 −19.5%·아모레 −9.95%) 10.0→8.5, 얕은 눌림은 10 유지
- ✅ universe 백필 e2e: `python -m collectors.charts refresh` → chart_ohlcv 31→**71 ticker**(leading 50종 적재)
- ✅ macro round-trip UT: dist=3·breadth_source 복원 보존
- ✅ MA-ride 라이브: 삼성·SK하이닉스=riding_ma4(alignment 10.0), 한미반도체=below_ma20

## 의도적으로 안 한 것
- **k_below / MA-ride magnitude 실튜닝** — 보수적 기본(1.0/1.0)만 커밋. single-day overfitting 회피(feedback_backtest_essence), universe 다일 누적 후 `--k-below` 스윕으로 확정
- **regime 히스테리시스** — 경계서 멂(breadth 0.30, weak서 0.10 떨어짐), 급하지 않음
- **persona MA-ride 인용 명시** — stock_picker/stock_analyst persona에 위계 인용은 별 작업

## 맥락 재진입 힌트
- KIS 토큰 발급 **1분당 1회** — 같은 1분에 연속 KIS 프로세스 띄우면 둘째 토큰 실패(graceful 폴백 작동). 1825일 차트는 ~22s/ticker(페이지네이션+rate limit retry)
- "extension k 재정합"은 **오진이었음** — 다음 세션이 k 다시 쫓지 말 것. ma20-아래 floor가 정답
- 진단 스윕: `screening_distribution.py --k-below 2.5` / `--deadband 0.5`

## 다음에 이어서 할 작업 (우선순위)
1. **k_below / MA-ride magnitude 다일 튜닝** — universe 백필로 leading 일봉 누적 시작됨. 다일 분포로 `--k-below` 스윕(broken 변별폭) + MA-ride 점수 간격 확정
2. **persona MA-ride 위계 인용** — stock_picker/stock_analyst persona에 "4일선=초강세 주도주" 위계 + canon 인용 명시 (별 작업)
3. **공백 2축 데이터 확장** — buy_score A(연간 EPS 3년)·N(뉴스부) 중립 fallback 실측화

## 커밋 상태
- 이 wrap-up에서 코드+docs 1커밋 + push 예정 (사용자 요청).
