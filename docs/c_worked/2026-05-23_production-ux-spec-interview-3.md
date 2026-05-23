---
date: 2026-05-23
topic: PRODUCTION-UX-001 SPEC 5라운드 면담 + SPEC 본문 신규 작성 (같은 날 세 번째 세션)
status: completed
plan_file: C:\Users\HOME\.claude\plans\snazzy-bouncing-kahn.md
---

# 2026-05-23 · PRODUCTION-UX-001 SPEC 5라운드 면담 + SPEC 본문 작성

## 배경

같은 날 직전 세션 (2026-05-23 production UX 머티턴 조사, `2026-05-23_production-ux-research-2.md`) 산출 = plan 파일 `jazzy-roaming-snail.md` 7차 갱신 + 사용자 합의 8건 + 7 freeze 항목 도출. 본 세션 = 그 합의에 따라 **`/spec-interview PRODUCTION-UX-001` 5라운드 면담 진행** + **`docs/specs/PRODUCTION-UX-001-natural-language-chat.md` 신규 작성**. 직전 세션의 7 freeze 항목 권위 박음으로 PROD-UX-1 구현 진입 시 재설계 위험 최소화 (CLAUDE.md 원칙 2 정합).

## 한 일

### SPEC 본문 작성
- `docs/specs/PRODUCTION-UX-001-natural-language-chat.md` — **신규 생성** (~400줄). frontmatter (spec_id, generates 15 파일, modifies 2, depends_on 4 SPEC, contracts 2 = `intent-classification-v1` + `production-chat-v1`, status=approved) + 본문 § 8개 (목적 / 배경 / 7 freeze 결단 / 30 시나리오 매핑 표 / 아키텍처 / sub-cycle 3 분할 / 테스트 / SLOT 5 + 검증 기준)

### 5라운드 면담 결단 누적 (`C:\Users\HOME\.claude\plans\snazzy-bouncing-kahn.md` 점진 Edit)
- **R1 본질**: 시나리오 v1=**1~11 freeze** (시연 1~10, 11=pending_ms5) / webapp **보존 + deprecate 라벨 없음** / SLOT S6 흡수 = **Intent JSON parser 강건화만** (anchors.py = `LLM-TIER-MIGRATION-001` 후속)
- **R2 Intent 세부**: Stage 2 default = **Gemini Flash-lite (FAST 계층)** + fallback chain (Flash-lite → Haiku 4.5 → mock) / manual fallback 임계 = **confidence < 0.6** OR ticker 매핑 실패 / cache TTL = **30일** (anchors.py mirror, llm_call_cache.type='intent_classification')
- **R3 라우팅 매핑**: 시나리오 2·5 default = **both** (A+B 동시 호출) / 시나리오 10 = **보유 종목 명세 종합** (Layer 4 미구현 시 v1) / 시나리오 11 = **`pending_ms5`** (v2 이행)
- **R4 종합 답변 포맷**: 압축 방식 = **LLM 1콜 추가 (FAST Flash-lite)** = raw → 1~3줄 결론 + 1~3줄 근거 (수급/차트/실적) / 코드 라벨 사전 = **`config/label_dictionary.yaml`** (외부, watchdog hot reload) / 근거 토글 = **raw 분석가 응답 풀세트 노출** (LLM 추가 호출 X)
- **R5 sub-cycle + 인수**: **3 분할 (PROD-UX-1/2/3) 채택** / PROD-UX-1 시연 = **시나리오 1~5** (사용자 명시 본질) / v1 인수 = **객관 90건 골든 eval ≥ 85% + 사용자 본인 발화 5~10건 만족도**

### 본 세션 추가 본질 결단 (인터뷰 중 도출)
- 사용자가 "30 시나리오 우주가 뭐더라 1~11 이 시연 좋은가?" 질문 → 30 시나리오 표 4 묶음 (A 사용자 명시 5 / B 자동 푸시 6 / C 일상 6 / D 보조·감정 13) 으로 명료 정리 + 1~11 권고 본질 (user_want_spec.md 직접 매핑) 제시
- 사용자가 "manual fallback 임계가 무슨 말?" + "cache TTL 어떤 데이터 캐싱?" 질문 → 쉽게 풀이 (LLM 확신도 점수 + 표현 분류 매핑만 캐싱, 시황·시대 데이터 X) → 같은 옵션 재선택으로 결단 확정
- **사용자 통찰 = "캐싱 대상 = 시대 흐름 vs 시황 vs 표현 분류"** → Intent cache 본질 = 표현 매핑만 → 30일 TTL 안전 확신. 미래 다른 cache TTL 결정 시 동일 frame 적용 가능

### validate.py 정합 정정
- 본 SPEC frontmatter `status: frozen` → **`status: approved`** 변경 (validate.py enum 위반 해소). WAVE-ALPHA-001 의 `status: frozen` 동일 에러 잔존 = 별도 부채 (백로그)

## 검증 결과

- ✅ `uv run python scripts/validate.py` 통과 (PRODUCTION-UX-001 관련 에러 0건)
- ✅ SPEC frontmatter generates 15 경로 모두 신규 (기존 파일 충돌 X)
- ✅ 7 freeze 결단 모두 SPEC § 본문 권위 박힘 (라운드 1~5 추적 가능)
- ✅ 30 시나리오 매핑 표 1~30 풀세트 + v1 시연 = 1~10 명시
- ⚠️  코드 변경 0 (구현은 다음 세션 PROD-UX-1 부터)
- ⚠️  WAVE-ALPHA-001 `status: frozen` 별도 부채 (모든 frozen SPEC 일괄 정정 필요 = 작은 cleanup 백로그)

## 의도적으로 안 한 것

- **PROD-UX-1 코드 작성 X** — SPEC frozen 단독 commit 패턴 정합 (cycle 14 WAVE-ALPHA SPEC + cycle 12 SNAPSHOT-EXTEND SPEC mirror)
- **WAVE-ALPHA-001 status enum 정정 X** — 별도 cleanup 영역, 본 SPEC scope 초과
- **scenario_keywords.yaml + label_dictionary.yaml 초안 X** — PROD-UX-1 sub-cycle 진입 시 작성

## 다음에 이어서 할 작업 (우선순위)

1. **PROD-UX-1 구현** (~1 세션) — Intent Classifier + Routing + 기본 채팅. 시연 = 시나리오 1~5 동작. 산출: `core/intent/{classifier.py, cache.py, router.py, system_prompt.md}` + `config/scenario_keywords.yaml` + `server/api/production_chat.py` + `webapp/src/app/production-chat/page.tsx` + `tests/intent/test_classifier_golden.py` 45건. 인수 = Stage 1 hit ≥ 40%, cache 2회차 ≥ 95%, 45건 정확도 ≥ 85%
2. **PROD-UX-2 구현** (~1 세션, PROD-UX-1 후) — 30 시나리오 6~10 확장 + 종합 답변 포맷터 (`core/intent/formatter.py`) + manual fallback drop-down (`IntentFallback.tsx`) + label_dictionary.yaml + 90건 골든 eval. 인수 = 코드 라벨 grep 0건 + 결론·근거 ≤3줄 assertion
3. **PROD-UX-3 구현 + 사용자 인수** (~1 세션) — `EvidenceToggle.tsx` (raw 풀세트 노출) + streaming 갱신 + 에러 메시지 자연어화 + 발화 로그 일일 리포트. 인수 = 사용자 본인 일상 발화 5~10건 만족도 검증 통과

(추가 백로그: **LLM-TIER-MIGRATION-001 SPEC 신설** = anchors.py Stage 2 Flash → Flash-lite + SLOT S6 통합 / 분석가 9 / 전략가 / 회고분석가 M4 영역별 1 PR 점진 마이그레이션 + 회귀 검증 / **WAVE-ALPHA SLOT S1·S2·S3·S4 후속 SPEC** / **모든 frozen SPEC `status` enum 정정** = approved 또는 implementing 으로 / Layer 4 계좌관리자 (M5) + Layer 5 회고분석가 (M4) / `INFRA-TICKER-RESOLVER-001` 30 종목 한계 해소 / `NEWS-SOURCE-001`)

## 맥락 재진입 힌트

- **SPEC frontmatter status 규약**: `draft / approved / implementing / implemented / verified` 만 valid. `frozen` 은 enum 위반 (validate.py). 다음 SPEC 작성 시 `approved` 사용 권고.
- **`/spec-interview` skill ritual 5 회 누적 ✨** → 영구 ritual (cycle 5 chart / cycle 9 fundamental / cycle 12 snapshot-extend / cycle 14 wave-alpha / **본 cycle production-ux**). 모두 동일 패턴 = ~0.5~1 세션 SPEC + ~1~3 세션 구현 분할 + AskUserQuestion 5 라운드 옵션 (추천 first) + 결단 N 건 영구 권위 + frontmatter status. 미래 모든 인프라/제품 SPEC 신설 시 default 진입점.
- **사용자 본질 명료화 패턴** = 모호한 옵션 답변 ("이게 무슨 말?") → 쉬운 풀이 + 표 + 본질 frame 제시 → 같은 옵션 재선택. 사용자 시간 부담 최소 + 결단 확실성 강화. 본 세션 R2-Q2/Q3 양쪽 활용 = 메모리 `feedback_concise_summary_first.md` 정신.

## 커밋 상태

- 본 wrap-up commit + push 진행 (사용자 명시 "커밋 푸시 해줘")
