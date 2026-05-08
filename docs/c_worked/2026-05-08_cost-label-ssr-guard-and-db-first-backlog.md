---
date: 2026-05-08
topic: claude_code cost 라벨 + analyst-chat SSR 가드 + 시장 스냅샷 DB-first 발견
status: completed
plan_file: C:\Users\HOME\.claude\plans\ethereal-forging-catmull.md
---

# 2026-05-08 · cost 라벨 + SSR 가드 + DB-first 발견

## 배경

같은 날 오전 단계 2 시장 스냅샷 자동 주입 후 두 작은 UX 결함 (claude_code cost misleading + analyst-chat SSR 깜빡임) 이 백로그로 남음. 30분 작업으로 정리하던 중 사용자가 LLM 응답 지연 본질 (~40s) 과 "외부 응답이 느리다" 를 제기 → snapshot.py 7 collector 가 `pipelines/market_briefing_{now,pre}/stages/collect_*` 와 동일 함수 호출 (100% 중복) 임을 식별. 옵션 A (DB-first hybrid) 결정 + 백로그 등재.

이번 세션 핵심 판단: **분석가가 collector 직호출 = 5-Layer "수집팀 → 분석팀" 단방향 위반**. 옵션 A 가 본질 정합 + cold fetch 30s 제거 동시 해결 → Top 1 (분화) 직전 처리.

## 한 일

### 신규/수정 코드
- `webapp/src/app/analyst-chat/page.tsx` — MetadataBar cost 표기에 `provider_used==="claude_code"` 면 `$0 (subscription)` 분기 / 누적 비용 reduce 에서 claude_code 호출 제외 / `analystMeta` state 를 `null` → `undefined | null | object` 3-state 로 확장 (undefined 면 회색 "분석가 메타 로딩…" placeholder, null 만 빨간 "로드 실패")

### 백로그 기록
- `C:\Users\HOME\.claude\projects\C--Users-HOME-claude-wevelStock\memory\project_db_first_snapshot.md` (신규) + `MEMORY.md` 인덱스 추가 — 옵션 A 결정/이유/구현 가이드/숙제
- `docs/RESUME.md` — Top 0 (DB-first, Top 1 분화 직전 권장) + 미완 섹션 항목 추가

## 검증 결과

- ✅ TypeScript 타입 체크 통과 (`npx tsc --noEmit -p .` in webapp)
- ✅ webapp dev (PID 15676 fast refresh) + BE FastAPI (PID b7pso9mr1, 24 routes) 부팅 후 사용자 브라우저 검증 4건 모두 통과:
  - SSR 첫 렌더 빨간 "로드 실패" 깜빡임 X (회색 "로딩…" → 정상 메타)
  - claude_code 토글 → MetadataBar `cost $0 (subscription)`, 하단 누적 0
  - gemini 토글 → 기존 `$0.0xxx` 회귀 OK
  - 두 provider 섞인 채팅 → 누적 = gemini 분만

## 의도적으로 안 한 것

- **백엔드 `claude_code_backend.py` 의 `total_cost_usd` 자체를 0 으로 강제하지 않음** — metadata 의미 (토큰 환산 가격, 다른 비교에 활용 여지) 유지. 표시 책임만 frontend 에서 분리.
- **streaming (SSE) 도입** — latency 본질 질문에 가장 큰 한 방으로 판단되나 FE/BE 양쪽 SSE 손이라 별도 SPEC + 세션 (3~4h). 백로그.
- **provider default = gemini 토글** — 5분 작업이지만 옵션 A (DB-first) 가 더 본질이라 묶지 않음.
- **옵션 A 즉시 구현** — 1.5~2h 작업, 다음 세션 분화 (Top 1) 직전 처리로 백로그.

## 맥락 재진입 힌트

- **snapshot.py 와 briefing_{now,pre}/stages 가 동일 collector 함수 호출** (`fetch_kr_indices`/`fetch_kr_supply_demand`/`fetch_overnight` 등) — 100% 중복. 한 군데 수정 시 양쪽 영향.
- **`parts_store.get_latest_parts_with_age()` 가 이미 `(run_id, parts, age_seconds)` 반환** — 옵션 A 어댑터의 진입점, 추가 API 불필요.
- **`market_briefing_pre` 는 LLM 단계 포함** — overnight part data 가 raw 인지 LLM 가공인지 stages 코드 (`collect_overnight_us` / `persist`) 확인 필요.
- **claude_code CLI ≠ Anthropic SDK** — subprocess + OAuth keychain 오버헤드 ~10s. `provider=anthropic` (ANTHROPIC_API_KEY 직접) 시 ~2s 첫 토큰. 단 Pro/Max 무료 혜택 포기.
- **streaming 미사용이 체감 latency 의 가장 큰 원인** — 동일 모델도 5~10배 차이. wevelStock 분석가는 챗봇이 아니라 알림 Agent (user_want_spec) — 자동 호출 시 무관, webapp 채팅은 검증/디버그 용.

## 다음에 이어서 할 작업 (우선순위)

1. **시장 스냅샷 DB-first hybrid (옵션 A)** (PC, 1.5~2h)
   - 왜: snapshot.py 7 collector 와 briefing_{now,pre} stages 100% 중복 + 5-Layer 단방향 위반 + cold fetch 30s. 분석가 응답 latency 40s → 5~15s.
   - 범위: `collectors/snapshot.py:build_market_snapshot()` 가 `parts_store.get_latest_parts_with_age()` 우선 → 신선도 임계 (한국 6h / 미국 24h) 초과 시 collector fallback. parts data_json → snapshot dict 어댑터. `market_briefing_pre` overnight part 형식 (raw vs LLM 가공) 확인.

2. **4명 분석가 분화 + canon 분기 (옵션 B) 묶음** (PC, 3~4h)
   - 왜: 자산전략가 통합 canon 답변이 영역 침범 (7계명·심법·박종훈 모두 인용). 5-Layer 1:1 매핑 정합. 매매코치 추가 시 톤 비교로 분화 의미 즉시 입증.
   - 범위: `agents/analysts/{principle_guardian, trade_coach, stock_analyst, news_curator}/{persona, manifest}` 4 set + `compose.load_shared_canon()` reads 분기 + run_analyst spec.reads 패스.

3. **종목분석부 자료 첫 ingest** (PC, 1h)
   - 왜: `rag_docs/logchart/` (untracked, ~288KB) 차트 교육 자료 가용. 종목분석가 분화 시 RAG 즉시 활용.
   - 범위: `knowledge/reference/stock_analysis/` 로 이동 + `just knowledge-sync stock_analysis` + 검증 회수.

(추가 백로그: streaming 도입 SPEC = FE/BE 양쪽 SSE, ~3-4h. provider default = gemini 토글 5분.)

## 커밋 상태

- ✅ `53e657b feat(webapp): claude_code cost 라벨 + analyst-chat SSR 메타 로딩 가드`
- ✅ `1e65c69 docs(resume): 시장 스냅샷 DB-first hybrid (옵션 A) 백로그 추가`
- ✅ main push (`cf7eeb9..1e65c69`)
- 본 wrap-up 후 추가 커밋 1건 예정
