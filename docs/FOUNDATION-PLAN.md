# 🏗️ wevelStock — 확장 가능한 SDD 토대 설계 (확정 v0.5)

## 📬 사용자 질문에 대한 답변 (v0.3 정정)

### Q1. `batch/` 는 왜 있지? 서버에 올라간 agent가 연속성을 갖는 것 아닌가?
**→ 정답입니다. `batch/` 는 불필요했습니다. v0.3에서 제거.**
- 서버(FastAPI)가 상주하고 그 안에 **APScheduler**가 같이 돌아갑니다.
- "배치"로 분류했던 것들(일일 매크로, 1시간 리프레시, 갭필링, 백업)은 모두 **서버 안의 스케줄 작업**일 뿐.
- 팀 manifest에 `schedule:` 필드를 두면 **팀이 스스로 자기 스케줄을 선언**하고, 스케줄러가 이걸 읽어 실행.
- 인프라성 작업(백업/로그로테이션/갭필링)만 `server/jobs/` 에 소수.
- 결론: 별도 `batch/` 폴더 삭제. 개념적으로도 "배치 = 스케줄에 따라 실행되는 에이전트" 이므로 팀과 중복.

### Q2. `api/` 는 왜 없지? webapp이 API까지 겸하나?
**→ 정답입니다. API 레이어가 보이지 않았습니다. v0.3에서 `server/` 로 명시.**
- 원래 `backend/` 라고 모호하게 썼는데, 이게 바로 **API + 스케줄러 + 오케스트레이터 진입점**이 다 들어있는 런타임 서버입니다.
- webapp(Next.js)은 **UI만** 담당하고, HTTP로 `server/` 에 요청만 보냄. API는 겸하지 않음.
- v0.3부터 `server/` 로 이름 변경 + 내부를 `api/`(REST routes), `jobs/`(스케줄 작업), `main.py`(uvicorn 진입)로 명확히 분리.
- 텔레그램 봇 webhook도 `server/api/telegram.py` 로 들어옴.

### 정정된 최상위 타입 (4가지)
```
teams/        — 🤖 AI 에이전트 (분석/판단) — 각 팀이 자기 스케줄 선언
mcp-servers/  — 🔌 외부 세계 연결 도구 (KIS, FRED, Telegram 발송)
server/       — 🖥️ 상주 런타임 (FastAPI + APScheduler + 오케스트레이터 진입점)
webapp/       — 🌐 UI (Next.js, 순수 프론트엔드)
core/         — 🧱 공유 라이브러리 (DB/contracts/llm/config/logging/notification)
docs/         — 📘 사람용 문서
```
→ **6개 폴더 = 6개 역할.** 중복 없음. 더 자명해짐.

---

## Context (왜 이 설계가 필요한가)

- 프로젝트는 **8개 팀 에이전트**에서 시작하지만, 앞으로 **N개로 계속 확장**되어야 한다.
- 개발자(사용자)는 **코드를 읽지 못해도** 프로젝트 구조만 보면 "어디에 뭐가 있고, 어떻게 동작하는지" 이해할 수 있어야 한다.
- SPEC 문서 하나를 올바른 위치에 쓰면, **코드가 예측 가능한 위치에 생성**되어야 한다 (AI가 막연하게 파일을 만들지 못함).
- 각 모듈은 4가지 타입 중 하나로 **명확히 분류**되어야 한다: `team-agent` | `mcp-server` | `batch` | `webapp`
- 새 팀을 추가할 때 **기존 구조를 건드리지 않고** 삽입만 하면 되어야 한다 (Open-Closed).

---

## 🎯 설계 원칙 5가지 (전체 시스템의 북극성)

1. **자명성(Self-evidence)** — 폴더 이름만 봐도 역할이 드러난다.
2. **대칭성(Symmetry)** — 모든 팀/컴포넌트는 동일한 내부 구조를 가진다.
3. **격리(Isolation)** — 팀은 다른 팀의 코드를 import 하지 않는다. 공유 DB 테이블과 메시지 계약으로만 통신한다.
4. **추적성(Traceability)** — SPEC ↔ 코드 ↔ 테스트가 양방향으로 연결된다 (헤더 메타데이터로).
5. **검증성(Verifiability)** — 스크립트 하나로 전체 구조의 정합성을 자동 검증할 수 있다.

---

## 📁 최상위 폴더 구조 (v0.3 — 6개 역할)

```
wevelStock/
├── README.md              # ★ 비개발자용 입구. "여기만 읽으면 전체 파악 가능"
├── CLAUDE.md              # ★ AI용 입구. 총괄 오케스트레이터 관점
│
├── docs/                  # 📘 사람용 문서 (지식)
│   ├── STRUCTURE.md       #   폴더 규약 (모든 규칙의 출처)
│   ├── WORKFLOW.md        #   SPEC 쓰기 → 코드 생성 절차 (1페이지)
│   ├── CONTRACTS.md       #   팀 간 메시지 계약
│   ├── RUNTIME.md         #   서버·스케줄러·오케스트레이터 동작 설명
│   ├── specs/             #   전역 SPEC (여러 팀에 걸친 것)
│   ├── domain/            #   자동 생성 도메인 문서 (사용자용 결과물)
│   └── [기존 아키텍처 문서 6개]
│
├── teams/                 # 🤖 AI 에이전트 (분석/판단)
│   ├── _template/         #   새 팀 만들 때 복사할 원본
│   ├── registry.yaml      #   모든 팀 목록 (자동 생성/검증)
│   ├── principles/        #   첫 팀 ① (규칙 기반 예시)
│   ├── daily-briefing/    #   첫 팀 ② (LLM 기반 예시)
│   ├── orchestrator/      #   팀 실행 조율 (lite, 서버에 의해 호출됨)
│   └── ... (팀 N개 삽입)
│
├── mcp-servers/           # 🔌 외부 세계 연결 도구
│   ├── _template/
│   ├── registry.yaml
│   ├── kis-api/           #   한국투자증권 (Python)
│   ├── global-data/       #   FRED, yfinance (Python)
│   └── notification/      #   Telegram 발송 (Python)
│
├── server/                # 🖥️ 상주 런타임 — 이 프로세스 하나가 "서버"의 전부
│   ├── main.py            #   ★ uvicorn 진입점. FastAPI + APScheduler 시작.
│   ├── api/               #   REST 엔드포인트 (webapp/Telegram webhook/CLI 용)
│   │   ├── teams.py       #     GET /api/teams, GET /api/teams/<id>/latest
│   │   ├── config.py      #     GET/POST /api/config (조회/리로드)
│   │   ├── demo.py        #     POST /api/demo/run?scenario=...
│   │   └── telegram.py    #     Telegram webhook 수신
│   ├── orchestration/     #   팀 실행 조율 (teams/orchestrator 호출)
│   │   └── runner.py      #     asyncio.gather 병렬 실행
│   ├── schedulers/        #   스케줄러 설정 + 인프라성 작업
│   │   ├── loader.py      #     팀 manifest의 schedule 읽어 APScheduler 등록
│   │   └── jobs/          #     팀에 속하지 않는 인프라 작업만
│   │       ├── backup.py          # 매일 자정 DB 백업
│   │       ├── gap_filler.py      # 서버 시작 시 갭 필링
│   │       ├── daily_rollup.py    # 23:50 메모리 일일 롤업
│   │       ├── weekly_rollup.py   # 일요일 주간 롤업
│   │       ├── monthly_rollup.py  # 월말 월간 롤업
│   │       └── memory_cleanup.py  # 월 1회 오래된 메모리 정리
│   └── CLAUDE.md
│
├── webapp/                # 🌐 UI (Next.js, 순수 프론트엔드)
│   ├── CLAUDE.md
│   └── src/               #   server/api 를 fetch 로 호출만 함
│
├── core/                  # 🧱 공유 라이브러리
│   ├── db/                #   SQLite 연결, 마이그레이션
│   ├── contracts/         #   StandardOutput, SPEC frontmatter 스키마
│   ├── llm/               #   LLM 클라이언트 (Anthropic 중심 + Prompt Caching)
│   ├── memory/            #   ★ LLM 맥락 메모리 레이어 (loader/composer/rollup/cleanup/cache/hasher)
│   ├── knowledge/         #   ★ RAG 지식 레이어 (ingest/chunk/embed/store/retrieve/compile)
│   ├── config/            #   통합 Config + 동적 --reload (pydantic-settings + watchdog)
│   ├── logging/           #   공통 로거
│   └── notification/      #   알림 발송 래퍼 (Telegram MCP 호출 + 파일 폴백)
│
├── config/                # ⚙️ 운영 설정 파일 (동적)
│   ├── defaults.yaml      #   안전한 기본값 (커밋)
│   └── runtime.yaml       #   동적 설정 (수정 시 핫 리로드)
│
├── knowledge/             # 📚 팀 공용 기본 자료 (팀별 지식은 teams/<팀>/knowledge/)
│
├── data/                  # 💾 런타임 데이터 (gitignore)
│   ├── db/stock-advisor.sqlite
│   ├── backups/
│   ├── reports/
│   ├── memory/            #   ★ 팀별 일일 narrative (data/memory/<team>/YYYY-MM-DD.md)
│   ├── notifications/     #   Telegram 미설정 시 파일 폴백
│   ├── seed/              #   시드 데이터 (mock_portfolio.json 등)
│   └── snapshots/         #   last_snapshot.json (갭필링용)
│
├── scripts/               # 🔧 개발/운용 도구 (사람이 실행)
│   ├── scaffold.py        #   새 팀/MCP/SPEC 자동 생성
│   ├── validate.py        #   구조 정합성 검증
│   ├── trace.py           #   SPEC ↔ 코드 매핑
│   └── generate_domain_doc.py  # 도메인 문서 자동 생성
│
├── .claude/
│   ├── commands/          #   /spec-interview, /evolve-review 등
│   └── settings.json
│
├── .mcp.json              # MCP 서버 등록
├── .env.example           # 시크릿만 (API 키 등)
├── .gitattributes
├── .gitignore
├── pyproject.toml         # Python 의존성 (uv)
├── justfile               # 크로스플랫폼 태스크 러너
└── tests/                 # E2E 테스트 (팀 단위는 팀 폴더에)
```

### 왜 이 구조인가 (v0.3 개선점)
- **`batch/` 삭제**: 스케줄러는 서버 안에 상주. 팀이 `manifest.yaml`의 `schedule:` 필드로 자기 주기를 선언 → `server/schedulers/loader.py`가 읽어 등록. 인프라성 작업만 `server/schedulers/jobs/`에.
- **`server/` 명시**: 이 프로세스 하나가 API + 스케줄러 + 오케스트레이터를 모두 담는다. 한눈에 "상주 프로세스의 집"임을 알 수 있음.
- **`server/api/` 로 API 레이어 명시**: webapp은 UI만, API는 server가 제공. 역할 분리 명확.
- **`config/` 를 최상위로 분리**: 시크릿(`.env`)과 운영 설정(yaml)을 명확히 분리. 운영 설정은 핫 리로드 대상.
- 각 타입 폴더는 **동일한 대칭 구조**(`_template/`, `registry.yaml`) 유지 → 확장은 "삽입"만으로 끝난다.

---

## 📐 팀 에이전트 표준 폴더 (Team Agent Standard Layout)

**모든 팀은 이 구조를 100% 따른다.** 예외 없음. `scripts/validate.py`가 자동 검증.

```
teams/<team-id>/
├── CLAUDE.md              # 이 팀의 컨텍스트 (AI가 읽음, 간결하게)
├── persona.md             # LLM system prompt 주입용 페르소나 (LLM 팀만)
├── manifest.yaml          # ★ 팀 메타데이터 (스케줄/메모리/지식 선언)
├── specs/                 # 이 팀 전용 SPEC 문서
│   ├── <PREFIX>-001-*.md  # PREFIX = PRINCIPLE, MACRO, TECH 등
│   └── <PREFIX>-002-*.md
├── src/
│   ├── __init__.py
│   ├── agent.py           # ★ 표준 진입점: class Agent { async run(input) -> Output }
│   ├── prompts/           # (LLM 팀) 프롬프트 템플릿
│   └── <모듈>.py           # 기타 구현
├── knowledge/             # ★ 이 팀 전용 학습 자료
│   ├── sources/           #   원본 자료 (PDF/MD/YouTube URL)
│   │   ├── *.pdf
│   │   ├── *.md
│   │   └── youtube/urls.txt
│   ├── compiled.md        #   ★ Canon (압축된 핵심 프레임워크)
│   ├── vector-index/      #   ★ Chroma DB (RAG 인덱스, gitignore)
│   └── templates/         #   프롬프트/롤업 템플릿
├── tests/
│   ├── test_agent.py      # 팀 전체 계약 테스트 (표준 출력 스키마)
│   └── test_<모듈>.py
└── CHANGELOG.md           # 이 팀의 변경 이력
```

### `manifest.yaml` 예시 — 팀의 자기소개 카드 (스케줄 포함)
```yaml
id: macro-analysis
name: 매크로 경제 분석팀
type: team-agent
runtime: llm        # llm | rule | hybrid
inputs:
  - source: mcp:global-data
    tools: [get_fred_series, get_yahoo_ticker]
  - source: db
    tables: [daily_macro]
outputs:
  - target: db
    tables: [team_outputs, daily_macro]
schedule:                    # ★ 팀이 자기 실행 주기를 선언
  - trigger: cron
    expr: "30 8 * * *"       #   매일 08:30 KST
    timezone: Asia/Seoul
  - trigger: event
    on: market_open          #   국내장 개장 시 1회
contract_version: "1.0"
depends_on: []               # 다른 팀 코드 import 금지. 참조만 가능한 공유 테이블/계약 명시.
status: planned              # planned | scaffolded | implemented | verified
owner: orchestrator
```

→ `teams/registry.yaml`은 이 manifest들을 스캔해서 자동 생성된다.
→ 서버 시작 시 `server/schedulers/loader.py` 가 모든 팀의 `schedule:` 을 읽어 APScheduler에 등록.
→ 팀 추가 = manifest 선언 + schedule 선언 → **서버 재시작 또는 config reload 시 자동 반영**.

---

## 📜 SPEC 문서 표준 (SPEC → 코드 자동 매핑)

### 모든 SPEC 파일 상단에 **Frontmatter 필수**

```markdown
---
spec_id: SPEC-003
title: 기술 지표 계산 엔진
team: technical-analysis
type: feature              # feature | refactor | infra | protocol
status: draft              # draft | approved | implementing | implemented | verified
generates:                 # 이 SPEC이 만들어낼 파일들 (예상)
  - teams/technical-analysis/src/indicator_engine.py
  - teams/technical-analysis/tests/test_indicator_engine.py
modifies:                  # 이 SPEC이 수정할 기존 파일 (있으면)
  - core/db/schema.sql
depends_on:                # 선행 SPEC
  - SPEC-001
  - SPEC-002
contracts:                 # 이 SPEC이 따르는 메시지/데이터 계약
  - contract: team-output-v1
  - contract: technical-indicator-schema-v1
---

# SPEC-003: 기술 지표 계산 엔진
(본문…)
```

### 규약이 주는 힘
- `scripts/trace.py`가 frontmatter를 파싱하여 **SPEC ↔ 코드 매핑 테이블**을 자동 생성 (`docs/traceability.md`)
- `scripts/validate.py`가 **generates에 선언된 파일이 실제로 존재하는지 검증**
- SPEC `status`가 `implemented`인데 코드가 없으면 → 경고
- AI가 엉뚱한 곳에 파일을 생성하면 → 검증에서 바로 탐지

### SPEC 위치 규칙
- 단일 팀 관련 → `teams/<team-id>/specs/SPEC-XXX-*.md`
- 여러 팀에 걸침 → `docs/specs/SPEC-XXX-*.md` (전역)
- 프로토콜/계약 → `docs/specs/CONTRACT-XXX-*.md`

---

## 🔗 팀 간 통신 표준 (Message Contract v1.0)

### 규칙
- 팀끼리 **코드 import 금지** — 오로지 DB 테이블과 표준 JSON 메시지로만 통신.
- 모든 팀 출력은 `team_outputs` 테이블에 통일 저장 (팀별 고유 데이터는 JSON 컬럼).
- 스키마 변경 시 `contract_version` 을 올리고 하위 호환성 검토.

### `team_outputs` 테이블 스키마
```sql
CREATE TABLE team_outputs (
    run_id TEXT,              -- 실행 식별자 (UUID)
    team_id TEXT,             -- manifest.yaml의 id
    timestamp TEXT,
    target TEXT,              -- 대상(ticker, market, "global" 등)
    verdict TEXT,             -- 표준 판단값
    confidence INTEGER,       -- 0-100
    reasons_json TEXT,        -- JSON array
    data_json TEXT,           -- 팀별 고유 데이터 (JSON)
    contract_version TEXT,
    PRIMARY KEY (run_id, team_id, target)
);
```

### 표준 출력 JSON (`StandardOutput`)
```json
{
  "team_id": "macro-analysis",
  "timestamp": "2026-04-16T09:00:00+09:00",
  "target": "global",
  "verdict": "상승장",
  "confidence": 78,
  "reasons": ["금리 안정", "유동성 증가"],
  "data": { /* 팀별 고유 데이터 */ },
  "contract_version": "1.0"
}
```

→ `core/contracts/team_output.py`에 Pydantic 모델로 정의. 모든 팀은 이 모델을 반환.

---

## 🧪 확장성 보장 장치 (Extensibility Primitives)

새 팀을 추가할 때 **기존 파일을 하나도 건드리지 않고** 작동해야 한다.

### 1. 스캐폴더: `scripts/scaffold.py`
```bash
python scripts/scaffold.py team sentiment-analysis --runtime llm
# → teams/sentiment-analysis/ 폴더와 표준 레이아웃 전체 자동 생성
# → manifest.yaml 초기값 작성
# → teams/registry.yaml 자동 갱신
# → SPEC-000-<team>-bootstrap.md 초안 생성
```

지원 명령:
- `scaffold.py team <id>` — 새 팀
- `scaffold.py mcp <id>` — 새 MCP 서버
- `scaffold.py batch <id>` — 새 배치 작업
- `scaffold.py spec <team> <title>` — 새 SPEC 문서

### 2. 레지스트리: `<타입>/registry.yaml`
- 각 타입 폴더마다 존재
- manifest.yaml들을 스캔해서 자동 생성
- 중복 id/포트/스케줄 충돌 자동 감지

### 3. 검증: `scripts/validate.py`
체크 항목:
- 모든 팀이 표준 레이아웃(CLAUDE.md, manifest.yaml, src/agent.py) 준수
- 모든 SPEC이 frontmatter 구비
- SPEC `generates` 파일이 실제 존재
- registry.yaml ↔ 폴더 존재 일치
- DB 스키마 ↔ `core/db/schema.sql` 일치
- contract_version 호환성

`just validate` 한 번이면 끝. CI에서도 동일 실행.

### 4. 추적: `scripts/trace.py`
```bash
python scripts/trace.py
# → docs/traceability.md 자동 생성
# → "SPEC-003이 어떤 파일을 만들었는지", "이 파일은 어느 SPEC에서 왔는지" 양방향 조회
```

### 5. 계약 버전: `CONTRACT_VERSION`
- `core/contracts/`에 v1, v2 공존 가능
- 팀이 점진적으로 버전 업그레이드
- 오케스트레이터가 호환성 자동 협상

---

## 📖 문서 네비게이션 (비개발자를 위한 3단 입구)

```
[1층] README.md            — 프로젝트 한눈에. 폴더 지도. 다음 어디로 갈지.
  ↓
[2층] docs/STRUCTURE.md    — 폴더 규약 전체 (이 한 파일이 모든 규칙의 원천)
      docs/WORKFLOW.md     — "새 기능 만들고 싶다 → 어떻게?" 1페이지 절차
      docs/CONTRACTS.md    — 팀 간 메시지 계약
  ↓
[3층] teams/<팀>/CLAUDE.md — 해당 팀 맥락
      teams/<팀>/specs/    — 실제 상세 기능 명세
```

핵심: **비개발자가 2층까지만 읽으면 "이 팀에 새 기능을 넣으려면 SPEC을 어디에 써야 하고 코드가 어디 생길지" 를 이해할 수 있어야 한다.**

---

## 🎯 첫 팀 선정: **두 팀 동시 조기 경험**

**결정**: 한 팀이 아니라 **두 팀**을 첫 풀사이클에 포함시킨다. 이유는 **두 개의 팀 패턴(규칙 기반 / LLM 기반)이 모두 살아있는 템플릿 예시**로 존재해야 향후 팀 추가 시 참조가 완벽해지기 때문.

### 첫 팀 ① **원칙 관리팀 (`principles`)** — 규칙 기반 패턴 예시
- 외부 API/LLM 의존 0. 규칙 기반(`runtime: rule`)
- 입력: `data/seed/mock_portfolio.json` (시나리오 4개: 정상/비중초과/손절없음/감정매매)
- 출력: `team_outputs` 테이블 + Telegram 알림 + 대시보드 스코어카드
- 7계명 각각을 개별 체커 모듈로 (`commandments/weight_limit.py` 등) → 규칙 기반 팀이 **모듈을 쪼개는 표준 방식** 제시

### 첫 팀 ② **데일리 브리핑 팀 (`daily-briefing`)** — LLM 기반 패턴 예시
- 입력: DB에서 최근 N일 요약 읽기 (원칙팀 결과 + 시드 매크로 데이터)
- 처리: Claude Sonnet 4 API 호출로 "오늘의 브리핑" 생성 (`runtime: llm`)
- 출력: `team_outputs` + Telegram 브리핑 메시지 + 대시보드 브리핑 카드
- 페르소나(`persona.md`) 주입 + knowledge 요약 주입 **이 실제로 LLM system prompt에 반영되는 코드 경로**를 증명
- `ANTHROPIC_API_KEY` 미설정 시 → mock LLM 응답으로 폴백 (로컬 개발/CI 지원)

### 두 팀을 함께 구현하는 이유 (확장성 증거)
- **두 패턴**(rule/llm)이 템플릿으로 공존 → 다음 팀은 "이 둘 중 어느 쪽인가"만 선택
- 오케스트레이터(lite)가 **두 팀을 asyncio.gather로 병렬 실행**하는 첫 증거 확보
- 팀 간 의존성(데일리 브리핑이 원칙팀 결과를 읽음) → **DB 계약만으로 통신하는 패턴** 시연
- Telegram 채널/포맷 분리 시연 (원칙 경고 vs 브리핑)
- 대시보드에 **두 카드**가 등장 → "팀 하나 추가 = 카드 하나 추가"의 규칙 증명

### SPEC 문서 철학: **뼈대만, 살은 `/spec-interview`로**
- 두 팀의 초기 SPEC은 **최소 프레임**만 작성 (frontmatter + 목적 + 입출력 계약).
- 상세 판단 로직/엣지케이스/확장 포인트는 **의도적으로 비워둠** — 이후 `/spec-interview` 로 점진 발전.
- 즉, SPEC은 **성장하는 문서**. 구조/frontmatter/위치만 고정, 내용은 가변.
- 템플릿 SPEC에 "여기가 면담으로 채워질 자리" 마커 명시 → AI가 함부로 완성하지 않음.

### "여기서 더 고려할 점" (추가 설계 반영)
1. **LLM 코스트 격리**: 원칙팀은 LLM 0원. 브리핑팀만 LLM 사용. API키 없어도 mock 폴백으로 전체 데모 가능.
2. **시드/실데이터 모드 전환**: `SOURCE_MODE=seed|live` 로 한 줄 전환.
3. **Telegram 없이도 동작**: 미설정 시 `data/notifications/*.jsonl` 파일에 기록 → 로컬/CI 보장.
4. **대시보드 1페이지 데모**: 버릴 수 있는 임시 페이지. 원칙 스코어카드 + 브리핑 카드 + 최근 알림. 5초 polling.
5. **E2E 재현성**: `just demo <scenario>` 한 줄로 "시나리오 선택 → 두 팀 실행 → DB 저장 → 알림 → 대시보드 렌더" 완전 재현.
6. **도메인 문서 자동 생성**: 각 SPEC 구현 후 `docs/domain/<team>/<topic>.md` 생성. 비개발자용 설명서.
7. **팀별 CHANGELOG**: 진화팀이 추적할 변경 이력.
8. **SPEC 성장 포인트 마커**: `<!-- SPEC:INTERVIEW-SLOT role="judgment-logic" -->` 같은 마커로 `/spec-interview`가 채워야 할 위치 명시.

---

## 📚 Knowledge Layer — 팀별 전문 지식 내재화 (v0.5 핵심 추가)

### 문제 정의
사용자가 팀마다 다른 학습 자료를 공급하고 싶음:
- **매크로팀**: 신뢰하는 거시경제 전문가 분석 리포트
- **단기 테마 팀**: 유튜브 요약 자료들
- **기술적 분석팀**: 엘리엇 파동 해석, 매매 타점 인사이트

요구사항:
- 매번 자료 전체를 읽으면 **토큰 폭발** (자료가 MB 단위면 불가능)
- 같은 자료에 대해 **일관된 해석** 필요 (매번 달라지면 안 됨)
- 자료가 쌓여도 **잘 확장**되어야 함
- 컨셉: **GPT Projects / Gemini Gems / NotebookLM** 의 로컬 구현

### 해법: 2계층 지식 구조 (Canon + Reference RAG)

```
사용자가 자료 투입
    ↓
┌──────────────────────────────────────────────────┐
│ Layer 1: CANON (필수 기본 지식, 항상 주입)          │
│   - teams/<team>/knowledge/compiled.md            │
│   - 크기: 5-10K 토큰 (신중하게 엄선)                │
│   - 내용: 팀의 판단 프레임워크, 핵심 원칙, 주요 패턴 │
│   - 항상 system_prompt에 포함 → Prompt Caching 대상│
│   - 같은 자료 → 같은 프레임워크 → 일관된 해석 보장   │
└──────────────────────────────────────────────────┘
                    +
┌──────────────────────────────────────────────────┐
│ Layer 2: REFERENCE (참조 자료, RAG 검색)            │
│   - teams/<team>/knowledge/vector-index/          │
│   - 크기: 수백 KB ~ MB (무제한 확장)                │
│   - 내용: 유튜브 요약, 전문가 리포트, 사례 모음      │
│   - 벡터 DB (Chroma 로컬 파일) 에 청크 단위 저장     │
│   - 매 호출 시 현재 상황과 유사한 청크 3-5개 retrieval│
│   - 판단 근거에 "참고한 자료 id" 같이 기록 (trace 가능)│
└──────────────────────────────────────────────────┘
```

### Canon 생성 파이프라인 (Knowledge Compilation)

```
사용자 실행: just knowledge-compile macro-analysis

1. Raw 자료 수집
   teams/macro-analysis/knowledge/sources/
       ├── 전문가_리포트_*.pdf
       ├── 거시경제_원칙.md
       └── 역사적_사례.md

2. 텍스트 추출 (PDF → text, etc.)

3. LLM에게 요청:
   "이 자료들에서 매크로 분석팀이 항상 기억해야 할
    핵심 판단 프레임워크/원칙/패턴을 5-10K 토큰으로 압축하라.
    persona.md 관점에서 가장 유용한 형태로."

4. 결과물: teams/macro-analysis/knowledge/compiled.md

5. Canon 버전 올림 (v1 → v2) + manifest에 기록
```

- **재컴파일**: 자료가 추가되면 `just knowledge-compile <team>` 재실행
- **수동 편집 가능**: compiled.md는 사람이 읽고 수정 가능한 마크다운
- **버전 관리**: Git에 커밋. 프레임워크 변천사 추적.

### Reference RAG 파이프라인 (Ingestion)

```
사용자 실행: just knowledge-ingest macro-analysis

입력 소스:
  teams/<team>/knowledge/sources/
      ├── *.md, *.pdf, *.txt
      └── youtube/urls.txt   (YouTube URL 목록)

파이프라인:
  1. Extract:  PDF→text (pypdf), YouTube→자막 (youtube-transcript-api)
  2. Chunk:    RecursiveCharacterTextSplitter (500-1000 토큰)
               + 메타데이터 (source, date, tags)
  3. Embed:    OpenAI text-embedding-3-small ($0.02/1M) 또는
               로컬 sentence-transformers/all-MiniLM-L6-v2 (무료)
  4. Store:    Chroma DB (teams/<team>/knowledge/vector-index/)
  5. Index:    manifest.yaml 갱신 (자료 목록 + 청크 수 + 업데이트 시각)
```

### Runtime Retrieval (매 LLM 호출 시)

```
매크로팀 호출 흐름:

1. [Canon] compiled.md 항상 로드 (~8K 토큰)     → 캐시 히트
2. [Memory] 최근 14일 요약 로드 (~3K 토큰)       → 부분 캐시
3. [Query] 현재 상황 요약: "금리 4.2% VIX 18..." → 벡터로 변환
4. [RAG] Chroma 에서 유사 청크 Top-3 검색 (~2K 토큰)
5. [Compose] system_prompt 조립
6. [LLM] Anthropic API 호출 (Prompt Caching 적용)
7. [Trace] 응답에 retrieved chunk의 source_id 기록
           → "이 판단은 '김XX 거시리포트 2026-03'에서 영향받음"
```

### 토큰 비용 예시 (매크로팀 1회 호출)

```
system_prompt (캐시 대상):
  persona.md              ~1,000  tokens
  canon (compiled)        ~8,000  tokens
  memory (14일 요약)       ~3,000  tokens
  ────────────────────────────────
  소계                    ~12,000 tokens  → 캐시되어 10% 비용만
                                             = 실효 ~1,200 tokens

system_prompt (매번 다름):
  retrieved chunks (3개)   ~2,000 tokens  → 실비

user_prompt:
  오늘의 데이터            ~1,000 tokens

output:                    ~500 tokens

실효 비용 (Sonnet 4):
  입력: ~4,200 × $3/1M  = $0.013
  출력: ~500  × $15/1M  = $0.008
  ─────────────────────
  합계: $0.021 / 1회

월 운용 (매일 매크로 1 + 종목 10 × 기술 1 + 오케스트 1 = 12회):
  $0.021 × 12 × 30 = $7.6 / 월 (~10,000원)
```

**이게 "GPT Projects + NotebookLM + Memory"를 다 갖춘 운용 비용.**

### 멱등성과의 결합
- `input_hash` 계산에 **`canon_version`**과 **`retrieved_chunk_ids`**를 포함
- Canon 갱신 시 → hash 변동 → 재판단 트리거
- 같은 상황 + 같은 지식 버전 → 같은 판단 보장

### 팀 manifest에 Knowledge 선언

```yaml
# teams/<team-id>/manifest.yaml 에 추가
knowledge:
  enabled: true
  canon:
    version: 3
    path: knowledge/compiled.md
    last_compiled: "2026-04-10"
    token_budget: 10000
  reference:
    enabled: true
    index_path: knowledge/vector-index/
    chunk_size: 800
    chunk_overlap: 100
    retrieval_top_k: 3
    embedding_model: text-embedding-3-small   # or local
    sources:                                   # manifest가 자동 스캔
      - type: pdf
        path: knowledge/sources/expert-report-2026-04.pdf
        tags: [macro, 2026Q2]
      - type: youtube
        url: https://youtube.com/watch?v=...
        title: "거시경제 긴급 분석 2026-03"
        tags: [macro, crisis]
      - type: markdown
        path: knowledge/sources/elliott-wave-rules.md
        tags: [technical, wave]
```

→ `just knowledge-status <team>` 으로 현재 상태 확인 (자료 개수, 청크 수, Canon 버전, 마지막 업데이트)

### NotebookLM 같은 탐색 기능 (선택)
- `just knowledge-browse <team>` — CLI로 청크 검색 + 프리뷰
- 나중에 webapp에 Knowledge Viewer 페이지 추가 (자료별 출처/태그/신뢰도/인용 통계)
- "이 판단에 가장 많이 인용된 자료 Top 10" 같은 메타 분석 가능

### 도구 선택 (추천)

| 역할 | 추천 | 이유 |
|------|------|------|
| Vector DB | **Chroma** | 파이썬 네이티브, 로컬 파일 기반, 무설치, 초보자 친화 |
| Embedding | **OpenAI text-embedding-3-small** | $0.02/1M 토큰으로 초저렴. 품질 우수. |
| Embedding (오프라인) | **sentence-transformers/all-MiniLM-L6-v2** | 완전 로컬, 무료, 성능 충분 |
| Chunker | **langchain RecursiveCharacterTextSplitter** | 성숙함, 설정 간단 |
| YouTube 자막 | **youtube-transcript-api** | API 키 불필요, 무료 |
| PDF 추출 | **pypdf** (또는 pymupdf) | 순수 파이썬, 크로스플랫폼 |

### `core/knowledge/` 모듈

```
core/knowledge/
├── ingest.py         # 자료 수집 (PDF/YouTube/MD) + 텍스트 추출
├── chunk.py          # 청킹 전략
├── embed.py          # Embedding 생성 (원격/로컬 선택)
├── store.py          # Chroma DB 저장/쿼리
├── retrieve.py       # 유사도 검색 + 다양성/신선도 필터
├── compile.py        # Canon 자동 생성 (LLM 활용)
└── manifest.py       # 팀별 자료 카탈로그 관리
```

### 사용자 워크플로 (NotebookLM 느낌)

```
# 1. 자료 투입
사용자: teams/macro-analysis/knowledge/sources/ 에 PDF 드롭

# 2. 인덱싱
$ just knowledge-ingest macro-analysis
> 📂 3개 신규 자료 감지
> 🔪 127개 청크 생성
> 🧠 임베딩 중... (14초)
> 💾 vector-index 갱신 완료

# 3. (선택) Canon 재컴파일
$ just knowledge-compile macro-analysis
> 🤖 LLM으로 원칙 추출 중...
> 📝 compiled.md v4 생성 (9,823 토큰)

# 4. 자동 반영
서버가 config reload 감지 → 다음 판단부터 새 지식 적용
```

### 서비스적 가치
- **팀이 "전문가처럼" 성장함**: 사용자가 믿는 자료를 넣을수록 해당 관점으로 판단.
- **판단 근거 투명성**: "이 판단은 ○○ 리포트에서 왔다" 자동 추적.
- **개인화**: GPT Projects와 달리 **완전 로컬, 완전 프라이버시**.
- **버저닝**: Canon 버전이 올라가면 "AI의 사고 체계가 진화"하는 느낌 (진화팀과 연동).

### 기술적 가치
- **토큰 효율**: Canon 캐시 + 선별 retrieval로 매번 MB 단위 자료 보내지 않음.
- **일관성**: Canon 고정 → 같은 프레임워크 보장.
- **확장성**: 자료 수에 제한 없음 (벡터 DB는 수백만 청크 OK).
- **오프라인**: 로컬 Chroma + 로컬 임베딩 옵션으로 인터넷 없이도 동작.

---

## 🧠 Memory Layer — LLM 판단의 맥락 연속성 (v0.3 핵심 추가)

### 문제 정의
- LLM은 **완전 stateless**. 매 호출마다 기억이 0.
- 서버가 꺼졌다 켜지면 **프로세스 메모리는 휘발**.
- 주식/경제 판단은 **시계열 맥락**이 생명. "어제 조정장, 오늘 상승장"의 연속성이 중요.
- 같은 입력 + 같은 컨텍스트 = **같은 판단** (멱등성) 이어야 백테스트와 복기 가능.
- 계속 쌓이면 무한 증가 → **주기적 롤업 + 정리** 필요.

### 설계 원칙: "LLM에게 기억을 파일/DB로 외장(外裝)한다"

```
LLM (뇌, stateless)     ←  매 호출마다
      ↑                     context 주입
      │
  Memory Layer
  ├── 원본 (hot):   최근 1-2주 상세 판단 (narrative 포함)
  ├── 요약 (warm):  월별·주별 압축 롤업
  └── 장기 (cold):  분기·연별 하이라이트만
      ↑
      │  매일/매주/매월 자동 롤업 (서버 스케줄러)
      │
  team_outputs (팀 판단 저장)
```

### 3계층 메모리 구조

| 계층 | 보관 기간(기본) | 내용 | 저장소 |
|------|----------|------|--------|
| **Hot (원본)** | 180일 | 팀별 일일 판단 원본 + LLM 생성 narrative | `team_memory` 테이블 + `data/memory/<team>/YYYY-MM-DD.md` |
| **Warm (주/월 요약)** | 2년 | 주간/월간 롤업 요약 | `memory_rollup` 테이블 |
| **Cold (장기)** | 무제한 | 분기·연간 하이라이트, 주요 이벤트만 | `memory_rollup` 테이블 (periodicity=quarterly/yearly) |

- **180일 지난 원본**: `narrative` 필드만 비움 (상세 사유 삭제). 정형 데이터(verdict/confidence)는 보존.
- 모든 보관 기간은 `config/runtime.yaml` 에서 조절 가능.

### DB 스키마 추가

```sql
-- 팀별 판단 원본 메모리
CREATE TABLE team_memory (
    team_id TEXT,
    date TEXT,                 -- YYYY-MM-DD (KST 기준)
    target TEXT,               -- 종목 코드 또는 'global'
    input_hash TEXT,           -- ★ 멱등성 키 (같은 hash → 같은 판단)
    verdict TEXT,
    confidence INTEGER,
    reasons_json TEXT,
    narrative TEXT,            -- LLM이 쓴 서술 (180일 후 NULL로)
    data_json TEXT,
    model TEXT,                -- 어떤 LLM이 판단했는지
    contract_version TEXT,
    created_at TEXT,
    PRIMARY KEY (team_id, date, target, input_hash)
);

-- 요약 롤업
CREATE TABLE memory_rollup (
    team_id TEXT,
    period_type TEXT,          -- daily | weekly | monthly | quarterly | yearly
    period_key TEXT,           -- '2026-04-16' | '2026-W16' | '2026-04' | '2026-Q2'
    summary_md TEXT,           -- 마크다운 요약
    key_events_json TEXT,      -- 주요 이벤트 배열
    metrics_json TEXT,         -- 정량 지표 (수익률/정확도 등)
    created_at TEXT,
    PRIMARY KEY (team_id, period_type, period_key)
);

-- LLM 호출 캐시 (멱등성 + 비용 절감)
CREATE TABLE llm_call_cache (
    input_hash TEXT PRIMARY KEY,
    model TEXT,
    response_json TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    cost_usd REAL,
    created_at TEXT,
    ttl_days INTEGER DEFAULT 7  -- 단기 TTL. 하루 1회 호출은 캐시 히트.
);
```

### 멱등성 보장 메커니즘

```
input_hash = sha256(
    canonicalize(input_data) +
    canonicalize(context_snapshot) +
    model_id +
    contract_version
)
```

- 동일 `input_hash` → **LLM 호출 스킵, 캐시 반환** (`llm_call_cache`)
- 또는 `team_memory` 의 기존 판단 반환
- 강제 재생성: `?force_rebuild=true` 플래그

### 컨텍스트 주입 파이프라인 (매 LLM 호출 시)

```
┌─────────────────────────────────────────┐
│ 1. 메모리 로더 (core/memory/loader.py)    │
│    - 최근 14일 team_memory 조회          │
│    - 최근 12주 weekly_rollup 조회        │
│    - 최근 6개월 monthly_rollup 조회      │
│    - 현재 상황 관련 장기 이벤트 조회       │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│ 2. 토큰 예산 추리기 (trim)                │
│    - 기본 4000 토큰 한도                  │
│    - 최근 것 우선, 오래될수록 압축         │
│    - 팀별 context_budget_tokens 조절     │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│ 3. System Prompt 조립 (composer.py)      │
│    = persona.md                          │
│    + knowledge 요약                      │
│    + 최근 맥락 (위에서 추린 것)            │
│    + 응답 규칙 (JSON 포맷)                │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│ 4. Anthropic Prompt Caching 활용         │
│    - system 부분은 캐시되어 90% 할인       │
│    - user 부분만 실비 결제                 │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│ 5. 결과 저장 (team_memory + cache)        │
└─────────────────────────────────────────┘
```

### 자동 롤업 스케줄 (서버 내장)

| 작업 | 주기 | 내용 |
|------|------|------|
| `daily_rollup` | 매일 23:50 KST | 오늘의 팀별 판단들을 하루 요약으로 압축 |
| `weekly_rollup` | 일요일 23:55 | 지난주 7일을 주간 요약으로 압축 |
| `monthly_rollup` | 매월 말일 23:58 | 지난달을 월간 요약으로 압축 |
| `quarterly_rollup` | 분기 마지막 주 | 분기 요약 |
| `memory_cleanup` | 매월 1일 | 보관기간 경과 원본 narrative 제거, 오래된 캐시 정리 |

### 팀 manifest 메모리 선언

```yaml
# teams/<team-id>/manifest.yaml 에 추가
memory:
  enabled: true
  retention:
    raw_days: 180         # team_memory 원본 narrative 보관일
    daily_days: 365       # daily rollup
    weekly_days: 730      # weekly rollup
    monthly_days: null    # null = 무제한
  context_budget_tokens: 4000
  rollup:
    daily_template: templates/daily_rollup.md
    weekly_template: templates/weekly_rollup.md
  idempotency:
    enabled: true
    cache_ttl_days: 7
```

### 서버 시작 시 — 3단계 맥락 복원

```
서버 ON
  ↓
[1] Gap Filler (server/schedulers/jobs/gap_filler.py)
    서버 꺼진 기간의 외부 데이터 소급 수집 (KIS, FRED)
  ↓
[2] Memory Warm-up
    최근 30일 team_memory + 최근 12주 rollup 을 메모리 캐시에 프리로드
  ↓
[3] Retroactive Analysis (선택)
    갭 기간의 팀 판단을 소급 생성 → 맥락 끊김 방지
  ↓
정상 스케줄 실행 시작
```

### 서비스적 가치 (사용자 관점)
- **투자 일지 효과**: narrative 축적 = "AI가 왜 그렇게 생각했는가"의 기록. 1년 후 복기 가능.
- **시계열 일관성**: 어제 "조정장" → 오늘 "상승장" 전환 시, LLM이 context에서 어제 판단을 보고 **"어제와 달라진 이유"를 자동 설명** 하게 됨.
- **백테스트**: `team_memory` 히스토리를 재생하여 과거 시점 판단 재현 가능.
- **사용자의 신뢰**: 랜덤하지 않은 일관된 판단 → 투자 의사결정 보조로서의 신뢰.

### 기술적 가치
- **멱등성**: 같은 input_hash → 같은 결과. 테스트 가능, 재현 가능.
- **비용 제어**: Prompt caching + LLM call cache 로 90%+ 토큰 절감.
- **Graceful degradation**: 메모리 로드 실패해도 최소 컨텍스트로 동작.
- **Cleanup 자동화**: 무한 증가 방지. 운영 부담 없음.

### `core/memory/` 모듈 구조 (추가 산출물)

```
core/memory/
├── loader.py         # 계층별 컨텍스트 조회 + 토큰 예산 내 추리기
├── composer.py       # system_prompt 조립 (persona + context + rules)
├── rollup.py         # daily/weekly/monthly 롤업 생성 (LLM 또는 템플릿)
├── cleanup.py        # 보관기간 경과 데이터 pruning
├── cache.py          # LLM 호출 결과 캐시 (멱등성)
└── hasher.py         # input_hash 정규화/계산
```

---

## ⚙️ 통합 Config + 동적 리로드 (사용자 요청 반영)

### 원칙: 하드코딩 금지, 설정 변경 시 프로세스 재시작 없이 반영

### 계층 구조 (덮어쓰기 우선순위: 위 > 아래)
1. **환경변수 / `.env`** — 시크릿 (API 키, DB 경로)
2. **`config/runtime.yaml`** — 동적 운영 설정 (스케줄, 알림 채널, 플래그, 임계값)
3. **`config/defaults.yaml`** — 안전한 기본값 (코드와 함께 커밋)

### `core/config/` 모듈
- `pydantic-settings` 로 타입 안전 설정 객체 제공
- `watchdog` 로 `config/runtime.yaml` 파일 변경 감지
- **변경 감지 시 Config 객체 핫 스왑** → 다음 스케줄/요청부터 자동 반영
- FastAPI 엔드포인트 `POST /api/config/reload` 로 수동 트리거도 지원
- 무효한 설정 반영 시 **이전 설정 유지 + 에러 로그** (안전 실패)

### 예시 `config/runtime.yaml`
```yaml
telegram:
  enabled: true
  chat_id: "@user_channel"     # .env 치환 지원: ${TELEGRAM_CHAT_ID}
  formats:
    principles: "⚠️ {message}"
    daily-briefing: "📊 {message}"
scheduler:
  daily_macro:
    cron: "30 8 * * *"           # 08:30 KST
  watchlist_refresh:
    interval_minutes: 60
llm:
  primary: claude-sonnet-4
  crosscheck_enabled: false
  crosscheck_targets: []
teams:
  principles:
    enabled: true
    thresholds:
      total_weight: 80
      single_stock: 15
      trading_weight: 20
  daily-briefing:
    enabled: true
    model_override: null          # null이면 llm.primary 사용
```

### 확장성 보장
- 새 팀 추가 시 `teams.<id>:` 섹션만 추가하면 끝.
- 새 MCP 서버, 배치 작업도 동일 방식으로 플러그인.
- 코드는 `config.teams["principles"].thresholds.total_weight` 처럼 타입 안전 접근.

---

## 🚀 구현 로드맵 (토대 구축 단계)

### Phase 0: 설계 확정 (지금 ← 완료)
- 이 플랜 v0.2 크로스 검증 완료
- 4가지 핵심 결정 확정 (실행방식/범위/언어/넘버링)

### Phase 1: 최상위 스캐폴딩
**산출물**:
- 폴더 구조 전체 (빈 폴더 + placeholder)
- 루트 문서: `README.md`, `CLAUDE.md`
- 규약 문서: `docs/STRUCTURE.md`, `docs/WORKFLOW.md`, `docs/CONTRACTS.md`
- 템플릿: `teams/_template/`, `mcp-servers/_template/`, `batch/_template/`
- 설정: `.env.example`, `.gitattributes`, `.gitignore`, `pyproject.toml`, `justfile`

### Phase 2: 핵심 인프라 (`core/` + `scripts/`)
**산출물**:
- `core/db/schema.sql` + `core/db/connection.py` — SQLite, ON CONFLICT REPLACE
- `core/contracts/team_output.py` — StandardOutput Pydantic v2 모델
- `core/contracts/spec_frontmatter.py` — SPEC frontmatter 파서
- `core/llm/client.py` — Anthropic 기본, 멀티 공급자 인터페이스 (결정 1에 따라 초기엔 Anthropic만 구현)
- `core/config/env.py` — dotenv 로더, 타입 안전한 설정
- `core/logging/` — 구조화 로깅
- `core/scheduler/` — APScheduler 래퍼
- `core/notification/` — Telegram + 파일 fallback
- `scripts/scaffold.py` — 팀/MCP/배치/SPEC 스캐폴더
- `scripts/validate.py` — 구조 정합성 검증
- `scripts/trace.py` — SPEC↔코드 양방향 매핑
- `scripts/generate_domain_doc.py` — SPEC + 코드 → 도메인 문서 생성

### Phase 3-A: 첫 팀 ① — 원칙 관리팀 (규칙 기반)
**산출물**:
- `teams/principles/` 표준 레이아웃 100% 준수
- `manifest.yaml` (runtime: rule), `CLAUDE.md`
- `specs/PRINCIPLE-001-seven-commandments-checker.md` — **뼈대만** (frontmatter + 목적 + 입출력 + SPEC:INTERVIEW-SLOT 마커)
- `src/agent.py` — 표준 Agent 클래스 (StandardOutput 반환)
- `src/commandments/` — 7계명 각각 개별 파일
- `tests/test_agent.py`, `tests/test_commandments.py`
- `data/seed/mock_portfolio.json` 4개 시나리오
- Telegram 알림 포맷 (`config/runtime.yaml`의 formats.principles 사용)
- `docs/domain/principles/seven-commandments.md` 자동 생성

### Phase 3-B: 첫 팀 ② — 데일리 브리핑 팀 (LLM 기반)
**산출물**:
- `teams/daily-briefing/` 표준 레이아웃
- `manifest.yaml` (runtime: llm, depends_on: [DB:team_outputs])
- `persona.md` — LLM system prompt 주입용 페르소나
- `specs/BRIEFING-001-daily-summary.md` — 뼈대만 (+INTERVIEW-SLOT)
- `src/agent.py` — `core.llm.client` 호출, 응답 JSON 파싱
- `src/prompts/briefing.md` — 프롬프트 템플릿
- `tests/test_agent.py` — mock LLM 사용
- API 키 미설정 시 mock 응답 폴백
- `docs/domain/daily-briefing/today-summary.md` 자동 생성

### Phase 3-C: 오케스트레이터 (lite)
**산출물**:
- `teams/orchestrator/` 스캐폴드
- `src/agent.py` — registry 스캔 → 활성 팀 필터 → `asyncio.gather(*[team.run() for team in teams])`
- 실행 순서/의존성 처리: manifest의 `depends_on`에 따라 순차/병렬 결정
- `team_outputs` 테이블에 `run_id` 로 묶어 저장

### Phase 4: `server/` 런타임 + 통합 Config + 1페이지 데모
**산출물**:
- `server/main.py` — uvicorn 진입. FastAPI + APScheduler + config watchdog
- `server/schedulers/loader.py` — 팀 manifest의 `schedule:` 읽어 APScheduler에 등록
- `server/schedulers/jobs/backup.py`, `gap_filler.py` — 인프라성 작업
- `server/api/config.py` — `GET/POST /api/config` (조회 + 리로드)
- `server/api/teams.py` — `GET /api/teams` (registry), `GET /api/teams/<id>/latest`
- `server/api/demo.py` — `POST /api/demo/run?scenario=over-allocation`
- `server/api/telegram.py` — Telegram webhook 수신 (명령 처리)
- `server/orchestration/runner.py` — `asyncio.gather` 병렬 실행
- `webapp/` Next.js 스캐폴딩 — **1페이지만** (`app/page.tsx`)
  - 원칙 스코어카드 + 브리핑 카드 + 최근 알림 리스트
  - server/api 호출, 5초 SWR polling
  - "버려지는 데모" 주석 명시 (Wave 6에서 정식 웹앱으로 대체 예정)
- E2E: `just demo over-allocation` → CLI 출력 + Telegram 메시지 + 대시보드 갱신 모두 확인
- E2E: `config/runtime.yaml` 수정 → 자동 감지 → 다음 호출부터 반영 확인

### Phase 5: 검증 & 문서화 마무리
- `just validate` 통과 (모든 팀/스펙/레지스트리 정합성)
- `just trace` → `docs/traceability.md` 생성
- `just domain-doc` → `docs/domain/principles/*.md` 생성
- `README.md` 최종본 — "새 팀 추가하는 법" 튜토리얼 포함

이후는 기존 아키텍처 문서의 Wave 2~6 로드맵을 따름. **토대가 이미 있으므로 모든 추가 기능은 "삽입"만으로 완성**.

---

## ✅ 검증 방법 (end-to-end)

### 시나리오 1: 확장성 검증 — "빈 팀 하나를 1분 안에 추가할 수 있는가?"
- `just new-team sentiment-analysis --runtime llm` 실행
- `teams/sentiment-analysis/` 생성, `teams/registry.yaml` 자동 갱신 확인
- `config/runtime.yaml` 에 `teams.sentiment-analysis.enabled: false` 자동 추가
- `just validate` 통과

### 시나리오 2: SPEC → 코드 정확성 — "AI가 올바른 위치에 만드는가?"
- 새 SPEC 파일을 frontmatter(generates, team)와 함께 작성
- Claude Code에게 "이 SPEC 구현해줘" 지시
- frontmatter `generates` 경로에 파일 생성 확인
- `just validate` 통과
- `just trace` 로 SPEC↔코드 매핑 자동 갱신 확인

### 시나리오 3: SPEC 성장성 — "/spec-interview로 살 붙일 수 있는가?"
- 뼈대 SPEC의 `INTERVIEW-SLOT` 마커 확인
- `/spec-interview` 명령 실행 → 면담 진행
- 마커 위치에 내용 추가되고 AI는 **다른 부분을 건드리지 않음**

### 시나리오 4: 풀사이클 데모 (두 팀)
- `just demo over-allocation` 실행
- 원칙팀 → 비중 초과 감지 → `team_outputs` 저장 → Telegram "⚠️" 알림 (또는 파일 폴백)
- 데일리 브리핑팀 → 원칙팀 결과 읽음 → LLM 호출 (또는 mock 폴백) → "📊" 브리핑 발송
- 대시보드 새로고침 시 두 카드 모두 반영

### 시나리오 5: 동적 Config 리로드
- 서버 구동 중 `config/runtime.yaml` 의 `telegram.formats.principles` 수정 → 저장
- 다음 알림부터 새 포맷 적용 (프로세스 재시작 없음)
- 잘못된 YAML 저장 → 이전 설정 유지 + 에러 로그

### 시나리오 6: 도메인 문서 자동 생성
- `just domain-doc PRINCIPLE-001` 실행
- `docs/domain/principles/seven-commandments.md` 생성
- 비개발자가 읽고 "이 기능 뭐 하는지" 설명 가능

### 시나리오 7: 비개발자 네비게이션
- "새 팀을 추가하려면?" — README → WORKFLOW.md 로 경로 확인 가능
- "데이터 저장 위치?" — STRUCTURE.md 에 명시
- "팀 간 소통 방식?" — CONTRACTS.md 에 명시

---

## ✅ 확정된 설계 결정 (크로스 검증 완료)

### 결정 1: 실행 방식 = **단일 프로세스 + 비동기 + 스케줄러 (서버 상주)**
- **런타임**: Python `asyncio` 기반 단일 프로세스. 오케스트레이터가 각 팀의 `agent.run()`을 `await` 또는 `asyncio.gather`로 병렬 호출.
- **자동화**: `APScheduler`로 08:30 KST 일일 배치, 1시간 주기 리프레시 등 자동 실행. 프로세스가 서버처럼 상주하며 스케줄에 따라 작업 트리거.
- **토큰 효율**: LLM API 호출은 팀 단위로 1회, 결과는 DB 캐시. 같은 날 재실행 시 캐시 활용.
- **Claude Code subagent는 개발 시에만**: `/spec-interview`, `/evolve-review` 같은 **개발 워크플로**에만 사용. 런타임에는 사용하지 않음.
- **외부 호출 인터페이스**: FastAPI 서버가 백엔드로 상주. webapp에서 `fetch('/api/teams/macro/latest')` 호출 가능. Telegram webhook도 이 서버가 수신.

**→ 구조**: 1 Python 프로세스 = FastAPI + APScheduler + asyncio 병렬 팀 실행. 서버 1개만 띄우면 끝.

### 결정 2: 스캐폴딩 범위 = **전체 구조 + 첫 팀 1개 완전 작동**
- 최상위 폴더 전체 + core/ + scripts/ + 문서 전체
- **첫 팀: `principles` (원칙 관리팀)** — 아래 "첫 팀 선정" 섹션 참조
- 첫 팀에서 **End-to-End 전체 사이클**이 작동:
  `SPEC 작성 → 코드 생성 → 도메인 문서 자동 생성 → DB 저장 → Telegram 알림 → 대시보드 표시 → validate/trace 통과`

### 결정 3: MCP 서버 언어 = **Python 통일 + webapp만 TypeScript**
- **추천 이유** (코틀린 개발자 관점 반영):
  - 팀 로직은 **Python** 이 절대적 우위: pandas, pandas-ta, yfinance, fredapi, anthropic SDK, 한투 API 파이썬 래퍼 모두 성숙.
  - **단일 언어 모노레포** = 의존성 관리 1개(uv), 테스트 러너 1개(pytest), 타입 시스템 1개(Python typing + Pydantic).
  - 코틀린에 익숙한 분에게 Python은 문법이 경쾌하고 타입힌트가 코틀린의 타입 시스템과 유사. 바이브 코딩에 최적.
  - JVM의 무거움 회피. 스케줄러/배치 상주 프로세스는 Python이 가벼움.
  - **웹앱 전용**: Next.js는 필수적으로 TypeScript. 이것만 예외.
- **구조**: `Python 모노레포 (core + teams + mcp + batch + scripts)` + `Next.js webapp (TypeScript)` + 두 레이어는 REST API로만 통신.

### 결정 4: SPEC 넘버링 = **팀 프리픽스 + 순번** + **도메인 문서 자동 생성**
- **파일명 규약**: `<TEAM>-<NNN>-<slug>.md`
  - 예: `PRINCIPLE-001-seven-commandments-checker.md`
  - 예: `MACRO-001-market-state-judge.md`
  - 전역 SPEC: `GLOBAL-001-*`, 계약: `CONTRACT-001-*`, 인프라: `INFRA-001-*`
- **teams/<team-id>/specs/** 에 저장 (전역만 `docs/specs/`)
- **★ 도메인 문서 자동 생성 (추가 요청사항)**:
  - SPEC 완성 → 코드 구현 → 테스트 통과 후, **`docs/domain/<team>/<topic>.md`** 자동 생성
  - 도메인 문서는 **사용자(비개발자)가 읽는 결과물 설명서**: "이 기능이 무엇을 하는가, 어떻게 쓰는가, 언제 알림이 오는가"
  - `scripts/generate_domain_doc.py` 가 SPEC + 코드 docstring + 테스트 케이스를 조합해서 생성
  - `just domain-doc <SPEC_ID>` 한 줄로 실행

**→ SDD 완전 사이클**: `/spec-interview` → SPEC md → 코드 → 테스트 → **도메인 문서** → validate → 커밋

---

## 🔑 핵심 파일 (구현 대상)

### Phase 1-2 (토대)
| 파일 | 역할 |
|------|------|
| `README.md` | 프로젝트 입구 (비개발자용) |
| `CLAUDE.md` | AI 입구 (루트 오케스트레이터) |
| `docs/STRUCTURE.md` | 폴더 규약 원천 |
| `docs/WORKFLOW.md` | SDD 사이클 1페이지 |
| `docs/CONTRACTS.md` | 메시지/DB 계약 |
| `teams/_template/` | 팀 원본 (CLAUDE.md, manifest.yaml, src/agent.py 포함) |
| `mcp-servers/_template/` | MCP 원본 |
| `batch/_template/` | 배치 원본 |
| `scripts/scaffold.py` | 타입별 자동 생성 |
| `scripts/validate.py` | 구조 정합성 |
| `scripts/trace.py` | SPEC↔코드 매핑 |
| `scripts/generate_domain_doc.py` | 도메인 문서 자동 생성 |
| `core/contracts/team_output.py` | StandardOutput (Pydantic) |
| `core/contracts/spec_frontmatter.py` | SPEC 메타 파서 |
| `core/db/schema.sql` | 전체 DB 스키마 |
| `core/db/connection.py` | SQLite 연결 |
| `core/config/env.py` | 환경변수 로더 |
| `core/llm/client.py` | LLM 통합 (Anthropic 기본) |
| `core/notification/telegram.py` | 알림 (+파일 fallback) |
| `core/scheduler/` | APScheduler 래퍼 |
| `.env.example`, `.gitignore`, `.gitattributes`, `pyproject.toml`, `justfile` | 환경 |

### Phase 3 (첫 두 팀 + 오케스트레이터 lite)
| 파일 | 역할 |
|------|------|
| `teams/principles/manifest.yaml` | 규칙 팀 메타 (runtime: rule) |
| `teams/principles/CLAUDE.md` | 팀 AI 컨텍스트 |
| `teams/principles/specs/PRINCIPLE-001-seven-commandments-checker.md` | 뼈대 SPEC + INTERVIEW-SLOT 마커 |
| `teams/principles/src/agent.py` | 표준 Agent 구현 |
| `teams/principles/src/commandments/*.py` | 7계명 각각 |
| `teams/principles/tests/` | 단위/계약 테스트 |
| `teams/daily-briefing/manifest.yaml` | LLM 팀 메타 (runtime: llm) |
| `teams/daily-briefing/persona.md` | LLM system prompt 주입 페르소나 |
| `teams/daily-briefing/specs/BRIEFING-001-daily-summary.md` | 뼈대 SPEC |
| `teams/daily-briefing/src/agent.py` | LLM 호출 에이전트 |
| `teams/daily-briefing/src/prompts/briefing.md` | 프롬프트 템플릿 |
| `teams/orchestrator/src/agent.py` | registry 스캔 + asyncio.gather 병렬 실행 |
| `data/seed/mock_portfolio.json` | 4개 시나리오 데이터 |
| `data/seed/mock_macro.json` | 브리핑용 시드 매크로 |
| `config/defaults.yaml` | 안전한 기본값 |
| `config/runtime.yaml` | 동적 운영 설정 (--reload 대상) |
| `docs/domain/principles/*.md` | 자동 생성 도메인 문서 |
| `docs/domain/daily-briefing/*.md` | 자동 생성 도메인 문서 |

### Phase 4 (server/ 런타임 + 데모 1페이지)
| 파일 | 역할 |
|------|------|
| `server/main.py` | uvicorn 진입, FastAPI + APScheduler |
| `server/schedulers/loader.py` | 팀 schedule 읽어 등록 |
| `server/schedulers/jobs/backup.py` | 인프라: DB 백업 |
| `server/schedulers/jobs/gap_filler.py` | 인프라: 갭 필링 |
| `server/api/teams.py` | 팀 registry/latest API |
| `server/api/config.py` | 설정 조회/리로드 API |
| `server/api/demo.py` | 시나리오 트리거 |
| `server/api/telegram.py` | Telegram webhook 수신 |
| `server/orchestration/runner.py` | asyncio.gather 병렬 실행 |
| `core/notification/telegram.py` | 알림 발송 (config 포맷) |
| `core/notification/file_fallback.py` | Telegram 미설정 시 파일 기록 |
| `webapp/src/app/page.tsx` | 1페이지 데모 (버려도 됨) |
| `webapp/src/components/PrincipleCard.tsx` | 원칙 스코어카드 |
| `webapp/src/components/BriefingCard.tsx` | 브리핑 카드 |
| `webapp/src/components/AlertList.tsx` | 최근 알림 |

---

## 📎 참고 — 기존 문서와의 관계

이 설계는 기존 6개 문서의 상위 뼈대 역할:
- `docs/stock-advisor-architecture-guide.md` — 전체 전략/Wave 로드맵
- `docs/stock-advisor-ux-spec.md` — webapp 부분의 입력
- `docs/llm-runtime-architecture.md` — core/llm/ 설계의 입력
- `docs/CLAUDE-ko.md` — 루트 CLAUDE.md 초안의 입력
- `docs/team-claude-md-example-ko.md` — teams/_template/CLAUDE.md의 입력
- `docs/SPEC-003-example-ko.md` — SPEC frontmatter 규약 적용 대상

**충돌 없음. 이 토대는 기존 설계를 더 엄격/확장 가능하게 만드는 것.**
