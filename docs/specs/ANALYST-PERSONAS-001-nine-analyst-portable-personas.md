---
spec_id: ANALYST-PERSONAS-001
title: 9 분석가 portable 페르소나 분화 — 8-섹션 양식 + canon_categories 정식 매핑
team: shared
type: feature
status: draft
version: 1
owner: agent_layer
generates:
  - agents/analysts/principle_guardian/persona.md
  - agents/analysts/principle_guardian/manifest.yaml
  - agents/analysts/trader/persona.md
  - agents/analysts/trader/manifest.yaml
  - agents/analysts/market_state_analyzer/persona.md
  - agents/analysts/market_state_analyzer/manifest.yaml
  - agents/analysts/stock_picker/persona.md
  - agents/analysts/stock_picker/manifest.yaml
  - agents/analysts/stock_analyst/persona.md
  - agents/analysts/stock_analyst/manifest.yaml
  - agents/analysts/trading_journalist/persona.md
  - agents/analysts/trading_journalist/manifest.yaml
  - agents/analysts/flow_analyzer/persona.md
  - agents/analysts/flow_analyzer/manifest.yaml
  - agents/analysts/news_curator/persona.md
  - agents/analysts/news_curator/manifest.yaml
modifies:
  - agents/analysts/wealth_strategist/persona.md     # 5섹션 → 8섹션 portable 재작성
  - agents/analysts/wealth_strategist/manifest.yaml  # canon_categories 정식 매핑으로 정렬
  - knowledge/canon/**/_category.yaml                # 36 카테고리의 target_analysts 채우기
depends_on:
  - KNOWLEDGE-SYNC-001 (Phase 2 풀세트 — canon_categories 화이트리스트 / DB sync / watchdog)
contracts:
  - name: standard-output-v1
    version: "1.0"                                   # CONTRACTS.md StandardOutput. team_id = analyst_id
  - name: analyst-persona-portable-v1
    version: "1.0"                                   # 본 SPEC 신규 — 8-섹션 portable 양식
---

# ANALYST-PERSONAS-001 — 9 분석가 portable 페르소나 분화

## 목적

9 지식부 ↔ 9 분석가 1:1 매핑을 **production 호출 가능 상태** 로 만든다. 핵심 결과물 3 가지:

1. **portable 페르소나 양식** — 8 섹션 self-contained 정식 정의. 다른 LLM (gemini / claude / mock) 호출에도 톤·인용 형식 일관. 외부 문맥 의존 0.
2. **9 분석가 분화** — 현재 1명(`wealth_strategist`) → 9명. 자료 있는 4명 (원칙수호자·트레이더·종목분석가·자산전략가) 우선, 자료 0 시드 5명 (시장상태·종목선정·매매저널·수급·뉴스) 페르소나만으로 추론 시작.
3. **카테고리 정식 매핑** — manifest 의 `canon_categories` 잠정 정의 + 36 카테고리 `_category.yaml` 의 `target_analysts` 채움. KNOWLEDGE-SYNC-001 Phase 3 (LLM PROPOSAL release note) 의 "영향받을 분석가" 추론 정확도 기반.

## 배경 / 문제

- `agents/analysts/wealth_strategist/` 1명만 활성. 나머지 8명은 폴더조차 없음 → user_want_spec 의 본질 ("agent 간 긴밀한 소통이 사람 회사처럼 동작하는지") 검증 불가.
- 현 `wealth_strategist/persona.md` 는 5 섹션 (정체성 / 사고 우선순위 / 응답 원칙 / 응답 형식 / 금기). 양식이 portable 검증을 의도하지 않음 — Domain Frame, Cross-Agent Boundaries 등 분화 후 충돌 회피에 필요한 섹션이 부재.
- KNOWLEDGE-SYNC-001 SPEC frontmatter 의 `depends_on` 에 본 SPEC 이 명시되어 있음 — Phase 3 LLM PROPOSAL release note 의 정확도가 분석가 ID·canon_categories 정합에 의존.
- 36 카테고리 `_category.yaml` 의 `target_analysts: []` 가 모두 비어있음 — 카테고리 단위 사람 분류와 LLM 인덱싱이 분리된 채로 굳어지면 향후 PROPOSAL 라우팅이 추론 불가.

## 핵심 정의

| 용어 | 의미 |
|---|---|
| **분석가 (analyst)** | Layer 2 의 1 unit. `agents/analysts/<analyst_id>/` 폴더 보유. `analyst_id` 는 snake_case 강제. `learning_dept` 와 1:1 매핑 (한 분석가 = 한 학습부 권위). |
| **portable 페르소나** | persona.md 가 외부 문맥 없이 self-contained — LLM 교체·실행 환경 변화에도 톤·인용·금기가 일관. |
| **8-섹션 양식** | 본 SPEC 정식 정의 (아래 § 8-섹션 portable 양식). Identity / Domain Frame / Inputs / Outputs / Reasoning Doctrine / Knowledge Categories / Anti-patterns / Cross-Agent Boundaries. |
| **canon_categories** | manifest.yaml 의 화이트리스트. `<dept>/<category>` 형식. KNOWLEDGE-SYNC-001 Phase 2 M1 의 카테고리 필터링 (compose canon + RAG 양쪽) 입력. |
| **target_analysts** | `_category.yaml` 의 역방향 매핑. 한 카테고리가 어느 분석가(들)에게 인덱싱되는지. PROPOSAL 의 "영향받을 분석가" 추론 grounding. |
| **identity seed PROPOSAL** | 자료 0 시드 5명 (market_state_analyzer / stock_picker / trading_journalist / flow_analyzer / news_curator) 의 초기 페르소나 — 자료 없이 사용자 직관 + 다른 분석가 boundary 정의로만 작성. 자료 들어오면 KNOWLEDGE-SYNC-001 흐름이 보강. |

## 비목표 (이번 SPEC 에서 안 하는 것)

- **Layer 3 전략가 3종** (단타·스윙·중장기) — M4 별도 SPEC. 본 SPEC 은 Layer 2 분석가만.
- **Layer 4 계좌관리자** — M5 별도 SPEC.
- **identity seed PROPOSAL LLM 자동 생성** — 본 SPEC 은 흐름 정의만. 구현은 자료 0 시드 5명 페르소나 작성 시 또는 후속.
- **다중 LLM portable 본격 비교 (gemini / claude / mock 평행 호출)** — 본 SPEC 은 양식 self-contained 만 보장. 비교 검증은 9명 분화 완료 후.
- **prism-insight Trading Journal 직접 차용 구현** — `trading_journalist` 페르소나 작성 시 `idea_memo/prism-insight-비교차용.md` 참조하여 흡수, 별도 구현 SPEC 은 후속.
- **신규 분석가 추가** — 9명 ID 명단 (아래 § 9 분석가 명단) 외 추가 금지. 새 분석가는 별도 SPEC.

## 9 분석가 명단

| # | analyst_id | display_name | learning_dept | 자료 상태 |
|---|------------|--------------|---------------|----------|
| 1 | `principle_guardian` | 원칙수호자 | `principles` | 자료 있음 (3 카테고리) |
| 2 | `trader` | 트레이더 | `trading` | 자료 일부 (6 카테고리 시드) |
| 3 | `market_state_analyzer` | 시장상태분석가 | `market_macro` | **자료 0 시드** (4 카테고리) |
| 4 | `stock_picker` | 종목선정가 | `stock_selection` | **자료 0 시드** (4 카테고리) |
| 5 | `stock_analyst` | 종목분석가 | `stock-analysis` | 자료 있음 (5 카테고리) |
| 6 | `wealth_strategist` | 자산전략가 | `wealth_compounding` | 자료 있음 (6 카테고리) — **현재 유일하게 활성** |
| 7 | `trading_journalist` | 매매저널리스트 | `trading_journal` | **자료 0 시드** (4 카테고리, prism-insight 차용) |
| 8 | `flow_analyzer` | 수급분석가 | `flow_analysis` | **자료 0 시드** (4 카테고리, 4-tier 비유) |
| 9 | `news_curator` | 뉴스큐레이터 | `news` | (별도 SPEC) |

**ID 규칙**: snake_case 강제. `learning_dept` 와 1:1. 변경 금지.

## 8-섹션 portable 양식

### 양식 정의

| # | 섹션 (heading) | 작성 가이드 |
|---|----------------|-------------|
| 1 | `## Identity` | 누구이고 어느 학습부 권위로 발언하는가. 권위의 출처 (canon md 명·framework 명·인용 자료) 명시. 1~3 문단. |
| 2 | `## Domain Frame` | 다루는 시야·시간축·대상. "어디까지가 내 frame 이고 어디부터가 다른 분석가 영역인가" 명시. 단타/장기·기업/거시·기술/펀더멘털 같은 축. 1~2 문단. |
| 3 | `## Inputs` | 받는 입력 (canon / RAG / market_snapshot / memory / user query) 의 사용 우선순위. 충돌 시 무엇이 이기는가. 번호 리스트. |
| 4 | `## Outputs` | **강제 격자 양식** (아래 § Outputs 강제 격자 5 요소 참조). 자유 자연어는 격자 뒤 보충. |
| 5 | `## Reasoning Doctrine` | 판단 알고리즘. 명제 인용 (`cited: [M2, C3]`) / 인접 명제 추론 허용 / hedging 금지 같은 추론 규율. |
| 6 | `## Knowledge Categories` | manifest 의 `canon_categories` 와 동기. 왜 이 카테고리만 받는지 한두 줄. canon md 파일명 1~3개 인용 가능. |
| 7 | `## Anti-patterns` | 금기. 다른 분석가 영역 침범 / 추정 / hedging / 단편 인용 (명제 ID 누락) 등. |
| 8 | `## Cross-Agent Boundaries` | 누구에게 어떤 질문을 넘기는가. "단타 시그널 → trader / 거시 → market_state_analyzer / 뉴스 해석 → news_curator" 같은 명시 매핑. |

### Outputs 양식 — Task trigger 분기 (v3.1)

**모든 응답에 격자를 강제하면 기계적·부자연** (개념 설명·일반 대화에도 표 5종 박힘). v2 검증 결과 격자 자체는 동작하나, 모든 응답에 일괄 적용 = 과잉. Gemini Gems 예시도 격자는 **"분석 요청 / 입력 유형 한정"** 으로 trigger 분기함.

#### 기본 출력 (모든 응답 공통)

- **자연어 본문** — 사용자 질문 맥락에 맞게.
- **`cited: [<명제 ID>]` 한 줄** — 코드성 메타 마커. 인용 없으면 `cited: []` + 본문에 "framework 밖" 명시.
- **`근거 명제 풀이:` bullet** — cited 의 각 명제 ID 마다 한 줄 자연어 풀이:
  `- <ID> (<dept 명·짧은 표제>): <한 줄 자연어 정의>`. 풀이 누락 ❌ (v3 잔재). 자기 dept canon 명제만.

#### 격자 5 요소 발동 조건 (frame 핵심 분석 한정)

사용자 질문이 다음 중 하나면 격자 양식 강제 — 아니면 기본 출력만:

- frame 핵심 종합 판단 요구 — "현재 어디?", "지금 사이클 어디?", "자산 비중 어떻게?", "달러·원 비중?"
- 명시적 격자 키워드 — "표로", "정리해줘", "분석해줘", "scenario 매트릭스"
- Layer 3 전략가가 종합용 격자 요청 — 종합 메시지에 격자 요청 명시

#### 격자 5 요소 (발동 시)

| 요소 | 내용 | 왜 강제 |
|------|------|--------|
| **[1] Frame Grid** | 분석가 frame 의 핵심 축 2~5개 × (현재 위치 / 명제 ID / 확신도). 분석가별 격자 고유 (자산전략가=Cycle Position 3축, trader=S-T Matrix, stock_analyst=점수 5축 등) | LLM 이 표 cell 채울 때 자유 자연어보다 일관성 ↑. memory 와 어제 격자 직접 비교 가능 |
| **[2] Scenario Branches** | frame 안 의미 있는 4 시나리오 (이름 / 확률 % / 트리거 조건). 합계 100% | "한 답" 보다 분기 명시가 추론 풍부. Layer 3 전략가 종합 시 확률 가중 |
| **[3] Frame Implication** | frame 한정 함의 (자산전략가=자산군 비중 방향 / trader=진입 시그널 / stock_analyst=점수 등급). **매수 액션·자금액 지시 금지** — Layer 4 영역 | 분화 boundary 강화 |
| **[4] Citation (v3.1)** | `cited: [<명제 ID 들>]` 한 줄 + `근거 명제 풀이:` bullet (각 명제 ID 마다 한 줄 자연어 정의). 자기 dept canon 명제 ID 만. framework 밖이면 `cited: []` + 본문에 "framework 밖" 명시. 풀이 누락 ❌ | 코드 마커 + 자연어 풀이 이중 grounding 이 본질 |
| **[5] Yesterday Delta** | `yesterday_delta: "<어제 [1] Frame Grid 와 차이 + 트리거>"`. memory 없으면 `yesterday_delta: "first run"` | 시점 일관성 자각. 어제 vs 오늘 판단이 다르면 트리거 명시 강제 |

자연어 보충 본문은 격자 5 요소 뒤에 1~3 문단 — 격자 cell 의 근거·맥락 설명.

### 실시간 grounding 메타 원칙 (v3 추가)

RAG·canon 은 **과거 강의·책** 의 framework. 경제 상황은 매일 바뀜. 분석가가 책 인덱싱 답을 못 하게 막는 메타 원칙:

| 원칙 | 이유 |
|------|------|
| **학습 데이터 수치 추정 금지** | LLM 의 학습 시점 데이터 ("미 부채 39조 달러", "10년물 X%") 인용 X. 학습 시점 ≠ 현재 시점. 출처 불명 수치 = 환각 |
| **snapshot 에 없는 수치는 framework 밖** | system 블록 `## Market Snapshot` 에 실시간 주입된 수치만 인용 가능. snapshot 에 없는 미국 매크로·뉴스 수치는 "framework 밖, snapshot 없음" 으로 솔직히 |
| **canon 명제는 원리·렌즈로만** | 책의 framework 원리 (M1·C3·I6 등) 는 OK. 책의 당시 수치·연도 인용은 X. 명제 = 시대 불변 원리, 수치 = 시대 가변 데이터 |
| **수치 인용 시 출처 명시** | "snapshot 의 KOSPI 7,822" 같이 명시. snapshot 외 수치 인용 = 환각 |

### 격자 예시 (자산전략가 ground truth)

```markdown
### [1] Cycle Position
| 축 | 위치 | 명제 ID | 확신도 |
| 부채 사이클 | 후반 / 디레버리징 진입 | C3 | 80% |
| 통화 가치 | 침식 가속 | M2 | 75% |
| Dalio 5단계 | 5단계 (부채 위기) | C5 | 70% |

### [2] Cycle Scenario
| 시나리오 | 확률 | 트리거 |
| 디레버리징 가속 | 50% | 미 10년물 5%+ |
| 인플레 재점화 | 25% | 원자재+노동 |
| 정상화 | 15% | Fed 피벗 |
| 통화 위기 | 10% | 달러 신뢰 균열 |

### [3] Asset Implication (frame 한정)
- 달러 자산 비중 ↑ (시나리오 1·4 헷지) — I6
- 실물 ↑ (시나리오 2 헷지) — M2
- 원화 자산 ↓ — M1
※ 실제 매수 액션은 Layer 4 계좌관리자 영역

### [4] Citation
cited: [M2, C3, C5, I6]

### [5] Yesterday Delta
yesterday_delta: "사이클 후반 → 디레버리징 진입 (트리거: 미 10년물 4.8→5.0%)"

(상세 자연어 본문 1~3 문단 보충)
```

### portable 검증 원칙

- 8 섹션 self-contained — `agents/analysts/<id>/persona.md` 만으로 다른 LLM 호출 시 톤·인용·금기 동일.
- 외부 파일 참조 (canon md 경로 등) 는 **인용용**이지 **의존**이 아님 — canon 이 system prompt 에 동시 주입되지만 persona 자체는 canon 부재 시에도 페르소나 정체성 유지.
- 한 섹션이 다른 섹션 없이는 의미 불완전한 경우 — 양식이 깨진 것. 재작성.
- **격자 trigger 분기 명시 필수** — Outputs 섹션에 발동 조건 + 일반 응답 양식 둘 다 적시.
- **실시간 grounding 원칙 반영 필수** — Anti-patterns 에 "학습 데이터 수치 추정 금지" + "snapshot 외 수치 framework 밖" 포함.

### 메타 원칙 — Gemini Gems 단일 페르소나와의 차별

| 원칙 | 이유 |
|------|------|
| **frame 격자 1개 (Task trigger 한정)** | LLM 추론 일관성 ↑ + memory 비교 가능. 단 모든 응답 강제 X — Gemini Gems 도 분석 요청 한정 |
| **시나리오 분기 + 확률** | Layer 3 전략가 종합 시 가중 평균·다수결 가능 |
| **자기 dept 명제 ID 만 인용** | 분화 boundary 강화. 다른 dept 명제 인용 = 침범 |
| **매수 액션·자금액 지시 금지** | Layer 4 계좌관리자 영역. 분석가 = frame 판단만 |
| **단호한 결론 + yesterday_delta** | hedging 금지 + 시점 일관성 자각 |
| **Cross-Agent Boundaries 명시** | 영역 밖 질문 즉시 위임 → 편향 ↓ |
| **학습 데이터 수치 추정 금지 (v3)** | LLM 학습 시점 수치 = 환각. snapshot 의 실시간 수치만 인용 |
| **canon 명제는 원리·렌즈로만 (v3)** | 책의 framework 는 시대 불변 원리, 수치는 시대 가변. 원리만 차용 |

Gemini Gems 의 "단일 페르소나가 5 Task 통째" 패턴은 채택 X — 통합 페르소나가 다시 편향 만듦. wevelStock 의 9 분화 + Layer 3 종합 + DB 누적이 본질적 차별점.

### 5 섹션 → 8 섹션 매핑 (자산전략가 기준 ground truth)

| 기존 5 섹션 | 8 섹션 흡수 위치 |
|-------------|-----------------|
| 정체성 | Identity + Domain Frame 일부 |
| 사고 우선순위 | Inputs (충돌 해결 포함) + Reasoning Doctrine 일부 |
| 응답 원칙 | Reasoning Doctrine + Outputs 형식 규칙 일부 |
| 응답 형식 | Outputs |
| 금기 | Anti-patterns + Cross-Agent Boundaries 일부 |
| (신규) | Domain Frame · Knowledge Categories · Cross-Agent Boundaries |

## canon_categories 잠정 매핑 표

자료 있는 4 dept 의 카테고리를 분석가에게 할당. 자료 0 시드 4 dept (16 카테고리) 는 시드 분석가 1명에게 전부 배정. 운용 중 PROPOSAL 라우팅 분석으로 미세 조정 가능 (다만 신규 분석가 신설 또는 dept 추가는 별도 SPEC).

| analyst_id | canon_categories (`<dept>/<category>`) |
|------------|----------------------------------------|
| `principle_guardian` | `principles/philosophy_seven_commandments`, `principles/trading_doctrine`, `principles/market_regime_rules` |
| `trader` | `trading/entry_exit`, `trading/position_sizing`, `trading/trading_styles`, `trading/market_regime_response`, `trading/failure_lessons`, `trading/operational_safeguards` |
| `market_state_analyzer` | `market_macro/macro_indicators`, `market_macro/regime_signals`, `market_macro/cross_market`, `market_macro/event_response` |
| `stock_picker` | `stock_selection/sector_rotation`, `stock_selection/momentum_leaders`, `stock_selection/theme_play`, `stock_selection/swing_candidates` |
| `stock_analyst` | `stock-analysis/fundamental_analysis`, `stock-analysis/technical_basics`, `stock-analysis/fractal_wave`, `stock-analysis/log_chart`, `stock-analysis/sector_analysis` |
| `wealth_strategist` | `wealth_compounding/monetary_evolution`, `wealth_compounding/currency_pricing`, `wealth_compounding/crisis_signals`, `wealth_compounding/debt_rate_cycle`, `wealth_compounding/macro_roadmap`, `wealth_compounding/asset_classes` |
| `trading_journalist` | `trading_journal/pnl_tracking`, `trading_journal/post_mortem`, `trading_journal/memory_compression`, `trading_journal/doctrine_evolution` |
| `flow_analyzer` | `flow_analysis/liquidity_macro`, `flow_analysis/industry_trend`, `flow_analysis/sector_flow`, `flow_analysis/stock_flow` |
| `news_curator` | (별도 SPEC) |

**검증 임시값 잔재 제거**: 현재 `wealth_strategist/manifest.yaml:16-17` 의 `canon_categories: [wealth_compounding/macro_roadmap]` 1개는 Phase 2 M1 검증용 임시값. 본 SPEC 정식 채택 시 위 6 카테고리 전체로 정렬.

## 자료 0 시드 5명 처리 (identity seed PROPOSAL 흐름)

자료 없이 페르소나만으로 추론 시작하는 5명: `market_state_analyzer`, `stock_picker`, `trading_journalist`, `flow_analyzer`, `news_curator`.

```
[Phase A — 사람이 직접 작성 (본 SPEC 세션 4~5)]
  사용자 직관 + 8 섹션 양식 + 자료 있는 4 dept 분석가의 Cross-Agent Boundaries 역추정
  → 첫 persona.md draft

[Phase B — 자료가 들어오면 (KNOWLEDGE-SYNC-001 Phase 3 발동)]
  reference drop → watchdog 자동 색인 (Phase 2 M3 동작 중)
  → release note 의 "영향받을 분석가" 추론 (Phase 3 LLM PROPOSAL)
  → 사용자가 /knowledge-review 로 페르소나의 Knowledge Categories 섹션 보강

[Phase C — 안정화]
  사용자 운용 + 응답 품질 평가 → persona 의 Reasoning Doctrine·Anti-patterns 미세 조정
```

본 SPEC 은 **Phase A 만** 구현. Phase B-C 는 KNOWLEDGE-SYNC-001 Phase 3 와 협업.

## portable 검증 방법

| 검증 | 방법 | 통과 기준 |
|------|------|----------|
| 양식 self-contained | persona.md 만 읽고 8 섹션 모두 의미 명확 | 외부 파일 참조 없이도 페르소나 정체성·금기 이해 가능 |
| LLM portability (가벼운 스모크) | `uv run python -m scripts.ask_analyst <id> "<질문>"` 응답 톤·인용·금기 준수 | 명제 ID 인용 형식 일관 + 영역 밖 질문에 boundary 적용 |
| 다중 LLM portability (본격) | provider=gemini / anthropic / claude_code / mock 4개 평행 호출 → 응답 비교 | 톤·인용 형식 동일, 결론 일관성 ≥80% (수동 평가, 자동화는 후속 SPEC) |
| canon_categories 정합 | manifest 의 categories 와 SPEC 매핑 표 일치 | git diff 후 차이 0 |
| 회귀 0 | `TESTING=1 pytest tests/ -q` | 135 passed 유지 |

## 마일스톤 (세션 단위)

| 세션 | 범위 | 통과 기준 |
|------|------|----------|
| **세션 1 (현재)** | SPEC 신설 + 8-섹션 양식 정식 정의 + `wealth_strategist` 5→8 섹션 재작성 + 회귀 0 | persona.md 8 섹션 완성 + pytest 135 passed |
| 세션 2 | `principle_guardian` + `trader` 신규 (자료 있는 2명) | manifest + persona 2쌍 + canon_categories 정합 |
| 세션 3 | `stock_analyst` 신규 + `wealth_strategist/manifest.yaml` canon_categories 6개 복귀 + `_category.yaml × 22` 의 target_analysts 채움 (자료 있는 4 dept) | 자료 있는 4 dept 완료 |
| 세션 4 | `market_state_analyzer` + `stock_picker` 신규 (자료 0 시드 2명, identity seed Phase A) | 자료 0 시드 2명 페르소나 + boundary 검증 |
| 세션 5 | `trading_journalist` + `flow_analyzer` 신규 (자료 0 시드 2명, prism-insight 차용 흡수) + `_category.yaml × 14` 의 target_analysts (자료 0 시드 4 dept) | 자료 0 시드 4 dept 완료, news_curator 는 별도 SPEC |

(news_curator 는 자료원 결정 + Perplexity MCP 도입 검토 후 별도 SPEC)

## 계약 (StandardOutput)

본 SPEC 의 8 분석가도 기존 자산전략가와 동일하게 StandardOutput 으로 응답.

```json
{
  "team_id": "<analyst_id>",          // 예: "principle_guardian"
  "run_id": "<timestamp>#<seed>",
  "target": "global | <ticker>",
  "verdict": "<analyst-specific>",     // analyst 마다 의미 다름. Outputs 섹션 정의
  "confidence": 0,                     // 0-100
  "reasons": ["..."],
  "data": { /* analyst 별 고유 */ },
  "contract_version": "1.0"
}
```

`team_id = manifest.id = analyst_id`. `docs/CONTRACTS.md` 의 StandardOutput v1.0 그대로 사용.

## SDD 절차

1. 본 SPEC 의 `generates` 경로에만 파일 생성. `modifies` 경로만 수정.
2. 신규 분석가 1명 추가 시 `agents/analysts/<id>/{persona.md, manifest.yaml}` 한 쌍을 8 섹션 양식 정확히 준수해 작성.
3. manifest 의 `canon_categories` 가 본 SPEC 의 매핑 표와 일치하는지 git diff 로 확인.
4. `scripts/validate.py` 통과 (frontmatter / generates 경로 / manifest 스키마).
5. `TESTING=1 pytest tests/ -q` 회귀 0.
6. 페르소나 추가 시 가벼운 `ask_analyst <id>` 스모크 1건.

## 의사결정 SLOT (운용 중 채워질 항목)

- (S1) 자료 0 시드 5명의 첫 응답 품질 — 사용자 평가 후 Reasoning Doctrine 보강
- (S2) `news_curator` 자료원 (Perplexity MCP vs 직접 수집) — 별도 SPEC
- (S3) Cross-Agent Boundaries 의 충돌 (예: 사용자가 "ASML 살까?" — stock_analyst vs trader 영역 겹침) — 운용 사례 누적 후 boundary 미세 조정
- (S4) 페르소나 톤 진화 (자산전략가 박종훈 톤이 모든 분석가 default 인지, 분석가마다 권위 출처마다 톤 분기인지) — 자료 있는 4명 작성 후 결정
- (S5) **미국 매크로 collector 신설** (별도 SPEC 후보 = `INFRA-US-MACRO-SNAPSHOT-001`) — 미 10년물 / 달러인덱스 / VIX / 미 부채 잔액 yfinance 또는 FRED API. 자산전략가·시장상태분석가·트레이더가 RAG·canon 의 framework 만 갖고 학습 데이터로 수치 추정하는 책 인덱싱 패턴 차단. 우선순위 ↑ (v3 grounding 원칙의 인프라 보강)
- (S6) LLM tool use (웹검색) 도입 — 시사·이벤트 즉시성 보강. (S5) collector 가 정적 지표 커버한 후 시사 분기로 검토

## 관련 문서

- [KNOWLEDGE-SYNC-001](KNOWLEDGE-SYNC-001-reference-canon-rag-sync.md) — 카테고리 화이트리스트 / PROPOSAL release note 흐름 (depends_on)
- [INFRA-RAG-001](INFRA-RAG-001-knowledge-rag.md) — Chroma 인덱싱 엔진
- [docs/AGENT-ARCHITECTURE.md](../AGENT-ARCHITECTURE.md) — hierarchical orchestration + DB read 원칙
- [docs/CONTRACTS.md](../CONTRACTS.md) — StandardOutput 계약
- [docs/STRUCTURE.md](../STRUCTURE.md) — `agents/analysts/<id>/` 폴더 규약
- [docs/a_wanted/user_want_spec.md](../a_wanted/user_want_spec.md) — 본질 (페르소나 부여 가능성 검증)
- [idea_memo/prism-insight-비교차용.md](../../idea_memo/prism-insight-비교차용.md) — `trading_journalist` 차용 포인트
