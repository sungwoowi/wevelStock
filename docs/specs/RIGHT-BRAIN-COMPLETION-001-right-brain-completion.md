---
spec_id: RIGHT-BRAIN-COMPLETION-001
title: 오른쪽 뇌 완성 — 비중·가상매매·채점·복리 (책임지는 페이퍼 트레이딩 데스크) (roadmap)
team: shared
type: roadmap
level: roadmap          # roadmap = 큰 방향·마일스톤 보유, 코드 직접 생성 X (자식 SPEC이 함)
status: draft
version: 1
owner: account_manager
generates: []           # roadmap SPEC 은 코드를 직접 생성하지 않음. 자식 implementation SPEC 이 generates 를 가짐
children:               # 의존 사슬 순서. 전부 스켈레톤 draft (2026-06-09 인터뷰).
  - ACCOUNT-MANAGER-001          # RB-MS1 — 비중 결정 (Layer 4 계좌관리자). 첫 자식, 판단 로직 확정
  - PAPER-TRADING-001            # RB-MS2 — 가상매매 스키마 (스켈레톤)
  - GUIDANCE-ACCURACY-TRACKER-001  # RB-MS3 — 코스피/미장 대비 채점 (기존 draft, 본 roadmap 편입)
  - WEALTH-COMPOUND-TRACKER-001  # RB-MS4 — 복리 추적·곡선 (스켈레톤)
  - PAPER-DESK-UX-001            # RB-MS5 — 페이퍼 데스크 webapp UI (시황·가상매매·계좌 상세, 1차). 화면 차단점 해소 (draft 2026-06-12)
  - INFRA-MARKET-ASSETS-002      # RB-MS5 지원 인프라 — 자산군 수집(WTI·브렌트·야간선물) + 알림 영속(notifications_log type·is_read). 시황 자산군·알림 탭 백엔드 (draft 2026-06-12)
depends_on:
  - LEFT-BRAIN-COMPLETION-001 (왼쪽 뇌 4/4 완성 — 신뢰성 있는 판단 발행이 전제)
  - STRATEGY-TRACK-001 (전략가 권고 = strategist-recommendation-v1 — 비중 변환 입력)
---

# RIGHT-BRAIN-COMPLETION-001 — 오른쪽 뇌 완성 (roadmap)

> **이 문서는 roadmap-level SPEC 이다.** 큰 방향과 마일스톤·우선순위만 못 박는다.
> 실제 코드는 `children:` 에 나열된 implementation SPEC (각자 `generates` 보유) 에서 만든다.
> PM (사용자) 은 이 문서로 "지금 어느 마일스톤인가 / 다음은 무엇인가" 를 점검한다.
> `PROJECT-NORTH-STAR-001` 의 두 번째 기둥(✋ 오른쪽 뇌). 왼쪽 뇌(`LEFT-BRAIN-COMPLETION-001`, done) 다음.

## 목적 — "오른쪽 뇌 완성" 의 정의

이 프로젝트는 **왼쪽 뇌(오감+뇌: 수집 → 분석가9 → 전략가A/B → 답변)** 와 **오른쪽 뇌(손발+책임: 비중결정 → 가상매매 → 채점 → 복리)** 로 나뉜다.
왼쪽 뇌는 4/4 완성(`LEFT-BRAIN-COMPLETION-001` done) — 북극성 4판단을 *새지 않고* 발행한다.
본 roadmap = **그 판단을 실행·책임으로 잇는** 절반. 사용자 본질 = **"매일 도는 책임지는 페이퍼 트레이딩 데스크"**.

**완성 기준 = 왼쪽 뇌의 권고가 손발·책임으로 이어진다:**
⑤비중(권고→자금액) → ⑥가상매매(자금액→가상 체결·계좌 책임 추적) → ⑦채점(체결·권고 vs 코스피/미장 지수) → ⑧복리(실현손익 누적·곡선).

> 북극성 5판단 중 ④비중 + 채점된 신뢰도(⑤) 가 여기서 닫힌다. 왼쪽 뇌(①주도주 ②순환매 ③시장 타이밍 ④파동) + 오른쪽 뇌 = 5판단 전부 발행 + 채점.

## 경계 결단 (인터뷰 2026-06-09, 영구)

1. **가상(페이퍼) 전용 — 실 KIS 주문은 범위 밖.** user_want_spec 명시: "실전 매매는 사실 사람이 하는 것이고, 텔레그램에 매수/매도/홀딩 의견을 주는 것으로 매매한 것으로 가정." 가상 계좌 스키마로 **책임 추적**만. KIS 실주문(`KIS_IS_PAPER`)은 후속 별 roadmap (범위 밖, 함정 회피).
2. **4 계좌 모델** = 국장 중장기 / 국장 단기 / 미장 중장기 / 미장 단기. 계좌당 1000만원. Track A(중장기, 자본 70-80%) / Track B(단기, 자본 20-30%) 매핑.
3. **채점 벤치마크 = 코스피(국장 계좌) + S&P500/나스닥(미장 계좌) + 트랙별 가중치.** 초과수익(알파)을 트랙 본질(A 수익금 게임 / B 손익비 게임)에 맞춰 차별 가중.
4. **투자 7계명이 비중의 하드 제약.** 총 비중 80% 이하 / 단일 종목 15% 이하 / 트레이딩 비중 20% 이하 / 손절선 없이 진입 X. 계좌관리자가 권고→비중 변환 시 이 한도를 강제.

## 마일스톤 (의존 사슬 = 시급도 순서)

| # | 마일스톤 | 자식 SPEC | 우선순위 | 완료 신호 |
|---|---|---|---|---|
| **RB-MS1** | **비중 결정 (Layer 4 계좌관리자)** — 전략가 권고 → 4계좌별 자금액·종목비중·분할매수 차수. 7계명 한도 강제 | `ACCOUNT-MANAGER-001` (첫 자식) | 시급⊗중요 (사슬의 머리, 가상매매·채점의 전제) | `swing:`/`long:` 권고 → 계좌·자금액·비중·차수 산출 + 7계명 위반 시 차단/축소 |
| **RB-MS2** | 가상매매 (페이퍼 트레이딩 스키마) — 비중 → 가상 체결 기록(매수가·비중·차수·수익률·보유기간·목표가). 매일 도는 데스크 | `PAPER-TRADING-001` (SPEC 대기) | 중요⊗RB-MS1 후 | 권고 → 가상 체결 row 멱등 적재 + 계좌별 보유 현황·평가손익 조회 |
| **RB-MS3** | 채점 (코스피/미장 대비 5 KPI) — 권고·체결을 벤치마크 대비 추적, 트랙별 가중 | `GUIDANCE-ACCURACY-TRACKER-001` (기존 draft) | 중요⊗비시급 (캘린더 누적 long-pole, 데스크 가동 후 채워짐) | `회고` → 30/60/90일 5 KPI + 코스피/미장 대비 알파 |
| **RB-MS4** | 복리 추적 (자산 곡선·복리 목표) — 실현손익 누적 → 복리 곡선·연 18% 목표 대비 | `WEALTH-COMPOUND-TRACKER-001` (SPEC 대기) | 중요⊗마지막 (RB-MS3 채점 데이터 위) | 계좌 통합 자산 곡선 + 복리 목표(1억→2.3억/5년) 대비 진척 |

> RB-MS1 → RB-MS2 → RB-MS3 → RB-MS4 순. 의존 사슬: 비중 없이 수량 산정 불가 → 가상매매 없이 매일 권고 스트림 누적 불가 → 누적 없이 채점 grounding 0 → 채점 없이 복리 곡선 의미 0.
> RB-MS3(채점)·RB-MS4(복리)는 **캘린더 누적**(30/60/90일)이 필요한 long-pole — 그래서 데스크(RB-MS1·MS2)를 먼저 세워 *매일 권고→가상체결 스트림*을 만들고, 그 위에서 채점·복리가 자란다.

## 자식 SPEC 상태판

| 자식 SPEC | level | status | 비고 |
|---|---|---|---|
| `ACCOUNT-MANAGER-001` | implementation | **implementing** | RB-MS1. 2026-06-09 **SDD 구현 완료**(generates 6파일: sizing.py 두 레버+게이트 / portfolio.py / accounts.yaml / schema v13 / persona·manifest + render + probe + 38 테스트, 1027 passed). 남은 것 = production_chat 배선(Layer3→Layer4, RB-MS2와 묶음) + 수치 캘리브레이션 |
| `PAPER-TRADING-001` | implementation | draft (스켈레톤) | RB-MS2. 가상 체결·계좌 책임 추적. INTERVIEW-SLOT(체결가·매도/손익·매일 데스크 루프). RB-MS1 구현 후 채움 |
| `GUIDANCE-ACCURACY-TRACKER-001` | implementation | draft | RB-MS3. 기존 백로그 draft(5 KPI). 본 roadmap 으로 편입(parent 연결) — drift 해소. 채점 벤치마크에 미장 지수(S&P/나스닥) 추가 정렬 필요 |
| `WEALTH-COMPOUND-TRACKER-001` | implementation | draft (스켈레톤) | RB-MS4. 복리 곡선·목표 진척. INTERVIEW-SLOT(자산곡선·복리목표). RB-MS3 후 채움 |

## 범위 밖 (의도적 — 함정 회피)

- **실 KIS 주문 실행** (`KIS_IS_PAPER` 주문 배선) — 가상 책임 추적이 본질. 실주문은 후속 별 roadmap.
- **계정 관리(멀티 유저)·매매일지 AI 피드백** — user_want_spec "향후 추가" 항목. 오른쪽 뇌 완성 후.
- **Layer 5 회고분석가 PROPOSAL 발행** (`RETROSPECT-ANALYST-001`) — 채점(RB-MS3) 데이터를 *입력*으로 쓰는 자가 진화. 별 roadmap.
- **magnitude 튜닝 / KIS rate limiter 전역화 / regime 히스테리시스** — 비차단 백로그(왼쪽 뇌에서 이월).

## 완료 정의 (Definition of Done)

RB-MS1·MS2·MS3·MS4 모두 완료 = 왼쪽 뇌 권고가 비중→가상체결→채점→복리로 닫혀 **매일 도는 책임지는 페이퍼 트레이딩 데스크** 가동. 이 시점에 본 roadmap `status: done` → 마스터 `PROJECT-NORTH-STAR-001 status: done` (5판단 신뢰 발행 + 채점까지 도는 시스템).
