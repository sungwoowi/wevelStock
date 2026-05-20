---
date: 2026-05-20
topic: ask_strategist/chat_strategist httpx wrap + operational_safeguards SPEC 정정 (cycle 7)
status: completed
plan_file: C:\Users\HOME\.claude\plans\composed-watching-leaf.md
---

# 2026-05-20 · ask_strategist httpx wrap + SPEC 정정 (cycle 7)

## 배경

cycle 6.5 wrap-up 직후 새 사이클. RESUME Top 2+3 묶음 commit — 회장 핑퐁 [22] 권유
("INFRA-RUNTIME-EFFICIENCY-001 진입 시 첫 commit 으로 묶음") 그대로 실현.
본 사이클 = **MS3 production smoke 완전 통과 베이스라인 위에서 운영 인프라 정합 정정**
(production behavior 변화 0, 코드/SPEC 정합 향상). 핵심 판단: cycle 3 의 임시 위임 명시
(trader persona 에 박힌 principle_guardian 권위 위임) 은 4 사이클간 잔존했고 cycle 4 의
ask_analyst httpx wrap 도 strategist 측에 미러되지 못해 cycle 3 메모리 압박 위험 잔존.
양쪽 모두 같은 commit 으로 정식 마무리.

## 한 일

### Part A — httpx wrap (INFRA-RUNTIME-EFFICIENCY-001 v3 patch)
- `scripts/ask_strategist.py` — in-process `run_strategist` 임포트 제거 → `POST /api/strategists/{id}/chat` httpx 호출 (ask_analyst.py L78-149 패턴 미러). target/provider/messages 필드 + REQUEST_TIMEOUT_SECONDS 180s + WEVELSTOCK_SERVER_URL env default 127.0.0.1:8000. ConnectError → exit 3 + "just server" 안내, ReadTimeout → exit 4, 404 → exit 2, 5xx → exit 1. JSONL 저장 (target 필드 포함) + `_format_metadata` 의 track/target/scores published/missing 라벨 보존.
- `scripts/chat_strategist.py` — 같은 패턴 + chat_analyst REPL 패턴 미러. `/exit /clear /save /target <ticker>` 4 명령 보존 (target 변경 시 다음 turn payload 갱신). messages 배열 누적 + 매 POST 마다 전체 history (stateless server). 누적 토큰 가시화 + JSONL turn 마다 추가.
- `tests/test_ask_strategist_http.py` — 신규 6 케이스. `_MockClient` 패턴으로 httpx.AsyncClient 가로채기. success(200) 정상 metadata + track/target/scores 라벨 / ConnectError → exit 3 / 404 → exit 2 / 500 → exit 1 / target+provider forwarding / no-provider default-target=global.

### Part B — operational_safeguards SPEC 정정
- `docs/specs/ANALYST-PERSONAS-001-nine-analyst-portable-personas.md` L347 — `trader` 행 canon_categories 에서 `trading/operational_safeguards` 제거 + `principle_guardian` 행에 추가. canon 파일 위치 (`knowledge/canon/trading/operational_safeguards/`) 는 그대로 유지 (canon_categories 키 형식 `<dept>/<category>` 가 dept 정보를 키 안에 박는 구조 → 파일 이동 불필요. frontmatter `analyst: principle_guardian` 와 정합 회복).
- `agents/analysts/trader/manifest.yaml` + `persona.md` — cycle 3 임시 박은 "principle_guardian 권위 위임 명시" 잔재 5 위치 정리. canon_categories 6→5 (operational_safeguards 제거), 자료원 list / Inputs § / Knowledge Categories § / Reasoning Doctrine / Anti-patterns / Cross-Agent Boundaries / response_rules 모두 cycle 7 정정 키워드로 갱신.
- `agents/analysts/principle_guardian/manifest.yaml` + `persona.md` — canon_categories 3→4 (trading/operational_safeguards 정식 포함). 자료원 4 § + Knowledge Categories § 의 "manifest 에 추가 X" 잔재 → "정식 포함" 갱신.
- `tests/test_data_analysts_v2.py` — `EXPECTED_CANON_CATEGORIES` 매핑 갱신 (principle_guardian 4 / trader 5) + `test_trader_operational_safeguards_delegation` 삭제 + 신규 `test_principle_guardian_owns_operational_safeguards` (3-way 검증: pg manifest 포함 + pg persona 명시 + trader manifest 제외).

## 검증 결과

- ✅ `tests/test_ask_strategist_http.py` 6 케이스 모두 통과 (신규)
- ✅ `tests/test_data_analysts_v2.py` 37 케이스 모두 통과 (회귀 0)
- ✅ 전체 pytest **379 → 385 passed** (+6 신규, 회귀 0)
- ✅ `scripts/validate.py` 0 errors, 1 warnings (teams/registry.yaml 부재 — 본 사이클 무관)
- ✅ Mock provider 수동 smoke (`ask_strategist track_a "Track A 본질이 무엇인지 짧게" --target 005930 --provider mock`): httpx 호출 정상 (서버 200) / metadata `track A · target 005930 · scores 0/6 (missing: stock_picker,stock_analyst,wealth_strategist,principle_guardian,market_state_analyzer,flow_analyzer)` / prompt 42,849 chars / ⚠ MOCK 라벨 / JSONL 저장 `data/strategist_queries/track_a/20260520-173431.jsonl` ✅

## 의도적으로 안 한 것

- **chat_strategist 수동 smoke** — REPL stdin pipe 자동화는 PowerShell 한국어 인코딩 깨짐 함정 (메모리 `chat REPL stdin pipe 자동화`). _post_chat 함수 패턴은 ask_strategist 와 공유 + tests 에서 충분 검증 → 사용자 수동 검증으로 충분.
- **claude_code provider silent HTTP 500 진단** (RESUME Top 1, cycle 6.5 신규 발견) — 본 사이클 스코프 밖 (Top 2+3 묶음 결정). 다음 사이클로.
- **frontmatter 일관성 자동 검증 스크립트** — validate.py 가 frontmatter 의 analyst 키 ↔ SPEC canon_categories 매핑 일관성을 잡지 않음. 본 사이클은 수동 검증 (실제 frontmatter read 후 매핑 정합 확인). 자동화는 별도 백로그.
- **`teams/registry.yaml` 부재 warning** — validate.py 가 매번 경고. legacy 호환 부채, 본 사이클 무관.

## 다음에 이어서 할 작업 (우선순위)

1. **claude_code provider silent HTTP 500 진단** (~0.3 세션) — cycle 6.5 신규 발견. body=`{"detail":"inference failed: "}` (메시지 빈 string). mock/gemini 는 정상이라 claude_code subprocess 특정 실패. `core/llm/claude_code_backend.py` 의 exception 메시지 캡처 보강 + server log stderr trace 확인 + CLI subprocess 종료 코드 캡처. `tests/test_claude_code_backend_error_capture.py` 신규. webapp 사용자 호출에선 이전에 작동한 적 있으므로 일시적 또는 burst 한도 가능성.

2. **`INFRA-FUNDAMENTAL-DATA-001` SPEC + 구현** (~2~3 세션) — MS3 완전 도달 차단점 (F5 분기 실적). stock_analyst v3 의 chart 흐름은 작동하나 F5 (분기 실적·EPS·매출 추세) 만 unknown 잔존. yfinance / DART / KIND backend 결합 SPEC 신설 + collectors/fundamentals.py + run_analyst 의 `fundamental_data_md` [4.5] 블록 신설. 새 SPEC 5 라운드 면담 필요.

3. **production UX 본질 구현** (~3 세션) — `feedback_webapp_production_ux.md` 의 "하나의 LLM 채팅창, 백단 0 노출". cycle 6.5 에서 종목명 매핑 35종 + ChatPane 분할이 첫 시동. 본격 구현 = 자연어 intent extractor (Layer 토글·agent_id·target·track 자동 추론) + Track Selector manifest input_routing 기반 자동 분기 + 종합 답변 형식. 9 분석가 + Track Selector 안정화 후 별도 사이클.

(추가 백로그: 자료 0 시드 5 분석가 페르소나 v2 완성 후 풀세트 production 검증 / Layer 4 계좌관리자 1+ N (M5) / Layer 5 회고분석가 본체 (M4 RETROSPECT-ANALYST-001) / GUIDANCE-ACCURACY-TRACKER-001 구현 / INFRA-US-MACRO-SNAPSHOT-001 / WAVE-ALPHA-001 / Memory Compression SPEC / scoring.py 정식 가중치 / KNOWLEDGE-SYNC-001 Phase 3 / 박종훈 Vol 2/3 OCR / xlsx 어댑터 sheet 별 분리)

## 맥락 재진입 힌트

- **httpx wrap 패턴**: scripts/{ask,chat}_strategist 는 in-process import 0 + httpx 호출. server 가 가동되어야 작동. 서버 미가동 시 exit 3 + "just server 실행" 안내. 환경변수 `WEVELSTOCK_SERVER_URL` 로 override 가능 (default 127.0.0.1:8000).
- **operational_safeguards canon 위치 vs 권위 분리**: canon 파일 위치 = `knowledge/canon/trading/operational_safeguards/` (cycle 7 후에도 그대로). 권위 = `principle_guardian` (frontmatter `analyst: principle_guardian` + manifest canon_categories + persona Knowledge Categories §). canon_categories key 형식 `<dept>/<category>` 가 dept 정보를 키 안에 박아 파일 이동 없이도 권위 이전 가능 — wevelStock RAG 인프라의 본질적 장점.
- **회장 핑퐁 [22] 권유 패턴**: 단독 작은 정정 (Top 3 = SPEC 표 정정) 을 큰 사이클 (Top 2 = httpx wrap) 에 묶음. 단일 commit 으로 SPEC + 코드 + 테스트 정합 동시 달성 + git history 정합. 다음에도 작은 부채 = 큰 commit 에 묶음 권유.

## 세션 중 실 비용

- mock provider 호출 1 회: $0
- 외부 LLM API 호출 0 회 (본 사이클은 SPEC + 코드 정정 + 테스트 검증으로만 진행)

## 커밋 상태

- cycle 7 코드 + SPEC commit: `78d8246` "feat+spec: ask_strategist/chat_strategist httpx wrap + operational_safeguards SPEC 정정 (cycle 7)" (9 files, +510/-138) → push 완료
- 본 wrap-up commit (c_worked + RESUME + SESSIONS) 진행 예정
