---
date: 2026-05-08
topic: 단계 2 시장 스냅샷 자동 주입 (분석가 system prompt 결합)
status: completed
plan_file: C:\Users\HOME\.claude\plans\serene-knitting-fairy.md
---

# 2026-05-08 · 단계 2 시장 스냅샷 자동 주입

## 배경

직전 세션 단계 1 (톤 직설화 + temp 0.7) 결과 framework 명제 인용은 살아남았으나 **응답이 framework 적용에만 머물고 실 수치 (환율·VIX·수급) 와 결합되지 않음** — user_want_spec 본질 ("오감 + 뇌") 미충족. user_want_spec Task 2/3 의 시장 데이터 7종을 분석가 호출 직전에 자동 수집·주입하여 답변이 실시간 시장 상황과 결합되도록.

이번 세션 핵심 판단: **자산전략가 1명 검증 단계에 옵션 B (canon 분기) 도입은 시기상조** — 5-Layer 1:1 매핑 정합 위해 4명 분화 (Top 2) 와 묶어서 다음 세션 처리.

## 한 일

### 신규/수정 코드
- `collectors/snapshot.py` (신규) — 7 collector 병렬 (overnight·fear_greed·kr_indices·kr_supply·kr_sectors·kr_leading·kr_futures_supply) + `asyncio.gather(return_exceptions=True)` partial-failure + 5분 인메모리 캐시 + cold call stderr `[market snapshot fetching... ~30s]`. `MarketSnapshot` dataclass + `render_snapshot_md()` (실패 항목은 `[수집 실패 - 사유]` 표기 — 7계명 #6 정합). 모든 분석가 자동 공유 (옵션 A 풀세트).
- `core/knowledge/compose.py` — `build_pipeline_prompt()` 시그니처에 `market_snapshot_md: str | None = None` 추가, RAG 직전 [3] 블록 삽입 (`cache_control` 없음 — 5분 갱신). docstring layout 갱신.
- `core/inference/run_analyst.py` — `build_market_snapshot()` 호출 → `render_snapshot_md()` → compose 전달. metadata 4키 추가 (`snapshot_age_seconds`, `snapshot_fetch_seconds`, `snapshot_cache_hit`, `snapshot_failures`).

### 테스트
- `tests/test_market_snapshot.py` (신규) — 8 테스트: cache cold/hit, TTL 만료, partial failure, render 안전성, compose 블록 주입, compose 스킵, run_analyst metadata 노출. 7 collector + KIS/KRX context manager + call_llm 모두 monkeypatch.

### 운영
- BE 재시작 (PID 6676 → 9188) — 새 코드 반영 위해 `uv run uvicorn server.main:app --host 127.0.0.1 --port 8000`.

## 검증 결과

- ✅ pytest 68 passed (기존 60 + 신규 8) — TESTING=1 환경
- ✅ 실호출 검증: `uv run python -m scripts.ask_analyst wealth_strategist --provider claude_code "원달러 1500원 가까이 가면 자산 비중 어떻게?"`
  - stderr `[market snapshot fetching... ~30s]` → `[market snapshot ready in 23.9s · 0 failed]`
  - 응답에 실 수치 결합: "현재 1,456원이니 사실상 지금이 그 시점이다", "3년 달러 평균가가 1,370원이고 지금 1,456원이면 이미 평균 위다" → I6 시그널 + I1/I2/M3/C4 framework 결합
  - metadata `[claude_code] · prompt 25,988 chars · RAG 3 chunks · cache hit (read 14,795) · cost $0.1599 · 40.1s`
- ✅ Provider 비교 — Gemini 호출도 동일 스냅샷 결합 ($0.0017, prompt 25,786 chars). 다만 7계명·심법·박종훈 4 영역 모두 인용 → 자산전략가 영역 침범 발견 (다음 세션 처리)

## 의도적으로 안 한 것

- **옵션 B (canon 분기)** — manifest `reads:` 따라 `load_shared_canon()` 분기. 자산전략가 1명만 가동 중 + Layer 3 종합 판단부 (M4) 미구현 → 지금 좁히면 검증 답변 퀄리티만 깎임. 4명 분석가 분화 (Top 2) 와 묶어 다음 세션 처리.
- **옵션 A (persona 가드)** — LLM 룰 안 지키면 또 침범 + 토큰 비용 그대로. 봉합용으로도 안 함. 통합 응답 그대로 두고 본질 해결을 다음 세션에 묶음.
- **streaming 도입 (FastAPI SSE)** — webapp/FastAPI 진행 표시는 spinner 그대로. 캐시 히트 자주 일어나면 자연스레 짧아짐. 별 작업.

## 맥락 재진입 힌트

- **"자산전략가" 명칭 = Layer 2 분석가** (자산 도메인 담당 1명) — Layer 3 의 단타·스윙·중장기 전략가 3종과 다름
- **Layer 3 = "투자 종합 판단부"** = CLAUDE.md L100-105 에 이미 설계 (M4 마일스톤). 단타전략가 (종목분석가+뉴스큐레이터) / 스윙전략가 (종목분석가+자산전략가+매매코치) / 중장기전략가 (자산전략가+종목분석가+원칙수호자)
- **canon 통합 vs 분화 모순**: `load_shared_canon()` 5 학습부 통합 (5-Layer 베이스 = "통합 두뇌") 와 `manifest.reads:` 1:1 매핑 (분석가별 영역) 사이 불일치. 4명 분화 + 옵션 B 로 해소
- **응답 퀄리티 검증**: Gemini Gems 수준 (사용자 평가). 자산전략가 1명만 통합 canon 으로 답하는 게 검증 단계엔 임시 봉합으로 가치 있음

## 다음에 이어서 할 작업 (우선순위)

1. **나머지 4명 분석가 분화 + canon 분기 (옵션 B) 묶음** (PC, 3~4h)
   - 왜: 단계 2 검증 끝났고, 자산전략가 통합 canon 답변이 영역 침범 (7계명·심법까지). 5-Layer 1:1 매핑 정합 위해 분화 + canon 분기 함께 처리해야 비대칭 회피
   - 범위: `agents/analysts/{principle_guardian, trade_coach, stock_analyst, news_curator}/{persona.md, manifest.yaml}` 4 set + `core/knowledge/compose.py:load_shared_canon()` 가 manifest `reads:` 받아 해당 학습부 canon 만 합치도록 분기 + run_analyst 가 spec.reads 패스. 매매코치 추가하면 자산전략가와 톤 비교로 분화 의미 즉시 입증

2. **claude_code cost 라벨 + analyst-chat SSR 깜빡임** (PC, 30분)
   - 왜: Pro/Max 구독은 호출당 추가 비용 0인데 metadata 가 토큰 환산 $0.16 표시 (오해 소지). SSR 첫 렌더 "분석가 메타 로드 실패" 빨간 텍스트도 묶어서
   - 범위: `webapp/src/app/analyst-chat/page.tsx` MetadataBar 에서 `provider_used==claude_code` 면 `$0 (subscription)` 라벨. SSR 가드 (mount 후 첫 fetch 까지 placeholder)

3. **종목분석부 자료 첫 ingest** (PC, 1h)
   - 왜: `rag_docs/logchart/` (untracked, ~288KB) 차트 교육 자료 가용. 종목분석가 분화 시 RAG 즉시 활용 가능
   - 범위: `knowledge/reference/stock_analysis/` 로 이동 + `just knowledge-sync stock_analysis` (또는 `knowledge.py ingest`) + 검증 회수

## 커밋 상태

- ✅ 1 commit (코드+테스트) + 1 commit (wrap-up) — 본 wrap-up 후 push
