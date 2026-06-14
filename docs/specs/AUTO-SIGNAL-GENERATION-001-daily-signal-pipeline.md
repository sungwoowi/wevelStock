---
spec_id: AUTO-SIGNAL-GENERATION-001
title: 자동 권고 생성 — 매일 스스로 종목 스크리닝→분석가→전략가→권고 발행 (두뇌↔몸통 빠진 연결)
team: shared
type: feature
level: implementation
status: draft
parent: BODY-AUTOMATION-001
generates: []   # 스켈레톤 — 다음 세션 인터뷰로 채움
depends_on:
  - RIGHT-BRAIN-COMPLETION-001 (데스크가 active recommendations 를 소비 — 본 SPEC 이 그 권고를 *생성*)
  - LEFT-BRAIN-COMPLETION-001 (분석가9·전략가A/B·5점수 — 권고 생성에 그대로 호출)
---

# AUTO-SIGNAL-GENERATION-001 — 자동 권고 생성 (두뇌↔몸통 빠진 연결)

> **현상 진단 SPEC (2026-06-14, 팩트 기반).** "몸통은 매일 도는데 매수/매도/관망 리포트·알림이 하나도 없던" 원인을 코드·DB로 확정하고, 빠진 연결을 채울 작업을 정의한다.

## 현상 (사실)
- 사용자 질문: "몸통은 도는데 왜 그간 매수·매도·관망·관심종목 리포트나 알림이 하나도 없었지?"
- **버그가 아니라 미구현.** 시스템은 배선된 대로 정확히 동작 중 — 자동 권고 생성 경로가 *애초에 없다*.

## 근거 (코드·DB, 2026-06-14 실측)
| 확인 | 결과 |
|---|---|
| `track_a/b` 권고 (`team_outputs`) | **총 4건, 전부 `verdict=wait`** (06-09·06-14, 과거 채팅 산물) |
| `account_fills` (가상 체결) | **0건** |
| 알림 (`notifications_log`) | `market_briefing` 11 + (legacy `None` 303) — **trade_signal·risk_alert·flow_idea = 0** |
| 권고 생성 함수 `persist_strategist_recommendations` 호출처 | **`server/api/production_chat.py` 단 하나** (사용자 채팅 트리거 전용) |
| 스케줄 잡 (`pipelines/*/manifest.yaml`) | 시황 브리핑만 (`market_briefing_pre` 07:00 / `market_briefing_now` 09:30·12:30·14:30) |
| 데스크 (`run_desk_today`, daily_refresh 18:05) | `load_active_recommendations()` 로 권고를 **소비만** — 생성 안 함 |

## 진단
```
수집(자동) → [종목 스크리닝→분석가→전략가→권고 발행: ❌ 없음] → 데스크 체결(자동) → 채점(자동) → 알림
                          ↑ 빠진 연결
```
- 권고는 **사용자가 채팅으로 물어볼 때만** 생성된다. 데스크(몸통)는 매일 돌지만 굴릴 권고가 없어 **빈손으로 돈다.**
- 있는 4건마저 방어장이라 전부 `wait` → 매수 0 → 체결 0 → 매매 알림 0.
- 이게 북극성 *"매일 **스스로** 4계좌에 매수/매도/홀딩 판단"* 의 **"스스로" 부분이 빠진** 것. 현재는 *"물어봐야 판단"*.

## 재료는 이미 있다
- **거래대금 상위 50종(watchlist) 매일 자동 적재됨** (`refresh_all_tickers`, chart_ohlcv).
- 분석가9·전략가A/B·5점수(S/T/α/buy/F)·track 라우팅 전부 라이브 (왼쪽 뇌).
- 데스크 소비·persist 계약(`strategist-recommendation-v1`)·체결·채점·알림 배선 완비.
- **빠진 건 "매일 그걸 엮어 돌리는 지휘자 잡" 하나.**

## 예정 범위 (다음 세션 인터뷰로 확정)
매일 장후(daily_refresh 합류 후보), watchlist → 분석가 → 전략가A/B → 권고 persist → 데스크가 소비.
- **방어장이어도** 전략가의 "오늘은 다 관망(wait)" 판단이 **매일 발행** = 관심종목·관망 리포트/알림이 그 자체로 생긴다(관망도 판단).
- 매수 신호 뜨는 날엔 체결→`trade_signal` 알림까지 자동.

## INTERVIEW-SLOT (미정 — 다음 세션)
1. **watchlist 정의** — 거래대금 상위 N? + 보유 종목 + 사용자 관심종목? scope(국장/미장)?
2. **실행 시점·빈도** — daily_refresh(18:05) 합류 vs 별 cron. 장중 갱신 여부.
3. **LLM 비용** — 매일 N종목 × 분석가 fan-out = 호출 폭증. 결정론 1차 스크리닝(점수 컷)으로 LLM 대상 좁히기 + 캐싱([[feedback_llm_intuition_distribution]]).
4. **중복·멱등** — 같은 종목 매일 재권고 vs 변화 시만. recommendation_id 키 설계.
5. **관망 리포트·알림 정책** — 매일 "관심종목 N개 중 매수 X·관망 Y" 요약 알림(🔵 하루 정량) 형태. 스팸 방지.
6. **production_chat 권고 생성 경로와의 관계** — 자동 생성분과 사용자 질문 생성분 공존(우선순위·표시).

## 완료 정의 (잠정)
사용자 개입 0으로 매일 watchlist가 권고(매수/관망)로 발행되고, 데스크가 그 위에서 체결·관망 리포트·알림을 산출한다 → 몸통이 빈손으로 돌지 않는다.
