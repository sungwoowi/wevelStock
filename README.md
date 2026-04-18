# wevelStock — AI 주식 분석 & 매매가이드 시스템

여러 AI 에이전트 팀이 각자 전문 관점에서 시장을 분석하고, 그 결과를 종합해 투자 판단을 제안하는 시스템.

> **이 문서의 목적**: 코드를 몰라도 "이 프로젝트에서 뭐가 어디에 있고, 어떻게 동작하며, 새 기능을 어떻게 추가하는지" 파악할 수 있게 합니다.

> 🌅 **처음이라면? → [MORNING.md](MORNING.md)** 5분 만에 실행하는 체크리스트 + 성공 기준.

---

## 🗺️ 폴더 지도 (한눈에 보기)

```
wevelStock/
├── teams/          🤖 AI 에이전트 팀 (분석·판단)
├── mcp-servers/    🔌 외부 세계 연결 도구 (KIS/FRED/Telegram)
├── server/         🖥️ 상주 런타임 (API + 스케줄러)
├── webapp/         🌐 UI (Next.js)
├── core/           🧱 공유 라이브러리
├── config/         ⚙️ 운영 설정 (동적 리로드)
├── docs/           📘 사람용 문서 (규약 + SPEC + 도메인)
├── scripts/        🔧 개발/운용 도구
├── data/           💾 런타임 데이터 (DB, 메모리, 백업)
└── knowledge/      📚 팀 공용 기본 자료
```

6개 폴더 = 6개 역할. 하나의 모듈은 하나의 역할에만 속합니다.

---

## 🧭 목적별 이동 가이드

| 하고 싶은 일 | 가야 할 곳 |
|---|---|
| 프로젝트 전체 규약을 이해하고 싶다 | [docs/STRUCTURE.md](docs/STRUCTURE.md) |
| 새 기능을 만드는 절차가 궁금하다 | [docs/WORKFLOW.md](docs/WORKFLOW.md) |
| 팀끼리 어떻게 소통하는지 알고 싶다 | [docs/CONTRACTS.md](docs/CONTRACTS.md) |
| 서버·스케줄러 동작을 이해하고 싶다 | [docs/RUNTIME.md](docs/RUNTIME.md) |
| 특정 팀의 역할이 궁금하다 | `teams/<팀>/CLAUDE.md` |
| 특정 기능의 상세 스펙이 궁금하다 | `teams/<팀>/specs/*.md` 또는 `docs/specs/` |
| 기능의 사용법(결과 설명서)이 궁금하다 | `docs/domain/<팀>/*.md` |
| 설정을 바꾸고 싶다 | [config/runtime.yaml](config/runtime.yaml) (서버 재시작 없이 반영됨) |

---

## 🚀 빠른 실행 (최초 1회)

### 1단계: 초기 세팅 (한 번만)

```bash
# Python 의존성 설치 (pytest/ruff 등 포함하려면 --all-extras 필수)
uv sync --all-extras

# 환경 변수 (API 키 없어도 mock 폴백으로 데모 동작)
cp .env.example .env

# DB 초기화
just db-init

# 웹앱 의존성 설치 (최초 1회)
just webapp-install
# 또는: cd webapp && pnpm install
```

### 2단계: CLI만으로 동작 확인

```bash
# 서버 없이 풀사이클 데모
just demo over-allocation
# → 원칙팀 → 브리핑팀 → 파일 알림 (data/notifications/*.jsonl) 생성
```

### 3단계: 서버 + 웹앱으로 대시보드 보기 (터미널 2개 필요)

wevelStock 은 **백엔드(FastAPI, 8000)** 와 **프론트엔드(Next.js, 3000)** 를 별도 프로세스로 띄웁니다. 웹앱은 백엔드 API를 fetch 로 호출하므로 **백엔드가 먼저 실행**되어 있어야 합니다.

**터미널 1 — 백엔드**
```bash
just server
# → http://localhost:8000/api/teams 에 JSON 응답
# → http://localhost:8000/docs 에 FastAPI Swagger UI
```

**터미널 2 — 웹앱**
```bash
just webapp-dev
# 또는: cd webapp && npm run dev
# → http://localhost:3000 에서 대시보드 열림
```

대시보드에서 시나리오 버튼(정상/비중 초과/손절 없음/감정 매매) 클릭 시 5초 내 카드들이 갱신됩니다.

> 💡 **웹앱에 데이터가 안 보인다면?** 대시보드 버튼을 누르거나 터미널에서 `just demo over-allocation` 한 번 실행해서 DB에 첫 데이터를 만드세요.
>
> 💡 **pnpm 쓰는 경우** 윈도우에서 `EPERM: rename` 에러가 나면 `npm install` 로 우회하세요. 레지스트리 hardlink 이슈가 원인입니다.

---

## ➕ 새 팀(에이전트) 추가하는 법 (3분 튜토리얼)

1. **스캐폴드 실행**
   ```bash
   python scripts/scaffold.py team sentiment-analysis --runtime llm
   ```
   → `teams/sentiment-analysis/` 가 표준 레이아웃으로 생성되고 `teams/registry.yaml` 이 자동 갱신됩니다.

2. **manifest.yaml 수정** — 이 팀이 무엇을 하는지, 언제 실행되는지 선언
3. **SPEC 작성** — `teams/sentiment-analysis/specs/SENTIMENT-001-*.md`
4. **`/spec-interview` 로 SPEC 살 붙이기** (Claude Code에서)
5. **"이 SPEC 구현해줘"** 라고 Claude Code에 지시 → 코드가 정확한 위치에 생성됨
6. **검증**: `just validate` 통과 확인
7. **도메인 문서 생성**: `just domain-doc SENTIMENT-001`

기존 파일을 전혀 건드리지 않고 **삽입만으로** 새 팀이 시스템에 참여합니다.

---

## 💡 철학: SDD(Spec-Driven Development) + 바이브 코딩

- **SPEC이 먼저**: 스펙 문서가 없으면 코드를 쓰지 않음.
- **AI가 길을 잃지 않게**: 계층적 `CLAUDE.md` 가 팀마다 존재.
- **사람이 읽는 결과물**: 모든 구현은 자동 생성된 도메인 문서(`docs/domain/`)로 설명됨.
- **확장은 삽입**: 새 팀·새 기능은 기존을 건드리지 않음.
- **판단은 LLM, 계산은 코드**: 데이터 수집·지표 계산은 코드가, 판단은 LLM API가.

---

## 📚 더 읽을 거리

- **[docs/STRUCTURE.md](docs/STRUCTURE.md)** — 이 한 파일이 모든 폴더 규칙의 원천
- **[docs/WORKFLOW.md](docs/WORKFLOW.md)** — SDD 사이클 1페이지
- **[docs/CONTRACTS.md](docs/CONTRACTS.md)** — 팀 간 메시지 계약
- **[docs/RUNTIME.md](docs/RUNTIME.md)** — 서버·스케줄러·메모리·지식 동작
- **[CLAUDE.md](CLAUDE.md)** — AI 에이전트(Claude Code)용 총괄 컨텍스트
- **[docs/stock-advisor-architecture-guide.md](docs/raw_docs/stock-advisor-architecture-guide.md)** — 전체 전략 원본 문서
- **[docs/FOUNDATION-PLAN.md](docs/FOUNDATION-PLAN.md)** — ★ 이 토대의 설계 계획서 (v0.5). 잔여 작업 이어갈 때 참조.
