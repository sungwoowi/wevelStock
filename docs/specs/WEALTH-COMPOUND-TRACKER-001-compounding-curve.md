---
spec_id: WEALTH-COMPOUND-TRACKER-001
title: 복리 추적 — 실현손익 누적 → 자산 곡선·복리 목표 대비 진척
team: account_manager
type: feature
status: implementing
version: 1
level: implementation
parent: RIGHT-BRAIN-COMPLETION-001
owner: account_manager
generates:
  - core/account/compounding.py                  # 매일 자산 스냅샷 + 통합 자산 곡선 + 복리 목표 진척
  - server/api/wealth.py                          # GET /api/wealth/curve, /api/wealth/progress
modifies:
  - core/db/schema.sql                           # v15 account_equity_snapshot (date×account PK, 멱등)
  - server/schedulers/jobs/daily_refresh.py      # 데스크 후 매일 자산 스냅샷 합류
  - server/main.py                               # wealth 라우터 등록
  - server/telegram/                             # `/wealth` 자산 곡선 명령
depends_on:
  - PAPER-TRADING-001 (account_fills 실현손익 + holdings 미실현 — 자산 곡선 입력)
  - GUIDANCE-ACCURACY-TRACKER-001 (benchmark.py 재사용 — 지수 대비)
  - RIGHT-BRAIN-COMPLETION-001 (소속 roadmap — RB-MS4 마지막 자식)
contracts:
  - name: equity-snapshot-v1
    version: "1.0"                               # 본 SPEC 신규 — 일별 계좌 자산 스냅샷 구조
---

# WEALTH-COMPOUND-TRACKER-001 — 복리 추적 (RB-MS4)

> **RIGHT-BRAIN-COMPLETION-001 의 넷째 자식 (RB-MS4, 마지막).** 채점(RB-MS3) 데이터 위.
> INTERVIEW-SLOT 채움 완료 (2026-06-09 spec-interview). **자산 곡선 = 매일 자산 스냅샷(going-forward MtM)**.

## 목적

북극성 4번 "자산을 복리로 불리는 시스템 자동화" 의 *추적·가시화* 절반. 가상 체결의 실현손익을 누적해 **4계좌 통합 자산 곡선** 과 **복리 목표 진척**(GUIDANCE-ACCURACY-TRACKER 의 1억→2.3억/5년·연 18% MDD -8%)을 보여준다.
자산복리부 canon(`wealth_compounding/`, 통화 3·사이클 5·생존 6룰)의 *판단* 은 wealth_strategist(왼쪽 뇌) 영역 — 본 SPEC 은 *실현 결과 추적*.

## 경계 (roadmap 상속)

- **가상 계좌 기준** 실현손익 누적 (실 자산 아님).
- 복리 *판단·전략* (언제 비중 늘릴지)은 왼쪽 뇌(wealth_strategist) — 본 SPEC 은 추적·곡선·목표 대비.

## 판단/추적 로직 (INTERVIEW-SLOT — 채움 완료 2026-06-09)

> **핵심 구분(사용자 통찰)**: ① 오늘 평가(쉬움) ② **오늘부터 매일 한 점씩 스냅샷(싸다=MVP)** ③ 과거 매일 평가 소급(가격 시계열 필요=비쌈=SLOT). 매일 스냅샷은 비싼 게 아님 — 그날 종가 한 번이면 됨.

<!-- SPEC:INTERVIEW-SLOT role="equity-curve" -->
**자산 곡선 = 매일 자산 스냅샷 (going-forward 마크투마켓)**:
- 데스크가 매일 도는 끝(run_daily_refresh)에 **계좌별 총자산 한 줄 저장** → `account_equity_snapshot`(date×account PK, ON CONFLICT REPLACE 멱등).
- `equity = seed_krw + 누적 실현손익(account_fills sell) + 미실현(holdings 오늘 종가 평가)`. cash·deployed_weight 동반.
- **곡선 = 두 시리즈**(사용자 요청): ① `realized_equity` = seed+누적 실현(확정·보수) / ② `equity` = +미실현(마크투마켓). 차이 = 평가뿐인 미실현분.
- **곡선 데이터** = 스냅샷 시계열 read(4계좌 통합 또는 계좌별). 첫 스냅샷의 realized_cum 이 이미 직전 모든 실현 포함.
- **MDD** = 곡선 최대낙폭(고점 대비). 벤치마크 = RB-MS3 `benchmark.py` 재사용, 시작~현재 지수 수익률 한 줄(알파, 곡선과 정렬).
- **SLOT(비쌈)**: 과거 *매일* 평가 소급(보유 종목 과거 가격 시계열) / 일·주·월 고정 롤업.
<!-- /SPEC:INTERVIEW-SLOT -->

<!-- SPEC:INTERVIEW-SLOT role="compound-target" -->
**복리 목표 진척**: 목표곡선 `target_equity(t) = total_seed × (1+연0.18)^경과연수`(5년 2.3배) vs 실제 총자산.
- `progress_pct`(목표 대비 위치)·`total_return_pct`·`mdd_pct`(목표 -8% 이하 가드 비교)·`alpha_pct`(벤치마크 대비).
- 시작 기준 = 첫 체결일(없으면 첫 스냅샷). **박종훈 framework 사이클 인용 = MVP 제외**(wealth_strategist 왼쪽 뇌 영역, 본 SPEC 은 추적만).
<!-- /SPEC:INTERVIEW-SLOT -->

## 비목표

- 복리 *전략 판단* (wealth_strategist 왼쪽 뇌 영역).
- 채점 KPI (RB-MS3) · 비중·체결 (RB-MS1/MS2).
