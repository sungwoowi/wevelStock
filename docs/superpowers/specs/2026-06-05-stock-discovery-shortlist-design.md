# 종목 발굴 경로 (Discovery Shortlist) — 설계

_2026-06-05 · PRODUCTION-UX-001 보강 · 가이드 품질 검증 #1 결함 해소_

## 문제
production-chat에서 "단타 종목 있어?" / "주도주 추천해줘"처럼 **종목이 지정되지 않은 추천 질의**는
`target_ticker_absent`로 후보 0개를 반환한다. 스크리닝 인프라(`rank_candidates`)는 *주어진 한 종목*의
L축 랭킹용으로만 쓰이고, *추천 리스트 생성*엔 라우팅이 안 붙어 있다. 사용자 핵심 시나리오(추천)가 비어 있음.

## 트리거
`route ∈ {track_a, track_b, both}` **AND** `classification.ticker is None` → **발굴 모드**.
("지금 시장 어때?"는 analyst_direct라 무관. 단타/주도주 추천만 발동.)

## 흐름 (기존 조각 재사용)
```
build_market_snapshot() → _leading_pool_tickers(snapshot)        # 풀 (비면 universe fallback)
  → _regime_from_snapshot                                         # regime
  → rank_candidates(pool, regime)                                 # 결정론 랭킹 (기존)
  → 상위 N(=5) + 종목명 → render_screening_shortlist_md           # 신규 렌더
  → stock_picker sub-task 프롬프트에 컨텍스트로 임베드            # 라우터 주입
  → stock_picker(LLM)가 후보 큐레이션·발행 → 전략가/포맷터 종합
```

## 설계 판단
- **선정 권위 = stock_picker(종목선정가)**: 라우터는 결정론 랭킹 테이블만 만들고, 큐레이션·근거는
  stock_picker LLM이. 라우터에 선정 로직을 박지 않음(도메인 경계 유지).
- **랭킹은 결정론**: `rank_candidates` screening_score(RS+과열도). 이미 검증된 순수 함수.
- **풀 fallback**: snapshot 주도주 비면 universe(`chart_ohlcv` 거래대금 상위 ticker)로.
- **discovery 모드 stock_picker**: target_ticker=None이라 per-ticker 점수 hook은 자연히 비활성
  (target_ticker_absent) — 대신 셔틀리스트 md가 입력. stock_picker는 "발굴 후보 발행"이 본 직무.

## 건드릴 파일
- `collectors/screening.py` — `render_screening_shortlist_md(ranked, names, *, top_n, track)` 신규(순수)
- `core/inference/run_analyst.py` — `build_discovery_shortlist_md(*, track, top_n=5)` 신규
  (snapshot 빌드 → pool(+universe fallback) → regime → rank_candidates → 종목명 resolve → render)
- `core/intent/router.py` — `_prefetch_analysts_for_tracks`에 발굴 조건 감지 + 셔틀리스트 빌드 +
  stock_picker sub-task 프롬프트에 임베드
- `config/analyst_subtasks.yaml` — stock_picker 발굴 모드 directive(있으면 보강)
- 테스트 — 발굴 트리거 / 랭킹→md 렌더 / 라우터 e2e(결정론, LLM mock)

## 범위 밖 (YAGNI)
- #1 자동 심화분석(상위 1종 풀분석) — 후속
- 종목 비교(#2) / formatter 근거축 가변(#3) — 별건
- 백테스팅 cutoff(이미 rank_candidates가 지원, 발굴 진입점은 라이브만)

## 검증
- UT: render_screening_shortlist_md / build_discovery_shortlist_md(snapshot mock) / 라우터 발굴 트리거
- 라이브: "단타 종목 있어?" production-chat → 후보 N종 shortlist 반환(0개 아님), is_mock=False
