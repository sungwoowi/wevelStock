---
spec_id: INFRA-LLM-STREAM-001
title: LLM Token Streaming (SSE) — webapp 채팅 첫 토큰 latency 단축
team: shared
type: feature
status: draft
version: 1
owner: platform
generates:
  - tests/test_llm_streaming.py
modifies:
  - core/llm/client.py
  - core/llm/claude_code_backend.py
  - core/inference/run_analyst.py
  - server/api/analyst_chat.py
  - webapp/src/app/analyst-chat/page.tsx
depends_on:
  - M3 분석가 가동 (run_analyst, analyst_chat 완료)
contracts:
  - name: llm-stream-event-v1
    version: "1.0"
---

# INFRA-LLM-STREAM-001 — LLM Token Streaming (SSE)

## 목적

분석가 LLM 호출 응답 ~40s 동안 사용자가 0초 동안 아무것도 못 보는 문제를 해결. 토큰 생성될 때마다 점진 표시 → 첫 토큰 1-3s, ChatGPT/Claude.ai 와 동등한 체감.

본질 위치: 분석가는 자동 호출이 본업 (user_want_spec 의 알림 Agent). streaming 은 자동 흐름과 무관 — **webapp 채팅의 검증/디버그 UX 만 영향**. 그러나 검증 UX 개선이 사용자가 분석가 응답 품질을 평가하는 회수를 좌우 → 결과적으로 시스템 고도화 속도에 영향.

## 배경 / 문제

현 흐름:
- `core/llm/client.py:call_llm()` 이 통 응답 dict 반환 (`messages.create()` / `generate_content()` / subprocess `communicate()`)
- `server/api/analyst_chat.py:POST /chat` 이 `ChatResponse` JSON 반환
- `webapp/src/app/analyst-chat/page.tsx` 가 `await res.json()` — 한 번에 받기

claude_code 호출 ~40s, gemini 호출 ~5s, anthropic 호출 ~10s. **각 provider 모두 streaming 메서드 제공**:
- Anthropic SDK: `client.messages.stream()`
- Gemini: `client.aio.models.generate_content_stream()`
- claude_code CLI: `--output-format stream-json --include-partial-messages`

## 핵심 정의

| 용어 | 의미 |
|---|---|
| **stream event** | `{"type": "text_delta"|"metadata"|"error"|"done", ...}` dict |
| **call_llm_stream** | 신규 async iterator. provider 추상화 + fallback chain 포함 |
| **SSE** | Server-Sent Events. `text/event-stream` MIME, `data: {...}\n\n` 형식 |
| **partial failure** | 첫 청크 받기 전 실패 = fallback 가능, 첫 청크 후 실패 = partial + error event |

## 이벤트 계약 (llm-stream-event-v1)

```python
# text_delta — 토큰 청크 (가장 빈번)
{"type": "text_delta", "text": "한 글자나 단어 등"}

# metadata — stream 종료 직전 1회. call_llm 의 dict 와 동일 키
{"type": "metadata",
 "tokens_in": int, "tokens_out": int, "model": str,
 "cost_usd": float, "cache_read_tokens": int,
 "cache_creation_tokens": int, "raw": dict}

# error — provider 에러 발생 시
{"type": "error", "message": str, "provider": str, "fatal": bool}

# done — 정상 종료 마커 (SSE 클라이언트가 close 시점 인식)
{"type": "done"}
```

## 백엔드 설계

### `core/llm/client.py`

```python
async def call_llm_stream(
    *, system, messages, input_hash=None, model=None,
    max_tokens=None, temperature=None, provider=None,
) -> AsyncIterator[dict]:
    """provider 분기 + fallback chain. text_delta * N → metadata → done."""
```

cache 는 streaming 에서 제외 (cache hit 시 즉시 metadata + done 만 emit). 멱등성 키는 후속 백로그.

### `core/llm/claude_code_backend.py`

신규 함수 `call_claude_code_stream`. CLI args 에 `--output-format stream-json --include-partial-messages` 추가 → `proc.stdout.readline()` 비동기 루프 → JSONL 파싱 → `content_block_delta.delta.text` 만 추출. 종료 시 `result` 메시지의 usage 로 metadata 조립.

### `core/inference/run_analyst.py`

신규 함수 `run_analyst_stream` — manifest+persona+canon+RAG+memory+market_snapshot 합성은 동일, 호출만 `call_llm_stream`. text_delta 들이 흘러 나옴 + 끝에 metadata.

## API 설계

`server/api/analyst_chat.py` 신규 endpoint:
```
POST /api/analysts/{id}/chat/stream
Content-Type: application/json
Body: ChatRequest (기존)
응답: text/event-stream
```

기존 `POST /chat` 은 그대로 유지 (회귀 안전).

## webapp 설계

`webapp/src/app/analyst-chat/page.tsx`:
- fetch URL `/chat` → `/chat/stream`
- `await res.json()` → `response.body.getReader()` 루프
- 토큰 누적해서 마지막 message 부분 갱신 (state setter)
- metadata 이벤트 받은 후 MetadataBar 표시
- streaming default ON. 토글은 백로그.

## 검증

- `pytest tests/test_llm_streaming.py -v` 통과 (mock provider stream)
- 회귀: 전체 테스트 (현재 87) 회귀 0
- Live smoke: webapp 채팅 1회. 첫 토큰까지 ms 측정
- 기존 `POST /chat` 회귀 안전

## 의도적 제외

- streaming on/off 토글 UI (default ON, 토글은 백로그)
- 텔레그램 streaming (atomic 메시지라 의미 없음)
- 자동 호출 흐름 streaming (run_analyst 그대로)
- token-by-token 비용 누적 표시 (metadata 일괄)
- streaming response cache (멱등성 키 전략 후속)
