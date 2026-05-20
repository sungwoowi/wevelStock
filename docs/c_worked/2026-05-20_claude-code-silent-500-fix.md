---
date: 2026-05-20
topic: claude_code provider HTTP 500 silent 진단 보강 + Selector fallback + 1회 retry (cycle 8)
status: completed
plan_file: C:\Users\HOME\.claude\plans\composed-watching-leaf.md
---

# 2026-05-20 · claude_code provider HTTP 500 silent 진단·해소 (cycle 8)

## 배경

cycle 7 wrap-up 직후 RESUME Top 1 진입. cycle 6.5 production smoke 중 발견된 silent HTTP 500 (body=`{"detail":"inference failed: "}` 빈 message) 의 원인 진단 + 메시지 캡처 보강 + 1회 retry 추가. Explore agent 사전 조사 → 원인 후보 4 위치 + retry 추가 위치 3 후보 식별. 사용자 결정 = "메시지 보강 + claude_code 전용 1회 retry" (Phase 1 풍세트). production smoke 중 추가 발견된 NotImplementedError 원인 = Selector loop subprocess 미지원 → batch_thread fallback 추가 (cycle 8 핵심).

## 한 일

### Part A — backend 메시지 캡처 보강 (4 위치)
- `core/llm/claude_code_backend.py` L204 (sync `call_claude_code` returncode!=0): stderr/stdout 모두 비음 → `"(no stderr/stdout captured)"` 명시
- L383 (`_call_claude_code_sync_via_thread` returncode!=0): 동일 fallback
- L596 (streaming `result` is_error): empty result → `"(no result field in is_error event)"`
- L630 (streaming proc.returncode!=0): stderr 비음 → `"(no stderr captured)"`

### Part B — call_claude_code Selector fallback (cycle 8 핵심)
- `call_claude_code` 시작 부분에 `_can_spawn_subprocess()` 사전 체크 추가 (`call_claude_code_stream` 패턴 미러). Selector loop + json_schema=None → `_call_claude_code_sync_via_thread` 직행 → NotImplementedError 자체 회피. json_schema 사용 시는 그대로 진행 (희귀 케이스).

### Part C — client.py logger 보강 + 1회 retry
- `_dispatch_provider` claude_code branch: RuntimeError("exited") 만 1회 재시도 (200ms backoff). TimeoutError·ClaudeCodeNotInstalled·JSONDecode 등 영구 실패는 즉시 break. logger 에 `error_type` + `error_repr` 키 추가.

### Part D — server endpoint detail fallback (4 endpoint)
- `server/api/analyst_chat.py` + `server/api/strategist_chat.py` 양쪽 chat + chat/stream:
  - `error_detail = str(e) or f"{type(e).__name__} (empty message)"` 적용
  - SSE error event message 도 동일

### Part E — tests/test_claude_code_backend_error_capture.py 신규 (10 케이스)
- backend 메시지 보강 4 케이스 + client retry 4 케이스 + Selector fallback 2 케이스

## 검증 결과

- ✅ pytest 385 → **395 passed** (+10 신규 cycle 8, 회귀 0)
- ✅ `scripts/validate.py` 0 errors
- ✅ **Production smoke** (`ask_analyst wealth_strategist "한 줄로 인플레이션이란?" --provider claude_code`):
  - 1차 (보강 전·후 진단): silent 500 → `inference failed: NotImplementedError (empty message)` (이전 빈 메시지 → type 명 노출 ✨)
  - 2차 (Selector fallback 추가 후): **14.9s 정상 응답** + cited [C1] + cost $0.1404 + cache hit 15,855 tokens ✨

## 의도적으로 안 한 것

- **stream 경로 retry** — 첫 청크 전 fallback chain 이 이미 있어 본질 정합 X. 명시 claude_code provider stream + 첫 청크 전 RuntimeError("exited") 는 별도 백로그.
- **다른 provider (gemini/anthropic) logger 의 error_type/error_repr 보강** — 본 사이클 본질 = claude_code silent 500. 일관성 위해 다른 provider 확장은 별도 백로그.

## 다음에 이어서 할 작업

본 사이클로 cycle 6.5 발견 Top 1 부채 해소. 다음 cycle 9 = RESUME Top 2 (INFRA-FUNDAMENTAL-DATA-001 SPEC) 진입 — MS3 완전 도달 차단점 F5·F2 해소 SPEC.

## 맥락 재진입 힌트

- **빈 string fallback 패턴**: `str(e)` 가 빈 string 인 케이스 (RuntimeError(""), NotImplementedError() 등) 에 `f"{type(e).__name__} (empty message)"` 적용. 4 위치 (backend·client·endpoint·SSE) 일관.
- **`_can_spawn_subprocess()` 사전 체크 패턴**: `call_claude_code_stream` 이 이미 적용 / cycle 8 에서 `call_claude_code` (non-stream) 도 정합. 미래 subprocess backend 추가 시 동일 패턴 우선.
- **RuntimeError("exited") 1회 retry**: 200ms backoff, 명시 provider 호출 (allow_fallback=False) 케이스의 안전망. 다른 provider transient 패턴 발견 시 확장 가능.

## 세션 중 실 비용

- claude_code production smoke 1 회: $0 (Pro/Max 구독)

## 커밋 상태

- cycle 8 코드 commit: `6cc5b5f` "fix: claude_code provider HTTP 500 silent 진단 + Selector fallback + 1회 retry (cycle 8)" (5 files, +435/-30) — push 완료
- cycle 8 wrap-up (본 c_worked + RESUME + SESSIONS) 은 cycle 9 wrap-up 묶음 commit 에 포함 (cycle 8 wrap-up 단독 누락 후 cycle 9 진입한 흐름)
