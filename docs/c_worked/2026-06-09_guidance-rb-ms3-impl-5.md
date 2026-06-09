---
date: 2026-06-09
topic: GUIDANCE-ACCURACY-TRACKER-001 (RB-MS3) 채점 — spec-interview + 슬림 MVP 구현
status: completed
plan_file: C:\Users\HOME\.claude\plans\drifting-foraging-yeti.md
---

# 2026-06-09 · GUIDANCE-ACCURACY-TRACKER-001 (RB-MS3) 슬림 MVP

## 배경
오른쪽 뇌 셋째 자식(채점). 같은 날 PAPER-TRADING(RB-MS2) verified 직후 `/spec-interview`.
기존 SPEC 은 **RB-MS2 전 작성**(prism 차용, 독립 30/60/90 KIS 가격추적·guidance_records 별도
테이블·5 KPI)이라 RB-MS2 와 상당 중복 → reconciliation 필요. **핵심 판단**: account_fills(실제
가상매매 실현손익) 재사용 / 벤치마크=시장 대비 *정직한 검산*(공격 목표 아님) / 슬림 MVP /
집계 view(복사 0, 진실 원천 하나, CLAUDE.md 절대원칙 1).

## 한 일
- `core/guidance/benchmark.py` (신규, G1) — 트랙×시장 지수(국장 ^KS11·미장 ^GSPC) [체결일,청산일]
  구간 수익률. `index_symbol`·`benchmark_return_pct`(순수)·`compute_benchmark_return`(fetch 주입, 기본 yfinance, graceful None).
- `core/guidance/kpi.py` (신규, G2) — `get_kpi_summary(track, period_days)`: account_fills(청산된 권고만)
  +team_outputs(stop/RR) read·계산. 실현수익률·벤치마크 초과(알파)·방향 적중률·R/R 실현율·트랙 분리. guidance-kpi-v1.
- `core/guidance/retrospective.py` (신규, G3) — `render_retrospective` 회고 양식(코드라벨 0, 중장기/단기 친화).
- `server/api/guidance.py` (신규) + main 등록 — GET /api/guidance/kpi, /retrospective.
- `server/telegram/{bot,commands}.py` — `/retro` 회고 명령.
- `scripts/_guidance_probe.py` (신규) — end-to-end probe.
- `tests/test_guidance_{benchmark,kpi,retrospective,api}.py` — 19 신규.
- `docs/specs/GUIDANCE-ACCURACY-TRACKER-001-...md` — 슬림 MVP 재정렬 권위 섹션 + S1~S6 해소, status draft→implementing.

## 검증 결과
- ✅ `TESTING=1 pytest` 전체 **1097 passed**(+19, 회귀 0). validate 0 errors.
- ✅ TDD G1~G3 RED→GREEN. 라이브 probe(2 청산: 익절 +30%·손절 -10% → 실현 평균 10%·시장 대비 +5%p·적중률 50%·R/R 33.4%·회고 양식·트랙 분리).
- ✅ project_status `🔨 GUIDANCE-ACCURACY-TRACKER-001 [implementing]`, RIGHT-BRAIN 1/4(25%)·진행중 2.

## 의도적으로 안 한 것 (MVP 비목표 → SLOT)
- **독립 30/60/90 KIS 가격 추적 + 비체결(wait/hold) 권고 채점** — RB-MS2 체결 기반만(책임지는 데스크=실제 한 매매). 비체결 품질은 가격추적 인프라 필요.
- **자가 진단 정확도 KPI#4** — 권고에 🔴 신뢰 라벨 부재 → 계산 불가(죽은 KPI).
- **MDD** — 청산 포지션 일중 저점 시계열 필요(account_fills 엔 체결가만). 트랙분리서 MDD 보류.
- **KPI 스냅샷 영속·일일 cron·KPI 가중치 자동학습·회고분석가 PROPOSAL** — 후속.

## 기술 부채/미완
- GUIDANCE status=implementing — 실 데이터(라이브 청산) 누적 후 KPI 검증 시 verified.
- 벤치마크 yfinance 실호출은 `/회고` 시점 네트워크(테스트는 주입). 캐싱/스냅샷 영속 SLOT.
- 이전 세션(같은 날): PAPER-TRADING-001 **verified**(실 LLM swing 검증, gemini 503 bounded 재시도 신설). 별 로그 [2026-06-09_paper-trading-rb-ms2-impl-4.md].

## 다음에 이어서 할 작업 (우선순위)
1. **RB-MS4 복리 — WEALTH-COMPOUND-TRACKER-001** (오른쪽 뇌 마지막 자식). `/spec-interview` → 계좌 자산 베이스·복리 곡선·account_fills 실현손익 누적 기반. RIGHT-BRAIN 2~4/4.
2. **ACCOUNT-MANAGER-001 verified 승격** — RB-MS2/3 가 size_position 을 실 데스크·채점에 쓰므로 implementing→verified 점검.
3. **수치 캘리브레이션 + 라이브 청산 누적** — 보간 분율·R·밴드 + KPI 임계, 라이브 데스크 청산 다일 누적 후([[feedback_backtest_essence]]).

## 커밋 상태
- 코드(feat `d58914f`) 완료. 본 wrap-up docs(docs) → main 직접 + push 예정.
