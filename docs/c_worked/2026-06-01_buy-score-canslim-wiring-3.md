---
date: 2026-06-01
topic: buy_score CAN SLIM 7축 배선 — 5점수 체계 완성 (같은 날 3번째 세션, 자율 진행)
status: completed
plan_file: C:\Users\HOME\.claude\plans\zesty-strolling-sunbeam.md
---

# 2026-06-01 · buy_score CAN SLIM 7축 배선 (5점수 체계 완성)

## 배경
5점수(S/T/α/buy/F) 중 S·T·α·F 실측 완결 후 마지막 빈칸 buy_score 배선. CAN SLIM 7축 중 S/I/M이
cross-agent라 소싱 경계 결정 필요 → **사용자 확정: collector 직접 호출 + M regime 분류기 신설**(team_outputs
DB read 기각, 단일 호출 시 stale). 사용자 추가 질문(시총 상위 쏠림 narrow breadth 장세 분류) → **옵션 3 확정**:
결정론은 moderate_bull 보수 라벨만, "구조적 주도 vs 천장 디버전스" 판단은 breadth·분산일 원시값 보고 LLM. 사용자
취침 중 "하는데까지 해봐" → 단계 1·2 전체 자율 완수.

## 한 일
### 단계 1 — classify_market_regime (커밋 `1e7ce98`)
- `collectors/market_macro.py` — `classify_market_regime(macro, thresholds)` 4축(position·trend·ma20기울기·breadth·분산일)→6단계 결정론 + `regime_to_score`(M축). **예측 X, 현재 상태 라벨링.** narrow breadth(<0.40)→moderate_bull 강등.
- `config/screening.yaml` — `regime_thresholds`(parabolic 기울기·breadth 경계·분산일 천장, SLOT) + `collectors/screening.py:get_regime_thresholds()`.
- `core/inference/run_analyst.py` — `_regime_from_snapshot` helper + S-Score hook이 실 regime을 `rank_candidates`에 전달(현재 None→균등 활성).
- `tests/test_market_macro.py` — regime 6단계 + narrow breadth 강등 + parabolic 분산일 억제 +13.

### 단계 2 — buy_score 입력 collector (커밋 `e5bed44`)
- `collectors/buy_score_inputs.py` 신규 — `BuyScoreInputs` + `compute_eps_yoy`/`compute_institution_ratio`(순수) + `build_buy_score_inputs`(7축 graceful 중립) + `render_buy_score_inputs_md`([5e], narrow breadth 맥락 노출).
- `config/score_inputs.yaml` — `buyscore` C/N/I breakpoints(S=flow 재사용·A 공백·L=screening·M=regime).
- `core/inference/run_analyst.py` — `reads_buyscore` + `_maybe_build_buy_score_inputs_md` hook(run_analyst·stream 양쪽) + metadata.
- `core/knowledge/compose.py` — `buy_score_inputs_md` kwarg + `[6e]` 블록.
- `agents/analysts/stock_picker/{manifest.yaml,persona.md}` — `reads_buyscore: true` + 7축 산출 소스 정합.
- `docs/specs/INFRA-SCORE-INPUTS-001` v2→v3(buy_score_inputs generates + market_macro modifies).
- `tests/{test_buy_score_inputs.py(15),test_run_analyst_score_inputs.py(+3)}`.

## 검증 결과
- ✅ 테스트 **769 → 800 (+31, 회귀 0, TESTING=1)**. validate.py **0 errors**.
- ✅ 실데이터 smoke(005930 + 합성 macro breadth 0.35): **regime=moderate_bull(narrow breadth 강등 정확)** / N=9.0(52주 신고가 실측)·S=3.5·I=7.0(flow stock_kis 실측)·L=7.5(screening)·M=7.0(regime) / C·A=5.0(EPS 공백 중립) → advisory_buy_score 6.5. **[5e] 블록 narrow breadth 디버전스 경고 렌더 확인.**

## 의도적으로 안 한 것
- **A 축(연간 EPS 3년) 실측 보류** — fundamentals 5분기(~1.25년)만 → 중립 5.0. KIS/별도 소스 확장은 후속 SLOT.
- **N 뉴스부(신제품) 보류** — news_curator 0시드 → 52주 신고가만. NEWS-SOURCE-001 후속.
- **team_outputs DB read 기각** — 단일 stock_picker 호출 시 분석가 발행물 stale/부재 → collector 직접 호출 채택.
- **regime/buyscore 임계 production 튜닝 보류** — 초기값 + config 외부화. 누적 후 screening_distribution 패턴.

## 기술 부채/미완
- **5점수 체계 배선은 완성**, 잔여는 전부 *튜닝·데이터 확장*: A축 EPS 3년 소스 / N 뉴스부 / regime·buyscore·RS 임계 production 캘리브레이션.
- buy_score collector가 단일 호출에 fundamentals(yfinance)+flow(KIS)+screening(DB)+regime 다중 호출 → 지연 가능(graceful, 비차단). 캐시는 각 collector 자체 TTL 의존.

## 맥락 재진입 힌트
- buy_score 7축 = C(EPS YoY=fundamentals)·A(공백 중립)·N(52주=charts)·S(flow inflow)·L(screening_score)·I(flow 기관비중)·M(classify_market_regime). cross-agent(S/I/M)=collector 직접 호출(분석가 import 아님).
- classify_market_regime = 현재 상태 분류(예측 X). narrow breadth→moderate_bull 보수, 해석은 LLM(breadth·분산일 [5e] 노출).
- regime이 이제 rank_candidates(regime=)에도 흘러 SCREEN-RS 가중 활성(구 None→균등).
- 5점수 배선 패턴 = α/flow/screening_inputs mirror 3단(compute 순수→build async graceful→render+hook). [5e]까지 5블록(α/T/F/S/buy).

## 다음에 이어서 할 작업 (우선순위)
1. **production 검증 + 점수 라이브 시연** — 5점수 모두 라이브 도달. `swing:`/`long:` 호출로 stock_picker가 [5d]+[5e] 받아 S·buy 발행하는 풀세트 시연(MS1/MS2). cited_scores 풍부도 확인.
2. **RS·regime·buyscore 임계 production 캘리브레이션** — `screening_distribution.py` 신규(flow_distribution 미러) + leading 종목 분포 → config R1/R2 + regime_thresholds 1차 정합(다일 누적).
3. **A축 EPS 3년 + N 뉴스부 데이터 확장** — fundamentals 연간 3년(KIS/별도 소스) / NEWS-SOURCE-001(신제품 판정). 공백 2축 실측화.

## 커밋 상태
- 코드 2 커밋(`1e7ce98` regime + `e5bed44` buy_score) main 직접 push 완료(`3486d1d..e5bed44`). wrap-up docs 별도 커밋 예정. 솔로.
