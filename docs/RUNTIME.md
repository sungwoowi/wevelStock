# 🖥️ RUNTIME.md — 서버·스케줄러·메모리·지식 동작

> `server/` 라는 단일 Python 프로세스가 어떻게 FastAPI + 스케줄러 + 오케스트레이터를 동시에 돌리는지, 그리고 LLM 맥락 연속성(Memory Layer)과 팀별 지식 내재화(Knowledge Layer)가 어떻게 작동하는지 설명합니다.

---

## 🏛️ 런타임 구조 (한 프로세스, 세 역할)

```
            uvicorn server.main:app
                      │
          ┌───────────┴───────────┐
          │  FastAPI Application  │
          │  (event loop: asyncio)│
          └─────────┬─────────────┘
                    │
   ┌────────────────┼────────────────┐
   ▼                ▼                ▼
[REST API]   [APScheduler]   [Orchestrator]
 (server/     (server/         (server/
   api/)        schedulers/)     orchestration/)
   │              │                │
   └──────────────┴────────────────┘
                  │
          모두 동일한 event loop에서
          teams/<...>/src/agent.py 호출
```

**단일 프로세스 이유**:
- 크로스 플랫폼 단순성 (Mac/Windows 동일)
- 개발 친화 (로그 한곳, 디버깅 한곳)
- 로컬/개인 규모엔 충분한 처리량

---

## 🚀 서버 시작 시퀀스

```
uvicorn server.main:app
    │
    ▼
1. 설정 로드 (core/config)
    - .env 읽기
    - config/defaults.yaml + config/runtime.yaml 병합
    - watchdog 으로 runtime.yaml 감시 시작
    │
    ▼
2. DB 초기화 체크 (core/db)
    - data/db/stock-advisor.sqlite 없으면 생성
    - schema.sql 실행 (멱등)
    - 마이그레이션 체크
    │
    ▼
3. Gap Filler 실행 (server/schedulers/jobs/gap_filler.py)
    - data/snapshots/last_snapshot.json 확인
    - 서버가 꺼졌던 기간 식별
    - 외부 데이터 소급 수집 (KIS/FRED — MCP 호출)
    - 갭 기간 팀 판단 소급 생성 (선택)
    │
    ▼
4. Memory Warm-up (core/memory/loader)
    - 최근 30일 team_memory + 12주 rollup 프리로드 (프로세스 캐시)
    │
    ▼
5. 팀 레지스트리 로드 (core/registry)
    - teams/registry.yaml 스캔
    - 각 팀 manifest.yaml 유효성 검증
    - 활성 팀 목록 확정 (config 기반 enabled 체크)
    │
    ▼
6. 스케줄러 등록 (server/schedulers/loader)
    - 각 팀 manifest의 schedule 필드 → APScheduler 작업으로 등록
    - 인프라성 작업(backup, rollup, cleanup) 등록
    │
    ▼
7. FastAPI 라우터 등록
    - server/api/*.py 의 엔드포인트 마운트
    │
    ▼
8. 서버 READY
    - http://localhost:8000 리스닝 시작
    - 스케줄러 첫 실행 대기
```

---

## ⏰ 스케줄러 동작

### 팀이 자기 스케줄을 선언
```yaml
# teams/<team-id>/manifest.yaml
schedule:
  - trigger: cron
    expr: "30 8 * * *"
    timezone: Asia/Seoul
  - trigger: interval
    hours: 1
  - trigger: event
    on: market_open
```

### 서버가 등록
`server/schedulers/loader.py` 가 시작 시 모든 manifest 를 읽어 APScheduler에 등록:
```python
for team in registry.active_teams():
    for sched in team.manifest.schedule:
        scheduler.add_job(
            run_team,
            trigger=build_trigger(sched),
            args=[team.id],
            id=f"{team.id}::{sched.id}",
            replace_existing=True,
        )
```

### 인프라성 작업 (server/schedulers/jobs/)
팀에 속하지 않는 작업:
| 작업 | 주기 |
|---|---|
| `backup.py` | 매일 자정 |
| `gap_filler.py` | 서버 시작 시 (1회) |
| `daily_rollup.py` | 매일 23:50 KST |
| `weekly_rollup.py` | 일요일 23:55 |
| `monthly_rollup.py` | 매월 말일 23:58 |
| `memory_cleanup.py` | 매월 1일 새벽 |

---

## 🎯 팀 실행 흐름 (run_team)

```
run_team(team_id) 호출
    │
    ▼
1. orchestrator.runner 가 팀을 실행
   - asyncio.gather로 depends_on 없으면 병렬
   - 있으면 선행 팀 완료 후 실행
    │
    ▼
2. 팀 agent.run(input) 호출
    - LLM 팀: core/memory + core/knowledge 로 context 구성
    - 규칙 팀: config에서 임계값 읽고 순수 로직
    │
    ▼
3. StandardOutput 반환
    - team_outputs 테이블에 INSERT (ON CONFLICT REPLACE)
    - team_memory 에 narrative 저장 (LLM 팀)
    │
    ▼
4. 알림 조건 체크
    - 팀이 notify() 호출 → core/notification
    - Telegram 또는 파일 폴백
    │
    ▼
5. 결과 반환 → OrchestratorResult 에 누적
```

---

## 🧠 Memory Layer 동작

### 3계층 구조

```
┌────────────────────────────────────────────────┐
│ Hot (원본, 180일): team_memory 테이블            │
│   + data/memory/<team>/YYYY-MM-DD.md            │
├────────────────────────────────────────────────┤
│ Warm (요약, 2년):  memory_rollup 테이블          │
│   - daily | weekly | monthly                    │
├────────────────────────────────────────────────┤
│ Cold (장기, ∞):   memory_rollup (quarterly/yearly)│
│   - 주요 이벤트 + 핵심 지표만                     │
└────────────────────────────────────────────────┘
```

### 매 LLM 호출 시 context 주입

```python
# core/memory/loader.py
async def load_context(team_id, target, token_budget=4000):
    recent_14_days = query_team_memory(team_id, days=14)
    recent_12_weeks = query_rollup(team_id, "weekly", weeks=12)
    recent_6_months = query_rollup(team_id, "monthly", months=6)
    return trim_to_budget(
        [recent_14_days, recent_12_weeks, recent_6_months],
        budget=token_budget,
    )
```

### 멱등성 (input_hash)

```python
# core/memory/hasher.py
def compute_input_hash(
    input_data: dict,
    context_snapshot: dict,
    model: str,
    contract_version: str,
    canon_version: int | None = None,
) -> str:
    payload = {
        "input": canonicalize(input_data),
        "context": canonicalize(context_snapshot),
        "model": model,
        "contract_version": contract_version,
        "canon_version": canon_version,
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
```

**같은 hash → LLM 호출 스킵 → llm_call_cache 에서 반환**. 테스트/재실행 시 동일 결과 보장.

### 자동 롤업

```
매일 23:50:
  SELECT * FROM team_memory WHERE date = today
  → 팀별로 "오늘의 요약" 생성 (LLM 또는 템플릿)
  → memory_rollup (daily) 에 저장

매주 일요일 23:55:
  지난 7일의 daily 를 읽어 weekly 로 압축

매월 말일 23:58:
  지난 한 달의 daily/weekly 를 monthly 로 압축

매월 1일 새벽 03:00:
  cleanup.py 실행:
    - 180일 지난 team_memory 의 narrative 를 NULL 로 (정형 데이터만 유지)
    - 7일 지난 llm_call_cache 삭제
    - data/memory/<team>/ 의 180일 지난 .md 삭제
```

### DB 스키마

```sql
CREATE TABLE team_memory (
    team_id TEXT NOT NULL,
    date TEXT NOT NULL,
    target TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    verdict TEXT,
    confidence INTEGER,
    reasons_json TEXT,
    narrative TEXT,                -- 180일 후 NULL
    data_json TEXT,
    model TEXT,
    contract_version TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (team_id, date, target, input_hash)
);

CREATE TABLE memory_rollup (
    team_id TEXT NOT NULL,
    period_type TEXT NOT NULL,     -- daily | weekly | monthly | quarterly | yearly
    period_key TEXT NOT NULL,      -- '2026-04-16' | '2026-W16' | '2026-04' | '2026-Q2'
    summary_md TEXT,
    key_events_json TEXT,
    metrics_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (team_id, period_type, period_key)
);

CREATE TABLE llm_call_cache (
    input_hash TEXT PRIMARY KEY,
    model TEXT,
    response_json TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    cost_usd REAL,
    created_at TEXT DEFAULT (datetime('now')),
    ttl_days INTEGER DEFAULT 7
);
```

---

## 📚 Knowledge Layer 동작

> 5-Layer 도메인 모델의 **Layer 1 (학습부)** 구체화. 분석가(Layer 2) 의 persona.md 와 함께 LLM 호출 system prompt 에 동시 주입.

### 2계층 구조

**Layer 1: Canon (5 학습부)** — 항상 주입
- 위치: `knowledge/canon/<learning_dept>/*.md` (재귀 로드)
- 5 학습부 폴더: `principles/`, `mechanics/`, `wealth_compounding/`, `stock-analysis/`, `news/`
- 분석가 1:1 매핑: 원칙수호자 / 매매코치 / **자산전략가** / 종목분석가 / 뉴스큐레이터
- 각 폴더 안의 모든 `.md` 가 자동 합쳐짐 (`README.md` 만 자동 제외)
- 분석가와 학습부는 1:1 매핑 (분석가 manifest 의 `reads:` 로 본인 학습부만 주입하는 N:M 모드는 추후 확장; 현재는 5 학습부 통째 주입)
- 크기: 5 학습부 합쳐 ~5-15K 토큰 목표 (신중히 엄선)
- **Anthropic Prompt Caching 대상** → 비용 90% 절감

**Layer 2: Reference RAG** — 필요시 검색 (Phase 3)
- Chroma DB: `knowledge/reference/vector-index/`
- 청크: 500-1000 토큰, 출처·태그 메타 포함
- 매 호출 시 현재 상황과 유사한 **Top-3** retrieval

### 자료 투입 파이프라인

```bash
# 사용자가 자료 드롭 (학습부 단위)
cp macro_report.pdf knowledge/reference/wealth_compounding/

# 인덱싱 (Chroma 저장 — Phase 3)
just knowledge-ingest wealth_compounding
  → core/knowledge/ingest.py 가:
    1. PDF → text (pypdf)
    2. 500-1000 토큰 청크로 분할
    3. Embedding (text-embedding-3-small 또는 로컬)
    4. Chroma 저장

# Canon 직접 편집 (M2 인터뷰 산출)
편집: knowledge/canon/wealth_compounding/<topic>.md
  → 다음 LLM 호출부터 자동 반영 (load_shared_canon 재귀 읽기)
```

### 런타임 주입 흐름

```python
# core/knowledge/compose.py — build_pipeline_prompt
async def build_pipeline_prompt(*, context_id, persona_path, ...):
    canon = load_shared_canon()           # knowledge/canon/**/*.md 재귀
    persona = read(persona_path)          # agents/analysts/<id>/persona.md (M3)
    memory = load_context(context_id, ...)

    return [  # Anthropic Prompt Caching 구조
        {"type": "text", "text": canon,   "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": persona, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": memory,  "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": retrieved},  # 매번 다름 (Phase 3)
    ]
```

`load_shared_canon()` 동작:
1. `knowledge/canon/` 아래 모든 `.md` 를 `rglob` 으로 재귀 수집
2. 파일명이 `README.md` 인 것은 scaffolding 표시용으로 자동 제외
3. 상대경로 정렬로 결정론적 순서
4. 빈 파일은 skip

### manifest.yaml 선언 (분석가 — M3)

```yaml
# agents/analysts/<analyst_id>/manifest.yaml (M3 신설)
id: principle_guardian
reads: [principles]                  # 본인 학습부 (1:N 확장 시 list)
knowledge:
  shared_canon: true                 # 5 학습부 통째 주입 (현재 default)
  rag_enabled: false                 # Phase 3 활성
```

---

## 💰 토큰 비용 & Prompt Caching

### Anthropic Prompt Caching 활용
`system` 메시지의 앞부분(persona + canon + memory)을 `cache_control: ephemeral` 로 표시 → 5분 내 재호출 시 90% 비용 할인.

### 예시 비용 (매크로팀 1회)
```
system (캐시):
  persona    1K  → 실효 0.1K
  canon      8K  → 실효 0.8K
  memory     3K  → 실효 0.3K
system (매번):
  retrieved  2K  → 실비 2K
user:        1K  → 실비 1K
output:      0.5K → 실비 0.5K

Sonnet 4 기준:
  입력: ~4.2K × $3/1M = $0.013
  출력: ~0.5K × $15/1M = $0.008
  = $0.021/호출

월 12회/일 × 30일 = $7.6/월 (~10,000원)
```

---

## ⚙️ 설정 핫 리로드 동작

```
config/runtime.yaml 수정 감지 (watchdog)
    │
    ▼
core/config/loader: 새 파일 파싱 시도
    │
    ├─ 성공 → Pydantic 스키마 통과 → Config 객체 원자적 교체
    │           → 이벤트 발행: 스케줄러/팀에 알림 (필요시 재등록)
    │
    └─ 실패 → 이전 Config 유지 + ERROR 로그 + Telegram 경고
```

변경 가능 항목 (예시):
- `telegram.enabled`, `telegram.formats.<team>`
- `scheduler.<job>.cron/interval`
- `teams.<id>.enabled`, 팀별 thresholds
- `llm.primary`, `llm.crosscheck_enabled`
- `memory.retention.*`

**불변 항목** (변경 시 재시작 필요):
- `database.path`
- MCP 서버 등록 (.mcp.json)

---

## 🌐 API 엔드포인트 (server/api/)

| 엔드포인트 | 메서드 | 용도 |
|---|---|---|
| `/api/health` | GET | 헬스체크 |
| `/api/teams` | GET | 팀 registry 조회 |
| `/api/teams/{id}/latest` | GET | 팀의 최근 StandardOutput |
| `/api/teams/{id}/history` | GET | 팀 판단 이력 (date range) |
| `/api/config` | GET | 현재 런타임 설정 조회 |
| `/api/config/reload` | POST | 설정 수동 리로드 |
| `/api/notifications/recent` | GET | 최근 알림 목록 |
| `/api/demo/run` | POST | 시나리오 기반 데모 실행 |
| `/api/telegram/webhook` | POST | Telegram 봇 명령 수신 |

---

## 🔌 MCP 서버와의 관계

- MCP 서버는 **별도 프로세스** (Python MCP SDK)
- `server/` 프로세스 내부에는 MCP **클라이언트**만 있음 (core/mcp_client.py)
- 팀이 MCP 도구 호출 = 서버가 MCP 프로세스로 JSON-RPC 전송

초기(Phase 1-4)에는 MCP 서버 실물은 없고, **mock/시드 데이터**로 개발. 추후 KIS/FRED 붙일 때 MCP 서버 구현.

---

## 🧪 E2E 데모 시나리오

```bash
just demo over-allocation
```

**내부 동작**:
1. server가 이미 떠있거나 데모 전용 1회 실행
2. `data/seed/mock_portfolio.json` 의 `over-allocation` 시나리오 로드
3. 오케스트레이터 호출:
   - principles 팀 실행 (규칙 체크) → "violation" StandardOutput
   - daily-briefing 팀 실행 (LLM 또는 mock) → principles 결과를 읽고 브리핑 생성
4. 두 팀의 알림 발송:
   - Telegram 설정되어 있으면 메시지 발송
   - 미설정이면 `data/notifications/*.jsonl` 에 기록
5. 대시보드(`http://localhost:3000`) 새로고침 → 두 카드 반영
6. CLI 결과 요약 출력

---

## 🛠️ 디버깅 팁

- **서버 로그**: 구조화 JSON 로깅 (`core/logging`). `just server 2>&1 | jq .`
- **DB 직접 조회**: `sqlite3 data/db/stock-advisor.sqlite "SELECT * FROM team_outputs ORDER BY created_at DESC LIMIT 10"`
- **알림 폴백 확인**: `tail -f data/notifications/$(date +%F).jsonl`
- **스케줄러 상태**: `GET /api/scheduler/jobs` (개발 모드)
- **설정 reload 감시**: `config/runtime.yaml` 저장 후 서버 로그에서 `[config] reloaded` 확인

---

## 🧯 Graceful Degradation

시스템은 부분 실패에 관용적입니다:
- **Telegram 설정 없음** → 파일 폴백
- **LLM API 키 없음** → mock 응답 폴백 (개발용)
- **MCP 서버 꺼짐** → 해당 팀 skip, 나머지 계속
- **config 파일 손상** → 이전 설정 유지
- **특정 팀 실행 실패** → 나머지 팀은 계속, OrchestratorResult.errors 에 기록
