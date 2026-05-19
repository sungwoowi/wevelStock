---
date: 2026-05-19
topic: Phase 4 production 검증 + (c) 백로그 강등 + Top 2 양 트랙 production 호출 (cycle 4 풀세트 완결)
status: completed
plan_file: C:\Users\HOME\.claude\plans\mossy-conjuring-crystal.md
---

# 2026-05-19 · Phase 4 production 검증 + Top 2 양 트랙 — cycle 4 풀세트 완결

## 배경

cycle 4 partial (`2026-05-19_runtime-efficiency-spec-phase-b-a-4.md` + commit `7a49e65`) 직후 같은 세션에서 이어 진행. 사용자 선택 = 옵션 B (구현 추가 전 데이터로 (c) embedding_cache 필요성 검증). server 띄우고 실 호출로 메모리 충돌 해소 + latency 측정 + (c) 의사결정 후 Top 2 양 트랙 production 호출까지 완결.

## 한 일

### Phase 4 production 검증
- `just server` 띄움 — startup 정상 (scheduler_started jobs=7 / watcher_started / server_ready / embedding_function_init x8 = sync_all reconcile / telegram_bot_started). Free RAM 7.02 → 4.2 GB (BGE-m3 ~2.5GB + 기타).
- `just ask market_state_analyzer "지금 시장 어때 짧게"` → 17.4s · $0.0007 · gemini-2.5-flash · RAG 0 chunks · verdict=unknown · cited:[] · framework 밖 풀이. server 로그 `chroma_skip_empty dept=market_macro` 발화 = Phase 1 (b) 작동 확인.
- `just ask principle_guardian "단일 종목 18%, 짧게"` → 12.4s · $0.0013 · RAG 3 chunks · **verdict=violation** · cited=[C2, C6, OS2] · 근거 명제 풀이 3 줄 · **메모리 충돌 0** (cycle 3 `memory allocation failed` 본질 해소).
- 동일 query 재호출 11.9s → 0.5s 차이만 (LLM ~11s dominant).

### (c) embedding_cache 백로그 강등
- Phase 4 측정: retrieve query 임베딩 forward pass ~50ms / 응답 11.9s = **0.4% 미만**. (c) 메모리 효과도 X (BGE-m3 모델 점유는 (a) 가 이미 1 회 + 재사용).
- 결정: (c) = 본 SPEC 백로그. 별도 SPEC `INFRA-EMBEDDING-CACHE-001` 으로 다중 dept 동시 호출 또는 고빈도 알림 사이클이 실제 bottleneck 으로 나타날 때 진입.

### Top 2 양 트랙 production 호출
- `POST /api/strategists/track_a/chat` (target=005930, "long: 삼성전자") → 74s · $0.2331 · claude_code (gemini 503 fallback) · RAG 3 chunks · verdict=wait · cited=[M2, M3] · M3 인계점 명시 ("USD/KRW 1,507 = M3 인계점 구간"). analyst_published=0/6 정직 인정.
- `POST /api/strategists/track_b/chat` (target=005930, "swing: 삼성전자") → 71s · $0.1921 · claude_code · RAG 0 chunks (trading dept reference 미인덱싱, `chroma_skip_empty dept=trading` 발화) · verdict=wait · cited:[] · snapshot 적극 활용 ("외인 -5.72조 → 심법 2 수급 원칙", "SOX -2.47% → Distribution Day 누적 가능"). analyst_published=0/5 정직 인정.
- server 종료 + 메모리 회수.

### 새 발견 2 가지 (SPEC 정정 + 백로그)
1. **`trading` dept chroma chunks = 0** — SPEC v2 자동 분기 표가 trader=RAG ON 으로 박혀있었으나 실측 OFF. 정정: trader 의 trading canon md 2 는 system 블록 주입, RAG (reference chunks) 는 OFF. SPEC v2 표 + 본문 "canon md vs chroma chunks 구분" 설명 추가.
2. **`ask_strategist`/`chat_strategist` 가 in-process** — Phase 2 (a) httpx wrap 누락. cycle 3 같은 메모리 압박 위험이 strategist CLI 호출에 잔존. 본 검증은 `httpx.post` 임시 직접 호출로 우회. **SPEC v3 patch** 또는 후속 SPEC 으로 ask_strategist/chat_strategist 도 동일 wrap 필요.

### 갱신된 파일
- `docs/specs/INFRA-RUNTIME-EFFICIENCY-001-runtime-efficiency.md` — v1 → v2: status=implemented, frontmatter modifies 실제 파일 4 개로 정정, 단계별 진입 표에 Phase 4 실측 결과 + (c) 백로그 강등 근거 박음, 자동 분기 9 분석가 표 trader 행 정정 + "canon md vs chroma chunks 구분" 설명.
- `docs/RESUME.md` — 현재 위치 = MS0 도달. Top 1 = 양 트랙 검증 (본 cycle 4 후속) → 본 cycle 에서 끝, 다음 사이클 Top 1 = stock_analyst v3 + INFRA-CHART-DATA-001 묶음.
- `~/.claude/projects/.../memory/project_runtime_efficiency_blocker.md` — 본질 제약 해소 상태 + Phase 결과 표 + (c) 백로그 근거 + ask_strategist 잔여 본문 갱신.
- `~/.claude/projects/.../memory/MEMORY.md` — 인덱스 1 줄 갱신.

## 검증 결과

- ✅ Phase 1 (b) 실측 작동 — server 로그 `chroma_skip_empty dept=market_macro/trading` 2 회 발화
- ✅ Phase 2 (a) 실측 작동 — server 안 BGE-m3 1 회 로딩 + lru_cache 재사용, 2 회차 호출 0.5s 차이만
- ✅ Phase 4 — `principle_guardian` (cycle 3 충돌 분석가) 정상 응답 + 메모리 충돌 0
- ✅ Top 2 — 양 트랙 동시 production 호출 가능, 시그니처 잠금 작동 (분석가 미발행 → verdict=wait + null), snapshot 적극 활용
- ✅ MS0 + MS1·MS2 도달
- ⚠️ ask_strategist in-process 잔존 = 본 SPEC v3 patch 또는 후속 SPEC 의제

## 의도적으로 안 한 것

- **(c) SQLite embedding_cache** — Phase 4 측정 결과 효과 < 0.4% 로 백로그 강등. 별도 SPEC 으로 다중 dept 동시 호출이 실제 bottleneck 시 진입.
- **ask_strategist v3 patch** — 본 세션 분량 한계로 다음 사이클 의제. 임시 우회는 `httpx.post('/api/strategists/{id}/chat')` 직접 호출.
- **분석가 점수 발행 → 양 트랙 권고 자연 인계 실 시나리오 검증** — 분석가 호출 사이클 필요 (별도 작업). Track B persona 본문에는 "1 파 완성 후 Track A 인계" 가 박혀있으나 (cycle 1 작업) 실 발동 검증은 분석가 점수 적재 후.
- **`operational_safeguards` 권위 SPEC 정정** — 별도 작은 SPEC (백로그).

## 맥락 재진입 힌트

- **MS0 시연 가능 상태** — 다음 세션부터 `just server` + `just ask/chat <id>` (또는 `httpx.post('/api/...')`) 로 production 호출 일상 가능. 사용자 PC Free RAM 5GB+ 면 안전.
- **server 첫 호출 latency**: BGE-m3 cold ~30s + 자료 있는 첫 분석가 호출 ~12s + 같은 분석가 재호출 ~3s. 자료 0 시드는 항상 ~3s (BGE-m3 미로딩).
- **gemini 503 자주** — 본 세션에서 strategist 2 호출 다 gemini 503 → claude_code fallback. cost 가 ~100배 (gemini $0.001 vs claude $0.20). 비용 의식 시 provider 명시 X = auto fallback 유지 또는 anthropic 명시. 한 번에 비용 보고 싶으면 webapp 사용.
- **양 트랙 권고 본질 검증은 분석가 점수 적재 후** — 본 검증 = 양 트랙 호출 가능성 + 시그니처 잠금 작동 + persona 활성화 까지. 실 권고 발동 + 자연 인계는 분석가 사이클 진행 후.

## 다음에 이어서 할 작업 (우선순위)

1. **`stock_analyst` v3 마이크로 정정 + `INFRA-CHART-DATA-001` SPEC 묶음** (~1.3 세션) — MS3 도달. cycle 3 stock_analyst persona 의 환각 가드 2 (INFRA 미구현) 제거 + KIS daily chart API + pandas-ta + matplotlib vision. `WAVE-ALPHA-001` (Module A α 공식) 과 묶음 가능.

2. **`ask_strategist`/`chat_strategist` httpx wrap (INFRA-RUNTIME-EFFICIENCY-001 v3 patch)** (~0.3 세션) — 본 SPEC 의 (a) 누락 보강. `scripts/ask_strategist.py` + `scripts/chat_strategist.py` 가 in-process `run_strategist` 대신 `POST /api/strategists/{id}/chat` 호출. test_ask_strategist_http.py 신규. 1·2 함께 묶을 수도.

3. **`operational_safeguards` 권위 SPEC 정정** (~0.2 세션) — `ANALYST-PERSONAS-001` v2 매핑 표 trader canon → principle_guardian canon. cycle 3 발견. 회귀 테스트 갱신.

(추가 백로그: `INFRA-EMBEDDING-CACHE-001` (다중 dept 동시 bottleneck 시) / 분석가 점수 적재 사이클 → 양 트랙 자연 인계 실 검증 / `GUIDANCE-ACCURACY-TRACKER-001` / Layer 4 계좌관리자 / Layer 5 회고분석가 / news_curator SLOT S2)

## 커밋 상태

- cycle 4 partial 본체 = `7a49e65` push (직전 wrap-up 직전)
- cycle 4 partial wrap-up = `504e50c` push (직전 wrap-up)
- 본 wrap-up (SPEC v2 정정 + RESUME.md + 메모리 갱신 + c_worked 신규 + SESSIONS.md 행) commit + push 진행

## 세션 중 실 비용

production 호출 4 건 = $0.4285 (대부분 gemini 503 → claude_code fallback). gemini 정상 시 ~$0.005 예상.
- market_state_analyzer: $0.0007
- principle_guardian ×2: $0.0026
- track_a (claude_code fallback): $0.2331
- track_b (claude_code fallback): $0.1921
