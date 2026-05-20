---
date: 2026-05-21
topic: INFRA-FUNDAMENTAL-DATA-001 구현 풀세트 + stock_analyst v4 마이크로 정정 (cycle 10)
status: completed
plan_file: C:\Users\HOME\.claude\plans\vast-snacking-crane.md
---

# 2026-05-21 · INFRA-FUNDAMENTAL-DATA-001 구현 풀세트 (cycle 10)

## 배경

cycle 9 (2026-05-20) 에서 SPEC frozen 완료. 본 사이클 = SPEC § 구현 순서 의 **15 단계 풀세트 실행**. 사용자 "uv 명령어는 묻지 말고 스스로 해" 자율 실행 신호 → 묶음 A→B→C→D→wrap-up 한 호흡에 진행 (5 commit 분할). 미러 = cycle 6 의 `INFRA-CHART-DATA-001` 구현 풀세트 패턴.

## 사용자 결정 + 자율 결정

| # | 트랩 | 결정 |
|---|------|------|
| 1 | yfinance 내부 LRU | **자동**: process restart 시 reset, 본 TTL 과 무관. 그대로 사용. |
| 2 | quarterly_financials 정렬 | **자동**: yfinance descending 기본 → recent-first list 변환 그대로. |
| 3 | 분기 라벨 포맷 | **자동**: `f"{ts.year}Q{(ts.month - 1) // 3 + 1}"` helper inline (`_quarter_label`). |
| **4** | **YoY 산출 위한 5분기 저장** | **사용자 결정 ✅**: SPEC § 2 schema 의 quarterly_data 4분기 vs § 3 형식의 YoY 표기 불일치 → **5분기 저장 + render 표는 최근 4분기 노출 + QoQ/YoY 자동 산출**. 5분기 미달 시 YoY = "N/A" 명시. |
| 5 | yfinance mock 패턴 | **자동**: `monkeypatch.setattr("collectors.fundamentals.YFinanceClient", lambda: mock_yf)` (test_charts.py mock_kis 패턴 1:1 미러). |
| 6 | watchlist source | **자동**: `KR_NAME_TO_TICKER` 35종 (run_analyst.py) + `fundamentals` DB distinct ticker union. |
| 7 | commit 분할 | **자동**: 묶음별 4 commit + wrap-up 1 = **5 commits** (롤백 안전, 회귀 추적 용이). |
| 8 | KOSPI/KOSDAQ 구분 | **자동 발견 트랩**: yfinance 의 `.KS` (KOSPI) vs `.KQ` (KOSDAQ) suffix 필요 → run_analyst.py 에 `KOSDAQ_TICKERS` set (시총 상위 9종) + `market_for_ticker(ticker)` 헬퍼 추가. resolve_ticker 시그니처 미변경 (회귀 0). |

## 한 일 (SPEC 15 단계 그대로 풀세트)

### 묶음 A — 데이터 인프라 (commit `1532760`)
- `core/db/migrations/v6_fundamentals.sql` 신규 + `core/db/schema.sql` v5→v6 (fundamentals 테이블 + schema_version 6)
- `connectors/yfinance/client.py` 갱신 — `YFinanceClient` class 추가 (`fetch_info` / `fetch_quarterly` / `fetch_full` + `_to_yf_ticker` + `_quarter_label` + `_clean_float` + `FundamentalNotAvailable` exception). 기존 `get_index/get_indices` 보존. yfinance API drift 대응 (`quarterly_financials` ↔ `quarterly_income_stmt` try/except fallback).
- `collectors/fundamentals.py` 신규 ~600줄 (charts.py 1:1 미러):
  - `Fundamentals` dataclass (ticker/market/fetched_at/5 ratio TTM/3 quarterly list/quarter_labels/source/stale_hours/failures)
  - `get_fundamentals(ticker, market, *, yfinance_client, force_refresh, max_age_seconds)` async DB-first 24h TTL + 3-tier fallback (Tier 1 yfinance 실패→stale_cache≤7d / Tier 2 ratio None→부분 발행 N/A / Tier 3 quarterly 빈→"분기 데이터 없음")
  - `render_fundamental_data_md(f, name)` `fundamental-data-md-v1` 계약 markdown 표 풀세트 — TTM 5 ratio 표 + 분기 4분기 표 + QoQ/YoY 자동 산출 + 가속/둔화/정체 라벨 자동
  - `refresh_all_tickers()` + `__main__` CLI (refresh/fetch 서브커맨드)
- 테스트 12 케이스 신규 (`test_fundamentals.py` 9 = yfinance fetch + DB persist / DB-first fresh skip / 24h stale refetch / yfinance 실패 + stale fallback / yfinance 실패 + DB 부재 None / FundamentalNotAvailable + DB 부재 None / render 풀세트 + YoY 자동 / render null 안전 / render YoY 5분기 미달 N/A · `test_fundamentals_db.py` 3 = schema_version 6 + fundamentals 테이블 / ON CONFLICT REPLACE 멱등 / quarterly_data JSON round-trip)
- **검증**: pytest 395 → 407 (+12)

### 묶음 B — 주입 파이프라인 (commit `2181ee7`)
- `core/knowledge/compose.py` — `build_pipeline_prompt(fundamental_data_md=)` kwarg 신설. `[4]` chart 직후 `[5]` fundamental 블록 직렬 추가. 기존 `[5]` RAG → `[6]` shift + `[6]` response_rules 주석 → `[7]` shift. docstring layout 7 라인 갱신.
- `core/inference/run_analyst.py` — `AnalystSpec.reads_fundamental_data` 필드 (52줄 직후) + `load_analyst_spec` manifest 로드 + `_maybe_build_fundamental_data_md` 헬퍼 (chart 헬퍼 1:1 미러) + `run_analyst`/`run_analyst_stream` 양쪽 fundamental_meta 7 키 spread (`fundamental_source` / `fundamental_fetched_at` / `fundamental_age_seconds` / `fundamental_failures` / `fundamental_quarter_count` / `fundamental_ratios_count` / `fundamental_ticker_used`). **KOSDAQ_TICKERS set + market_for_ticker(ticker) 헬퍼** (KOSPI = "KS", KOSDAQ = "KQ" 자동).
- `agents/analysts/stock_analyst/manifest.yaml` — `reads_fundamental_data: true` 플래그 추가 (다른 분석가 default False).
- 테스트 10 케이스 신규 (`test_compose_fundamental_data_md.py` 4 + `test_run_analyst_fundamental_injection.py` 6 — KOSDAQ market="KQ" 자동 전달 + get_fundamentals None → no_fundamental_data failure 케이스 추가).
- **검증**: pytest 407 → 417 (+10) / chart shift 회귀 0

### 묶음 C — stock_analyst v4 정정 (commit `ca93dc6`)
- `agents/analysts/stock_analyst/persona.md` 3 위치 정정 + v4 트레이스 § 신설:
  - § Outputs 격자 [1] Quality Grid F2/F5: `INFRA-FUNDAMENTAL-DATA-001 후속 (현재 unknown)` → `fundamental_data_md [5]` 출처 + v3 단계 → v4 단계 라벨 전환
  - § Outputs StandardOutput confidence: `F2·F5 만 잔존 unknown 시` → `fundamental_data_md [5] 부재 시`
  - § Reasoning Doctrine F1~F5 정의 표 F2/F5: 5 ratio 정량 임계 (PE/ROE/Op.Margin/Debt/Eq) + 분기 4분기 QoQ·YoY 출처
  - § verdict 매핑 결측 표현 갱신
  - § v3 정정 트레이스 § 보존 + § v4 정정 트레이스 § 신설 (MS3 완전 도달 명시 + 후속 SPEC = WAVE-ALPHA-001 / INFRA-FUNDAMENTAL-CROSS-VALIDATE-001)
- `agents/analysts/stock_analyst/manifest.yaml` 헤더 v3 → v4 + response_rules F2/F5 정의 본문 정정 + v3 정정 → v4 정정 라벨
- 테스트 5 신규 (`test_stock_analyst_v4_persona.py` = manifest reads_fundamental_data:true + Quality Grid F2/F5 정정 + Reasoning Doctrine v4 + manifest response_rules v4 + v4 트레이스 § + v3 흔적 보존)
- **검증**: pytest 417 → 422 (+5) / v3 페르소나 테스트 회귀 0 (deprecation X)

### 묶음 D — 운영 cron (commit `0f2d415`)
- `server/schedulers/jobs/fundamentals.py` 신규 (charts.py 1:1 미러, `run_fundamentals_refresh()` cron entrypoint)
- `server/schedulers/jobs/__init__.py` register_infra_jobs 에 `infra::fundamentals_refresh` 등록 (`day_of_week=sun, hour=18, minute=0, timezone=Asia/Seoul`)
- `justfile` 2 레시피 (`refresh-fundamentals` 전체 + `fetch-fundamental` 단일 디버깅, KOSDAQ 예시 명시)
- **검증**: pytest 422 (회귀 0)

### 묶음 wrap-up (본 commit)
- SPEC frontmatter v1 → v2 + `status: draft → implemented`
- `docs/c_worked/2026-05-21_infra-fundamental-data-impl.md` 신규 (본 파일)
- `docs/RESUME.md` Top 갱신 (Top 1 = production smoke 잔여 / Top 2 production UX 본질 / Top 3 자료 0 시드 5명 검증)
- `docs/SESSIONS.md` 행 추가

## 검증 결과

- ✅ pytest 395 → **422 passed** (+27 신규: 묶음 A 12 + B 10 + C 5, 회귀 0)
- ✅ scripts/validate.py 0 errors (1 warnings = teams/registry.yaml 부재, 본 사이클 무관)
- ✅ SPEC frontmatter v2 + status: implemented 단독 파싱 통과
- ✅ stock_analyst manifest `reads_fundamental_data: true` 로드 검증
- ✅ run_analyst metadata 7 fundamental 키 정합
- ✅ KOSDAQ ticker (247540) → market="KQ" 자동 전달 검증
- ✅ Track Selector 양 트랙 (Track A·B) 회귀 0

## 의도적으로 안 한 것

- **Production smoke (Step 15)** = 실 yfinance 호출 필요 (network) + 사용자 활성 시 webapp `ask_analyst stock_analyst "삼성전자 분석" --provider claude_code --target 005930` 호출로 [5] 블록 LLM read + F5·F2 정상 발행 + verdict ≠ inconclusive 확인 → **MS3 완전 도달 ✨**. RESUME Top 1 잔여 (cycle 6 chart 미러 패턴).
- **DART 이중 검증 (Phase 2)** — `INFRA-FUNDAMENTAL-CROSS-VALIDATE-001` 별도 SPEC.
- **SLOT 4 필드** (forward EPS·PE·배당수익률·현금흐름) — Phase 2 또는 사용자 의사결정 후.
- **pyproject.toml yfinance 버전 핀** — 기존 `yfinance>=0.2` 가 이미 deps 에 있어 본 SPEC 명시 `>=0.2.40,<0.3` 핀은 보류. yfinance API drift 시 핀 갱신 권유 (try/except fallback 으로 현 호환성 확보).
- **`Ticker.earnings` deprecated 경고** — yfinance 0.2.x 의 `quarterly_earnings` deprecated. try/except 로 보호되어 본질 영향 0. SLOT 갱신 시 `income_stmt` Net Income 으로 대체 가능 (백로그).

## 다음에 이어서 할 작업 (우선순위)

1. **Production smoke 검증 + MS3 완전 도달 시연** (~0.3 세션) — 사용자 webapp `target=005930` + `analyst=stock_analyst` 호출. 응답 검사:
   - `system_prompt_chars` 증가 (cycle 6 의 ~31K + fundamental_data_md ~3K = ~34K)
   - metadata `fundamental_source = yfinance` (첫 호출, 24h TTL 들어가면 `db`)
   - metadata `fundamental_quarter_count = 5` + `fundamental_ratios_count = 5`
   - `verdict ≠ inconclusive` (chart + fundamental 둘 다 주입 시 confirmed_*)
   - cited 풀이 v3.1 양식 (chart_data_md [4] + fundamental_data_md [5] 양쪽 출처 명시)
   - F2·F5 정상 발행 (양호·경고·약화 / 가속·둔화·정체)
   - **MS3 완전 도달 ✨** 시연 commit + wrap-up

2. **production UX 본질 구현** (~3 세션) — `feedback_webapp_production_ux.md` 첫 본격 사이클. MS3 완전 도달 후 자연 진입.

3. **자료 0 시드 5 분석가 페르소나 풀세트 production 검증** (~1.5 세션) — 5 분석가 production 호출 검증 + boundary 가드 + news_curator SLOT S2.

## 맥락 재진입 힌트

- **5 분기 저장 결정 트레이스**: SPEC § 2 schema 의 4분기 명시 ↔ § 3 형식의 YoY 표기 불일치 → 사용자 5분기 채택. DB JSON 의 quarterly_data list 길이 = 5. render 표는 최근 4분기 노출 + QoQ(0 vs 1)/YoY(0 vs 4) 자동 산출. 5분기 미달 = "N/A".
- **KOSDAQ_TICKERS set 위치**: `core/inference/run_analyst.py` L178~ (KR_NAME_TO_TICKER + KR_TICKER_TO_NAME 직후). 시총 상위 9종. 신규 KOSDAQ 등록 시 set 갱신 + market_for_ticker(ticker) 자동 분기.
- **fundamental_data_md 자동 주입 흐름**: stock_analyst manifest `reads_fundamental_data: true` → `_maybe_build_fundamental_data_md(spec, target_ticker)` → resolve_ticker (한글 종목명 자동 매핑) → market_for_ticker → get_fundamentals (DB-first 24h TTL) → render_fundamental_data_md → compose.build_pipeline_prompt `[5]` 블록.
- **v3 흔적 보존 원칙**: v4 정정 시 v3 트레이스 § 보존 (deprecation X). v3 페르소나 테스트 (5 케이스) 그대로 통과 — chart_data_md 출처 명시는 v3 = v4 공통이라 v4 정정과 무관.
- **yfinance 의존성**: pyproject `yfinance>=0.2` 이미 deps. YFinanceClient class 추가만으로 활성. 기존 `get_index/get_indices` (해외 지수 + 금) 와 분리된 영역.

## 세션 중 실 비용

- LLM API 호출 0 회 (mock yfinance 만 사용, 실 yfinance 호출 0)

## 커밋 상태

- `1532760` 묶음 A (yfinance + DB v6 + 12 tests)
- `2181ee7` 묶음 B (compose [5] + run_analyst + 10 tests)
- `ca93dc6` 묶음 C (stock_analyst v4 + 5 tests)
- `0f2d415` 묶음 D (scheduler + justfile)
- 본 wrap-up commit + push 진행
