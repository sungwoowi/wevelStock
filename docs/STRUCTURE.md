# 📐 STRUCTURE.md — 폴더 규약의 원천

> **이 문서가 프로젝트의 모든 폴더 규칙의 기준입니다.**
> 어디에 파일을 둘지, 어떤 이름을 쓸지 결정할 때 항상 이 문서를 참조합니다.

---

## 🎯 5가지 설계 원칙 (북극성)

1. **자명성(Self-evidence)** — 폴더 이름만 봐도 역할이 드러나야 한다.
2. **대칭성(Symmetry)** — 모든 파이프라인·컴포넌트는 동일한 내부 구조를 가진다.
3. **격리(Isolation)** — 파이프라인은 다른 파이프라인의 코드를 import 하지 않는다. 공용은 `collectors/`·`checkers/`·DB·계약으로만 통신.
4. **추적성(Traceability)** — SPEC ↔ 코드 ↔ 테스트가 양방향으로 연결된다.
5. **검증성(Verifiability)** — `just validate` 하나로 모든 규약이 자동 검증된다.

---

## 🏛️ 최상위 폴더

| 폴더 | 역할 | 특징 |
|---|---|---|
| `pipelines/` | 🔀 시간대별 AI 판단 파이프라인 | 각 파이프라인이 `manifest.yaml`에 stages + schedule 선언 (Layer 5 출력 채널의 한 형태) |
| `agents/` | 🧠 페르소나 보관소 | 분석가(`analysts/`, 9) · 전략가(`strategists/`, 2+ track) · 계좌관리자(`account_manager/`, 1+ N 가변) · 회고분석가(`retrospect/`, N 가변). 5-Layer 모델 Layer 2~5. M3 부터 점진 신설 |
| `knowledge/` | 📚 학습부 (Layer 1) | `canon/<learning_dept>/<category>/` 9 폴더 × 36 카테고리 = 분석가들이 읽는 자료 |
| `collectors/` | 📥 공용 데이터 수집 라이브러리 | 파이프라인 간 import 허용되는 무상태 함수 모듈 |
| `checkers/` | ✅ 공용 규칙/원칙 체커 | 7계명, 손절 체크 등 순수 로직 |
| `connectors/` | 🔌 외부 API 커넥터 | KIS / yfinance 등 외부 시스템 어댑터 |
| `mcp-servers/` | 🔌 MCP 프로토콜 서버 | 별도 프로세스 |
| `server/` | 🖥️ 상주 런타임 | FastAPI + APScheduler + 텔레그램 봇 |
| `webapp/` | 🌐 UI (Next.js) | `server/api`를 HTTP로 호출만 함 |
| `core/` | 🧱 공유 라이브러리 | contracts / db / llm / memory / knowledge / config / logging / notification |
| `docs/` | 📘 사람용 문서 | 규약, SPEC, 도메인 문서 |

보조 폴더:
- `config/` — 운영 설정 (동적 리로드 대상)
- `data/` — 런타임 데이터 (gitignore)
- `scripts/` — 개발·운용 도구
- `tests/` — 레포 전역 테스트 (파이프라인 단위는 각 파이프라인 폴더)
- `.claude/` — Claude Code 설정

**규칙**: 하나의 모듈은 **하나의 폴더 역할**에만 속한다. 어디에 둘지 모호하다면 STRUCTURE.md를 다시 읽는다.

---

## 🧠 9+3+1+회고N 도메인 모델 (5-Layer)

> 시스템은 다섯 레이어로 구성된다. 9·3·1 은 본질 골격, 계좌관리자·회고분석가는 N 가변. 각 레이어는 plugin 패턴 — 새 학습부/분석가/전략가/트랙은 폴더 드롭만으로 확장.

| Layer | 역할 | 수 | 폴더 |
|---|---|---|---|
| **1. 학습부** | 분석가가 읽을 자료 | **9** (1:1, 카테고리 36) | `knowledge/canon/<learning_dept>/<category>/` |
| **2. 분석가** | 자료 → 점수·verdict 발행 (S/T/α/buy_score/F-Score). 학습부 1:1 | **9** (1:1, ANALYST-PERSONAS-001 v2) | `agents/analysts/<analyst_id>/persona.md` |
| **3. 전략가** | Track A (중장기 수익금) + Track B (단기 손익비). 분석가 점수 종합 → 권고 발행 | **2+** (plugin 확장, STRATEGY-TRACK-001) | `agents/strategists/<track_id>/persona.md` |
| **4. 계좌관리자** | 4 계좌 (국장/미장 × 중장기/단기) + 자산배분 | **1+** (계좌 수 따라 N 가변, M5) | `agents/account_manager/persona.md` |
| **5. 회고분석가** | 분석·전략·계좌 등 미진한 것 보완 + 신규 기능 제안 (PROPOSAL 발행) | **N** (제한 X, 창의성 보존, RETROSPECT-ANALYST-001 백로그) | `agents/retrospect/<id>/persona.md` |
| (출력 채널) | 시간대 브리핑 / 종목 추천 / 매매 알림 / 매매일지 | — | `pipelines/` + `server/api/` + `server/telegram/` |

**흐름**: 분석가 → 전략가 → 계좌관리자 → 회고분석가 (분석·전략·계좌 등 보완 + 신규 부서 제안). 신규 부서 효율성 판단 = 회고분석가의 영역 자체.

### Layer 1 ↔ Layer 2 매핑 (9:9, 1:1, ANALYST-PERSONAS-001 v2)

| 학습부 (Layer 1) | 폴더 | 분석가 (Layer 2) | analyst_id |
|---|---|---|---|
| 원칙부 | `knowledge/canon/principles/` | 원칙수호자 | `principle_guardian` |
| 트레이딩부 | `knowledge/canon/trading/` | 트레이더 | `trader` |
| 시장매크로부 | `knowledge/canon/market_macro/` | 시장상태분석가 | `market_state_analyzer` |
| 종목선정부 | `knowledge/canon/stock_selection/` | 종목선정가 | `stock_picker` |
| 종목분석부 | `knowledge/canon/stock-analysis/` | 종목분석가 | `stock_analyst` |
| 자산복리부 | `knowledge/canon/wealth_compounding/` | 자산전략가 | `wealth_strategist` |
| 매매저널부 | `knowledge/canon/trading_journal/` | 매매저널리스트 | `trading_journalist` |
| 수급분석부 | `knowledge/canon/flow_analysis/` | 수급분석가 | `flow_analyzer` |
| 뉴스부 | `knowledge/canon/news/` | 뉴스큐레이터 | `news_curator` |

### Layer 3 트랙 (STRATEGY-TRACK-001)

| 전략가 (Layer 3) | 본질 | 자본 | 폴더 |
|------------------|------|-----|------|
| **Track A** | 🏢 중장기 수익금 게임 (부동산 임대업) | 70-80% | `agents/strategists/track_a/` |
| **Track B** | ☕ 단기 손익비 게임 (카페 운영) | 20-30% | `agents/strategists/track_b/` |

단타·중장기 (지수 투자) 빼고 A/B 만 (사용자 결정 2026-05-17). 향후 plugin 확장 가능 (`agents/strategists/<new_track>/` 드롭).

### plugin 패턴 규칙
- 새 학습부 추가 = `knowledge/canon/<id>/` + `README.md` 드롭. 코드 변경 0 — `load_shared_canon()` 자동 인식.
- 새 분석가 추가 = `agents/analysts/<id>/{persona.md, manifest.yaml}` 드롭 + ANALYST-PERSONAS-001 v2 의 9 분석가 명단 갱신 (별도 SPEC 신설).
- 새 전략가 트랙 추가 = `agents/strategists/<track_id>/{persona.md, manifest.yaml}` 드롭 + manifest 의 `input_routing` 정의. 코드 변경 0 (`core/strategist/run_strategist.py` 가 manifest 메타로 동적 호출).
- 새 회고분석가 추가 = `agents/retrospect/<id>/{persona.md, manifest.yaml}` 드롭. N 제한 X.
- 분산투자는 별도 Layer 가 아니라 **Layer 4 계좌관리자의 한 모드** (자산배분 = 계좌 단위 메타 결정).

---

## 🔀 파이프라인 표준 레이아웃 (pipelines/<pipeline-id>/)

모든 파이프라인은 이 구조를 따른다. `scripts/validate.py` 가 자동 검증.

```
pipelines/<pipeline-id>/
├── __init__.py
├── manifest.yaml             # ★ 파이프라인 메타 (stages + schedule + parts)
├── stages/                   # ★ 각 stage = 단일 책임 모듈
│   ├── __init__.py
│   ├── collect_<x>.py        # type: collect  — 외부/DB 수집
│   ├── check_<y>.py          # type: check    — 규칙·불변식 검증
│   ├── analyze.py            # type: analyze  — LLM 판단 (runtime: llm)
│   ├── persist.py            # type: act      — DB 저장 (briefing_parts 등)
│   └── notify.py             # type: act      — 텔레그램/파일 알림
├── prompts/                  # (runtime: llm 가진 stage 있을 때) 프롬프트 템플릿
│   └── *.md                  # stages/analyze.py 가 pipeline_prompts_dir() 로 자동 해결
└── tests/
    ├── test_<stage>.py
    └── test_smoke.py         # 파이프라인 전체 스모크
```

### `manifest.yaml` 필수 필드

```yaml
id: morning_pre                 # 폴더 이름과 일치 (snake_case)
name: "07:00 장전 브리핑"

schedule:                       # 선택. 없으면 수동/이벤트 트리거
  - trigger: cron | interval | event
    expr: "0 7 * * 1-5"
    timezone: Asia/Seoul

knowledge:                      # 선택. 지식 레이어 활성화
  shared_canon: true
  rag_enabled: false

stages:                         # ★ 실행 그래프. depends_on + parallel_with 로 DAG 정의
  - id: <stage-id>
    module: stages.<module_name>
    type: collect | check | analyze | act
    runtime: llm                # 선택. llm 호출 stage만
    depends_on: [...]           # 선택. 선행 stage id 목록
    parallel_with: <stage-id>   # 선택. 같이 시작 가능
    timeout_sec: <int>
    memory:                     # 선택. analyze 등에서 컨텍스트 주입
      context_id: <key>
      budget_tokens: <int>

parts:                          # 선택. 브리핑 파이프라인이 산출하는 파트 목록
  - key: overnight
    label: 간밤시황
    order: 1

contract_version: "1.0"
status: draft | scaffolded | active | deprecated
```

### 필수 체크리스트
- [x] `__init__.py`
- [x] `manifest.yaml` — id 가 폴더명과 일치
- [x] `stages/` 내 manifest 가 참조하는 모든 module 존재
- [x] `tests/` — 최소 1개 smoke test
- [x] snake_case 폴더명 (파이썬 패키지 호환)

### 파이프라인 간 규칙
- **다른 파이프라인의 `stages/` 를 import 하지 않는다.** 공용 로직은 `collectors/`·`checkers/` 로만.
- 파이프라인 간 통신은 DB (team_outputs, briefing_parts, 등) 또는 계약 JSON 으로만.

---

## 📥 collectors/ — 공용 데이터 수집 라이브러리

```
collectors/
├── __init__.py
├── us_markets.py              # 미국 야간 시황 + 원달러
├── kr_futures.py              # 코스피 야간 선물
├── news_rss.py                # 뉴스 RSS
└── fear_greed.py              # CNN Fear & Greed (비공식 API)
```

**규칙**: 파이프라인의 stage 가 얇게 래핑해서 쓴다. 무상태 함수 중심. 외부 API 호출은 `connectors/` 를 경유.

---

## ✅ checkers/ — 공용 규칙/원칙 체커

```
checkers/
├── __init__.py
├── commandments/              # 7계명 각 조항별 순수 체커
└── principles.py              # 원칙팀 진입점
```

**규칙**: LLM 호출 없음. 입력 → bool/verdict 반환. 테스트하기 쉬운 순수 함수.

---

## 🔌 connectors/ — 외부 API 커넥터

```
connectors/
├── __init__.py
├── kis/                       # 한국투자증권 OpenAPI (주문 금지, paper 모드만)
└── yfinance/                  # Yahoo Finance
```

**규칙**: 외부 SDK 의 얇은 래퍼. 에러 정규화·재시도·토큰 갱신 등 외부 시스템 어댑터 역할만.

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

### SPEC 2-tier (큰 방향 ↔ 다음다음 디테일 분리)
혼자 하는 프로젝트에서 "디테일의 디테일"에 빠져 PM이 길을 잃지 않도록, SPEC을 2층으로 구분한다 (frontmatter `level`).

| level | 역할 | `generates` | 연결 | PM 용도 |
|---|---|---|---|---|
| **roadmap** | 큰 방향 + 마일스톤 + 우선순위(시급도×중요도)만 못 박음. 코드 직접 생성 X | 비움 `[]` | `children:` 로 자식 implementation SPEC 나열 | "지금 어느 마일스톤인가 / 다음은 무엇인가" 중간 점검 |
| **implementation** | 실제 `generates` 코드를 가진 SDD 단위 (= 기존 SPEC) | 있음 | `parent:` 로 소속 roadmap (선택) | 실제 코딩 단위 |

- roadmap SPEC `type: roadmap`, `status` 에 `done` 사용 가능 (마일스톤 전부 완료 시).
- 첫 roadmap 예: `LEFT-BRAIN-COMPLETION-001` (왼쪽 뇌 = 분석·답변 절반 완성, 자식 = ANSWER-FIDELITY-001 / MARKET-VIEW-SYNTHESIS-001 / NEWS-SOURCE-001 / INFRA-US-MACRO-SNAPSHOT-001).
- 애자일 규칙: **"이 디테일이 현재 마일스톤을 전진시키나? 아니면 백로그."** roadmap의 *범위 밖* 절이 이 판단의 기준.

### 파일명: `<PREFIX>-<NNN>-<slug>.md`
- PREFIX = 특별 분류 또는 파이프라인 관련 키워드
  - 예: `BRIEFING`, `PRINCIPLE`, `MACRO`, `TECH`
  - 전역: `GLOBAL`, 계약: `CONTRACT`, 인프라: `INFRA`
- `NNN` = 3자리 순번 (001부터)
- `<slug>` = kebab-case 짧은 제목

예: `BRIEFING-ON-DEMAND-001-briefings-on-demand.md`, `CONTRACT-001-team-output-v1.md`

### 위치
| SPEC 범위 | 위치 |
|---|---|
| 전역 / 여러 파이프라인 공유 | `docs/specs/` |
| 계약(프로토콜) | `docs/specs/CONTRACT-*.md` |
| 인프라(core/server) | `docs/specs/INFRA-*.md` |

### 필수 Frontmatter
```yaml
---
spec_id: BRIEFING-ON-DEMAND-001
title: 온디맨드 브리핑
type: feature            # feature | refactor | infra | protocol | roadmap
status: draft            # draft | approved | implementing | implemented | verified | done
level: implementation    # implementation(기본) | roadmap (위 § SPEC 2-tier 참조)
generates:               # ★ 이 SPEC이 만들 파일들 (validate.py가 검증)
  - core/briefing/render.py
  - server/api/briefings_on_demand.py
modifies:                # 수정할 기존 파일 (있으면)
  - core/db/schema.sql
depends_on:              # 선행 SPEC
  - INFRA-001
contracts:               # 따르는 계약
  briefing_part: briefing-part-v1
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

파이프라인 간 통신은 **Pydantic 모델로 정의된 계약**을 통해서만.

| 계약 | 파일 | 설명 |
|---|---|---|
| StandardOutput | `core/contracts/team_output.py` | 팀/파이프라인 출력의 표준 형식 |
| BriefingPart | `core/contracts/briefing_part.py` | 브리핑 파트 (parts_store upsert 단위) |
| SpecFrontmatter | `core/contracts/spec_frontmatter.py` | SPEC 메타 파서 |
| MemoryRecord | `core/contracts/memory.py` | 메모리 레이어 레코드 |
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
- 코드에서는 `from core.config import get_config` 로 타입 안전하게 접근.
- 잘못된 YAML 저장 시 → **이전 설정 유지 + 에러 로그** (안전 실패).

---

## 💾 data/ — 런타임 데이터 (gitignore)

```
data/
├── db/stock-advisor.sqlite    # 메인 SQLite DB
├── backups/                   # 일별 DB 백업 (30일 보관)
├── reports/                   # 생성된 리포트 (마크다운)
├── memory/<context>/YYYY-MM-DD.md   # 일일 narrative
├── notifications/*.jsonl      # Telegram 미설정 시 알림 폴백
├── seed/                      # 시드 데이터 (mock_portfolio.json 등) — 커밋함
└── snapshots/last_snapshot.json  # 갭필링용 상태
```

**규칙**: `data/`는 gitignore. 단 `data/seed/` 는 예외 (커밋 허용).

---

## 🧱 core/ — 공유 라이브러리

```
core/
├── briefing/            # 브리핑 렌더러 + parts_store (upsert/get)
├── config/              # 통합 Config + 동적 리로드
├── contracts/           # Pydantic 계약 모델
├── db/                  # SQLite 연결, 마이그레이션
├── knowledge/           # RAG 지식 레이어 (ingest/chunk/embed/retrieve/compile)
├── llm/                 # LLM 클라이언트 (Anthropic/Gemini + Prompt Caching)
├── logging/             # 구조화 로거 (httpx/telegram 등 토큰 유출 차단 포함)
├── memory/              # LLM 맥락 메모리 레이어 (loader/composer/rollup/cleanup/cache/hasher)
├── notification/        # 알림 발송 (Telegram + 파일 폴백)
└── scheduler/           # APScheduler 래퍼
```

**규칙**: `core/`는 프레임워크. 특정 파이프라인·도메인 로직이 들어가지 않는다.

---

## 🖥️ server/ — 상주 런타임

```
server/
├── main.py                    # ★ uvicorn 진입점. FastAPI + APScheduler + Telegram 봇 시작.
├── api/                       # REST 엔드포인트
│   ├── pipelines.py           #   GET/POST /api/pipelines, /api/pipelines/<id>/run
│   ├── teams.py               #   GET /api/teams/<id>/latest (호환)
│   ├── briefings.py           #   GET /api/briefings/...
│   ├── briefings_on_demand.py #   4종 엔드포인트 (latest/parts/run/resend)
│   ├── config.py              #   GET/POST /api/config
│   ├── notifications.py       #   알림 조회
│   └── positions.py           #   watch_positions / sim_positions
├── telegram/                  # python-telegram-bot long-polling + 3 명령어
├── orchestration/             # (예약) 파이프라인 실행 헬퍼
└── schedulers/
    ├── loader.py              # pipelines/*/manifest.yaml 의 schedule 읽어 APScheduler 등록
    └── jobs/                  # 파이프라인에 속하지 않는 인프라 작업
        ├── backup.py
        ├── gap_filler.py
        ├── daily_rollup.py
        ├── weekly_rollup.py
        ├── monthly_rollup.py
        └── memory_cleanup.py
```

**원칙**: `server/`는 FastAPI + 스케줄러 + 텔레그램 봇만. 파이프라인 로직은 전혀 없음. 오로지 파이프라인을 "불러쓰는" 레이어.

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

## 📚 knowledge/ — 공용 학습 자료 (Layer 1 학습부)

```
knowledge/
├── canon/                            # 항상 주입되는 compiled 지식 (9 학습부 × 36 카테고리)
│   ├── principles/                   # 원칙부 → principle_guardian (3 카테고리)
│   │   ├── philosophy_seven_commandments/
│   │   ├── trading_doctrine/
│   │   └── market_regime_rules/
│   ├── trading/                      # 트레이딩부 → trader (6 카테고리)
│   │   ├── entry_exit/
│   │   ├── position_sizing/
│   │   ├── trading_styles/
│   │   ├── market_regime_response/
│   │   ├── failure_lessons/
│   │   └── operational_safeguards/
│   ├── market_macro/                 # 시장매크로부 → market_state_analyzer (4 카테고리, 시드)
│   ├── stock_selection/              # 종목선정부 → stock_picker (4 카테고리, 시드)
│   ├── stock-analysis/               # 종목분석부 → stock_analyst (5 카테고리)
│   ├── wealth_compounding/           # 자산복리부 → wealth_strategist (6 카테고리)
│   │   ├── monetary_evolution/
│   │   ├── currency_pricing/
│   │   ├── crisis_signals/
│   │   ├── debt_rate_cycle/
│   │   ├── macro_roadmap/
│   │   └── asset_classes/
│   ├── trading_journal/              # 매매저널부 → trading_journalist (4 카테고리, 시드)
│   ├── flow_analysis/                # 수급분석부 → flow_analyzer (4 카테고리, 시드)
│   └── news/                         # 뉴스부 → news_curator (별도 SPEC)
└── reference/                        # Chroma RAG 용 원본 (LLM 비주입, INFRA-RAG-001 인덱싱)
    └── <learning_dept>/              # 학습부별 PDF 추출본 / 원자료
```

각 카테고리는 `_category.yaml` (frontmatter: title, description, when_to_inject, target_analysts) 를 가진다. KNOWLEDGE-SYNC-001 Phase 2 = 카테고리 단위 화이트리스트·자동 색인.

`core.knowledge.compose.load_shared_canon()` 이 `canon/` 을 **재귀로** (`rglob("*.md")`) 모두 읽어 모든 LLM 호출의 system prompt 에 주입한다. `README.md` 는 scaffolding 표시용이므로 자동 제외.

자료 투입 흐름:
1. 사용자가 `knowledge/reference/` 에 파일 드롭
2. `just knowledge-ingest <topic>` → Chroma 인덱싱 (Phase 3)
3. canon 은 수작업 편집 또는 `just knowledge-compile` 로 재생성
4. 다음 LLM 호출부터 반영

새 학습부 추가 = `knowledge/canon/<new_id>/` 폴더 드롭만으로 즉시 반영 (plugin 패턴).

---

## 🔧 scripts/ — 개발·운용 도구

| 스크립트 | 역할 |
|---|---|
| `scaffold.py` | 새 파이프라인/MCP/SPEC 자동 생성 |
| `validate.py` | 전체 구조 정합성 검증 |
| `trace.py` | SPEC ↔ 코드 양방향 매핑 (`docs/traceability.md` 생성) |
| `generate_domain_doc.py` | SPEC + 코드 → 도메인 문서 자동 생성 |
| `db_init.py` | SQLite 스키마 초기화 |
| `knowledge.py` | knowledge ingest/compile/status/browse |

`justfile` 에서 모든 명령을 단축 (`just validate`, `just trace`, `just test-pipeline <name>`).

---

## 📘 docs/ 구조

```
docs/
├── STRUCTURE.md          # ★ 이 문서 (규약의 원천)
├── WORKFLOW.md           # SDD 사이클 1페이지
├── CONTRACTS.md          # 메시지/DB/run_id 계약 명세
├── RUNTIME.md            # 서버·스케줄러·메모리·지식 동작
├── RESUME.md             # 세션 재진입용 상태판
├── SESSIONS.md           # 세션 로그 인덱스
├── traceability.md       # 자동 생성 (SPEC↔코드 매핑)
├── a_wanted/             # 사용자 원 요구사항
├── b_plan/               # 활성 설계/계획 문서
├── c_worked/             # 세션별 완료 로그 (YYYY-MM-DD_*.md)
├── specs/                # 전역 SPEC
│   ├── BRIEFING-*.md
│   ├── CONTRACT-*.md
│   ├── INFRA-*.md
│   └── GLOBAL-*.md
├── domain/               # ★ 자동 생성 — 사용자용 결과물 설명서
└── raw_docs/             # 원본 아키텍처 문서
```

**`docs/domain/` 은 자동 생성**. 사람이 직접 편집하지 않음. `scripts/generate_domain_doc.py` 가 SPEC + 코드 docstring + 테스트 케이스를 조합해 생성.

---

## ✅ 검증 규칙 (validate.py가 체크)

- [ ] 모든 파이프라인이 필수 파일(`__init__.py`, `manifest.yaml`, `stages/`) 구비
- [ ] manifest.yaml 의 id 가 폴더명과 일치 (snake_case)
- [ ] 모든 SPEC이 frontmatter 구비
- [ ] SPEC의 `generates` 경로에 실제 파일 존재 (status=implemented 이상)
- [ ] `mcp-servers/registry.yaml` ↔ MCP 폴더 존재 일치
- [ ] DB 스키마 ↔ `core/db/schema.sql` 일치
- [ ] 파이프라인 간 `stages/` 코드 import 없음 (AST 검사)
- [ ] 모든 `.py` 파일이 타입 힌트 구비 (선택적 경고)
- [ ] `contract_version` 충돌 없음
- [ ] `config/runtime.yaml` 이 Pydantic 스키마 통과

---

## 🚫 절대 하지 말 것

- 파이프라인의 `stages/` 가 다른 파이프라인의 `stages/` 를 `import` 금지 — 공용은 `collectors/`·`checkers/`·`core/` 로만 공유
- `.sh` / `.bat` 스크립트 작성 금지 — `justfile` + Python 스크립트 사용
- 문자열 경로 조합 금지 — `pathlib.Path` 사용
- 하드코딩된 임계값 금지 — `config/runtime.yaml` 또는 `manifest.yaml` 에 선언
- SPEC의 `generates` 외 위치에 파일 생성 금지
- `data/` 아래 파일을 커밋 (단, `data/seed/` 제외)
- `config/runtime.yaml` 과 `.env` 값을 코드에 인라인하지 않기
- 파이프라인 폴더명에 하이픈 사용 금지 — 파이썬 패키지 호환 위해 snake_case
