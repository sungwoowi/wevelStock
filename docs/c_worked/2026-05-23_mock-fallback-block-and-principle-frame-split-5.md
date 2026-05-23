---
date: 2026-05-23
topic: track_b MOCK silent fallback 차단 + principle_guardian advisory/execution frame 분리 (5번째 세션)
status: completed
plan_file:
---

# 2026-05-23 · track_b MOCK silent fallback 차단 + principle_guardian advisory/execution frame 분리

## 배경
PROD-UX-1+2 시연 후 사용자 보완점 제보 4건 (수급/원칙수호자/실적/chat AI 비교) 진단 + 우선순위 재정의 (RESUME Top 3 vs 사용자 제보 통합 표). 본 세션 scope = #1 (track_b MOCK 응답) + #2 (principle_guardian frame 분리) — 사용자 즉시 체감 + 작은 변경 우선.

**핵심 판단**: track_b 의 `[MOCK]` 응답 = gemini transient failure → claude_code fallback 실패 → silent mock fallback 의 발현. 본질은 **production 사용자 경로에서 silent mock 노출 자체 차단** (mock 발생 자체 fix 가 아닌 path 차단). principle_guardian 의 OS1·OS3 violation 발동 = **advisory frame vs execution frame 미분리**. 일반 의견 단계에서 placement 입력 (`stop_loss_price`) 결측을 violation 으로 발동시키는 잘못. frame 분리로 silent blocking 해소.

## 한 일

### #1 track_b MOCK silent fallback 차단 (`mock_fallback_allowed` flag)
- `core/llm/client.py` — `call_llm` / `call_llm_stream` / `_resolve_provider` / `_dispatch_provider` 에 `mock_fallback_allowed: bool = True` 파라미터 추가. False 면 real provider 전부 실패 시 RuntimeError 전파 (기본 True = legacy dev/CI 동작 보존)
- `core/inference/run_analyst.py` — `run_analyst` / `run_analyst_stream` 에 동일 forward
- `core/strategist/run_strategist.py` — `run_strategist` / `run_strategist_stream` 에 동일 forward
- `core/intent/router.py` — production-chat 6개 wrap (`_call_strategist_safe` / `_call_analyst_safe` / `_stream_strategist_safe` / `_stream_analyst_safe` / `_call_refuse_or_guide` / `_stream_refuse_or_guide`) 에서 `mock_fallback_allowed=False` 강제
- `core/intent/formatter.py` — `format_answer` 도 mock_fallback_allowed=False + `_compose_user_message` 가 is_mock/upstream_error 응답을 본문에서 제외하고 "응답 누락" 섹션에 ID만 표기 + 모든 응답 누락 시 LLM 호출 자체 skip + 명시 안내 return
- `webapp/src/app/production-chat/components/EvidenceToggle.tsx` — is_mock 응답은 빨간 border + "⚠ MOCK 응답" 뱃지 + upstream_error 명시 표시
- 신규 `tests/test_llm_mock_fallback_gate.py` (6 cases) — `_resolve_provider` flag gate + `call_llm` 실 호출 RuntimeError 전파 + legacy default 동작 보존
- `tests/intent/test_formatter.py` — 회귀 fix + 신규 2 (compose_excludes_mock_entries + skips_llm_when_all_responses_missing)
- `tests/intent/test_router.py` — 신규 3 (`TestMockFallbackForwarded`: track_a / both / analyst_direct 가 모두 mock_fallback_allowed=False forward)
- 회귀 fix 3: `tests/test_llm_streaming.py` (stub lambda `**_kwargs`) + `tests/test_run_strategist.py` + `tests/test_track_b_strategist.py` (fake_call_llm `**_kw`)

### #2 principle_guardian frame 분리 (advisory vs execution)
- `config/analyst_subtasks.yaml` — principle_guardian sub-task 에 **advisory frame 명시** 섹션 신설 + `advisory_warning` verdict 라벨 강제 + **`violation` 라벨 사용 금지** 명시 + Track A/B 가 advisory_warning 을 wait 강제 도미노로 받지 않는다는 명시
- `agents/analysts/principle_guardian/persona.md` — § Reasoning Doctrine 에 **frame_mode 분기 표** 신설 (advisory vs execution × trigger·verdict 라벨) + `issue_verdict` 알고리즘에 frame_mode 인자 추가 + § Outputs 한국어 친화 verdict 표에 `advisory_warning (사전 검토 권장 — advisory frame)` 라벨 추가 + StandardOutput 매핑에 verdict 5종 정합
- `agents/analysts/principle_guardian/manifest.yaml` — response_rules 에 frame_mode 섹션 신설 + verdict 분기 표 갱신 + verdict 산출 결정론 룰 frame 분기 (advisory frame 의 OS 위반 → advisory_warning, execution frame → blocking violation)
- `agents/strategists/track_a/persona.md` — 진입 조건 #5 ("7계명 위반 0") 에 "**advisory_warning 은 위반 0 처럼 취급**" 명시 + 종합 알고리즘 가중치 표의 principle_guardian 라인 갱신
- `agents/strategists/track_b/persona.md` — 진입 조건 #6 + 가중치 표 동일 정합
- 신규 `tests/test_principle_guardian_frame_split.py` (9 cases) — sub-task prompt advisory frame 명시 + persona doctrine frame 분기 + manifest verdict 표 + Track A/B advisory_warning 처리

## 검증 결과
- ✅ pytest **590 → 610 passed** (+20 신규, 회귀 0). 신규 11 (#1) + 9 (#2). 회귀 fix 3 stub kwargs 수용
- ✅ validate.py 0 errors (teams/registry.yaml warning 은 기존 비차단)
- ✅ webapp tsc 0 errors
- ✅ 재현 시연 (`curl POST /api/chat/production` "삼성전자 살까?") = Track A·B 양쪽 정상 gemini 응답 (Track B latency 24.4s / cost $0.0017 / model gemini-2.5-flash, is_mock=False). 본 호출에서는 transient failure 미발생 — silent mock path 차단은 결정론 unit test 로 보강

## 의도적으로 안 한 것
- **#3 INFRA-SCORE-INPUTS-001 SPEC 인터뷰** — ~1.5 세션 별 사이클로 분리 (사용자 결정 = #1+#2 까지)
- **#5 production UX 부분 답변 정직성** — 별 작업으로 분리 (~1 세션)
- **gemini transient failure root cause fix** — silent fallback path 차단으로 충분 (사용자 입장 가짜 응답 노출 X). retry 강화는 별 영역
- **commit 자동화** — 사용자 명시 후 진행

## 기술 부채/미완
- **서버 재시작** (PID 33600) — 본 fix 가 실제 호출에 반영되려면 사용자 console 에서 수동 재시작 필요 (`just server` 의 `--reload` 여부 미확인). 자동 reload 면 watchdog 가 처리
- **track_b mock 발생 root cause** = gemini 의 동시 burst quota / timeout 자체는 그대로. silent path 차단으로 사용자 가시화는 보장, 실 응답 안정성은 retry 또는 sequential 호출 (별 작업)

## 다음에 이어서 할 작업 (우선순위)

1. **INFRA-SCORE-INPUTS-001 SPEC 인터뷰** (~1.5 세션) — 사용자 Q1·Q3 본질 해소. `flow_inputs.py` (F-Score 4축) 우선순위 1위 (도미노 끊음). `/spec-interview` 5라운드 면담 → SPEC frozen → Phase 1 (`flow_inputs.py`) 구현. 메모리 `project_score_inputs_gap.md` 그대로
2. **production UX 부분 답변 정직성 + 부분 결론** (~1 세션) — 한 축이 unknown 이어도 다른 축들로 부분 결론 (현재 = 1개 null 시 전체 wait 도미노). LLM 직관 분포 활용 (메모리 `feedback_llm_intuition_distribution`) + 답변에 "현재 측정 가능 / 측정 불가 + 채워질 ETA" 명시
3. **LLM-TIER-MIGRATION-001 microcycle** (~0.5 세션) — `anchors_stage2`/분석가/전략가 영역별 LLM 3계층 점진 마이그레이션. PROD-UX-1 적용 범위 D 점진 결단의 후속

## 커밋 상태
- 코드+테스트 commit + wrap-up commit + push 진행 예정 (사용자 명시 요청 — Step 6)
