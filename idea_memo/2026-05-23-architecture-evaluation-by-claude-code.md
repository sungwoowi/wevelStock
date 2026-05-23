---
date: 2026-05-23
author: Claude Code (sungwoowi 의 엔지니어링 페어)
target_reviewer: chat Claude Opus (R&D 회장)
status: 가능성 탐색 메모 (결단 X)
purpose: 9 분석가 multi-agent vs 단일 임원 LLM vs 하이브리드 의 객관 평가 + chat Opus 핑퐁용
model_constraint: 사용자 명시 — Anthropic Opus API 키 없음. PoC 임원 LLM = **Gemini 2.5 Pro / Flash** (메모리 `feedback_llm_tier_strategy` 정합)
---

# wevelStock 아키텍처 본질 재평가 — 9 분석가 multi-agent 의 가능성 탐색

> **이 메모는 결단을 위한 게 아닙니다.** 사용자가 던진 본질 의문에 대한 객관 평가 + chat Claude Opus 핑퐁 자료. PoC 는 별도 feature 브랜치에서 진행 예정.

---

## 1. 사용자가 던진 본질 의문 (원문)

> *"본질은 사실 주식 예측과 실제로 돈을 벌 수 있는 매매 퀄리티다. 이 관점에서 9분석가 체계가 데이터를 통합으로 받고 9분석가를 하나의 llm으로 9분석가 효과를 낼 수 있느냐 그게 실전적으로 궁금했다.*
>
> *왜냐면 분석가 한명한명 응답이 사실 점수화 되어 나오는데 그 응답에 단촐하고 시장 섹터 종목 등의 흐름과 시장 평가의 맥락이 자연어에서 드러나지 않는점을 발견했다. 3줄 요약에서 사 말아 홀딩 분할매수 매도 등 관점도 빈약하고 때론 수급을 우선해야할 수도 있고 때론 펀더멘탈 때론 차트 위치가 중요할 때도 있다. 이런 통찰적인 총괄적인 분석의 깊이가 현재로선 부족해 보인다.*
>
> *페르소나가 9개 이니 9개 응답을 모두 취합하려면 간추릴 수밖에 없고 그 와중에 맥락은 생략되는 것 같기도 하다. 그럼 전략가 llm은 단촐한 프롬프트를 되게 기계적인 정량 평가만으로 단정 짓게 되고 사실 멍청한 임원으로 보인다.*
>
> *실전에서 임원은 분석가 9에게 일을 위임하지만 세부적인 데이터는 몰라도 그간 경험과 경륜으로 흐름은 다 알고 있고 분석가에게 이게 맞아? 라며 반문도 할 수 있어야 하는데 현재는 그게 없다."*

---

## 2. 사용자가 발견한 결함 6건

| # | 결함 | 발현 사례 |
|---|---|---|
| 1 | 분석가 응답이 점수화 위주, 시장·섹터·종목 흐름 자연어 맥락 X | 9 분석가 cited 풀이 양식이 정량 점수 + 명제 ID 위주, 자연어 통찰 빈약 |
| 2 | 3줄 요약에서 "사/말/홀/분/매" 관점 빈약 | formatter 자연어 압축 시 정량 종합 verdict 만 노출 |
| 3 | 상황별 가중치 차별 안 됨 (수급·펀더·차트) | Track A/B persona 의 가중치 표 = 결정론 고정. regime 별 자유 가중치 X |
| 4 | 9 응답 취합 시 맥락 생략 | 종합 verdict 산출 시 정량 anchor 중심, 자연어 reasoning 소실 |
| 5 | 전략가 = 멍청한 임원 (정량 평가만, 통찰 X) | Track A/B persona 의 알고리즘이 진입 조건 매칭 + 가중치 합산. canon 인용 자연어 통찰 doctrine 약함 |
| 6 | 임원이 분석가에게 "이게 맞아?" 반문 X | 1-shot dispatch + 종합. 2nd round 분석가 재호출 메커니즘 없음 |

→ **본질**: 결함 #1·#2·#4 = **9 분석가 cited 자연어 풀이 양식 자체** 의 문제. 결함 #3·#5·#6 = **전략가 doctrine** 의 문제.

---

## 2.5 사용자가 가져온 prism 실 응답 샘플 (2026-05-23, 6번째 세션 중)

사용자가 prism-insight 텔레그램 봇에 **삼성전자 (005930)** 직접 질의 → 응답 2건 (분석 리포트 + 후속 목표가) 가져옴. 사용자 평가:

> *"환각이 있을 수 있지만 내용은 풍부하다. 분석가들의 코멘트를 모아보기 한 거 같다.*
>
> *나랑 종목을 보는 관점은 다르지만, 자연어가 현재 우린 되게 퀄리티가 떨어진다. **위 수준 정도가 되면 좋겠다**."*

→ **prism 응답 수준 = wevelStock 의 응답 품질 KPI**. 본 메모 옵션 결단의 결정적 기준.

### 2.5.1 prism 응답에서 발견한 5 패턴 (= wevelStock 이 도달해야 할 수준)

1. **5-layer 자연어 chain** = 데이터 (가격·거래량·수급) → 자연어 풀이 ("외국인 빠지고 개인이 받은 구조") → 의미 해석 ("단기 수급 다소 불안하지만 기관이 받쳐주고 있다") → 시나리오 3 (긍정·중립·부정 + 각 가격 구간) → 구체 권고 ("280,000원 이탈 시 손절 or 비중 축소")
2. **시나리오 3** = 긍정 (300,000원 돌파 → 310-320,000 목표) / 중립 (박스권 → 평단 낮추기) / 부정 (280,000 이탈 → 손절). 사용자 입장 즉시 행동 가능
3. **"솔직히 말하면" 임원 톤** + 정량 (PER 44.28 / EPS 6,605 / PBR 4.57) + 자연어 동시 grounding. 똑똑한 임원 느낌 강함
4. **상황별 가중치 통합** = "외국인 매도 + 개인 매수 + 기관 5월 매수 전환" 을 **하나의 자연어로 통합** ("기관이 받쳐주고 있다는 게 중요한 포인트")
5. **컨텍스트 이어진 후속 질문** = 첫 응답의 "300,000원 저항" → 후속 답변 "300,000원 확실히 돌파 및 안착 조건". 세션 기억 + 일관성

### 2.5.2 prism 환각 사례 (사용자 인지 정합)

- "5월 6일 거래량 5,309만주" → 실 사실 검증 필요. **wevelStock 가 옵션 2 의 9 분석가 정량 anchor 를 강하게 유지하면 같은 환각 차단 가능** (정량 점수가 raw 데이터 검증 layer 역할)
- "삼성전자 반도체 사이클 피크 PER 25~35배" → 정성적 일반화. **wevelStock 의 wealth_strategist canon (박종훈 framework) 으로 grounding 가능**
- 사용자도 "환각 있을 수 있지만" 인정 = trade-off 수용. wevelStock 의 cited grounding 우위는 보존 가치

### 2.5.3 wevelStock 현재 응답이 prism 수준에 못 미치는 본질 3가지

1. **9 분석가 cited 자연어 풀이가 임원 통찰의 자리 차지** = 정량 ID 인용 (`cited: [F1, F2]`) 이 자연어 흐름을 끊음. 임원이 통합 자연어 추론할 공간 부재
2. **시나리오 3 같은 "사용자 입장 행동 가이드" doctrine 부재** = Track A/B persona 가 단일 verdict (long/swing/중립) 만 발행, prism 의 시나리오 3 + 가격 구간 + 행동 권고 doctrine 없음
3. **종합 시 압축 알고리즘이 정량 가중치 합산** = 임원이 "지금 상황에서는 수급이 우선이다 (이 종목·이 시장 regime 에서는)" 같은 상황별 통합 추론 X. 가중치 표 매칭 + 합산 정량 알고리즘

### 2.5.4 옵션별 prism 수준 도달 가능성 (재평가)

| 옵션 | prism 5 패턴 도달 가능성 | 비고 |
|---|---|---|
| 옵션 1 (단일 임원) | ✅ 자연어 chain 완벽 / ⚠️ wevelStock 고유 grounding (α/7계명/위계) 약화 | prism 만큼 환각 위험 |
| 옵션 2 (하이브리드) ⭐ | ✅ **모두 도달 + 9 분석가 정량 anchor 로 환각 억제** | 본 메모 추천 결정 |
| 옵션 3 (현재 + 임원 deepening) | 🟡 임원 layer 추가는 가능하나 9 분석가 cited 자연어가 무거워서 5-layer chain 어려움 | 부분 도달 |

→ **prism 응답 분석 결과 옵션 2 의 가치 결정적으로 강해짐**. 본 메모 § 6 추천 정정:

**§ 6 추천 정정 (prism 실 응답 반영)**: 옵션 3 단계적 접근 → **옵션 2 (하이브리드) 직진**. prism 응답 수준 도달이 사용자 본질 (자연어 퀄리티) 의 명시 KPI. 옵션 3 으로는 부분 도달만 가능 (9 분석가 cited 자연어 풀이가 5-layer chain 차단).

PoC scope 재조정:
- **최소 PoC** = 임원 페르소나 1개 (prism Investment Strategist 패턴 차용) + Track A + 005930 단일 종목 + **prism 응답 5 패턴 모두 시연** (5-layer chain + 시나리오 3 + 솔직 톤 + 상황별 가중치 통합 + 컨텍스트 이어짐)
- **검증 기준 = prism 응답과 1:1 비교** (005930 같은 종목, 같은 질문). 사용자 평가 "위 수준 이상" 받으면 옵션 2 확정, 못 미치면 9 분석가 cited 자연어 풀이 슬림화까지 escalation

---

## 3. prism-insight `/evaluate` 실 패턴 확인 (WebFetch 결과)

### 3.1 prism 도 13+ agent multi-agent (단일 LLM 아님)

GitHub `dragon1086/prism-insight` 의 `docs/CLAUDE_AGENTS.md` 원문:

> "13+ specialized AI agents collaborate to detect surge stocks, generate analyst-grade reports, and execute trades automatically."

5 팀 구성:
- **Macro Team** (1 agent) — Market regime, sector rotation, risk events
- **Analysis Team** (6 agent, GPT-5) — Technical / Trading Flow / Financial / Industry / Information / Market
- **Strategy Team** (1 agent) — "Synthesize all analyses into actionable strategy"
- **Communication Team** (3 agent) — Summary Optimizer + Quality Evaluator + Translation
- **Trading Simulation Team** (3 agent, GPT-5) — Buy / Sell / Trading Journal
- **User Consultation Team** (2 agent, Claude Sonnet 4.5)

### 3.2 실행 패턴 = Sequential (rate limit friendly)

원문: *"Sequential execution (rate limit friendly) → 각 섹션마다 agent 순차 실행 → 모든 section_reports 수집 → Investment Strategist가 통합"*

→ **wevelStock 의 9 분석가 dispatch (병렬 시도) + Track A/B 종합 + formatter 압축 = prism 의 6 agent sequential + Strategist 통합 + Communication 압축 과 본질 동형**.

### 3.3 prism 의 환각 가드 = Quality Evaluator 반복 루프

원문: *"Quality Evaluator: Checks accuracy, clarity, format compliance, hallucination detection. Iterative improvement loop until EXCELLENT rating."*

→ **wevelStock 에는 없는 layer**. 종합 응답 → Quality Evaluator → 재호출 루프 = production 응답 품질 보증.

### 3.4 prism 이 "빠르다" 의 진짜 본질 (단일 LLM 아님)

사용자가 prism 을 "빠르고 환각 있지만 참고 가치 충분" 으로 평가한 이유 = 단일 LLM 이 아니라 **다음 4 요인의 합**:

1. **GPT-5 가 latency 적게 응답** (Anthropic Sonnet 4.6 대비 빠른 first-token)
2. **Communication Team 의 Summary Optimizer** = 텔레그램 400자 이내 강제 압축 → 정보량 자체가 적음
3. **MCP 도구로 raw 데이터 직접 grounding** (firecrawl, perplexity, kospi_kosdaq) → RAG canon 보다 직접적, token 적음
4. **Market Analysis 캐싱** + agent 단위 캐싱 → 반복 호출 줄임

→ **wevelStock 가 9 분석가 폐기 X 한 채로 위 4 요인 차용 가능**. prism = 동일 multi-agent 패턴 + 속도·UX 최적화.

---

## 4. 3 옵션 trade-off

### 옵션 1 — 단일 똑똑한 임원 LLM (9 분석가 폐기)

**구조**: **Gemini 2.5 Pro / Flash (사용자 명시 — Opus API 키 없음)** 또는 Sonnet 4.6 단일 LLM 이 모든 raw 데이터 + 9 canon + scoring 결정론 점수 받아서 cited 자연어 통합 추론.

| 차원 | 평가 |
|---|---|
| 사용자 본질 (매매 퀄리티) | ✅ 임원의 통찰 자연어 추론. 상황별 가중치 자유 |
| 속도 | ✅ LLM 1회 (~5-15s Gemini Flash / ~10-20s Gemini Pro) |
| Fragility | ✅ 단일 호출 도미노 없음 |
| 정확도 (cited grounding) | ⚠️ 9 canon 압축 주입 = 토큰 한계. Gemini 1M context 는 여유 있음 |
| 환각 위험 | ⚠️ 9 영역 모두 LLM 직관 → 환각 가능 |
| 사용자 본질 (회사처럼 일하는 multi-agent) | ❌ user_want_spec.md L209 위반 |
| **prism 정합** | ❌ **prism 도 13+ agent multi-agent.** 옵션 1 = "prism 따라하기" 명분 없음 |
| 비용 (Gemini 가정) | Gemini Flash 1회 ~$0.005-0.02 / Pro ~$0.03-0.08 |
| 구현 부담 | ~3-4 세션 (9 분석가 완전 폐기 + 임원 페르소나 신설) |

### 옵션 2 — 하이브리드 (9 분석가 정량 + 임원 LLM 자연어 통합)

**구조**: 9 분석가는 정량 점수만 발행 (cited 자연어 풀이 X, JSON StandardOutput). 임원 LLM (**Gemini Pro 권장 — 사용자 명시 Opus API 키 없음**) 이 9 점수 + raw snapshot + canon + reasoning context 받아서 cited 자연어 통합 추론. **반문 = 2nd round 분석가 dispatch (임계값 trigger)**.

| 차원 | 평가 |
|---|---|
| 사용자 본질 (매매 퀄리티) | ✅ 임원이 9 영역 정량 + 흐름 통합. 상황별 가중치 자유 |
| 사용자 본질 (multi-agent) | ✅ 9 분석가 + 임원 = "회사 구조" 정합 |
| 속도 | 🟡 9 분석가 정량 dispatch (가벼움 ~5-10s 병렬) + 임원 1회 (~10-20s) = **총 15-30s** (현재의 절반) |
| Fragility | ✅ 임원 LLM 부분 결론 룰 자가 적용 |
| 정확도 | ✅ 9 분석가 정량 = 결정론 + 임원 cited 자연어 = grounding 보존 |
| 환각 위험 | 🟡 정량 점수 anchor → 임원 환각 억제 |
| **prism 정합** | ✅ **prism Investment Strategist = 정확히 옵션 2 의 임원 LLM 역할** |
| 비용 (Gemini 가정) | 9 분석가 Gemini Flash (~$0.005-0.02) + 임원 Gemini Pro (~$0.03-0.08) = 현재의 30-50% |
| 구현 부담 | ~2-3 세션 (9 분석가 cited 자연어 풀이 제거 역방향 마이그레이션 + 임원 페르소나 + 종합 doctrine 재작성) |

### 옵션 3 — 현재 구조 유지 + 임원 deepening (반문·통찰 layer 추가)

**구조**: 9 분석가 자연어 풀이 유지. 임원 LLM (**Gemini Pro 권장**) 이 9 응답 + raw + canon 으로 종합 + 반문 + 통찰 layer 추가. Track A/B 페르소나에 임원 doctrine 강화. **Communication Team 패턴 차용** (Quality Evaluator 반복 루프, Gemini Flash 가능).

| 차원 | 평가 |
|---|---|
| 사용자 본질 (매매 퀄리티) | ✅ 통찰 추가. 다만 9 분석가 cited 자연어 풀이가 임원 통찰과 중복 |
| 사용자 본질 (multi-agent) | ✅ 가장 정합 (현재 구조 그대로) |
| 속도 | ❌ 현재 30-60s 그대로 + 임원 추가 → 더 느려질 위험 (Quality Evaluator 루프면 더) |
| Fragility | 🟡 부분 결론 룰 추가로 일부 해소 |
| 정확도 | ✅ cited grounding 보존 + 임원 통찰 추가 |
| 환각 위험 | ✅ 9 분석가 cited + 임원 cited + Quality Evaluator = 3 중 가드 |
| **prism 정합** | ✅ **prism Strategy + Communication Team 패턴 그대로 차용** |
| 비용 (Gemini 가정) | 현재 + 임원 Gemini Pro 1회 + Quality Evaluator Gemini Flash 1-2회 ~$0.05-0.10 추가 |
| 구현 부담 | ~1-1.5 세션 (Track A/B persona 강화 + Quality Evaluator 신설) |

---

## 5. 옵션별 사용자 결함 6건 해소 매핑

| 사용자 결함 | 옵션 1 | 옵션 2 | 옵션 3 |
|---|---|---|---|
| #1 분석가 점수화 위주, 자연어 맥락 X | ✅ (단일 임원 자연어) | ✅ (분석가 정량만, 임원 자연어) | 🟡 (현재 자연어 + 임원 통찰) |
| #2 3줄 요약 빈약 | ✅ | ✅ | ✅ (formatter doctrine 강화) |
| #3 상황별 가중치 차별 X | ✅ | ✅ | ✅ (임원 doctrine 자유 가중치) |
| #4 9 응답 취합 시 맥락 생략 | ✅ (취합 자체 없음) | ✅ (임원이 raw 직접 보유) | 🟡 (임원이 9 응답 + raw 동시) |
| #5 멍청한 임원 | ✅ (똑똑한 임원 1) | ✅ (똑똑한 임원 1) | ✅ (현 임원 deepening) |
| #6 반문 X | 🟡 (단일 LLM 자가 reflection) | ✅ (2nd round dispatch) | ✅ (Quality Evaluator 반복 루프) |

---

## 6. 추천 (claude-code 직설, prism 실 응답 반영 정정)

### 6.0 prism 실 응답 분석 후 추천 정정

**최초 추천 (prism 실 응답 보기 전)** = 옵션 3 단계적 접근

**정정 후 추천 (prism 실 응답 § 2.5 반영)** = **옵션 2 (하이브리드) 직진**

근거 6건 (prism 5 패턴 도달 기준):
1. **prism 응답 5 패턴 = 사용자 명시 KPI** ("위 수준 정도가 되면 좋겠다"). 옵션 3 으로는 부분 도달만 (9 분석가 cited 자연어 풀이가 5-layer chain 차단)
2. **prism Investment Strategist = 옵션 2 의 임원 LLM 역할 정확히 일치** = prism 의 검증된 패턴 그대로 차용
3. **사용자 본질 (multi-agent 회사처럼) L209 정합** = 9 분석가 정량 발행 유지 (역할 분담)
4. **wevelStock 고유 grounding 보존** (α·7계명·위계·F-Score 등) = 9 분석가 정량 anchor 가 prism 환각 사례 ("5/6 거래량 5,309만주") 같은 사고 차단
5. **구현 부담 ~2-3 세션** = main 안전성은 별 feature 브랜치 + 최소 PoC 단계로 보존
6. **속도·비용 동시 개선** = 9 분석가 Gemini Flash 정량 dispatch (~5s 병렬) + 임원 Gemini Pro 1회 (~10-15s) = 총 15-20s. 현재 30-60s 의 1/2-1/3

### 6.1 옵션 3 단계적 접근의 한계 (정정 이유)

prism 실 응답을 본 후 옵션 3 의 본질 한계 노출:
- 9 분석가 cited 자연어 풀이 (예: `cited: [F1, F2] - F-Score F1 (테마-주체 매칭) 가중치 0.4, F2 (모멘텀) 가중치 0.3 ...`) 가 임원 LLM 에 input 으로 들어가면 임원이 그것을 자연어 chain 으로 재구성하는 데 토큰·시간 낭비
- prism 의 Investment Strategist 는 raw section reports 받아 통합 자연어 추론 — 분석가가 자연어 풀이를 미리 안 한 채 정량 점수 + 1줄 사실 코멘트만 발행하는 게 정합

### 6.2 PoC scope 재조정 (옵션 2 직진)

- **최소 PoC** (Phase 1, ~1 세션):
  - 임원 페르소나 1개 신설 (prism Investment Strategist 패턴 차용 + wevelStock 고유 doctrine)
  - Track A 만 적용 + 005930 단일 종목 smoke
  - **prism 응답 5 패턴 모두 시연** (5-layer chain + 시나리오 3 + 솔직 톤 + 상황별 가중치 통합 + 컨텍스트 이어짐)
  - 9 분석가 페르소나는 안 건드림 (응답을 그대로 받아서 임원이 무시·통합)
- **검증 기준**: prism 005930 응답과 1:1 비교. 사용자 평가 "위 수준 이상" 받으면 옵션 2 확정
- **중간 PoC** (Phase 2, ~1 세션, 최소 PoC 성공 시): Track B 도 적용 + 다종목 smoke + 후속 질문 컨텍스트 일관성 검증
- **풀 PoC** (Phase 3, ~1 세션, 옵션 2 확정 후): 9 분석가 페르소나 슬림화 (cited 자연어 풀이 제거, 정량 JSON + 1줄 사실 코멘트만)
- **main 머지**: 풀 PoC 통과 + 회귀 0 시

---

## 7. chat Claude Opus 핑퐁용 미해결 질문 5건

1. **v3.0 설계서 (`idea_memo/prism-insight-비교차용2.md`) 의 16 페르소나 유지 권고 vs 본 메모 옵션 3 의 9 분석가 + 임원 deepening 정합 여부**
   - v3.0 = 16 페르소나 (현 9 + 신규 7). 본 메모 옵션 3 = 9 + 임원 1 = 10. 차이 = 7 (Trigger Hunter / Distribution Detector / Trailing Manager / CAN SLIM Scorer / Reliability Labeler / Self-Diagnosis Officer / Track Selector). 옵션 3 = v3.0 의 부분 적용?

2. **임원 LLM 의 doctrine = "어떻게 똑똑하게 만드는가"**
   - canon 추가 주입? few-shot examples? Chain-of-Thought 강제? Quality Evaluator 자가 reflection?
   - prism Investment Strategist 의 prompt 구조 확인 필요 (코드 직접 확인 권장)

3. **임원 → 분석가 반문 = 2nd round dispatch 시점·임계값**
   - prism 은 1-shot Sequential (반문 메커니즘 명시 X). wevelStock 가 이걸 신설하면 prism 보다 우월
   - trigger: 임원 신뢰도 < threshold? 9 분석가 점수 분산 > threshold? 사용자 명시 `재검토:` 단축어?

4. **Quality Evaluator 반복 루프의 비용·latency 영향**
   - prism = EXCELLENT rating 까지 반복. 최대 몇 회? 평균 호출 수?
   - wevelStock 차용 시 비용 ↑ + latency ↑ → 옵션 3 의 속도 단점 심화 위험

5. **사용자 본질 (user_want_spec.md L209) "회사처럼 일하는 multi-agent" 와 옵션 3 정합도 vs v3.0 16 페르소나 정합도**
   - 옵션 3 = 10 페르소나 (9 분석가 + 임원). v3.0 = 16. 사용자가 본 메모를 받은 후 v3.0 으로 회귀할지, 옵션 3 부분 적용으로 머무를지

---

## 8. PoC 진행 시 권장 사항

사용자 명시: *"이 다음에 하이브리드 poc를 해보고 싶은데 아마도 이건 별도 feature 브랜치 따서 Poc 해봐야할 것 같아"*

### 8.1 브랜치 전략
- `git checkout -b feature/hybrid-executive-poc` (main 에서 분기)
- main 안전성 보존 (본 fix 5번째 세션 #1+#2 후 안정 상태)

### 8.2 PoC scope (작게 시작, 옵션 3 부터)
- **최소 PoC** (Phase 1): 임원 페르소나 1개 신설 + Track A 에만 적용 + 005930 단일 종목 smoke. 9 분석가 페르소나 안 건드림
- **중간 PoC**: 위 + Track B 도 적용 + 다종목 smoke
- **풀 PoC** (Phase 2, 옵션 3 한계 발견 시): 9 분석가 페르소나 슬림화 (cited 자연어 풀이 제거, 정량 JSON only) + 옵션 2 로 escalation

### 8.3 PoC 검증 기준
- **결함 해소 측정**: 6 결함 각각 PoC 응답에서 해소 여부 (smoke 5 종목 × 3 옵션)
- **latency 비교**: prism `/evaluate` (~5-15s) 대비 PoC latency
- **환각 비교**: prism 환각 사례 vs PoC 응답 cited grounding 정확도
- **결정 시점**: PoC 결과 → main 머지 결단 (성공) or 폐기·learnings 메모 (실패)

### 8.4 SPEC 신설 (PoC 시작 시)
- 경로: `docs/specs/ARCHITECTURE-HYBRID-EXECUTIVE-001-hybrid-executive-llm.md`
- 최소 SPEC (PoC scope 만 명시, 풀세트 SPEC 은 PoC 결과 후)

---

## 9. 본 메모 작성자의 입장 (claude-code)

- **결단은 사용자 + chat Opus 의 영역**. 본 메모는 객관 데이터 + 옵션 trade-off + 추천만 제공
- **PoC 결과가 본 메모의 가정을 뒤집을 수 있음** = 옵션 3 으로 충분하다고 추천했지만 PoC 에서 결함 #1·#4 미해소 시 옵션 2 로 escalation 명시
- **사용자 본질 의문에 9 분석가 multi-agent 자체는 본질 정합** = prism 도 13+ agent. 폐기 X 가 맞음
- **속도·fragility 결함은 옵션 1 폐기 없이 해소 가능** = LLM tier + Communication 압축 + Quality Evaluator + 부분 결론 룰

---

## 10. chat Claude Opus 에게

회장, 위 미해결 질문 5건 + PoC 추천에 대한 응답 부탁드립니다. 특히:

- **Q1**: v3.0 설계서의 16 페르소나 유지 권고 vs 본 메모 옵션 3 의 단계적 접근 (10 페르소나) — 어느 게 사용자 본질 (자산 복리 구조 보장) 에 더 정합?
- **Q4**: Quality Evaluator 반복 루프의 비용·latency 영향 — prism 코드 직접 확인하고 운영 데이터 참조해서 알려주실 수 있나요?
- **Q5**: 본 옵션 3 추천이 v3.0 의 부분 적용으로 인정 가능한지, 아니면 별도 경로로 인식해야 하는지

응답 받으면 사용자가 PoC 브랜치에서 직접 옵션 결단 → SPEC 인터뷰 → 구현 진입 예정.

*— claude-code (sungwoowi 의 엔지니어링 페어), 2026-05-23*
