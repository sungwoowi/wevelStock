---
spec_id: AUTO-SIGNAL-GENERATION-001
title: 자동 권고 생성 — 매일 스스로 종목 스크리닝→분석가→전략가→권고 발행 (두뇌↔몸통 빠진 연결)
team: shared
type: feature
level: implementation
status: implementing
parent: BODY-AUTOMATION-001
generates:
  - core/signal/__init__.py
  - core/signal/watchlist.py          # M1: watchlist 합집합 + 결정론 스크리닝 게이트 (Stage 0)
  - core/signal/auto_signal.py        # M2: 지휘자 — funnel Stage 1(전략가 직접)→persist→notify
  - server/schedulers/jobs/auto_signal.py   # M3: cron entrypoints (09:35/12:35/14:35 장중)
  - tests/test_auto_signal.py
modifies:
  - collectors/screening.py                 # M1: signal_gate config 로더(min_score·max_candidates)
  - config/screening.yaml                   # M1: signal_gate 섹션
  - server/schedulers/jobs/__init__.py      # M3: 장중 3 cron 등록
  - server/schedulers/jobs/daily_refresh.py # M3: 18:05 종가 cadence 단계 합류
contracts:
  - name: strategist-recommendation-v1   # team_outputs, 기존 — persist 재사용
    version: "1.0"
depends_on:
  - RIGHT-BRAIN-COMPLETION-001 (데스크가 active recommendations 를 소비 — 본 SPEC 이 그 권고를 *생성*)
  - LEFT-BRAIN-COMPLETION-001 (분석가9·전략가A/B·5점수 — 권고 생성에 그대로 호출)
---

# AUTO-SIGNAL-GENERATION-001 — 자동 권고 생성 (두뇌↔몸통 빠진 연결)

> **현상 진단 SPEC (2026-06-14, 팩트 기반).** "몸통은 매일 도는데 매수/매도/관망 리포트·알림이 하나도 없던" 원인을 코드·DB로 확정하고, 빠진 연결을 채울 작업을 정의한다.

## 현상 (사실)
- 사용자 질문: "몸통은 도는데 왜 그간 매수·매도·관망·관심종목 리포트나 알림이 하나도 없었지?"
- **버그가 아니라 미구현.** 시스템은 배선된 대로 정확히 동작 중 — 자동 권고 생성 경로가 *애초에 없다*.

## 근거 (코드·DB, 2026-06-14 실측)
| 확인 | 결과 |
|---|---|
| `track_a/b` 권고 (`team_outputs`) | **총 4건, 전부 `verdict=wait`** (06-09·06-14, 과거 채팅 산물) |
| `account_fills` (가상 체결) | **0건** |
| 알림 (`notifications_log`) | `market_briefing` 11 + (legacy `None` 303) — **trade_signal·risk_alert·flow_idea = 0** |
| 권고 생성 함수 `persist_strategist_recommendations` 호출처 | **`server/api/production_chat.py` 단 하나** (사용자 채팅 트리거 전용) |
| 스케줄 잡 (`pipelines/*/manifest.yaml`) | 시황 브리핑만 (`market_briefing_pre` 07:00 / `market_briefing_now` 09:30·12:30·14:30) |
| 데스크 (`run_desk_today`, daily_refresh 18:05) | `load_active_recommendations()` 로 권고를 **소비만** — 생성 안 함 |

## 진단
```
수집(자동) → [종목 스크리닝→분석가→전략가→권고 발행: ❌ 없음] → 데스크 체결(자동) → 채점(자동) → 알림
                          ↑ 빠진 연결
```
- 권고는 **사용자가 채팅으로 물어볼 때만** 생성된다. 데스크(몸통)는 매일 돌지만 굴릴 권고가 없어 **빈손으로 돈다.**
- 있는 4건마저 방어장이라 전부 `wait` → 매수 0 → 체결 0 → 매매 알림 0.
- 이게 북극성 *"매일 **스스로** 4계좌에 매수/매도/홀딩 판단"* 의 **"스스로" 부분이 빠진** 것. 현재는 *"물어봐야 판단"*.

## 재료는 이미 있다
- **거래대금 상위 50종(watchlist) 매일 자동 적재됨** (`refresh_all_tickers`, chart_ohlcv).
- 분석가9·전략가A/B·5점수(S/T/α/buy/F)·track 라우팅 전부 라이브 (왼쪽 뇌).
- 데스크 소비·persist 계약(`strategist-recommendation-v1`)·체결·채점·알림 배선 완비.
- **빠진 건 "매일 그걸 엮어 돌리는 지휘자 잡" 하나.**

## 예정 범위 (다음 세션 인터뷰로 확정)
매일 장후(daily_refresh 합류 후보), watchlist → 분석가 → 전략가A/B → 권고 persist → 데스크가 소비.
- **방어장이어도** 전략가의 "오늘은 다 관망(wait)" 판단이 **매일 발행** = 관심종목·관망 리포트/알림이 그 자체로 생긴다(관망도 판단).
- 매수 신호 뜨는 날엔 체결→`trade_signal` 알림까지 자동.

## 설계 결정 (2026-06-15 spec-interview freeze — 6 SLOT 확정)

### SLOT1 — watchlist 정의 ✅
**거래대금 상위 50(`fetch_universe_tickers`, 기존 매일 적재) ∪ 보유 종목(`account_positions`) ∪ 사용자 관심종목(`watch_positions`).** scope = **국장만**(MVP). 미장은 buy_score 미배선이라 제외(후속 SLOT). 합집합 dedup 후 watchlist 확정.

### SLOT2 — 실행 시점·cadence ✅ (track별 다중 cadence)
| 배치 | 시각(KST, 평일) | 데이터 | 비고 |
|---|---|---|---|
| 장중 ① | **09:35** | `market_briefing_now` 09:30 스냅샷 갱신 직후 = fresh 외인·기관 수급 | |
| 장중 ② | **12:35** | 12:30 갱신 직후 | |
| 장중 ③ | **14:35** | 14:30 갱신 직후 | |
| 장마감 | **18:05** | `chart_ohlcv` 18:00 종가 확정 후 (daily_refresh 합류) | Track A 스윙·다음날 준비 |

- **왜 09:35(09:20 아님)**: 외인·기관 flow 는 09:30 스냅샷 갱신에 들어옴 → 09:20 은 stale. 사용자 도메인 논리("외인·기관 들어와야 안다")와 같은 방향, 데이터 갱신 타이밍 정합.
- **왜 18:05**: 종가 기반 결정론 점수(extension·MA-ride·α)는 `chart_ohlcv` 18:00 fetch 후라야 확정. 더 일찍은 D-1 차트.
- **정직한 한계**: 장중 차트 점수(extension·α)는 **D-1 종가 기준**(장중 일봉 미배선). 장중 신호 = **수급·가격 변화 위주**. 장중 차트 점수 정밀화 = **Phase 2**(장중 일봉/분봉 배선 선행).

### SLOT3 — LLM 비용: funnel 3단 (분석가 우회 ≠ 분석가 삭제) ✅
오늘 코드 검증 발견 — **결정론 점수(F/T/S/buy/α)는 코드가 계산, 분석가 LLM 은 해설자.** + 실제 출력 비교(flow_analyzer 05-22 = scope 거부·8.0 점수 오해 지적 = 실값 / stock_picker 05-21 = 도표 재진술 = 앵무새): **분석가 값은 *판단 케이스에만* 나온다.**

| 단계 | 대상 | LLM | 내용 |
|---|---|---|---|
| **0. 결정론 스크리닝** | watchlist 전부 | **0** | 점수 계산(collectors 직접 호출)·랭킹·임계 컷 |
| **1. 전략가 직접 (분석가 우회)** | 컷 통과분 | 종목당 ~1콜 (Flash), **배치 묶기 5~10종/콜** | 결정론 점수+원시지표를 전략가에 직접 주입(prefetch entries = metadata 점수, 분석가 LLM 텍스트 없음) → A/B verdict |
| **2. 풀 fan-out (선택)** | 매수/매도 뜬 top-K | 9분석가 + 전략가 | 감사급 권고 (override·divergence 판단 필요한 자리) |

- **채팅 경로도 동일 funnel** (사용자 요청 — 빠른 응답): 일반 질문=Stage 1 직답, 깊은 질문만 Stage 2. **분석가 9명 유지**(삭제 X — flow 사례가 실값 증명).
- 추가 절감: `llm_call_cache` 멱등 / Flash 기본·Pro 는 top-K 만([[feedback_llm_tier_strategy]]).
- 효과: 50종×9분석가 ≈ 450콜 → 결정론 컷 후 배치묶음 **~10콜**. 비용·서버·배치시간 셋 다.

**장중 다중 cadence 비용 제어 (2026-06-15 사용자 정정 — "구간 밴드")**: raw 점수/가격은 매 cadence 미세 변동 → 순수 input-hash 캐시는 장중에 거의 안 맞음(사용자 지적 정확). 두 레버로 제어:
1. **결정론 컷 = 주 필터 (캐시 무관)**: Stage 1 LLM 은 임계 통과분에만. 방어장이면 통과 0~소수 → cadence 4개라도 콜 0~소수.
2. **의사결정 밴드 게이트 (구간 밴드)**: raw 값이 아니라 **밴드 지문**으로 비교. 직전 cadence 와 밴드 지문 동일 → LLM 스킵(직전 verdict 유지·point-in-time 행만 갱신). 밴드 변동 → 재호출. → **비용 ∝ 밴드를 넘은 종목 수**(판단이 바뀔 가치가 있는 종목). 결정론·투명.
   - **밴드의 정의 (2026-06-15 사용자 질문 — "기준이 뭐냐")**: 밴드 경계 = **전략가가 이미 쓰는 의사결정 임계**(새 magic number 발명 X). "verdict 가 바뀔 수 없는 구간" = 밴드. 지문 튜플 =
     - regime (6 카테고리 자체가 밴드)
     - F/T/S/buy 점수 → persona 티어 경계로 버킷 (F: 2·4·6·8 / buy: regime별 min — 이미 persona·config)
     - 가격 → **ADR 단위 버킷** + entry·stop·target 라인 교차 여부 (ADR 이미 screening 계산)
     - R/R → regime floor 기준 버킷 (accounts.yaml floor)
     - DD kill-switch(≥4) bool · trigger 발동 bool · macro_inflection flag
   - **경계 진동 방어** = deadband/hysteresis (기존 regime 히스테리시스 백로그와 동일 기법).
   - **정확한 밴드 폭 = 캘리브레이션 SLOT** (라이브 누적 후, [[feedback_backtest_essence]]). MVP = coarse(점수 정수·가격 1 ADR·regime·bool).
3. **cadence 는 config 값**(하드코딩 금지, CLAUDE.md #9): 기본 4(09:35/12:35/14:35/18:05), 사용자가 언제든 축소/비활성.

### SLOT4 — 중복·멱등 ✅
`recommendation_id = REC-<date>-<cadence>-<ticker>-<track>` (cadence ∈ premarket/intraday1/intraday2/intraday3/postclose). **cadence 를 키에 포함**해 같은 날 시점별 권고를 별 행으로 보존(point-in-time — 오른쪽 뇌 "매일 스냅샷" 철학 일관). 동일 cadence 재실행 = `ON CONFLICT REPLACE` 멱등.

### SLOT5 — 관망 리포트·알림 정책 ✅
- **🔵 일일 요약 1건** = 18:05 종가 cadence 후 1회 ("관심종목 N 중 매수 X·관망 Y"). 장중 cadence 는 요약 push 안 함(스팸 방지).
- **🟢 매수/매도 개별 알림** = 어느 cadence든 buy/sell verdict 뜨면 즉시(장중 포착의 핵심).
- 알림 타입은 기존 `notifications_log.notification_type` distinct 값 재사용(daily_summary / trade_signal). 신규 타입 0.

### SLOT6 — production_chat 경로와의 관계 ✅
- 자동 생성분 `data.source="auto"` vs 사용자 질문분 `data.source="chat"` — 같은 `persist_strategist_recommendations` 경로, **source 태그로 구분**(컬럼 아닌 data_json 필드).
- 데스크는 둘 다 소비, 같은 (ticker, track) 충돌 시 **최신 timestamp 우선**.
- 충돌·혼선 없음: cadence·source 가 data_json 에, 알림 타입이 notification_type 에 분리 저장.

## 재사용 영향도 (가드 #11 — DATA-MAP 확인 완료)
- **신규 테이블 0.** 권고는 `team_outputs`(정본 — DATA-MAP §6, `core/strategist/recommendation.py` 가 이미 write). 체결=`account_fills`, 알림=`notifications_log`(type·is_read 이미 존재). → 데이터 도메인 전부 기존, 컬럼 추가도 불필요.
- **신규 collector/connector 0.** 점수 입력은 기존 collectors(`flow_inputs`·`technicals`·`s_score_inputs`·`buy_score_inputs`·`anchors`) 직접 호출. watchlist=`collectors/screening.fetch_universe_tickers`(기존).
- **신규는 오케스트레이션 모듈만** (`core/signal/`) — 데이터가 아니라 *기존 함수들을 매일 엮어 돌리는 지휘자*. 같은 도메인 테이블/모듈이 없어서가 아니라, "엮어 돌리는 잡"이 존재하지 않기 때문(빠진 연결). 3층 파급: DB(team_outputs 재사용·write 증가) → backend(`run_desk_today` 가 더 많은 active 권고 소비) → frontend(데스크/알림이 더 풍부 — 화면 변경 0, 데이터만 채워짐).
- **재사용 함수**: `persist_strategist_recommendations`·`load_active_recommendations`(recommendation.py) / `run_strategist`·`render_prefetched_analyst_outputs`·`_deterministic_scores_from_metadata`(run_strategist.py) / `run_desk_today`(desk.py) / `run_daily_refresh`(daily_refresh.py) / `is_macro_inflection`(market_macro.py) / `notification/service`.

## 완료 정의
사용자 개입 0으로 매일 4 cadence(09:35/12:35/14:35/18:05)에 watchlist 가 결정론 스크리닝→funnel→권고(매수/관망)로 발행되고(Track A·B 모두, 국장), 데스크가 그 위에서 체결·관망 리포트를 산출하며, 🔵 일일 요약 1건 + 🟢 매수/매도 개별 알림이 나간다 → 몸통이 빈손으로 돌지 않는다. (LLM 비용 = 결정론 컷 + 배치묶음으로 ~10콜/cadence 수준.)
