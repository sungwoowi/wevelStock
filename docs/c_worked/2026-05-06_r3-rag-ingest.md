---
date: 2026-05-06
topic: R3 — INFRA-RAG-001 SPEC + 5-Layer RAG 리팩터 + 박종훈 자료 첫 인덱싱
status: completed
plan_file: C:\Users\HOME\.claude\plans\lucky-riding-tiger.md
---

# 2026-05-06 · R3 RAG SPEC + Chroma ingest + wealth_compounding 첫 인덱싱

## 배경

2026-05-04 R2 까지 박종훈 24 PDF (자산복리부) 추출 완료, 540K tokens — Sonnet 200K의 270%, RAG 없이 LLM 활용 불가임을 정량 확인. `core/knowledge/{ingest,retrieve,compose,embed}.py` 코드 골격은 반쯤 있었으나 4개의 잠복 결함:

1. **legacy `team` 의존 9곳** (`get_team(team_id) + team.path/knowledge/{sources,vector-index}`) — 5-Layer 모델 미정합
2. **임베딩 함수 미wiring** — `ingest.py:108` 가 `collection.add(documents=...)` 호출 시 `embedding_function=` 인자 없음 → Chroma 기본 모델 (`all-MiniLM-L6-v2`, **영문 전용**) fallback. `embed.py` 추상화는 어디서도 호출되지 않는 dead code. 한국어 RAG 가 사실상 동작하지 않는 상태였음
3. **frontmatter 메타 미사용** — sync_knowledge 가 만든 `source/extracted_at/subfolder` 메타가 ingest 에서 무시
4. **`build_pipeline_prompt` RAG 호출 비현실** — `compose.py:224` 가 `retrieve("shared", ...)` 하드코딩, 실재하지 않는 dept 라 항상 빈 결과

R3 끝나면 박종훈 자료가 자동으로 LLM 추론에 들어가 "뇌 이식 + 연속 판단" 본질의 핵심 한 축 동작 시작.

## 한 일

### Stage A — SPEC INFRA-RAG-001 작성
- `docs/specs/INFRA-RAG-001-knowledge-rag.md` (신규)
- frontmatter generates: ingest/retrieve/compose/embed/scripts.knowledge/justfile
- 한국어 임베딩 모델 비교표 (BGE-m3 vs OpenAI text-embedding-3-small vs multilingual-e5) → **BGE-m3 선택** (한국어 retrieval 강자, 외부 호출 0, Chroma 빌트인 지원)
- 5-Layer 흐름 명세: 입력 `knowledge/reference/<dept>/`, 인덱스 `data/chroma/<dept>/`, collection name = dept
- 비목표 명시 (PDF 직접 ingest, OCR, KnowledgeChunk 필드 rename, 자동 재인덱싱 등 — 후속 SPEC 으로)

### Stage B — `core/knowledge/` 5-Layer 리팩터

**`core/knowledge/embed.py`** (rewrite)
- `get_embedding_function()` — Chroma EmbeddingFunction 어댑터 (BGE-m3 로컬 / OpenAI 분기). 키·의존성 미설정 시 silent fallback 금지 (RuntimeError raise).
- 기존 비동기 `embed_texts()` 삭제 (dead code).

**`core/knowledge/ingest.py`** (rewrite)
- `ingest(dept: str, *, force: bool = False)` — 동기 함수.
- 입력 `knowledge/reference/<dept>/`, 출력 `data/chroma/<dept>/`.
- `python-frontmatter` 로 메타 파싱 → Chroma metadata 화이트리스트(`source`, `extracted_at`, `subfolder`, `title`, `lang`).
- `collection.upsert(ids=...)` 멱등 — 청크 ID = `<rel_path>::<chunk_index>` 안정.
- **임베딩 함수 명시 wiring** — `client.get_or_create_collection(name=dept, embedding_function=ef)`. 한국어 BGE-m3 가 실제로 사용됨.
- **연산 멱등성**: 파일 sha256(16자) 를 첫 청크 metadata 에 저장 → 재실행 시 비교 → 일치 시 skip + chunks=0.
- **legacy 인덱스 자동 backfill** — file_hash 가 없는 기존 인덱스를 만나면 metadata 만 update (임베딩 재계산 X).

**`core/knowledge/retrieve.py`** (rewrite)
- `retrieve(dept: str, query: str, top_k: int = 3)` — 비동기.
- `lru_cache(maxsize=8)` 로 PersistentClient + collection 핸들 dept 당 1회만 생성.
- 임베딩 함수 일치 보장 (ingest 와 동일 EF 명시 wiring).

**`core/knowledge/compose.py`** (편집)
- `build_pipeline_prompt` 에 `rag_dept: str | None` 인자 추가. `query_for_rag` AND `rag_dept` 둘 다 있을 때만 retrieve.
- legacy `build_system_prompt` 는 호출처 0이라 그대로 유지 (deprecated mark, M3 에서 제거 예정).

**`scripts/knowledge.py`** (단순화)
- `team` → `dept` 인자명 통일. `compile`/`status` 제거 (canon 자동컴파일은 5-Layer 와 정합 X). `ingest`/`browse` 만 유지.
- Windows cp949 콘솔 회피: 모듈 시작에서 stdout/stderr 를 `utf-8 + errors=replace` 로 reconfigure. 한국어/이모지 청크 출력 가능.

**`justfile`** (정리)
- `knowledge-ingest dept` (멱등 upsert), `knowledge-reingest dept` (force=True), `knowledge-browse dept query`. `knowledge-compile`/`knowledge-status` 삭제.

**`pyproject.toml`** + **`config/defaults.yaml`** + **`core/config/schema.py`**
- `sentence-transformers>=3.0` optional → required 승격 (BGE-m3 default).
- `knowledge.embedding.provider` `openai` → `local`, `model` → `BAAI/bge-m3`.

**`.gitignore`**
- `data/chroma/` 추가. legacy `teams/*/knowledge/vector-index/` 보존 (M3 에서 정리).

### Stage C — 첫 인덱싱 + 검증

**첫 인덱싱**: `just knowledge-ingest wealth_compounding`
- BGE-m3 ~4.3GB 첫 다운로드 (HF cache, 향후 재사용)
- 25 sources (lectures 18 + materials 6 + ebooks 1) → **787 chunks**
- CPU only, 약 55분 소요 (worker CPU 누적 ~22,484초 = 멀티코어 풀가동)
- 결과: `{status: ok, sources: 25, chunks: 787, embedding_model: BAAI/bge-m3}`

**검증 질의 4건 — 정성 평가 ★★★★★**
- "환율 1500원 시나리오와 한국 자본 유출" → top-5 모두 박종훈 강의, 2위가 "환율이 1,500원을 돌파하는 순간" 직접 매칭 (score 0.580)
- "FRB 양적긴축과 통화정책 사이클" → "파멸의 J커브와 공포의 톱니바퀴", "고물가가 뉴노멀이 된 시대" 등 통화정책 강의 정확
- "한국 가계부채와 부동산 위기" → "위기를 보는 눈", "금리는 왜 우리를 배신하는가", **"부채의 J커브, 세계는 지금 빚잔치 중"** 정확
- "복리 자산 증식과 장기 생존 전략" → "패권전쟁과 돈의 미래", "돈이 휴지가 되는 시대" 등 거시 자산 보존 강의

→ **한국어 RAG 정상 동작 확인**. BGE-m3 의 한국어 의미 매칭 강력.

**멱등성 검증**
- 첫 재실행 (legacy 인덱스 backfill): 22.1s, chunks=0, skipped_unchanged=25 (metadata 만 update)
- 두 번째 재실행 (모든 hash 일치): 17.7s, chunks=0, skipped_unchanged=25
- → **170배 단축** (3,300s → 17.7s). 17초 대부분은 BGE-m3 모델 로드 startup. 실제 인덱싱 작업 0초.

**회귀 검증**
- pytest 60 passed (2.83s) — 모든 변경 후에도 통과.

## 검증 결과

- ✅ SPEC 작성 (한국어 임베딩 BGE-m3 결정 근거 명시)
- ✅ legacy team 의존 9곳 모두 제거 (compose.py 의 legacy `build_system_prompt` 만 deprecated 보존)
- ✅ 임베딩 함수 wiring (Chroma 기본 영문 모델 fallback 버그 해결)
- ✅ frontmatter 메타 → Chroma metadata 화이트리스트 흐름
- ✅ `data/chroma/wealth_compounding/` 17MB sqlite + HNSW 인덱스 생성
- ✅ 검증 질의 4건 모두 박종훈 강의 정확 회수
- ✅ 결과 멱등성 + 연산 멱등성 모두 작동 (재실행 17.7s, 170배 단축)
- ✅ pytest 60 passed
- ⚠️ Windows 콘솔 cp949 인코딩 이슈 — `scripts/knowledge.py` 가 utf-8 reconfigure. 다른 print 경유 명령은 영향 X.

## 의도적으로 안 한 것

- **GitHub commit/push** — 사용자 검토 후 결정 (`.claude/settings.json` modified, `rag_docs/` untracked 도 함께)
- **legacy `core/registry.py`, `teams/*` dead code 청산** — 회귀 리스크, 별도 세션
- **`KnowledgeChunk.team_id` → `dept_id` 필드 rename** — 회귀 리스크, M3 분석가 분화 SPEC 에서 묶기
- **`build_system_prompt` (legacy) 삭제** — 호출처 0 이지만 docs 에서 참조. M3 또는 후속 cleanup
- **분석가 manifest 의 `reads:` 와 RAG dept 자동 매핑** — M3 에서 정식 정의
- **Vol 2/3 OCR** — `ocrmypdf` + tesseract 도입, 별도 백로그
- **영문 글자 사이 공백 정규화** — RAG 검증 결과 BGE-m3 가 공백 무시하고 정확 매칭. 후순위
- **`config/knowledge_sources.yaml` ingest 통합** — 현재 ingest 가 hard-coded `knowledge/reference/<dept>/` 사용. yaml 의 source 매핑은 sync 전용. 단순성 유지

## 다음에 이어서 할 작업 (우선순위)

1. **R4 — wealth_compounding framework manifesto** (PC/모바일, 1~1.5h 인터뷰)
   - `canon/wealth_compounding/01-framework-manifesto.md` (~2K tokens) 사용자 손글로 박종훈 framework + 사용자 시각 1~2 페이지 압축. 옵션으로 `02-survival-imperatives.md`.
   - **이제 RAG 가 동작하므로** framework 작성 시 검증 질의로 박종훈 자료 단편 회수해 시각 정합 확인 가능.
   - 코드 변경 0, markdown Q&A.

2. **M3 — 분석가 5명 페르소나 분화 + 매매일지 SPEC** (PC, 2~3h)
   - `analyst.md` 1 → 5 persona.md split (`agents/analysts/<id>/persona.md`).
   - 자산전략가의 manifest `reads: [wealth_compounding]` 첫 가동 — R3 의 `rag_dept` 인자가 여기서 의미 가짐.
   - `BRIEFING-JOURNAL-001` 매매일지 SPEC 골격.

3. **다른 학습부 자료 채우기** (실전부 / 종목분석부 / 뉴스부 — M2 후속)
   - 자료 수집 → sync_knowledge → ingest 흐름이 plugin 으로 동작하므로 학습부 추가는 `config/knowledge_sources.yaml` 한 줄 추가.

## 맥락 재진입 힌트

- **연산 멱등성의 의미**: 사용자가 박종훈 강의 1편 추가 → `just knowledge-sync wealth_compounding` 후 `just knowledge-ingest wealth_compounding` 재실행 시 **새 1 파일만 임베딩** (~1~2분), 기존 24 파일은 hash 일치로 즉시 skip. 50분씩 다시 안 돌아감.
- **검색 명령**: `just knowledge-browse wealth_compounding "<한국어 질의>"` — 디버깅 / framework 작성 보조용.
- **인덱스 위치**: `data/chroma/wealth_compounding/` (gitignore). 영구 캐시. 임베딩 모델 변경 시에만 `just knowledge-reingest <dept>` 로 재생성.
- **HF cache**: `~/.cache/huggingface/hub/models--BAAI--bge-m3/` ~4.3GB. 다른 worktree 도 공유.
- **Windows 콘솔 한국어/이모지 출력**: `scripts/knowledge.py` 가 utf-8 reconfigure 처리. 다른 곳에서 print 시 같은 패턴 적용 가능 (`sys.stdout.reconfigure(encoding='utf-8', errors='replace')`).
- **5-Layer plugin 패턴**: 새 학습부 추가 = (1) `knowledge/canon/<dept>/` 폴더 + (2) `config/knowledge_sources.yaml` 매핑 + (3) `just knowledge-sync` + `just knowledge-ingest`. 코드 변경 0.

## 커밋 상태

**아직 커밋 안 함** — 사용자가 깨어나서 검토 후 결정.

대상 변경 (모두 staging 안 됨):
- `docs/specs/INFRA-RAG-001-knowledge-rag.md` (신규)
- `core/knowledge/embed.py` (rewrite)
- `core/knowledge/ingest.py` (rewrite + idempotency)
- `core/knowledge/retrieve.py` (rewrite)
- `core/knowledge/compose.py` (rag_dept 인자)
- `scripts/knowledge.py` (단순화 + utf-8 reconfigure)
- `justfile` (명령 정리)
- `pyproject.toml` (sentence-transformers required)
- `core/config/schema.py` (KnowledgeEmbedConfig default)
- `config/defaults.yaml` (BGE-m3 default)
- `.gitignore` (data/chroma/)
- `docs/c_worked/2026-05-06_r3-rag-ingest.md` (이 파일)
- `docs/RESUME.md` (다음 세션용 갱신)

**기존에 modified 였던 것 (R3 무관, 보존):**
- `.claude/settings.json` modified
- `rag_docs/` untracked
