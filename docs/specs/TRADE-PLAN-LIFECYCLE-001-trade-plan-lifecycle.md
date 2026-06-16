---
spec_id: TRADE-PLAN-LIFECYCLE-001
title: 트레이드 플랜 생애주기 — 대기진입·분할매수·손절·목표·분할매도가 시계열로 진화하는 살아있는 플랜 + 알림
team: shared
type: feature
level: implementation
status: implementing
parent: BRAIN-QUALITY-001
generates:           # 1단계(B-MS1) 산출.
  - core/signal/trade_plan_menu.py
  - tests/test_trade_plan_menu.py
modifies:            # 1단계(B-MS1) 수정 — 재사용 우선(아래 재사용 영향도).
  - core/strategist/run_strategist.py
  - core/strategist/recommendation.py
  - core/signal/auto_signal.py
  - collectors/screening.py
  - config/screening.yaml
  - agents/strategists/track_a/persona.md
  - agents/strategists/track_b/persona.md
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
단계:  관심(interest) ─▶ 매수대기(watching) ─▶ 진입/buy(entering) ─▶ 보유(holding) ─▶ 청산(exiting) ─▶ 종료
레벨:           대기진입가 · 분할매수가[] · 손절가 · 목표가[] · 분할매도가[]   (각 = 후보 메뉴 + 선택)
진화:  매 cadence 재평가 → 단계 승격/강등 + 변동 시 수정 + 사유 로그 → 레벨 도달 시 알림
```
- **스냅샷 아니라 시계열 객체** — 단계·레벨의 버전 이력 보존(언제·왜 바뀌었나).
- **단계 = 상태지 강제 순서 아님** — 종목이 현시점에 부합한 단계로 진입(핫한 모멘텀주는 관심→바로 buy, 바닥 다지는 주는 매수대기에 머묾). 꼭 3단계를 다 거칠 필요 없다.
- **목표가 도달 ≠ 자동 매도** (prism 차용): regime 조건부 — 강세장 = trailing 전환·보유 / 약세장 = 도달 즉시 전량.

## 다층 진입 단계 — legible 진입 funnel (2026-06-16 사용자 통찰)
> "관심종목 → 매수대기 → buy 로 가는 절차가 *라벨된 단계*로 추출되면 이 시스템이 더 빨리·직관적으로
> 인정받는다. 트레이더가 실제 매매하는 직관적 단계다." 각 단계는 **라벨 + 그 단계가 된 사유 + 그 단계의
> 매매 시나리오**를 가진다. 결정론/판단 분업 원칙은 동일 — 단계는 **새로 판단하는 게 아니라 이미 있는
> 판단(점수·verdict·alpha_posture·다단 메뉴)을 *조립·표면화* 한 라벨**이다(재료는 다 있고 연결만 없다).

| 단계 | 라벨이 되는 사유 (= 무엇이 이 단계로 만들었나) | 그 단계의 시나리오 (산출물) |
|---|---|---|
| **관심종목** | 거래대금 상위 ∪ 보유 ∪ 관심 + 결정론 점수(S/T/buy/F) 통과 | 선정 사유 + 거친 매매 시나리오(왜 레이더에 올랐나) |
| **매수대기** | verdict=wait/hold 이나 **품질 점수 근접 + alpha_posture.conditional_entry 존재** (진입 트리거 대기) | 승격 사유 + **실전 진입 시나리오 시계열**(대기진입가·트리거·조건) = 2단계 |
| **buy(진입)** | verdict=buy | 매수 근거 + 다단 플랜(1단계 ✅ + 3단계 목표/분할매도) |
| (보유·청산) | 체결 발생 → 가상매매 상태 | 보유 지속 조건 / 분할 청산 (기존 desk·lifecycle) |

- **단계 = 파생 라벨 (새 판단 레이어 최소화)**: 관심=watchlist 멤버십+점수 / 매수대기=wait+근접+conditional_entry / buy=verdict buy. 승격 판정의 *후보 신호*는 결정론, 최종 승격/시나리오 서술은 LLM·룰(가드레일 있는 C 동일).
- **legibility 가 본질**: 사용자가 "이 종목은 지금 매수대기고 이런 시나리오로 진입 노린다"를 *본다* = FractalSignal "쓰는 데스크" 차별화 축. wait 을 죽은 통이 아니라 **승격 사유·시나리오를 가진 단계**로.

## 산출물 목표 형태 (prism 트레이드 시나리오 리포트 차용, 2026-06-15 사용자 제공)
- **핵심 가격대 다단**: 저항 1·2차 / 현재가 / 지지 1·2차 (단일 아님 = 후보 메뉴 확증).
- **매도 시그널 세트**: ⏰목표=마일스톤(regime 조건부 trailing/매도) · 추세약화 **multi-condition AND**(종가 20일선 이탈 ∧ 거래량 동반 ∧ 섹터 약세 中 2+) · ⛔하드스탑(**종가 기준**·장중 wick 무시) · 오닐 **−7% 절대** · 시간점검(트리거 아님).
- **보유 지속 조건**: 종가 stop 위 + 20일선 회복 / 섹터 주도 유지 / 수급 유지.
- **트리거별 과거 승률** (예 50%·18건) → 적중률(GUIDANCE-ACCURACY·북극성)과 연결.
- **투자근거 + 매매일지 반영** (cited 점수·regime·R/R + 과거 경험).

## 5단계 로드맵 (쉬운·결정론 → 어려운·동적, 각 단계 독립 가치)
- **1단계 — 손절 + 분할매수 레벨 (후보 메뉴) ✅ B-MS1 구현 (2026-06-16)**: `extract_swing_candidates`(스윙 저점)·`compute_indicators`(ma20/60/120)·`_atr` 로 후보 메뉴 계산 → buy 권고에 다단 실제 숫자. 분할 사다리는 sizing/paper_trading 재사용.
  - **결론 (사용자 철학 재점검 → B→C 합본)**: 결정론 *선택 머신*(상황별 손절 룰 트리)은 **만들지 않음** — 끝없고 신뢰 낮아 LLM+진화 영역. 결정론은 **객관 가격대 *계산*만**(스윙·MA·ATR·52w) 해서 LLM 에 **사실**로 주입(숫자 환각 차단). LLM 이 메뉴에서 선택·조합. 소수의 절대 가드레일(오닐 −7%·종가기준)만 결정론 강제(코드 clamp + menu-bound 감사). 프리즘급 다단 시나리오는 그대로 산출되되 "환각 안됨=숫자 출처 결정론 / 근거 없는 잦은 변경 안됨=deviation 로그 + 측정 루프(C)".
  - 구현물: `core/signal/trade_plan_menu.py`(순수 — TradePlanConfig/Inputs/Menu + build/render/adapter/config_from_dict + clamp/menu_bound 가드레일), `run_strategist(trade_plan_menu_md=)` 주입, recommendation 파서 `data.trade_plan`(scaled_buy/scaled_sell/stop_basis/stop_label/deviation_reason) 가산, auto_signal funnel 배선 + `data.trade_plan_menu` 영속 + `_apply_trade_plan_guardrails`, persona 다단 발행 지시, config `trade_plan` 섹션. <!-- SPEC:DONE name="stop-buy-level-menu" -->
- **2단계 — 매수대기 *단계* (대기 진입가 + 승격 사유 + 라벨) ✅ 구현 (2026-06-16)**: 단순 "조건부 진입가 숫자"가 아니라 **매수대기 단계로 격상**.
  - **결정론 = 팩트만, 판단 안 함 (사용자 결정)**: 손절가·진입가는 "판단 불가 영역(사람마다 다름)" → 결정론은 진입가 *후보 zone*(팩트)·트리거·진입존만 제공, **어느 가격을 택할지·시나리오 서술은 LLM**. = B-MS1 "가드레일 있는 C" 일반화.
  - **승격 임계 = 점수 근접 + 트리거 대기**: wait/hold + 1차 점수 ≥ (min − margin) + conditional_entry 존재 → "매수대기". 나머지 wait = "관심". margin = config SLOT(`watching_score_margin`).
  - (a) `enrich_conditional_entry`(순수) — trigger→메뉴 지지 후보 zone 부착(pullback=20일선·스윙저점 / bear_alignment=스윙저점·60일선 / 조건재평가형=가격 없음). **재사용 정정**: compute_scorecard 에 price/ma 신규 적재 대신 **이미 빌드된 trade_plan_menu.support_levels 재사용**(가드 #11). (b) `derive_funnel_stage`(순수 룰) — 관심/매수대기/진입 파생. (c) LLM 이 진입존 후보 중 선택 + 진입 시나리오(`stage_scenario`·`waiting_entry`) 서술.
  - 구현물: `core/signal/alpha_posture.py`(`enrich_conditional_entry`·`FunnelStage`·`derive_funnel_stage`·`PostureConfig.watching_score_margin`·render zone), `auto_signal.py` funnel 배선(enrich·재렌더·stage 파생·`data.funnel_stage`/`stage_reason` 영속), persona 매수대기 시나리오 지시(track_a/b), config `watching_score_margin`. 테스트 +22(A8·B9·C4·파서1). 라이브(실 Gemini): buy→entering·근접wait→watching·먼wait→interest 확증, 조건재평가형 진입존 빈값(가격 환각 0). 단계 라벨=결정론 권위(LLM over-label 정정). <!-- SPEC:DONE name="watching-tier" 미관측=pullback 진입존 가격 zone(오늘 과열눌림 wait 부재, 단위테스트 커버) -->
- **3단계 — 목표 + 분할매도 (buy 단계 완성)**: measured-move(anchor B 거리) 결정론 후보 + **LLM 수정** + 분할매도 비중. **신고가권 = 목표 열림/trailing**(직전 고점에 상방 가두지 않음 — 2026-06-16 현대차 사례). 목표 도달 시 regime 조건부 대응. <!-- SPEC:INTERVIEW-SLOT name="target-sell" 목표 후보·동적 수정 규칙·신고가권 trailing·분할매도 비중·매도 AND 조합 -->
- **단계 라벨·사유 영속 + 데스크 UI** (legible funnel 표면화): 단계 라벨+사유+시나리오를 `team_outputs.data_json` 가산 영속(가드 #11 확장) → 데스크가 관심/매수대기/buy 3-tier 로 표시(PAPER-DESK-UX 연계). <!-- SPEC:INTERVIEW-SLOT name="funnel-ui" 영속 형태(가산 vs 신규)·데스크 표현(칸반/리스트)·관심종목 선정사유 출처 -->
- **4단계 — 시계열 진화**: 플랜·**단계 승격/강등** 영속·매 cadence 갱신·목표 동적 수정·수정 사유 로그·보유 지속 조건 점검. <!-- SPEC:INTERVIEW-SLOT name="evolution-model" 전체재계산 vs 델타수정·surprise 정의·단계 전이 이력 보존 -->
- **5단계 — 알림**: 단계 전이(관심→매수대기→buy) + 레벨 도달(대기진입·목표·손절) 감지·발송. <!-- SPEC:INTERVIEW-SLOT name="alert-trigger" 도달·전이 감지(cadence vs 실시간)·알림 종류·종가 기준 -->

## 재사용 영향도 (가드 #11, DATA-MAP 확인)
- **재사용(신규 0)**: `collectors/anchors.py extract_swing_candidates`(스윙 다단)·`collectors/charts.py compute_indicators`(MA)·`collectors/technicals.py _atr`/`compute_rr`(직전 저점·인근 고점)·`core/strategist/recommendation.py`(entry/stop/target)·`core/account/sizing.py`·`paper_trading.py`(분할 사다리·체결)·`core/notification`(알림).
- **플랜 영속 = SLOT(신규 테이블 미확정)**: 진화하는 플랜을 `team_outputs.data_json` 가산 확장 vs 신규 `trade_plan` 테이블 — 4단계 구현 시 DATA-MAP 재확인 후 결정(현재 신규 금지, 확장 우선 검토).
- **트리거 승률**: `account_fills`·GUIDANCE-ACCURACY-TRACKER 집계 재사용(신규 추적 X).
- 3층 파급: DB(가산 우선) → backend(strategist·desk·notification) → frontend(데스크가 플랜 표시 — PAPER-DESK-UX 연계).

## 완료 정의 (잠정)
종목이 **관심 → 매수대기 → buy** 단계로 라벨되어(각 단계 사유+시나리오 보임), buy·매수대기 권고가 단일
가격이 아니라 **다단 레벨 + 상황별 액션 플랜**을 갖고, 매 cadence **진화**(단계 전이·목표 동적 수정 포함)하며,
단계 전이·레벨 도달 시 **알림**이 오고, 각 플랜이 **트리거 승률**로 사후 평가된다. = prism 리포트급 시나리오를
*스스로* 생성·갱신하되, **funnel 자체가 legible**(트레이더 직관 단계 그대로 보임).

## 비고
- 본 SPEC 은 **설계 골격** — 단계별 구현 시 각 INTERVIEW-SLOT 을 `/spec-interview` 또는 직접 확정.
- 1·2단계는 결정론 비중↑(레벨), 3·4단계에서 LLM 판단·수정↑(목표 동적), 5단계는 배선. 한 번에 다 하지 않음.
