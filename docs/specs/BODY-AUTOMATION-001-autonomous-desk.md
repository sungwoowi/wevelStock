---
spec_id: BODY-AUTOMATION-001
title: 몸통 — 자동 가상매매 실행 + 복리 관리 (자율 운전) (roadmap)
team: shared
type: roadmap
level: roadmap
status: draft
generates: []
children:
  - AUTO-SIGNAL-GENERATION-001    # 빠진 연결 — 매일 자동 종목 스크리닝→분석가→전략가→권고 발행
depends_on:
  - RIGHT-BRAIN-COMPLETION-001 (데스크 엔진(비중·체결·채점·복리) 코드 done — 본 roadmap 은 그 엔진을 *자율*로 돌림)
---

# BODY-AUTOMATION-001 — 몸통: 자동 가상매매 + 복리 관리 (Phase 2 기둥 2)

> 4기둥 중 **2. 몸통**. `PROJECT-NORTH-STAR-001` 직속.
> `RIGHT-BRAIN-COMPLETION-001` 이 **엔진(비중→체결→채점→복리)** 을 지었다 — 본 roadmap = 그 엔진이 **매일 스스로(자율) 돌며 결과를 누적·검증** 하게 한다.

## 현 상태 — "기계는 도는데 빈손으로 돈다" (2026-06-14 팩트)
데스크(`run_desk_today`)는 매일 18:05 자동으로 돈다. **그러나 산출물(매수/매도/관망 리포트·알림)이 0이었다.** 두 겹의 이유 — 상세 팩트는 자식 `AUTO-SIGNAL-GENERATION-001` 본문 참조:
1. **권고를 매일 자동 생성하는 잡이 없다** — 권고는 사용자가 채팅(`production_chat`)으로 물어볼 때만 생김. 데스크는 권고를 *소비*만 한다 → 연료 자동 공급 부재.
2. **있는 권고 4건마저 전부 `wait`**(방어장) → 체결 0 → 매매 알림 0.

## 빠진 연결 (이 roadmap 의 머리)
```
수집(자동) → [종목 스크리닝→분석가→전략가→권고: ❌ 자동 잡 없음] → 데스크 체결(자동) → 채점(자동) → 알림
                          ↑ 여기가 끊겨 있음 = AUTO-SIGNAL-GENERATION-001
```
이게 북극성 *"매일 **스스로** 판단"* 의 핵심 — 지금은 *"사용자가 물어봐야 판단"* 이다.

## 마일스톤
| # | 작업 | 자식 SPEC | 상태 |
|---|---|---|---|
| 1 | **자동 권고 생성 잡** — 매일 watchlist → 분석가→전략가 → persist → 데스크 소비 | `AUTO-SIGNAL-GENERATION-001` | draft (다음 세션 인터뷰) |
| 2 | **verified 게이트 마감** — 라이브 청산·스냅샷 누적 → RIGHT-BRAIN 4 자식 implementing→verified | (RIGHT-BRAIN 자식) | 시장·시간 의존 |
| 3 | 수치 캘리브레이션 — sizing/split_ladder/KPI 임계 (다일 누적 후) | (백로그) | — |

## 완료 정의 (잠정)
매일 사용자 개입 0으로 종목 스크리닝→권고→체결/관망→알림이 돌고, 자산 곡선·KPI가 라이브로 쌓여 **"매일 도는 책임지는 페이퍼 트레이딩 데스크"** 가 *증명*된다.
