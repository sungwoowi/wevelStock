---
date: 2026-05-31
topic: theme_match SLOT S1 라이브 검증 + Gemini thinking 예산 잠식 버그 시스템 수정
status: completed
plan_file: C:\Users\HOME\.claude\plans\compressed-juggling-fairy.md
---

# 2026-05-31 · theme_match 라이브 검증 → Gemini thinking_budget fix

## 배경
직전 세션(SLOT S1 theme_match 2-Stage 골격)이 8000 좀비 소켓으로 **라이브 미검증** 상태로 남아 첫 확인을 진행. 검증 중 theme 분류가 항상 `neutral_fallback` 으로 떨어지는 것을 발견 → 근본 원인 추적 결과 **Gemini-2.5 thinking 토큰이 max_output_tokens 예산을 잠식**해 짧은 JSON 출력이 잘리는 시스템 결함이었음. **핵심 판단**: 결정론 분류/선택 LLM 호출은 thinking 비활성(`thinking_budget=0`)이 필수 — `call_llm` 에 per-call 파라미터를 신설해 theme_match·anchors 양쪽을 동시 해소.

## 한 일
- `core/llm/client.py` — `call_llm` 에 `thinking_budget: int|None` 파라미터 신설 → `_dispatch_provider` → `_call_gemini_real` 까지 스레딩. `_call_gemini_real` 이 `types.ThinkingConfig(thinking_budget=)` 를 조건부로 config 에 주입. None=모델 기본(분석가 긴 추론 보존), 0=비활성(flash), anthropic/claude_code/mock 은 no-op.
- `collectors/theme_match.py` — Stage 2 분류 호출이 `thinking_budget=0` + `max_tokens 200→512`.
- `collectors/anchors.py` — Stage 2 anchor 선택 호출이 `thinking_budget=0` + `max_tokens 400→512`. WAVE-ALPHA 의 deterministic_fallback 결함도 동일 수정으로 해소.
- `tests/test_theme_match.py` (+1) — classify_theme 가 thinking_budget=0 + max_tokens≥512 로 호출하는지.
- `tests/test_anchors.py` (+1) — select_anchors_via_llm 동일.
- `tests/test_llm_mock_fallback_gate.py` (+1) — call_llm(thinking_budget=0) 이 Gemini 백엔드까지 전달되는지 (monkeypatch `_call_gemini_real`).

## 검증 결과
- ✅ pytest **695 → 698 passed** (+3, 회귀 0, `TESTING=1`).
- ✅ in-process (실 Gemini): `resolve_theme_match('005930')` → `theme=AI_semiconductor, source=llm, score=8.0` (샘플 net). 수정 전엔 `tokens_out=8` 잘림 → JSONDecodeError → neutral.
- ✅ **라이브 HTTP 서버** (--reload 자동 반영): `POST /api/analysts/flow_analyzer/chat` 005930 → metadata `flow_inputs_failures` 에 `theme_match: AI_semiconductor (llm) → 4.5`, `is_mock: False`. SLOT S1 라이브 미검증 부채 **해소**.

## 의도적으로 안 한 것
- **inflow_speed 미산출** (`자금 유입 속도 미산출 (시총/market_cap 부재)`) — market_cap 미주입 별개 gap, theme_match 와 무관해 이번 scope 밖.
- **theme_authority/taxonomy/breakpoints production 튜닝** — placeholder 유지(SLOT S2).
- **score 4.5 의 시장 프록시 한계** — 종목 레벨 수급 collector(Top 1) 후 변별력 발현. 설계대로.

## 기술 부채/미완
- net_sums 시장 레벨 프록시 — theme_match·F-Score 변별력은 종목 레벨 수급 collector 후 발현.
- `test_executive.py:136` 은 같은 결함을 max_tokens 8000 으로 우회 중 — thinking_budget=0 로 정리하면 더 깔끔(여유 시).

## 맥락 재진입 힌트
- Gemini-2.5 결정론 JSON 호출은 항상 `thinking_budget=0` + max_tokens≥512. 메모리 `feedback_gemini_thinking_budget_json` 박음.
- theme 분류 캐시 = `llm_call_cache` type='theme_match' (TTL 30일). 라이브 검증 시 `skip_cache=True` 또는 새 ticker 사용.

## 다음에 이어서 할 작업 (우선순위)
1. **종목 레벨 5주체 수급 collector** ⭐ — SPEC(가칭 INFRA-STOCK-SUPPLY-001) + KRX/KIS 종목별 투자자 매매동향. F-Score 세 축(momentum/inflow_speed/theme_match) 동시 시장→종목 실측 승급. theme_match 골격은 `net_sums` 입력만 교체.
2. **SLOT S2 임계 + S3 목표 정밀화** — `config/score_inputs.yaml` breakpoints·theme_authority·rr_rule floor/cap 실분포 튜닝 + R/R ATH 근처 measured-move 보강.
3. **buy_score·S-Score 후속 배선** — scoring.py 정식 가중치(SLOT S7) + SCREEN-RS-EXTENSION-001(rs 축) 같이.

## 커밋 상태
- 코드(client.py/theme_match.py/anchors.py/tests 3) feat 커밋 + wrap-up docs 커밋 → main 직접 push (사용자 명시 요청).
