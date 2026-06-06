---
spec_id: LEFT-BRAIN-COMPLETION-001
title: 왼쪽 뇌 완성 — 분석·답변 절반의 신뢰성 종결 (roadmap)
team: shared
type: roadmap
level: roadmap          # roadmap = 큰 방향·마일스톤 보유, 코드 직접 생성 X (자식 SPEC이 함)
status: draft
version: 1
owner: production_chat
generates: []           # roadmap SPEC 은 코드를 직접 생성하지 않음. 자식 implementation SPEC 이 generates 를 가짐
children:               # 이 roadmap 아래 매달리는 implementation SPEC (다음다음 디테일)
  - ANSWER-FIDELITY-001          # ① Q1 (지금) — 답변 누수 봉합
  - MARKET-VIEW-SYNTHESIS-001    # ③ Q2 — 순환매 + 시장 타이밍 상시 종합 뷰
  - NEWS-SOURCE-001              # ② Q2 — 뉴스부 (최대 구조 공백, 기존 백로그)
  - INFRA-US-MACRO-SNAPSHOT-001  # ④ Q2 — 미장 매크로 입력 (③ 에 흡수, 기존 백로그)
depends_on:
  - PRODUCTION-UX-001 v1 (답변 포맷터 · intent 라우팅 베이스라인 — 누수 봉합 대상)
  - INFRA-SNAPSHOT-EXTEND-001 (섹터 RS · 매크로 재료 — 종합 뷰 입력)
  - INFRA-SCORE-INPUTS-001 (5 점수 S/T/α/buy/F 라이브 — 분석가 판단 입력)
  - WAVE-ALPHA-001 / SCREEN-RS-EXTENSION-001 (파동 · 주도주 판단, 이미 라이브)
---

# LEFT-BRAIN-COMPLETION-001 — 왼쪽 뇌 완성 (roadmap)

> **이 문서는 roadmap-level SPEC 이다.** 큰 방향과 마일스톤·우선순위만 못 박는다.
> 실제 코드는 `children:` 에 나열된 implementation SPEC (각자 `generates` 보유) 에서 만든다.
> PM (사용자) 은 이 문서로 "지금 어느 마일스톤인가 / 다음은 무엇인가" 를 점검한다.

## 목적 — "왼쪽 뇌 완성" 의 정의

이 프로젝트는 **왼쪽 뇌(오감+뇌: 수집 → 분석가9 → 전략가A/B → 답변)** 와 **오른쪽 뇌(손발+책임: 비중결정 → 가상매매 → 채점 → 복리)** 로 나뉜다.
오른쪽 뇌는 **이후**(별 roadmap)로 미룬다. 본 roadmap = **왼쪽 뇌를 신뢰성 있게 종결**하는 것.

**완성 기준 = 왼쪽 뇌가 사용자 북극성 4 판단을 *새지 않고* 내놓는다:**
①주도주 ②순환매 ③시장 타이밍("지금 들어갈 때냐") ④파동·추세추종.

## 현재 채점표 (2026-06-06)

| 북극성 판단 | 상태 | 막힌 곳 |
|---|---|---|
| 주도주 (Track A·발굴·MA-ride) | ~80% | magnitude 미튜닝 (범위 밖) |
| 파동·추세추종 (WAVE-ALPHA) | ~85% | LLM anchor Stage2 파싱 (폴백 동작 중) |
| **순환매** (섹터 RS) | ~40% | 재료는 있으나 **"돈이 A→B 섹터로 돈다" 종합 판단 부재** |
| **시장 타이밍** (6/5 버블 예시) | ~50% | regime 라벨뿐, **상시 시장관 미종합 + 뉴스부 0 + 미장 매크로 없음** |
| **답변 전달** (formatter) | ~70% | **종목비교·일반질의에서 raw 노출/잘림/코드라벨 누수** |

**한 줄 진단**: 부품은 대부분 있으나 (1) 순환매·시장타이밍이 *종합 판단*으로 안 올라왔고, (2) 만든 판단조차 *답변층에서 샌다*. 왼쪽 뇌 완성 = 이 둘을 닫는 것.

## 마일스톤 (시급도 × 중요도 순서)

| # | 마일스톤 | 자식 SPEC | 우선순위 | 완료 신호 |
|---|---|---|---|---|
| **LB-MS1** | 답변 누수 봉합 — formatter 가 분석가 판단을 raw 노출·잘림·코드라벨 없이 전달 | `ANSWER-FIDELITY-001` | **중요⊗시급 (지금)** | 종목비교·일반질의 실 스모크에서 코드라벨 0 · 잘림 0 · 한 종목만 분석 0 |
| **LB-MS2** | 시장관 종합 — 섹터 RS·regime·매크로를 *상시 시장관 한 줄* 로 종합 (순환매 + "지금 들어갈 때냐") | `MARKET-VIEW-SYNTHESIS-001` (+ `INFRA-US-MACRO-SNAPSHOT-001` 입력) | 중요⊗비시급 (계획) | 묻기 전에도 "현재 regime + 주도 섹터 + 순환 방향 + 진입 자세" 1 줄 상존 |
| **LB-MS3** | 뉴스부 — 장기/단기 이슈 수집·해석을 시장관과 buy_score N 축에 공급 | `NEWS-SOURCE-001` | 중요⊗비시급 (가장 무거움, 마지막) | 6/5 형 "버블 붕괴냐 조정이냐" 내러티브를 LB-MS2 시장관이 인용 · buy_score N 축 7/7 라이브 |

> LB-MS1 → LB-MS2 → LB-MS3 순. LB-MS2 는 뉴스(LB-MS3) 없이도 *지금 있는 재료*(섹터 RS·regime·매크로)로 먼저 골격을 세우고, 뉴스는 나중에 이 종합자에 먹인다.

## 자식 SPEC 상태판

| 자식 SPEC | level | status | 비고 |
|---|---|---|---|
| `ANSWER-FIDELITY-001` | implementation | implementing | LB-MS1. **F1 raw누수+F2 근거축가변 ✅ 라이브 검증** / F3 비교 양종목 ⏳(classifier dual-ticker) |
| `MARKET-VIEW-SYNTHESIS-001` | implementation | (미작성) | LB-MS2. LB-MS1 후 |
| `INFRA-US-MACRO-SNAPSHOT-001` | implementation | 백로그 | LB-MS2 입력 (③에 흡수) |
| `NEWS-SOURCE-001` | implementation | 백로그 (방향성 합의됨) | LB-MS3. `/spec-interview` 필요 |

## 범위 밖 (의도적 — 함정 회피)

- **magnitude 튜닝** (k_below/MA-ride) — universe 다일 누적 전제 미충족 + 한계효용. "시급해 보이는 함정", 보류.
- **오른쪽 뇌 전체** (비중관리 Layer4 · 가상매매 · 채점 루프 · 복리) — 왼쪽 뇌 완성 후 별 roadmap (`RIGHT-BRAIN-*`).
- KIS rate limiter 전역화 / regime 히스테리시스 / validate cp949 — 비차단 백로그.

## 완료 정의 (Definition of Done)

LB-MS1·MS2·MS3 모두 완료 = 왼쪽 뇌가 북극성 4 판단을 신뢰성 있게 발행. 이 시점에 본 roadmap `status: done`, 오른쪽 뇌 roadmap 착수.
