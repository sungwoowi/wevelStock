# wevelStock — AI 에이전트 협업 주식 분석 시스템 (루트 컨텍스트)

## 프로젝트 개요
멀티팀 AI 주식 분석 & 매매가이드 시스템. 각 팀이 독립 분석 → 오케스트레이터가 종합 → 최종 투자 가이드 생성.
크로스 플랫폼(Mac + Windows). DB: SQLite. API: 한국투자증권(KIS) OpenAPI 예정.
현재 토대 구축 단계 — 첫 두 팀(principles, daily-briefing) + server 런타임 + 1페이지 데모 완성이 목표.

## 최상위 구조 (6개 역할)
```
teams/        — 🤖 AI 에이전트 팀 (분석/판단). 각 팀은 manifest.yaml에 schedule 선언.
mcp-servers/  — 🔌 외부 세계 연결 (KIS, FRED, Telegram 발송). 별도 MCP 프로세스.
server/       — 🖥️ 상주 런타임 (FastAPI + APScheduler + 오케스트레이터). 프로세스 1개.
webapp/       — 🌐 UI (Next.js, 순수 프론트엔드). server/api를 fetch로 호출.
core/         — 🧱 공유 라이브러리 (db/contracts/llm/memory/knowledge/config/notification).
docs/         — 📘 사람용 문서 (규약 + SPEC + 도메인).
```

## 작업 전 반드시 읽어야 할 것
1. **docs/a_wanted/user_want_spec.md** — 이 프로젝트의 본질(사용자가 원하는 것). 매 세션 초반에 반드시 읽어 방향이 본질에서 벗어나지 않는지 점검.
2. **docs/RESUME.md** — 현재 상태판. 마지막 세션이 어디까지 했고 다음 Top 3가 무엇인지.
3. **docs/STRUCTURE.md** — 폴더 규약의 원천. 파일을 어디에 둘지 결정할 때 항상 참조.
4. **docs/WORKFLOW.md** — SDD 사이클 (SPEC → 코드 → 테스트 → 도메인 문서).
5. **docs/CONTRACTS.md** — 팀 간 메시지 계약 (StandardOutput 스키마).
6. **작업 대상 팀의 CLAUDE.md** — teams/<team>/CLAUDE.md 는 해당 팀 맥락.
7. **작업 대상 SPEC** — frontmatter의 `generates` 에 명시된 경로에만 파일 생성.

## 세션 연속성 (중요)
사용자는 세션 간격(몇 시간~며칠)이 있어 맥락 단절이 일어난다. 다음 규칙으로 연속성 유지:
- **세션 시작 시**: `/resume` 명령을 권장. 자동으로 `docs/a_wanted/user_want_spec.md`(본질) + `docs/RESUME.md`(상태) + `docs/c_worked/` 최신 로그를 읽고 플랜모드로 브리핑 → 오늘 할 일 인터뷰.
- **의미 있는 작업 완료 후**: `/wrap-up` 명령을 권장. 이번 세션을 `docs/c_worked/YYYY-MM-DD_<slug>.md` 로 저장 + `docs/RESUME.md` 갱신.
- 사용자가 이 명령을 안 불러도 **세션 시작 시 최소한 `docs/a_wanted/user_want_spec.md` 와 `docs/RESUME.md` 는 읽고 시작할 것.**

## 절대 원칙
1. **팀 간 코드 import 금지**. 팀끼리는 DB 테이블(`team_outputs`)과 표준 JSON 메시지로만 통신.
2. **SPEC 없이 코드 쓰지 말 것**. 스펙이 없으면 먼저 `/spec-interview` 로 작성.
3. **SPEC frontmatter의 `generates` 경로에만 파일 생성**. 다른 위치에 만들면 validate가 실패.
4. **표준 팀 레이아웃 100% 준수**. CLAUDE.md, manifest.yaml, src/agent.py 는 필수.
5. **파이썬: pathlib 전용**, 문자열 경로 조합 금지. 모든 함수에 타입 힌트.
6. **크로스 플랫폼**: .sh 금지, .bat 금지, justfile 사용. Windows 경로 고려.
7. **DB**: SQLite, ON CONFLICT REPLACE (멱등성 보장).
8. **환경변수**: 모든 시크릿은 .env. 하드코딩 금지. python-dotenv로 로드.
9. **동적 설정**: config/runtime.yaml 수정은 재시작 없이 반영 (watchdog 감지). 하드코딩 금지.
10. **Telegram 미설정 시 파일 폴백**: `data/notifications/*.jsonl` 에 기록하여 로컬 개발 지원.

## 런타임 아키텍처 핵심
- **단일 Python 프로세스** = FastAPI + APScheduler + asyncio 병렬 팀 실행
- 팀 실행: `asyncio.gather(*[team.run() for team in active_teams])`
- 판단은 LLM이 하되, 데이터 수집·지표 계산은 순수 코드가 한다.
- 서버가 죽었다 살아나도 맥락 유지: Gap Filler + Memory Layer + Knowledge Layer
- **Memory Layer** (`core/memory/`): 팀 판단의 시계열 맥락 보존, 일/주/월 롤업, 멱등성 캐시.
- **Knowledge Layer** (`core/knowledge/`): 팀별 학습 자료 = Canon(compiled.md, 항상 주입) + Reference(Chroma RAG).

## 팀 간 통신 계약 (요약)
모든 팀은 StandardOutput JSON을 반환하고 `team_outputs` 테이블에 저장.
```json
{
  "team_id": "principles",
  "timestamp": "...",
  "target": "global",
  "verdict": "violation" | "compliant" | ...,
  "confidence": 0-100,
  "reasons": ["..."],
  "data": { /* 팀별 고유 데이터 */ },
  "contract_version": "1.0"
}
```
상세는 `docs/CONTRACTS.md` 및 `core/contracts/team_output.py` 참조.

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
1. `teams/<team>/specs/` 또는 `docs/specs/` 의 해당 SPEC을 먼저 읽는다.
2. 대상 팀의 CLAUDE.md, persona.md(있다면), manifest.yaml 을 읽는다.
3. SPEC의 frontmatter `generates` 경로에만 파일을 만든다.
4. 테스트를 작성한다 (`tests/test_*.py`).
5. 기존 테스트가 통과하는지 확인한다 (회귀 방지).
6. `scripts/generate_domain_doc.py` 로 도메인 문서 생성.
7. `scripts/validate.py` 통과 확인.
8. 팀의 CHANGELOG.md 에 변경 이력 추가.

## 전략 라우팅 (병렬 운용, 추후 구현)
- 단타 트레이딩: 기술적분석팀 + 수급팀 → 당일 시그널
- 스윙 트레이딩: 기술적분석팀 + 수급팀 + 매크로팀 → 수일~수주
- 자산 투자: 매크로팀 + 기술적분석팀 + 원칙팀 → 장기 보유

## LLM 호출 규칙 (런타임)
- 데이터 수집·계산은 코드, 판단·해석은 LLM API 호출.
- 기본 모델: Claude Sonnet 4 (`ANTHROPIC_API_KEY` 필요).
- LLM 호출 시 반드시 해당 팀의 persona.md + compiled.md(Canon) 주입.
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
