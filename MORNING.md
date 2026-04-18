# ☀️ 아침에 읽을 문서

> 자는 동안 wevelStock 토대를 구축했습니다. 여기에 **무엇을 해야 하고**, **무엇이 성공인지** 정리했습니다.

---

## 🎯 먼저 할 일 (5분)

### Step 1 — 초기 세팅 (한 번만)

```bash
cd C:/Users/HOME/claude/wevelStock

# Python 의존성 설치
#   --all-extras 필수: pytest/ruff/mypy 는 optional deps
uv sync --all-extras

# DB 초기화 (SQLite 파일 생성)
uv run python -m scripts.db_init

# 구조 정합성 검증
uv run python -m scripts.validate

# 테스트 실행 (24개 모두 통과해야 정상)
uv run pytest
```

### Step 2 — CLI 데모 (터미널 1개)

```bash
uv run python -m scripts.demo over-allocation
# → 원칙팀(violation) + 브리핑팀(caution) + 파일 알림 생성
```

### Step 3 — 서버 + 웹앱 데모 (터미널 2개 필요!)

**wevelStock 은 백엔드와 프론트엔드가 별도 프로세스입니다.**

| 프로세스 | 포트 | 역할 |
|---|---|---|
| FastAPI 백엔드 | 8000 | API + 스케줄러 + 오케스트레이터 진입 |
| Next.js 웹앱 | 3000 | 대시보드 UI (백엔드 8000을 fetch 로 호출) |

**📟 터미널 1 — 백엔드 띄우기**
```bash
cd C:/Users/HOME/claude/wevelStock
uv run uvicorn server.main:app --reload --host 127.0.0.1 --port 8000
# 또는: just server
```
확인: 브라우저에서 `http://localhost:8000/api/health` → `{"status":"ok"}`

**📟 터미널 2 — 웹앱 띄우기**
```bash
cd C:/Users/HOME/claude/wevelStock/webapp
npm install       # ← 최초 1회만. 이후엔 생략
npm run dev
# 또는 pnpm 사용자는: pnpm install && pnpm dev
#   (윈도우에서 pnpm이 EPERM 실패하면 npm 사용 권장)
```
확인: 브라우저에서 `http://localhost:3000` → 대시보드 페이지

> ⚠️ **3000번 "연결할 수 없음"** → 웹앱이 안 떠 있습니다. 터미널 2 확인.
> ⚠️ **3000번 떴는데 데이터 없음** → 백엔드(8000)가 꺼져 있거나 DB가 비었음.
> 대시보드의 "비중 초과" 버튼 클릭 or 터미널에서 `uv run python -m scripts.demo over-allocation` 한 번 돌리세요.

### `just` 가 설치돼 있다면 더 간단

```bash
# Step 1
just install     # = uv sync --all-extras
just db-init
just validate
just test

# Step 2
just demo over-allocation

# Step 3 — 터미널 1
just server

# Step 3 — 터미널 2 (별도 창)
just webapp-install    # 최초 1회
just webapp-dev
```

---

## ✅ 성공 기준 체크리스트

### 1. 구조 검증 (`just validate`)
- [ ] 출력에 `✓ 0 errors` 나오면 성공 (warning 몇 개는 OK)
- [ ] `teams/registry.yaml` 이 자동 갱신됨 (generated_at 타임스탬프 있음)

### 2. 테스트 (`just test`)
- [ ] 원칙 관리팀 테스트 6개 모두 통과:
  - `test_normal_scenario_compliant`
  - `test_over_allocation_violation`
  - `test_no_stop_loss_violation`
  - `test_emotional_violation`
  - `test_idempotency_same_input_same_hash`
  - `test_commandments.py` 의 단위 테스트들
- [ ] 데일리 브리핑 팀 테스트 3개 모두 통과 (API 키 없이 mock 폴백으로):
  - `test_agent_returns_standard_output_without_api_key`
  - `test_briefing_narrative_non_empty`
  - `test_idempotency_hash`
- [ ] 오케스트레이터 테스트 2개 통과:
  - `test_orchestrator_runs_two_teams`
  - `test_orchestrator_violation_scenario`

### 3. 데모 실행 (`just demo over-allocation`)
```
성공 시 출력 예시:

🚀 wevelStock Demo
Scenario: over-allocation
Run ID: 2026-04-16...#demo-abcd1234

Orchestrator Verdict: alert  (confidence 85)

Team results:
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━
┃ Team             ┃ Verdict    ┃ Confidence ┃ Top reason
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━
│ principles       │ violation  │         95 │ [계명 1] 총 비중 82%…
│ daily_briefing   │ caution    │         55 │ [MOCK] LLM API 키 없음…
```
- [ ] `data/db/stock-advisor.sqlite` 가 생성됨
- [ ] `data/notifications/2026-04-16.jsonl` 에 2줄 이상 JSON 기록됨
  (Telegram 미설정이라 파일 폴백)
- [ ] 4개 시나리오 (`normal`/`over-allocation`/`no-stop-loss`/`emotional`) 모두 동작

### 4. 서버 구동 (`just server`)
```bash
just server
# http://localhost:8000
```
- [ ] `http://localhost:8000/api/health` → `{"status":"ok"}`
- [ ] `http://localhost:8000/api/teams` → 3개 팀 목록 JSON
- [ ] `http://localhost:8000/api/teams/principles/latest` → 원칙팀 최근 판단 (데모 실행 후)
- [ ] `http://localhost:8000/docs` → FastAPI Swagger UI
- [ ] `curl -X POST http://localhost:8000/api/demo/run?scenario=over-allocation` → StandardOutput JSON

### 5. 웹앱 (별도 터미널 필요)

**전제 조건**: 백엔드(8000)가 먼저 떠 있어야 합니다.

```bash
# 터미널 1 (백엔드 유지):
just server

# 터미널 2 (웹앱):
cd webapp
pnpm install    # 최초 1회만
pnpm dev
# → http://localhost:3000 자동 오픈 또는 수동 접속
```

- [ ] `http://localhost:3000` 접속 시 "wevelStock" 제목 + 시나리오 버튼 4개 보임
- [ ] 시나리오 버튼 클릭 → 5초 내 원칙 카드 + 브리핑 카드 갱신
- [ ] 원칙 카드에 녹/황/적 배지(verdict) 표시
- [ ] 브리핑 카드에 narrative 2~4문장 표시 (API 키 없으면 `[MOCK]` 접두)
- [ ] 최근 알림 리스트에 `notifications_log` 이력 표시
- [ ] 5초마다 자동 새로고침

**자주 겪는 문제**:
- ⚠️ `localhost:3000` 접속 불가 → webapp dev 서버 미실행. `cd webapp && pnpm dev` 재확인.
- ⚠️ 카드에 "데이터 없음" → 백엔드 미실행 or DB 비어있음. `just demo over-allocation` 한 번 실행.
- ⚠️ CORS 에러 → `config/runtime.yaml` 에 `server.cors.allowed_origins: ["http://localhost:3000"]` 추가.
- ⚠️ `pnpm` 없음 → `npm install -g pnpm` 또는 `npm install && npm run dev` 대체 가능.

### 6. 동적 Config 리로드
- [ ] 서버 구동 중 `config/runtime.yaml` 에 다음 추가 후 저장:
  ```yaml
  teams:
    principles:
      thresholds:
        total_weight_pct: 75
  ```
- [ ] `http://localhost:8000/api/config` 에서 값 변경 확인
- [ ] 데모 재실행 시 새 임계값 적용됨 (75% 초과만 위반)

---

## 📁 완성된 폴더 구조 (요약)

```
wevelStock/
├── README.md              ← 비개발자용 입구
├── CLAUDE.md              ← AI용 루트 컨텍스트
├── MORNING.md             ← 이 문서
├── docs/
│   ├── FOUNDATION-PLAN.md ← ★ 전체 설계 계획서 v0.5 (잔여 작업용)
│   ├── STRUCTURE.md       ← 폴더 규약 원천
│   ├── WORKFLOW.md        ← SDD 절차 1페이지
│   ├── CONTRACTS.md       ← 팀 간 메시지 계약
│   └── RUNTIME.md         ← 서버/스케줄러/메모리/지식 동작
├── teams/
│   ├── _template/         ← 새 팀 원본
│   ├── registry.yaml      ← 자동 갱신
│   ├── principles/        ← 팀 ① (규칙 기반 예시)
│   ├── daily_briefing/    ← 팀 ② (LLM 기반 예시)
│   └── orchestrator/      ← 팀 실행 조율
├── mcp-servers/
│   ├── _template/
│   └── registry.yaml      ← (현재 비어있음, Wave 2 이후 KIS/FRED 등 추가)
├── server/                ← FastAPI + APScheduler + 오케스트레이터 진입점
├── webapp/                ← Next.js 1페이지 데모 (버려질 UI)
├── core/                  ← 공유 라이브러리
├── config/
│   ├── defaults.yaml      ← 안전한 기본값
│   └── runtime.yaml       ← 동적 설정 (핫 리로드)
├── data/
│   ├── db/                ← SQLite
│   ├── seed/              ← 시드 데이터 (4개 시나리오)
│   ├── notifications/     ← Telegram 미설정 시 파일 폴백
│   └── memory/            ← 팀별 일일 narrative
├── scripts/               ← scaffold / validate / trace / demo / knowledge / domain-doc
└── .claude/               ← Claude Code 커스텀 명령 (추후 추가)
```

---

## 🚀 다음에 /spec-interview 로 진행할 작업

토대가 작동 확인되면 이 순서로 확장하세요:

### 당장 할 수 있는 것 (설치 없이)
1. **`PRINCIPLE-001` 에 살 붙이기**: `/spec-interview PRINCIPLE-001` — 엣지 케이스 로직 강화
2. **`BRIEFING-001` 프롬프트 고도화**: persona.md 확장 + knowledge/sources/ 에 자료 투입 → `just knowledge-compile daily_briefing`
3. **새 팀 추가 연습**: `just new-team sentiment-analysis --runtime llm` → 구조 확인

### API 키 설정 후 (ANTHROPIC_API_KEY)
4. 실제 LLM 응답으로 `just demo` 재실행 — mock 대신 진짜 브리핑
5. Anthropic Prompt Caching 실효 확인 (서버 로그에서 비용 추적)

### Wave 2 이후 (Foundation-Plan 참조)
6. MCP 서버 추가: `just new-mcp kis-api` → 실제 KIS 연동
7. 매크로 분석팀: `just new-team macro-analysis --runtime llm`
8. 기술적 분석팀: `just new-team technical-analysis --runtime llm`

---

## ⚠️ 알려진 제한 (초기 토대)

1. **Chroma 벡터 검색**: 자료를 `sources/` 에 넣고 `just knowledge-ingest <team>` 실행 전까지는 RAG가 비어있음. 그래도 Canon + Memory 만으로 LLM 팀 동작.
2. **Telegram**: 기본 파일 폴백. `.env` 에 `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` 설정 시 활성화.
3. **KIS/FRED MCP**: 아직 구현 안 됨. 현재는 seed 데이터 모드만 동작 (`SOURCE_MODE=seed`).
4. **웹앱**: "버려질 1페이지" 수준. 디자인 고도화는 Wave 6.
5. **자동 롤업 스케줄**: 서버 상주 상태여야 매일 23:50 발동. CLI 데모는 롤업을 트리거하지 않음 (필요 시 `just -m server.schedulers.jobs.daily_rollup`).

---

## 🔑 주요 명령 치트시트

```bash
# 구조
just validate           # 정합성 검증
just trace              # SPEC↔코드 매핑 → docs/traceability.md
just domain-doc PRINCIPLE-001    # 도메인 문서 생성

# 새 모듈
just new-team <id> [--runtime rule|llm|hybrid]
just new-mcp <id>
just new-spec <team> "<title>"

# 실행
just server             # FastAPI 개발 모드
just demo <scenario>    # CLI E2E 데모
just test               # pytest 전체
just test-team <team>   # 팀 단위

# 데이터
just db-init
just db-backup
just knowledge-ingest <team>
just knowledge-compile <team>

# 웹앱
just webapp-install
just webapp-dev

# 린트
just lint
just fmt

# 전체 품질 게이트 (커밋 전 권장)
just check
```

---

## 📖 더 읽을 문서

- **[docs/FOUNDATION-PLAN.md](docs/FOUNDATION-PLAN.md)** — 토대 설계 전체 (v0.5). 잔여 작업 이어갈 때 참조.
- **[docs/STRUCTURE.md](docs/STRUCTURE.md)** — 폴더/파일 규약의 원천
- **[docs/WORKFLOW.md](docs/WORKFLOW.md)** — SDD 사이클
- **[docs/CONTRACTS.md](docs/CONTRACTS.md)** — StandardOutput 등 팀 계약
- **[docs/RUNTIME.md](docs/RUNTIME.md)** — 서버/스케줄러/메모리/지식 동작

---

## 💬 문제 생기면

**Python / 백엔드**
- `uv sync` 실패 → Python 3.11+ 확인 (`python --version`)
- `pytest` / `ruff` / `mypy` 못 찾음 → `uv sync --all-extras` (optional deps 설치)
- `just` 없음 → 직접 `uv run python -m scripts.<name>` 실행
- `pytest` 실패 → 대부분 import 경로 이슈. `teams/__init__.py`, `core/__init__.py` 존재 확인

**웹앱 / 프론트엔드**
- `http://localhost:3000` **연결할 수 없음** → webapp 이 안 떠 있음. 별도 터미널에서 `cd webapp && pnpm dev` 필요.
- 대시보드 "데이터 없음" → 백엔드(8000) 가 안 떠 있거나 DB 비어있음. `just server` 상주 + `just demo over-allocation` 한 번.
- webapp 빌드 실패 → `cd webapp && pnpm install --no-frozen-lockfile`
- 서버 CORS 에러 → `config/runtime.yaml` 에 `server.cors.allowed_origins: ["http://localhost:3000"]` 추가 (저장하면 서버 재시작 없이 반영)
- `pnpm` 없음 → `npm install -g pnpm` 또는 `npm install && npm run dev` 로 대체 가능

모든 것이 막히면 **[docs/FOUNDATION-PLAN.md](docs/FOUNDATION-PLAN.md)** 를 펼쳐서 잔여 작업을 `/spec-interview` 로 이어가시면 됩니다.

**좋은 아침 되세요.** 🌅
