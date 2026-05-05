---
spec_id: INFRA-RAG-001
title: 5-Layer RAG — Chroma ingest/retrieve + 한국어 임베딩
team: shared
type: feature
status: draft
version: 1
owner: platform
generates:
  - core/knowledge/ingest.py
  - core/knowledge/retrieve.py
  - core/knowledge/embed.py
  - core/knowledge/compose.py
  - scripts/knowledge.py
  - justfile
modifies:
  - core/contracts/knowledge.py
  - pyproject.toml
  - .gitignore
depends_on:
  - (없음 — 학습부 폴더 구조 M1 완료 + R2 sync_knowledge 멱등 흐름이 전제)
contracts:
  - name: knowledge-chunk-v1
    version: "1.0"
---

# INFRA-RAG-001 — 5-Layer RAG (Chroma ingest/retrieve + 한국어 임베딩)

## 목적

5 학습부의 `knowledge/reference/<dept>/` 자료(주로 한국어 PDF 추출본)를 Chroma 벡터 DB로 인덱싱하고, 분석가 프롬프트 합성 시 dept 단위로 retrieve 한다. **자산복리부(`wealth_compounding`) 24 파일 540K tokens** 가 LLM 컨텍스트(Sonnet 200K) 한계를 270% 초과 — RAG 없이는 LLM 호출 자체가 불가능하므로 본질("뇌 이식 + 연속 판단")의 핵심 종속.

## 배경 / 문제

현 `core/knowledge/` 코드 골격은 반쯤 구현되어 있으나 다음 4가지 문제로 사용 불가:

1. **Legacy team 의존 9곳** — `get_team(team_id)` + `team.path/knowledge/sources` + `team.path/knowledge/vector-index`. 5-Layer 모델(학습부 = `dept`)과 정합 X.
2. **임베딩 함수가 wiring 되지 않음** — `core/knowledge/ingest.py:108-130` 에서 `collection.add(documents=...)` 호출 시 embedding_function 인자 없음. Chroma 가 기본 모델(`all-MiniLM-L6-v2`, **영문 전용**) 사용 → 한국어 임베딩 불가능. `core/knowledge/embed.py` 추상화는 존재하지만 어디서도 호출되지 않음. **이번 SPEC 의 가장 중요한 수정.**
3. **Frontmatter 메타 미사용** — `scripts/sync_knowledge.py` 가 작성한 frontmatter (`source`, `extracted_at`, `subfolder` 등) 를 `_iter_sources` (라인 66-83) 가 무시. python-frontmatter 가 의존성에 있는데도 안 씀.
4. **`build_pipeline_prompt` 의 RAG 호출 비현실** — `compose.py:224` 가 `retrieve("shared", ...)` 하드코딩. 실재하지 않는 dept 라 항상 빈 결과. 실 사용처(`pipelines/market_briefing_pre/stages/analyze.py:153`) 도 `query_for_rag` 미전달이라 회귀 위험은 낮음.

R3 끝나면 박종훈 자료 24 파일이 dept-scoped 인덱스에 들어가 `just knowledge-browse wealth_compounding "환율 1500원 시나리오"` 같은 쿼리로 단편 회수 가능. M3 분석가 분화 시점에 자산전략가가 query_for_rag 로 자기 학습부에 retrieve 호출.

## 핵심 정의

| 용어 | 의미 |
|---|---|
| **dept** | 5 학습부 ID. 폴더명·임베딩 collection 명·인덱스 디렉토리명 모두 일치. 현재 = `principles`, `mechanics`, `wealth_compounding`, `stock-analysis`, `news`. |
| **canon** | `knowledge/canon/<dept>/*.md` (사용자 손글 압축 framework, RAG 비대상, 매 호출 주입). 본 SPEC 변경 X. |
| **reference** | `knowledge/reference/<dept>/**/*.md` (PDF 추출본 + 사용자 원본 보존, RAG 인덱싱 대상). 본 SPEC 입력. |
| **인덱스** | `data/chroma/<dept>/` (per-dept Chroma PersistentClient). gitignore 대상. |
| **collection** | Chroma collection 이름 = dept. 1 dept = 1 collection. |

## 임베딩 모델 평가 (Stage A 결정)

| 모델 | dim | 한국어 성능 | 비용/의존성 | 외부 호출 | 적용 난이도 |
|---|---|---|---|---|---|
| **BAAI/bge-m3** (sentence-transformers, 로컬) | 1024 | ★★★★★ — MIRACL-ko 등 한국어 retrieval 벤치 강자, 100+ 언어 동시 학습 | ~2.3GB 첫 다운로드, CPU 가능(느림), 추론 0원, 의존 `sentence-transformers>=3.0` (이미 optional) | **0** — 완전 로컬 | Chroma `embedding_functions.SentenceTransformerEmbeddingFunction("BAAI/bge-m3")` 한 줄 |
| OpenAI text-embedding-3-small | 1536 | ★★★ — 다국어 지원 OK 이나 한국어 전용 벤치에서 BGE-m3 대비 열등. 540K tokens 1회 ≈ $0.01 | OPENAI_API_KEY 필요, 호출당 비용 | API 호출 매번 | 기존 `embed.py:_embed_openai` httpx wrapping 재사용 |
| intfloat/multilingual-e5-large (로컬) | 1024 | ★★★★ — 다국어 강자, 한국어 BGE-m3 대비 살짝 열등 | ~2.2GB | 0 | BGE-m3 와 동일 인터페이스 |

**결정 → BAAI/bge-m3 (default), OpenAI 는 fallback 옵션 유지.**

근거:
1. 박종훈 자료 = 100% 한국어. 한국어 retrieval 정확도가 1순위.
2. R3 의 정신("자료 자체는 외부 의존 없이 인덱싱") 과 부합 — 인덱스 재구축 시 API 키·네트워크 불필요.
3. 인덱싱은 1회성, 추론(retrieve)은 매 호출 — OpenAI 면 retrieve 마다 API 호출. 비용은 작지만 지연·실패 가능성 추가.
4. Chroma 가 `SentenceTransformerEmbeddingFunction` 빌트인 지원 → wiring 1줄.
5. CPU 도 동작(첫 인덱싱 ~5분 예상, retrieve ~0.5s/쿼리). 충분히 실용적.

OpenAI fallback 유지 이유: GPU 없이도 빠른 인덱싱이 필요하거나 `OPENAI_API_KEY` 만 있는 CI 환경 위해 `KnowledgeEmbedConfig.provider="openai"` 분기 보존.

## 명세

### 1. 인덱스 디렉토리 구조

```
data/chroma/                       # gitignore
├── wealth_compounding/            # Chroma PersistentClient(path=...)
│   ├── chroma.sqlite3
│   └── <uuid>/                    # collection 데이터
├── principles/                    # 향후 dept 추가 시 자동
└── ...
```

### 2. 함수 시그니처 (Before / After)

```python
# core/knowledge/ingest.py
# Before: async def ingest_team(team_id: str, ...) -> dict
async def ingest(dept: str, *, force: bool = False, chunk_size: int = 800, overlap: int = 100) -> dict

# core/knowledge/retrieve.py
# Before: async def retrieve(team_id: str, query: str, top_k: int = 3)
async def retrieve(dept: str, query: str, top_k: int = 3) -> list[RetrievalResult]

# core/knowledge/compose.py — build_pipeline_prompt
# Before: query_for_rag: str | None  (dept 하드코딩 "shared")
# After: query_for_rag: str | None, rag_dept: str | None  — 둘 다 있어야 retrieve 호출

# core/knowledge/compose.py — build_system_prompt (legacy)
# 그대로 유지 (호출처 무, 회귀 0)
```

### 3. Ingest 흐름

1. `path = Path("knowledge/reference") / dept` 존재 확인. 없으면 ValueError.
2. `index_dir = Path("data/chroma") / dept` mkdir.
3. Chroma `PersistentClient(path=str(index_dir))` + embedding_function 명시 (`KnowledgeEmbedConfig` 기반):
   - `local`: `SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-m3")`
   - `openai`: `OpenAIEmbeddingFunction(api_key=..., model_name="text-embedding-3-small")`
4. `collection = client.get_or_create_collection(name=dept, embedding_function=ef)`. **`force=True`** 일 때만 `delete_collection` 후 재생성. default 는 upsert.
5. `path.rglob("*.md")` 만 수집 (이번 SPEC 은 markdown 만; PDF/YouTube branch 는 sync_knowledge 가 이미 전처리). README.md 제외.
6. 각 파일에 대해:
   - `frontmatter.load(p)` → meta + body
   - body chunking (현 `_chunk_text` 재사용, char 800/100)
   - chunk id = `<rel_path>::<chunk_index>` (멱등 ID)
   - metadata = `{source_id, source_type, source_title, source_subfolder, extracted_at, chunk_index, dept}` + frontmatter 의 안전 키 화이트리스트
   - `collection.upsert(ids, documents, metadatas)` (멱등성)
7. 통계 반환: `{status, dept, sources, chunks, index_path, embedding_model}`

### 4. Retrieve 흐름

1. `idx = Path("data/chroma") / dept`. 없거나 비어있으면 `[]`.
2. `_get_client(dept)` — `lru_cache(maxsize=8)` 로 PersistentClient + collection 캐시 (매 호출 재생성 회피).
3. embedding_function 은 ingest 와 동일하게 명시 (Chroma 가 collection 메타에서 영구 저장하나 재명시 안전).
4. `collection.query(query_texts=[query], n_results=top_k)` → `RetrievalResult` 변환 (기존 로직 재사용).
5. `KnowledgeChunk.team_id` 필드는 contract 호환 위해 유지하되 dept 값을 담음. M3 후속 SPEC 에서 `dept_id` 로 rename 예정 (이번 R3 범위 X).

### 5. Embed 어댑터

`core/knowledge/embed.py` 를 **Chroma EmbeddingFunction 어댑터** 로 단일화:

```python
def get_embedding_function():
    cfg = get_config().knowledge.embedding
    if cfg.provider == "local":
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(model_name=cfg.model)
    if cfg.provider == "openai":
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        key = env("OPENAI_API_KEY_FOR_EMBEDDING") or env("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY required for openai embedding")
        return OpenAIEmbeddingFunction(api_key=key, model_name=cfg.model)
    raise ValueError(f"unknown embedding provider: {cfg.provider}")
```

기존 `embed_texts` 비동기 함수는 더 이상 호출되지 않으므로 삭제 (dead code).

### 6. Config 변경

`config/defaults.yaml` 의 `knowledge.embedding` (현 `provider: openai`, `model: text-embedding-3-small`) → **`provider: local`, `model: BAAI/bge-m3`** 로 변경. `KnowledgeEmbedConfig` schema 의 default 도 동일 갱신.

`runtime.yaml` 에서 사용자가 OpenAI 로 override 가능. `.env` 에서 `OPENAI_API_KEY_FOR_EMBEDDING` 또는 `OPENAI_API_KEY` 우선순위 그대로.

### 7. CLI / justfile

`scripts/knowledge.py`:
- 인자명 `team` → `dept`. `_status`/`_compile` 은 legacy `get_team` 의존 + canon 자동컴파일이라 5-Layer 와 정합 X — **삭제** (canon 은 손글 정제본, auto-compile 안 함).
- `ingest`/`browse` 만 유지. 새 시그니처 호출.

`justfile`:
- `knowledge-ingest team` → `knowledge-ingest dept`, `knowledge-browse team query` → `knowledge-browse dept query`
- `knowledge-compile`, `knowledge-status` 삭제 (대체: `just knowledge-sync <dept>` 가 동기화 + 디렉토리 상태 출력하면 충분)

### 8. 의존성 (`pyproject.toml`)

`sentence-transformers>=3.0` 을 **optional `local-embed`** → **required dependencies** 로 승격. 이유: BGE-m3 가 default 가 되었으므로 base install 에 포함되어야 함. 디스크 ~2.3GB 첫 다운로드 부담은 수용 (RAG 가 시스템 본질).

`chromadb>=0.4` 는 이미 required. `python-frontmatter>=1.1` 도 이미 required.

### 9. .gitignore

`data/chroma/` 추가. 인덱스는 코드/자료 변경 시 재생성 가능한 캐시.

## 비목표 (이번 SPEC 에서 안 하는 것)

- **PDF/YouTube 직접 ingest** — sync_knowledge 가 이미 markdown 으로 추출. ingest 는 markdown only 로 단순화.
- **Vol 2/3 OCR** — 별도 백로그 (`ocrmypdf` 도입 시점).
- **`KnowledgeChunk.team_id` → `dept_id` 필드 rename** — 회귀 리스크, M3 분석가 분화 SPEC 에서 묶어 처리.
- **분석가별 RAG dept 매핑 자동화** — M3 의 분석가 manifest 의 `reads:` 가 정식 매핑. R3 에서는 `wealth_compounding` 1개 동작 검증만.
- **재인덱싱 자동 트리거** — `sync_knowledge` 후 수동 `just knowledge-ingest`. cron 자동화는 후속.
- **Chroma collection 메타 마이그레이션** — 기존 인덱스 파괴 (없음, 처음 인덱싱).
- **다국어 임베딩 모델 평가 정량 측정** — 본 SPEC 은 정성 결정. 정량은 M3 분석가 출력 평가 시점.

## 검증 방법

1. **인덱싱 성공**: `just knowledge-ingest wealth_compounding` 종료 코드 0, `data/chroma/wealth_compounding/chroma.sqlite3` 생성, stdout 에 `{sources: 24, chunks: ~700, embedding_model: BAAI/bge-m3}` 류 반환
2. **멱등성**: 즉시 재실행 시 sources/chunks 동일, 시간 단축 (Chroma upsert 동작)
3. **검증 질의 3~5개**:
   - "환율 1500원 시나리오" → 박종훈 환율·통화 단편 회수
   - "FRB 양적긴축 사이클 위치" → 통화정책 단편
   - "한국 부동산 위기와 가계부채" → 부동산·가계 단편
   - "조선업 사이클" 또는 "반도체 사이클" → 산업 사이클 단편
   - top_k=5 결과의 source_title 이 박종훈 강의 파일 (`lectures/`, `ebooks/`) 에서 나옴
4. **회귀**: `TESTING=1 pytest` 60 passed 유지
5. **Type check**: `just lint` (mypy strict) 통과 (또는 기존 ignore 보존)

## 마이그레이션

- 기존 `team.path/knowledge/vector-index` 인덱스 파일은 어떤 dept 도 안 만들었으므로 마이그레이션 불필요 (`teams/` 트리는 이미 사용 안 함).
- legacy `build_system_prompt(team_id, ...)` 는 호출처 0 — deprecated 마크만 (M3 에서 삭제).

## 작업 순서

1. `pyproject.toml` 의존성 승격 + `uv sync`
2. `config/defaults.yaml` 의 `knowledge.embedding` 변경 + `core/config/schema.py` default 갱신
3. `core/knowledge/embed.py` rewrite → `get_embedding_function()`
4. `core/knowledge/ingest.py` rewrite → `ingest(dept, *, force=False)` + frontmatter + upsert + ef wiring
5. `core/knowledge/retrieve.py` rewrite → `retrieve(dept, ...)` + lru_cache + ef wiring
6. `core/knowledge/compose.py` 의 `build_pipeline_prompt` RAG 호출 → `rag_dept` 인자 받도록 + `build_system_prompt` 호출부 dept 명으로 단순 치환
7. `scripts/knowledge.py` 단순화 (`ingest`/`browse` 만)
8. `justfile` 인자명 + 명령 정리
9. `.gitignore` `data/chroma/` 추가
10. `just knowledge-ingest wealth_compounding` 실 인덱싱
11. `just knowledge-browse wealth_compounding "<query>"` 4~5 질의
12. `TESTING=1 pytest` 회귀

## 위험 / 알려진 제약

- **첫 BGE-m3 다운로드 ~2.3GB** — HuggingFace mirror 기본. 사용자 PC 디스크·대역폭 가정 OK.
- **CPU 인덱싱 시간** — 540K tokens, ~700 chunks, CPU 추정 ~5~10분. 일회성. GPU 있으면 ~30s.
- **`sentence-transformers` import 시 torch 같이 설치** — 디스크 추가 ~2GB. 수용.
- **embedding_function 변경 시 collection 재인덱싱 필요** — Chroma 가 임베딩 모델을 collection 메타에 묶음. 모델 바꾸면 `force=True` 로 재생성. 사용자에게 명시.
