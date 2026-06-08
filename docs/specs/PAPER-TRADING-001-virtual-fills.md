---
spec_id: PAPER-TRADING-001
title: 가상매매 — 비중 지시 → 가상 체결·계좌 책임 추적 (매일 도는 데스크)
team: account_manager
type: feature
status: draft
version: 1
level: implementation
parent: RIGHT-BRAIN-COMPLETION-001
owner: account_manager
generates:
  - core/account/paper_trading.py                # position-sizing-v1 → 가상 체결 기록 (멱등)
  - core/account/holdings.py                     # 계좌별 보유·평가손익·보유기간 조회
  - server/api/accounts.py                       # GET /api/accounts, /api/accounts/{id}/holdings
modifies:
  - core/db/schema.sql                           # account_positions / account_fills / account_state (ACCOUNT-MANAGER-001 정의 스키마 write)
  - server/telegram/                             # `/계좌` 보유현황 명령
depends_on:
  - ACCOUNT-MANAGER-001 (비중 지시 = position-sizing-v1 — 가상 체결 입력)
  - RIGHT-BRAIN-COMPLETION-001 (소속 roadmap — 가상 전용·4계좌 경계 상속)
contracts:
  - name: position-sizing-v1
    version: "1.0"                               # ACCOUNT-MANAGER-001 정의 (입력)
  - name: paper-fill-v1
    version: "1.0"                               # 본 SPEC 신규 — 가상 체결 기록 구조
---

# PAPER-TRADING-001 — 가상매매 (RB-MS2)

> **RIGHT-BRAIN-COMPLETION-001 의 둘째 자식 (RB-MS2).** ACCOUNT-MANAGER-001(RB-MS1) 후속.
> 다음 작업: ACCOUNT-MANAGER-001 구현 완료 후 `/spec-interview` 로 INTERVIEW-SLOT 채움.

## 목적

계좌관리자(RB-MS1)의 비중 *지시*(position-sizing-v1)를 받아 **가상 체결로 기록**하고 계좌 책임을 추적한다.
user_want_spec: "실전 매매는 텔레그램 의견으로 가정 + 가상 계좌별 매매 관리 내역 스키마." 매수가·비중·차수·수익률·보유기간·목표가·실현손익을 기록 → 채점(RB-MS3)·복리(RB-MS4)의 데이터 원천.
"매일 도는 책임지는 데스크" 의 *도는* 부분 = 권고→가상체결 스트림을 매일 누적.

## 경계 (roadmap 상속)

- **가상 전용** — 실 KIS 주문 X. 텔레그램 의견 = 체결 간주.
- ACCOUNT-MANAGER-001 가 정의한 `account_positions`/`account_state` 스키마에 **write** (MS1=정의/read, MS2=write/갱신).

## 핵심 정의 (스켈레톤)

| 용어 | 의미 |
|---|---|
| **가상 체결 (paper fill)** | 비중 지시 1 차수의 가상 매수/매도 기록. `paper-fill-v1`. |
| **보유 (holding)** | 계좌×종목 누적 포지션(평단·수량·차수·비중·보유기간). |
| **매매 마커** | 투자성격(중장기/단기)·예상 보유기간·근거(각 분석가 판단) 기록. |

## 판단/기록 로직 (INTERVIEW-SLOT — 다음 세션)

<!-- SPEC:INTERVIEW-SLOT role="fill-recording" -->
가상 체결가 결정(권고 진입가? 당일 종가? 차수별 지정가 도달 판정?). 멱등 키(권고ID×차수×날짜). 분할 차수 진행(2차/3차 트리거 = 가격 도달 vs 시간). ON CONFLICT REPLACE 멱등.
<!-- /SPEC:INTERVIEW-SLOT -->

<!-- SPEC:INTERVIEW-SLOT role="sell-and-pnl" -->
매도 기록(목표가 3단 도달·stop 히트·trailing). 실현수익/실현수익률/성공·실패 의견. 평가손익 daily 갱신 source(KIS/DB-first 시세). 보유기간 누적.
<!-- /SPEC:INTERVIEW-SLOT -->

<!-- SPEC:INTERVIEW-SLOT role="daily-desk-loop" -->
"매일 도는" 배선 — 일일 cron 이 활성 권고를 가상 체결로 굴리고 보유 평가손익 갱신. run_daily_refresh 3-surface 합류 여부. 알림(매수/매도/계좌 안심) 트리거.
<!-- /SPEC:INTERVIEW-SLOT -->

## 비목표

- 비중 *결정* (RB-MS1 영역 — 본 SPEC 은 지시를 *기록*).
- 채점·KPI (RB-MS3) · 복리 곡선 (RB-MS4).
- 실 KIS 주문 (roadmap 범위 밖).
