---
date: 2026-05-20
topic: INFRA-CHART-DATA-001 SPEC 5 라운드 면담 신설 (cycle 5 SPEC only)
status: completed
plan_file: C:\Users\HOME\.claude\plans\jiggly-imagining-simon.md
---

# 2026-05-20 · INFRA-CHART-DATA-001 SPEC 5 라운드 면담 신설

## 배경

cycle 3 `stock_analyst` persona v2 가 차트 데이터 인프라 부재로 환각 가드 2 (INFRA-CHART-DATA-001 미구현 → `verdict=unknown` 강제) 박혀 α·F1·F4·목표가 3 단 결정론 산출이 차단됨. MS3 (stock_analyst 완전) 도달의 핵심 차단점. 본 세션 = SPEC frontmatter + 본문만 (~0.5 세션, 구현은 다음 사이클). 회장 결단으로 1.3 세션 풀세트 (SPEC + 구현) 대신 SPEC 만 끝내 다음 세션 구현 단계의 모호성 0 으로 박는 전략 채택.

## 한 일

- `docs/specs/INFRA-CHART-DATA-001-chart-data.md` — 신규 340 줄. frontmatter (generates 8 / modifies 9 / depends_on 2 / contracts 1 dict `chart-data-md-v1`) + 12 본문 섹션 (목적·배경·핵심정의·Phase분리·명세 8·non-goals 8·SLOT 7·다른SPEC영향 4·구현순서 15단계·테스트전략 6묶음 ~33케이스·완료기준·변경파일요약)

### R1~R5 면담 결단 누적
- **R1** 본질: 공용 인프라 (`collectors/charts.py`, 5 분석가 잠재 소비자, 즉시 활성화 = stock_analyst 1) / Phase 분리 (Phase 1 텍스트 지표 = 본 SPEC / Phase 2 vision = `INFRA-CHART-VISION-001` 후속) / non-goals 8 종
- **R2** I/O: KIS daily 5년 1825봉 + 수정주가 + 8 컬럼 / snapshot 7 필드 (`current_price`·`open`·`high`·`low`·`change_rate`·`volume_today`·`value_today`) / pandas-ta Default 6 (월봉 7·20MA / 주봉 10·20·60MA / 일봉 4·7·20·60·120MA / MACD 12-26-9 / 거래량 20일이평 spike / 52주 고저) + SLOT 2 (RSI·볼린저, WAVE-ALPHA-001 결단 후) / `chart_data_md` kwarg `[4]` 블록 (market_snapshot_md 패턴 미러) / `chart_ohlcv` 테이블 + lru_cache + 60s TTL
- **R3** 운영: 기존 `connectors/kis/client.py` 재사용 (`get_daily_chart` + `get_current_price` 추가) / APScheduler in-server `0 18 * * 1-5` cron + `just refresh-charts` 수동 백업 / 3-tier fallback (KIS 실패 → 5 영업일 stale cache / pandas-ta 실패 → 부분 발행 / snapshot 만료 → last cache) / yfinance backup 미포함
- **R4** 테스트: 6 묶음 ~33 신규 케이스 (`test_charts.py` 12 + `test_charts_indicators.py` 6 + `test_compose_chart_data_md.py` 4 + `test_run_analyst_chart_injection.py` 3 + `test_chart_ohlcv_db.py` 3 + `test_stock_analyst_v3_persona.py` 5) / TESTING=1 KIS mock 강제 / 회귀 영향 3 (`test_data_analysts_v2`·`test_seed_analysts_v2`·`test_market_snapshot`)
- **R5** 구현: 15 단계 (DB 마이그레이션 → KIS client → collectors/charts.py → 테스트 묶음 A → compose.py → 테스트 → run_analyst → 테스트 → persona v3 정정 → manifest 정정 → 테스트 → APScheduler cron → justfile → production 첫 검증 → validate.py) / schema_version 4 → 5 / SLOT 7 (`<!-- SPEC:INTERVIEW-SLOT -->` 마커) — α anchor 공식·RSI/볼린저·watchlist·yfinance·호가창·F5 분기실적·Phase 2 vision

## 검증 결과

- ✅ frontmatter 단독 파싱: `spec_id=INFRA-CHART-DATA-001` / `generates=8` / `modifies=9` / `depends_on=2` / `contracts=[dict]` / `status=draft` 정합
- ⚠️ `scripts/validate.py` 전체 실행 중 **별도 부채 발견** (본 SPEC 무관): `docs/specs/INFRA-RUNTIME-EFFICIENCY-001-runtime-efficiency.md` 의 frontmatter 2 validation 에러 — `generates` 가 `None` 으로 파싱 (cycle 4 partial 에서 status=implemented bump 시 generates 비워둔 영향) + `contracts.0` 가 dict 가 아닌 str (`"없음 (런타임 효율 — 분석가 응답 스키마 불변)"`). 다음 사이클 합류 의제.

## 의도적으로 안 한 것

- **구현 코드 진입** — KIS 어댑터·pandas-ta 의존성 추가·`collectors/charts.py`·DB 마이그레이션·compose.py·run_analyst.py·persona v3 정정. 본 세션 = SPEC frozen 만. 다음 세션 1 사이클로 구현 풀세트.
- **`stock_analyst` v3 마이크로 정정** — persona·manifest 의 환각 가드 2 해제 3 위치. INFRA 구현 후 같이 진행해야 정합 (구현 미완 상태에서 가드만 제거 = production 환각 위험).
- **`INFRA-RUNTIME-EFFICIENCY-001` v3 patch** (ask_strategist/chat_strategist httpx wrap) — 본 사이클 분량 외. 다음 사이클 별도.
- **`WAVE-ALPHA-001` α 공식 SPEC** — α anchor A·B·C 공식 결단은 R&D 부서장 영역, 인프라 SPEC 에 박으면 본질 두 갈래로 흐려짐. SLOT 처리 (S1).

## 다음에 이어서 할 작업 (우선순위)

1. **`INFRA-CHART-DATA-001` 구현 풀세트 + stock_analyst v3 마이크로 정정** (~1 세션) — MS3 부분 도달. SPEC 의 15 단계 그대로 진입 (DB 마이그레이션 → KIS client 두 메서드 추가 → `collectors/charts.py` 신규 → 테스트 묶음 A 21 케이스 → `compose.py` `chart_data_md` kwarg → `run_analyst.py` `AnalystSpec.reads_chart_data` → `stock_analyst` persona v3 정정 3 위치 → manifest 정정 → APScheduler cron + justfile → production 첫 검증 `just ask stock_analyst "삼성전자 분석"`). 완료 = α/F1/목표가 3단 정상 발행 + verdict ≠ unknown + F5 만 잔존 (`INFRA-FUNDAMENTAL-DATA-001` 후속).

2. **`ask_strategist`/`chat_strategist` httpx wrap (INFRA-RUNTIME-EFFICIENCY-001 v3 patch) + frontmatter validation 부채 정정 묶음** (~0.4 세션) — `scripts/ask_strategist.py` + `scripts/chat_strategist.py` 가 in-process `run_strategist` 임포트 → `POST /api/strategists/{id}/chat` httpx wrap 으로 변경 (cycle 4 partial 의 `ask_analyst` 와 동일 패턴 미러). 동일 commit 으로 **INFRA-RUNTIME-EFFICIENCY-001 v2 frontmatter 2 에러 정정** (`generates: []` 빈 list 명시 + `contracts: [{name: "없음 (런타임 효율 - 분석가 응답 스키마 불변)", version: "1.0"}]` dict 변환 또는 contracts 키 자체 제거). `tests/test_ask_strategist_http.py` 신규.

3. **`operational_safeguards` 권위 SPEC 정정** (~0.2 세션) — `ANALYST-PERSONAS-001` v2 매핑 표가 `operational_safeguards` 를 `trader` canon 으로 박았으나 실제 파일 frontmatter `analyst: principle_guardian` + 본문은 principle_guardian verdict 산출 알고리즘. SPEC v2 매핑 표 수정 + 회귀 테스트 갱신 + canon dir frontmatter 일관성 검사.

## 맥락 재진입 힌트

- **SPEC frozen — 다음 세션 구현은 SPEC 만 보고 모호성 0 으로 진입 가능**. 15 단계 구현 순서 + 7 SLOT (`<!-- SPEC:INTERVIEW-SLOT -->` 마커) + 8 non-goals + 4 SPEC 영향 모두 본문 박힘.
- **MS3 부분 도달 정의**: Phase 1 (텍스트 지표) 완료 = α·F1·목표가 3 단·F4·F2~F3 정상 발행. F5 (분기 실적 trigger) 만 잔존 unknown → `INFRA-FUNDAMENTAL-DATA-001` 후 완전 도달.
- **Phase 2 vision = `INFRA-CHART-VISION-001` 후속**. matplotlib + vision API provider 호환성 (gemini/claude/openai vision) 검증 필요. Phase 1 production 안정화 후 의사결정.
- **chart_data_md 토큰 비용 추정 ~2-3K**: Sonnet 200K 한계 vs (canon 18K + snapshot 9K + chart 3K) = 30K. 여유 충분.

## 커밋 상태

- 본 wrap-up commit + push 진행 (`docs/specs/INFRA-CHART-DATA-001-chart-data.md` + `docs/c_worked/2026-05-20_infra-chart-data-spec.md` + `docs/RESUME.md` + `docs/SESSIONS.md`)
- main 보다 앞선 커밋 0 (`git log main..HEAD` 비어있음) — 본 commit 직후 main FF 머지 불필요 (현재 브랜치 = main)
