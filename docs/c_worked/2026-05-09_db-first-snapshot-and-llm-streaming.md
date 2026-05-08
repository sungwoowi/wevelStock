---
date: 2026-05-09
topic: 시장 스냅샷 DB-first hybrid (옵션 A) + LLM token streaming (SSE)
status: completed
plan_file: C:\Users\HOME\.claude\plans\reflective-wondering-volcano.md
---

# 2026-05-09 · DB-first 시장 스냅샷 + LLM streaming (SSE)

## 배경

직전 세션 백로그 Top 1 = 옵션 A (DB-first hybrid). `collectors/snapshot.py` 7 collector 가 `pipelines/market_briefing_{now,pre}/stages/collect_*` 와 100% 중복 호출 → 5-Layer "수집팀 → 분석팀" 단방향 위반 + 분석가 호출마다 cold fetch ~30s. 본 세션 1단계로 해결.

이어 사용자가 "LLM 응답 통째로 기다리니 느리다 — slim window 같은 거?" 질문 → **streaming (SSE) 도입** 으로 전환. 분석가 자동 호출은 본업 (알림 Agent) 이라 streaming 무관, 그러나 webapp 채팅의 검증/디버그 UX 가 본질적 가치. INFRA-LLM-STREAM-001 SPEC 신설.

핵심 판단: 분석가 streaming UX 의 본질은 Gemini/Anthropic SDK 의 진짜 streaming. claude_code 는 부팅 ~12s + Windows uvicorn 의 SelectorEventLoop subprocess 한계 → silent batch_thread fallback 이 합리적 타협.

## 한 일

### 옵션 A — 시장 스냅샷 DB-first hybrid (2 커밋)
- `collectors/snapshot.py` — `kr/us_threshold_seconds()` 시간대 인식 임계 (cron 발동 시각 기반, 정규장 중 ~3h, 장 마감 후 ~18h, 주말 월요일 09:30 까지 ~66h) + 4개 어댑터 (`_adapt_overnight/kr_indices/supply_sectors/leading_from_part`) + `build_market_snapshot()` 재작성 (DB 조회 → 임계 판정 → stale 그룹만 cold fetch). `MarketSnapshot` 에 `source_map`, `db_run_ids`, `db_age_seconds` 필드 추가. `render_snapshot_md` 헤더에 `_데이터 출처: 미국=DB (X시간 전 적재)_` 라인 추가. 인메모리 캐시 TTL default 300s → 60s (DB-first 가 0.3s 라 5분 캐시는 cron 직후 옛 데이터 노출 위험만)
- `core/inference/run_analyst.py` — metadata 에 `snapshot_source_map` + `snapshot_db_run_ids` 2 키
- `tests/test_market_snapshot.py` — fixture 에 `parts_store.get_latest_parts_with_age` None mock (회귀 안전) + 신규 19 케이스 (임계 7 / 어댑터 4 / 부분 fetch 4 / render 헤더 4)

### LLM streaming (SSE) — 4 커밋
- `core/llm/client.py` — `call_llm_stream()` async iterator + `_stream_anthropic` (messages.stream) / `_stream_gemini` (client.aio.models.generate_content_stream) / `_stream_mock` (5글자 청크). fallback chain (첫 청크 전 실패만 다음 provider). `llm_stream_failed` 로그에 `error_repr`/`error_type` 추가
- `core/llm/claude_code_backend.py` — `call_claude_code_stream()` wrapper + `_claude_code_stream_native()` (CLI `--output-format stream-json --include-partial-messages`, JSONL 파싱) + `_call_claude_code_sync_via_thread()` (subprocess.run + asyncio.to_thread). stdin 송신을 background task 로 분리 (Windows pipe deadlock 회피) + subprocess `limit=10MB` (skill md 한 라인 64KB 초과). `_can_spawn_subprocess()` 사전 체크 — SelectorEventLoop 면 native 시도 X 로 silent batch_thread (warning 0)
- `core/inference/run_analyst.py` — `run_analyst_stream()` async iterator + `first_token_ms` metadata
- `server/api/analyst_chat.py` — `POST /api/analysts/{id}/chat/stream` (`StreamingResponse text/event-stream`)
- `webapp/src/app/analyst-chat/page.tsx` — fetch `/chat/stream` + `response.body.getReader()` + SSE 프레임 (`data: {...}\n\n`) 파싱. 빈 assistant 메시지 미리 추가 → text_delta 누적. `MetadataBar` 에 `(first XXXms)` 초록 라벨
- `tests/test_llm_streaming.py` — 7 신규 (mock provider stream + fallback chain + run_analyst_stream + first_token_ms)
- `docs/specs/INFRA-LLM-STREAM-001-llm-streaming.md` — SPEC 신설

## 검증 결과

- ✅ pytest 60 → 94 통과 (옵션 A 19 + streaming 7 + render 헤더 1, 회귀 0)
- ✅ TypeScript 타입 체크 통과
- ✅ Live smoke (옵션 A): `cold_collectors=0`, `source_map={'kr':'db','us':'db'}`, elapsed 0.28s (이전 ~30s)
- ✅ Live smoke (claude_code stream native, ProactorEventLoop): 첫 토큰 ~12s, output 122 토큰
- ✅ Live smoke (claude_code stream batch_thread, SelectorEventLoop 강제): 정상 응답 + warning 0 + `stream_fallback=batch_thread` 마커
- ✅ 사용자 webapp 검증: Gemini streaming 토큰 흐름 정상, claude_code batch_thread silent fallback 정상

## 의도적으로 안 한 것

- **4명 분석가 분화 + canon 분기** — 직전 세션 백로그 Top 2. 본 세션 옵션 A → streaming 흐름이 길어 다음 세션
- **Anthropic SDK key 등록** — claude_code 의 12s 부팅을 줄이려면 anthropic provider (~2s 첫 토큰) 가 답이지만 Pro/Max 무료 혜택 포기. 사용자 선택은 batch_thread fallback
- **streaming on/off 토글 UI** — default ON 으로 두고 토글은 백로그
- **streaming response cache (멱등성)** — call_llm 의 cache_lookup 패턴 streaming 용 미적용. 후속 백로그
- **공휴일 캘린더** — `pykrx.get_business_days()` 도입 시 한국 공휴일 인지 임계 가능. 1회 cold fetch 회피 가치 작아 미반영

## 맥락 재진입 힌트

- **claude_code latency 분해**: subprocess 부팅 ~3-5s + OAuth keychain handshake ~3-5s + 첫 LLM 처리 ~2-3s = ~12s. CLI 자체 한계라 streaming 도입에도 단축 X. Anthropic SDK 직접 호출은 ~2s.
- **Windows uvicorn = SelectorEventLoop**: `asyncio.create_subprocess_exec` 가 NotImplementedError. `_can_spawn_subprocess()` 가 loop type 사전 검사 → SelectorEventLoop 면 sync subprocess + asyncio.to_thread 의 batch_thread 직행. ProactorEventLoop (CLI, just ask) 환경에선 native streaming.
- **stream_fallback 진단 마커**: claude_code 의 raw.stream_fallback="batch_thread" 면 silent fallback 발생 (warning 없음). webapp MetadataBar 의 `(first XXXms)` 가 latency_s 와 거의 같으면 batch fallback.
- **시간대 인식 임계 핵심**: `kr_threshold_seconds(now_kst)` = `now - last_expected_cron_time + 60s grace`. 평일 정규장 중엔 짧고, 장 마감 후엔 다음 cron 까지, 주말은 월요일 09:30 까지.

## 다음에 이어서 할 작업 (우선순위)

1. **4명 분석가 분화 + canon 분기 (옵션 B)** (PC, 3~4h) — 자산전략가 통합 canon 답변이 영역 침범 (7계명·심법·박종훈 모두 인용). 5-Layer 1:1 매핑 정합. `agents/analysts/{principle_guardian, trade_coach, stock_analyst, news_curator}/{persona, manifest}` 4 set + `core/knowledge/compose.py:load_shared_canon()` reads 분기 + run_analyst spec.reads 패스. 매매코치 추가하면 자산전략가와 톤 비교로 분화 의미 즉시 입증.

2. **종목분석부 자료 첫 ingest** (PC, 1h) — `rag_docs/logchart/` (untracked, ~288KB) 차트 교육 자료 가용. 종목분석가 분화 시 RAG 즉시 활용. 5 학습부 마지막 미채움. `knowledge/reference/stock_analysis/` 이동 + `just knowledge-sync stock_analysis` + 검증.

3. **streaming 토글 UI + AbortController** (PC, 1.5h) — webapp 에 streaming on/off 토글 + 응답 도중 cancel 버튼. default ON 유지하되 batch 모드 회귀 옵션. AbortController 로 fetch cancel + SSE reader cancel.

(추가 백로그: streaming response cache 멱등성 / KIS 토큰 캐시 검증 / claude_code anthropic API key 옵션)

## 커밋 상태

- ✅ `bead271 feat(snapshot): DB-first hybrid + 시간대 인식 임계 + 부분 fetch`
- ✅ `e318768 feat(snapshot): 캐시 TTL 60s 단축 + render 데이터 출처/시점 헤더`
- ✅ `bb63929 feat(llm): token streaming (SSE) — call_llm_stream + SSE endpoint + webapp 점진 렌더`
- ✅ `5a9f798 fix(llm): claude_code stream deadlock — background stdin + readline 10MB limit`
- ✅ `723ef5f fix(llm): claude_code stream — SelectorEventLoop NotImplementedError 우회`
- ✅ `224e5e5 fix(llm): claude_code 환경 사전 체크 — SelectorEventLoop 시 native 시도 X`
- ✅ main push 완료 (`1e65c69..224e5e5`)
- 본 wrap-up 후 추가 커밋 1건 + push 예정 (사용자 요청)
