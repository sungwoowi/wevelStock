---
date: 2026-05-20
topic: INFRA-CHART-DATA-001 구현 풀세트 + stock_analyst v3 마이크로 정정 (cycle 6)
status: completed
plan_file: C:\Users\HOME\.claude\plans\elegant-moseying-cloud.md
---

# 2026-05-20 · INFRA-CHART-DATA-001 구현 풀세트 (cycle 6)

## 배경

cycle 5 (같은 날 직전) 에서 SPEC frozen (340 줄). 본 사이클 = 15 단계 구현 + stock_analyst v3 마이크로 정정 풀세트. 사용자가 "자러 가니 다 만들어놓아" 자율 실행 의사 명시 → 미정의 3 트랩 자율 결정 박고 진입.

## 자율 결정 (사용자 부재)

1. **Target ticker 자동 인식 방식** → manifest 의 `reads_chart_data: true` + `run_analyst(target_ticker=...)` kwarg 명시적 전달. 종목명 → ticker 매핑은 별도 백로그 유지.
2. **collectors/charts.py sync/async** → async (`collectors/snapshot.py` 패턴 미러).
3. **pandas-ta 의존성 추가 vs 직접 계산** → **pandas 기본 함수 (rolling / ewm) 로 직접 계산**. SPEC 본문은 pandas-ta 명시했으나 Default 6 지표 (MA · MACD · 거래량 · 52주 고저) 는 pandas 기본 함수로 충분. numpy 호환성 위험 회피 + 의존성 최소화. RSI · 볼린저 (SLOT S2) 활성화 시점에 pandas-ta 도입 재검토.

## 한 일 (SPEC 15 단계 그대로)

### 묶음 A — 데이터 인프라 (Step 1-4)
- **`core/db/migrations/v5_chart_ohlcv.sql`** 신규 + **`core/db/schema.sql`** 의 chart_ohlcv 테이블 + schema_version 4 → 5 bump
- **`connectors/kis/client.py`** 에 두 메서드 추가:
  - `get_daily_chart(ticker, period_days=1825, adjust=True)` — KIS `inquire-daily-itemchartprice` (tr_id=`FHKST03010100`) 페이징 fetch + 정순 정렬 + 25 회 안전 가드
  - `get_current_price(ticker)` — 기존 `stock_price()` wrap → snapshot 7 필드 reformat
- **`collectors/charts.py`** 신규 (~470 줄):
  - `ChartData` dataclass (snapshot + indicators + ohlcv_count + source + db_last_date + stale_hours + failures)
  - `build_chart_data(ticker, max_age_seconds=60)` async — DB-first hybrid + 60s 인메모리 TTL + 3-tier fallback (KIS 실패 → stale_cache → unknown)
  - `compute_indicators(ohlcv)` — Default 6 지표 (pandas rolling/ewm 직접 계산)
  - `render_chart_data_md(chart, name=)` — `chart-data-md-v1` 계약 markdown 표 풀세트
  - `refresh_all_tickers()` + `__main__` CLI (`refresh` / `fetch` 서브커맨드)
  - 임계 분리: `_FRESH_MAX_HOURS=26` (다음 cron 까지 신선) + `_STALE_MAX_HOURS=168` (5 영업일 fallback 허용)
- **테스트 묶음 A 23 케이스 통과**:
  - `tests/test_charts.py` (12) — KIS fetch + DB upsert / DB-first fresh skip / 60s TTL cache / TTL 만료 재호출 / stale_cache fallback / unknown / snapshot 실패 partial / render 풀구조 / null 안전 / 7 필드 / 다중 ticker 격리 / failures propagate
  - `tests/test_charts_indicators.py` (8) — 일봉 5MA 산술 정확도 / 주봉 resample / 월봉 resample / 월봉 데이터 부족 null / MACD 12-26-9 양수 / MACD 데이터 부족 / 거래량 spike 1.0 / 52주 고저 fixture
  - `tests/test_chart_ohlcv_db.py` (3) — ON CONFLICT REPLACE 멱등 / schema_version 5 적재 / load 정순 정렬

### 묶음 B — 주입 파이프라인 (Step 5-8)
- **`core/knowledge/compose.py`** `build_pipeline_prompt(..., chart_data_md=None)` kwarg 추가 + `[4]` 블록 신설 (snapshot 직후 / RAG 직전 정확 위치). `## [4] 차트 데이터` prefix 인식 → 본문 그대로, 그 외 → `## Chart Data` 헤더 prepend.
- **`core/inference/run_analyst.py`** 변경:
  - `AnalystSpec.reads_chart_data: bool = False` 필드 추가
  - `load_analyst_spec` 에서 manifest `reads_chart_data` 키 로드
  - `_maybe_build_chart_data_md(spec, target_ticker)` 헬퍼 — `reads_chart_data=True` + `target_ticker` 충족 시 build_chart_data 호출 + chart_data_md 산출 + 7 키 metadata 반환
  - `run_analyst` + `run_analyst_stream` 양쪽 `target_ticker` kwarg 추가 + chart_meta 7 키 metadata 통합 (chart_data_age_seconds / chart_fetch_seconds / chart_cache_hit / chart_failures / chart_ohlcv_count / chart_source / chart_ticker)
- **테스트 묶음 B 7 케이스 통과**:
  - `tests/test_compose_chart_data_md.py` (4) — kwarg 주입 / None silent skip / 블록 순서 / empty string silent skip
  - `tests/test_run_analyst_chart_injection.py` (3) — stock_analyst + target_ticker → 주입 O + metadata 정합 / target_ticker=None → silent skip + chart_failures=["target_ticker_absent"] / 다른 분석가 (reads_chart_data=False) → 주입 X

### 묶음 C — stock_analyst v3 페르소나 정정 (Step 9-11)
- **`agents/analysts/stock_analyst/manifest.yaml`** v3 정정:
  - `reads_chart_data: true` 신규 추가
  - response_rules 의 v2 환각 가드 2 본문 ("verdict=`unknown` 강제") → "chart_data_md `[4]` 블록 출처 명시 강제 + 자유 패턴 추론 금지" 로 정정
  - verdict 매핑 v2 → v3 (chart 부재 시 `inconclusive` + confidence ≤ 40, `unknown` 강제 해제)
  - α 산출 + Module A + F1~F5 + cited v3.1 + Track A read 정합 + 자연어 분기 룰 모두 chart_data_md 어휘로 정정 (INFRA 미구현 표현 → chart_data_md 부재 표현)
- **`agents/analysts/stock_analyst/persona.md`** v3 정정 3 위치 + 보조:
  - § Identity 헤더 "환각 우려 2 중" → "v3 (2026-05-20) — INFRA-CHART-DATA-001 구현 후 차트 추론 가드 해제"
  - 권위 한정 4 가지 발행물의 INFRA 미비 → chart_data_md 부재 표현
  - § Inputs 1 (차트 데이터) 본문 + 6 (snapshot · INFRA 의존 강도) 본문 정정
  - § Outputs 격자 [1] Quality Grid (α·F1·F4 row) — "INFRA-CHART-DATA-001 (미비 시 unknown)" → "chart_data_md [4] (월봉 7MA·20MA + 52주 고저)" 표기
  - § Outputs 격자 [2] anchor → "INFRA 미비 시 모두 null" → "chart_data_md 부재 시 모두 null"
  - § Outputs 격자 [4] Citation 자연어/격자 양식의 cited 풀이 v3.1 분기 (chart 주입 시 / 부재 시)
  - § Outputs StandardOutput 매핑 — verdict `unknown` 강제 제거 + chart_source 자각 추가
  - § Reasoning Doctrine α 산출 + Module A + F1~F5 정의 + verdict 매핑 모두 v3 어휘로 정정
  - § Anti-patterns 의 환각 가드 2 본문 → "chart_data_md `[4]` 블록 출처만 인용" 으로 정정 + LLM 추정·환각 차단 § v3 보강
  - 미래 정정 메타-가이드 § → v3 정정 트레이스 § (정정 완료 기록 + 후속 SPEC 3개 명시 — INFRA-CHART-VISION-001 / INFRA-FUNDAMENTAL-DATA-001 / WAVE-ALPHA-001)
- **테스트 묶음 C 5 케이스 통과**:
  - `tests/test_stock_analyst_v3_persona.py` (5) — manifest reads_chart_data=true / verdict=unknown 강제 제거 / 차트 인용 규율 v3 / Quality Grid α·F1 unknown 강제 해제 / 8 섹션 portable + cited v3.1 + Track A 정합 회귀 0

### 묶음 D — 운영 + 검증 (Step 12-15)
- **`server/schedulers/jobs/charts.py`** 신규 — `run_chart_refresh()` cron entrypoint (collectors/charts.refresh_all_tickers wrap + 로그 + exception 폴백)
- **`server/schedulers/jobs/__init__.py`** 의 `register_infra_jobs` 에 chart 고정 cron 등록 (`day_of_week=mon-fri`, `hour=18`, `minute=0`, `timezone=Asia/Seoul`, `id=infra::chart_ohlcv_refresh`)
- **`justfile`** 에 `refresh-charts` + `fetch-chart` 2 레시피 추가 (수동 백업·디버깅)
- **부수 부채 정리**: `docs/specs/INFRA-RUNTIME-EFFICIENCY-001-runtime-efficiency.md` v2 frontmatter 2 validation 에러 정정 (`generates: []` + `contracts:` 키 제거). RESUME.md Top 2 묶음 권유 즉시 처리.
- **`docs/specs/INFRA-CHART-DATA-001-chart-data.md`** frontmatter v1 → v2 + status `draft` → `implemented` + generates 9 (server/schedulers/jobs/charts.py 추가) + modifies 8 (server/main.py + pyproject.toml 제거, server/schedulers/jobs/__init__.py 추가) + v2 변경 한 줄 wrap 추가
- **pytest 전체**: 341 → **376 passed** (회귀 0, +35 신규 — SPEC 예상 +33 +α)
- **scripts/validate.py**: 0 errors / 1 warning (`teams/registry.yaml` 기존 부채, 본 SPEC 무관)

## 검증 결과

- ✅ pytest 376 passed (회귀 0)
- ✅ scripts/validate.py 0 errors
- ✅ SPEC frontmatter generates 9 / modifies 8 / contracts 1 dict / status: implemented 단독 파싱 통과
- ✅ stock_analyst manifest `reads_chart_data: true` 로드 검증 (test_stock_analyst_v3_persona.py)
- ✅ run_analyst metadata 7 chart 키 (chart_data_age_seconds / chart_fetch_seconds / chart_cache_hit / chart_failures / chart_ohlcv_count / chart_source / chart_ticker) 정합 검증

## 의도적으로 안 한 것

- **Production smoke (Step 14)** — KIS 실 API 호출 필요. 사용자가 자고 있어 webapp 또는 `just ask stock_analyst "삼성전자 분석" --target 005930` 호출 검증은 본 사이클 미진행. 깨어났을 때 webapp Track A → target=005930 + analyst=stock_analyst 호출하면 [4] 블록 LLM read + α/F1/F4/목표가 3 단 정상 발행 확인 가능. **RESUME 에 Top 1 잔여로 명시**.
- **`ask_strategist`/`chat_strategist` httpx wrap** (RESUME Top 2 본체) — 본 사이클 분량 외. 다음 사이클 별도. frontmatter 부채만 동시 정정.
- **pandas-ta 의존성 추가** — SPEC 본문은 명시했으나 Default 6 지표는 pandas 기본 함수로 산출 가능. numpy 호환성 위험 회피. RSI · 볼린저 (SLOT S2) 활성화 시 재검토.
- **종목명 → ticker 자동 매핑** — webapp target 필드 한글 입력 지원은 별도 백로그 (existing).
- **stale_cache 케이스의 chart_source 자동 강등** — manifest response_rules 안내만 박음. 실제 confidence 자동 강등은 LLM 추종에 위임.

## 다음에 이어서 할 작업 (우선순위)

1. **Production smoke 검증 + stock_analyst 양 트랙 인계 시연** (~0.2 세션) — 사용자 webapp Track A `target=005930` + `analyst=stock_analyst` 호출. 응답 검사:
   - verdict ≠ unknown (inconclusive 또는 confirmed_*)
   - α (가속계수) 값 발행 (placeholder 공식이라도) + cited proposition ID
   - F1 (장기 추세) ∈ {valid, broken, unknown}
   - 목표가 3 단 (보수/중립/공격) 정상 발행
   - cited 풀이 v3.1 양식 (`근거 명제 풀이:` bullet, chart_data_md [4] 출처 명시)
   - response metadata 의 chart_source / chart_ohlcv_count / chart_data_age_seconds 정합
   - **chart_data_md [4] 블록이 system prompt 에 실제 들어갔는지** = system_prompt_chars 증가 (기존 ~30K → +2~3K)

2. **`ask_strategist`/`chat_strategist` httpx wrap** (RESUME Top 2 본체, ~0.4 세션) — `scripts/ask_strategist.py` + `scripts/chat_strategist.py` 가 in-process `run_strategist` 임포트 → `POST /api/strategists/{id}/chat` httpx wrap. cycle 4 partial 의 `ask_analyst` 패턴 미러. `tests/test_ask_strategist_http.py` 신규.

3. **`operational_safeguards` 권위 SPEC 정정** (~0.2 세션) — `ANALYST-PERSONAS-001` v2 매핑 표가 `operational_safeguards` 를 `trader` canon 으로 박았으나 실제 frontmatter `analyst: principle_guardian` + 본문 = principle_guardian verdict 알고리즘. SPEC v2 매핑 표 수정 + 회귀 테스트 갱신.

## 맥락 재진입 힌트

- **MS3 부분 도달** — chart_data_md [4] 블록 자동 주입 + stock_analyst v3 환각 가드 해제 = α/F1/F4/목표가 3 단 정상 발행 가능. F5 (분기 실적) 만 잔존 unknown → `INFRA-FUNDAMENTAL-DATA-001` 후속.
- **collectors/charts.py 사용법**: `await build_chart_data("005930")` → `ChartData(ticker, snapshot, indicators, source, ...)`. `render_chart_data_md(chart, name="삼성전자")` → markdown 표.
- **자동 cron 등록** — server lifespan 의 `register_infra_jobs(sched)` 가 평일 18:00 KST `infra::chart_ohlcv_refresh` 자동 등록. config 불필요 (고정 cron).
- **수동 백업** — `just refresh-charts` (DB 적재된 모든 ticker) / `just fetch-chart 005930 --days 1825` (단일 ticker).
- **3-tier fallback 동작**:
  - Tier 1: KIS fetch 실패 + DB stale ≤ 168h → `source=stale_cache` + chart_failures 적재
  - Tier 2: 지표 NaN → 부분 발행 (해당 키 null + reasons)
  - Tier 3: snapshot 60s TTL 만료 + KIS 실패 → snapshot 빈 dict + chart_failures 적재
- **v3 페르소나 정정 트레이스 3 위치** — persona.md § Anti-patterns 의 차트 인용 규율 § (가드 2 본문 정정) + § Outputs 격자 [1] Quality Grid (α·F1·F4 row 의 chart_data_md [4] 출처) + manifest.yaml response_rules 의 차트 인용 규율 § (가드 2 본문 정정).
- **본 사이클 자율 결정 트레이스** — pandas-ta 미사용 (직접 계산) + manifest target 필드 패턴 (run_analyst target_ticker kwarg 명시적) + async charts.py + 임계 분리 (_FRESH_MAX_HOURS / _STALE_MAX_HOURS).

## 커밋 상태

- 본 wrap-up commit + push 진행 (`collectors/charts.py` + `core/db/migrations/v5_chart_ohlcv.sql` + `server/schedulers/jobs/charts.py` + 신규 테스트 6 + 수정 11 파일 + RESUME + c_worked + SESSIONS)
- main 보다 앞선 커밋 0 (`git log main..HEAD` 비어있음) — 본 commit 직후 main FF 머지 불필요 (현재 브랜치 = main)
