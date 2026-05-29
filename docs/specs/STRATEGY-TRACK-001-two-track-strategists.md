---
spec_id: STRATEGY-TRACK-001
title: Layer 3 Track A·B 전략가 분화 — 이원 트랙 (수익금 + 손익비) + plugin 확장
team: shared
type: feature
status: draft
version: 2                                       # v2 (2026-05-29): Track B 매도 정책 종가 기준 명시 + let-winners-run (prism v2.13.0 #279 차용)
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

5-Layer 모델의 **Layer 3 전략가** 정식 분화. 사용자 의도 (2026-05-17 chat Claude Opus R&D 인수인계 + 2026-05-19 본질 재정의 — 기간 기준 → 전략 본질 기준) 에 따라 **이원 트랙** 으로 정의:

- **Track A** = 🏢 **추세 추적 + 분할 운용 게임** (자본 70-80%·승률 70%+·연 5-15회·MDD -8% 보호·추세 깨짐 = F1 이탈 시까지 보유. 타점에 따라 큰 진입 또는 분할 매수 유기적 선택, 분할 매수 시 역피라미드 = 저점 비중 크게)
- **Track B** = ☕ **프랙탈 1 파 사이클 게임** (자본 20-30%·승률 50%+·월 5-15회·R/R 1.5+ 백업 가드. 저점~고점 1 파 회수가 최대 목표, 종목 실적·장기 관점 무관, 1 파 완성 또는 -7% 절대 매도 시 청산)

**시간 기간은 결과지 본질 아님** — Track A 결과적 보유 = 3 개월~수년 (추세 살아있는 한 더 길게), Track B 결과적 보유 = 일~수주 (1 파 완성 속도 따름).

인트라데이 스캘핑 (당일·분봉 frame) 과 장기 믿음 영역 (지수 투자) 은 본 SPEC 범위 밖. 향후 track 확장은 **plugin 패턴** 으로 가능 (`agents/strategists/<new_track>/` 드롭).

## 배경 / 문제

- 기존 RESUME.md L100-105 의 "단타·스윙·중장기 3분류" 는 prism-insight 가 이미 비효율 증명 (단타·스윙 boundary 모호 / 중장기는 결국 지수 투자가 우월). 사용자 결정 = **A/B 2 트랙 + 향후 확장**.
- ANALYST-PERSONAS-001 v2 의 9 분석가가 각자 점수 (S/T/α/buy_score/F-Score) 발행해도 종합 의사결정 부재 → 분석가 1명 단일 호출 = 답 빈약 (자료 D 의 hierarchical 원칙 = "통합 agent 필수"). 본 SPEC 이 그 통합 agent.
- 자료 B (v3.0 이원 트랙 설계서) 의 #16 Track Selector = 별도 페르소나가 아니라 **전략가 manifest 의 입력 라우팅 룰** 로 흡수 (자료 절약 + 의사결정 단순화).
- chat Opus 메타 설계 의 Layer 3.5 Decision Sanity Check (Haiku) 은 **별도 SPEC** (`INFRA-RELIABILITY-VALIDATOR-001`) 백로그. 본 SPEC 은 Layer 3 본체만.

## 핵심 정의

| 용어 | 의미 |
|---|---|
| **전략가 (strategist)** | Layer 3 의 1 unit. `agents/strategists/<strategist_id>/` 폴더. **production 호출 단위** — 사용자 응답은 분석가 직접 호출이 아니라 전략가 종합 결과. |
| **Track A** | 추세 추적 + 분할 운용 본진. 자본 70-80%, 분할 운용 임대업 비유. 월봉 7월선 위계 (추세 깨짐 기준) + α 가속계수 + S-Score 우선. 타점 맞으면 큰 진입, 애매하면 역피라미드 분할 매수. 결과적 보유 = 3 개월~수년. |
| **Track B** | 프랙탈 1 파 사이클 인컴. 자본 20-30%, 1 파 카페 회전 비유. 트리거 (1 파 저점 시그널) + T-Score + buy_score + 1 파 목표 도달 익절 + trailing stop. 종목 실적·장기 관점 무관, 1 파만 회수. 결과적 보유 = 일~수주. |
| **Track Selector** | `manifest.yaml` 의 `input_routing` 블록. 사용자 입력 단축어 (`long:` / `swing:` / `both:`) + 종목 메타 (월봉위계·트리거발동) 로 A/B/Both 자동 라우팅. 별도 페르소나 X. |
| **권고 (recommendation)** | 전략가의 발행물. `strategist-recommendation-v1` 계약. 진입가 / 목표가 3단 / stop_loss / 신뢰도 / 트랙 / 권고 ID. |
| **plugin 확장** | 새 트랙 추가 = `agents/strategists/<new_track>/{persona.md, manifest.yaml}` 드롭. 코드 변경 X. core/strategist/run_strategist.py 는 manifest 메타로 동적 호출. |

## 비목표

- **Layer 4 계좌관리자** 의 실 비중 결정·자금 배분 — 별도 SPEC.
- **Layer 3.5 Haiku sanity check** — `INFRA-RELIABILITY-VALIDATOR-001` 백로그.
- **인트라데이 스캘핑 트랙·장기 믿음 영역 트랙 신설** — 사용자 명시 = "인트라데이 (당일·분봉 frame) 빼고, 장기 믿음 영역 (지수 투자) 빼고". Track A (추세 추적 + 분할 운용) 와 Track B (1 파 사이클) 두 본질만. 향후 필요 시 plugin 패턴으로 가능 (코드 변경 X). 본 SPEC 의 "단타" 와 "중장기" 어휘는 기간 표기로 폐기 — Track A·B 본질은 *전략* (추세 추적 vs 1 파 사이클) 이지 *기간* 아님.
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

## Track A — 추세 추적 + 분할 운용 전략가 (`track_a`)

### Domain Frame
- **본질 게임**: 🏢 **추세 추적 + 분할 운용 게임** (수익금 = 절대 금액 기준). 분할 운용 임대업 비유. 추세가 깨지지 않는 한 보유 유지.
- **자본 비중**: 자산의 70-80% (본진).
- **결과적 보유 기간** (참고): 3 개월~수년. 추세 살아있는 한 더 길게 가능. **기간은 결과지 본질이 아님**.
- **시간축 위계**: 월봉 7선 > 주봉 MFI > 일봉 Vol Osc. 큰 사이클이 작은 사이클 압도.
- **승률 목표**: 70%+ (큰 자본은 자주 틀리면 복리 누수).
- **회전율**: 낮음 (연 5-15회).
- **MDD 보호**: -8% 이하 (복리 구조 보호 핵심).
- **진입 방식 분기**: 타점 맞으면 (의미있는 저점·강추세 발산 α ≥ 1.5) **큰 진입** (1 회) / 타점 애매하면 (눌림목 모호·체제 전환기·이격 큰 상태) **역피라미드 분할 매수** (저점 비중 크게, 평단이 머리 무거워지지 않도록 상단 추가는 작게).

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

## Track B — 프랙탈 1 파 사이클 전략가 (`track_b`)

### Domain Frame
- **본질 게임**: ☕ **프랙탈 1 파 사이클 게임** (저점~고점 1 파 수익이 최대 목표). 1 파 카페 회전 비유. R/R 1.5+ 는 1 파 미달 시 백업 가드. 종목 실적·장기 관점 무관 — 1 파만 회수.
- **자본 비중**: 자산의 20-30% (인컴).
- **결과적 보유 기간** (참고): 일~수주. 1 파 완성 속도에 따름 — 1 주 미만도 가능 (1 파 빨리 완성 시), 3 개월 넘기지 않음 (1 파 단위 본질, 추세 더 가면 Track A 인계). **기간은 결과지 본질이 아님**.
- **시간축**: 일봉 1 파 + 주봉 1 파 보조 + 시간외 시그널 (월봉 위계 X — 월봉 = Track A 영역). 1 파 = 저점에서 고점까지 한 사이클.
- **승률 목표**: 50%+ (낮아도 R/R 로 보상 가능).
- **R/R 목표**: 평균 1.5:1+ (1 파 미달 시 백업 가드).
- **회전율**: 높음 (월 5-15회).
- **손절 절대 룰**: -7% 이상 손실 시 예외 없는 매도 (한 거래가 인컴 흐름 끊지 못하게).
- **인트라데이 스캘핑 제외**: 당일 매매·분봉 frame 은 Track B 영역 밖 (별도 트랙 미래 의제 — 분봉 차트 인프라 + 인트라데이 페르소나 후속 SPEC 필요).

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
- **종가 기준 원칙** (prism v2.13.0 #279 차용): 모든 trailing·익절 판정은 **종가** 기준. 일중 꼬리(intraday wick) 흔들림은 매도 사유 아님 — 매수 직후 0~1일 노이즈 손절 근절.
- **Trailing stop 활성화**: peak(고점) ≥ 진입가 +5% 도달 **후에만** 작동 (진입 직후 trailing 이 진입가 밑으로 깔리는 것 방지).
- **trailing 폭** (종가 기준): parabolic·strong_bull -10% / sideways -7%.
- **일방향 래칫**: trailing stop 절대 내릴 수 없음.
- **목표가 처리 — let winners run** (prism v2.13.0 #279 차용): `target_price_1` 도달은 강세·parabolic 체제에선 **즉시 전량청산이 아니라 trailing 전환점** (1 파가 더 길게 가면 추세 회수). sideways·약세 진입 체제에선 즉시 익절. **시간(보유 일수)은 checkpoint 모니터일 뿐 매도 트리거 아님**.
- **절대 매도**: 종가 -7% 이상 손실 (예외 없음).

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
- (S8) Track A § 분할 매수 룰 자본 단위 분모 통일 — 현재 표기 "50% 또는 단일 종목 한도의 70%" 의 두 분모 (의도 비중 / 단일 종목 한도 / 계좌 전체) 가 의미상 다름. Layer 4 계좌관리자 페르소나 작성 시 자본 단위 합의 후 Track A persona § 분할 매수 룰 + 본 SPEC 동시 갱신. 후보 = "의도 비중의 50%" (의도 비중 = 단일 종목 한도 내 매수 의도 비중) 또는 "단일 종목 한도의 70%" 단일 분모.

## 분석가 페르소나 작성 가드 (선언적)

본 SPEC 의 Track A·B 가 ANALYST-PERSONAS-001 v2 분석가 점수를 read 하므로, 해당 분석가 페르소나 작성 시 다음 발행 책임을 사전 약속 (가드). 페르소나 작성 시 본 약속 위반 = SPEC 정합 위반.

### G1. stock_picker — 두 점수 발행 강제

`stock_picker` 페르소나는 **S-Score (Track A read) + buy_score (Track B read) 두 점수를 모두 발행 책임**으로 명시한다. 한 점수만 발행하는 결정 금지 — 둘 중 하나라도 누락 시 해당 트랙의 권고 양식 `cited_scores` 가 null 처리되어 결정 품질 저하.

근거:
- Track A § read 분석가 출력 (본 SPEC L91): `stock_picker` → S-Score (주도주 점수)
- Track B § read 분석가 출력 (본 SPEC L153): `stock_picker` → buy_score (매수 점수)

### G2. trader — 6 트리거 정식 정의 + 명단 변경 동시 수정 강제

`trader` 페르소나는 다음을 발행 책임으로 명시:
- **T-Score (타점 점수)** — α 오버라이드 적용 (`collectors/scoring.py:t_score(divergence, macd, volume, rr, alpha)` 시그니처)
- **6 트리거** 정식 정의 (영문 ID 고정) + 발동 알고리즘 + `data.triggers_fired` StandardOutput 발행 (Track B persona 가 그대로 read):
  - `volume_surge` (거래량 급증)
  - `intraday_top` (일중 상승 Top)
  - `gap_up` (갭상승)
  - `closing_strength` (마감 강도)
  - `fund_inflow` (자금 유입)
  - `volume_increase_sideways` (거래량 증가 횡보)

**Track B persona 가 read 하는 6 트리거 명단 (영문 ID) 변경 금지** — 변경 시 Track B persona 의 § Inputs 및 권고 양식 예제 (`data.triggers_fired`) 동시 수정 강제 (양 파일 트랜잭션 정합).

근거:
- Track B persona § Inputs (`trader: 타점 점수 + 6 가지 트리거`) + § 권고 양식 예제 (`data.triggers_fired: ["volume_surge", "intraday_top"]`)
- 본 SPEC § Track B 진입 조건 #1 (L159): 6 트리거 중 1+ 발동 강제

## 관련 문서

- [ANALYST-PERSONAS-001](ANALYST-PERSONAS-001-nine-analyst-portable-personas.md) — depends_on. 9 분석가 점수 발행
- [GUIDANCE-ACCURACY-TRACKER-001](GUIDANCE-ACCURACY-TRACKER-001-five-kpi-tracking.md) — related. 전략가 권고 추적
- [docs/AGENT-ARCHITECTURE.md](../AGENT-ARCHITECTURE.md) — hierarchical orchestration + DB read 원칙
- [docs/CONTRACTS.md](../CONTRACTS.md) — StandardOutput 계약 (team_id = strategist_id)
- [docs/STRUCTURE.md](../STRUCTURE.md) — `agents/strategists/<track_id>/` 폴더 규약
- [idea_memo/prism-insight-비교차용2.md](../../idea_memo/prism-insight-비교차용2.md) — v3.0 이원 트랙 설계서 (Track A·B 본질 정의 원천)
- [idea_memo/2026-05-17-wevelstock-rd-meta-design-by-chat-claude-opus.md](../../idea_memo/2026-05-17-wevelstock-rd-meta-design-by-chat-claude-opus.md) — chat Opus 메타 (패턴 D + Layer 3 통합 전략가 핵심)
