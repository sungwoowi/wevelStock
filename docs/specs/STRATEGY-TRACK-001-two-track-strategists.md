---
spec_id: STRATEGY-TRACK-001
title: Layer 3 Track A·B 전략가 분화 — 이원 트랙 (수익금 + 손익비) + plugin 확장
team: shared
type: feature
status: draft
version: 1
owner: agent_layer
generates:
  - agents/strategists/track_a/persona.md
  - agents/strategists/track_a/manifest.yaml
  - agents/strategists/track_b/persona.md
  - agents/strategists/track_b/manifest.yaml
  - core/strategist/run_strategist.py             # 분석가 team_outputs read + LLM 호출 wrap
  - core/strategist/track_selector.py             # 사용자 입력 → A/B/Both 자동 라우팅
modifies:
  - core/db/schema.sql                            # strategist_outputs view 또는 team_outputs.layer 컬럼
depends_on:
  - ANALYST-PERSONAS-001 (v2 — 9 분석가 점수 발행 권위 매핑 / S/T/α/buy_score/F-Score)
related:
  - GUIDANCE-ACCURACY-TRACKER-001 (전략가 권고가 추적 대상)
  - AGENT-ARCHITECTURE.md (hierarchical orchestration + DB read 원칙)
contracts:
  - name: standard-output-v1
    version: "1.0"                                # team_id = strategist_id (예: "track_a")
  - name: strategist-recommendation-v1
    version: "1.0"                                # 본 SPEC 신규 — 권고 객체 (진입가 / 목표가 3단 / stop_loss / 신뢰도)
---

# STRATEGY-TRACK-001 — Layer 3 Track A·B 전략가 + plugin 확장

## 목적

5-Layer 모델의 **Layer 3 전략가** 정식 분화. 사용자 의도 (2026-05-17 chat Claude Opus R&D 인수인계) 에 따라 **이원 트랙** 으로 정의:

- **Track A** = 🏢 중장기 수익금 게임 (자본 70-80%·승률 70%+·연 5-15회·MDD -8% 보호)
- **Track B** = ☕ 단기 손익비 게임 (자본 20-30%·승률 50%+·월 5-15회·R/R 1.5:1+)

장기 투자 (믿음 영역) 와 단타는 본 SPEC 범위 밖. 향후 track 확장은 **plugin 패턴** 으로 가능 (`agents/strategists/<new_track>/` 드롭).

## 배경 / 문제

- 기존 RESUME.md L100-105 의 "단타·스윙·중장기 3분류" 는 prism-insight 가 이미 비효율 증명 (단타·스윙 boundary 모호 / 중장기는 결국 지수 투자가 우월). 사용자 결정 = **A/B 2 트랙 + 향후 확장**.
- ANALYST-PERSONAS-001 v2 의 9 분석가가 각자 점수 (S/T/α/buy_score/F-Score) 발행해도 종합 의사결정 부재 → 분석가 1명 단일 호출 = 답 빈약 (자료 D 의 hierarchical 원칙 = "통합 agent 필수"). 본 SPEC 이 그 통합 agent.
- 자료 B (v3.0 이원 트랙 설계서) 의 #16 Track Selector = 별도 페르소나가 아니라 **전략가 manifest 의 입력 라우팅 룰** 로 흡수 (자료 절약 + 의사결정 단순화).
- chat Opus 메타 설계 의 Layer 3.5 Decision Sanity Check (Haiku) 은 **별도 SPEC** (`INFRA-RELIABILITY-VALIDATOR-001`) 백로그. 본 SPEC 은 Layer 3 본체만.

## 핵심 정의

| 용어 | 의미 |
|---|---|
| **전략가 (strategist)** | Layer 3 의 1 unit. `agents/strategists/<strategist_id>/` 폴더. **production 호출 단위** — 사용자 응답은 분석가 직접 호출이 아니라 전략가 종합 결과. |
| **Track A** | 중장기 수익금 게임. 자본 70-80%, 부동산 임대업 비유. 월봉 7월선 위계 + α 가속계수 + S-Score 우선. |
| **Track B** | 단기 손익비 게임. 자본 20-30%, 카페 운영 비유. 트리거 발동 + T-Score + buy_score + trailing stop. |
| **Track Selector** | `manifest.yaml` 의 `input_routing` 블록. 사용자 입력 단축어 (`long:` / `swing:` / `both:`) + 종목 메타 (월봉위계·트리거발동) 로 A/B/Both 자동 라우팅. 별도 페르소나 X. |
| **권고 (recommendation)** | 전략가의 발행물. `strategist-recommendation-v1` 계약. 진입가 / 목표가 3단 / stop_loss / 신뢰도 / 트랙 / 권고 ID. |
| **plugin 확장** | 새 트랙 추가 = `agents/strategists/<new_track>/{persona.md, manifest.yaml}` 드롭. 코드 변경 X. core/strategist/run_strategist.py 는 manifest 메타로 동적 호출. |

## 비목표

- **Layer 4 계좌관리자** 의 실 비중 결정·자금 배분 — 별도 SPEC.
- **Layer 3.5 Haiku sanity check** — `INFRA-RELIABILITY-VALIDATOR-001` 백로그.
- **단타 트랙·중장기 트랙 신설** — 사용자 명시 = "단타 빼고, 장기 빼고 (믿음 영역 + 지수 투자)". 향후 필요 시 plugin 패턴으로 가능 (코드 변경 X).
- **prism-insight 의 trading_journal 자기 학습 직접 차용** — Layer 5 회고분석가 별도 SPEC.

## 9+3+1+회고N 골격에서의 위치

```
Layer 2 (9): 분석가 9명 (ANALYST-PERSONAS-001 v2)
   ↓ team_outputs DB write (S/T/α/buy_score/F-Score 점수 + verdict)
Layer 3 (2+): 본 SPEC — Track A + Track B + plugin 확장
   ↓ team_outputs DB write (권고 = strategist-recommendation-v1)
Layer 4 (1+): 계좌관리자 (별도 SPEC)
   ↓ team_outputs DB write (실 매매 시뮬·실 주문)
Layer 5 (N): 회고분석가 (별도 SPEC)
```

## Track A — 중장기 전략가 (`track_a`)

### Domain Frame
- **본질 게임**: 🏢 수익금 게임 (절대 금액 기준). 부동산 임대업 비유.
- **자본 비중**: 자산의 70-80% (본진).
- **시간 지평**: 3-12 개월.
- **시간축 위계**: 월봉 7선 > 주봉 MFI > 일봉 Vol Osc.
- **승률 목표**: 70%+ (수익금 게임의 핵심 — 큰 자본은 자주 틀리면 안 됨).
- **회전율**: 낮음 (연 5-15회).
- **MDD 보호**: -8% 이하 (복리 구조 보호 핵심).

### read 하는 분석가 출력 (team_outputs)
- `stock_picker` 의 **S-Score (주도주 점수)** + 월봉 7월선 위계
- `stock_analyst` 의 **α (가속계수)** + Module A 목표가 3단 + F1~F5 생존 필터
- `wealth_strategist` 의 거시 frame 격자 (사이클 위치 / 자산군 비중 방향)
- `principle_guardian` 의 7계명 (특히 단일 종목 15% / 손절선 / 데이터 없이 추측 X)
- `market_state_analyzer` 의 시장 체제 (Regime Classifier 6 단계)
- `flow_analyzer` 의 **F-Score (수급 점수)**

### 진입 조건 (manifest 룰)
- 월봉 종가 7월선 위 (F1 통과)
- S-Score ≥ 7 (주도주)
- α ≥ 1.3 (발산 시작) 또는 눌림목 (이격도 -10% ~ 0%)
- 시장 체제 = strong_bull / moderate_bull / parabolic 중 하나
- 7계명 위반 X

### 권고 양식 (strategist-recommendation-v1)
```yaml
recommendation_id: REC-20260513-005930-A
date: 2026-05-13
ticker: "005930"
display_name: "삼성전자"
track: A
verdict: "buy" | "hold" | "sell" | "wait"
entry_price: 285000
target_price_1: 320000          # Module A α 목표 1단
target_price_2: 380000          # 2단
target_price_3: 450000          # 3단 (α 1.5+ 보정)
stop_loss: 270000               # 월봉 7월선 종가
risk_reward: 3.2
cited_scores:
  s_score: 8.5
  alpha: 1.6
  f_score: 7
  cited_propositions: [W1, SP1, M2]
confidence: 80                  # 0-100
reasons:
  - "주도주 점수 8.5 (S-Score=8.5) — 반도체 섹터 RS Top 1 + 외인 60일 1.2조"
  - "가속계수 1.6 (α=1.6) — 강발산 구간, T-Score 이격도 강제 보정 적용"
  - "수급 점수 7 (F-Score=7) — AI 반도체 테마 + 외인·기관 일치"
data:
  monthly_7ma_aligned: true
  market_regime: "strong_bull"
  holding_period_estimate_days: 120
contract_version: "1.0"
```

### 익절·청산 정책
- Module A 목표가 3단 도달 시 단계별 익절 (1단 30% / 2단 30% / 3단 잔여)
- F1 (월봉 7월선 종가 위) 이탈 시 즉시 청산
- 7계명 위반 (단일 종목 15% 초과) 시 부분 청산

## Track B — 단기 스윙 전략가 (`track_b`)

### Domain Frame
- **본질 게임**: ☕ 손익비 게임 (R/R 기준). 카페 운영 비유.
- **자본 비중**: 자산의 20-30% (인컴).
- **시간 지평**: 1주 ~ 3개월.
- **시간축**: 일봉 단일 + 시간외 시그널.
- **승률 목표**: 50%+ (낮아도 R/R 로 보상 가능).
- **R/R 목표**: 평균 1.5:1+.
- **회전율**: 높음 (월 5-15회).
- **손절 절대 룰**: -7% 이상 손실 시 예외 없는 매도 (한 거래가 인컴 흐름 끊지 못하게).

### read 하는 분석가 출력 (team_outputs)
- `stock_picker` 의 **buy_score (매수 점수, CAN SLIM)**
- `trader` 의 **T-Score (타점 점수, α 오버라이드 적용)** + 6 가지 트리거 (거래량 급증·갭상승·일중 상승 Top·마감 강도·자금 유입·거래량 증가 횡보)
- `market_state_analyzer` 의 시장 체제 + Distribution Day kill switch
- `flow_analyzer` 의 **F-Score (수급 점수)**
- `principle_guardian` 의 트레이딩 비중 20% 한도

### 진입 조건 (manifest 룰)
- 6 가지 트리거 중 1개 이상 발동
- buy_score ≥ 체제별 min_score (parabolic 4 / strong_bull 4 / moderate_bull 5 / sideways 6 / bear 매매 중단)
- R/R ≥ 체제별 floor (parabolic 0.7 / strong_bull 1.0 / moderate_bull 1.2 / sideways 1.5)
- Distribution Day 4건+ 시 매매 중단
- 시장 체제 ≠ moderate_bear / strong_bear

### 권고 양식 (strategist-recommendation-v1)
Track A 와 동일 schema. 차이:
- `track: B`
- `target_price_1` 만 사용 (3단 X)
- `stop_loss` = 진입가 × (1 - 손절_floor)
- `cited_scores` 에 `buy_score` + `t_score`

### 익절·청산 정책
- **Trailing stop 활성화**: 진입가 +5% 도달 후
- **trailing 폭**: parabolic·strong_bull -10% / sideways -7%
- **일방향 래칫**: trailing stop 절대 내릴 수 없음
- **절대 매도**: 종가 -7% 이상 손실 (예외 없음)

## α 가속계수 오버라이드 룰 (Track A·B 공통)

| α 범위 | T-Score 이격도 강제 보정 | 매매 의미 |
|--------|----------------------|----------|
| α < 0.8 | 기본 룰 유지 | 둔화, 관망 |
| 0.8 ≤ α < 1.3 | 기본 룰 유지 | 정상 추세 |
| 1.3 ≤ α < 1.5 | max(원래값, 5) | 발산 시작, 분할 진입 |
| 1.5 ≤ α < 2.0 | max(원래값, 7) | **강발산, 적극 진입** ⭐ |
| α ≥ 2.0 | min(원래값, 3) | 폭주, 부분 청산 |

**왜 강제 보정**: 로그 함수 발산 구간 (α 1.3~1.7) = 가장 큰 수익 자리 (사용자 W 계좌 실측). 일봉 이격도로 차단하면 발산 참여 불가. **α 는 "참여 여부"** / 일봉 이격은 **"비중 크기"**.

**구현 위치**: `collectors/scoring.py` 의 `t_score(divergence, macd, volume, rr, alpha)` 함수가 α 인자 받아 내부 적용. 전략가는 점수 read 만 (재계산 X).

## Track Selector — manifest 입력 라우팅 룰

별도 페르소나 X. 각 전략가의 `manifest.yaml` `input_routing` 블록에 정의. **server 측 dispatcher** 가 manifest 룰 읽어 사용자 입력 → A/B/Both 분기.

```yaml
# agents/strategists/track_a/manifest.yaml (input_routing 발췌)
input_routing:
  shortcuts:
    explicit: ["long:", "core:", "wave:"]      # 사용자가 명시한 단축어
  auto:
    conditions:
      - monthly_7ma_aligned: true
      - market_cap_min: 1000000000000          # 1조원
      - sector_rs_min: 7
  fallback: true                                # 단축어·트리거·체제 모두 부재 시 default

# agents/strategists/track_b/manifest.yaml (input_routing 발췌)
input_routing:
  shortcuts:
    explicit: ["swing:", "short:", "trigger:"]
  auto:
    conditions:
      - any_trigger_fired: true                  # 6가지 트리거 중 1개 이상
  fallback: false

# 양 트랙 동시 평가
input_routing_both:
  shortcuts: ["both:"]
  auto:
    conditions:
      - monthly_7ma_aligned: true
      - any_trigger_fired: true                  # 월봉 위계 AND 트리거 동시
```

라우팅 우선순위: **명시 단축어 > auto.conditions > fallback**.

`core/strategist/track_selector.py` 가 모든 전략가 manifest 의 `input_routing` 읽어 사용자 입력 → 해당 전략가 호출 결정. plugin 확장 = 새 manifest 의 `input_routing` 자동 인식.

## plugin 확장 규칙 (Track C 미래 신설 시)

새 트랙 추가는 **3 단계**:

1. `agents/strategists/<new_track>/persona.md` + `manifest.yaml` 드롭
2. manifest 에 `input_routing` 정의
3. (선택) `core/strategist/track_selector.py` 의 default 룰 갱신

코드 변경 0. `core/strategist/run_strategist.py` 가 manifest 메타로 동적 호출.

**제약**:
- 트랙 ID = snake_case (`track_a`, `track_b`, `track_c`, ...).
- 한 트랙은 ANALYST-PERSONAS-001 v2 의 9 분석가 중 N 명 read (직접 호출 X, `team_outputs` DB read 만).
- 트랙 간 직접 통신 X (AGENT-ARCHITECTURE.md 의 hierarchical 원칙).

## strategist-recommendation-v1 계약 (StandardOutput data 필드)

```json
{
  "team_id": "track_a" | "track_b" | "track_<custom>",
  "run_id": "<timestamp>#<seed>",
  "target": "<ticker>",
  "verdict": "buy" | "hold" | "sell" | "wait",
  "confidence": 0,
  "reasons": ["..."],
  "data": {
    "recommendation_id": "REC-<YYYYMMDD>-<ticker>-<track>",
    "track": "A" | "B" | "<custom>",
    "entry_price": 0,
    "target_price_1": 0,
    "target_price_2": null,
    "target_price_3": null,
    "stop_loss": 0,
    "risk_reward": 0.0,
    "cited_scores": {
      "s_score": null,
      "t_score": null,
      "alpha": null,
      "buy_score": null,
      "f_score": null,
      "cited_propositions": []
    },
    "holding_period_estimate_days": null,
    "market_regime": "<6단계 중 하나>"
  },
  "contract_version": "1.0"
}
```

## 마일스톤 (세션 단위)

| 세션 | 범위 | 통과 기준 |
|------|------|----------|
| 세션 1 | 본 SPEC 신설 (이번 세션) | frontmatter / 본문 완성, validate.py 통과 |
| 세션 2 | `agents/strategists/track_a/{persona.md, manifest.yaml}` 작성 + `core/strategist/run_strategist.py` 골격 | Track A 단일 호출 스모크 |
| 세션 3 | `agents/strategists/track_b/{persona.md, manifest.yaml}` 작성 + `track_selector.py` 동적 라우팅 | A/B/Both 분기 검증 |
| 세션 4 | webapp `analyst-chat/page.tsx` default agent = Track A 또는 Both 로 교체 | 사용자 production 호출 = 전략가 종합 |
| 세션 5 | strategist-recommendation-v1 DB 적재 + GUIDANCE-ACCURACY-TRACKER-001 연동 | 권고 ID 자동 생성 + 추적 |

## 검증 방법

| 검증 | 방법 | 통과 기준 |
|------|------|----------|
| 트랙 분리 | Track A 권고 vs Track B 권고 의 verdict·entry·stop 양식 비교 | 본질 게임 (수익금 vs 손익비) 차이가 reasons·data 에 명시 |
| Track Selector 라우팅 | `swing: 삼성전자` → Track B / `long: 삼성전자` → Track A / `both: 삼성전자` → 양쪽 | 명시 단축어 우선 / auto 조건 / fallback 순서 |
| plugin 확장 | 임시 `track_c` 드롭 → run_strategist 자동 인식 | 코드 변경 0 |
| 회귀 | `TESTING=1 pytest tests/ -q` | 135 passed 유지 |
| validate.py | frontmatter / generates 경로 / manifest 스키마 | 0 errors |

## 의사결정 SLOT (운용 중 채워질 항목)

- (S1) Track A 의 default LLM 모델 — Sonnet (Standard) vs Opus (Deep). chat Opus 메타 = Sonnet, 자료 B = Standard Sonnet · Deep Opus. 초안 = Sonnet 4.6 + `provider: "claude_code"` 토글
- (S2) Track B 의 default LLM 모델 — Haiku (트리거 스캔 빈도 ↑) vs Sonnet (buy_score CAN SLIM 통합). 자료 B 권장 = 트리거 = Haiku / buy_score = Sonnet. 초안 = Sonnet 단일 (분기 비용 vs 단순성)
- (S3) Track A·B 동시 평가 (`both:`) 시 응답 양식 — 두 권고 병렬 표시 vs 통합 메시지. 사용자 체감 검증 후 결정
- (S4) Track Selector fallback default — Track A 우선 (자료 B 권장) vs 사용자 명시 강제. 초안 = Track A fallback
- (S5) plugin 확장 활성화 시점 — 9 분석가 + 2 트랙 안정 운용 3 개월 후 (Track C 검토). 그 전엔 plugin 패턴 인프라만 유지
- (S6) prism-insight 트레이딩 저널 (분석가 가중치 자동 갱신) 흡수 — Layer 5 회고분석가 SPEC 후속
- (S7) Layer 3.5 Decision Sanity Check (Haiku 검증) 도입 — 운용 1 개월 데이터 후 환각·내부 모순 빈도 보고 결정. `INFRA-RELIABILITY-VALIDATOR-001` 백로그

## 관련 문서

- [ANALYST-PERSONAS-001](ANALYST-PERSONAS-001-nine-analyst-portable-personas.md) — depends_on. 9 분석가 점수 발행
- [GUIDANCE-ACCURACY-TRACKER-001](GUIDANCE-ACCURACY-TRACKER-001-five-kpi-tracking.md) — related. 전략가 권고 추적
- [docs/AGENT-ARCHITECTURE.md](../AGENT-ARCHITECTURE.md) — hierarchical orchestration + DB read 원칙
- [docs/CONTRACTS.md](../CONTRACTS.md) — StandardOutput 계약 (team_id = strategist_id)
- [docs/STRUCTURE.md](../STRUCTURE.md) — `agents/strategists/<track_id>/` 폴더 규약
- [idea_memo/prism-insight-비교차용2.md](../../idea_memo/prism-insight-비교차용2.md) — v3.0 이원 트랙 설계서 (Track A·B 본질 정의 원천)
- [idea_memo/2026-05-17-wevelstock-rd-meta-design-by-chat-claude-opus.md](../../idea_memo/2026-05-17-wevelstock-rd-meta-design-by-chat-claude-opus.md) — chat Opus 메타 (패턴 D + Layer 3 통합 전략가 핵심)
