---
date: 2026-06-09
topic: PAPER-TRADING-001 (RB-MS2) 가상매매 — spec-interview + M1~M5 풀세트 구현
status: completed
plan_file: C:\Users\HOME\.claude\plans\drifting-foraging-yeti.md
---

# 2026-06-09 · PAPER-TRADING-001 (RB-MS2) 가상매매 풀세트

## 배경
오른쪽 뇌 둘째 자식. RB-MS1(비중 산정 `size_position`)은 코드 완성됐으나 실 흐름 미연결.
RB-MS2 = "매일 도는 데스크"의 *도는* 부분 — 권고→가상체결→채점·복리 원천. spec-interview 로
SLOT 3개 채우다 **전략가 권고가 자유텍스트로만 존재(구조화·영속 0)** 차단점 발견 → C 결정(전략가가
구조 발행). 구현 직전 확인 결과 **persona 가 이미 strategist-recommendation-v1 YAML 발행 중**이라
범위 축소(파싱·영속만 신규, run_strategist/persona/계약 수정 0). 체결 모델 = **지정가 도달 판정 +
entry→stop 보간 사다리(무지성 물타기 차단) + 손절 우선 매도**. TDD 5 마일스톤.

## 한 일
- `core/strategist/recommendation.py` (신규, M1) — `parse_recommendation`(fenced YAML→dataclass,graceful)
  + `is_actionable` + `persist_recommendation`(team_outputs, run_id=rec_id 멱등) + `load_active_recommendations`
  + `persist_strategist_recommendations`(agent_responses 헬퍼).
- `core/account/paper_trading.py` (신규, M2/M3) — `compute_tranche_ladder`(보간 사다리·stop위 보장) +
  `tranches_reaching` + `record_buy_fill`(멱등) + `plan_exits`(손절우선·부분익절·오버셀 cap) +
  `record_sell_fill`(실현손익) + `get_position` + 포지션/계좌상태 파생 재계산.
- `core/account/holdings.py` (신규, M3) — `get_holdings`(DB-first 평가손익·보유기간·실현누적) + `latest_close`.
- `core/account/desk.py` (신규, M4) — `run_desk_once`(활성권고→size_position→도달 매수→매도, 멱등) +
  `db_ohlc_provider` + `run_desk_today` + DB-first 시장맥락(entry_posture/extreme).
- `core/db/schema.sql` — v14 `account_fills`(paper-fill-v1, PK rec×account×side×leg 멱등).
- `server/api/accounts.py` (신규, M4) + `server/main.py` 라우터 등록 — GET /api/accounts, /{id}/holdings.
- `server/schedulers/jobs/daily_refresh.py` — 3단계 `run_desk_today` 합류 (macro·뉴스 후, 격리 try/except).
- `server/api/production_chat.py` — non-stream·stream 양 경로 전략가 권고 자동 영속(graceful).
- `server/telegram/{bot,commands}.py` — `/accounts` 보유현황 명령 + 순수 render.
- `scripts/_paper_trading_probe.py` (신규, M5) — 격리 temp DB end-to-end 라이브 probe.
- `tests/test_{strategist_recommendation,account_paper_trading,account_holdings,account_desk,account_api}.py` — 51 신규.
- `docs/specs/PAPER-TRADING-001-...md` — SLOT 3개 + 권고 구조화(C) 섹션 + generates/modifies, status implementing.

## 검증 결과
- ✅ `TESTING=1 pytest` 전체 **1078 passed**, 회귀 0 (직전 3 snapshot 실패는 DB freshness 환경 의존, 이번 통과).
- ✅ RB-MS2 신규 51 tests GREEN (TDD RED→GREEN 각 마일스톤).
- ✅ 라이브 probe: 권고 영속→Day1 1차 매수(8.8주·6%, 사다리 1차만 도달)→재실행 멱등(0)→Day2 목표 익절·청산→vix_panic 동결(0).
- ✅ `validate.py` 0 errors (1 무관 warning). project_status PAPER-TRADING implementing.

## 의도적으로 안 한 것
- **실 LLM `swing:` 라이브 검증** — 8 분석가+전략가 다수 LLM 호출(비용·503 리스크). 결정론 probe+51 tests 로 로직 입증, persona YAML 형식이 파서와 일치 확인. 실 LLM 한 바퀴는 사용자 동석 시 capstone.
- **종목별 과열도(extension) 주입** — 데스크가 현재 extension=None(중립 분할). 스냅샷 per-ticker 연결은 SLOT.
- **수치 캘리브레이션** — 보간 분율[0.4,0.7]·R·밴드 보수 기본만, 다일 누적 후 튜닝([[feedback_backtest_essence]]).

## 기술 부채/미완
- PAPER-TRADING-001 status=implementing — 실 LLM `swing:` 검증 시 verified 승격.
- 시장맥락이 KOSPI MarketView+us_macro 단일(미장 계좌도 동일 적용) — market별 맥락 분리 SLOT.
- 데스크 OHLC 가 chart_ohlcv 의존 — 권고 종목이 universe 밖이면 최신 일봉 폴백(당일 미적재 가능).

## 다음에 이어서 할 작업 (우선순위)
1. **실 LLM `swing:` 라이브 검증 → verified 승격** — production_chat 으로 실 권고 발행→파서가 실 strategist YAML
   포착→데스크 굴림→`/accounts` 조회. persona YAML↔파서 정합 실증 후 PAPER-TRADING-001 verified.
2. **RB-MS3 채점 (GUIDANCE-ACCURACY-TRACKER-001)** — account_fills 실현손익 → 시장수익률 대비 적중률 5 KPI. `/spec-interview`.
3. **ACCOUNT-MANAGER + PAPER 수치 캘리브레이션** — 보간 분율·R·배포밴드 다일 누적 후 스윕.

## 커밋 상태
- M1 커밋·푸시 완료(`8182e0c`). M2~M5 코드 + 본 wrap-up docs 는 이 세션에서 커밋·푸시 예정.
