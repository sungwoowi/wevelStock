---
date: 2026-05-19
topic: INFRA-RUNTIME-EFFICIENCY-001 SPEC + Phase 1 (b) RAG 자료 0 시드 자동 OFF + Phase 2 (a) 서버 모드 reuse — cycle 4 partial
status: partial
plan_file: C:\Users\HOME\.claude\plans\mossy-conjuring-crystal.md
---

# 2026-05-19 · INFRA-RUNTIME-EFFICIENCY-001 SPEC + Phase 1·2 (cycle 4 partial)

## 배경

cycle 3 (자료 있는 3 분석가 v2) 직후 `principle_guardian` 첫 production 호출이 `memory allocation of 17301520 bytes failed` 로 차단. 원인 = BGE-m3 ~2.5GB CLI 매 호출 재로딩. RESUME.md Top 1 = `INFRA-RUNTIME-EFFICIENCY-001` SPEC + 3 묶음 구현. 본 사이클 = SPEC draft + Phase 1·2 까지 완료, Phase 3 (c) embedding_cache + Phase 4 production 검증은 다음 사이클로.

## 한 일

- `docs/specs/INFRA-RUNTIME-EFFICIENCY-001-runtime-efficiency.md` — SPEC 신설 (3 묶음 = 서버 모드 reuse + RAG 자료 0 시드 자동 OFF + SQLite embedding_cache + 단계별 진입 표 + 자동 분기 9 분석가 표).
- `core/knowledge/retrieve.py` — `_get_collection()` 가 `client.get_collection(name=dept)` 로 chunk count 먼저 본 뒤 0 이거나 collection 부재면 `get_embedding_function()` (BGE-m3 wiring) 호출 전에 None 반환. 자료 0 시드 6 분석가 호출 시 BGE-m3 미로딩.
- `tests/test_retrieve_skip_empty.py` — 신규 4 케이스. FakeClient·FakeCollection + ef 호출 카운터로 `count()==0` / `get_collection` raise / `count()>0` 3 경로 모두 ef 호출 횟수 검증 + retrieve end-to-end.
- `scripts/ask_analyst.py` — in-process `run_analyst` 임포트 제거. `httpx.AsyncClient` 로 `POST /api/analysts/{id}/chat` 호출. `WEVELSTOCK_SERVER_URL` env (default `http://127.0.0.1:8000`). connect 실패 = exit 3 + "WevelStock 서버에 연결할 수 없습니다 … 'just server' …" 명확 메시지. 404→2 / 500→1 / timeout→4. `_display_path` 헬퍼 (relative_to fallback).
- `scripts/chat_analyst.py` — 동일 패턴 (멀티턴 REPL, 같은 client 재사용으로 KeepAlive).
- `tests/test_ask_analyst_http.py` — 신규 6 케이스. httpx.AsyncClient mock + 정상/connect error/404/500/provider 전달/auto 모드 exit code·메시지 검증.
- `docs/RESUME.md` — "현재 위치" Phase 1·2 완료 + Top 1 잔여 (Phase 3·4) 갱신.

## 검증 결과

- ✅ `TESTING=1 PYTHONIOENCODING=utf-8 uv run pytest tests/ -q` → **341 passed** (331 → +10, 회귀 0) in 43.73s
- ✅ Phase 1 (b) 신규 4 cases / Phase 2 (a) 신규 6 cases 모두 통과
- ✅ 1 commit + push (`7a49e65`)
- ⏸ production 실 호출 검증 = **다음 사이클** (Phase 3·4 와 묶음)

## 의도적으로 안 한 것

- **Phase 3 (c) SQLite embedding_cache** — 별도 ~0.4 세션. `core/knowledge/embed_cache.py` 신설 + `embedding_cache(model, query_hash, vector, dim, created_at)` 테이블 + retrieve cache hit 분기 (`collection.query(query_embeddings=[v])` 직접 전달).
- **Phase 4 production 호출 재시도** — `just server` 후 `just ask principle_guardian "정량 룰 위반 시나리오 1"` 실 호출 + 메모리 충돌 0 확인 + 2 회차 latency 가시 감소. ~0.3 세션.
- **`operational_safeguards` 권위 SPEC 정정** — 회장 핑퐁 [22] 권고 (cycle 3) 의 INFRA 첫 commit 묶음 권유는 본 사이클 분량으로 인해 별도 SPEC 으로 분리. cycle 5 합류 후보.
- **chat AI 외부 reviewer 핑퐁** — Phase 3·4 완료 후 cycle 4 풀세트 1회로 묶음.

## 맥락 재진입 힌트

- **CLI 사용 패턴 영구 변경**: `just ask` / `just chat` 호출 전 다른 터미널에 `just server` 살아있어야 함. server 부재 시 exit 3 + 안내 메시지. silent fallback 금지 원칙 (`feedback_silent_env_fallback.md`).
- **자동 분기 9 분석가**: 자료 0 시드 6 (`market_state_analyzer`·`stock_picker`·`stock_analyst`·`trading_journalist`·`flow_analyzer`·`news_curator`) = RAG OFF / 자료 있는 3 (`principle_guardian`·`trader`·`wealth_strategist`) = RAG ON. SPEC 본문 표 참고.
- **server 첫 호출 latency ~30s** (자료 있는 분석가 첫 호출 시 BGE-m3 cold). 이후 lru_cache 로 ~3s. Phase 3 (c) 후엔 동일 query 재호출 < 2s.
- **`_get_collection` 가드 순서**: idx 존재 → `chromadb.PersistentClient` → `client.get_collection(name=dept)` (ef 없이) → `count()` 확인 → 0 이면 None / >0 이면 `get_or_create_collection(name=dept, embedding_function=ef)` 로 다시 가져옴. `get_or_create` 가 ef wiring 의 유일한 지점.

## 다음에 이어서 할 작업 (우선순위)

1. **Phase 3 (c) SQLite embedding_cache + Phase 4 production 호출 검증 묶음** (~0.7 세션) — `core/knowledge/embed_cache.py` + 테이블 + retrieve cache hit + `just server` 실 호출 = `principle_guardian` 메모리 충돌 0 + 자료 0 시드 분석가 BGE-m3 미로딩 로그 확인. MS0 도달.

2. **양 트랙 통합 production 검증 + 자연 인계 메커니즘 검증** (~0.5 세션) — Phase 4 후 진입. `both: 삼성전자` 호출 → Track A·B 동시 권고 + Track B 1 파 완성 시나리오에서 Track A 인계 자연 메커니즘 검증. MS1·MS2 도달. webapp default agent 교체 결정.

3. **`stock_analyst` v3 마이크로 정정 + `INFRA-CHART-DATA-001` SPEC 묶음** (~1.3 세션) — 환각 가드 2 (INFRA 미구현) 제거 + KIS daily chart API + pandas-ta + matplotlib vision. MS3 도달. `WAVE-ALPHA-001` (Module A α 공식) 과 묶음 가능.

(백로그: `operational_safeguards` 권위 SPEC 정정 (별도 작은 SPEC, cycle 5 합류 후보) / `GUIDANCE-ACCURACY-TRACKER-001` / `WAVE-ALPHA-001` / `INFRA-RELIABILITY-VALIDATOR-001` / `RETROSPECT-ANALYST-001` / Layer 4 계좌관리자 / news_curator SLOT S2)

## 커밋 상태

- ✅ cycle 4 partial 본체 = `7a49e65` (SPEC + retrieve.py + ask_analyst.py + chat_analyst.py + 2 신규 test + RESUME.md) push 완료
- 본 wrap-up commit (c_worked + SESSIONS.md + RESUME.md 미세 갱신) 진행
