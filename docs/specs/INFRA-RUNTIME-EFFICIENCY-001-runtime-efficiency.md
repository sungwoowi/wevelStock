---
spec_id: INFRA-RUNTIME-EFFICIENCY-001
title: 런타임 효율성 — 서버 모드 reuse + 자료 0 시드 RAG 자동 OFF (+ embedding_cache 백로그)
team: shared
type: feature
status: implemented
version: 2
owner: platform
generates:
modifies:
  - scripts/ask_analyst.py
  - scripts/chat_analyst.py
  - core/knowledge/retrieve.py
  - tests/test_retrieve_skip_empty.py
  - tests/test_ask_analyst_http.py
depends_on:
  - INFRA-RAG-001 (5-Layer RAG + BGE-m3 wiring)
  - ANALYST-PERSONAS-001 (분석가 manifest reads/canon_categories)
contracts:
  - 없음 (런타임 효율 — 분석가 응답 스키마 불변)
---

> **v2 변경 (2026-05-19 cycle 4 풀세트 후)**: Phase 1 (b) RAG 자료 0 시드 자동 OFF + Phase 2 (a) 서버 모드 reuse 만으로 cycle 3 production 차단 (`memory allocation failed`) **본질 해소 확인**. Phase 4 검증에서 (c) SQLite embedding_cache 의 latency 효과 = LLM 11s dominant 대비 ~50ms = **0.4% 미만** 으로 측정됨. (c) = 본 SPEC 에서 **백로그 강등**. 별도 SPEC (예: `INFRA-EMBEDDING-CACHE-001`) 으로 다중 dept 동시 호출·고빈도 재호출 워크플로우가 실제로 latency bottleneck 으로 나타날 때 진입.


# INFRA-RUNTIME-EFFICIENCY-001 — 런타임 효율성

## 목적

분석가 호출 시 BGE-m3 ~2.5GB 임베딩 모델의 **중복 로딩을 제거**하여 production 호출 가능 상태로 복귀. `cycle 3` (2026-05-19 자료 있는 3 분석가 v2) 직후 `principle_guardian` 첫 production 호출이 `memory allocation of 17301520 bytes failed` 로 차단됨. 이 SPEC = **MS0 (양 트랙 시연 가능) 도달 전제**.

## 배경 / 문제

`scripts/ask_analyst.py` CLI 는 in-process 로 `run_analyst()` 를 호출한다. 그러나:

1. **CLI 매 실행 = 새 Python 프로세스**. Python 인터프리터 + imports + `core/knowledge/retrieve.py:_get_collection` 의 `lru_cache` 가 매 실행마다 초기화. 같은 분석가에 두 번째 질문해도 BGE-m3 가 다시 로드된다.
2. **자료 0 시드 분석가도 RAG 시도**. 9 dept 중 6 dept (`market_macro`, `stock_selection`, `stock-analysis`, `trading_journal`, `flow_analysis`, `news`) 가 canon md 0 인데 `data/chroma/<dept>/` 디렉토리는 만들어진 상태 (빈 collection). `retrieve()` 진입 → `chromadb.PersistentClient` 열림 → `get_embedding_function()` 호출 → BGE-m3 wiring (2.5GB 로딩). 자료 0 인데 임베딩만 잡아먹는다.
3. **같은 query 재호출 시 query 임베딩 재계산**. Chroma 의 `collection.query(query_texts=[...])` 는 내부에서 매번 query 텍스트를 BGE-m3 로 임베딩. lru_cache 가 살아있어도 query 가 다르면 새로 계산. 사용자가 같은 질문을 다시 던지면 BGE-m3 forward pass 가 또 돈다.

### cycle 3 진단 (구체)
- `principle_guardian` 시나리오 1 호출 시 BGE-m3 ~2.5GB 로딩 중 추가 17MB 할당 실패
- 사용자 PC 메모리 거의 가득 참 (Chrome + Claude Code + 다른 프로세스 + Chroma 합산)
- 단순 자원 인식 차원이 아니라 **운용 구조 본질 제약** — Top 2 (양 트랙 통합 production 검증) 도 같은 부담 누적

## 핵심 정의

| 용어 | 의미 |
|---|---|
| **CLI in-process** | `scripts/ask_analyst.py` 가 `run_analyst()` 를 같은 Python 프로세스 안에서 호출. 매 CLI 실행 = 새 인터프리터 = lru_cache 초기화. |
| **server mode** | `just server` 로 띄운 uvicorn 프로세스. `POST /api/analysts/{id}/chat` endpoint 가 동일 `run_analyst()` 호출. 프로세스가 지속되므로 BGE-m3 1 회 로딩 + 재사용. |
| **자료 0 시드 dept** | `knowledge/canon/<dept>/*.md` (README 제외) 개수 = 0 인 dept. 현재 6/9 (`market_macro`, `stock_selection`, `stock-analysis`, `trading_journal`, `flow_analysis`, `news`). |
| **embedding_cache** | `data/db.sqlite` 의 `embedding_cache(model, query_hash, vector_bytes, created_at)` 테이블. (model, query) → vector 캐시. retrieve 시 cache hit → BGE-m3 forward skip. |

## 명세

### 묶음 (a) — 서버 모드 reuse

**의도**: CLI 가 매번 새 프로세스 띄우는 대신, 한 번 띄운 uvicorn 안의 `run_analyst()` 를 HTTP 로 호출. BGE-m3 1 회 로딩 + 후속 호출 재사용.

**변경**:
- `scripts/ask_analyst.py` — `from core.inference import run_analyst` → `httpx.post(f"{base_url}/api/analysts/{analyst_id}/chat", ...)` 로 교체. base_url = `WEVELSTOCK_SERVER_URL` env (default `http://127.0.0.1:8000`).
- `scripts/chat_analyst.py` — 동일 패턴.
- **서버 부재 시 명확한 에러** (silent fallback 금지 — `feedback_silent_env_fallback.md`): connect 실패 시 `[error] WevelStock 서버에 연결할 수 없습니다 ({base_url}). 다른 터미널에서 'just server' 실행 후 다시 시도하세요.` 출력 + exit 3.
- 응답 스키마 = 기존 `/api/analysts/{id}/chat` 의 `{answer, metadata}` 그대로. `_format_metadata` 재사용. JSONL 저장 로직도 그대로.

**대체안 검토 ❌**:
- `--in-process` 토글 — 사용자가 옵션을 외워야 함. 본질 ("CLI 도 서버 거치는 게 디폴트") 흐림.
- subprocess 풀 — Python 임포트 + BGE-m3 로딩 모두 cold 인 워커 풀은 구조 과잉. server 가 이미 이 역할.

### 묶음 (b) — RAG 자료 0 시드 자동 OFF

**의도**: 자료 0 시드 분석가 호출 시 `retrieve()` 진입조차 skip → BGE-m3 wiring 자체 발생 X.

**변경**:
- `core/knowledge/retrieve.py:_get_collection(dept)` — 기존의 `if not idx.exists() or not any(idx.iterdir())` 분기를 **확장**: `data/chroma/<dept>/` 에 chunk 가 0 개 (`collection.count() == 0`) 면도 `None` 반환. 빈 collection 이 만들어져 있어도 BGE-m3 wiring 으로 진입 X.
  - 단, `count()` 호출 자체가 collection 인스턴스 필요 → embedding_function wiring 전에 `chromadb.PersistentClient` 만 열고 `client.get_collection(name=dept)` (embedding_function 없이) 로 count 만 본 뒤, 0 이면 즉시 `None`.
- `core/knowledge/compose.py:build_pipeline_prompt` — `if not query_for_rag or not rag_dept: skip RAG` 분기 유지. 추가로 `canon_categories` 가 비어있고 dept canon md 0 이면 caller 가 query_for_rag 를 명시했어도 retrieve 건너뜀 (분석가 manifest 가 자료 0 시드를 명시한 케이스).
- `core/inference/run_analyst.py:158` 의 `rag_dept = spec.reads[0] if spec.reads else None` 은 그대로. 분석가 manifest 의 `reads:[market_macro]` 같이 dept 명이 박혀 있어도 (b) 의 retrieve 진입 가드가 BGE-m3 wiring 을 막는다.

**자동 분기 표** (변경 후):

| 분석가 | reads | canon md | chroma chunks | 결과 |
|---|---|---|---|---|
| principle_guardian | principles | 3 | >0 | RAG ON |
| trader | trading | 2 | **0** | **RAG OFF** (canon md 는 system 블록 주입 ON) |
| wealth_strategist | wealth_compounding | 2 | 787 | RAG ON |
| market_state_analyzer | market_macro | 0 | 0 | **RAG OFF** (BGE-m3 미로딩) |
| stock_picker | stock_selection | 0 | 0 | **RAG OFF** |
| stock_analyst | stock-analysis | 0 | 0 | **RAG OFF** |
| trading_journalist | trading_journal | 0 | 0 | **RAG OFF** |
| flow_analyzer | flow_analysis | 0 | 0 | **RAG OFF** |
| news_curator | news | 0 | 0 | **RAG OFF** |

→ 9 분석가 중 **7 호출** (Phase 4 실측 정정 — trader 의 trading dept reference 자료 미인덱싱) 에서 BGE-m3 로딩 발생 X.

**중요 구분**: `knowledge/canon/<dept>/*.md` 는 `load_shared_canon()` 으로 매 호출 system 블록 주입 (RAG 와 무관, 자료 0 시드 분기와도 무관). `data/chroma/<dept>/` chunks 는 `knowledge/reference/<dept>/` 자료가 `scripts/sync_knowledge.py` 로 인덱싱된 결과 (RAG 대상). trader 의 trading dept = canon md 2 (framework 매 호출 주입) + reference chunks 0 (RAG 자동 OFF, ✅ Phase 1 (b) 가드 작동).

### 묶음 (c) — SQLite embedding_cache

**의도**: 자료 있는 3 분석가 (RAG ON) 호출에서, 같은 query 재호출 시 BGE-m3 forward 를 skip.

**스키마** (`core/db/migrations/<NNNN>_embedding_cache.sql` 또는 startup 자동 생성):
```sql
CREATE TABLE IF NOT EXISTS embedding_cache (
  model TEXT NOT NULL,
  query_hash TEXT NOT NULL,
  vector BLOB NOT NULL,           -- float32 NDarray.tobytes()
  dim INTEGER NOT NULL,
  created_at INTEGER NOT NULL,    -- unix epoch
  PRIMARY KEY (model, query_hash)
);
```

**API** (`core/knowledge/embed_cache.py` 신설):
```python
def cached_query_embedding(model: str, query: str) -> list[float] | None: ...
def store_query_embedding(model: str, query: str, vector: list[float]) -> None: ...
```
- `query_hash = sha256(query.encode("utf-8")).hexdigest()` (model 별 분리, 중복 X)
- vector = `numpy.array(v, dtype=np.float32).tobytes()` 저장 / `np.frombuffer(blob, dtype=np.float32).tolist()` 복원

**retrieve() 연결**:
- `retrieve(dept, query, ...)` 가 cache hit → `collection.query(query_embeddings=[v], n_results=top_k)` 직접 전달 (Chroma 가 ef 호출 skip)
- miss → `ef([query])[0]` 명시 호출 + `store_query_embedding(...)` + 동일 vector 로 `query_embeddings=[v]` 전달
- 캐시 무한 누적 방지: 본 SPEC 에서는 retention X (테이블 크기 < 100MB 예상, 1000 query × 1024 dim × 4B = ~4MB). 90 일 retention cron 은 별도 백로그 (`project_retention_spec_backlog.md`).

**호출되지 않는 경우** (b) 의 자료 0 시드 가드로 retrieve 자체 skip 되는 6/9 분석가에서는 cache 도 무관.

### 묶음 외 — 기존 동작 보존

- `wealth_strategist`, `principle_guardian`, `trader` (자료 있는 3) 의 응답 스키마·verdict·점수 모두 불변. RAG ON 흐름 유지.
- mock provider (TESTING=1) 시 BGE-m3 로딩 자체 발생 X (기존 `_get_collection` 가드).
- chroma 인덱스가 들어오는 미래 dept (예: news 가 perplexity ingest 후) 는 자동으로 (b) 의 가드를 통과 → RAG ON.

## 검증

1. **회귀 — pytest 전체**:
   ```
   $env:TESTING='1'; $env:PYTHONIOENCODING='utf-8'; uv run pytest tests/ -q
   ```
   기대 = **331+ passed** (기존 331 + 신규 `test_embed_cache.py` ~5 + `test_knowledge_compose.py` 자료 0 시드 skip 분기 ~2).

2. **validate**:
   ```
   $env:PYTHONIOENCODING='utf-8'; uv run python scripts/validate.py
   ```
   기대 = **0 errors**.

3. **자료 0 시드 RAG OFF 가시 확인** — `market_state_analyzer` (자료 0 시드, RAG OFF 기대) 와 `principle_guardian` (자료 있음, RAG ON 기대) 호출 시 메타 비교:
   - market_state_analyzer 메타 `rag_chunks_returned == 0` + 로그 `chroma_skip_empty` 발화
   - principle_guardian 메타 `rag_chunks_returned > 0` + 로그 정상

4. **server mode reuse 가시 확인** — `just server` 후 동일 분석가에 두 번 호출:
   - 1 회차 latency = BGE-m3 cold 로딩 포함 (~30s)
   - 2 회차 latency = lru_cache hit (~3s, embedding cache 추가 hit 시 < 2s)

5. **production 호출 재시도**:
   - `just ask principle_guardian "정량 룰 위반 검증 시나리오 1"` → 메모리 충돌 없이 응답
   - `just ask market_state_analyzer "지금 시장 어디?"` → BGE-m3 미로딩 + 정상 응답
   - 양 트랙 권고 호출 (`both: 삼성전자`) → Track A + Track B 동시 응답

## 의도적으로 안 하는 것

- **임베딩 캐시 retention** — 90 일 또는 LRU eviction. 본 SPEC 범위 외. `project_retention_spec_backlog.md` 후속.
- **lazy lru_cache 워밍업** — 서버 startup 시 자료 있는 3 dept 의 BGE-m3 를 미리 로딩하는 hook. 운용 중 첫 호출이 ~30s cold latency 를 한 번 무는 것 허용 (재호출은 빠름).
- **`--in-process` 토글** — server mode 가 디폴트, 의도적으로 단일 경로.
- **operational_safeguards 권위 SPEC 정정** — 별도 작은 SPEC. 회장 핑퐁 [22] 권고에 따라 본 SPEC 첫 commit 으로 묶을 수 있음. 사용자 결정 후.

## 단계별 진입 + 실측 결과

| Phase | 묶음 | 추정 → 실측 | 검증 결과 |
|---|---|---|---|
| 1 | (b) RAG 자료 0 시드 자동 OFF | ~0.3 → 완료 | ✅ server 로그 `chroma_skip_empty dept=market_macro` 발화, `market_state_analyzer` 호출 시 `rag_chunks_returned=0` |
| 2 | (a) 서버 모드 reuse | ~0.5 → 완료 | ✅ httpx wrap, server 1 회 BGE-m3 로딩 + lru_cache 재사용, 2 회차 호출 ~3s |
| 3 | (c) SQLite embedding_cache | ~0.4 → **백로그 강등** | ⏸ Phase 4 측정 결과 latency 효과 < 0.4% (LLM 11s dominant). 다중 dept 동시 호출이 실제 bottleneck 으로 나타날 때 별도 SPEC. |
| 4 | production 호출 재시도 | ~0.3 → 완료 | ✅ `principle_guardian` (cycle 3 충돌 분석가) 호출 = verdict=violation + cited=[C2,C6,OS2] + 메모리 충돌 0, server BGE-m3 reconcile 후 free RAM 7.02 → 3.33 GB (안정) |

**(c) 백로그 근거** — Phase 4 검증에서:
- `principle_guardian` 첫 호출 12.4s / 재호출 11.9s = 0.5s 차이만. LLM 호출 ~11s 가 dominant.
- retrieve query 임베딩 forward pass = 추정 ~50ms. (c) skip 효과 = 50ms / 11900ms = **0.4%**.
- BGE-m3 모델 메모리 점유 (~2.5GB) 는 (a) 의 server reuse 가 이미 1 회 + 재사용. (c) 추가 메모리 절감 X.
- 같은 query 재호출이 운용에서 빈발할 때 (예: 알림 파이프라인 분당 재호출) bottleneck 되면 별도 SPEC 으로 진입.
