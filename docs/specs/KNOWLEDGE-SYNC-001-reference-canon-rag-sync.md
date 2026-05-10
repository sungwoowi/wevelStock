---
spec_id: KNOWLEDGE-SYNC-001
title: knowledge 동기화 — reference 인덱싱 + canon 승격 PROPOSAL + release note (델타·카테고리 단위)
team: shared
type: feature
status: draft
version: 1
owner: knowledge_layer
generates:
  - core/knowledge/sync.py
  - core/knowledge/watcher.py
  - core/knowledge/proposal.py
  - core/knowledge/release_note.py
  - core/knowledge/category.py
  - core/knowledge/adapters/__init__.py
  - core/knowledge/adapters/markdown.py
  - core/knowledge/adapters/text.py
  - core/knowledge/adapters/pdf.py
  - core/knowledge/adapters/xlsx.py
  - core/knowledge/adapters/png.py
  - core/contracts/knowledge_sync.py
  - scripts/knowledge_sync.py
  - .claude/skills/knowledge-sync.md
  - .claude/skills/knowledge-review.md
modifies:
  - core/knowledge/ingest.py        # dept → (dept, category) 2-tier 확장 + 델타 모드
  - core/knowledge/retrieve.py      # 카테고리 필터 옵션
  - core/knowledge/compose.py       # canon_categories 기반 선택 주입
  - core/db/schema.py               # knowledge_index_runs 테이블 추가
  - knowledge/canon/**              # 폴더 구조 마이그레이션 (카테고리 단계 추가, 별도 사전 PR)
  - knowledge/reference/**          # 폴더 구조 마이그레이션 (동일)
  - justfile                        # knowledge-sync / knowledge-rebuild 명령
  - pyproject.toml                  # watchdog, openpyxl, anthropic vision 의존성
depends_on:
  - INFRA-RAG-001 (Chroma 인덱싱 엔진 — ingest/retrieve/embed/compose 기반)
  - M3 분석가 분화 SPEC (Phase 3~5 만 — PROPOSAL/release note 의 분석가 영향 추론 정확도)
contracts:
  - name: knowledge-proposal-v1
    version: "1.0"
  - name: knowledge-release-note-v1
    version: "1.0"
  - name: knowledge-sync-run-v1
    version: "1.0"
---

# KNOWLEDGE-SYNC-001 — knowledge 동기화 (reference 인덱싱 + canon 승격 PROPOSAL + release note)

## 목적

지식부 자료(`knowledge/reference/**`) 가 누적·델타 갱신될 때 다음 셋을 자동 처리한다:

1. **(A) reference → RAG 인덱싱** — 변경된 파일만 델타 인덱싱. 분석가 RAG 검색이 항상 최신.
2. **(B) reference → canon 승격 PROPOSAL** — LLM 이 "어느 자료의 어느 부분이 canon 에 한 줄로 들어가면 좋을지" 제안서 작성. 사용자가 `/knowledge-review` 스킬로 검토·승인. 승인 시 canon md 자동 patch + git commit.
3. **(C) release note 자동 생성** — 1 sync = 1 release note md. "변경 요약 + 영향받을 분석가 + 인용 시나리오 + canon 보강·충돌 관계" 까지 LLM 이 추론.

본 SPEC 은 또한 **canon·reference 의 LLM 인식 단위를 지식부에서 카테고리로 한 단계 내려** 토큰 예산·prompt cache 효율·release note 그래뉼래러티를 동시에 개선한다.

## 배경 / 문제

- INFRA-RAG-001 이 dept 단위 인덱싱 엔진을 정의했으나 **재인덱싱 자동 트리거가 비목표** — 현재 사용자가 reference 에 파일을 push 해도 인덱스에 반영되지 않음.
- canon 갱신 절차가 비명시적 — 사용자가 직접 md 편집해야 하나, "어떤 자료를 canon 으로 올릴지" 의 판단·기록이 사라짐.
- `knowledge/reference/stock-analysis/` 처럼 **카테고리(fundamental_analysis, technical_analysis, valuation 등) 가 명확히 분기되는 지식부** 가 지식부 단위 통째 주입으로 묶이면, 토큰 예산·캐시 효율·인용 출처 명시성이 모두 손해.
- 박종훈 강의 같은 자료는 누적 10+ 회차 예정 — **델타 인덱싱이 비용·속도 면에서 압도적 유리**, 단 일관성 회복용 전체 재인덱싱 명령(`/knowledge-rebuild`) 도 필요.

## 핵심 정의

| 용어 | 의미 |
|---|---|
| **dept** | 9 지식부 ID (`principles`, `trading`, `market_macro`, `stock_selection`, `stock-analysis`, `wealth_compounding`, `trading_journal`, `flow_analysis`, `news`). 본 SPEC 에서 `news` 는 제외 (별도 SPEC). `market_macro` / `stock_selection` / `trading_journal` / `flow_analysis` 는 자료 0 시드 — Phase 0 에서 빈 카테고리 폴더만 신설. |
| **reference 카테고리** | 사람의 분류 단위. 학습 순서·주제·자료 출처 기준. 사용자가 폴더 만들고 자료 push. `_inbox/` 폴더는 분류 미정 자료 임시 위치. |
| **canon 카테고리** | LLM(AI) 친화 분류 단위. self-contained 추론 단위 / 토큰 예산 균형 / frame 차별성 / 카테고리 직교성 4 기준. **reference 카테고리와 1:1 강제 X** — 시드로 동일 이름 시작하나 PROPOSAL 의 라우팅 분석이 다른 canon 카테고리 추천 가능. |
| **category** | reference / canon 측 통칭. dept 하위의 폴더 1단계. 카테고리당 `_category.yaml` 메타 (canon 측 필수). 예: `stock-analysis/fundamental_analysis`. |
| **canon** | `knowledge/canon/<dept>/<category>/*.md` — 분석가 호출 시 system prompt 에 통째 주입. SoT = repo md. 본 SPEC 변경 대상. |
| **reference** | `knowledge/reference/<dept>/<category>/**` — RAG 검색 대상. 사용자가 직접 push. |
| **sync run** | watchdog 또는 명령으로 트리거되는 1회 동기화 단위. 1 sync = 1 PROPOSAL md + 1 release note md. |
| **PROPOSAL** | `knowledge/proposals/<dept>/<sync_id>.md` — 검토 전 자료. 상태: pending / partially_approved / approved / rejected. |
| **release note** | `knowledge/release_notes/<dept>/<sync_id>.md` — 변경 누적 timeline. M2 web UI 가 이 폴더를 read. |
| **인덱스** | `data/chroma/<dept>/` (per-dept Chroma collection — INFRA-RAG-001 그대로). 카테고리는 chunk metadata 의 `category` 필드로 표현 (collection 분리 X). |
| **sync_id** | `YYYY-MM-DD-HHMM` 형식 (분 단위 충분, 한 분 내 동시 트리거 시 watchdog 큐가 묶음). |

## 비목표 (이번 SPEC 에서 안 하는 것)

- **web UI** (release note 페이지, PROPOSAL 검토·LLM 대화·승인 페이지) — M2 별도 SPEC.
- **텔레그램 inline button 승인** — 후속 SPEC 또는 폐기.
- **뉴스부 동기화** — rolling canon + retention 패턴이 본질적으로 달라 별도 SPEC.
- **canon 승격 완전 자동화** — 항상 사람 승인 (`/knowledge-review`) 거침. PROPOSAL 의 자동 적용 분기 없음.
- **신규 카테고리 자동 신설** — reference·canon 양쪽 모두 사용자 명시 승인 시에만 신설. LLM 의 라우팅 분석은 *추천* 까지만.
- **카테고리 동적 선택 (질문 맥락 기반 LLM 라우팅)** — M1 은 정적 (persona.md `canon_categories: [...]`). 동적은 후속.
- **OneDrive 등 외부 sync 자동 fetch** — 사용자가 reference 폴더에 직접 둠 (현재 워크플로 유지).
- **DB 화** — proposal/release_note 는 repo md. DB 는 RAG 임베딩(Chroma) + `knowledge_index_runs` 운영 로그만.
- **embedding 모델 변경 시 자동 재인덱싱** — 모델 변경은 `/knowledge-rebuild` 수동 트리거만 (드문 작업).

## 흐름

### A. reference 변경 → 델타 인덱싱

```
[trigger]
  ├─ watchdog: knowledge/reference/** 변경 감지 (분 단위 debounce)
  └─ /knowledge-sync 수동 명령
       │
       ▼
[1. discover delta]
   git status + 마지막 sync 의 file hash 비교 → added/modified/deleted 파일 목록
       │
       ▼
[2. extract per file]
   적합한 어댑터 호출 (md/txt/pdf/xlsx/png)
   → frontmatter + body text + extraction_meta
       │
       ▼
[3. chunk + embed + upsert (Chroma)]
   chunk_id = "<dept>/<category>/<rel_path>::<chunk_index>" (멱등)
   metadata = {dept, category, source_id, source_title, chunk_index, ...}
   삭제된 파일: collection.delete(where={"source_id": ...}) — hard
       │
       ▼
[4. write run log → SQLite knowledge_index_runs]
   {sync_id, started_at, ended_at, dept, files_added, files_modified, files_deleted, chunks_upserted, chunks_deleted, status}
       │
       ▼
[5. trigger LLM analysis → PROPOSAL md + release note md 작성]
```

### B. PROPOSAL 생성 → 승인 → canon patch

```
[5. LLM analysis call (Anthropic Sonnet)]
   input = (delta 파일들 + 해당 dept 의 현 canon 전문 + persona.md 의 canon_categories)
   output = PROPOSAL md frontmatter + body
       │
       ▼
[6. write knowledge/proposals/<dept>/<sync_id>.md]
   status: pending
       │
       ▼
[7. write knowledge/release_notes/<dept>/<sync_id>.md]
   "변경 요약 + 영향받을 분석가 + 인용 시나리오 + canon 보강·충돌 관계"
       │
       ▼
[user invokes /knowledge-review]
       │
       ▼
[8. 스킬이 pending PROPOSAL 들 brief]
   사용자가 한 후보씩 approve / reject / refine (LLM 대화로 본문 정제)
       │
       ▼
[9. approved 후보들 한 번에 canon patch]
   각 후보의 target_path (knowledge/canon/<dept>/<category>/<file>.md) 에 patch 적용
   파일 없으면 신규 생성
       │
       ▼
[10. git commit]
   author = sungwoowi <wsw628@naver.com> (사용자 author 통일)
   message = "knowledge: promote <N> from proposal <sync_id> [auto:knowledge-sync]\n\n  - <dept>/<category>: <change summary>\n  ..."
       │
       ▼
[11. PROPOSAL md 의 frontmatter status 갱신 + archive/ 이동]
   approved 또는 partially_approved (일부 거절 시)
   knowledge/proposals/<dept>/archive/<sync_id>.md
```

### C. canon md 직접 수정 (사람이 손으로)

```
[user edits knowledge/canon/<dept>/<category>/<file>.md 직접]
       │
       ▼
[watchdog: knowledge/canon/** 변경 감지]
       │
       ▼
[prompt cache key 무효화 (해당 dept/category 만)]
   release note 자동 생성 X (사람이 git commit message 에 의도 작성)
```

## 폴더 구조 (마이그레이션 영향)

**현재 (2-tier)**:
```
knowledge/canon/<dept>/*.md
knowledge/reference/<dept>/[<subfolder>/]*.md
```

**변경 후 (3-tier)**:
```
knowledge/canon/<dept>/<category>/_category.yaml
knowledge/canon/<dept>/<category>/*.md
knowledge/reference/<dept>/<category>/**         # category 폴더 안엔 자유 구조
```

**`_category.yaml` 메타** (canon 측에만 둠 — reference 는 폴더 이름이 카테고리 ID):

```yaml
category_id: fundamental_analysis
title: 기본적 분석
description: 재무제표·가치평가·DCF·PER/PBR 등 기업 가치 평가 기법
target_analysts:
  - stock_analyst
when_to_inject: always   # always | on_demand
related_categories:
  - stock-analysis/valuation
```

**마이그레이션은 본 SPEC 의 prerequisite 별도 PR 로 처리**. 현재 1-depth md 들을 카테고리 폴더로 git mv. 분석가 persona.md (M3) 의 `canon_categories: [...]` 와 동시에 도입.

## canon 카테고리 AI 친화 4 기준

PROPOSAL 의 canon 라우팅 추천은 다음 4 기준을 LLM 이 자체 검증:

1. **self-contained 추론**: 그 카테고리만 system prompt 에 들어가도 독립 결론이 나오는가
2. **토큰 예산 균형**: 한 카테고리가 다른 것보다 5x 이상 크면 분리 추천
3. **frame 차별성**: 같은 종목·시장에 *다른 frame 의 결론* 을 내는가 (e.g. fractal_wave vs log_chart)
4. **카테고리 직교성**: 인용 시 출처를 "X 카테고리 관점에서…" 라 자연스럽게 부를 수 있고 다른 카테고리와 overlap 최소

새 자료가 4 기준 모두 충족하나 기존 카테고리에 흡수되지 않으면 **신규 canon 카테고리 신설 추천**. 사용자 승인 필수 (자동 신설 X).

## `_inbox/` 폴더 규약

분류 미정 자료의 임시 위치. 두 가지 용도:

- `knowledge/reference/<dept>/_inbox/<file>` — 사용자가 카테고리 결정 못한 reference 자료
- watchdog 가 감지 시 PROPOSAL 의 routing 섹션이 **강제 모드** 로 작동 (1차 카테고리 추천 + 신설 vs 흡수 분석)
- `/knowledge-review` 승인 시 자동으로 결정된 카테고리 폴더로 `git mv`

`_inbox/` 자체는 RAG 인덱싱 *대상*. 단 chunk metadata 의 `category` 필드는 `_inbox` 로 표시 — 분석가가 의도치 않게 인용하지 않도록 retrieve 에서 default exclude.

## PROPOSAL md 본문 스펙 (contract: knowledge-proposal-v1)

```markdown
---
contract: knowledge-proposal-v1
sync_id: 2026-05-10-1430
dept: stock-analysis
status: pending           # pending | partially_approved | approved | rejected
created_at: 2026-05-10T14:30:00+09:00
files_changed:
  - path: knowledge/reference/stock-analysis/_inbox/신고가매매기법.md
    change: added
    chunks: 4
  - path: knowledge/reference/stock-analysis/fundamental_analysis/03-DCF.md
    change: added
    chunks: 8
  - path: knowledge/reference/stock-analysis/technical_analysis/02-거래량.md
    change: modified
    chunks_delta: +2
  - path: knowledge/reference/stock-analysis/valuation/old.md
    change: deleted
    chunks: -5
---

# Sync 2026-05-10-1430 — stock-analysis

## 0. Category routing analysis (LLM 추천)

### 0-1. reference 라우팅 (사람 친화 — 사용자 결정)

| 자료 | 현 위치 | 추천 reference 카테고리 | 근거 | decision |
|---|---|---|---|---|
| 신고가매매기법.md | `_inbox/` | **`breakout_strategy` 신설** 또는 `technical_basics` 흡수 | 신고가 돌파 frame 은 자족적, 향후 누적 가능성 시 신설 유리. 분량 1 파일이라 흡수도 OK | pending |

### 0-2. canon 라우팅 (AI 친화 — LLM 분석)

자료가 canon 승격 후보면 추가로 다음 분석:

| 후보 | 추천 canon 카테고리 | 4 기준 검증 | decision |
|---|---|---|---|
| DCF 핵심 한 줄 | `fundamental_analysis` 흡수 | self-contained ✅ / 토큰 균형 ✅ / frame 차별성 (DCF 가 PER/PBR 과 다른 frame) ✅ / 직교성 ✅ → 흡수 | pending |
| 신고가 돌파 패턴 | **`breakout_strategy` 신설** 추천 | self-contained ✅ / frame 차별성 (모멘텀 돌파 ≠ 추세 분석) ✅ / 직교성 ✅ / 단 토큰 분량 작음 (1 파일) → **자료 누적 후 신설** 권장 | pending |

> reference 카테고리와 canon 카테고리는 *독립적*. 같은 자료가 reference `_inbox/` 에 있다가 canon 으로 갈 때 다른 카테고리명으로 편입될 수 있음.

## 1. RAG 인덱싱 결과 (자동 반영됨, 검토만)

| 파일 | 변경 | 청크 |
|---|---|---|
| .../fundamental_analysis/03-DCF.md | added | +8 |
| .../technical_analysis/02-거래량.md | modified | +2 |
| .../valuation/old.md | deleted | -5 |

총 청크 변동: +5 (Chroma collection: stock-analysis)

## 2. canon 승격 후보 (승인 필요)

### 후보 #1 — fundamental_analysis 카테고리에 DCF 핵심 추가

- **출처**: `reference/stock-analysis/fundamental_analysis/03-DCF.md`
- **target**: `canon/stock-analysis/fundamental_analysis/02-가치평가-DCF.md` (신규 생성)
- **제안 patch**:
  ```diff
  + ## DCF 핵심 한 줄
  + 미래현금흐름 할인율 = WACC 기준, 성장률은 보수적 (장기 GDP 성장률 + α 이내).
  ```
- **영향받을 분석가**: stock_analyst (자산전략가도 가치평가 보강 가능)
- **인용 시나리오**: 적정주가 산정 / 장기 보유 판단 / 가치투자 근거
- **기존 canon 과 관계**: `valuation/01-PER-PBR.md` 와 보강 (상호 참조). 충돌 없음.
- **decision**: pending      # pending | approved | rejected
- **refined_patch**: null    # /knowledge-review 에서 LLM 대화로 다듬은 결과

### 후보 #2 — ...

## 3. 검토 가이드

- 각 후보의 `decision:` 을 `approved` 또는 `rejected` 로 수정 후 저장
- LLM 대화로 patch 본문을 다듬으려면 `refined_patch:` 에 작성하면 그게 우선 적용
- 모두 처리 후 `/knowledge-review` 가 frontmatter 의 `status:` 를 자동 갱신
```

## release note md 본문 스펙 (contract: knowledge-release-note-v1)

```markdown
---
contract: knowledge-release-note-v1
sync_id: 2026-05-10-1430
dept: stock-analysis
created_at: 2026-05-10T14:30:00+09:00
proposal_path: knowledge/proposals/stock-analysis/2026-05-10-1430.md
canon_commit_sha: null    # /knowledge-review 후 채워짐
---

# stock-analysis · 2026-05-10 14:30

## 한줄 요약
DCF 가치평가 자료 추가 + 거래량 분석 보강 + valuation/old.md 폐기.

## 변경 핵심
- **신규**: DCF 미래현금흐름 할인 기법 (WACC, 보수적 성장률)
- **보강**: 거래량 다이버전스 패턴 2건 추가
- **폐기**: 구식 EBITDA 배수법 페이지 제거

## 영향받을 분석가의 판단 영역
- **stock_analyst**: 가치평가 질문에서 DCF 인용 가능 → "PER만 보는 것" 한계 보완
- **자산전략가** (M3 이후): 장기 보유 종목 선정 시 DCF 결과 참고 가능

## 인용 예상 시나리오
- "이 종목 적정주가는?" → DCF 단편 + PER/PBR 단편 결합
- "성장주 거품 여부는?" → DCF 의 성장률 가정 보수성 + 거래량 다이버전스
- "왜 이 종목을 장기 보유?" → DCF 보강된 가치투자 근거

## canon 승격 결과
(승인 후 채워짐)
- promoted: 1/2  (#1 approved, #2 rejected)
- canon_commit: abc123
```

## 자료 형식 어댑터

`core/knowledge/adapters/` 에 형식별 모듈. 공통 인터페이스:

```python
class Adapter(Protocol):
    extensions: tuple[str, ...]      # (".md",) / (".pdf",) / ...
    def extract(self, path: Path) -> ExtractedDocument: ...

@dataclass
class ExtractedDocument:
    body_text: str
    frontmatter_meta: dict[str, Any]
    extraction_meta: dict[str, Any]  # 어댑터별 (페이지수, OCR 신뢰도 등)
```

| 형식 | 어댑터 | 핵심 의존 |
|---|---|---|
| md | markdown | python-frontmatter (이미 required) |
| txt | text | stdlib |
| pdf | pdf | pdfplumber (1차) — INFRA-RAG-001 의 sync_knowledge 와 정합 |
| xlsx | xlsx | openpyxl (신규 의존) — 시트별 텍스트 추출 |
| png | png | Anthropic vision API (1차) — 비용·품질 우선. tesseract 옵션은 후속 |

png 의 vision 호출은 `core/llm/` 의 캐시·쿼터 정책을 그대로 사용. 한 번 추출하면 결과를 `data/chroma/<dept>/_extraction_cache/` 에 저장해 재추출 회피.

## 트리거

### watchdog (`core/knowledge/watcher.py`)

- 감시 경로: `knowledge/reference/**`, `knowledge/canon/**` (cache 무효화 용)
- debounce: 60s (한 번에 여러 파일 push 시 묶음)
- server (FastAPI + APScheduler 단일 프로세스) lifecycle 에 등록
- 절전모드 복귀 후 fsevents 누락 가능성 → server 재기동 시 `git status` 기준 reconcile 1회

### 수동 명령

- `just knowledge-sync` — 전체 dept 동기화 (델타)
- `just knowledge-sync <dept>` — 특정 dept 만
- `just knowledge-rebuild <dept>` — 인덱스 전체 재구축 (`force=True`)
- `just knowledge-status` — 마지막 sync run 요약 (`knowledge_index_runs` 최신 row)

## Claude 스킬 2개 (`.claude/skills/`)

### `/knowledge-sync`

수동 sync 실행 (watchdog 와 동일 로직). 인자: `[<dept>]` (생략 시 전체).
- 출력: 변경 파일 요약, PROPOSAL 경로, release note 경로
- LLM 호출 1회 (PROPOSAL + release note 본문 생성)
- **라우팅 의도 반영**: PROPOSAL 의 "0. Category routing analysis" 섹션을 항상 작성. `_inbox/` 자료가 있으면 강제 모드 (모든 자료에 reference 카테고리 추천 + canon 승격 시 별 카테고리 추천). reference vs canon 카테고리 독립적으로 분석.

### `/knowledge-review`

pending PROPOSAL 들 brief + 사용자 응답으로 frontmatter 정제 + canon patch + git commit.
- 출력: 각 후보 표시, 승인/거절/정제 받기, 최종 git commit sha
- **라우팅 의도 반영**:
  - 0-1 (reference 라우팅) 승인 시: 자료를 `_inbox/` → 결정된 카테고리 폴더로 자동 `git mv`. 신규 카테고리면 폴더 + `_category.yaml` 자동 생성.
  - 0-2 (canon 라우팅) 승인 시: canon 측 카테고리에 patch 적용. 신규 canon 카테고리는 사용자 명시 승인 시에만 신설.
  - reference/canon 카테고리가 다른 이름으로 결정되면 둘 다 반영 (예: reference 는 `breakout_strategy` 신설, canon 은 `technical_basics` 흡수 — 독립).
- 신규 카테고리 신설 시 `_category.yaml` 의 `target_analysts` 는 빈 값으로 초기화 (M3 후 사용자가 정정).

## DB 스키마 변경 (`core/db/schema.py`)

```sql
CREATE TABLE IF NOT EXISTS knowledge_index_runs (
    sync_id TEXT PRIMARY KEY,           -- "YYYY-MM-DD-HHMM"
    dept TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL,                -- running | success | partial | failed
    files_added INTEGER DEFAULT 0,
    files_modified INTEGER DEFAULT 0,
    files_deleted INTEGER DEFAULT 0,
    chunks_upserted INTEGER DEFAULT 0,
    chunks_deleted INTEGER DEFAULT 0,
    proposal_path TEXT,
    release_note_path TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_kir_dept_started ON knowledge_index_runs(dept, started_at DESC);
```

`team_outputs` / `team_memory` / `llm_call_cache` 등 기존 테이블 변경 없음.

## git commit 정책

- author: `sungwoowi <wsw628@naver.com>` (현재 git config 그대로)
- message 패턴:
  - canon patch: `knowledge: promote <N> from proposal <sync_id> [auto:knowledge-sync]`
  - canon 본인 손편집: 사용자 자유 (자동 분기 없음)
- `[auto:knowledge-sync]` 마커로 grep 분리: `git log --grep='\[auto:knowledge-sync\]'`
- pre-commit hook: 본 SPEC 의 자동 commit 도 동일하게 통과해야 함. 실패 시 PROPOSAL frontmatter 의 `status` 를 `pending` 으로 되돌리고 사용자에게 alert.

## 분석가·파이프라인 영향 (M3 와 인터페이스)

- **분석가 persona.md** 에 `canon_categories: [<dept>/<category>, ...]` 추가 (M3 분석가 분화 SPEC 에서 정식 도입). 본 SPEC 은 `compose.py` 가 이 필드를 읽도록 확장만.
- **`build_pipeline_prompt`** 의 canon 주입 로직: 지식부 통째 → 카테고리 필터링.
- **RAG retrieve** 는 카테고리 필터 옵션 추가 (`retrieve(dept, query, *, categories=None, top_k=3)`). 미지정 시 dept 전체 (현 동작과 동일).

## 검증 방법

1. **마이그레이션 후 인덱싱**: `just knowledge-rebuild stock-analysis` → Chroma collection 재생성, chunk metadata 의 `category` 필드 채워짐.
2. **델타 시나리오**:
   - reference 에 신규 md 1개 추가 → watchdog 가 60s 내 sync 실행 → PROPOSAL md + release note md 생성
   - 동일 파일 수정 → 청크 upsert (id 동일), `chunks_modified` 증가
   - 파일 삭제 → 인덱스에서 hard delete, release note 에 `폐기` 항목
3. **PROPOSAL 승인**: `/knowledge-review` 호출 → 한 후보 approve, 한 후보 reject → canon md patch 적용 확인 + git commit sha 확인 + PROPOSAL `archive/` 이동 확인 + release note 의 `canon_commit_sha` 채워짐.
4. **카테고리 주입 검증**: 분석가 persona 에 `canon_categories: [stock-analysis/fundamental_analysis]` 만 두고 호출 → system prompt 에 fundamental_analysis 카테고리만 포함, technical_analysis 부재.
5. **회귀**: `TESTING=1 pytest` 통과 — 외부 API mock 필수 (vision API, anthropic LLM 호출).
6. **idempotent re-run**: 같은 sync 즉시 재실행 시 변경 없음(델타 0), 새 PROPOSAL/release note 생성 X.

## 단계별 가능 시점 (capability timeline)

| 종료 시점 | 사용자가 할 수 있게 되는 것 |
|---|---|
| Phase 0 종료 | 폴더만 정돈. 기능 변화 없음. 기존 `just knowledge-ingest <dept>` (INFRA-RAG-001) 그대로 동작 — 카테고리 metadata 는 비어있음 |
| **Phase 1~2 종료** | **reference 변경 자동 인덱싱 (watchdog 60s debounce + 수동 `just knowledge-sync`). 추론 질문 검증 가능: `just knowledge-browse <dept> "<query>"`. 카테고리 metadata 채워짐. 델타·삭제 hard 처리** |
| M3 종료 (별도 SPEC) | 5명 분석가 페르소나(`canon_categories`) 기반 production 호출에서 자료가 자동 활용. `_category.yaml` 의 `target_analysts` 정정 |
| Phase 3~5 종료 | PROPOSAL md 자동 생성 + `/knowledge-review` 사람 승인 + canon patch auto commit + release note 자동 작성 풀 사이클 |

→ 사용자가 reference 에 자료 push 하고 RAG 검색으로 추론 검증해보는 단계는 **Phase 1~2 종료 직후부터** 가능. PROPOSAL/release note 의 정확한 분석가 영향 추론은 M3 후 보장.

## 작업 순서 (phase 별)

권장 순서: **Phase 0 → Phase 1~2 → M3(별도 SPEC) → Phase 3~5**. Phase 0 은 본 SPEC + M3 의 공통 prerequisite. Phase 1~2 는 분석가 의존 없음. Phase 3~5 는 M3 완료 후 진행해야 분석가 추론 정확도 확보 (임시 hardcode 매핑·후속 교체 작업 제거).

**Phase 0 — 마이그레이션 (별도 사전 PR)**
1. 9 지식부 폴더 신설 + canon·reference 파일을 카테고리 폴더로 `git mv` (자료 0 지식부 = `market_macro` / `stock_selection` / `trading_journal` / `flow_analysis` 는 빈 카테고리 폴더 + `_category.yaml` 만)
2. 각 카테고리에 `_category.yaml` 작성
3. INFRA-RAG-001 의 ingest/retrieve 가 새 구조에서 동작하는지 회귀 확인

**Phase 1 — 어댑터 + 인덱싱 확장**
4. `core/knowledge/adapters/` 신설 (md/txt/pdf/xlsx/png)
5. `ingest.py` 확장: 카테고리 metadata 채움, 델타 모드 (`since_run_id` 인자)
6. `retrieve.py` 확장: `categories` 필터
7. `compose.py` 확장: `canon_categories` 기반 선택 주입

**Phase 2 — sync run + DB**
8. `core/db/schema.py` 에 `knowledge_index_runs` 추가
9. `core/knowledge/sync.py` 작성 (delta 발견 → 어댑터 → 인덱싱 → run log)

> ⛔ **Phase 3 prerequisite: M3 분석가 분화 SPEC 완료** — 5명 분석가의 `persona.md` (`canon_categories: [...]`) + `_category.yaml` 의 `target_analysts` 가 채워져야 PROPOSAL/release note LLM 추론이 정확. M3 전에는 reference 인덱싱(Phase 1~2)만 가동, PROPOSAL/release note 는 미작동.

**Phase 3 — PROPOSAL + release note 생성** (M3 후 진행)
10. `core/knowledge/proposal.py` (LLM 호출 → md 작성)
11. `core/knowledge/release_note.py` (LLM 호출 → md 작성)
12. `core/contracts/knowledge_sync.py` (Pydantic v2 모델)

**Phase 4 — 트리거 + 스킬**
13. `scripts/knowledge_sync.py` + `justfile` 명령 4개
14. `core/knowledge/watcher.py` (watchdog) + server lifecycle 등록
15. `.claude/skills/knowledge-sync.md`
16. `.claude/skills/knowledge-review.md` (canon patch + git commit + archive 이동)

**Phase 5 — 검증**
17. `just knowledge-rebuild stock-analysis` 실 인덱싱
18. 신규 md push → watchdog → PROPOSAL → /knowledge-review → canon commit 풀 사이클 검증
19. `TESTING=1 pytest` 회귀

## 위험 / 알려진 제약

- **마이그레이션 영향 큼** — 9 지식부 모두 폴더 한 단계 깊어짐. 분석가 persona.md / pipelines 호출부 / INFRA-RAG-001 ingest 모두 영향. Phase 0 별도 PR 로 분리해 위험 격리.
- **vision API 비용** — png 자료가 다수면 sync 1회당 비용 ↑. 초기엔 png 비활성 옵션(`config.knowledge.adapters.png.enabled: false`) 두고 가시화 후 결정.
- **watchdog 절전 누락** — 절전모드/sleep 후 fsevents 일부 누락 가능. server 재기동 시 git status 기준 reconcile 1회로 보완.
- **PROPOSAL md 의 LLM 정제 충돌** — 사용자가 `refined_patch:` 작성 중 다른 sync 가 같은 PROPOSAL 갱신할 일 없음(1 sync = 1 PROPOSAL md), 그러나 사용자 편집 중 git pull 시 conflict 가능 → frontmatter 의 sync_id 가 자연 lock.
- **첫 인덱싱 시간** — 카테고리 단위 metadata 채움이 추가되어 INFRA-RAG-001 대비 +α. 일회성.
- **canon SoT = repo** 로 결정한 만큼 **DB 화는 M2 web UI 단계에서 다시 결정 필요** — proposal/release_note 를 DB 로 옮기면 SoT 가 흔들림. M2 SPEC 에서 일관된 설계 필수.

## 마이그레이션 (DB)

- `knowledge_index_runs` 신규 테이블만 추가. 기존 데이터 마이그레이션 없음.
- INFRA-RAG-001 의 Chroma 인덱스는 카테고리 metadata 가 없는 상태 → Phase 0 마이그레이션 후 `/knowledge-rebuild` 로 재인덱싱 필요. 일회성.

<!-- SPEC:INTERVIEW-SLOT — 아래는 사용자 정제 대기 -->

## 보류 / 추가 정제 필요 (SLOT)

- [ ] **카테고리 _category.yaml 의 `when_to_inject` 의미** — `always` vs `on_demand` 의 런타임 동작 정확히 어떻게 다른지 (M3 분석가 분화 SPEC 과 결합 필요)
- [ ] **PROPOSAL LLM 호출 모델/토큰 한도** — Sonnet vs Haiku, 한 dept 의 canon 전문 + delta 가 200K 초과 시 분할 전략
- [ ] **release note 의 "영향받을 분석가" 추론 정확도** — M3 전 분석가 페르소나가 일부만 정의된 상태. 임시로 hardcode 매핑(`stock-analysis → stock_analyst, ...`) 두고 M3 후 동적 매핑으로 교체
- [ ] **watchdog debounce 60s 적정성** — 여러 파일 한 번에 push 할 때 묶음 시간. 사용자 패턴 관측 후 조정
- [ ] **PROPOSAL 의 LLM 대화 정제 (`/knowledge-review`)** — 정제 결과를 `refined_patch` 에 누적 vs 마지막 버전만 저장
- [ ] **png 어댑터 비활성 default 여부** — 비용·품질 가시화 전 default off 권장
- [ ] **xlsx 어댑터 시트별 분리 chunk vs 통합 chunk**
- [ ] **canon 자동 patch 시 파일 신규 생성 vs 기존 파일에 append** — `_category.yaml` 의 default_target 필드 추가 검토
