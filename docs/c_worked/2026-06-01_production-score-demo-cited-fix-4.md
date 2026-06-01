---
date: 2026-06-01
topic: 점수 라이브 production 시연(MS1/MS2) + cited_scores 누수 수정 (같은 날 4번째 세션)
status: completed
plan_file: C:\Users\HOME\.claude\plans\binary-waddling-axolotl.md
---

# 2026-06-01 · production 점수 시연(MS1/MS2) + cited_scores 누수 수정

## 배경
5점수(S/T/α/buy/F) 배선 완성 직후, 실 LLM이 그 점수를 받아 권고까지 가는 end-to-end를
한 번도 시연 안 함(결정론 collector smoke까지만). MS1/MS2 = "점수가 실제로 흐른다"를 눈으로
확인하는 시점. 핵심 판단: **production 시연은 production-chat 엔드포인트(`POST /api/chat/production`)
구동 = 코드 0 변경 검증** — `core/intent/router.py`가 ticker를 분석가 prefetch에 전달하고
prefetch raw를 전략가에 직접 주입(옵션 A, DB 우회). 사용자 정정으로 **provider=gemini**(실제 배포
기본 모델, claude_code는 이상화 경로 → 누수 은폐). 시연 중 발견한 누수를 같은 세션에 수정+검증까지.

## 한 일
### 시연 (코드 0 변경 — 순수 검증)
- production-chat 4회 구동(실 Gemini, `mock=False`): Track B(swing) 005930 / Track A(long) 005930 /
  005930 재검증 / NAVER(035420) 변별. 산출물 `data/_demo_*.json` 4건(비커밋 scratch).
- **인프라 검증 통과**: ticker 해석·점수 실측(005930 S=8.5~9.5/buy=6.0~7.0)·prefetch 5/5 published·
  formatter 자연어(코드라벨 0)·공백 2축(A 연간EPS·N 뉴스부) 정직 중립·라우팅 정확(swing→track_b 위임).
- **발견된 누수**: track_b가 stock_picker 텍스트의 buy_score=6.0을 못 읽고 `cited_scores.buy_score=null`
  + "미발현" 처리. 원인 = 전략가가 점수를 분석가 **자유텍스트에서 LLM 재추출**(Gemini Flash 비결정).
  대조: track_a 호출은 S=8.5/F=7 정확 인용 → 인프라 아닌 LLM 추출 신뢰성 문제.

### 누수 수정 (TDD)
- `core/strategist/run_strategist.py` — `render_prefetched_analyst_outputs`에 `_deterministic_scores_from_metadata`
  헬퍼 + `_ADVISORY_SCORE_FIELDS`(advisory_s/buy/t/f_score → cited_scores 키) 추가. 각 분석가 metadata의
  결정론 점수를 **"결정론 점수(권위값)" 줄로 구조 직접 주입** + cited_scores 규칙 헤더("그대로 인용,
  추정 금지"). α는 제외(multi-timeframe, 단일 collapse 없음 → LLM 해석 유지). 빈 응답이어도 점수 살림.
- `tests/test_run_strategist.py` — render_prefetched 결정론 점수 주입 테스트 +4(노출/빈텍스트방어/점수없음/α제외).

## 검증 결과
- ✅ pytest **804 → 808 (+4, 회귀 0, TESTING=1)**. validate.py **0 errors**.
- ✅ **라이브 before/after(005930 track_b)**: 수정 전 buy_score=null"미발현" → 수정 후 **buy_score=7.0·s_score=9.5·f_score=3.0** 정확 인용.
- ✅ **수정 일반화(NAVER 035420)**: metadata(s=3.5/buy=5.5) = cited_scores(3.5/5.5) 정확 일치, 누수 0.
- ✅ **종목 변별**: 삼성 S=9.5/buy=7.0(반도체 주도주) vs NAVER S=3.5/buy=5.5(비주도) — 뭉개지지 않음.

## 의도적으로 안 한 것
- **CLI --ticker 추가 보류** — ask_analyst/chat_analyst가 target_ticker 미전달이라 단일 분석가 호출로는
  [5d]/[5e] 안 켜짐. R&D 편의용·시연 필수 아님 → 백로그(사용자 "순수 검증만" 확정).
- **DB-read 경로(render_analyst_scores_block) 미수정** — production 경로는 prefetch라 우선순위 밖.

## 기술 부채/미완
- **시나리오2 prefetch에 trader 미포함** → Track B여도 T-Score 항상 null(`_resolve_analyst_ids_for_scenario`
  축약 매핑). swing 권고에 T-Score 필요하면 시나리오 라우팅에 trader 추가 검토(별 작업).
- **regime run간 흔들림** — 같은 005930이 run1=strong_bull / run2=moderate_bull(narrow breadth 경계
  인접). classify_market_regime 경계 히스테리시스/스냅샷 타이밍 점검 후보.
- 임계 production 캘리브레이션(RS·regime·buyscore)·공백 2축(A 연간EPS·N 뉴스부)은 여전히 미완(직전 세션 부채 유지).

## 맥락 재진입 힌트
- production 시연 = `POST /api/chat/production` (CLI 없음, Invoke-RestMethod/httpx 직접). provider=gemini가 실 배포 경로.
- cited_scores 누수 패턴 = 결정론 점수가 metadata에 있는데 LLM이 자유텍스트 재추출 → 구조 주입으로 해소(점수=결정론/해석=LLM 철학 정합, [[feedback_score_collapse_advisory]]).
- 점수 주입 위치 = render_prefetched_analyst_outputs (옵션 A prefetch 경로). α는 의도적 제외.

## 다음에 이어서 할 작업 (우선순위)
1. **임계 production 캘리브레이션** — RS R1/R2/R3 + regime_thresholds + buyscore breakpoints 전부 초기값.
   `screening_distribution.py` 신규(flow_distribution 미러) + leading 종목 분포 → config 1차 정합(다일 누적).
2. **공백 2축 데이터 확장** — buy_score A(연간 EPS 3년)·N 뉴스부(0시드) 중립 fallback 실측화.
   fundamentals 연간 3년 소스 / NEWS-SOURCE-001(news_curator 신제품 판정).
3. **시나리오 라우팅 보강** — 시나리오2(신규 진입) Track B인데 trader 미포함 → T-Score 항상 null.
   `config/scenario_analyst_routing.yaml`에 swing 시 trader 추가 + regime 경계 히스테리시스.

## 커밋 상태
- 코드(`run_strategist.py`+test) + wrap-up docs를 이 세션에서 커밋·push 예정(사용자 요청, 솔로 main 직접).
- 산출물 `data/_demo_*.json` 4건은 비커밋 scratch.
