---
spec_id: PROJECT-NORTH-STAR-001
title: 프로젝트 북극성 — 최상위 마스터 roadmap (모든 roadmap 의 뿌리)
team: shared
type: roadmap
status: implementing
level: roadmap
generates: []
children:
  - LEFT-BRAIN-COMPLETION-001     # 왼쪽 뇌 (분석·답변) — 완료 4/4 (done)
  - RIGHT-BRAIN-COMPLETION-001    # 오른쪽 뇌 (비중·가상매매·채점·복리) — 착수 (2026-06-09)
depends_on: []
---

# PROJECT-NORTH-STAR-001 — 프로젝트 북극성 (마스터 roadmap)

> **이 문서는 트리의 뿌리(root roadmap)다.** 모든 roadmap 이 이 아래 매달린다.
> `scripts/project_status.py` 가 이 뿌리부터 단계 지도를 그린다. 세션마다 `/resume`·`/wrap-up`
> 이 이 지도를 읽어 "지금 전체 단계 중 어디인가 / 딴 데로 새는가" 를 점검한다.

## 북극성 (사용자 최종 4목표, user_want_spec.md)

1. **주도주를 강력하게 이익 먹기** (Track A 중장기 주도주)
2. **주도주 쉬는 구간엔 월 인컴처럼 트레이딩** (Track B 단기 손익비)
3. **프랙탈 파동 매매 / 추세추종이 기초** (WAVE-ALPHA + MA-ride momentum_leaders)
4. **자산을 복리로 불리는 시스템 자동화** (wealth_compounding + 계좌관리 Layer4)

이를 위해 시스템은 항상 5판단을 내야 한다: ①주도주 ②순환매 ③시장 타이밍 ④비중 ⑤채점된 신뢰도.

## 두 기둥 (좌/우 뇌)

| 기둥 | roadmap | 정의 | 상태 |
|---|---|---|---|
| 🧠 왼쪽 뇌 | `LEFT-BRAIN-COMPLETION-001` | 오감+뇌: 수집 → 분석가9 → 전략가A/B → 답변. 북극성 4판단을 *새지 않고* 발행 | **완료 4/4 (done, 2026-06-09)** |
| ✋ 오른쪽 뇌 | `RIGHT-BRAIN-COMPLETION-001` | 손발+책임: 비중결정(Layer4) → 가상매매 → 시장대비 채점 → 복리추적 | **착수 (2026-06-09, 첫 자식 ACCOUNT-MANAGER-001)** |

> 순서 = 왼쪽 뇌 먼저 완성(신뢰성 있는 판단) → 오른쪽 뇌(그 판단을 실행·채점). 둘이 다 서야 "실전 도움" 선을 넘는다.

## 단계 점검 규칙 (drift 감시)

- `scripts/project_status.py` 가 이 트리를 읽어 **파생 진행도**(자식 SPEC done/total)와 **ACTIVE 작업**(status=implementing), **roadmap 밖 미완 SPEC**(drift 후보)을 출력한다.
- `/resume` 시작 시: 지도를 보여주고 "오늘 작업이 ACTIVE 단계에 맞나" 확인.
- `/wrap-up` 끝에: 이번 세션이 어느 마일스톤을 전진시켰는지 기록 + roadmap 밖으로 샜으면 경고.
- **drift 판정은 사람/LLM 추론** (스크립트는 지도·후보만 제공, 게이트 아님).

## 완료 정의

왼쪽 뇌 + 오른쪽 뇌 roadmap 모두 `done` = 북극성 5판단을 신뢰성 있게 발행하고 채점까지 도는 시스템. 이 시점에 본 마스터 `status: done`.
