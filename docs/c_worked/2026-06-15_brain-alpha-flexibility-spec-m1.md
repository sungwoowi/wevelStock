---
date: 2026-06-15
topic: BRAIN-ALPHA-FLEXIBILITY-001 SPEC 작성 + M1 결정론 차등 변조(alpha_posture)
status: partial
plan_file: C:\Users\HOME\.claude\plans\dapper-hopping-volcano.md
---

# 2026-06-15 (3) · 두뇌 알파 유연성 — SPEC + M1 차등 변조

## 배경
/resume → 두뇌 알파 유연성(BRAIN-QUALITY 첫 자식) 착수. 오늘 라이브 auto-signal 이
**regime=strong_bull 인데 권고 32건 전부 wait** = regime 이 verdict 를 3단으로 통째 억압
(persona 범주 게이트 + kill-switch + confidence 가중)인 게 코드로 확인됨. 핵심 판단:
**regime 을 binary blanket 게이트에서 baseline 으로 강등**하고 섹터RS·주도주·파동·과열도가
종목별로 override 하게 한다. 면담 5라운드로 SPEC 박고 M1(결정론 절반)만 구현.

## 한 일
### SPEC (면담 산출)
- `docs/specs/BRAIN-ALPHA-FLEXIBILITY-001-regime-differentiated-alpha.md` — 신규. 결단 4건 + 6 마일스톤 + SLOT 6 + 재사용 영향도(신규 테이블 0). status=implementing.
- `docs/specs/BRAIN-QUALITY-001-investment-quality.md` — children 에 첫 자식 연결.

### M1 — 결정론 차등 변조 (TDD)
- `core/signal/alpha_posture.py` — 신규 **순수 함수**(I/O·LLM 0). `derive_alpha_posture(PostureInputs, PostureConfig)` → `AlphaPosture(verdict_candidate·regime_class·selection_reason·modulation·conditional_entry)`. regime 6→3분류(bullish/neutral/bearish/unknown) baseline × 섹터RS × 주도주 × 파동 × 과열도. `posture_config_from_dict` graceful 매퍼.
- `config/screening.yaml` — `alpha_posture` 섹션(임계 전부 외부화·watchdog, SLOT).
- `collectors/screening.py` — `load_posture_config()` 얇은 로더(M3 주입용).
- `tests/test_alpha_posture.py` — 신규 17 테스트.

## 핵심 설계 결단 (면담)
1. **regime = 섹터·종목 차등 변조** (blanket gate 폐기). regime 은 baseline, 섹터RS·주도주·파동이 override.
2. **가드레일 있는 C** (사용자 선택 C + 내 가드 보강): 결정론이 *verdict 후보+조건부 진입가* 발행 → LLM 은 "반박할 사실 있나?" 검증자로 시작, 후보 강등엔 **사실 근거 로그 필수**(blanket 보수 강등 금지), 웹 더블체크는 buy 후보에만. 사용자 논거="결정론은 블랙박스·LLM 웹검증 필요"는 수용하되 순수 C 는 오늘 버그의 실패 모드라 가드 추가.
3. **MVP = 4 스레드 전부** (차등 변조·관망 조건부 진입가·watchlist 선정 강화·설명가능성).
4. **시장 = 국장+미장 동시** (미장 watchlist source 는 M4 에서 해결 ⚠️).

## M1 동작 (테스트로 명세)
- 🟢 약세장 + 강세섹터(RS≥7) + 주도주(S≥7 or RS≥8) + 파동 생존 + 눌림목(건강도≥6) → **buy(bear_override)** ← 오늘 버그의 정반대.
- 🔴 강세장 + 과열(건강도<4) → buy→**wait(bull_chase_demote)** + pullback 조건부 진입.
- 🛡 분산일 ≥4 → kill-switch(어떤 regime 도 진입 차단, strong_bear 면 sell 의도).
- 점수 하한(track A=S+buy / track B=T+buy) 미달 → regime 무관 wait. 모든 분기 selection_reason 존재.

## 검증 결과
- ✅ TDD RED→GREEN, `tests/test_alpha_posture.py` **17/17 passed**.
- ✅ 전체 **1239 passed** (직전 1225 + 신규 17 - 3 실패). 실패 3 = `test_market_snapshot.py`(KR 스냅샷 신선도 + 라이브 KIS 호출 의존 기존 환경성, grep 으로 alpha_posture·snapshot 미참조 입증 → M1 회귀 아님).
- ✅ `scripts/validate.py` 0 errors. `project_status.py` = BRAIN-QUALITY 0/1, 자식 등록·drift 없음.

## 의도적으로 안 한 것
- M2(persona doctrine)·M3(funnel 주입)·M4(watchlist 선정 강화)·M5(웹 더블체크+persist 확장)·M6(라이브) — LLM 라이브 검증 얽혀 전용 세션이 정직. 사용자 "M1만 + 랩업" 선택.
- conditional_entry 는 M1 에서 심볼릭(trigger·note)만 — 실제 진입가는 M3 가 가격으로 채움.

## 다음에 이어서 할 작업 (우선순위)
1. **M2 — persona doctrine 전환** — track_a/b persona.md 를 blanket gate 폐기 + AlphaPosture 후보 소비자 + deviation 사실근거 로그로 재집필. (가드레일 있는 C 의 LLM 절반)
2. **M3 — funnel 주입** — `auto_signal.py compute_scorecard`/`build_prefetched_entries` 에 섹터RS·파동·후보 주입 + conditional_entry 가격화. 라이브에서 buy 후보 ≥1 발생(오늘 "전부 wait" 탈피) 확인.
3. **M4 — watchlist 선정 강화 + M5 웹 더블체크** — rank_candidates 가중에 파동/주도주/섹터RS + 미장 source / buy 후보 Gemini grounding + data_json 가산.

## 맥락 재진입 힌트
- alpha_posture 는 **순수 함수** — Scorecard(`core/signal/auto_signal.py`)+screening rank 행에서 입력 채움. 파동(wave_alive)은 현 Scorecard 에 없음 → M3 에서 `collectors/anchors.py` α·verdict 매트릭스 → bool 배선 필요.
- 임계값은 전부 SLOT(추측) — 라이브 누적 후 BRAIN-QUALITY 회고 루프로 캘리브레이션. 지금 buy/wait 경계가 너무 빡세/느슨하면 `config/screening.yaml alpha_posture` 조정(코드 변경 0, watchdog).
- 과열도(extension_score) semantics: 높음=건강(눌림), 낮음=과열 또는 이탈(혼재). M1 은 이 혼재를 단순화 — chase vs broken 분리는 튜닝 follow-up(SLOT differentiation-formula).

## 커밋 상태
- 세션 중 미커밋 → 이 wrap-up 이 코드(M1)+SPEC+문서를 커밋 + main 은 이미 현재 브랜치 + push 예정.
