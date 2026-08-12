---
date: 2026-08-12
topic: ADVISOR-CORE-001 신설 + M1 판세 트랙 (a·b·c·e) + 사용자 제보 3건 정정
status: partial
---

# 2026-08-12 · 시장 판세 트랙 — 신설·구현·라이브, 그리고 세 번의 정정

## 배경

전날 알림 개선에서 드러난 "매수 원천봉쇄"를 고친 뒤, 사용자가 **프로젝트 본질을 재정의**했다:
*"폭등장·폭락장 겪고 생각이 간결해졌다. 필요한 건 ①시장분석 ②자산/시장/종목 배분
③종목 스크리닝·추천. 정량은 최대한 결정론, 추론 필요한 지능 영역만 LLM."*

이에 따라 **Track A/B 를 접고 Track C 신설 + 시장 판세 트랙 신설**을 결정하고
`ADVISOR-CORE-001` SPEC 을 세운 뒤 M1(판세)을 a·b·c·e 순으로 구현했다.
단계 = `ENGINE-FUNNEL-REWIRE-001`(roadmap) 의 P3a+P3b 를 본 SPEC 이 흡수.

**이번 세션의 핵심 판단**: 판세가 "모르는 걸 아는 척"하지 않게 만드는 것이 기능 추가보다
중요했다 — 사용자 제보 3건이 전부 그 문제였고, 셋 다 "근거 없으면 None" 으로 통일했다.

## 한 일

### SPEC · 설계
- `docs/specs/ADVISOR-CORE-001-market-stance-and-track-c.md` — 신설(D1~D7 + §7 M1 확장).
  Track C(1콜 2관점)·A/B 비활성 보존·판세 2회·advisory·페르소나 4,000자 상한·예산 월 ₩30,000
- `docs/specs/ENGINE-FUNNEL-REWIRE-001-*.md` — children 갱신(FUNNEL-TOPDOWN+DEEP-DIVE → 흡수)

### M1-a 배선 (LLM 0)
- `core/signal/market_stance.py` — 신규. 양대 시장·야간선물·섹터 3밴드·수급 연속성·자산군 수집
  + `render_stance_facts_md`(2,000자 예산). **엇갈림을 1급 시민으로**(추세↔상승종목폭, 현물↔선물)
- `collectors/kr_futures_supply_demand.py` — `persist_futures_supply_demand` 신설.
  스냅샷에서 계산만 하고 버려지던 선물 3주체를 `supply_demand_history market='K200_FUT'` 로
- 스키마 v21 — `market_view_snapshot` PK 에 `session` + narrative/rotation_read/risk_read/stance/facts_json
  (SQLite PK ALTER 미지원 → recreate + 이관, 실 DB 47행 무손실 리허설 후 적용)

### M1-b 숏 압력
- `connectors/kis/client.py` — `daily_short_sale`·`daily_credit_balance`·`program_trade_by_stock`
  (KRX STAT 는 봇차단이지만 KIS 로 열림 — 실호출 probe 4종 확인)
- `collectors/short_sale.py` — 신규. 3축 동시 수집(축별 graceful) + 시장 집계
- 스키마 v22 — `stock_supply_history` 에 공매도·융자/대주잔고·프로그램 7컬럼

### M1-c 코스닥 섹터 RS
- `collectors/sector_rs.py` — `BENCHMARK_BY_MARKET` + `compute_sector_rs(market=)`
  + `refresh_sector_rs_all_markets`. **market 인자와 무관하게 항상 KOSPI 벤치마크였던 결함** 정정
- `collectors/kr_sectors.py` — 코스닥 테마 ETF 4종 + `ALL_TRACKED_ETFS`
- `collectors/charts.py` — 갱신 대상에 포함 + `chart_refresh_universe` 공개
- `server/schedulers/jobs/snapshot_macro.py` — build_market_view 앞에 양 시장 RS 단계

### M1-e 판세 LLM + 알림
- `core/signal/market_stance.py` — `generate_market_stance`(1콜)·`render_stance_notification`
  ·`run_market_stance`. LLM 실패 시 **알림 미발송**(빈 판세보다 침묵)
- `server/schedulers/jobs/market_stance.py` + cron 2건 (18:00 / 07:05)

### 사용자 제보 정정 3건
- **신선도** (`market_stance._index_freshness`) — 지수 차트가 08-07 에 멈췄는데
  `market_macro_snapshot` 이 매일 그 값을 복사, breadth·야간선물만 신선해 "반쯤 신선한" 판세가
  나갔다. **원천이 아니라 소비값 정합**(index_close vs 그날 차트 종가)을 검증하고, 낡으면
  LLM 호출조차 안 하고 발행 거부
- **야간선물** (`collectors/night_futures.py` 신규) — KIS `change_pct` 는 전일 대비 누적이라
  주간 상승분(+4.26%)이 섞여 "+4.31% → 갭상승"으로 오판. 세션 인식 + 주간 선물 종가 기준으로
  정정. 스키마 v23 `k200_futures_day_close`. **현물 대비 근사는 두 번 틀려서 제거**
- **다중 시간축** (F2) — `turning_signal`(rebound_attempt/fatigue) + `excess_1d/5d/20d`.
  스키마 v24. 60일만 보면 변곡이 구조적으로 후행한다는 사용자 지적 반영

## 검증 결과
- ✅ 전체 **1585 passed** (신규 테스트 ~100, 회귀 0). `scripts/validate.py` 0 errors
- ✅ **텔레그램 실발송 2회** — 판세 알림 delivered=True (2,526자)
- ✅ 라이브 LLM 판세 발행 — 숫자 환각 0(전부 사실 블록 인용), 시나리오 3건
- ✅ M1-b 실 KIS 5종목 160행 (삼전 공매도 7.14%·대주잔고 −782주 커버링 진행)
- ✅ M1-c 양 시장 19섹터 (반도체: 코스피 대비 −10.7% vs 코스닥 대비 +1.3%)
- ✅ F2 실측 — 2차전지 60일 −18.3%인데 20일 +12.4% = rebound_attempt / 화장품 fatigue
- ✅ 서버 재시작 후 cron 13건 등록 확인 (`market_stance::postclose` 18:00 / `premarket` 07:05)

## 의도적으로 안 한 것
- **M1-d 호가 장중 수집** — 사용자 판단: *"단타 칠 거 아니면 의미가 있나"*. 동의하고 접음
  (30분 스냅샷 근사 + 허수 주문 노이즈, 북극성이 중장기·스윙이라 판단을 안 바꿈)
- **Track C(M2)** — M1 판세 안착 후
- 야간선물 현물 대비 근사 — 두 번 조용히 틀려서 제거. 기준선 없으면 None

## 기술 부채 / 미완
- **F3 주도 종목 축 미착수** — 판세에 개별 종목 축이 없어 *"삼성전자가 20일선 하단에서
  변곡하는 장대양봉"* 같은 걸 못 본다. 시장·섹터 레벨만 봄
- `market_view_snapshot` 08-12 행에 정정 전 야간선물 값(4.6) 잔존 — 하루 지난 값이라 무해
- 판세 md 가 예산(2,000자) 안이지만 F2·F3 축이 늘면 재검 필요

## 다음에 이어서 할 작업 (우선순위)
1. **F3 주도 종목 축** — 지수를 끌어올린/끌어내린 상위 종목 + 20일선 관계를 판세에 추가.
   `kr_leading_stocks`·`universe_membership`·`chart_ohlcv` 재사용(신규 수집 0 예상).
   사용자 체감이 가장 큰 갭 — "반도체 투심이 바닥에서 돈다"는 판단이 여기서 나온다.
2. **M2 Track C 착수** — `agents/strategists/track_c/`(페르소나 ≤4,000자) + 라우팅 +
   판세 advisory 주입 + 2관점 렌더 + A/B 비활성 + 상위 10종·cadence 1회.
   프롬프트 사실 비중 30%→63% 역전이 목표(SPEC §3-c 표).
3. **라이브 관측 1~2일** — 18:00·07:05 판세가 자동으로 나가는지 + `/ops/llm-cost` 로
   월 환산 ₩30,000 검산. 07:00 기존 브리핑과 중복도 비교(D5) 후 흡수/하이브리드 결정.

## 커밋 상태
- `409cc4b` docs(spec): ADVISOR-CORE-001 신설
- `4d723a9` docs(spec): §7 M1 확장 (공매도·호가·프로그램·코스닥 섹터)
- `180eee6` feat: M1-a 판세 결정론 팩트 수집
- `accbc6d` feat: M1-b 숏 압력 수집
- `dfb1ab6` feat: M1-c 코스닥 섹터 RS
- `d2d595e` feat: M1-e 판세 LLM + 알림
- `46f5dec` fix: 신선도 가드
- `318993f` fix: F1 야간선물
- `1c2aecd` feat: F2 섹터 다중 시간축
