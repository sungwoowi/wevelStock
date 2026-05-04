---
canon_id: principles.operational_safeguards
analyst: principle_guardian
title: 운용 안전핀 (시스템 자동 검증 가능 룰)
distilled_at: 2026-05-04
note: 철학(01)·심법(02)·국면(03)이 사람의 판단을 잡아준다면, 본 문서는 시스템이 기계적으로 검증할 수 있는 정량 룰만 담는다.
---

# 운용 안전핀 — 시스템 자동 검증 룰

> 철학(01)/심법(02)/국면(03)은 정성적 판단. 본 문서는 분석가/시스템이 **기계적으로 검증** 가능한 정량 룰. 한 줄로 위반 여부 판정 가능해야 함.

## 비중 룰 (포트폴리오 단위)

| 룰 | 임계값 | 위반 시 |
|---|---|---|
| 총 투자비중 | ≤ 80% | `violation` + 추가 매수 차단 |
| 단일 종목 비중 | ≤ 15% | `violation` + 분산 권고 |
| 트레이딩(단기) 비중 | ≤ 20% | `violation` + 트레이딩 진입 차단 |

> 트레이딩 = 단기 회전 목적. 시대적 주도주(중장기 보유)와 분리 계산.

## 손절 룰 (개별 종목 단위)

- **손절선 없이 진입 X**: 매수 주문 검증 시 `stop_loss_price` 필수 (없으면 `violation`).
- 손절선 도달 시 **기계적 실행** (감정 개입 금지).
- 손절선은 매수 **전에** 정한다 (매수 후 변경 시 `violation` — 기준 흔들림).

> 분할 매수 (1:2:3:6:12) 의 경우 손절선은 **평균단가 기준** 으로 갱신 가능. 다만 갱신 룰 자체가 사전 명시되어야 함.

## 진입 검증 룰 (3개 교차)

- **단일 지표 진입 금지**: 매수 결정에 사용한 신호가 **3개 이상 독립** 이어야 한다.
- 신호 후보 (분석가별 산출):
  - 거시분석가: 거시 국면 (상승장/조정장/하락장 — 03 참조)
  - 종목분석가: 차트 (월봉/주봉 추세, 2차 함수 파동 위치, 음봉/양봉)
  - 종목분석가: 거래대금 / 신고가-박스-과대낙폭 분류
  - 뉴스큐레이터: 시대적 주도주 흐름 / 테마 vs 본질
  - 거시분석가: 외국인 현물·선물 수급 방향
- 동일 차원 신호 2개는 1개로 카운트 (예: 일봉 + 주봉 = 차트 1개).

## 데이터 무결성 룰

- **데이터 없이 추측 금지**: 분석가 응답에 `data` 필드 비어있으면 `violation`.
- 모든 verdict 에는 `reasons` 배열에 **최소 3개** 근거가 있어야 한다 (`StandardOutput` 계약).

## 감정 통제 룰 (자동 감지 어려움 — 사용자 셀프체크)

- FOMO 매매 금지 (예: 양봉 추격 매수 — 5대 심법 #3 위반 → 자동 감지 가능).
- 공포 매도 금지 (예: 일봉 -3% 에 즉시 매도 — 사용자 매매 패턴 분석으로 감지 가능, M5+).

## 분석가 활용 가이드 (원칙수호자)

매 verdict 산출 시 다음 정량 체크:

```
def check_safeguards(action, portfolio, signals) -> Verdict:
    if portfolio.total_ratio > 0.80: return violation("총비중 80% 초과")
    if any(p.ratio > 0.15 for p in portfolio.positions): return violation("단일 15% 초과")
    if portfolio.trading_ratio > 0.20: return violation("트레이딩 20% 초과")
    if action.is_buy and action.stop_loss is None: return violation("손절선 미설정")
    if len(distinct_signal_dims(signals)) < 3: return violation("3교차 미달")
    if action.signal_count == 0: return violation("데이터 없는 추측")
    return compliant
```

본 룰은 **차단(blocking)** 룰. 위반 시 진입을 막고 사용자에게 알림.
정성 판단(01·02·03) 위반은 경고(warning) 후 사용자 판단 위임.
