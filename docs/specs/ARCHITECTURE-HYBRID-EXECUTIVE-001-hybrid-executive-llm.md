---
spec_id: ARCHITECTURE-HYBRID-EXECUTIVE-001
title: 하이브리드 임원 LLM — 9 분석가 정량 + 투자 총괄 임원 종합 (PoC scope)
team: shared
type: feature
status: implementing
version: 1
owner: agent_layer
generates:
  - agents/executive/persona.md
  - agents/executive/manifest.yaml
  - core/executive/__init__.py
  - core/executive/synthesize.py
  - scripts/smoke_executive.py
  - tests/test_executive.py
modifies:
  - server/api/production_chat.py     # executive_mode 플래그 (formatter A/B)
  - core/config/schema.py             # LLMAreas.executive_synthesis = deep
  - config/runtime.yaml               # areas.executive_synthesis: deep
related:
  - PRODUCTION-UX-001 (formatter '압축기' — 본 SPEC 이 doctrine 임원으로 대체 검증)
  - ANALYST-PERSONAS-001 (9 분석가 정량 발행 — 임원의 입력)
  - STRATEGY-TRACK-001 (Track A/B 전략가 — 임원이 verdict 맹종 X 재통합)
contracts: []
---

# ARCHITECTURE-HYBRID-EXECUTIVE-001 — 하이브리드 임원 LLM (PoC)

## 배경 (왜)

production UX 답변 품질 저하 진단 (2026-05-29, `_smoke_track_b_resp.json` + `_baseline_formatter_005930.json` 실증):

- **원인 1 (데이터 미배선)**: 점수 input collector 부재 → 일부 분석가 빈손. = INFRA-SCORE-INPUTS-001.
- **원인 2 (종합 레이어가 "압축기 + 점수 문지기")**: `core/intent/formatter.py` 가 스스로 "압축기" 라 명시 (FAST tier 3줄 압축). 전략가(track_a/b)는 점수 임계값 게이트 + "발행 누락 3+ → 기계적 wait". → prism 같은 통찰 서사가 구조적으로 안 나옴.
- **LIVE 베이스라인 결정 증거**: `stock_analyst` 혼자 풍부한 신호(주봉 sweet 1.287 / ROE 18.9% / 영업이익률 42.8% / 실적 가속 / "Track A 진입 친화")를 냈으나, track_a 가 S/F-Score·wealth_strategist 미발행 3건으로 기계적 "wait" → formatter 가 "보류하세요" 앵무새 압축. **이 질문에선 데이터가 아니라 종합 레이어가 병목.**

→ cycle 6 옵션 2 (하이브리드 임원) = 분석가 분리 유지 + 종합 레이어를 "점수 합산" → "doctrine 통합 추론 임원" 으로 교체. 본 SPEC = 그 **최소 PoC**.

## PoC scope

**In**: 임원 doctrine(persona) + executive 종합 모듈 + production_chat A/B 플래그 + 005930 smoke + 단위 테스트.
**Out**: 9 분석가 페르소나 변경, INFRA-SCORE-INPUTS-001(데이터 배선), Quality Evaluator 반복 루프, 2nd-round 반문, frame_mode 결정론 배선(하드닝 백로그 — LIVE 베이스라인서 principle_guardian 이미 advisory_warning 발행 확인), main 머지(PoC 결과 후 별도 결단).

## 결단 (영구 권위)

1. **종합 임원 = 신규 Layer 3 unit** (`chief_executive`), 9 분석가·2 전략가 raw 를 받아 사용자 직답 자연어 1개 발행. 9 분석가는 안 건드림 (받아서 임원이 통합).
2. **임원 = "압축기" 아님**. prism 7 패턴 doctrine (5-layer chain / 시나리오 3 / 솔직 톤 / 상황별 가중치 통합 / 멀티턴 / 수혜·피해 매트릭스 / 과거 사례). max_tokens 8000 (Gemini 2.5 Pro thinking 토큰 예산 잠식 → 답 잘림 방지).
   - **tier 전략 (하이브리드, 2026-05-29 결정)**: 기본 `executive_synthesis` = **BALANCED(Flash, 무료 1,500/일)**. **DEEP(Pro)는 주요 트리거/이벤트/제한 UX 질문만 `model` override** (Pro 무료 50/일 한도 + 비용 ~24배). Pro 발동 케이스 라우팅 = 추후 확정 (SLOT S7). 비교 근거: 005930 smoke — Pro 가 doctrine(라벨 억제·결단력·환각 가드) 완벽 준수 / Flash 는 풍부하나 코드 라벨 누출·관망 후퇴 (doctrine 튜닝으로 좁힘 시도).
3. **전략가 verdict 맹종 금지**. 임원은 전략가의 기계적 "wait" 에 갇히지 않고 분석가 raw 신호를 직접 재통합 (LIVE 베이스라인 병목 직격).
4. **박종훈 거시 framework = 변곡점 전용 회로차단기** (사용자 명시 2026-05-29). 기본 트레이딩 렌즈 = WAVE-ALPHA(α)+7계명+상황별 가중치+regime. 거시는 regime 전환/분배일 4건+/사이클 단계 변화 3 케이스에서만, wealth_strategist cross-reference (직접 인용 X). = memory `feedback_park_jonghoon_scope`.
5. **환각 가드 보존**. 정량 anchor + snapshot 출처 수치만, 없는 데이터 솔직히, 코드 라벨 본문 금지(label_dictionary), 과거 사례 "검증 필요" 라벨. production 경로 `mock_fallback_allowed=False`.

## 검증 기준 (성공 판정)

1. 005930 "삼성전자 살까?" 임원 답변이 prism 7 패턴 시연 + formatter 대비 풍부.
2. 부족 데이터를 방어적 "보류"가 아니라 솔직한 서사로 처리 (전략가 기계적 wait 탈출).
3. 회귀 0 (pytest 619 passed), validate.py 0 errors.
4. **사용자 평가 "prism 수준 이상"** → 옵션 2 확정 → 중간 PoC(Track B + 다종목) → 풀 PoC(9 분석가 cited 자연어 슬림화). 미달 → 데이터(원인 1, INFRA-SCORE-INPUTS-001)로 방향 전환.

## SLOT (후속)

- S1: frame_mode 결정론 배선 (router→run_analyst→build_pipeline_prompt) — advisory 비결정성 하드닝.
- S2: market_snapshot_md 임원 주입 (현재 분석가 raw 에 간접 포함).
- S3: Quality Evaluator 반복 루프 (prism Communication Team 패턴).
- S4: 2nd-round 반문 (임원 → 분석가 재dispatch, 임계값 trigger).
- S5: 9 분석가 cited 자연어 풀이 슬림화 (정량 JSON + 1줄 코멘트만) — 풀 PoC.
- S6: webapp 임원 모드 토글 UI + SSE formatted 이벤트 분기.
- S7: Pro(DEEP) 발동 라우팅 — 주요 트리거/이벤트/제한 UX 질문 판정 기준 (기본 Flash, 중요 질문만 Pro override).
