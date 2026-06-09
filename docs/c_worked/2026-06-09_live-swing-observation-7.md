---
date: 2026-06-09
topic: 라이브 swing 권고 배치 관찰 — 방어장→전부 wait, 청산은 cron organic 누적 확인
status: completed
plan_file: C:\Users\HOME\.claude\plans\drifting-foraging-yeti.md
---

# 2026-06-09 · 라이브 swing 관찰 (RB-MS2~4 데스크 실가동 점검)

## 배경
오른쪽 뇌 4 자식 코드 완성 후, 사용자가 "라이브 청산 누적 관찰하게 swing 권고 몇 개 더 돌려줘"
요청. 실 LLM 로 여러 종목 swing: 를 돌려 데스크가 실제로 무엇을 하는지 관찰. **핵심 발견**:
시장 진입 자세가 현재 `defensive` 라 전략가가 종목 불문 전부 `wait` → 체결·청산 0 (= 시스템이
규율대로 "지금은 살 때 아님"을 정직하게 판단, 버그 아님). 청산은 수동 run 이 아니라 매일 cron 이
organic 하게 누적.

## 한 일
- `scripts/_swing_batch.py` (신규) — 여러 종목 실 swing: 배치(production_chat) → 권고 누적 →
  `run_desk_today` → 활성 권고·계좌 현황·회고 출력. 라이브 관찰 헬퍼.
- 실행: 삼성전자(503 소진)·SK하이닉스(wait)·현대차(wait) → 3건 실 DB 권고 영속(전부 wait, 비actionable).
  데스크 매수 0(posture=defensive). 회고 = 청산 0.

## 검증 결과 (관찰)
- ✅ 실 파이프라인 end-to-end 동작(분류→분석가→전략가→권고 영속→데스크 게이팅). gemini 503 bounded 재시도·KIS rate limit 자가 재시도 작동.
- ✅ 데스크 규율 정상: 방어장 + wait → 체결 0. 권고는 team_outputs 영속(cron 이 이후 굴릴 원천).
- ⚠️ 코드 변경 없음(관찰 세션). 직전 RB-MS4 wrap(`0016a8c`) 이후 신규 = `_swing_batch.py` 뿐.

## 의도적으로 안 한 것
- **swing: 추가 반복** — 방어장에선 "wait" 재확인일 뿐 청산 안 생김. 억지 매수는 시스템 철학 위반. LLM 비용만 소모 → 중단(사용자 "그대로 두자" 동의).

## 기술 부채/미완 (사소, 관찰 중 노출)
- WAVE-ALPHA `alpha_compute_failed: current.date must be after C.date`(현대차, 같은 날짜 anchor 엣지) — 비차단, 다음 데이터 정리 시.
- KIS "초당 거래건수 초과" 1건 — 자가 재시도 회복(기존 백로그 INFRA-KIS-RATELIMIT 전역화).

## 다음에 이어서 할 작업 (우선순위)
1. **오른쪽 뇌 verified 마감 (라이브 청산 누적 — 수동성/시간)** — 매일 18:05 cron 이 organic 하게 굴러 시장이 매수 신호 줄 때 체결→청산→`/retro`·`/wealth` 채워짐. 그때 implementing→verified.
2. **PAPER-DESK-UX-001 (화면)** — 백엔드·API·텔레그램 동작, 한눈에 보는 webapp 대시보드 + 텔레그램 다듬기. `/spec-interview`.
3. **자산복리부 정체성 재정의**([[project_wealth_dept_identity]]) + 라이브 데이터 쌓인 뒤 수치 캘리브레이션.

## 커밋 상태
- `_swing_batch.py` + 본 wrap-up docs → main 직접 + push 예정.
