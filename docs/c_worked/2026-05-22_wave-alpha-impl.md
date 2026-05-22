---
date: 2026-05-22
topic: cycle 14.0 + 14.1 = SLOT S4 KIS fallback + WAVE-ALPHA canon 21 + DB v8 + scoring.py alpha 시간 정규화
status: completed
plan_file: C:\Users\HOME\.claude\plans\serene-booping-petal.md
---

# 2026-05-22 · WAVE-ALPHA 구현 14.0 + 14.1 (같은 날 세 번째 세션)

## 배경

cycle 14 SPEC frozen (`dd4782f`, 같은 날 두 번째 세션) 직후 자연 진입. cycle 13 INFRA-SNAPSHOT-EXTEND-001 풀세트 잔여 부채 = SLOT S4 (KRX breadth bld 4종 모두 400 응답). 사용자 결단 = 본 세션 = **SLOT S4 KIS fallback (14.0) → WAVE-ALPHA sub-cycle 14.1 (canon 21명제 + DB v8 + scoring.py alpha 시간 정규화 정식)**. 14.2 (anchors.py + α 3 timeframe 통합) / 14.3 (persona v3→v4 + 테스트 풀세트 + smoke) 는 별 세션. cycle 5/9/12 의 "SPEC frozen → 구현 풀세트" 분할 패턴 **5 회째 누적 검증**.

## 한 일

### Step 1 — SLOT S4 KIS volume_rank fallback (commit 14.0 `98cbf32`)

- `collectors/market_macro.py` — `_fetch_breadth_kis_fallback(market)` 신규 (KIS top30 change_pct 분포 카운트 → advancing/declining/unchanged/breadth_ratio). `_fetch_breadth` 가 KRX 400/empty 시 자동 fallback. `MarketMacro` dataclass 에 `breadth_source` 필드 추가 ("krx" / "kis_volrank_top30" / "unavailable"). 분석가에게 한계 메타데이터 노출.

### Step 2 — WAVE-ALPHA 14.1 풀세트 (commit 14.1 `a536428`)

- `knowledge/canon/stock-analysis/fractal_wave/01-anchor-and-alpha-formula.md` 신규 (~380줄) — **WA1~WA5 + WF1~WF4 + WL1~WL4 + WE1~WE7 + WX1 = 21 명제**. SPEC 라운드 1~4 결단 1:1 마크다운 변환 + cited 형식.
- `knowledge/canon/stock-analysis/fractal_wave/_category.yaml` — `target_analysts: [stock_analyst]` + description 갱신.
- `core/db/migrations/v8_wave_alpha.sql` 신규 — `manual_anchors` 테이블 (ticker, timeframe, A·B·C 6컬럼 PK ticker+timeframe) + `llm_call_cache.type` ALTER ADD COLUMN + `schema_version 8` INSERT.
- `core/db/schema.sql` — `llm_call_cache.type` 컬럼 + `manual_anchors` CREATE + `idx_llm_call_cache_type` 인덱스 + `idx_manual_anchors_ticker` + schema_version v8 INSERT.
- `collectors/scoring.py` — `alpha()` 시그니처 `(float×4)` → `(Anchor=tuple[date,float]×4)` 정식 교체. 시간 정규화 공식 `k₁=ln(B/A)/days(A→B), k₂=ln(current/C)/days(C→current), α=k₂/k₁`. 신규 = `interpret_alpha(α, timeframe) → 5단계 Literal` / `progress_to_b` / `duration_ratio` / `THRESHOLDS` dict (daily 0.5/1.0/4.0, weekly 0.7/1.0/3.0, monthly 0.8/1.0/2.5) / `TIMEFRAME_LIMITS` dict / 가드 = k1_flat (WE2) → None, current ≤ C (WE3) → α 음수·0, 시간 역행 → ValueError, 가격 ≤ 0 → ValueError.
- `tests/test_scoring.py` — `TestAlpha` 클래스 13 케이스 새 시그니처 재작성 (시간 정규화 1.0 / accelerating 2.0 / decelerating / trend_broken zero·negative / k1_flat → None / time normalized 0.5 / raise 4종 / determinism). `test_all_functions_deterministic` 도 새 anchor 인자.
- `tests/test_snapshot_extend_db.py` — `assert max(versions) == 7` → `>= 7` 정정 (v8 호환).
- `docs/specs/WAVE-ALPHA-001-wave-alpha.md` — 부록 B § "INFRA-CHART-DATA-001 v2 chart_ohlcv 깊이" 정정 마이크로 patch (실 코드 = 이미 5년 1825봉, SPEC 작성 시점 "1년 250봉" 인식 오류 보정. monthly 60봉 + weekly 156봉 요구 = 현 5년 fetch 로 충족, v3 정정 불필요).

## 검증 결과

- ✅ pytest 전체 **468 passed** (cycle 13 = 467 → +1 신규 = test_scoring.py 의 TestAlpha 새 시그니처 통과)
- ✅ DB v8 schema 임시 DB smoke = `manual_anchors` 테이블 생성 + `llm_call_cache.type` 컬럼 + `schema_version 8` 적용 ([1..8] 박힘)
- ✅ scoring.py alpha 시간 정규화 본질 = "1차 6개월 100→200 + 2차 12개월 150→300" (시간 2배) → α = 0.5 정확 (수동 검증)
- ✅ interpret_alpha 5 단계 모두 정확 (trend_broken α=-0.5 / weak 0.3 / modest 0.9 / sweet 1.5 / overheated 5.0, daily·weekly·monthly 각 timeframe 차등)
- ✅ canon 21 명제 ID 모두 박힘 (WA1~WA5, WF1~WF4, WL1~WL4, WE1~WE7, WX1 grep 검증)
- ✅ git log = `98cbf32` (14.0) + `a536428` (14.1) 깔끔

## 의도적으로 안 한 것

- **14.2 anchors.py + α 3 timeframe 통합** — Stage 1 결정론 candidate (`extract_swing_candidates`) + Stage 2 LLM Haiku 4.5 직관 + 3 단 캐싱 + manual override + E6 fallback. `core/inference/run_analyst.py` 또는 `collectors/snapshot.py` hook 으로 stock_analyst data.alpha_daily/weekly/monthly 자동 주입. 다음 세션
- **14.3 persona v3→v4 + 테스트 풀세트 + smoke** — § 4 (α 산출) 전면 재작성 + § 5 (verdict 매트릭스 long/swing/중립) + § 6 (holding_period 매핑) + § 7 (환각 가드 3 중). manifest reads_chart_data + canon_categories 에 fractal_wave 추가. 테스트 ~60 케이스 (test_alpha 25 + test_anchors 30 + 통합 5). smoke 삼성전자 + NVIDIA + KOSPI. 별 세션
- **SLOT S4 정확도 정정** — KIS top30 한계 (전체 시장 breadth 아님). KRX 데이터시스템 manual devtools 추출 또는 다른 backend SPEC. 우선순위 낮음

## 다음에 이어서 할 작업 (우선순위)

### 1. WAVE-ALPHA-001 sub-cycle 14.2 + 14.3 (~1 세션)
- **왜**: 14.1 commit 후 자연 진입. anchors.py + α 3 timeframe 통합 + persona v4 + 테스트 풀세트 = stock_analyst verdict=confirmed_* 정식 발행 + holding_period 매핑 활성 = **MS4 (실 매매 시연) 베이스라인 도달**
- **범위**: 14.2 = `collectors/anchors.py` 신규 (extract_swing_candidates + select_anchors_via_llm Haiku 4.5 + 3 단 캐싱 + manual_anchors override + E6 fallback) + α 3 timeframe 통합. 14.3 = persona § 4·5·6·7 재작성 + manifest reads 갱신 + 테스트 ~60 + smoke + wrap-up
- **예상 산출**: stock_analyst α 3 timeframe 정식 발행 + verdict=confirmed_* + holding_period (장기/중기/단기) 활성

### 2. production UX 본질 구현 (~3 세션) — webapp 자연어 채팅창
- **왜**: cycle 13 MS3 차단점 해소 + cycle 14.2·14.3 완료 후 자연 진입. 가장 큰 사용자 가치 = 자연어 채팅창에서 의미 있는 답변. WAVE-ALPHA SPEC 부록 A 의 자연어 변환 사전 활용 가능
- **범위**: 자연어 intent extractor (Haiku 4.5 분류) + Track Selector 자동 라우팅 + 종합 답변 형식 + webapp 단일 채팅창 UI 재구성 + R&D 토글 별도 페이지 보존

### 3. SLOT S4 정확도 정정 (~0.3 세션 마이크로)
- **왜**: 본 세션 14.0 = KIS top30 한계 (전체 시장 breadth 아님). 정확도 정정 = KRX 데이터시스템 manual devtools 추출 또는 다른 backend
- **범위**: data.krx.co.kr "통계 > 주식 > 등락 종목수" devtools Network 탭 POST bld 추출 → `BLD_MARKET_BREADTH` 교체. KIS fallback 은 retention

(추가 백로그: WAVE-ALPHA-CANON-001 (SLOT S4 풀세트 canon W5+) / WAVE-ALPHA-WATCH-001 (SLOT S2 월봉 황제주 알림) / WAVE-ALPHA-BACKTEST-001 (SLOT S3 백테스팅 본체) / NEWS-SOURCE-001 / PERSONA-REFUSAL-CITED-RULE-001 / Layer 4 계좌관리자 (M5) / Layer 5 회고분석가 (M4) / GUIDANCE-ACCURACY-TRACKER-001 구현 / INFRA-US-MACRO-SNAPSHOT-001 / scoring.py s_score·buy_score 정식 가중치 (SLOT S7))

## 맥락 재진입 힌트

- **sub-cycle 분할 ritual 5 회 누적** = cycle 5 / 9 / 12 / 14 (SPEC) / 본 cycle (14.0+14.1 impl). "SPEC frozen → 구현 분할" 패턴이 영구 ritual 격상 (cycle 4 회 누적 → 5 회). 미래 인프라 SPEC 신설 시 default 진입점.
- **scoring.alpha() 시그니처 breaking change** = 기존 `(float×4)` 호출처 = `tests/test_scoring.py` 만. persona/manifest 문서는 호출처 X (문서 인용만). 14.3 persona v3→v4 정정 시 함께 갱신.
- **DB v8 마이그레이션 자동화 부재** = `core/db/connection.py:_ensure_schema` 가 `schema.sql` 만 통째 실행, `migrations/v*.sql` 자동 실행 X. v8 = `schema.sql` 통합 CREATE 정의 (새 DB) + `migrations/v8_wave_alpha.sql` reference (기존 DB ALTER manual 적용). 사용자 dev DB 만 있으면 schema.sql 자동 적용으로 충분.
- **manual_anchors 테이블 활용 시점** = 14.2 anchors.py 의 Stage 1+2 보다 우선 SELECT. 황제주 ~10 종목 사용자 직접 박는 surface (CLI 또는 webapp admin SPEC 후속).

## 커밋 상태

- **14.0** `98cbf32` = SLOT S4 KIS volume_rank fallback (1 파일, +57/-7)
- **14.1** `a536428` = canon 21 + DB v8 + scoring.py alpha (8 파일, +725/-82)
- **wrap-up commit** = 본 wrap-up 묶음 진행 예정 (c_worked + RESUME.md + SESSIONS.md, cycle 5/9/12 정합)
- **push 진행** (사용자 명시 요청 "커밋 푸시해")
