# 📐 STRUCTURE.md — 폴더 규약의 원천

> **이 문서가 프로젝트의 모든 폴더 규칙의 기준입니다.** 
> 어디에 파일을 둘지, 어떤 이름을 쓸지 결정할 때 항상 이 문서를 참조합니다.

---

## 🎯 5가지 설계 원칙 (북극성)

1. **자명성(Self-evidence)** — 폴더 이름만 봐도 역할이 드러나야 한다.
2. **대칭성(Symmetry)** — 모든 팀·컴포넌트는 동일한 내부 구조를 가진다.
3. **격리(Isolation)** — 팀은 다른 팀의 코드를 import 하지 않는다. DB·계약으로만 통신.
4. **추적성(Traceability)** — SPEC ↔ 코드 ↔ 테스트가 양방향으로 연결된다.
5. **검증성(Verifiability)** — `just validate` 하나로 모든 규약이 자동 검증된다.

---

## 🏛️ 최상위 폴더 (6개 역할)

| 폴더 | 역할 | 특징 |
|---|---|---|
| `teams/` | 🤖 AI 에이전트 팀 (분석/판단) | 각 팀이 `manifest.yaml`에 schedule 선언 |
| `mcp-servers/` | 🔌 외부 세계 연결 도구 | 별도 프로세스 (MCP 프로토콜) |
| `server/` | 🖥️ 상주 런타임 | FastAPI + APScheduler + 오케스트레이터 |
| `webapp/` | 🌐 UI (Next.js) | `server/api`를 HTTP로 호출만 함 |
| `core/` | 🧱 공유 라이브러리 | 모든 팀이 의존 |
| `docs/` | 📘 사람용 문서 | 규약, SPEC, 도메인 문서 |

보조 폴더:
- `config/` — 운영 설정 (동적 리로드 대상)
- `knowledge/` — 팀 공용 기본 자료
- `data/` — 런타임 데이터 (gitignore)
- `scripts/` — 개발·운용 도구
- `tests/` — E2E 테스트 (팀 단위는 각 팀 폴더)
- `.claude/` — Claude Code 설정

**규칙**: 하나의 모듈은 **하나의 폴더 역할**에만 속한다. 어디에 둘지 모호하다면 STRUCTURE.md를 다시 읽는다.

---

## 🤖 팀 표준 레이아웃 (teams/<team-id>/)

모든 팀은 이 구조를 **100% 동일하게** 따른다. `scripts/validate.py` 가 자동 검증.

```
teams/<team-id>/
├── CLAUDE.md                 # 이 팀의 AI 컨텍스트 (짧고 명확)
├── persona.md                # LLM 주입용 페르소나 (LLM 팀만)
├── manifest.yaml             # ★ 팀 메타데이터 (스케줄/메모리/지식 선언)
├── CHANGELOG.md              # 이 팀의 변경 이력
├── specs/                    # 이 팀 전용 SPEC
│   ├── <PREFIX>-001-*.md
│   └── <PREFIX>-002-*.md
├── src/
│   ├── __init__.py
│   ├── agent.py              # ★ 표준 진입점: class Agent: async def run(input) -> Output
│   ├── prompts/              # (LLM 팀) 프롬프트 템플릿
│   └── <module>.py           # 기타 구현
├── knowledge/                # 이 팀 전용 학습 자료
│   ├── sources/              # 원본 (PDF/MD/YouTube urls.txt)
│   ├── compiled.md           # Canon (LLM으로 압축된 핵심 프레임워크)
│   ├── vector-index/         # Chroma DB (gitignore)
│   └── templates/            # 프롬프트/롤업 템플릿
└── tests/
    ├── test_agent.py         # 팀 전체 계약 테스트
    └── test_<module>.py
```

### 필수 파일 체크리스트
- [x] `CLAUDE.md`
- [x] `manifest.yaml`
- [x] `src/agent.py` (표준 Agent 클래스)
- [x] `tests/test_agent.py` (계약 테스트)
- [x] `CHANGELOG.md`
- [x] `persona.md` — LLM 팀만

### `manifest.yaml` 필수 필드
```yaml
id: <team-id>              # 폴더 이름과 일치
name: <한글 이름>
type: team-agent
runtime: rule | llm | hybrid
inputs:
  - source: ...            # mcp:<name> | db | seed | user
    ...
outputs:
  - target: db
    tables: [team_outputs, ...]
schedule:                  # 선택. 없으면 수동/이벤트 트리거
  - trigger: cron | interval | event
    expr: "..."
    timezone: Asia/Seoul
contract_version: "1.0"
depends_on: []             # 다른 팀의 코드 import 금지. 의존 "테이블/계약" 만 명시.
status: planned | scaffolded | implemented | verified
owner: <사람 또는 팀>
memory:                    # 선택. 기본값은 core 기본값 적용
  enabled: true
  retention: { raw_days: 180, ... }
  context_budget_tokens: 4000
knowledge:                 # 선택. knowledge 레이어 활성화
  canon: { version: 1, path: knowledge/compiled.md, token_budget: 8000 }
  reference: { enabled: true, retrieval_top_k: 3 }
```

---

## 🔌 MCP 서버 표준 레이아웃 (mcp-servers/<id>/)

```
mcp-servers/<id>/
├── CLAUDE.md
├── manifest.yaml           # 타입: mcp-server, 제공 도구 목록
├── src/
│   ├── server.py           # MCP 서버 진입점 (Python MCP SDK)
│   └── tools/
├── tests/
└── README.md               # 사람용: 이 서버가 제공하는 도구 설명
```

---

## 📜 SPEC 문서 규약

### 파일명: `<PREFIX>-<NNN>-<slug>.md`
- PREFIX = 팀 ID 대문자 또는 특별 분류
  - 예: `PRINCIPLE`, `MACRO`, `TECH`, `BRIEFING`
  - 전역: `GLOBAL`, 계약: `CONTRACT`, 인프라: `INFRA`
- `NNN` = 팀별 3자리 순번 (001부터)
- `<slug>` = kebab-case 짧은 제목

예: `PRINCIPLE-001-seven-commandments-checker.md`, `CONTRACT-001-team-output-v1.md`

### 위치
| SPEC 범위 | 위치 |
|---|---|
| 단일 팀 전용 | `teams/<team-id>/specs/` |
| 여러 팀 공유 | `docs/specs/` |
| 계약(프로토콜) | `docs/specs/CONTRACT-*.md` |
| 인프라(core/server) | `docs/specs/INFRA-*.md` |

### 필수 Frontmatter
```yaml
---
spec_id: PRINCIPLE-001
title: 7계명 체커
team: principles
type: feature            # feature | refactor | infra | protocol
status: draft            # draft | approved | implementing | implemented | verified
generates:               # ★ 이 SPEC이 만들 파일들 (validate.py가 검증)
  - teams/principles/src/commandments/weight_limit.py
  - teams/principles/tests/test_commandments.py
modifies:                # 수정할 기존 파일 (있으면)
  - core/db/schema.sql
depends_on:              # 선행 SPEC
  - INFRA-001
contracts:               # 따르는 계약
  - contract: team-output-v1
---
```

### 성장 포인트 마커
SPEC은 처음엔 뼈대만 쓰고, `/spec-interview` 로 점진적으로 살을 붙입니다.
비워둔 자리는 HTML 주석으로 명시:

```markdown
## 판단 로직
<!-- SPEC:INTERVIEW-SLOT role="judgment-logic" -->
(이 영역은 /spec-interview 로 채워집니다)
```

AI는 `INTERVIEW-SLOT` 마커가 있는 영역만 수정하고 나머지는 건드리지 않습니다.

---

## 🔗 계약 레이어 (core/contracts/)

팀 간 통신은 **Pydantic 모델로 정의된 계약**을 통해서만 이루어집니다.

| 계약 | 파일 | 설명 |
|---|---|---|
| StandardOutput | `core/contracts/team_output.py` | 모든 팀 출력의 표준 형식 |
| SpecFrontmatter | `core/contracts/spec_frontmatter.py` | SPEC 메타 파서 |
| MemoryRecord | `core/contracts/memory.py` | 팀 메모리 레코드 |
| KnowledgeChunk | `core/contracts/knowledge.py` | RAG 청크 메타 |

**규칙**: 계약 변경 시 `contract_version`을 올리고, 하위 호환성 또는 마이그레이션 경로를 명시합니다.

---

## ⚙️ config/ — 동적 설정

```
config/
├── defaults.yaml           # 커밋되는 안전한 기본값
└── runtime.yaml            # 수정 시 서버가 watchdog로 자동 감지 → 핫 리로드
```

- `.env` = 시크릿 (API 키 등). git에 절대 올리지 않음.
- `config/runtime.yaml` = 운영 설정 (임계값, 스케줄, 알림 포맷).
- 코드에서는 `from core.config import config` 로 타입 안전하게 접근.
- 잘못된 YAML 저장 시 → **이전 설정 유지 + 에러 로그** (안전 실패).

---

## 💾 data/ — 런타임 데이터 (gitignore)

```
data/
├── db/stock-advisor.sqlite    # 메인 SQLite DB
├── backups/                   # 일별 DB 백업 (30일 보관)
├── reports/                   # 생성된 리포트 (마크다운)
├── memory/<team>/YYYY-MM-DD.md   # 팀별 일일 narrative
├── notifications/*.jsonl      # Telegram 미설정 시 알림 폴백
├── seed/                      # 시드 데이터 (mock_portfolio.json 등) — 커밋함
└── snapshots/last_snapshot.json  # 갭필링용 상태
```

**규칙**: `data/`는 gitignore. 단 `data/seed/` 는 예외 (커밋 허용).

---

## 🧱 core/ — 공유 라이브러리

```
core/
├── db/               # SQLite 연결, 마이그레이션
├── contracts/        # Pydantic 계약 모델
├── llm/              # LLM 클라이언트 (Anthropic 중심 + Prompt Caching)
├── memory/           # LLM 맥락 메모리 레이어
│   ├── loader.py     # 계층별 컨텍스트 조회 + 토큰 예산 내 추리기
│   ├── composer.py   # system_prompt 조립
│   ├── rollup.py     # 일/주/월 롤업 생성
│   ├── cleanup.py    # 보관기간 경과 pruning
│   ├── cache.py      # LLM 호출 캐시 (멱등성)
│   └── hasher.py     # input_hash 정규화/계산
├── knowledge/        # RAG 지식 레이어
│   ├── ingest.py     # 자료 수집 + 텍스트 추출
│   ├── chunk.py      # 청킹
│   ├── embed.py      # Embedding
│   ├── store.py      # Chroma DB
│   ├── retrieve.py   # 유사도 검색
│   ├── compile.py    # Canon 생성
│   └── manifest.py   # 팀별 자료 카탈로그
├── config/           # 통합 Config + 동적 리로드
├── logging/          # 구조화 로거
├── notification/     # 알림 발송 (Telegram + 파일 폴백)
└── scheduler/        # APScheduler 래퍼
```

**규칙**: `core/`는 프레임워크. 특정 팀·도메인 로직이 들어가지 않는다.

---

## 🖥️ server/ — 상주 런타임

```
server/
├── main.py                    # ★ uvicorn 진입점. FastAPI + APScheduler 시작.
├── api/                       # REST 엔드포인트
│   ├── teams.py               #   GET /api/teams, GET /api/teams/<id>/latest
│   ├── config.py              #   GET/POST /api/config
│   ├── demo.py                #   POST /api/demo/run?scenario=...
│   └── telegram.py            #   Telegram webhook
├── orchestration/
│   └── runner.py              # asyncio.gather 병렬 팀 실행
├── schedulers/
│   ├── loader.py              # 팀 manifest의 schedule 읽어 APScheduler 등록
│   └── jobs/                  # 팀에 속하지 않는 인프라성 작업만
│       ├── backup.py
│       ├── gap_filler.py
│       ├── daily_rollup.py
│       ├── weekly_rollup.py
│       ├── monthly_rollup.py
│       └── memory_cleanup.py
└── CLAUDE.md
```

**원칙**: `server/`는 FastAPI + 스케줄러만. 팀 로직은 전혀 없음. 오로지 팀을 "불러쓰는" 레이어.

---

## 🌐 webapp/ — UI

```
webapp/
├── CLAUDE.md
└── src/
    ├── app/                   # Next.js App Router
    ├── components/
    └── lib/                   # fetch 래퍼, 타입 등
```

**규칙**: webapp은 **UI만**. 모든 데이터는 `server/api`를 HTTP로 호출해서 얻음.

---

## 📚 knowledge/ vs teams/<team>/knowledge/

| 위치 | 용도 |
|---|---|
| `knowledge/` (최상위) | 여러 팀이 공유하는 기본 자료 (시장 상식, 용어 사전 등) |
| `teams/<team>/knowledge/` | 해당 팀 전용 자료 (페르소나 관점의 전문 지식) |

자료 투입 흐름:
1. 사용자가 `teams/<team>/knowledge/sources/` 에 파일 드롭
2. `just knowledge-ingest <team>` → Chroma 인덱싱
3. `just knowledge-compile <team>` → Canon (compiled.md) 재생성
4. 서버가 config reload 감지 → 다음 판단부터 반영

---

## 🔧 scripts/ — 개발·운용 도구

| 스크립트 | 역할 |
|---|---|
| `scaffold.py` | 새 팀/MCP/SPEC 자동 생성 (표준 레이아웃) |
| `validate.py` | 전체 구조 정합성 검증 |
| `trace.py` | SPEC ↔ 코드 양방향 매핑 (`docs/traceability.md` 생성) |
| `generate_domain_doc.py` | SPEC + 코드 → 도메인 문서 자동 생성 |

`justfile` 에서 모든 명령을 단축 (`just validate`, `just trace`, `just new-team <id>`).

---

## 📘 docs/ 구조

```
docs/
├── STRUCTURE.md          # ★ 이 문서 (규약의 원천)
├── WORKFLOW.md           # SDD 사이클 1페이지
├── CONTRACTS.md          # 팀 간 계약 명세
├── RUNTIME.md            # 서버·스케줄러·메모리·지식 동작
├── FOUNDATION-PLAN.md    # 이 토대의 설계 계획서
├── traceability.md       # 자동 생성 (SPEC↔코드 매핑)
├── specs/                # 전역 SPEC
│   ├── CONTRACT-*.md
│   ├── INFRA-*.md
│   └── GLOBAL-*.md
├── domain/               # ★ 자동 생성 — 사용자용 결과물 설명서
│   └── <team>/<topic>.md
└── [기존 아키텍처 원본 문서들]
```

**`docs/domain/` 은 자동 생성**. 사람이 직접 편집하지 않음. `scripts/generate_domain_doc.py` 가 SPEC + 코드 docstring + 테스트 케이스를 조합해 생성.

---

## ✅ 검증 규칙 (validate.py가 체크)

- [ ] 모든 팀이 필수 파일(CLAUDE.md, manifest.yaml, src/agent.py) 구비
- [ ] 모든 SPEC이 frontmatter 구비
- [ ] SPEC의 `generates` 경로에 실제 파일 존재 (status=implemented 이상)
- [ ] `teams/registry.yaml` ↔ 팀 폴더 존재 일치
- [ ] `mcp-servers/registry.yaml` ↔ MCP 폴더 존재 일치
- [ ] DB 스키마 ↔ `core/db/schema.sql` 일치
- [ ] 팀 간 코드 import 없음 (AST 검사)
- [ ] 모든 `.py` 파일이 타입 힌트 구비 (선택적 경고)
- [ ] `contract_version` 충돌 없음
- [ ] `config/runtime.yaml` 이 Pydantic 스키마 통과

---

## 🚫 절대 하지 말 것

- 팀에서 다른 팀 코드 `import` 금지 — DB나 메시지 계약으로만 통신
- `.sh` 스크립트 작성 금지 — `justfile` + Python 스크립트 사용
- 문자열 경로 조합 금지 — `pathlib.Path` 사용
- 하드코딩된 임계값 금지 — `config/runtime.yaml` 에 선언
- SPEC의 `generates` 외 위치에 파일 생성 금지
- `data/` 아래 파일을 커밋 (단, `data/seed/` 제외)
- `config/runtime.yaml` 과 `.env` 값을 코드에 인라인하지 않기
