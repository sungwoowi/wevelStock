# wevelStock — AI 에이전트 협업 주식 분석 시스템 (루트 컨텍스트)

## 프로젝트 개요
5-Layer AI 에이전트 주식 분석 & 매매가이드 시스템. 지식부 → 분석가 → 전략가 → 계좌관리자 → 출력 채널의 단방향 흐름.
크로스 플랫폼(Mac + Windows). DB: SQLite. API: 한국투자증권(KIS) + KRX.

## 9+3+1+회고N 골격 (불변, 일부 N 가변)

2026-05-17 chat Claude Opus R&D 인수인계 + 사용자 의도 반영. 흐름은 절대적이되 N 일부는 가변.

| Layer | 역할 | 수 | 폴더 |
|---|---|---|---|
| 1. 지식부 | 분석가가 읽을 자료 | **9** (1:1) | `knowledge/canon/<dept>/<category>/` |
| 2. 분석가 | 자료 → 판단 (점수 발행: S/T/α/buy_score/F-Score) | **9** (1:1, ANALYST-PERSONAS-001 v2) | `agents/analysts/<analyst_id>/persona.md` |
| 3. 전략가 | Track A (중장기 수익금) + Track B (단기 손익비) — 분석가 점수 종합 → 권고 발행 | **2+** (plugin 확장, STRATEGY-TRACK-001) | `agents/strategists/<track_id>/persona.md` |
| 4. 계좌관리자 | 4 계좌 (국장/미장 × 중장기/단기) + 자산배분 | **1+** (계좌 수에 따라 N 가변) | `agents/account_manager/persona.md` (M5) |
| 5. 회고분석가 | 분석·전략·계좌 등 미진한 것 보완 + 신규 기능 제안 (PROPOSAL 발행) | **N** (제한 X, 창의성 보존) | `agents/retrospect/<id>/persona.md` (RETROSPECT-ANALYST-001, M4 백로그) |
| (출력 채널) | 브리핑 / 추천 / 알림 / 매매일지 | — | `pipelines/` + `server/api/` + `server/telegram/` |

**흐름**: 분석가 9 → 전략가 → 계좌관리자 → 회고분석가 (분석·전략·계좌 등 보완 + 신규 부서 제안). 신규 부서 효율성 판단 = 회고분석가의 영역 자체 (정의·위계·검증 레이어 갖춤).

지식부 9 = 원칙부(`principles/`) · 트레이딩부(`trading/`) · 시장매크로부(`market_macro/`) · 종목선정부(`stock_selection/`) · 종목분석부(`stock-analysis/`) · 자산복리부(`wealth_compounding/`) · 매매저널부(`trading_journal/`) · 수급분석부(`flow_analysis/`) · 뉴스부(`news/`).
분석가 9 = 원칙수호자 · 트레이더 · 시장상태분석가 · 종목선정가 · 종목분석가 · 자산전략가 · 매매저널리스트 · 수급분석가 · 뉴스큐레이터 (1:1 매핑).
전략가 2+ = Track A 중장기 수익금 게임 (자본 70-80%·승률 70%+) / Track B 단기 손익비 게임 (자본 20-30%·R/R 1.5:1+). plugin 확장 가능.

지식부 9 = 원칙부(`principles/`) · 트레이딩부(`trading/`) · 시장매크로부(`market_macro/`) · 종목선정부(`stock_selection/`) · 종목분석부(`stock-analysis/`) · 자산복리부(`wealth_compounding/`) · 매매저널부(`trading_journal/`) · 수급분석부(`flow_analysis/`) · 뉴스부(`news/`).
분석가 9 = 원칙수호자 · 트레이더 · 시장상태분석가 · 종목선정가 · 종목분석가 · 자산전략가 · 매매저널리스트 · 수급분석가 · 뉴스큐레이터 (1:1 매핑).
plugin 패턴: 새 지식부/분석가/전략가는 폴더 + manifest 드롭만으로 추가. 분화는 운용 중 trigger 시.

## 최상위 구조
```
pipelines/    — 🔀 시간대별 실행 단위 (Layer 5 의 한 형태). manifest.yaml 에 stages + schedule.
agents/       — 🧠 페르소나 보관소 (Layer 2~4). M3 부터 점진 신설.
knowledge/    — 📚 지식부 (Layer 1). canon/<dept>/<category>/.
collectors/   — 📥 공용 수집 모듈 (KIS/KRX/yfinance 호출).
checkers/     — ✅ 순수 규칙 체커 (LLM 없음).
connectors/   — 🔌 외부 API 어댑터 (KIS/KRX/...).
mcp-servers/  — 🔌 MCP 프로토콜 서버. 별도 프로세스.
server/       — 🖥️ 상주 런타임 (FastAPI + APScheduler + 텔레그램 봇). 프로세스 1개.
webapp/       — 🌐 UI (Next.js). server/api를 fetch.
core/         — 🧱 공유 라이브러리 (db/contracts/llm/memory/knowledge/config/notification).
docs/         — 📘 사람용 문서 (규약 + SPEC + 도메인).
```

## 작업 전 반드시 읽어야 할 것
1. **docs/a_wanted/user_want_spec.md** — 이 프로젝트의 본질(사용자가 원하는 것). 매 세션 초반에 반드시 읽어 방향이 본질에서 벗어나지 않는지 점검.
2. **docs/RESUME.md** — 현재 상태판. 마지막 세션이 어디까지 했고 다음 Top 3가 무엇인지.
3. **docs/STRUCTURE.md** — 폴더 규약의 원천. 파일을 어디에 둘지 결정할 때 항상 참조.
4. **docs/WORKFLOW.md** — SDD 사이클 (SPEC → 코드 → 테스트 → 도메인 문서).
5. **docs/CONTRACTS.md** — 팀 간 메시지 계약 (StandardOutput 스키마).
6. **작업 대상 SPEC** — frontmatter의 `generates` 에 명시된 경로에만 파일 생성.

## 세션 연속성 (중요)
사용자는 세션 간격(몇 시간~며칠)이 있어 맥락 단절이 일어난다. 다음 규칙으로 연속성 유지:
- **세션 시작 시**: `/resume` 명령을 권장. 자동으로 `docs/a_wanted/user_want_spec.md`(본질) + `docs/RESUME.md`(상태) + `docs/c_worked/` 최신 로그를 읽고 플랜모드로 브리핑 → 오늘 할 일 인터뷰.
- **의미 있는 작업 완료 후**: `/wrap-up` 명령을 권장. 이번 세션을 `docs/c_worked/YYYY-MM-DD_<slug>.md` 로 저장 + `docs/RESUME.md` 갱신.
- 사용자가 이 명령을 안 불러도 **세션 시작 시 최소한 `docs/a_wanted/user_want_spec.md` 와 `docs/RESUME.md` 는 읽고 시작할 것.**

## 절대 원칙
1. **파이프라인 간 코드 import 금지**. 통신은 DB 테이블(`team_outputs` / `briefing_parts`)과 계약 JSON 으로만. (근거: 시점 일관성·frame 응집·debugging — 본질·trade-off 는 [docs/AGENT-ARCHITECTURE.md](docs/AGENT-ARCHITECTURE.md) 참조)
2. **SPEC 없이 코드 쓰지 말 것**. 스펙이 없으면 먼저 `/spec-interview` 로 작성.
3. **SPEC frontmatter의 `generates` 경로에만 파일 생성**. 다른 위치에 만들면 validate가 실패.
4. **표준 파이프라인 레이아웃 100% 준수**. `__init__.py`, `manifest.yaml`, `stages/` 는 필수.
5. **파이썬: pathlib 전용**, 문자열 경로 조합 금지. 모든 함수에 타입 힌트.
6. **크로스 플랫폼**: .sh 금지, .bat 금지, justfile 사용. Windows 경로 고려.
7. **DB**: SQLite, ON CONFLICT REPLACE (멱등성 보장).
8. **환경변수**: 모든 시크릿은 .env. 하드코딩 금지. python-dotenv로 로드.
9. **동적 설정**: config/runtime.yaml 수정은 재시작 없이 반영 (watchdog 감지). 하드코딩 금지.
10. **Telegram 미설정 시 파일 폴백**: `data/notifications/*.jsonl` 에 기록하여 로컬 개발 지원.
11. **기존 도메인 재사용 우선 (신규 확장 가드)**: 신규 테이블·`collectors/*.py`·`connectors/*.py`·API 라우트를 만들기 **전에** 반드시 [docs/DATA-MAP.md](docs/DATA-MAP.md) 를 읽어 같은 도메인이 이미 있는지 확인. 있으면 **컬럼/필드 확장**(신규 금지). 신규를 택하려면 SPEC 본문 "재사용 영향도" 에 DB→backend→frontend 파급을 통찰하고 **왜 확장이 불가한지** 입증. (근거: AI 개발은 "안 보이면 새로 만든다"가 기본값 — 2026-06-12 `commodity_futures_snapshot` 과잉 신설을 `us_macro_snapshot` 컬럼 확장으로 정정한 전례.)

## 운영 환경 (Environment)
- 플랫폼: **Windows**. 패키지 매니저는 `winget` (NOT brew). PowerShell 실행 정책 조정 필요할 수 있음.
- 도구: `uv` (Python), `just` (task runner), `npm` (Node — pnpm은 Windows에서 EPERM 빈발).

## 워크트리 (Worktree) 규칙
- 워크트리는 메인 레포의 `.env` 와 venv 를 **공유**. 격리된 venv 만들지 말 것.
- 파이프라인 실행 전 공유 venv 에 의존성이 설치되어 있는지 항상 확인.
- 코드 수정 후 서버 프로세스 **재시작**. hot reload 신뢰하지 말 것 — stale 프로세스가 옛 코드로 응답해 중복 LLM 호출이 발생한 사고 전적 있음.

## 테스트 안전 (Testing Safety)
- 테스트는 **절대로 외부 API (Telegram, KIS, Gemini, Anthropic) 실호출 금지**. mock 필수.
- pytest 호출 시 `TESTING=1` 환경변수 명시 — `.claude/hooks/pytest_safety.ps1` PreToolUse hook 이 미지정 시 차단.
  - PowerShell: `$env:TESTING='1'; pytest ...`
  - POSIX bash: `TESTING=1 pytest ...`
- 테스트/`conftest.py` 가 `TESTING=1` 시 실 API 호출을 mock 처리하도록 보장.
- 중복 LLM 호출 방지: `llm_call_cache` 테이블 DB 캐시 활용.
- 사고 전적: 테스트가 mock 없이 실 BOT_TOKEN 으로 사용자 카톡에 스팸 발송한 적 있음 (BRIEFING-ON-DEMAND-001 v1).

## Claude 도구 사용 규율 (Tool Usage Discipline)
- 단순 파일 read 에 Explore/Task 서브에이전트 쓰지 말 것 — Read 직접 호출.
- LLM 파이프라인 검증 시 캐시된 응답을 보려면 `/resend`, 새 호출이 필요하면 `/run?force=true`. 혼동 금지.
- 사용자가 작업 중간에 개념적 질문을 던지면 **곧장 구현 계속하지 말고 의도 먼저 확인**.
- **Bash 명령에 `cd <레포> && ...` 프리픽스 금지** (서브에이전트 포함). 작업 디렉터리는 호출 간 유지되고 시작점이 레포 루트라 cd 불필요. compound `cd && x` 는 권한 매칭을 깨서(문자열이 `cd` 로 시작 → `Bash(uv *)` 등 allowlist 미스) **불필요한 권한 프롬프트**를 유발한다. 그냥 bare 명령(`uv run ...`, `git ...`)을 직접 실행.
  - 다른 디렉터리가 필요하면: ① **경로 인자·도구 플래그 우선** (`git -C <dir>`, `pytest <경로>`, `ls "<절대경로>"`) ② 정 필요하면 **독립 `cd <abs>` 를 별도 호출**로 (cd 자동 허용 + cwd 유지). compound 로 묶지 말 것.
  - 환경변수 프리픽스는 allowlist 에 맞는 형태로 (`TESTING=1 uv ...`, `PYTHONIOENCODING=utf-8 uv ...`, 둘 다면 `TESTING=1 PYTHONIOENCODING=utf-8 uv ...`).

## 런타임 아키텍처 핵심
- **단일 Python 프로세스** = FastAPI + APScheduler + asyncio 병렬 파이프라인 실행
- 파이프라인 실행: `asyncio.gather(*[pipeline.run() for pipeline in active_pipelines])`
- 판단은 LLM이 하되, 데이터 수집·지표 계산은 순수 코드가 한다.
- 서버가 죽었다 살아나도 맥락 유지: Gap Filler + Memory Layer + Knowledge Layer
- **Memory Layer** (`core/memory/`): 분석가/전략가 판단의 시계열 맥락 보존, 일/주/월 롤업, 멱등성 캐시.
- **Knowledge Layer** (`core/knowledge/`): 9 지식부 자료 (`knowledge/canon/<dept>/<category>/`) 항상 주입 + Reference(Chroma RAG).

## 분석가/전략가 통신 계약 (요약)
각 분석가는 StandardOutput JSON 을 반환하고 `team_outputs` 테이블에 저장 (전략가가 종합 시 이 행들을 read).
```json
{
  "team_id": "principle_guardian",
  "timestamp": "...",
  "target": "global",
  "verdict": "violation" | "compliant" | ...,
  "confidence": 0-100,
  "reasons": ["..."],
  "data": { /* 분석가별 고유 데이터 */ },
  "contract_version": "1.0"
}
```
상세는 `docs/CONTRACTS.md` 및 `core/contracts/team_output.py` 참조. (`team_outputs` 테이블명/계약 키는 legacy 호환을 위해 유지.)

## 투자 7계명 (불변)
1. 총 투자비중 80% 이하 유지
2. 단일 종목 비중 15% 이하
3. 트레이딩 비중 20% 이하
4. 손절선 없이 진입하지 않음
5. 단일 지표로 판단하지 않음 (최소 3개 교차 검증)
6. 데이터 없이 추측하지 않음
7. 감정(FOMO/공포)으로 매매하지 않음

## KIS API 안전 규칙 (향후 KIS 통합 시)
- 주문 관련 코드 작성 시 반드시 `KIS_IS_PAPER=true` 확인.
- OAuth 토큰은 메모리에만 보관. 파일 저장 절대 금지. 만료 전 자동 갱신.
- API 호출 간격: 최소 100ms. 초당 최대 20건.

## 기능 구현 절차 (SDD)
1. `docs/specs/` 의 해당 SPEC을 먼저 읽는다.
2. 대상 파이프라인/분석가의 manifest.yaml + persona.md(있다면) 를 읽는다.
3. SPEC의 frontmatter `generates` 경로에만 파일을 만든다.
4. 테스트를 작성한다 (`tests/test_*.py`).
5. 기존 테스트가 통과하는지 확인한다 (회귀 방지).
6. `scripts/generate_domain_doc.py` 로 도메인 문서 생성.
7. `scripts/validate.py` 통과 확인.

## 전략가 라우팅 (Layer 3, STRATEGY-TRACK-001)
- **Track A (중장기 수익금 게임)**: stock_picker (S-Score) + stock_analyst (α, F1~F5) + wealth_strategist + principle_guardian + market_state_analyzer + flow_analyzer (F-Score) → 권고 (목표가 3단·stop_loss·R/R)
- **Track B (단기 손익비 게임)**: stock_picker (buy_score) + trader (T-Score + 트리거 6) + market_state_analyzer (Distribution kill switch) + flow_analyzer (F-Score) + principle_guardian (트레이딩 비중 20% 한도) → 권고 (진입가·trailing stop·R/R floor)
- **단타·중장기 (지수 투자) 빼고 A/B 만** (사용자 결정 2026-05-17). 향후 trackplugin 확장 가능 (`agents/strategists/<new_track>/` 드롭, 코드 변경 0)
> 라우팅 = 전략가 manifest 의 `input_routing` 블록 (명시 단축어 우선 → auto.conditions → fallback). 사용자 입력 `long: / swing: / both:` 단축어 + 종목 메타로 A/B/Both 자동 분기.

## LLM 호출 규칙 (런타임)
- 데이터 수집·계산은 코드, 판단·해석은 LLM API 호출.
- 기본 모델: Claude Sonnet 4 (`ANTHROPIC_API_KEY` 필요).
- LLM 호출 시 반드시 해당 분석가의 persona.md + 본인 지식부의 canon md 주입 (`load_shared_canon()` 이 9 지식부 재귀 로드).
- **Anthropic Prompt Caching 활용** (system 부분 캐시로 비용 90% 절감).
- 호출 결과는 `team_memory` + `llm_call_cache` 테이블에 저장.
- 멱등성: `input_hash = sha256(input + context_snapshot + model + contract_version)`.
- 호출 실패 시 이전 판단 유지, 크래시 금지.
- API 키 미설정 시 mock 응답으로 폴백 (개발/CI 지원).

## 상세 참조 문서
- [docs/STRUCTURE.md](docs/STRUCTURE.md) — 폴더 규약의 원천
- [docs/WORKFLOW.md](docs/WORKFLOW.md) — SDD 사이클
- [docs/CONTRACTS.md](docs/CONTRACTS.md) — 메시지/DB 계약
- [docs/RUNTIME.md](docs/RUNTIME.md) — 서버/스케줄러/메모리/지식 동작
- [docs/stock-advisor-architecture-guide.md](docs/raw_docs/stock-advisor-architecture-guide.md) — 원본 전체 아키텍처
- [docs/llm-runtime-architecture.md](docs/raw_docs/llm-runtime-architecture.md) — LLM 런타임 상세
