---
spec_id: WEALTH-COMPOUND-TRACKER-001
title: 복리 추적 — 실현손익 누적 → 자산 곡선·복리 목표 대비 진척
team: account_manager
type: feature
status: draft
version: 1
level: implementation
parent: RIGHT-BRAIN-COMPLETION-001
owner: account_manager
generates:
  - core/account/compounding.py                  # 4계좌 통합 자산 곡선 + 복리 목표 진척
  - server/api/wealth.py                          # GET /api/wealth/curve, /api/wealth/progress
modifies:
  - server/telegram/                             # `/자산` 복리 곡선 명령
depends_on:
  - PAPER-TRADING-001 (가상 체결·실현손익 — 복리 곡선 입력)
  - GUIDANCE-ACCURACY-TRACKER-001 (채점 KPI — 복리 신뢰도 맥락)
  - RIGHT-BRAIN-COMPLETION-001 (소속 roadmap)
contracts:
  - name: paper-fill-v1
    version: "1.0"                               # PAPER-TRADING-001 정의 (입력)
---

# WEALTH-COMPOUND-TRACKER-001 — 복리 추적 (RB-MS4)

> **RIGHT-BRAIN-COMPLETION-001 의 넷째 자식 (RB-MS4, 마지막).** 채점(RB-MS3) 데이터 위.
> 다음 작업: RB-MS2·MS3 후 `/spec-interview` 로 INTERVIEW-SLOT 채움.

## 목적

북극성 4번 "자산을 복리로 불리는 시스템 자동화" 의 *추적·가시화* 절반. 가상 체결의 실현손익을 누적해 **4계좌 통합 자산 곡선** 과 **복리 목표 진척**(GUIDANCE-ACCURACY-TRACKER 의 1억→2.3억/5년·연 18% MDD -8%)을 보여준다.
자산복리부 canon(`wealth_compounding/`, 통화 3·사이클 5·생존 6룰)의 *판단* 은 wealth_strategist(왼쪽 뇌) 영역 — 본 SPEC 은 *실현 결과 추적*.

## 경계 (roadmap 상속)

- **가상 계좌 기준** 실현손익 누적 (실 자산 아님).
- 복리 *판단·전략* (언제 비중 늘릴지)은 왼쪽 뇌(wealth_strategist) — 본 SPEC 은 추적·곡선·목표 대비.

## 판단/추적 로직 (INTERVIEW-SLOT — 다음 세션)

<!-- SPEC:INTERVIEW-SLOT role="equity-curve" -->
4계좌 통합 자산 곡선 산출(가상 체결 실현 + 평가손익). 시점·롤업(일/주/월) 멱등. MDD 계산. 코스피/미장 벤치마크 곡선 오버레이(RB-MS3 채점과 정렬).
<!-- /SPEC:INTERVIEW-SLOT -->

<!-- SPEC:INTERVIEW-SLOT role="compound-target" -->
복리 목표 진척(연 18%·5년 2.3배·MDD -8% 이하) 대비 현재 위치. 목표 곡선 vs 실제. 박종훈 framework 사이클 단계 맥락 인용 여부.
<!-- /SPEC:INTERVIEW-SLOT -->

## 비목표

- 복리 *전략 판단* (wealth_strategist 왼쪽 뇌 영역).
- 채점 KPI (RB-MS3) · 비중·체결 (RB-MS1/MS2).
