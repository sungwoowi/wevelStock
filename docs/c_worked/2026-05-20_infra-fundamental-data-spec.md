---
date: 2026-05-20
topic: INFRA-FUNDAMENTAL-DATA-001 SPEC 5 라운드 면담 신설 (cycle 9 SPEC only)
status: completed
plan_file: C:\Users\HOME\.claude\plans\composed-watching-leaf.md
---

# 2026-05-20 · INFRA-FUNDAMENTAL-DATA-001 SPEC 신설 (cycle 9 SPEC only)

## 배경

cycle 8 (claude_code provider silent 500 진단·해소) 직후 새 사이클. RESUME Top 2 = MS3 완전 도달 차단점 (F5 분기 실적·EPS·매출 추세 unknown 잔존) 해소를 위한 `INFRA-FUNDAMENTAL-DATA-001` SPEC 신설. INFRA-CHART-DATA-001 cycle 5 패턴 (SPEC frozen → cycle 6 구현 풀세트) 1:1 미러. 본 사이클 = SPEC frozen 만 + 다음 사이클 (cycle 10) = 15 단계 구현.

`/spec-interview` ritual 로 5 라운드 면담 진행 — 사용자 결정 5 건 박힘.

## 한 일

- `docs/specs/INFRA-FUNDAMENTAL-DATA-001-fundamental-data.md` 신설 (~330 줄). frontmatter generates 9 + modifies 8 + depends_on 2 + contracts 1 (`fundamental-data-md-v1`). status: draft, version 1.

### 5 라운드 면담 결정

- **R1 자료 source** = yfinance Phase 1 단독 (DART/KIND/hybrid 후보 제외). 한국·미주 모두 자동 처리 + API 키 불필요 + MVP 1 세션 완성 가능. DART 이중 검증은 Phase 2 (`INFRA-FUNDAMENTAL-CROSS-VALIDATE-001` 후속).
- **R2 Default 8 필드** = (1) EPS TTM (2) PE 현재 (3) ROE (4) operating margin (5) debt/equity (6) 분기 매출 4 분기 (7) 분기 영업이익 4 분기 (8) 분기 EPS 4 분기. F5 (실적 모멘텀 QoQ·YoY) + F2 (펀더멘털 양호도) 양쪽 동시 해소. SLOT 4 (forward EPS·PE·배당수익률·현금흐름) 는 Phase 2.
- **R3 저장 구조** = DB-first hybrid + cache TTL 24h + APScheduler 주 1회 cron (일요일 18:00 KST). `fundamentals` 테이블 (`core/db/migrations/v6_fundamentals.sql`, schema_version 5→6). yfinance scraping rate limit 보호 + 사용자 burst 흡수.
- **R4 fundamental_data_md `[5]` 블록 + persona v4 정정** = chart `[4]` 직후 RAG 직전 자동 주입. stock_analyst manifest `reads_fundamental_data: true` 플래그 + persona v4 3 위치 정정 (§ Reasoning Doctrine F2/F5 정의 row / § Outputs 격자 [1] Quality Grid F5/F2 unknown 강제 해제 / manifest response_rules 가드 2 정리). chart v3 정정 패턴 1:1 미러. **MS3 완전 도달** 명시.
- **R5 본 사이클 스코프** = SPEC frozen 만 (INFRA-CHART-DATA-001 cycle 5 패턴 미러). 구현 15 단계는 다음 사이클 cycle 10 (~2 세션).

## 검증 결과

- ✅ `scripts/validate.py` 통과 (0 errors, 1 warnings — `teams/registry.yaml` 부재 본 사이클 무관)
- ✅ SPEC frontmatter generates 9 + modifies 8 정합 (draft status 라 generates 경로 미존재 OK)
- ✅ depends_on 2 SPEC (INFRA-CHART-DATA-001 v2 + ANALYST-PERSONAS-001 v2) 영향 표 명시

## 의도적으로 안 한 것

- **실제 구현** — 본 사이클 = SPEC frozen 만 (R5 결정). 다음 사이클 cycle 10 = collectors/fundamentals.py + connectors/yfinance/ + DB migration + compose + run_analyst + persona v4 + cron + 5 테스트 파일 풀세트.
- **DART 이중 검증** — Phase 2 별도 SPEC. 본 SPEC Phase 1 = yfinance 단독.
- **미주 (US) 종목 명시 검증 범위** — yfinance 가 자동 처리하나 본 SPEC 검증 범위는 한국 (KOSPI/KOSDAQ) 만. 미주 분석은 사용자 등록 시 자연 활성.
- **SLOT 4 필드** (forward EPS·PE·배당수익률·현금흐름) — Phase 2 또는 사용자 의사결정 후.
- **분기 발표 webhook / push 패턴** — 본 SPEC = polling (주 1회 cron). webhook 은 별도 SPEC.

## 다음에 이어서 할 작업 (우선순위)

1. **INFRA-FUNDAMENTAL-DATA-001 구현 풀세트 (cycle 10)** (~2 세션) — SPEC 의 15 단계 구현. pyproject.toml yfinance + DB migration + connectors/yfinance + collectors/fundamentals + compose [5] 블록 + run_analyst + stock_analyst persona v4 + cron + 5 테스트 파일 (~18~20 케이스). production smoke (`ask_analyst stock_analyst "삼성전자 분석" --provider claude_code --target 005930`) → **MS3 완전 도달 ✨**

2. **production UX 본질 구현** (~3 세션) — `feedback_webapp_production_ux.md` 첫 본격 사이클. 자연어 → 자동 라우팅 → 종합 답변. 자연어 intent extractor (Haiku 4.5 분류 또는 결정론 키워드 룰) + Track Selector input_routing 자동 분기 + 종합 답변 markdown + webapp 단일 채팅창 UI 재구성. 9 분석가 + Track Selector 안정화 후 진입 권유 → MS3 완전 도달 후 자연 진입 시점.

3. **자료 0 시드 5 분석가 페르소나 v2 완성 후 풀세트 production 검증** (~1.5 세션) — 자료 0 시드 5명 (market_state_analyzer / stock_picker / trading_journalist / flow_analyzer / news_curator) 페르소나 양식은 cycle 2 에서 작성됐으나 production 호출 풀세트 검증은 0. news_curator SLOT S2 자료원 결정 (Perplexity MCP vs 직접 수집) 도 동반 필요.

## 맥락 재진입 힌트

- **5 라운드 면담 = `/spec-interview` skill ritual 정합**: spec-interview skill 발동 후 R1~R5 옵션 제시 + 사용자 결정. cycle 9 = 첫 본격 적용 (cycle 5 의 INFRA-CHART-DATA-001 SPEC 면담은 비공식 진행). 미래 새 SPEC 신설 시 동일 ritual.
- **cycle 5 (chart SPEC) → cycle 9 (fundamental SPEC) 정합**: SPEC frozen 사이클 → 구현 풀세트 사이클 분할 패턴. 본 SPEC 구현 시 cycle 6 의 chart 구현 풀세트를 1:1 미러 가능 (collectors/connectors/compose/run_analyst/persona 5 영역).
- **stock_analyst persona v4 정정 트레이스 3 위치**: chart v3 패턴 (cycle 6) 1:1 미러. F5·F2 동시 해제 = 한 마이크로 정정. 구현 후 `verdict=inconclusive` 해제 → 정상 발행.

## 세션 중 실 비용

- LLM API 호출 0 회 (본 사이클은 SPEC 작성·면담만 진행)

## 커밋 상태

- SPEC + 본 c_worked + RESUME + SESSIONS 한 commit 으로 묶음 (cycle 5 ad6ec07 패턴 미러)
- `docs+spec: INFRA-FUNDAMENTAL-DATA-001 SPEC 5 라운드 면담 신설 + wrap-up 2026-05-20 (cycle 9 SPEC only)` 진행 예정
