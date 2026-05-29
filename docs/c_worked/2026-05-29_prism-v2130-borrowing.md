---
date: 2026-05-29
topic: prism-insight v2.13.0 분석 + 매도 로직 종가 기준 봉합 + RS·과열도 스크리닝 SPEC 신설
status: completed
plan_file:
---

# 2026-05-29 · prism-insight v2.13.0 차용 (매도 종가 기준 + RS·과열도 스크리닝)

## 배경
prism-insight 가 v2.13.0 (매매 엔진 대규모 업그레이드) 을 냄. 릴리즈 노트 + 핵심 PR(#279 매도, #289 스크리닝) 을 분석해 우리 wevelStock 에 차용할 점을 도출. **핵심 발견**: 매도 로직 결함은 전략가 SPEC 이 아니라 trader 분석가 페르소나에 있었음 — 전략가 SPEC(STRATEGY-TRACK-001) 은 이미 prism 급(+5% 활성화·종가 -7%·regime 폭·일방향 래칫) 인데, trader 가 그것과 모순되는 "일중 고가 -2% trailing" 을 발행하고 있었던 것 (= prism 이 근절한 intraday wick 방식).

## 한 일
- `agents/analysts/trader/persona.md` — `trailing_stop_rule` 예시를 "일중 고가 -2% trailing" → "종가 기준 trailing (일중 꼬리 매도 X) — 활성화·폭은 전략가 regime 정책 위임" 으로 봉합 (실 런타임 결함 해소)
- `docs/specs/STRATEGY-TRACK-001-two-track-strategists.md` — v1→**v2**. Track B 익절·청산 정책에 **종가 기준 원칙** 명시 + **let-winners-run** (목표가=강세장 trailing 전환점, 시간은 checkpoint) 추가 (prism #279 차용)
- `docs/specs/ANALYST-PERSONAS-001-nine-analyst-portable-personas.md` — v2→**v3**. trader `trailing_stop_rule` 종가 기준 정합 근거 문서화 + 모순 봉합 명시
- `docs/specs/SCREEN-RS-EXTENSION-001-stock-rs-extension.md` — **신규 SPEC (draft)**. 종목 RS(후보 풀 정규화) + 과열도(ADR 정규화) + regime 가중 합성. prism #289 오닐식 스크리닝을 결정론 순수 함수 + cutoff_date 백테스팅 친화로 이식. **구현은 보류** (트레이딩부/scoring 구현 때 같이)
- 메모리: `project_prism_insight_borrowing.md` v2.13.0 분석 5항목(A~E) 추가 + 작업 결과 / `project_screen_rs_extension_backlog.md` 신규 / `MEMORY.md` 인덱스 갱신

## 검증 결과
- ✅ `uv run python scripts/validate.py` → **0 errors, 1 warning** (warning = 기존 teams/registry.yaml 부재, 본 작업 무관)
- ✅ 회귀 가드: `grep "일중 고가 -2%|trailing_stop_rule"` in test_*.py → 매치 0 (테스트가 옛 문자열 단정 안 함)
- 코드(scoring.py) 미변경 — SPEC 문서 + persona 텍스트만 변경이라 pytest 불요

## 의도적으로 안 한 것
- **SCREEN-RS-EXTENSION-001 구현** — 사용자 결정으로 보류. 다음 트레이딩부/scoring 구현 사이클에서 SPEC 열고 함수 3개 + config + collector 작성.
- **피라미딩(prism #1)·매매일지 투명화(#4)** — 백로그만. 피라미딩은 실주문(KIS) 레이어 전이라 doctrine 보류.
- **main 머지** — feature/hybrid-executive-poc 는 PoC 격리 상태, 머지는 별 결단 (이번에도 유지).

## 다음에 이어서 할 작업 (우선순위)
1. **SCREEN-RS-EXTENSION-001 구현 (트레이딩부 구현 때)** — scoring.py 순수 함수 3개(stock_rs_score/extension_score/screening_score) + config/screening.yaml + collectors/screening.py + tests. SLOT R1~R3(정규화 방식·스케일 k·가중치)은 초기값 구현 후 production 분포로 튜닝.
2. **하이브리드 임원 PoC 후속 (기존 Top 1·2)** — Flash 라벨 스크러버 + webapp 임원 토글 / Pro 발동 라우팅(SLOT S7) + 다종목 검증.
3. **main 머지 결단 → INFRA-SCORE-INPUTS-001** — PoC 채택 시 main 머지 + F/S/buy/T-Score input collector.

## 맥락 재진입 힌트
- prism 차용 전체 맥락 = 메모리 `project_prism_insight_borrowing.md` § v2.13.0 (A 완료 / B SPEC·보류 / C·D 백로그).
- 워킹트리에 **이전 세션 PoC 후속 코드 변경**(synthesize.py / formatter.py / production_chat.py / label_dictionary.yaml / page.tsx / test 2건)이 미커밋 상태로 남아 있음 — 본 세션 것 아님, 별도 커밋 필요 (사용자 확인 대상).

## 커밋 상태
- 본 세션 산출(persona + SPEC 3건 + wrap-up 문서)만 분리 커밋 + feature 브랜치 push. main FF 머지 skip (PoC 격리 유지).
