---
date: 2026-06-01
topic: S-Score SLOT 정밀화 — supply_chain 실측화 + alignment 비례 정규화 (같은 날 2번째 세션)
status: completed
plan_file: C:\Users\HOME\.claude\plans\zesty-strolling-sunbeam.md
---

# 2026-06-01 · S-Score SLOT 정밀화 (supply_chain 실측화 + alignment 정규화)

## 배경
같은 날 1번째 세션에서 S-Score를 라이브 배선했으나 2개 축이 임시 상태로 남음: **supply_chain=MVP 중립 고정(5.0)**,
**alignment=부분 데이터 저평가 편향**. 이번 세션은 이 둘을 **완결 가능한 결정론 부분**으로 정밀화. RS 가중치
R1/R2/R3 실튜닝은 다일 누적 의존(F-Score S2와 동일)이라 분리. 핵심 판단: theme→섹터 RS는 이미 있는 재료
(`classify_theme`+`sector_rs`)를 매핑 테이블 하나로 연결만 하면 됐고, alignment는 결측 위계를 0 기여가 아니라
*평가 제외*로 보는 비례 정규화가 본질(품질 측정이지 데이터 양 측정 아님).

## 한 일
- `config/score_inputs.yaml` — `flow.theme_sector_mapping` 신규(테마 10종 → SectorRS.sector 이름 리스트, kr_sectors 기준).
- `collectors/score_inputs_config.py` — `get_theme_sector_mapping()` getter(`get_theme_taxonomy` mirror).
- `collectors/screening_inputs.py` — `compute_supply_chain_score`(순수: theme→매핑 섹터 최강 RS, 없으면 중립) 신규 + `build_s_score_inputs(sector_rs=)` 파라미터 + `classify_theme`(2-Stage 캐싱) 연동 + `ScreeningInputs` supply_chain_theme/sector 필드 + render 셀 갱신. **`compute_alignment` 비례 정규화**(earned/available_max×10, 결측 위계 평가 제외).
- `core/inference/run_analyst.py` — `_maybe_build_s_score_inputs_md` 가 `snapshot.sector_rs` 를 build 에 전달(추가 fetch 0).
- `agents/analysts/stock_picker/persona.md` — supply_chain 정의 정합(classify_theme → sector_rs 실측).
- `tests/test_screening_inputs.py` — compute_supply_chain 7 + alignment 정규화 기대값 갱신/신규 3 + build sector_rs 주입 2 = +11.

## 검증 결과
- ✅ 테스트 **758 → 769 (+11, 회귀 0, TESTING=1)**. validate.py **0 errors**.
- ✅ 실데이터 smoke(090430 아모레=manual cosmetics, LLM 없이 결정론): supply_chain **7.5**(TIGER 화장품 섹터 RS, source=theme_sector) — **중립 5.0 탈피 확인**.

## 의도적으로 안 한 것
- **RS R1/R2/R3 실튜닝 보류** — k/regime 가중치/percentile 정합은 다일 다종목 누적 데이터 필요(F-Score S2 패턴). 단일 패스는 1차 캘리브레이션에 그쳐 가치 얕음. `screening_distribution.py`(flow_distribution 미러) 진단 도구 + 분포 정합은 후속.
- **MFI/Vol Osc 도입 안 함** — `compute_indicators`에 미구현(pandas-ta 회피). persona도 MA 기반만 정의 → 코드·persona 정합. alignment 정밀화는 MFI가 아니라 부분 데이터 정규화가 실체였음.

## 기술 부채/미완
- **buy_score CAN SLIM 7축 미배선** = 5점수 마지막 1칸. C/A(EPS)·N(52주신고가)·L(SCREEN-RS) 자체 산출 가능하나 **S/I/M 축=cross-agent**(F-Score=flow_analyzer, regime=market_state_analyzer) → CLAUDE.md 절대원칙 1(import 금지·DB read만)과 얽힘. inline 재계산 vs team_outputs DB read 경계 결정 필요.
- **S-Score RS 가중치 production 미튜닝** — config/screening.yaml R1/R2/R3 = prism 초기값.
- supply_chain: kosdaq_theme 등 매핑 없는 테마는 중립(섹터 ETF 부재 — 구조적 한계).

## 맥락 재진입 힌트
- supply_chain 흐름: `classify_theme(ticker)`(manual_theme→결정론 / LLM Stage2 캐싱) → theme → `get_theme_sector_mapping()` → `snapshot.sector_rs`에서 매핑 섹터 필터 → 최강 rs_score. sector_rs 없으면 classify 호출도 skip(중립).
- alignment 정규화: 결측 위계(월/주봉 짧은 종목)는 available_max에서 빠짐 → 일봉만 정배열 종목도 10점 가능(구 구현 max 3 막힘 해소).
- 새 테마 추가 시: `flow.theme_taxonomy`+`theme_authority`+`theme_sector_mapping` 3곳 정합 유지.

## 다음에 이어서 할 작업 (우선순위)
1. **buy_score CAN SLIM 7축 배선** ⭐ — 5점수 마지막. C/A(EPS=fundamentals)·N(52주신고가)·L(SCREEN-RS) 자체 산출 + **S/I/M cross-agent 경계 결정**(inline 재계산 vs team_outputs DB read) + run_analyst hook + manifest `reads_buyscore`.
2. **RS 분포 진단 + R1/R2/R3 1차 캘리브레이션** — `screening_distribution.py`(flow_distribution 미러) 신규 + leading 종목으로 rs/extension 분포 수집 → config 1차 정합. 실튜닝은 누적 후.
3. **F-Score breakpoint 운용 재튜닝** — `scripts/flow_distribution.py` 재실행 다일·다종목 분포 → flow 3축 중간점 정밀화.

## 커밋 상태
- 코드 1 커밋(`5147aea`) + wrap-up docs 1 커밋. 사용자 요청으로 **push 예정**. main 직접(솔로).
