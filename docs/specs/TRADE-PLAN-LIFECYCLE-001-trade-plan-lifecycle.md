---
spec_id: TRADE-PLAN-LIFECYCLE-001
title: 트레이드 플랜 생애주기 — 대기진입·분할매수·손절·목표·분할매도가 시계열로 진화하는 살아있는 플랜 + 알림
team: shared
type: feature
level: implementation
status: draft
parent: BRAIN-QUALITY-001
generates: []        # 설계 SPEC (구현 0). 단계별 구현 시 generates 확정.
modifies: []         # 단계별 확정. 재사용 우선(아래 재사용 영향도).
contracts:
  - name: strategist-recommendation-v1   # team_outputs, 기존 — 플랜 필드 가산 확장 후보
    version: "1.0"
depends_on:
  - BRAIN-QUALITY-001 (parent roadmap)
  - BRAIN-ALPHA-FLEXIBILITY-001 (조건부 진입가 = 본 SPEC 2단계로 이관 — verdict 후보가 플랜의 시작점)
  - PAPER-TRADING-001 (분할 사다리·체결·손익 = sizing/paper_trading 재사용)
  - GUIDANCE-ACCURACY-TRACKER-001 (트리거별 과거 승률 = 적중률 추적과 연결)
  - WAVE-ALPHA-001 (앵커 가격·목표가 proxy)
---

# TRADE-PLAN-LIFECYCLE-001 — 트레이드 플랜 생애주기 (설계 SPEC)

> **설계 전용 (코드 0).** 2026-06-15 "관망 조건부 진입가" 논의가 더 큰 그림으로 자라남. 비전 + 핵심
> 원칙 + 5단계 로드맵을 박아 큰 그림을 보존하고, 다음 세션부터 단계별로 구현한다.

## 문제 / 동기
현재 권고는 buy 시 **단일** entry/stop/target 만, wait 는 심볼릭 조건부 진입(숫자 없음). 그러나 실전
매매 계획은 **여러 가격대(다단 지지/저항)·여러 액션(분할 매수/매도)·상황별 대응(목표 도달 시 trailing vs
매도)** 이 **시간에 따라 진화**한다. 사용자 의도: "목표가·손절가·분할매수가·분할매도가·대기 진입가를
시계열로 통찰력 있게 전략을 짜고, 목표는 시장이 예상 못한 방향이면 변경하며, 데이터로 정하고 알림까지."

## 핵심 설계 원칙 (2026-06-15 논의로 확정 — 이 SPEC 의 뼈대)
**결정론 = 후보 메뉴·신호 *계산기* / 판단(LLM·룰) = *선택·임계·수정*. 모든 레벨에 동일.**
- 결정론은 **절대 결정자가 아니다.** "여기 후보들이 있다"까지만: 스윙 저점 12,300 / ATR손절 12,100 /
  ma60 이탈 11,800 / MDD−10% 11,500 + 신호(이평 차례 꺾임 = 참/거짓). 객관적·재현 가능.
- 판단은 "이 상황(추세 초기·주도주)엔 ma60 이탈을 손절로, MDD −10%까지 허용" = **적재적소 선택 + 임계 + 수정.**
- 따라서 **"결정론이 모든 상황을 타이트하게 맞춰야 하나"의 답은 영원히 아니오** (사용자 우려 해소). 손절도
  단일 공식 아님 — 후보가 *많고 객관적*일 뿐. 목표는 후보가 *적고*(measured-move proxy) 수정이 잦다.
- = "가드레일 있는 C"(BRAIN-ALPHA-FLEXIBILITY)의 일반화: 결정론 후보 → LLM 이 사실 근거로 선택·수정·로그.

## 모델 — (종목 × 트랙)당 살아있는 트레이드 플랜
```
상태:  대기(watching) ─▶ (분할)진입(entering) ─▶ 보유(holding) ─▶ (분할)청산(exiting) ─▶ 종료
레벨:  대기진입가 · 분할매수가[] · 손절가 · 목표가[] · 분할매도가[]   (각 = 후보 메뉴 + 선택)
진화:  매 cadence 재평가 → 변동 시 수정 + 사유 로그(목표 동적 변경 포함) → 레벨 도달 시 알림
```
- **스냅샷 아니라 시계열 객체** — 버전 이력 보존(언제·왜 바뀌었나).
- **목표가 도달 ≠ 자동 매도** (prism 차용): regime 조건부 — 강세장 = trailing 전환·보유 / 약세장 = 도달 즉시 전량.

## 산출물 목표 형태 (prism 트레이드 시나리오 리포트 차용, 2026-06-15 사용자 제공)
- **핵심 가격대 다단**: 저항 1·2차 / 현재가 / 지지 1·2차 (단일 아님 = 후보 메뉴 확증).
- **매도 시그널 세트**: ⏰목표=마일스톤(regime 조건부 trailing/매도) · 추세약화 **multi-condition AND**(종가 20일선 이탈 ∧ 거래량 동반 ∧ 섹터 약세 中 2+) · ⛔하드스탑(**종가 기준**·장중 wick 무시) · 오닐 **−7% 절대** · 시간점검(트리거 아님).
- **보유 지속 조건**: 종가 stop 위 + 20일선 회복 / 섹터 주도 유지 / 수급 유지.
- **트리거별 과거 승률** (예 50%·18건) → 적중률(GUIDANCE-ACCURACY·북극성)과 연결.
- **투자근거 + 매매일지 반영** (cited 점수·regime·R/R + 과거 경험).

## 5단계 로드맵 (쉬운·결정론 → 어려운·동적, 각 단계 독립 가치)
- **1단계 — 손절 + 분할매수 레벨 (후보 메뉴)**: `extract_swing_candidates`(스윙 저점)·`compute_indicators`(ma20/60/120)·`_atr` 로 후보 메뉴 계산 → buy 권고에 다단 실제 숫자. 분할 사다리는 sizing/paper_trading 재사용. <!-- SPEC:INTERVIEW-SLOT name="stop-buy-level-menu" 후보 메뉴 공식·선택 규칙(추세초기/주도주별)·종가기준·−7% 절대 -->
- **2단계 — 대기(관망) 진입가** (BRAIN-ALPHA-FLEXIBILITY 조건부진입 이관): 눌림 분할 / 돌파 / 추세 하단 **방법 선택** + 가격. <!-- SPEC:INTERVIEW-SLOT name="waiting-entry-method" 방법 선택 규칙(과열→눌림·박스→돌파·정석→추세하단)·각 가격 기준 -->
- **3단계 — 목표 + 분할매도**: measured-move(anchor B 거리) 결정론 후보 + **LLM 수정** + 분할매도 비중. 목표 도달 시 regime 조건부 대응. <!-- SPEC:INTERVIEW-SLOT name="target-sell" 목표 후보·동적 수정 규칙·분할매도 비중·매도 AND 조합 -->
- **4단계 — 시계열 진화**: 플랜 영속·매 cadence 갱신·목표 동적 수정·수정 사유 로그·보유 지속 조건 점검. <!-- SPEC:INTERVIEW-SLOT name="evolution-model" 전체재계산 vs 델타수정·surprise 정의·이력 보존 -->
- **5단계 — 알림**: 레벨 도달(대기진입·목표·손절) 감지·발송. <!-- SPEC:INTERVIEW-SLOT name="alert-trigger" 도달 감지(cadence vs 실시간)·알림 종류·종가 기준 -->

## 재사용 영향도 (가드 #11, DATA-MAP 확인)
- **재사용(신규 0)**: `collectors/anchors.py extract_swing_candidates`(스윙 다단)·`collectors/charts.py compute_indicators`(MA)·`collectors/technicals.py _atr`/`compute_rr`(직전 저점·인근 고점)·`core/strategist/recommendation.py`(entry/stop/target)·`core/account/sizing.py`·`paper_trading.py`(분할 사다리·체결)·`core/notification`(알림).
- **플랜 영속 = SLOT(신규 테이블 미확정)**: 진화하는 플랜을 `team_outputs.data_json` 가산 확장 vs 신규 `trade_plan` 테이블 — 4단계 구현 시 DATA-MAP 재확인 후 결정(현재 신규 금지, 확장 우선 검토).
- **트리거 승률**: `account_fills`·GUIDANCE-ACCURACY-TRACKER 집계 재사용(신규 추적 X).
- 3층 파급: DB(가산 우선) → backend(strategist·desk·notification) → frontend(데스크가 플랜 표시 — PAPER-DESK-UX 연계).

## 완료 정의 (잠정)
buy·wait 권고가 단일 가격이 아니라 **다단 레벨 + 상황별 액션 플랜**을 갖고, 매 cadence **진화**(목표 동적
수정 포함)하며, 레벨 도달 시 **알림**이 오고, 각 플랜이 **트리거 승률**로 사후 평가된다. = prism 리포트급
시나리오를 *스스로* 생성·갱신.

## 비고
- 본 SPEC 은 **설계 골격** — 단계별 구현 시 각 INTERVIEW-SLOT 을 `/spec-interview` 또는 직접 확정.
- 1·2단계는 결정론 비중↑(레벨), 3·4단계에서 LLM 판단·수정↑(목표 동적), 5단계는 배선. 한 번에 다 하지 않음.
