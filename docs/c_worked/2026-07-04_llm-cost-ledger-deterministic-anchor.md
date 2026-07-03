---
date: 2026-07-04
topic: LLM 비용 원장 + 결정론 anchor 기본화 (Gemini 지출 폭발 대응 — 가시성 우선)
status: completed
plan_file:
---

# 2026-07-04 · LLM 비용 원장 + 결정론 anchor 기본화

## 배경
Gemini 월 지출이 매일 폭발적으로 늘어 사용자가 AI Studio 지출 상한을 걸고 며칠간 서버 중단.
요구 = "다른 벤더로 갈지 말고 현 구조에서 지출 줄이되 결과물 최대한 유지." **진단 결과 진짜
청구서가 로컬에 기록이 없어(캐시 테이블은 멱등이라 대형 호출 미기록) 추측만 가능했던
가시성 부재가 근본 장애.** 핵심 판단: 추측으로 끄지 말고 **① 비용 원장(가시성) 세우고 →
② 실증된 낭비(anchor LLM)를 결과물 손실 없이 제거**. 단계 = OPS-CLOUD-001 아래 LLM-COST-LEDGER-001.

## 한 일
### ① 비용 원장 (M-A)
- `core/db/schema.sql` — `llm_cost_ledger` 테이블 + 인덱스(day/provider·model/call_type). 캐시와 별개, 모든 호출 1행씩.
- `core/llm/ledger.py` (신규) — `record_llm_cost` writer + `cost_summary(days)` 집계(벤더·모델·질의영역·일자).
- `core/llm/client.py` — `call_llm` 에 `call_type`·`target` 파라미터 + `_record_ledger`(served + cache hit 기록, mock 제외). provider 는 raw.provider 우선.
- 9개 호출처에 call_type 라벨: `core/inference/run_analyst.py`(analyst:<id>), `core/strategist/run_strategist.py`(strategist:<track>), `core/executive/synthesize.py`(executive), `core/intent/{classifier,formatter,router}.py`, `collectors/{anchors,theme_match,news_source,market_view}.py`, `pipelines/market_briefing_pre/stages/analyze.py`(briefing).

### ② 결정론 anchor 기본화 (M-B)
- `core/config/schema.py` — `AlphaConfig(anchor_llm_enabled=False)` + `RuntimeConfig.alpha`.
- `config/defaults.yaml` — `alpha.anchor_llm_enabled: false`.
- `collectors/anchors.py` — `_deterministic_anchors` 헬퍼 추출 + `_compute_one` 이 config false 시 LLM 우회하고 결정론 픽 기본(source='deterministic'), true 시에만 Stage2 LLM. source Literal + render 범례 갱신.
- `tests/test_anchors.py` — 결정론 기본 가드 테스트 추가 + 기존 fallback 테스트를 config 게이트(anchor_llm_enabled=true)로 수정.

### ③ 운영자 화면 (M-C·M-D)
- `server/api/ops.py` (신규) — `GET /api/ops/llm-cost?days=N`. `server/main.py` 라우터 등록.
- `webapp/src/lib/api.ts` — `LlmCostSummary` 타입. `webapp/src/app/ops/llm-cost/page.tsx` (신규) — 총계 + 벤더/모델/질의영역 막대 + 일자별 표, 7/14/30일 토글. 유저 내비 밖(비노출 URL).
- `docs/specs/LLM-COST-LEDGER-001-...md` (신규) — SPEC (status=verified).

## 검증 결과
- ✅ 관련 테스트 400+ 통과 (test_anchors 47, auto_signal, run_strategist, track_b, market_view, theme_match, news_source, executive, intent/*, run_analyst*, llm_mock_fallback).
- ✅ `scripts/validate.py` 0 errors. webapp `tsc --noEmit` 신규 파일 에러 0.
- ✅ **실 Gemini 라이브**: anchor α 005930·000660 6/6 timeframe 산출(deterministic, LLM콜 0) — LLM 성공분과 소수점까지 동일, LLM이 실패하던 4/6도 성공. 원장 writer→cost_summary 3축 집계 실콜 검증.
- ✅ **실서버 라이브**: production chat 종목분석 1회 = 10콜/$0.024/입력16.6만토큰 원장 캡처(분석가6+전략가2+formatter+market_view), anchor_selection 부재=결정론 전환 production 확인. 3회 누적 27콜/$0.067.
- ✅ "빈 답변" 파봄 = 검증 curl이 top-level `.text`(없음) 읽은 파싱오류. 실제는 `formatted.text` 297자 정상(is_mock=False). 시스템 버그 아님.

## 의도적으로 안 한 것
- 분석가/전략가 판단 호출 캐싱 — 사용자 반박 반영: 장중 입력(시장 스냅샷) 계속 변해 히트율 낮음 + temperature>0 변주 자연스러움 → 명확한 이득 아님. 결정론 분류(anchor/theme/intent/news)만 캐싱 옳고 이미 됨.
- 결정론 JSON collector tier flash→flash-lite — 후속 절감 후보로 백로그.

## 다음에 이어서 할 작업 (우선순위)
1. **원장 켠 채 하루 실가동 → 실측** — 추측 끝. 분석가 fan-out vs 입력토큰 vs cadence 중 진짜 주범을 `/ops/llm-cost` 숫자로 확정하고 그 위에서 절감 결정.
2. **"활용" 절감 (품질 유지형)** — 질문에 필요한 분석가만 부르기(6→2~3, 라우터가 sub-task 분배) + 분석가 주입 컨텍스트 다이어트. 입력토큰 16~48만/채팅이 비용 본체. (참고 [[feedback_analyst_subtask_decomposition]])
3. **"종합 판단 부재" 별개 진단** — "종목은 좋은데 시장 미반영" → 아낀 예산을 시장-엮는 종합 판단에 투입 (별도 SPEC 후보). 단 이번 라이브에선 답변이 시장(분산일 4건)을 실제 인용 — 케이스 편차 확인 필요.

## 맥락 재진입 힌트
- 운영자 화면 보기: `just server` + webapp `npm run dev` → `http://localhost:3000/ops/llm-cost`. API 직접: `http://localhost:8000/api/ops/llm-cost?days=7`.
- anchor LLM 되살리려면 `config/runtime.yaml` 에 `alpha: {anchor_llm_enabled: true}` (hot reload).
- production chat 응답 = `formatted.text` (top-level text 없음). 라우터 prefix `/api/chat/production`.
- 부수 발견: production chat 은 판단 호출 input_hash 미전달 → 동일 질문도 매번 과금(단 위 "안 한 것" 참고, 명확한 낭비 아님).

## 커밋 상태
- 이 wrap-up 에서 커밋 예정 (feat 코드+spec 1커밋 + docs wrap-up 1커밋), main FF + push.
