---
date: 2026-05-31
topic: INFRA-STOCK-SUPPLY-001 — 종목 레벨 5주체 수급 collector (SPEC→구현→KRX 로그인 벽→KIS 3주체 피벗→단위 버그 정정, 라이브 점등)
status: completed
plan_file: C:\Users\HOME\.claude\plans\compressed-juggling-fairy.md
---

# 2026-05-31 · 종목 레벨 수급 collector (KIS 3주체, 라이브 점등)

## 배경
F-Score 세 축(theme_match·momentum·inflow_speed)이 전부 시장 레벨(KOSPI 집계) 프록시라 종목 변별력 0 (라이브에서 005930 theme_match가 모든 종목과 동일한 4.5). 종목 레벨 수급을 넣어 실측 승급. **핵심 판단 3건**: (1) 분류(LLM)⊥채점(결정론) 분리 덕에 theme_match 골격은 `net_sums` 입력만 교체하면 재사용 (2) KRX 통계가 로그인 벽이라 KIS 3주체로 피벗 (theme_authority 영향 거의 0) (3) KIS 순매수 거래대금 필드는 이미 백만원 — ÷1e6 금지.

## 한 일
- `docs/specs/INFRA-STOCK-SUPPLY-001-stock-level-supply.md` (신규) — 5라운드 면담 결단 10건. R1-a는 KRX 5주체→KIS 3주체로 구현 중 정정.
- `core/db/schema.sql` — `stock_supply_history` 테이블 (PK (ticker,date), 5주체 net) + schema v9. `CREATE TABLE IF NOT EXISTS`라 기존 DB도 자동 생성.
- `connectors/kis/client.py` — `stock_investor_history(ticker)` 신규 (외인·기관·개인 일별 시계열). **단위 버그 정정**: `*_ntby_tr_pbmn`은 이미 백만원 → ÷1e6 제거.
- `connectors/krx/client.py` — `stock_investor_supply` helper (휴면 — 로그인 벽으로 보류, 5주체 복귀 시 활성) + bld 400 진단 주석.
- `collectors/stock_supply.py` (신규) — `ensure_stock_supply_series`(KIS 1콜 멱등 upsert/cutoff) + upsert/load + `get_stock_supply_60d` + `get_stock_market_cap`(KIS 시총 억→백만원). financial_inv/pension=0, source=stock_kis. `supply_demand_history.py` mirror, `agreement_score` 재사용.
- `collectors/flow_inputs.py` — `build_flow_inputs`가 종목 수급(KIS) 우선 → 미가용 시 시장 supply_demand_history graceful fallback(source 라벨) + market_cap 주입. render 종목/프록시 표기.
- `tests/test_stock_supply.py` (신규 16) — 멱등 upsert/load 정순/fetch(KIS mock)/cutoff/market_cap 변환/fallback + 단위 회귀 가드(`test_investor_history_no_division`, 실서버 raw 고정).

## 검증 결과
- ✅ pytest **698 → 714 passed** (+16, 회귀 0, TESTING=1).
- ✅ **라이브 서버 end-to-end GREEN** (005930, is_mock=False): source=stock_kis. 단위 정정 후 외인 30일 -1,661억 / 기관 +801억 (현실 규모) → theme_match 4.0 / momentum -1.0 / inflow_speed -46.4 / advisory_f 2.5. "오늘 +5.84%는 기관 견인이나 30일 외인 순매도 우위=수급 약" 방어 가능 신호.
- ✅ KIS_IS_PAPER=false(실서버) 원시값으로 단위 버그 확정 — 모의계좌 문제 아님.

## 의도적으로 안 한 것
- **KRX 5주체 복구** — getJsonData STAT 통계가 로그인 벽+안티봇("LOGOUT"). 방법 B(pykrx 추정값) 전부 400. devtools 실요청 캡처(방법 A) 필요. 휴면 helper로 보존.
- **theme_authority pension→institution 명시 정정** — pension_net=0이라 자동으로 institution만 반영(defense_nuclear 정상 작동), config 무변경.

## 기술 부채/미완
- **market_breadth(MDCSTAT04302, INFRA-SNAPSHOT-EXTEND-001) 잠복 고장** — KRX STAT 로그인 벽으로 동일하게 400, 지금껏 silent fallback 중. KRX 실요청 해소 시 종목 5주체와 함께 복구.
- **KIS 시총 hts_avls 단위** — 005930에서 1,853조로 큰데, price 317,000(미래 sim 데이터) 기준이면 내부 정합(별 버그 아님). 다른 종목 교차 확인 권장.
- **환경 사고**: 세션 중 백그라운드 pytest 다수가 죽지 않고 venv 락을 쥐어 이후 `uv run` 전부 무한 정지 → `TaskStop`으로 해소. (8000 좀비 소켓과 동류의 Windows 좀비. 백그라운드 pytest 남발 주의.)

## 맥락 재진입 힌트
- 종목 수급 단위 정합 레퍼런스 = `market_investor_total`(시장 레벨, 동일 필드 백만원 무변환). 새 KIS 금액 필드 추가 시 이걸 기준 삼을 것.
- theme_match 채점은 net_sums만 받으므로, KRX 5주체 복구 시 collector fetch만 KIS→KRX로 교체하면 골격 재사용.

## 다음에 이어서 할 작업 (우선순위)
1. **SLOT S2 임계 + theme_authority production 튜닝** — 이제 실 종목 수급이 들어오니 `config/score_inputs.yaml` breakpoints·theme_authority를 실 분포로 정합 + 다종목 라이브 검증(현대차/하이닉스 등 종목별 변별 확인).
2. **KRX 5주체 복구 (방법 A)** — data.krx.co.kr 개별종목 투자자별 거래실적 페이지 devtools로 실 getJsonData 요청 캡처 → bld/params/세션 이식. market_breadth 잠복 고장 동반 복구.
3. **buy_score·S-Score 후속 배선** — scoring.py 정식 가중치(SLOT S7) + SCREEN-RS-EXTENSION-001(rs 축) 같이.

## 커밋 상태
- 코드 4 커밋 push 완료: `5083a70`(SPEC) / `107c5fb`(구현 KRX) / `55c16bd`(KIS 피벗) / `a5ef3b1`(단위 버그 정정). wrap-up docs는 본 세션에서 커밋·push (main 직접, 솔로).
