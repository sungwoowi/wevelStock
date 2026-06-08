---
spec_id: ACCOUNT-MANAGER-001
title: Layer 4 계좌관리자 — 권고 → 4계좌별 비중·자금액·분할매수 (7계명 강제)
team: account_manager
type: feature
status: implementing
version: 1
level: implementation
parent: RIGHT-BRAIN-COMPLETION-001
owner: account_manager
generates:
  - agents/account_manager/persona.md            # Layer 4 페르소나 (계좌를 사랑·아끼는 자산배분자)
  - agents/account_manager/manifest.yaml         # 매니페스트 (reads: 전략가 권고, 4계좌 config)
  - core/account/sizing.py                       # 권고 → 비중·자금액 변환 (결정론 + 7계명 강제)
  - core/account/portfolio.py                    # 4계좌 보유·가용 자본 상태
  - config/accounts.yaml                         # 4계좌 정의 (국장/미장 × 중장기/단기, 계좌당 1000만)
modifies:
  - core/db/schema.sql                           # account_positions / account_state 테이블 (가상)
depends_on:
  - STRATEGY-TRACK-001 (전략가 권고 = strategist-recommendation-v1 — 변환 입력)
  - RIGHT-BRAIN-COMPLETION-001 (소속 roadmap — 경계 결단 상속, 가상 전용·4계좌·7계명 하드 제약)
contracts:
  - name: strategist-recommendation-v1
    version: "1.0"                               # STRATEGY-TRACK-001 정의 (입력)
  - name: position-sizing-v1
    version: "1.0"                               # 본 SPEC 신규 — 계좌별 비중·자금액 산출 (출력)
---

# ACCOUNT-MANAGER-001 — Layer 4 계좌관리자 (비중 결정)

> **이 SPEC 은 RIGHT-BRAIN-COMPLETION-001 (오른쪽 뇌) 의 첫 자식 (RB-MS1).**
> 다음 세션 작업: 아래 `INTERVIEW-SLOT` 마커를 `/spec-interview` 5라운드로 채운 뒤 SDD 구현.

## 목적

왼쪽 뇌(전략가 A/B)의 권고는 *무엇을 살까*까지만 답한다. 계좌관리자 = **얼마를, 어느 계좌에, 몇 차에 걸쳐** 를 결정.
"투자는 계좌 관리가 핵심이다. 계좌를 사랑하고 아껴야 한다"(user_want_spec) = Layer 4 의 페르소나 본질.
가상매매(RB-MS2)·채점(RB-MS3)이 이 산출(계좌별 비중·자금액) 위에 선다.

## 경계 (roadmap 에서 상속, 영구)

- **가상 전용** — 실 KIS 주문 X. 산출은 "가상 체결 지시"(position-sizing-v1)까지.
- **4 계좌** — 국장 중장기 / 국장 단기 / 미장 중장기 / 미장 단기. 계좌당 1000만원. Track A→중장기 계좌(70-80%) / Track B→단기 계좌(20-30%).
- **7계명 = 하드 제약** — 총 비중 80% 이하 / 단일 종목 15% 이하 / 트레이딩(단기 계좌) 비중 20% 이하 / 손절선 없는 권고는 진입 차단.

## 입력 / 출력

- **입력**: 전략가 권고(`strategist-recommendation-v1` — 진입가·목표가 3단·stop_loss·트랙·점수) + 현 계좌 상태(`account_state`: 가용 현금·보유 종목·기존 비중).
- **출력**: `position-sizing-v1` — { 계좌 id, 종목, 목표 비중%, 자금액, 분할매수 차수·차당 금액, 적용된 7계명 한도, 차단/축소 사유 }. `team_outputs` 저장(가상매매가 read).

## 핵심 정의

| 용어 | 의미 |
|---|---|
| **계좌 (account)** | 4개 가상 계좌. config/accounts.yaml 정의. 각 1000만원 시드. |
| **목표 비중** | 해당 종목이 계좌에서 차지할 %. 7계명 단일 15% 한도 하. |
| **분할매수 차수** | 1차/2차/3차 진입 분할. 권고 진입가·stop_loss 간격 기반. |
| **7계명 강제** | 변환 결과가 한도 초과 시 *축소* 또는 *차단* + 사유 기록 (advisory 아님, 하드 게이트). |

## 판단 로직 (인터뷰 2026-06-09 확정 — 수치만 SLOT)

### 비중 산정 = 두 레버 (리스크 × regime) — 확정

"보수 vs 공격" 을 고정 선택하지 않는다. **종목당 리스크는 고정(MDD 통제), 총 공격성은 시장상태가 변조(시장 추종).**

- **레버 1 — 종목당 고정 리스크 R (수량 역산):**
  `수량 = (계좌자본 × R) ÷ (진입가 − stop_loss)`. → 변동성·stop 먼 종목은 비중이 자동 축소되어 **MDD 구조적 통제**.
  R 예시(튜닝 SLOT): 중장기 계좌 1% / 단기 계좌 1.5%. 확신도(buy_score/S/α/R·R)는 **R 배수 상한**(고확신 +0.5R)으로 advisory — 점수가 비중을 직접 *결정*하지 않고 *상한*만 ([[feedback_score_collapse_advisory]] 일관).
  7계명 5번(단일 지표 금지): R 배수 상향은 buy_score·S·α 중 **최소 3개 교차 충족 시만**.
- **레버 2 — 총 배포 한도 (regime/entry_posture 변조):**
  계좌 총 비중 천장을 시장상태로 변조. `confirmed_bull`/`risk_on` → 상향(최대 80% = 7계명 1번 천장) / `distribution`·`risk_off`·`vix_panic` → 하향. → 강세장 추종 + 위험장 자동 보수.
  밴드 예시(튜닝 SLOT): bull 70-80% / neutral 55-65% / distribution·risk_off 40-50% / vix_panic 방어(신규 진입 게이트, INFRA-US-MACRO mirror).

<!-- SPEC:INTERVIEW-SLOT role="sizing-numeric-tuning" -->
R 값(1%/1.5%)·R 배수 상한·regime 배포 밴드 구체 수치 = 다일 누적 후 튜닝. 백테스팅 친화(cutoff_date) 전제([[feedback_backtest_essence]]). regime↔밴드 매핑 source = MarketView(entry_posture) + us_macro_snapshot(risk_on/off).
<!-- /SPEC:INTERVIEW-SLOT -->

### 분할매수 = 과열도(extension) 함수 — 확정

차수·차당 비중을 **타점 품질(과열도·anchor 지지)** 의 함수로. 사용자 직관: "고점이면 소액 분할, 좋은 타점이면 초반부터 비중 실어 평단 머리 안 무겁게."
입력 = 이미 라이브인 **WAVE-ALPHA 과열도(extension_score)·anchor 지지** (`collectors/anchors.py`).

- **좋은 타점 (저과열 · anchor 지지 근처)** → **front-load** (예 1차 60 / 2차 30 / 3차 10%). 초기 비중 무겁게.
- **고점 (고과열)** → **back-load 소액** (예 20 / 30 / 50%) 또는 진입 보류.
- Track A 보수(넓은 분할) / Track B 빠른 진입(좁은 분할) 차등은 R(레버1) 차이로 자연 반영.

<!-- SPEC:INTERVIEW-SLOT role="split-entry-numeric" -->
과열도 구간↔front/back 분할 비율 매핑 테이블 구체 수치 = 다일 튜닝. extension_score breakpoint 와 정렬. 박종훈 3년 평균가 시그널(I6) 을 anchor 지지 보조로 인용할지 결정.
<!-- /SPEC:INTERVIEW-SLOT -->

### 7계명 게이트 = 자동 축소 기본 + 손절 누락만 하드 차단 — 확정

- **비중 한도 초과 = 자동 축소** (차단 아님). 총 80% / 단일 15% / 트레이딩(단기 계좌) 20% 초과 시 **한도까지 비중을 깎아 통과** + 축소 사유 기록.
- **손절(stop_loss) 누락 = 하드 차단** (유일한 차단 케이스). 이유 ① 7계명 4번 위반 ② 레버1 리스크 역산이 stop 없이는 *수량 계산 불가*. → 진입 거부 + 사유.
- 위반·축소 사유는 production 답변 친화 자연어로 노출 (코드 라벨 금지, [[feedback_production_answer_brevity]]).

<!-- SPEC:INTERVIEW-SLOT role="gate-edge-detail" -->
복수 한도 동시 초과 시 축소 우선순위(단일 15% → 트레이딩 20% → 총 80% 순?). 축소가 1차 분할 금액을 0 으로 만들 때 처리. 사유 메시지 톤/번역 사전.
<!-- /SPEC:INTERVIEW-SLOT -->

### 계좌 상태 스냅샷 — 경계 확정

- 비중 산정 입력 = 계좌 상태(가용 현금·기존 보유·누적 비중). source = `account_state`/`account_positions` 테이블(본 SPEC 가 스키마 정의, RB-MS2 가상매매가 기록·갱신).
- **닭-달걀 해소**: MS1(본 SPEC)이 *지시*(position-sizing-v1) 산출 → MS2 가 가상 체결로 *기록* → MS1 다음 호출 시 그 기록을 *스냅샷*으로 read. MS1 단독 1차에선 초기 시드(계좌당 1000만, 보유 0)로 부트스트랩.
- 산정은 결정론 + 계좌 상태 read 만 — import 금지, DB 경유([[agent_architecture_pattern]]).

<!-- SPEC:INTERVIEW-SLOT role="state-schema-detail" -->
account_state / account_positions 테이블 컬럼 확정(가상 체결 평단·수량·차수·실현/평가손익). MS2 PAPER-TRADING-001 과 스키마 소유 경계(본 SPEC 가 정의 → MS2 가 write). 환율 스냅샷(원/달러) 저장 위치.
<!-- /SPEC:INTERVIEW-SLOT -->

## MVP 범위 (인터뷰 2026-06-09 확정 = 풀)

1차 = **비중(레버1·2) + 분할매수(과열도 함수) + 환율(미장) + 엣지 케이스** 전부 포함. 후속 SLOT = 수치 튜닝뿐.

## 엣지 케이스 (1차 포함 — 처리 방침 확정, 디테일 SLOT)

- **4계좌 전부 한도 소진** → 신규 권고는 "여력 없음" 반려 + 사유(축소가 0 비중 산출).
- **Both(A+B) 권고 동일 종목** → 중장기 계좌(A)·단기 계좌(B)에 각 트랙 R 로 분리 배분 (단일 15% 한도는 계좌별 독립).
- **미장 계좌 환율** → 원/달러 스냅샷으로 1000만 시드 달러 환산 후 산정. 환율 source = 기존 수집 자산(시장 스냅샷 원/달러) 재사용.
- **stop_loss 누락** → 하드 차단(위 게이트) + 왼쪽 뇌(전략가) 피드백 경로.

<!-- SPEC:INTERVIEW-SLOT role="edge-detail" -->
각 엣지의 사유 메시지 문구·환율 스냅샷 시점(장중 vs 일배치)·Both 배분 시 합산 노출 한도(한 종목 양 계좌 합 비중 상한) 디테일.
<!-- /SPEC:INTERVIEW-SLOT -->

## 비목표

- 실 KIS 주문 (roadmap 범위 밖).
- 가상 체결 *기록* (RB-MS2 PAPER-TRADING-001 의 영역 — 본 SPEC 은 *지시*까지).
- 채점·복리 (RB-MS3/MS4).
