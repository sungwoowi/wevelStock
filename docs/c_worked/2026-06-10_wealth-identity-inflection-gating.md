---
date: 2026-06-10
topic: 자산복리부 정체성 = 변곡점 길잡이 확정 + 박종훈 frame 결정론 게이팅
status: completed
plan_file: C:\Users\HOME\.claude\plans\valiant-riding-globe.md
---

# 2026-06-10 · 자산복리부 정체성 재정의 + 변곡점 게이팅

## 배경
"복리"가 지식부 자산복리부(박종훈 거시 frame)와 RB-MS4 추적(자산 곡선)에서 의미 충돌
(2026-06-09 사용자 제기). 오늘 사용자가 본질 우려 추가: **박종훈 frame 은 절대 매수를 말하지
않는 비관 시각이라 LLM 이 평상시 트레이딩을 망설일 것**. 확인 결과 실재 — Track A 가 매
`long:` 마다 wealth_strategist 를 read 하는데 "변곡점에만" 원칙(2026-05 피드백)이 소비측에
미배선. **핵심 판단: ①정체성 명확화+③워딩 분리+결정론 게이팅 (rename X, ②전략 자료 보강은
자료 생길 때)**.

## 한 일
- `collectors/market_macro.py` — `is_macro_inflection()` 신규: 변곡점 = regime 전환(직전
  스냅샷 대비 분류 비교) or DD≥4. cutoff(date_str) 인자 백테스팅 친화. 스냅샷/직전 행 부재 시
  보수적 평상시.
- `core/intent/router.py` — `_prefetch_analysts_for_tracks` 가 wealth_strategist entry 에
  `macro_inflection` 플래그 부착 (to_thread, 실패 시 미부착 graceful).
- `core/strategist/run_strategist.py` — `render_prefetched_analyst_outputs` 가 플래그 따라
  지침 자동 삽입: 평상시="자산배분 맥락만, verdict 직접 근거 금지" / 변곡점="사유와 함께 전면
  반영". advisory (점수 collapse·verdict 차단 아님).
- `agents/strategists/track_a/persona.md` — Inputs wealth_strategist 사용 룰 + Anti-pattern
  "보수 frame 단독 wait 금지" + composite 표 주석 (변곡점 시만 의미 가중).
- `agents/analysts/wealth_strategist/persona.md` — Identity 에 "변곡점 길잡이, 비관/보수는
  frame 속성이지 매매 신호 아님" 명시.
- `knowledge/canon/wealth_compounding/README.md` — 부서 정체성 재서술 (다년 거시 frame·생존·
  변곡점 길잡이 / market_macro 와 시계 경계 / ② 복리 전략 자료는 향후 보강 / RB-MS4 와 무관).
- 워딩 분리: `server/telegram/commands.py`(HELP)·`server/telegram/bot.py`(BotCommand)·
  `server/api/wealth.py`·`core/account/compounding.py`(render 텍스트·docstring) — 사용자 노출
  "복리" → "자산 곡선/성장 목표". 함수명·테이블명·SPEC ID 불변.
- `tests/test_macro_inflection.py` (신규 7) + `tests/test_run_strategist.py` (지침 4 추가) +
  `tests/test_account_compounding.py` 워딩 단언 갱신.
- `scripts/_macro_gate_probe.py` (신규) — 실 Gemini prefetch 라이브 probe.
- 메모리 `project_wealth_dept_identity.md` 백로그→해소 기록 + MEMORY.md 인덱스.

## 검증 결과
- ✅ 신규 26 (inflection 7 + 렌더 19) + 전체 회귀 **1121 passed** (워딩 단언 1건 의도 갱신).
- ✅ 결정론 라이브: `is_macro_inflection()` 실 DB = **변곡점 True** (regime 전환 + DD 4건) —
  현 시장과 정합 (regime 이 06-08 moderate_bull→06-09 parabolic→06-10 moderate_bull 요동 중).
- ✅ 실 LLM 라이브 probe: track_a 풀세트 6 분석가 실 Gemini prefetch → entry 플래그 부착 +
  렌더에 "[거시 frame 사용 지침 — 변곡점 감지: regime 전환 parabolic→moderate_bull + DD 4건]"
  정직하게 박힘. gemini 503 bounded 재시도 작동.

## 의도적으로 안 한 것
- **폴더/analyst ID/SPEC ID rename** — manifest·canon_categories·chroma 연쇄 비용 (사용자 결정).
- **② 복리 전략 (켈리·비중 증대·재투자 룰) 자료 보강** — 자료가 실제 생길 때 별도 라운드.
- **Dalio 사이클 단계 변화의 결정론 판정** — LLM 영역, 변곡점 3 케이스 중 결정론 2개만.
- **advisory composite 가중치 수치 변경** — 다일 데이터 없이 튜닝 금지.

## 기술 부채/미완 (사소)
- regime 이 경계에서 요동 (3일 연속 전환) → 변곡점 플래그가 자주 켜질 수 있음. 기존 백로그
  "regime 히스테리시스" 가 해소하면 같이 안정화 (게이팅은 그 위에 자동으로 올라탐).
- wealth_strategist 의 다른 소비 경로 (브리핑 등) 신설 시 `is_macro_inflection()` 재사용 필요.

## 다음에 이어서 할 작업 (우선순위)
1. **오른쪽 뇌 verified 마감 (라이브 청산 누적 — 시간 영역)** — 매일 18:05 cron organic 누적,
   시장 매수 신호 시 체결→청산→`/retro`·`/wealth`. ACCOUNT-MANAGER/GUIDANCE/WEALTH
   implementing→verified.
2. **PAPER-DESK-UX-001 (화면)** — webapp 데스크 대시보드 (4계좌·회고 KPI·자산 곡선 두 시리즈)
   + 텔레그램 다듬기. `/spec-interview` 부터.
3. **regime 흔들림 히스테리시스** — 경계 요동이 변곡점 플래그 빈발로 이어질 수 있어 우선순위
   소폭 상승. `collectors/market_macro.py` sticky 밴드.

## 커밋 상태
- 본 wrap-up 에서 코드+docs 일괄 커밋 + main push 예정.
