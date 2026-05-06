---
date: 2026-05-06
topic: M3 — 자산전략가 1명 추론부 조회 인터페이스 (CLI + REPL + webapp) 신설 + end-to-end 가동
status: completed
plan_file: C:\Users\HOME\.claude\plans\streamed-swinging-haven.md
---

# 2026-05-06 · M3 자산전략가 추론부 조회 인터페이스

## 배경

R4 (자산복리부 canon 19,166 chars) 직후 M3 진입. 처음에는 "분석가 5명 일괄 분화" 로 가려 했으나 사용자가 두 번 본질 의구심을 던져 방향이 바뀜:
- (1) "RAG·데이터로 LLM 응답 과정을 구축하고 품질을 알고 싶다" → 검증 우선 → 점진 확산
- (2) "추론부 조회는 기존 단순 정보 알림 받기 파이프라인과 다르다" → 별도 호출 흐름. `market_briefing_pre` 안에 끼워넣지 않음
- (3) 멀티턴 대화 가능성 + 메모리 위치 + 누적 토큰 우려 + JSONL 회전 우려 4축 의구심 모두 plan 안에서 해소

핵심 판단: 인터페이스 차원에서 **분석가는 알림 파이프라인이 아닌 별도 호출 단위**. 핵심 함수 `core/inference/run_analyst.py` 1개를 만들고 CLI/REPL/FastAPI/webapp 모두 wrap.

## 한 일

### 분석가 정체성 (Layer 2 — wealth_strategist)
- `agents/analysts/wealth_strategist/persona.md` — 신규. R4 canon 톤. framework 우선·imperatives 메타 가이드·hedging 금지·박종훈 표현 그대로
- `agents/analysts/wealth_strategist/manifest.yaml` — 신규. `reads:[wealth_compounding]` + max_tokens 4000 + temp 0.4 + response_rules

### 핵심 호출 함수
- `core/inference/__init__.py` — 신규. AnalystSpec/Response/run_analyst export
- `core/inference/run_analyst.py` — 신규. `run_analyst(analyst_id, messages, ...)` 멀티턴 messages 배열 수용. manifest 로드 → `build_pipeline_prompt(rag_dept, query_for_rag, response_rules)` → `call_llm` → metadata 산출 (system char, RAG chunks, cache tokens, cost, latency)

### CLI 인터페이스
- `scripts/chat_analyst.py` — 신규 REPL. `>` prompt + 멀티턴 누적 + `/exit` `/clear` `/save` 명령 + 매 턴 metadata 출력 + 누적 토큰 200K 한계 가시화 + JSONL 자동 저장. stdin/stdout/stderr utf-8 reconfigure (Windows cp949 함정 회피) + surrogate normalize
- `scripts/ask_analyst.py` — 신규. 단일 턴 wrap. JSONL 1 turn 저장
- `justfile` — `chat <id>` + `ask <id> <query>` 레시피 추가

### 웹 인터페이스
- `server/api/analyst_chat.py` — 신규. `POST /api/analysts/{id}/chat` (멀티턴) + `GET /api/analysts/{id}` (메타). pydantic ChatRequest/Response
- `server/main.py` — analyst_chat router include 추가
- `webapp/src/app/analyst-chat/page.tsx` — 신규. textarea + Ctrl+Enter 전송 + 멀티턴 누적 + 매 턴 metadata 박스 + `/clear` + 누적 토큰·비용 가시화. messages state 클라이언트 보관
- `webapp/src/app/page.tsx` — 메인 페이지에 "Layer 2 추론부 데모" 카드 링크 추가
- `.gitignore` — `data/analyst_queries/` 추가

## 검증 결과
- ✅ pytest 60 passed (회귀 없음, 기존 알림 파이프라인 영향 0)
- ✅ analyst spec 로딩 — id/reads/persona path/model 모두 정상
- ✅ system prompt build — blocks 4 (canon + persona + RAG + rules) / cache_breakpoints 2 / system 23,145 chars / RAG chunks 3 (top_k=3)
- ✅ `just ask wealth_strategist "지금 자산 비중을 어떻게 가져가야 할까?"` 1회 실 LLM — Gemini Flash Lite auto-fallback ($0.0011), 8.4s, canon 명제 ID 정확 인용 (M1·M2·M3 / C1·C3·C4·C5 / I2~I6), 박종훈 표현 그대로 ("펀치 카드"·"공포의 톱니바퀴"·I6 3년 평균가)
- ✅ Next.js build 성공 — `/analyst-chat` 2.63 kB compile
- ✅ 두 서버 동시 띄움 (uvicorn 8000 + next 3000) → 사용자 직접 멀티턴 검증 OK ("기능 적으론 잘 됨")

## 의도적으로 안 한 것
- **나머지 4명 분석가 분화** — 1명 검증 후 패턴 복사 (다음 세션)
- **매매일지 SPEC `BRIEFING-JOURNAL-001` 골격** — 분량 분리
- **텔레그램 `/ask` 명령 wrap** — 1명 검증 후
- **배치 자동 트리거 (T2) + team_outputs DB 저장** — 인터랙티브 단계 후
- **JSONL → SQLite 마이그** — 5K 파일 임계점 도달 시 (분석가 5명 분화 직전)
- **`team_id → dept_id` rename** — 회귀 리스크, 별도 세션
- **legacy `compose.py` dead code 청소** — `build_system_prompt`/`load_canon`/`load_persona` 호출처 0
- **자동 컴팩트 (50+ turn 압축)** — 백로그
- **chat REPL stdin pipe 자동화 fix** — PowerShell here-string 한국어 인코딩 깨짐. 사용자 콘솔 직접 입력은 OK (stdin reconfigure 적용됨)

## 이번에 굳힌 판단

- **추론부 조회 ≠ 알림 파이프라인** — 별도 호출 흐름 (CLI/REPL/FastAPI/webapp). 기존 `market_briefing_pre`/`market_briefing_now` 알림 파이프라인 안에 분석가 끼워넣지 않음
- **인터페이스 핵심 함수 1개 (`core/inference/run_analyst.py`)** — CLI/REPL/FastAPI/webapp 모두 wrap. 후속 텔레그램·MCP 도 같은 패턴
- **검증 우선 → 점진 확산** — 5명 일괄 분화는 미검증 패턴 5번 복사 위험. 1명 가동 → 패턴 안정 → 4명 적용
- **메모리 두 차원 분리** — 대화 메모리 (한 conversation 안 multi-turn messages, REPL 누적 + JSONL 디스크) vs 에이전트 시계열 메모리 (`core/memory/` SQLite, system prompt 자동 주입). API 서버는 stateless (Anthropic 영구 보관 X) — 모든 대화 통제권 = 로컬
- **JSONL retention 단계** — A: 그대로 (검증 단계, 1년 ~22MB) → B: 매월 폴더 + 90일 retention (분석가 5명 분화 직전, 5K 파일 임계) → C: SQLite 마이그 (50K 파일, 장기)
- **응답 원론·반복 패턴 발견** — 사용자 직접 검증 결과: canon 19K 압도 + persona "framework 우선" 톤 + 시장 데이터 부재 + temp 0.4 → 추상 명제 인용 중심. 다음 세션 핵심 과제

## 맥락 재진입 힌트
- `just chat wealth_strategist` / `just ask wealth_strategist "<질문>"` / 웹 = `http://localhost:3000/analyst-chat`
- 두 서버 = `just server` (8000) + `just webapp-dev` (3000). webapp 메인 페이지에 카드 링크 있음
- 실 LLM 호출 시 ANTHROPIC_API_KEY 있어도 Gemini fallback 일어남 (이유 미확인 — config provider 검증 필요할 수도)
- canon 자동 주입 char 수 검증: `uv run python -c "import sys; sys.stdout.reconfigure(encoding='utf-8'); from core.knowledge.compose import load_shared_canon; print(len(load_shared_canon()))"` → 19,166

## 세션 중 실 비용
- ask 1회 실 LLM = $0.0011 (Gemini auto-fallback)
- 두 서버 + 검증 = ~0
- **합계 < $0.01**

## 다음에 이어서 할 작업 (우선순위)

1. **분석가 응답 원론·반복 패턴 개선** (중요, 1.5~2.5h)
   - 사용자가 직접 검증 시 발견: canon/persona 가 압도적 → framework 명제 나열만 반복
   - 단계 1 (5분): persona 톤 직설 강화 + response_rules 의 cited 강제 제거 + temp 0.4 → 0.7
   - 단계 2 (1~1.5h): 시장 데이터 주입 — `collectors/` 의 KIS/KRX 스냅샷 (환율·지수·VIX·수급) 을 user 메시지 또는 system 컨텍스트에 자동 첨부 → framework × 실시간 데이터 결합
   - user_want_spec "분석팀에 도움이 되는 raw data" 흐름의 첫 진입

2. **나머지 4명 분석가 분화** (M3 완성, 2~3h)
   - `agents/analysts/{principle_guardian,trade_coach,stock_analyst,news_curator}/persona.md + manifest.yaml` — 1명 가동 패턴 복사
   - 매매코치 추가하면 자산전략가와 응답 톤 비교로 분화 의미 즉시 입증
   - canon 19K 가 5명에 모두 깔리지만 `reads:` 매핑은 분석가별 = 학습부별 다름

3. **JSONL → 매월 폴더 + 90일 retention 도입** (5명 분화 직전, 30분)
   - `data/analyst_queries/<id>/<YYYY-MM>/<dt>.jsonl` 폴더 분리 + cron retention
   - 5K 파일 임계 도달 전 선조치. RESUME backlog 의 "Retention SPEC" 흐름 흡수 가능

## 커밋 상태
이번 wrap-up 에서 2 커밋 예정:
1. `feat(inference): M3 자산전략가 추론부 조회 인터페이스 (CLI/REPL/webapp)` — 신규 파일 + 수정 파일
2. `docs: wrap-up 2026-05-06 M3 자산전략가 1명 추론부 trial` — c_worked + RESUME + SESSIONS + memory
