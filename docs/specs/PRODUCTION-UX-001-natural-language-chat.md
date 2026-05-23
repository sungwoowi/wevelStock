---
spec_id: PRODUCTION-UX-001
title: 자연어 채팅창 production UX — Intent Classifier + 30 시나리오 라우팅 + 종합 답변 포맷터
team: shared
type: feature
status: approved
version: 1
owner: production_chat
generates:
  - core/intent/__init__.py
  - core/intent/classifier.py
  - core/intent/cache.py
  - core/intent/router.py
  - core/intent/formatter.py
  - core/intent/system_prompt.md
  - config/scenario_keywords.yaml
  - config/label_dictionary.yaml
  - server/api/production_chat.py
  - webapp/src/app/production-chat/page.tsx
  - webapp/src/app/production-chat/components/IntentFallback.tsx
  - webapp/src/app/production-chat/components/EvidenceToggle.tsx
  - tests/intent/test_classifier_golden.py
  - tests/intent/test_router.py
  - tests/intent/test_formatter.py
  - tests/intent/test_30_scenarios_e2e.py
modifies:
  - config/runtime.yaml
  - core/llm/client.py
depends_on:
  - WAVE-ALPHA-001 v1 (stock_analyst α 3 timeframe + verdict + holding_period — Track A 권고 풀세트 발행 베이스라인)
  - STRATEGY-TRACK-001 v1 (Track A/B + input_routing manifest 패턴 1:1 mirror)
  - ANALYST-PERSONAS-001 v2 (9 분석가 v3.1 cited 정합 — 근거 토글 raw 노출 시 신뢰)
  - INFRA-LLM-STREAM-001 v1 (SSE 패턴 재사용 — production-chat 도 동일 SSE 프로토콜)
contracts:
  - name: intent-classification-v1
    version: "1.0"
    description: "사용자 자연어 발화 → {scenario_id: 1~30, ticker: str | null, agent_route: track_a | track_b | both | analyst_direct | refuse_or_guide | pending_ms5, confidence: 0~1, manual_fallback_required: bool, stage: deterministic | llm | cache, latency_ms: int}. Stage 1 (결정론 keyword + scenario_keywords.yaml) → Stage 2 (FAST 계층 LLM, Gemini Flash-lite default + fallback chain) → 결과 캐시 (llm_call_cache.type='intent_classification', TTL 30일). confidence < 0.6 또는 ticker 매핑 실패 시 manual fallback drop-down."
  - name: production-chat-v1
    version: "1.0"
    description: "POST /api/chat/production = 사용자 발화 입력 → Intent Classifier → agent_route 별 분석가/전략가 호출 (BALANCED Flash 본문) → 종합 답변 포맷터 (FAST Flash-lite, raw → 1~3줄 결론 + 1~3줄 근거, 코드 라벨 자연어 변환 label_dictionary.yaml 주입) → SSE 스트림 (text_delta + metadata + done). 근거 토글 = raw 응답 풀세트 (cited 명제 + 격자 + 코드 라벨 포함, 추가 LLM 호출 X)."
---

# PRODUCTION-UX-001 — 자연어 채팅창 production UX

## 목적

cycle 14.3 (WAVE-ALPHA 풀세트, 2026-05-23) 완료로 **MS4 베이스라인 도달** ✨ = 분석가 9 + 전략가 2 + α 3 timeframe + verdict 매트릭스 + holding_period 매핑 모두 활성. 그러나 **사용자가 실제로 시스템을 사용하는 인터페이스 = R&D 검증용 webapp (`/analyst-chat`, `/strategist-chat`)** 만 존재 — agent_id/target/Layer 토글이 노출되어 초보자 진입 불가능 + 코드 라벨 (S-Score/α/F-Score/cited) 본문 노출.

본 SPEC = **production UX 본질 구현**. 사용자 가치 최대 = 하나의 자연어 채팅창에서 "삼성전자 살까?" 같은 발화 → 시스템이 자동 분류 → 적절한 분석가/전략가 호출 → **자연어 1~3줄 결론 + 1~3줄 근거** 응답. user_want_spec.md 의 "사용자가 매수/매도/홀딩 의견 받는 것이 매매 행위" 본질 정합.

**핵심 4 결단**:

1. **2-Stage Intent Classifier** (cycle 14 `collectors/anchors.py` 패턴 1:1 mirror): Stage 1 결정론 keyword + Stage 2 LLM (FAST 계층 Flash-lite) + 30일 cache + manual fallback drop-down
2. **30 시나리오 우주 ↔ agent_route 매핑** (사용자 명시 5 + Claude 4차 25 누적): v1 freeze = 1~11, v1 시연 = 1~10 (시나리오 11 자가 진화 = v2 MS5 후)
3. **종합 답변 포맷터** = 분석가/전략가 raw 응답 → FAST Flash-lite 1콜 → 자연어 1~3줄 결론 + 1~3줄 근거 (수급/차트/실적 3요소). `config/label_dictionary.yaml` 외부 사전 주입
4. **LLM 3계층 정책 신설** (FAST/BALANCED/DEEP, Gemini-Anthropic 1:1 mirror). 적용 범위 = D 점진 (신규 영역만 즉시, 기존 영역은 후속 `LLM-TIER-MIGRATION-001`)

v1 완료 = 사용자가 5 본질 시나리오 (보유/진입/시장/섹터/주도주) 모두 자연어로 묻고 자연어로 답 받는 시연 인수.

## 배경 / 문제

### cycle 14.3 직후 production UX 부재 (2026-05-23)

| 영역 | 현재 상태 | 차단점 |
|---|---|---|
| 분석가 9 본문 | 활성 (v5 stock_analyst α 3 timeframe + verdict 매트릭스 + holding_period) | 해소 |
| 전략가 2 본문 | Track A/B 권고 양식 활성 | 해소 |
| webapp `/analyst-chat`, `/strategist-chat` | R&D 검증 UI (agent_id/target/Layer 토글 노출) | **production UX 부재** |
| 자연어 자동 라우팅 | 명시 단축어 (`long:`/`swing:`/`both:`) 만 (track_selector) | **자연어 발화 → scenario_id 분류 부재** |
| 코드 라벨 → 자연어 변환 | response_rules 에 부분 박힘 (manifest 별 분산) | **중앙 사전 부재, 일관성 X** |
| 종합 답변 포맷 | 분석가 raw 응답 그대로 (cited + 격자 풍부, 초보자 이해 불가) | **압축 부재** |

### 사용자 의도 (메모리 누적, 2026-05-21 ~ 2026-05-23)

**`feedback_webapp_production_ux`** = production = 하나의 LLM 채팅창, 백단 0 노출. 자연어 → 자동 라우팅 → 종합 답변. 현재 webapp 의 Layer 토글/agent_id/target 입력은 R&D 검증용 임시.

**`feedback_production_answer_brevity`** = 1~3줄 결론 + 1~3줄 근거. 30 시나리오 우주 (사용자 명시 5 + Claude 4차 25). 코드 라벨 (S-Score/α/F-Score/cited) 금지, 번역 사전 + 근거 3요소 (수급·차트·실적) 자연어 강제.

**`feedback_llm_intuition_distribution`** = LLM 직관 분포 활용 (2-Stage 하이브리드). 결정론 candidate + LLM 선택 + 캐싱 + manual override.

**`feedback_llm_tier_strategy`** = LLM 3계층 (FAST/BALANCED/DEEP, Gemini-Anthropic 1:1 mirror). 영역별 tier 매핑 + config 외부 설정.

### 인프라 80% 완성 (재사용 가능)

직전 세션 (2026-05-23 머티턴 조사) 결과:

| 영역 | 위치 | 본 SPEC 활용 |
|---|---|---|
| `track_selector.select_tracks` | `core/strategist/track_selector.py:141-191` | 명시 단축어 우선 → auto.conditions → fallback 4단계, manifest input_routing 외부 설정 패턴 mirror |
| `run_strategist` + `run_strategist_stream` | `core/strategist/run_strategist.py:247-382` | Track A/B 호출 진입점, metadata 28 키 |
| `run_analyst` + `run_analyst_stream` | `core/inference/run_analyst.py:469-602` | 분석가 직접 호출 (시나리오 3·4·9 = market_state_analyzer 직접) |
| `resolve_ticker` | `core/inference/run_analyst.py:174-289` | KR_NAME_TO_TICKER 30 종목 dict (한계, INFRA-TICKER-RESOLVER-001 백로그) |
| `core/llm/client.py` | provider-agnostic | mock/claude_code/gemini/anthropic + fallback chain Flash-lite → Haiku 4.5 → mock |
| `collectors/anchors.py` | cycle 14 production 검증 | 2-Stage 하이브리드 패턴 = Intent Classifier 1:1 mirror |
| `webapp/src/lib/api.ts` + `ChatPane.tsx` | SSE 패턴 + ChatMetadata 타입 | production-chat 신규 라우트에서 패턴 재사용 |
| `llm_call_cache` | DB v8 (type 컬럼 활성) | type='intent_classification' 신규 type, TTL 30일 |

### 신설 필요 (~3 세션 분산)

- Intent Classifier 코어 (`core/intent/` 6 파일)
- 종합 답변 포맷터 (`core/intent/formatter.py`)
- 신규 라우트 `webapp/src/app/production-chat/page.tsx` 0 부터 (기존 webapp 보존, deprecate 라벨 없음)
- `config/scenario_keywords.yaml` (Stage 1 결정론 룰) + `config/label_dictionary.yaml` (코드 라벨 자연어 변환)
- 90건 골든 eval

## 7 freeze 결단 (라운드 1~5 결정)

본 SPEC 의 영구 권위. 향후 sub-cycle 구현 + 변경 제안 시 본 § 결단을 먼저 다시 읽어야 한다.

| # | 영역 | 결단 | 근거 |
|---|---|---|---|
| **1** | **30 시나리오 ↔ agent_route 매핑 권위** | 표 § 30 시나리오 매핑 (아래 § 참조). 모호 default 3건: 시나리오 2/5 (신규 진입·주도주) = **both** (A+B 동시 호출, 사용자 단/장 미정 시), 시나리오 10 (계좌 안심) = **보유 종목 명세 종합** (Layer 4 미구현 시), 시나리오 11 (자가 진화) = **`route: pending_ms5`** (v1 제외, MS5 도달 후 활성) | R3 면담. user_want_spec.md 4계좌 구조 (국장/미장 × 중장기/단기) → 단/장 균등 노출 |
| **2** | **종합 답변 포맷 contract** | LLM 1콜 추가 (FAST 계층 Gemini Flash-lite, fallback Haiku 4.5). 분석가/전략가 raw → 포맷 LLM → **1~3줄 결론 + 1~3줄 근거 (수급/차트/실적 3요소)**. 코드 라벨 자연어 변환은 `label_dictionary.yaml` 주입 | R4 면담. memory `feedback_production_answer_brevity` 정신 |
| **3** | **manual fallback trigger 임계** | `confidence < 0.6` OR `ticker 매핑 실패 (ticker 필요 시나리오 1/2/5/6/7/8/12/13/14 에서 resolve_ticker null)`. drop-down = 30 종목 + 1~10 시나리오 선택 | R2 면담. cycle 14 anchors.py 보수 임계 패턴 |
| **4** | **코드 라벨 사전 권위** | `config/label_dictionary.yaml` (외부 설정, watchdog hot reload). 시드 = memory `feedback_production_answer_brevity` 의 번역 사전 14 종 (α / F-Score / S-Score / T-Score / buy_score / regime / verdict / confidence / cited / RS / breadth / divergence / 분배일 / Distribution Day) | R4 면담. CLAUDE.md 원칙 9 (하드코딩 금지) |
| **5** | **production-chat vs 기존 webapp 분리 경계** | 기존 webapp (`/`, `/analyst-chat`, `/strategist-chat`) = **전면 보존 + deprecate 라벨 없음 (R&D 데모 무기한 유지)**. production-chat = 완전 별도 라우트 `webapp/src/app/production-chat/page.tsx` 0 부터 작성 | R1 면담. 직전 세션 합의 (3) |
| **6** | **30 시나리오 우주 v1 freeze 범위** | **1~11 v1 freeze** (사용자 명시 5 + 자동 푸시 6). 12~30 = SPEC 매핑 표엔 잔류 (input_routing yaml 1~3줄/시나리오), v1 시연 포커스 X. v1 시연 = 1~10 (시나리오 11 = `pending_ms5`) | R1 면담. user_want_spec.md 명시 발화 5개 + 알림 Agent Task 5 직접 매핑 |
| **7** | **Intent Classifier LLM 정책** | default = **Gemini Flash-lite (FAST 계층)**. fallback chain = Flash-lite → Haiku 4.5 → mock (`core/llm/client.py` 기존 chain). **JSON 파서 강건화 + response_schema 명시 (SLOT S6 본질 동일 해소)**. cache = `llm_call_cache.type='intent_classification'`, TTL 30일, key=`sha256(normalized_input + model)`. 무료 티어 1500회/일 cache 70%+ hit 시 실호출 ~450/일 보호 | R2 면담. memory `feedback_llm_tier_strategy` |

추가 결단 (인터뷰 중 도출):

- **LLM 3계층 정책 신설** (FAST/BALANCED/DEEP). 적용 범위 = **D 점진** (신규 영역만 즉시 = Intent Classifier + 포맷터 → FAST. 기존 영역 = 후속 SPEC `LLM-TIER-MIGRATION-001` 에서 영역별 1 PR 단위 교체 + 회귀 검증)
- **근거 토글 정책** = raw 분석가/전략가 응답 풀세트 노출 (cited 명제 + 격자 + 코드 라벨 포함). LLM 추가 호출 X. R&D 수준 투명성

## 30 시나리오 우주 + agent_route 매핑

본 표 = production UX 라우팅 권위. 새 시나리오 발견 시 본 표 갱신 + scenario_keywords.yaml 갱신.

### v1 freeze (1~11)

| # | 시나리오 | trigger | agent_route | v1 시연 |
|---|---|---|---|---|
| 1 | 보유자 (4 결정 추매/홀딩/매도/손절) | 사용자 호출 | `track_a` (보유 종목 holding_period 메타 read) | ✅ |
| 2 | 신규 진입 (얼마에 어떻게) | 사용자 호출 | **`both`** (사용자 단/장 미정 default) | ✅ |
| 3 | 시장 판단 (불장/횡보/하락) | 사용자 호출 | `analyst_direct: market_state_analyzer` | ✅ |
| 4 | 섹터 선택 (Top 3) | 사용자 호출 | `analyst_direct: stock_picker + market_state_analyzer` | ✅ |
| 5 | 주도주 진입 (언제 얼마) | 사용자 호출 | **`both`** (단/장 균등 노출) | ✅ |
| 6 | 매도 시그널 (상승 후 분할) | 사용자 호출 + 자동 푸시 | `track_a` | ✅ |
| 7 | 손절 발동 (선 이탈) | 자동 푸시 + 사용자 확인 | `track_a + principle_guardian` | ✅ |
| 8 | 추매 시그널 (눌림 2차) | 자동 푸시 + 사용자 확인 | `track_a` | ✅ |
| 9 | 시장 위기 (kill switch / 전쟁 / 폭락) | 자동 푸시 | `analyst_direct: market_state_analyzer + principle_guardian` | ✅ |
| 10 | 계좌 안심 (매일 아침) | 매일 자동 (08:30 KST) | **보유 종목 명세 종합** (Layer 4 미구현 시) — 보유 메타 read + 각 종목 분석가 점검 + 위험 신호 카운트 | ✅ |
| 11 | 자가 진화 PROPOSAL | MS5 후 자동 | **`pending_ms5`** (v2 이행, 30건+ 매매일지 누적 + Layer 5 회고분석가 필요) | ❌ (v2) |

### v2 점진 확장 (12~30)

SPEC 매핑 표엔 잔류, 구현은 v2 점진 추가:

| # | 시나리오 | agent_route 가설 |
|---|---|---|
| 12 | 종목 비교 (A vs B) | `both` × 2 종목 비교 |
| 13 | 포트폴리오 평가 | `track_a` (보유 종목별 4 결정 라벨링) |
| 14 | 테마 분석 | `analyst_direct: stock_picker + flow_analyzer` |
| 15 | 자금 비중 추천 | `principle_guardian` (7계명 자동 준수) + 계좌관리자 |
| 16 | 단기 vs 중장기 선택 | `stock_analyst` α + verdict + holding_period |
| 17 | 거시 변곡점 | `analyst_direct: wealth_strategist` |
| 18 | 뉴스 해석 | `analyst_direct: news_curator` |
| 19 | 환율/달러 영향 | `analyst_direct: market_state_analyzer + wealth_strategist` |
| 20 | 첫 사용자 안내 | `refuse_or_guide` (onboarding LLM 직접 답변) |
| 21 | 분할 매수 전략 정밀 | `track_a` 또는 `track_b` (사용자 단축어) |
| 22 | 매매 후 회고 | `trading_journalist` |
| 23 | 일별 시장 브리핑 | 기존 `market_briefing_now` pipeline 재사용 |
| 24 | 매도 후 재진입 | `track_a` 또는 `track_b` |
| 25 | 자산 배분 | `analyst_direct: wealth_strategist` |
| 26 | 미장·국장 비중 | `analyst_direct: wealth_strategist + market_state_analyzer` |
| 27 | FOMO 통제 | `refuse_or_guide` (7계명 #7 인용) |
| 28 | 세금·수수료 | `refuse_or_guide` (LLM 직접 답변, 데이터 fetch X) |
| 29 | 시장 외 자산 (부동산·코인) | `analyst_direct: wealth_strategist` |
| 30 | 단일 시그널 신뢰도 | `refuse_or_guide` (7계명 #5 인용) |

## 아키텍처 (2-Stage Intent + Routing + Format)

### 흐름도

```
사용자 발화 ("삼성전자 살까")
  ↓
[1] Intent Classifier
    ├─ Stage 1: 결정론 keyword (scenario_keywords.yaml) ─┐
    │   ├─ Hit → scenario_id + ticker + agent_route       │
    │   └─ Miss/모호 ─────────────────────────────────────┤
    ├─ Stage 2: LLM (FAST Flash-lite) → JSON              ├─→ classification
    │   ├─ response_schema 강제 + parser 강건화           │
    │   ├─ cache check (llm_call_cache, TTL 30일)         │
    │   └─ fallback chain (Flash-lite → Haiku 4.5 → mock) │
    └─ confidence < 0.6 OR ticker null → manual fallback ─┘
        UI drop-down (30 종목 + 1~10 시나리오)
  ↓
[2] Router (agent_route → 분석가/전략가 호출)
    ├─ track_a → run_strategist("track_a", ticker)
    ├─ track_b → run_strategist("track_b", ticker)
    ├─ both → run_strategist("track_a") + run_strategist("track_b")
    ├─ analyst_direct → run_analyst(analyst_id, ticker)
    └─ refuse_or_guide → LLM 직접 답변 (FAST Flash-lite)
  ↓ raw response (BALANCED Flash 본문, cited + 격자 + 코드 라벨 풍부)
  ↓
[3] Format LLM (FAST Flash-lite)
    ├─ system prompt = label_dictionary.yaml 주입
    ├─ 1~3줄 결론 + 1~3줄 근거 (수급/차트/실적 3요소)
    └─ 코드 라벨 자연어 변환 (S-Score → 주도주 점수 등)
  ↓ formatted response
  ↓
[4] SSE Stream → webapp
    ├─ text_delta (스트리밍 토큰)
    ├─ metadata (scenario_id, ticker, route, confidence, latency, cost)
    └─ done

근거 토글 클릭 → raw response 풀세트 노출 (LLM 추가 호출 X)
```

### 모듈별 책임

| 파일 | 책임 | LOC 추정 |
|---|---|---|
| `core/intent/classifier.py` | 2-Stage 분류 진입점. Stage 1 (keyword match) + Stage 2 (LLM call) 통합 | 250 |
| `core/intent/cache.py` | `llm_call_cache` 재사용 wrapper. type='intent_classification', TTL 30일 | 80 |
| `core/intent/router.py` | agent_route → run_strategist/run_analyst 호출 분기. both = asyncio.gather | 180 |
| `core/intent/formatter.py` | raw → 1~3줄 결론 + 근거 3요소 LLM 1콜. label_dictionary.yaml 주입 | 200 |
| `core/intent/system_prompt.md` | Intent Classifier Stage 2 LLM system prompt (30 시나리오 정의 + 출력 JSON schema) | 100 |
| `config/scenario_keywords.yaml` | Stage 1 결정론 룰. 시나리오별 keyword + regex + 단축어 매핑 | 200 |
| `config/label_dictionary.yaml` | 코드 라벨 자연어 변환 사전. 시드 14 종 + 신규 자유 | 80 |
| `server/api/production_chat.py` | `POST /api/chat/production` + `/stream` SSE | 150 |
| `webapp/src/app/production-chat/page.tsx` | 신규 라우트, 0 부터. 채팅 UI + SSE 클라이언트 | 200 |
| `webapp/src/app/production-chat/components/IntentFallback.tsx` | manual fallback drop-down (30 종목 + 1~10 시나리오) | 150 |
| `webapp/src/app/production-chat/components/EvidenceToggle.tsx` | "근거 보기" 토글 → raw 응답 풀세트 노출 | 120 |
| `tests/intent/test_classifier_golden.py` | 90건 골든 eval (10 시나리오 × 9건) | 250 |
| `tests/intent/test_router.py` | router 분기 단위 테스트 | 100 |
| `tests/intent/test_formatter.py` | formatter 자연어 변환 검증 (코드 라벨 grep 0건 assertion) | 120 |
| `tests/intent/test_30_scenarios_e2e.py` | 시나리오 1~10 e2e (PROD-UX-2 산출) | 300 |

### config 스키마 확장 (`config/runtime.yaml`)

```yaml
llm:
  provider: gemini  # default provider (전 시스템)
  tiers:
    fast:
      gemini: gemini-2.5-flash-lite
      anthropic: claude-haiku-4-5
    balanced:
      gemini: gemini-2.5-flash
      anthropic: claude-sonnet-4-5
    deep:
      gemini: gemini-2.5-pro
      anthropic: claude-opus-4-6
  areas:
    intent_classifier: fast      # 본 SPEC 신규
    answer_formatter: fast       # 본 SPEC 신규
    anchors_stage2: fast         # LLM-TIER-MIGRATION-001 후속 (현재 balanced)
    analyst: balanced            # 9 분석가, 기존 유지
    strategist: balanced         # Track A/B, 기존 유지
    retrospect: deep             # M4 후속
```

`call_llm` 호출 시 `tier="fast"` 또는 `area="intent_classifier"` 인자만 넘기면 cfg 에서 provider+model 자동 해석.

## sub-cycle 3 분할

### PROD-UX-1 (~1 세션) — Intent Classifier + Routing + 기본 채팅

**시연 마일스톤**: 시나리오 1~5 (사용자 명시 본질 5) 동작.

- "삼성전자 들고 있는데?" → 시나리오 1 → track_a 호출 → raw 응답 표시
- "삼성전자 살까?" → 시나리오 2 → both 호출 → raw 응답 표시
- "지금 시장 어때?" → 시나리오 3 → market_state_analyzer 직접 → raw 응답
- "어떤 섹터 투자?" → 시나리오 4 → stock_picker + market_state_analyzer → raw 응답
- "지금 뭐 사?" → 시나리오 5 → both → raw 응답

**산출물**: `core/intent/{classifier.py, cache.py, router.py, system_prompt.md}` + `config/scenario_keywords.yaml` + `server/api/production_chat.py` + `webapp/src/app/production-chat/page.tsx` + `tests/intent/test_classifier_golden.py` (시나리오 1~5 × 9건 = 45건)

**테스트 기준**: 45건 골든 eval ≥ 85% 정확도, Stage 1 hit ≥ 40%, cache 2회차 ≥ 95%

**아직 안 함**: 종합 답변 포맷터 (raw 그대로 표시), manual fallback drop-down, 근거 토글

### PROD-UX-2 (~1 세션) — 30 시나리오 확장 + 포맷터 + manual fallback

**시연 마일스톤**: 시나리오 1~10 e2e + 자연어 1~3줄 압축.

**산출물**: `core/intent/formatter.py` + `config/label_dictionary.yaml` + 시나리오 6~10 keyword + router 확장 + `webapp/.../IntentFallback.tsx` + `tests/intent/test_30_scenarios_e2e.py` + `tests/intent/test_formatter.py`

**테스트 기준**: 90건 골든 eval ≥ 85%, formatter 응답에 코드 라벨 (α/F-Score/S-Score/T-Score/buy_score/regime/verdict/confidence/cited/RS/breadth/divergence) grep 0건, 결론·근거 각 ≤3줄 assertion

### PROD-UX-3 (~1 세션) — 근거 토글 + 폴리싱 + 사용자 인수

**시연 마일스톤**: 사용자 인수 완성형.

**산출물**: `webapp/.../EvidenceToggle.tsx` + streaming 갱신 + 에러 메시지 자연어화 + 발화 로그 관측 (일일 리포트)

**테스트 기준**: 사용자 본인 일상 발화 5~10건 던져 직관 만족도 검증 + 90건 골든 회귀 유지

## 테스트 전략

### 객관 골든 eval (자동 회귀)

`tests/intent/test_classifier_golden.py` 에 시나리오별 9건 (10 시나리오 × 9건 = **90건**) 골든 셋. 구성:

- 사용자 발화 (자연어) → 기대 `{scenario_id, ticker, agent_route, confidence_min}`
- 발화 다양성: 명시 단축어 / 키워드만 / 모호 / 오타 / 다른 종목명 / 영어 혼용 / 줄임말 / 격식체 / 반말
- **인수 기준**: 정확도 ≥ 85% (시나리오·ticker·route 모두 맞음). Stage 1 hit ≥ 40%, cache 2회차 ≥ 95%

### 사용자 주관 발화 검증

PROD-UX-3 시점에서 사용자 본인이 일상 발화 5~10건 던져 본인 직관 만족도 검증. 통과 = "production = 이 정도면 일상에서 쓰겠다" 확신.

### 회귀 보호

기존 pytest 542 통과 유지 (분석가 9 + 전략가 + WAVE-ALPHA). 본 SPEC 신규 ~80건 추가 = 총 ~620 expected.

## SLOT (후속 SPEC)

| SLOT | 영역 | 후속 SPEC | 본 SPEC 와 관계 |
|---|---|---|---|
| **S1** | 시나리오 11 (자가 진화) v2 활성 | M4 회고분석가 SPEC + MS5 도달 | 매핑 표 `pending_ms5` 라벨 잔류, M4 진입 시 본 SPEC 갱신 |
| **S2** | 시나리오 10 (계좌 안심) Layer 4 풀세트 | `M5 계좌관리자 SPEC` | v1 = 보유 종목 명세 종합, v2 = Layer 4 계좌관리자 호출 |
| **S3** | 기존 영역 LLM 3계층 마이그레이션 | `LLM-TIER-MIGRATION-001` | anchors.py Stage 2 (Flash → Flash-lite + SLOT S6 통합) + 분석가 9 + 전략가 + 회고분석가. 영역별 1 PR 단위 회귀 검증 |
| **S4** | resolve_ticker 30 종목 한계 | `INFRA-TICKER-RESOLVER-001` | 본 SPEC 의 manual fallback drop-down 이 임시 회피. ticker 매핑 풀세트 (KRX 전 종목 fuzzy match) 후속 |
| **S5** | 30 시나리오 v2 (12~30) 점진 확장 | sub-cycle PROD-UX-4 또는 후속 SPEC | SPEC 매핑 표엔 잔류, scenario_keywords.yaml + router 확장으로 점진 추가 |

## 검증 (acceptance)

PROD-UX-3 완료 시 본 SPEC frozen → spec_completed 전환 기준:

- ✅ 90건 골든 eval ≥ 85% 정확도 + Stage 1 hit ≥ 40% + cache 2회차 ≥ 95%
- ✅ 사용자 본인 일상 발화 5~10건 만족도 검증 통과
- ✅ formatter 응답 grep 0건 (코드 라벨 12종 모두)
- ✅ 결론·근거 각 ≤ 3줄 assertion
- ✅ pytest 회귀 0 (기존 542 + 본 SPEC 신규 ~80 = ~620)
- ✅ 기존 webapp (`/`, `/analyst-chat`, `/strategist-chat`) 전면 작동 유지 (deprecate X)
- ✅ `python scripts/validate.py` 통과 (frontmatter generates 경로 100% 존재)
