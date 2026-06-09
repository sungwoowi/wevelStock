---
spec_id: PAPER-TRADING-001
title: 가상매매 — 비중 지시 → 가상 체결·계좌 책임 추적 (매일 도는 데스크)
team: account_manager
type: feature
status: implementing
version: 1
level: implementation
parent: RIGHT-BRAIN-COMPLETION-001
owner: account_manager
generates:
  - core/strategist/recommendation.py            # 구조화 권고(strategist-recommendation-v1) dataclass + 검증 + team_outputs 영속/조회 helper (C 결정)
  - core/account/paper_trading.py                # 구조화 권고 → position-sizing → 가상 체결 기록 (멱등, 지정가 도달 판정)
  - core/account/holdings.py                     # 계좌별 보유·평가손익·보유기간 조회
  - core/account/desk.py                          # 매일 도는 데스크 한 바퀴 (체결+매도+평가) — run_daily_refresh 합류
  - server/api/accounts.py                       # GET /api/accounts, /api/accounts/{id}/holdings
modifies:
  - core/db/schema.sql                           # account_positions / account_fills(신규 v14) / account_state write
  - server/api/production_chat.py                # 구조화 권고 영속(persist_strategist_recommendations) — non-stream·stream 양 경로
  - server/schedulers/jobs/daily_refresh.py      # 데스크 한 바퀴(run_desk_today) 합류 — 3-surface 단일 호출점 3단계
  - server/api/__init__ (server/main.py)         # accounts 라우터 등록
  - server/telegram/{bot,commands}.py            # `/accounts` 보유현황 명령 (Telegram 슬래시 latin 제약)
  # 미수정(C 이미 충족): core/strategist/run_strategist.py · agents/strategists/track_{a,b}/persona.md
  #   — persona 가 이미 strategist-recommendation-v1 YAML 블록 발행 중이라 파싱·영속만 신규.
depends_on:
  - ACCOUNT-MANAGER-001 (비중 지시 = position-sizing-v1 — 가상 체결 입력)
  - RIGHT-BRAIN-COMPLETION-001 (소속 roadmap — 가상 전용·4계좌 경계 상속)
contracts:
  - name: position-sizing-v1
    version: "1.0"                               # ACCOUNT-MANAGER-001 정의 (입력)
  - name: strategist-recommendation-v1
    version: "1.0"                               # 기존 계약 (이미 persona 가 YAML 발행) — 본 SPEC 은 파싱·영속 미구현분을 완성 (계약 변경 X)
  - name: paper-fill-v1
    version: "1.0"                               # 본 SPEC 신규 — 가상 체결 기록 구조
---

# PAPER-TRADING-001 — 가상매매 (RB-MS2)

> **RIGHT-BRAIN-COMPLETION-001 의 둘째 자식 (RB-MS2).** ACCOUNT-MANAGER-001(RB-MS1) 후속.
> INTERVIEW-SLOT 3개 채움 완료 (2026-06-09 spec-interview). 체결 모델 = **지정가 도달 판정**(손절선이 분할·손절 구분).

## 목적

계좌관리자(RB-MS1)의 비중 *지시*(position-sizing-v1)를 받아 **가상 체결로 기록**하고 계좌 책임을 추적한다.
user_want_spec: "실전 매매는 텔레그램 의견으로 가정 + 가상 계좌별 매매 관리 내역 스키마." 매수가·비중·차수·수익률·보유기간·목표가·실현손익을 기록 → 채점(RB-MS3)·복리(RB-MS4)의 데이터 원천.
"매일 도는 책임지는 데스크" 의 *도는* 부분 = 권고→가상체결 스트림을 매일 누적.

## 경계 (roadmap 상속)

- **가상 전용** — 실 KIS 주문 X. 텔레그램 의견 = 체결 간주.
- ACCOUNT-MANAGER-001 가 정의한 `account_positions`/`account_state` 스키마에 **write** (MS1=정의/read, MS2=write/갱신).

## 핵심 정의 (스켈레톤)

| 용어 | 의미 |
|---|---|
| **가상 체결 (paper fill)** | 비중 지시 1 차수의 가상 매수/매도 기록. `paper-fill-v1`. |
| **보유 (holding)** | 계좌×종목 누적 포지션(평단·수량·차수·비중·보유기간). |
| **매매 마커** | 투자성격(중장기/단기)·예상 보유기간·근거(각 분석가 판단) 기록. |

## 권고 구조화 (C 확정 — 전략가 JSON 동시 발행, 2026-06-09)

**발견된 차단점**: 전략가 권고(진입가/손절/목표가)는 현재 LLM **자유텍스트로만** 존재
(`run_strategist.py:496` `resp["content"]`). 구조화 필드도 DB 영속도 없어, 데스크가 매일
"활성 권고의 지정가 vs 시세" 를 비교할 **구조적 원천이 없다**. → C 채택.

**C = 정하는 주체(전략가)가 발행하는 주체.** 진입가·손절·목표가는 LLM 판단이라 결정론으로 못 뽑음.
재해석(2차 추출, 옵션 A)은 해석 드리프트 위험 + 과거 cited_scores 자유텍스트 재추출 누수 패턴
([[project_cited_scores_extraction_leak]])과 동형이라 기각.

**정정(2026-06-09 구현 직전 확인)**: 전략가 persona 는 **이미** 권고 시 `strategist-recommendation-v1`
**YAML 블록을 계약상 발행**하고 있다(track_a/b persona, STRATEGY-TRACK-001 § contract). 즉 C 의
"정하는 주체가 구조 발행"은 emission 층에서 **이미 충족**. 빠진 것은 `run_strategist` 가 그 블록을
**파싱·영속하는 코드**뿐(STRATEGY-TRACK-001:179 이 `data` 영속을 의도했으나 미구현). 따라서:
- persona/계약을 JSON 으로 갈아엎지 **않는다**(불필요 churn). 기존 YAML 블록을 `yaml.safe_load` 파싱.
- 이는 옵션 B(prose 정규식 scrape)와 다름 — 전략가가 **의도적으로 발행한 전용 계약 블록**을 파싱하는 것.
- 범위 축소: persona 수정 = (필요 시) YAML 펜스 파싱 보장 1줄 보강뿐. 핵심은 파싱+영속 신규 코드.

### strategist-recommendation-v1 구조화 키 (영속 대상)
`run_strategist` 가 권고 텍스트의 YAML 블록을 파싱해 `StrategistResponse.recommendation` 첨부,
`production_chat` 가 `persist_output`(team_outputs `data_json`)로 영속.
```
recommendation_id  REC-YYYYMMDD-<ticker>-<track>   # 멱등 키
ticker / track / verdict / horizon                 # 메타
entry_price / stop_loss                            # 레버1 리스크 역산 입력 (필수 — 없으면 size_position 차단)
target_prices: [t1, t2, t3]                        # 목표 3단 (부분 익절)
risk_reward                                        # R/R
cited_scores: {s_score, t_score, alpha, buy_score, f_score}  # 확신 카운트(레버1 보너스)
```
- 파싱 실패·필드 누락 → 권고는 표시되되 **영속 skip**(graceful, 크래시 X). 가상 체결 대상에서 제외.
- 영속은 **team_outputs** (기존 통신 계약, 신규 comms 테이블 X — CLAUDE.md 절대원칙 1 일관).
- 데스크는 team_outputs 에서 활성 권고(track_a/track_b·최근 N일·미청산) read → size_position·체결.

## 판단/기록 로직 (INTERVIEW-SLOT — 채움 완료 2026-06-09)

<!-- SPEC:INTERVIEW-SLOT role="fill-recording" -->
**체결 모델 = 지정가 도달 판정** (즉시 체결 X — 가상매매 충실도 확보). 데스크 루프가 활성 권고의
미체결 차수 지정가를 당일 DB-first 시세와 비교해 **도달분만** 체결. "텔레그램 의견 = 체결 간주"는
*시점 판정*을 시장 시세에 맡긴다는 의미 (무조건 체결이 아님).

- **차수 지정가**: 1차 = 권고 진입가(`entry_price`). 2·3차 = entry→stop **보간 사다리**
  (기본 2차 = entry−0.4×(entry−stop), 3차 = entry−0.7×(entry−stop), config `split_ladder`).
  보간이라 **stop 아래로 절대 내려가지 않음** → 무지성 물타기 원천 차단(thesis-valid 구간에서만 추가매수).
- **도달 판정**: 당일 저가 ≤ 차수 지정가 → 그 **지정가에** 체결(보수적). OHLC 없으면 종가로 판정(DB-first 폴백).
- **차수 비율(얼마나)**: sizing `split_ratios`(과열도 함수, RB-MS1) 유지. 지정가(어느 가격)만 본 SPEC 담당.
- **멱등 키**: (recommendation_id × tranche_index). ON CONFLICT REPLACE. 같은 차수 재실행 무해.
- **pending**: 미도달 차수는 보유 미반영 → 다음 날 재판정. 권고 만료/무효 시 미체결 차수 취소.
<!-- /SPEC:INTERVIEW-SLOT -->

<!-- SPEC:INTERVIEW-SLOT role="sell-and-pnl" -->
**매도 = 매수와 동일한 도달 메커니즘 + 손절 우선 게이트.**

- **목표가 도달**: 당일 고가 ≥ 목표가단(target 3단) → 해당 비율 부분매도. 실현손익 누적.
- **손절 도달**: 당일 저가 ≤ stop → **보유 전량 청산**(체결된 모든 차수). 일반 손절 관령.
- **손절 우선 (충돌 규칙)**: 같은 날 stop·미체결 차수 지정가 동시 도달(갭하락 등) →
  **추가매수 안 함, 손절만 체결**, 그 날 미체결 차수 취소. "손절 시그널인데 물타기" 사고 차단.
- **실현손익**: 실현금액·실현률·성공/실패 의견 기록 → 채점(RB-MS3) 데이터 원천.
- **평가손익(미실현)**: DB-first hybrid 최신 종가로 daily 갱신(chart_ohlcv/snapshot, 없으면 KIS fetch).
  보유기간 = opened_at→현재 누적.
- trailing stop·부분 익절 후 stop 상향은 후속 SLOT (MVP는 고정 목표가·고정 stop).
<!-- /SPEC:INTERVIEW-SLOT -->

<!-- SPEC:INTERVIEW-SLOT role="daily-desk-loop" -->
**"매일 도는" = `run_daily_refresh` 3-surface 합류** (별도 cron 신설 X — 기존 단일 호출점 재사용).

매 영업일 데스크 한 바퀴 (전구간 멱등):
1. 활성 권고 미체결 매수 차수 도달 판정 → 가상 체결 (SLOT fill-recording).
2. 보유 포지션 목표가/손절 도달 판정 → 매도 체결 (SLOT sell-and-pnl). **손절 우선.**
3. 잔여 보유 평가손익·보유기간 DB-first 갱신.

- cron·CLI(`just refresh-daily`)·endpoint(`POST /api/infra/refresh-snapshots`) 어느 경로·몇 번이든 멱등.
- 알림(매수/매도/계좌 안심 텔레그램) 트리거는 **후속 SLOT** — 본 MVP는 DB 누적·조회까지.
- on-demand `swing:`/`long:` 발화 시 production_chat 배선이 즉시 1차 비중 *지시* 표시(체결과 별개, RB-MS1 render).
<!-- /SPEC:INTERVIEW-SLOT -->

## 비목표

- 비중 *결정* (RB-MS1 영역 — 본 SPEC 은 지시를 *기록*).
- 채점·KPI (RB-MS3) · 복리 곡선 (RB-MS4).
- 실 KIS 주문 (roadmap 범위 밖).
