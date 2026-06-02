---
date: 2026-06-02
topic: 임계 캘리브레이션 — screening 분포 진단 도구 + 베이스라인 1회
status: completed
plan_file: C:\Users\HOME\.claude\plans\piped-mapping-matsumoto.md
---

# 2026-06-02 · screening 분포 진단 도구 + 베이스라인 1회

## 배경
5점수(S/T/α/buy/F)가 전부 라이브가 됐으니 다음 본질은 **"점수가 맞느냐"**(임계 캘리브레이션).
현재 모든 임계(SCREEN-RS k/adr_window/regime_weights, regime_thresholds, buyscore breakpoints)는
prism 차용 초기값 — 라이브 분포로 검증된 적 없음. 진짜 재정합은 다일 누적이 필요하므로 이번 세션은
**전제 조건인 진단 도구 + 베이스라인 1회**로 한정(사용자 범위 결정). regime 히스테리시스는 범위 밖
(분포 본 뒤 방식 결정). **핵심 판단**: RS는 풀 내 백분위라 F-Score처럼 종목 루프가 아니라
`rank_candidates` 한 번으로 풀 전체를 랭킹하는 게 맞음.

## 한 일
- `scripts/screening_distribution.py` — **신규**. `flow_distribution.py` 미러 진단 도구.
  `compute_market_macro("KOSPI")`로 라이브 regime 1콜 → `rank_candidates(pool, regime)` 한 번으로
  rs/extension/screening 산출 → 축별 분위수(p10~p90) + **regime 경계 근접도**(breadth/slope/분산일이
  임계에 얼마나 붙었나 = 히스테리시스 필요성 진단) 출력. `_quantile`/`_stats`/utf-8 보일러플레이트는
  flow_distribution에서 복제. CLI 기본 13종 바구니 + 커스텀 ticker.
- (백필, 코드 아님) 누락 11종 `chart_ohlcv` KIS 백필 — `build_chart_data`로 각 ~400봉 적재.
- (산출) `_screening_distribution.json` — n=13 베이스라인(gitignore `/_*.json`, 커밋 X).

## 검증 결과
- ✅ 회귀 `TESTING=1 pytest` **813 passed**, 0 깨짐 (신규 도구는 일회성이라 전용 UT 없음 — flow_distribution 선례)
- ✅ 베이스라인 실행 2회 (1차 n=2 → 데이터 공백 발견 → 백필 → 2차 n=13 전종목 랭킹)
- ✅ `validate.py` 영향 없음(신규 scripts/ 파일, generates 무관)

## 베이스라인이 드러낸 것 (다음 캘리브레이션 입력)
- **rs_score**: p10=1.2 / median=5.0 / p90=8.8 — ✅ 건강(백분위 정규화가 0~10 고르게 분산)
- **extension_score**: p25=8.0 / **median=10.0 / p75=p90=max=10.0** — ⚠️ **천장 포화**. 13종 중 7+가 10.0.
  공식 `clamp(10 - k·extension/ADR)` 에서 ma20 아래·근처면 음수→10 clamp. **`k=1.0`이 약해 과열 페널티가
  거의 안 걸림 = 변별 상실**. 재정합 1순위.
- **screening_score**: p10=5.1 / median=7.0 / max=8.0 — 포화된 ext가 합성을 4.5~8.0으로 압축
- **regime**: moderate_bull (breadth 0.2988 ≪ breadth_weak 0.40 → narrow breadth 강등 발화).
  경계서 충분히 멀어 **오늘 진동 위험 낮음** → 히스테리시스 급하지 않음 확인.

## 의도적으로 안 한 것
- regime 히스테리시스 코드 — 분포상 경계서 멂(급하지 않음). 다일 누적 후 방식 결정(입력 스무딩/sticky/데드밴드)
- 임계 실제 재정합 — 단일 분포로는 부족(다일 필요). 단 **extension k 상향**이 첫 후보로 명확해짐
- 공백 2축(A 연간 EPS / N 뉴스부) — 별 Top 3 항목

## 기술 부채/미완
- **`chart_ohlcv` 시드 공백**: `_seed_tickers()`가 지수+14섹터ETF만 → leading 종목은 분석될 때만 적재.
  스크리닝 universe 백필 메커니즘 부재(이번엔 수동 build_chart_data로 13종만 메움). 캘리브레이션을
  다일 돌리려면 universe refresh 필요.
- **macro DB 캐시 충실도**: `_get_today_macro` 복원 시 `breadth_source`/`distribution_count_25d` 누락
  (1차 run dist=3·source=computed → 2차 run dist=0·breadth_source=None·source=db). regime 작업 때 같이.

## 다음에 이어서 할 작업 (우선순위)
1. **extension k 재정합 (천장 포화 해소)** — `config/screening.yaml::k` 1.0 상향 후보. 베이스라인이
   extension median=10.0 포화 실증. 다종목·다일 분포로 ext가 0~10 변별 회복하는 k 탐색(도구 재실행으로 즉시 검증)
2. **스크리닝 universe 백필 메커니즘** — `_seed_tickers()` 확장 or 별도 universe refresh cron으로 leading
   종목 일봉을 chart_ohlcv에 상시 적재. 캘리브레이션 다일 누적의 전제
3. **공백 2축 데이터 확장** — buy_score A(연간 EPS 3년)·N 뉴스부 중립 fallback 실측화

## 맥락 재진입 힌트
- 도구 실행: `uv run python scripts/screening_distribution.py` (기본 13종) / `... 005930 000660`(커스텀)
- RS는 풀 상대 백분위 → 풀 크기·구성이 점수에 직접 영향(절대 점수 아님). 베이스라인은 leading 13종 풀 기준
- regime 경계 근접도 = 히스테리시스 필요성 1차 게이지. 오늘은 breadth가 weak에서 0.10 떨어져 안전

## 커밋 상태
- 아직 안 됨. 신규 `scripts/screening_distribution.py` + wrap-up docs를 이 wrap-up에서 1커밋 예정.
  `_screening_distribution.json`은 gitignore.
