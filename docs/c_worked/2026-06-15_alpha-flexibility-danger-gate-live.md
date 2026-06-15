---
date: 2026-06-15
topic: BRAIN-ALPHA-FLEXIBILITY 라이브 검증 → 복합 위험 게이트 신설 + 배치 누수 2건 정정
status: partial
plan_file: C:\Users\HOME\.claude\plans\dapper-hopping-volcano.md
---

# 2026-06-15 (5) · 알파 유연성 라이브 검증 + 복합 위험 게이트

## 배경
M1+M2+M3a(전 세션) 후 실 Gemini 라이브 검증 착수. 라이브가 "여전히 전부 wait" 의 **진짜 원인**을
연쇄로 드러내, 검증이 실질 구현(복합 위험 게이트 + 누수 2건 정정)까지 확장됨. 핵심 판단:
**regime blanket 을 풀었더니 진범이 분산일 kill-switch(시장전체 blanket)였고, 그걸 "복합 위험
게이트"로 교체 — 폭락은 막고 완만한 분산은 통과.** 그리고 persona text 로는 LLM 안전핀을 못 막아
(프로젝트 핵심 교훈 재현) 구조(코드)로 해결.

## 한 일
- `core/signal/alpha_posture.py` — dd 단독 kill(4) → **복합 위험 게이트**: 당일 급락(change_pct≤−2.5)·breadth 붕괴(≤0.2)·VIX 패닉·지속 분산(dd≥6) 중 하나라도 → blanket 방어. PostureInputs 에 index_change_pct·breadth_ratio·vix_panic 추가, PostureConfig 에 crash_change_pct·breadth_collapse + dd_kill 4→6.
- `core/signal/auto_signal.py` — Scorecard 에 위험 입력 3필드 + compute_scorecard 가 macro(change_pct·breadth, 무료)+us_macro(vix_panic, DB-first) 채움 + posture_inputs 전달. **Fix①** `_market_state_md` stale "kill-switch ≥4" 하드코딩 제거(판정을 게이트에 위임). **Fix②** `build_prefetched_entries` 에 우회 분석가(stock_analyst·wealth_strategist·principle_guardian)를 **"의도적 우회" entry(batch_bypassed)** 로 주입 — LLM 이 "미발행→wait" 로 안 세게.
- `agents/strategists/track_a/persona.md`·`track_b/persona.md` — "분석가 미발행→wait" 에 배치 경로 예외(보조; 실효는 Fix② 구조 주입).
- `config/screening.yaml` — alpha_posture 에 crash_change_pct·breadth_collapse + dd_kill 6.
- `tests/test_alpha_posture.py`·`tests/test_auto_signal.py` — 위험 게이트 7종 + bypass entry + market_state 재정의(TDD).

## 검증 결과
- ✅ TDD RED→GREEN, 전체 **1253 passed**(회귀 0).
- ✅ **결정론 스캔(오늘 +5.2% 상승일)**: 위험 게이트 미발동 → buy 14 / wait 26(직전 0 buy 에서 탈피).
- ✅ **라이브 실 Gemini**: 000660 **LLM=buy**(후보 채택·탈피) / 005930 **사실근거 wait**("외인 60일 순매도 −27.88조+수급 약함" 로그 — blanket 아님) / 402340 no_yaml(일시적). = "가드레일 있는 C" 작동.
- ✅ 폭락 보호: 당일 급락/breadth 붕괴/VIX 단위 테스트로 blanket 방어 증명.

## 의도적으로 안 한 것 / 미완
- **관망 조건부 진입가(숫자)** — 여전히 심볼릭(trigger/note)만. 사용자와 다음 세션 논의 합의.
- 보유종목 관리·M3b(sector_rs·wave LLM 입력) 미착수 → 약세장 bear_override 아직 미동작.
- 402340 no_yaml = LLM YAML 발행 신뢰도 블립(실 funnel retries 로 회복).

## 다음에 이어서 할 작업 (우선순위)
1. **관망 조건부 진입가(숫자) 설계·구현** — wait 종목에 "X원 도달 시 매수" 실제 가격. entry→stop 보간(RB-MS2 패턴)·눌림목(ma20 부근)·돌파 트리거. price/ma20 를 scorecard 에 실어 conditional_entry 채움. **사용자와 설계 먼저 논의 합의.**
2. **M3b — sector_rs·wave LLM 입력** — compute_scorecard 에 섹터RS(theme classify)·파동(anchors α→bool) → 약세장 bear_override 활성(현재 None 이라 bullish/neutral 차등만).
3. **임계 캘리브레이션 + Track B 희소성** — 라이브 누적 후 alpha_posture 임계(dd_kill·crash·score floor) + Track B buy 가 오늘 2건뿐(T-Score 하한 binding) 점검.

## 맥락 재진입 힌트
- **persona text 로 LLM 분기 강제 불가 재확인**: Fix② 를 persona 예외로 먼저 시도했으나 LLM 이 "미발행→wait" 안전핀으로 회귀 → bypass **entry 구조 주입**(코드)으로 해결됨. 앞으로 "LLM 이 규칙 안 따름" = persona 수정 말고 구조/코드로.
- 위험 게이트는 시장 전체 신호(change_pct·breadth·vix·dd) = 모든 종목 동일. 차등(섹터·주도주·파동)은 게이트 통과 후.
- 임계 전부 SLOT(config/screening.yaml alpha_posture) — watchdog hot reload.

## 커밋 상태
- 세션 중 미커밋 → 이 wrap-up 이 코드+persona+config+테스트 + 문서를 1커밋 + main(현 브랜치) + push 예정.
