---
date: 2026-06-04
topic: persona MA-ride 주도강도 위계 인용 (stock_picker alignment stale 정정 + stock_analyst cross-ref)
status: completed
plan_file: C:\Users\HOME\.claude\plans\swirling-coalescing-pumpkin.md
---

# 2026-06-04 · persona MA-ride 위계 인용

## 배경
2026-06-02 세션에서 MA-ride 주도강도 위계(빠른 이평 탈수록 강한 주도주: 4일선=초강세 / 7일선=강세 /
월봉 7MA=시대적 장기)를 결정론 점수(`compute_alignment` 일봉 graded)와 canon
(`stock_selection/momentum_leaders/01-ma-ride-leadership.md`)로 구현했으나, **분석가 persona가 이 위계를
인용하지 않음** = LLM이 raw `daily_leadership` label을 doctrine으로 해석할 연결 부재. 더 나아가
`stock_picker/persona.md`의 alignment 축 서술이 **stale**(일봉 컴포넌트를 아직 "Vol Osc 양의 영역 = 3점"으로
적어 실제 MA-ride 구현과 불일치). **핵심 판단: canon 주입은 분석가별 `canon_categories` 필터라 stock_analyst는
`stock_selection/momentum_leaders`를 안 받음 → 직접 canon ID 인용 불가, cross-ref로만 연결.**

## 한 일
- `agents/analysts/stock_picker/persona.md` — (1) alignment 축 정의 row stale 정정: 일봉 "Vol Osc"→**MA-ride 위계** `daily_leadership`(riding_ma4=3.0 초강세/ma7=2.5/uptrend=2.0/above=1.5/below=0.0) + canon 출처 `stock_selection/momentum_leaders` + 구조⊥과열도 명시. (2) S-Score Reasoning Doctrine에 MA-ride 해석 지침(4일선/7일선=초강세/강세, 20일 정배열만=정상추세 주도주 아님, advisory override 가능). (3) Knowledge Categories momentum_leaders bullet을 `01-ma-ride-leadership.md` 활성으로 갱신
- `agents/analysts/stock_analyst/persona.md` — holding_period 매핑 맥락에 경량 cross-ref 1단락: "월봉 7MA 밀착 상승=시대적 장기 주도주"가 holding_period `monthly→장기`(WL3)+F1 broken 정합 강화. **chart_data_md [4] 월봉 7MA 출처로만 grounding**, MA-ride 결정론 점수(alignment 축)는 `stock_picker` 영역 = momentum_leaders canon ID 직접 인용 금지(부서 밖) 명시

## 검증 결과
- ✅ persona 양식 회귀 **106 passed** (`test_seed_analysts_v2` + `test_data_analysts_v2` + `test_stock_analyst_v4_persona` + `test_stock_analyst_v3_persona`, `TESTING=1`)
- ✅ `validate.py` 0 errors (1 warning = 기존 teams/registry.yaml, 무관)
- ✅ 육안: stock_picker persona에 "Vol Osc" 잔존 0 / stock_analyst에 momentum_leaders canon ID 직접 인용 0

## 의도적으로 안 한 것
- **magnitude 다일 튜닝**(RESUME Top 1) — universe 누적 후 별 작업
- **공백 2축**(RESUME Top 3) — 별 사이클
- **stock_picker의 다른 "자료 0 시드" 단정 전면 정리** — 본 작업은 momentum_leaders 카테고리만(과범위 회피)
- **manifest 수정** — stale 서술은 persona 한 곳뿐, manifest는 정상

## 맥락 재진입 힌트
- **canon 주입 = 분석가별 `canon_categories` 필터** (`core/knowledge/compose.py::load_shared_canon`). stock_picker=`stock_selection/*`, stock_analyst=`stock-analysis/*`. 부서 밖 canon은 cross-ref만, ID 직접 인용 X
- persona 양식 테스트 negation 가드는 "박종훈"·"Dalio 5단계"만 검사 → MA-ride 편집과 무관

## 다음에 이어서 할 작업 (우선순위)
1. **k_below / MA-ride magnitude 다일 튜닝** — mechanism은 라이브, magnitude(k_below/deadband 1.0/1.0, MA-ride 점수 간격)는 보수적 기본만 커밋. universe 백필로 leading 일봉 다일 누적 시작됨 → `scripts/screening_distribution.py --k-below` 스윕으로 broken 변별폭 확정 후 `config/screening.yaml` 반영
2. **공백 2축 데이터 확장** — buy_score A(연간 EPS 3년)·N(뉴스부 0시드) 중립 fallback 실측화. fundamentals 연간 3년 소스 / NEWS-SOURCE-001
3. **regime 히스테리시스 점검** — 같은 종목 strong/moderate 경계 인접 시 run간 흔들림(2026-06-02 진단, 급하지 않음)

## 커밋 상태
- 이 wrap-up에서 코드(persona 2파일)+docs 1커밋 + push 예정 (사용자 요청 "커밋 푸시").
