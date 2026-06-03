---
date: 2026-06-04
topic: buy_score A축 배선 — 연간 EPS YoY 실측 (yfinance income_stmt, 같은 날 2번째 세션)
status: completed
plan_file: C:\Users\HOME\.claude\plans\swirling-coalescing-pumpkin.md
---

# 2026-06-04 · buy_score A축 배선 (연간 EPS YoY 실측)

## 배경
persona MA-ride 인용(1세션) 후 "다음 뭐?" → Top 1(magnitude 다일 튜닝)이 **단일-데이터로 막힘** 발견
(universe 백필이 2026-06-02 단 하루만 적재, 이후 cron 미작동). single-day overfitting 회피로 미룸.
사용자 결정 = **buy_score A축(연간 EPS) 실측화 + universe refresh 병행**. 세션 중 사용자가 "과잉설계 아니냐"
점검 → 정직 평가(A축 작업 자체는 소규모 plumbing, over-design 아님 / 다만 입력 미세튜닝이 수 세션 누적은
사실) 후 사용자 "배선부터 다 끝내야겠어"로 진행 결정. **핵심 판단: A점수=최근 연간 EPS YoY breakpoint
매핑(C의 연간판) + 3년 시계열 raw 노출 → 가속·일관성 고차 판단은 LLM(brittle O'Neil 공식 안 박음).**

## 한 일
- `connectors/yfinance/client.py` — `fetch_annual`(income_stmt/financials "Diluted EPS" 4년 recent-first, API drift 대응) + `fetch_full` 결합
- `collectors/fundamentals.py` — `Fundamentals.annual_eps/annual_labels`(기본값) + DB `quarterly_data` JSON round-trip(스키마 변경 0) + get_fundamentals populate
- `collectors/buy_score_inputs.py` — `compute_annual_eps_yoy` 순수 함수(≥3년, 최근 연간 YoY%) + A축 배선(중립 5.0 탈피, axis_source) + BuyScoreInputs `annual_eps_yoy_pct`/`annual_eps` 필드 + render md A row(YoY + 3년 시계열)
- `config/score_inputs.yaml` — `buyscore.a_annual_eps_yoy` breakpoints(+25%→10·0%→3·음수→0, C 앵커 미러)
- `agents/analysts/stock_picker/{persona.md,manifest.yaml}` + `docs/specs/INFRA-SCORE-INPUTS-001-*.md` — A축 "공백 중립"→연간 EPS 실측 갱신
- `tests/{test_buy_score_inputs,test_fundamentals,test_run_analyst_score_inputs}.py` — +8 테스트(순수 7 + A축 라이브 1 + DB round-trip 보강)

## 검증 결과
- ✅ 회귀 `TESTING=1 pytest` **837 passed**(829→+8, 0 깨짐) / `validate.py` 0 errors
- ✅ 라이브 yfinance: 005930 `fetch_annual` 실파싱 = [6603(2025)/4950(2024)/2131(2023)/8057(2022)]
- ✅ 라이브 A축 end-to-end: 005930 A **5.0→10.0** (연간 EPS YoY +33.4%), axis_source=fundamentals(yfinance)

## 의도적으로 안 한 것
- **N 뉴스부(신제품) 절반** — NEWS-SOURCE-001 SPEC 설계 프로젝트(Perplexity MCP·유튜브·시간축), "배선" 아님. 별 `/spec-interview`
- **stock_analyst fundamental_data_md에 연간 EPS 노출** — A축은 stock_picker buy_score 영역, scope 회피
- **yfinance _fetch_annual_sync 단위 테스트** — 기존 컨벤션(boundary mock)대로 round-trip + 라이브 스모크로 커버
- **magnitude 다일 튜닝(Top 1)** — universe 단일-데이터로 여전히 막힘. 누적 더 필요

## 맥락 재진입 힌트
- **buy_score 7축 중 6.5축 라이브**: C·A·N(52주)·S·L·I·M 전부 실측. 남은 공백 = N 뉴스부(신제품) 절반뿐(SPEC 게이트)
- **universe 누적은 dev에서 자기치유 안 됨**: `refresh_all_tickers` cron(`0 18 * * 1-5`)이 서버 떠야 돎. 다일 튜닝은 매일 장후 수동 `python -m collectors.charts refresh` 또는 서버 상주 필요. 본 세션 중 1회 수동 refresh 띄움(장전이라 6/3 봉 갭 메움 위주)
- 연간 EPS YoY는 분기 C와 같은 앵커지만 계절성 평탄화. 가속/3년 일관성은 md 원시 시계열로 LLM 판단(advisory)

## 다음에 이어서 할 작업 (우선순위)
1. **k_below / MA-ride magnitude 다일 튜닝** — universe 다일 누적이 전제(현재 단일일). 매일 장후 refresh로 며칠 쌓은 뒤 `screening_distribution.py --k-below` 스윕. **누적 전제부터 점검**
2. **N 뉴스부 = NEWS-SOURCE-001 SPEC 착수** — buy_score 마지막 공백. Perplexity MCP + 유튜브 + 시간축 + 학습부 DB. `/spec-interview`. 메모리 [[project_news_source_decision]]
3. **end-to-end 가이드 품질 검증 / MS4 적중률 루프** — 입력 배관 충분히 좋음(6.5/7축), 본질(회사처럼 작동·적중률 고도화)로 한 단계 위 레버. 사용자 의향 확인 필요

## 커밋 상태
- A축 코드 10파일 = **b84af9e** (이미 커밋+push 완료, 본 세션 중)
- 이 wrap-up docs = 별도 커밋 + push 예정
