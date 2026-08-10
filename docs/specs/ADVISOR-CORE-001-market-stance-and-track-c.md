---
spec_id: ADVISOR-CORE-001
title: 전용 투자 어드바이저 코어 — 시장 판세 트랙(2회/일) + 전략가 Track C(1콜 2관점)
team: shared
type: feature
level: implementation
status: draft
parent: ENGINE-FUNNEL-REWIRE-001
generates:
  - agents/strategists/track_c/persona.md      # ≤4,000자 (하드 상한, 테스트로 강제)
  - agents/strategists/track_c/manifest.yaml   # canon_categories 선별 주입
  - core/signal/market_stance.py               # 판세 판단 LLM 1콜 + 영속 (2회/일)
  - tests/test_market_stance.py
  - tests/test_track_c.py
modifies:
  - core/db/schema.sql                         # market_view_snapshot 컬럼 확장(신규 테이블 0)
  - collectors/market_view.py                  # session 축 + narrative 필드 read/write
  - core/signal/auto_signal.py                 # _TRACK_ID/_TRACK_LABEL 에 C + 판세 md 주입
  - core/strategist/run_strategist.py          # market_stance_md 슬롯 (news_digest_md 와 같은 패턴)
  - core/signal/daily_digest.py                # 2관점 렌더 (중기/단기)
  - config/screening.yaml                      # tracks=["C"] · max_candidates 10 · cadence 1회
  - server/schedulers/jobs/__init__.py         # 판세 cron 18:00 / 07:05
contracts:
  - name: strategist-recommendation-v1         # 기존 — Track C 도 동일 YAML. 2관점은 data 필드로
    version: "1.0"
depends_on:
  - AUTO-SIGNAL-GENERATION-001 (깔때기·cadence·밴드게이트 재사용)
  - NEWS-SOURCE-001 (뉴스 다이제스트 = 판세 입력)
  - MARKET-VIEW-SYNTHESIS-001 (market_view_snapshot = 판세 저장소)
  - AUTO-SIGNAL-DIGEST-001 (알림 렌더)
supersedes:
  - FUNNEL-TOPDOWN-001 (P3a 탑다운 배선 — 본 SPEC 의 시장 판세 트랙이 흡수)
  - DEEP-DIVE-REPORT-001 (P3b 심층 리포트 출구 — 본 SPEC 의 Track C 가 흡수)
---

# ADVISOR-CORE-001 — 전용 투자 어드바이저 코어

> **사용자 재정의 (2026-08-11)**: 초반의 욕심을 접고 폭등장·폭락장을 겪은 뒤 남은 것.
> *"필요한 건 시장흐름을 눈치있게 파악하는 것, 그리고 어떤 상황에서든 FOMO 오지 않되 시장이
> 주는 만큼을 먹을 줄 아는 기민한 배팅과 시장이 무너질 때 회피하는 능력, 최악이 와도 무너지지
> 않는 포트폴리오."*
>
> → 필요한 층 3개: **1. 시장분석 · 2. 자산/시장/종목 배분 · 3. 종목 스크리닝 및 추천.**
> 본 SPEC 은 **1 과 3**. (2 는 `ACCOUNT-MANAGER-001`·sizing 이 이미 있어 다음 단계.)
>
> **원칙**: 로직으로 해석 가능한 정량 데이터는 **최대한 결정론**, 추론이 필요한 지능 영역만 **LLM**.

## 1. 왜 — 진단

### 1-a. 매수/매도가 안 나온다 (해소 착수)

| | 전체 기간 |
|---|---|
| `track_b` | **560건 전부 wait. buy·sell 역대 0건** |
| `track_a` | 468 wait / 12 buy / 6 hold (**97.5% wait**) |

직접 원인이었던 분산일 blanket 은 2026-08-11 소프트 밴드로 재보정
([AUTO-SIGNAL-INTEGRITY-001](AUTO-SIGNAL-INTEGRITY-001-auto-signal-integrity.md) 개정).
본 SPEC 은 그 위의 **판단 층**을 다시 짓는다.

### 1-b. 프롬프트가 "사실 30% · 지시문 70%" 다 — 앵무새의 구조적 원인

Track A 실측(2026-08-11, 블록별 문자 수):

| 성격 | 블록 | 문자 | 비중 |
|---|---|---:|---:|
| **지시문·지식** | 페르소나 20,955 + canon 18,462 + 응답규칙 3,433 | **42,850** | **70%** |
| 사실 | 뉴스 10,781 + 시장 스냅샷 4,438 + RAG 2,476 + **종목 점수표 613** | 18,308 | 30% |
| | 합계 | 61,158 | |

**종목 점수표가 613자**다. 판단할 재료는 거의 없고 출력 형식을 지시하는 규칙만 산더미 —
"일반 LLM 쓸 때보다 멍청한 앵무새"라는 사용자 체감의 실체가 이 비율이다.

### 1-c. Track A/B 분리가 값을 못 했다

A(중장기)/B(단기) 분리는 종목당 전략가 콜을 2배로 만들었지만, 두 트랙이 같은 점수표를 보고
같은 게이트를 통과하며 사실상 같은 결론(wait)을 냈다. 분석가 9 는 **자동 경로에서 이미 우회**
중이고(`team_outputs` 적재 역대 0건) 당분간 운용 계획도 없다.

### 1-d. 예산

LLM 지출 목표 = **월 ₩30,000**(영업일 22일 → **₩1,364/일**). 최근 실측 일평균 ₩3,300
(월 ₩73,000) — 2.4배 초과. *"종목 개수를 많이 분석하는 정도"* 에는 그 이상 쓰지 않는다.
단 적중률이 실증되면(예: 7월 대하락장에 삼전·하닉 매도 리포트) 월 ₩100,000 도 가능 —
**돈은 콜 개수가 아니라 판단 품질에 쓴다.**

## 2. 결정 (2026-08-11 인터뷰)

| # | 결정 | 근거 |
|---|---|---|
| D1 | **Track C 신설** — 종목당 **1콜**이 중기 매수의견 + 단기 트레이딩 의견 **2관점**을 함께 발행 | 콜 절반. 두 관점이 같은 맥락을 공유해 모순도 감소 |
| D2 | **Track A/B 는 비활성 보존** — config 스위치 off, 폴더·과거 1,046건 데이터 유지 | Track C 안정화까지 롤백 가능 + 채점·백테스트 재료 보존 |
| D3 | **시장 판세 트랙 신설 — 하루 2회** (18:00 장마감 · 07:05 아침) | 사용자: *"제일 중요한 건 시장흐름을 눈치있게 파악하는 것"* |
| D4 | **판세 → Track C 는 advisory** — 코드가 막는 건 진짜 폭락(당일급락·breadth붕괴·VIX패닉·분산≥9)뿐. 판세와 다른 판단을 내면 사유 기록 | 하드컷 금지(부모 SPEC D1). 오늘 고친 분산일 blanket 과 같은 결 |
| D5 | **아침 판세는 기존 07:00 브리핑과 병행** 후 비교 → 흡수/하이브리드 결정 | 사용자: 유사하거나 더 나은 부분이 있으면 그때 교체 |
| D6 | **cadence 1회(18:05) × 상위 10종 × 1트랙 = 10콜/일** | 예산 ₩30,000 에 맞는 유일한 조합 |
| D7 | **Track C 페르소나 4,000자 하드 상한** (테스트로 강제) | 다이어트의 실체. 현 track_a 20,955자 |

## 3. 설계

### 3-a. 전체 흐름

```
[결정론 — 최대한 여기서]                    [LLM — 추론이 필요한 곳만]

watchlist(거래대금 ∪ 거래량양봉 ∪ 보유)
  → 스크리닝 컷 rank_candidates
  → 매매 매력도 상위 10종
  → 종목별 점수표(S/T/F/buy/α) + 가격대 메뉴

18:00 장마감 ───────────────────→ ① 시장 판세 (장마감판) · 1콜
  (macro·섹터RS·수급 갱신 직후)        섹터 로테이션(기술↔가치)·수급 주체·
                                        매크로 소화·종목 선후행 서술
                                              ↓ advisory 주입
18:05 ──────────────────────────→ ② Track C × 10종 · 10콜
                                        중기 매수의견 + 단기 트레이딩 의견

07:05 아침 ─────────────────────→ ① 시장 판세 (아침판) · 1콜
  (미장·야간선물·뉴스·실적 수집 후)     밤사이 이벤트를 어떻게 소화할지
                                        → 사람용 알림 + 다음 18:05 C 입력
```

### 3-b. 시장 판세 트랙 (M1)

**입력** (전부 기존 자산 read — 신규 수집 0): `market_view_snapshot`(regime·entry_posture·
섹터 rotation/leading/fading) · `us_macro_snapshot` · 뉴스 다이제스트 · 5주체 수급 · 지수·breadth.

**출력** — 사용자가 말한 "촉"을 그대로 구조화:

| 필드 | 내용 |
|---|---|
| `narrative` | 판세 서술 — 지금 흐름이 기술주 중심인가 가치주 중심인가, 금리·매크로 이벤트를 시장이 어떻게 소화하는가 |
| `rotation_read` | 어느 섹터가 선행하고 어느 쪽이 후행하는가 (결정론 sector_rs 를 **해석**) |
| `risk_read` | 무너질 조짐인가 눌림인가 — 회피 판단 |
| `stance` | 기민한 배팅 / 관망 / 회피 (사람이 읽는 한 줄) |

**저장** — 신규 테이블 0. `market_view_snapshot` 컬럼 확장 + PK 에 `session` 추가:

```sql
ALTER TABLE market_view_snapshot ADD COLUMN session TEXT DEFAULT 'postclose';  -- postclose|premarket
ALTER TABLE market_view_snapshot ADD COLUMN narrative TEXT;
ALTER TABLE market_view_snapshot ADD COLUMN rotation_read TEXT;
ALTER TABLE market_view_snapshot ADD COLUMN risk_read TEXT;
ALTER TABLE market_view_snapshot ADD COLUMN stance TEXT;
-- PK (date, market) → (date, market, session)
```

### 3-c. Track C (M2)

`agents/strategists/track_c/` **폴더 드롭** — plugin 패턴이 원래 설계라 코드는
`_TRACK_ID`/`_TRACK_LABEL` 에 한 줄씩만 추가.

**2관점 = 1콜.** `strategist-recommendation-v1` 계약은 그대로 두고 2관점을 `data` 필드로:

```yaml
verdict: buy          # 종합 결론 (기존 필드 — 데스크·체결이 소비)
data:
  mid_term:           # 중기 매수의견
    verdict: buy
    horizon: "4~8주"
    thesis: "..."
    entry_zone: [...]
    stop_loss: ...
  short_term:         # 단기 트레이딩 의견
    verdict: wait
    horizon: "3~10일"
    thesis: "..."
    trigger: "..."
  divergence_reason: "중기는 매수·단기는 대기 — 눌림 진행 중이라 ..."
```

두 관점이 갈리면 `divergence_reason` 을 강제한다 — 모순을 숨기지 않고 **사용자가 읽을 정보**로.

**프롬프트 예산 (D7 · 다이어트의 실체)** — 축소가 아니라 **역전**:

| 성격 | 현재(A) | Track C 목표 |
|---|---:|---:|
| 페르소나 | 20,955 | **≤4,000** |
| canon | 18,462 (9부서 전량 재귀) | **~2,000** (manifest `canon_categories` 선별) |
| 응답 규칙 | 3,433 | ~1,500 |
| **시장 판세 서술** | 0 | **2,000** (신규) |
| **종목 점수표·원시지표** | **613** | **3,000** (5배↑) |
| 시장 스냅샷 | 4,438 | 3,000 |
| 뉴스 | 10,781 | 4,000 (압축) |
| RAG | 2,476 | 1,000 |
| **합계** | 61,158 | **~20,500** |
| **사실 비중** | **30%** | **63%** |

LLM 이 판단할 재료는 **늘고** 지시문은 줄어든다. 입력 토큰 ~1/3.

**"통찰 아티클 주입"** (사용자 니즈) = manifest `canon_categories` 선별 주입 경로.
드롭 → 자동 반영은 KNOWLEDGE-SYNC-001 이 이미 담당. 9부서 전량 로드로 되돌리지 말 것.

### 3-d. 안전핀 (D4)

코드가 강제하는 것은 **진짜 폭락뿐**: 당일 지수 급락 · breadth 붕괴 · VIX 패닉 · 분산일 ≥ 9.
판세가 "회피"인데 C 가 매수를 내면 **막지 않고** `llm_deviation_reason` 을 요구·기록한다
(Tier 4 채점 재료). 판세를 게이트로 올리면 오늘 고친 blanket 문제가 상위 레이어에서 재발한다.

### 3-e. 비용 목표

| 항목 | 콜/일 | 콜당 | 일 |
|---|---:|---:|---:|
| 시장 판세 (시장 1건, 입력 ~12k) | 2 | ₩81 | ₩162 |
| Track C (종목 10, 입력 ~13k · 2관점 출력) | 10 | ₩114 | ₩1,140 |
| 기존 소액 (theme_match 등) | — | — | ₩110 |
| **합계** | **12** | | **₩1,412** |

**× 22 영업일 = 월 ₩31,000.** D5 병행 비교 기간에는 +₩80/일(월 +₩1,800) 초과 —
비교 종료 후 하나로 합치면 목표 안으로 들어온다. **M3 에서 원장 실측으로 검산한다.**

## 4. 마일스톤

| M | 범위 | 완료 기준 |
|---|---|---|
| **M1** | 시장 판세 트랙 — 스키마 확장 + `market_stance.py` + cron 18:00/07:05 + 알림 | 판세 2회 발행·영속, 사람이 읽고 "오늘 시장 어떤가"에 답이 됨 |
| **M2** | Track C — 페르소나(≤4,000자)·manifest·라우팅 + 판세 advisory 주입 + 2관점 렌더 + A/B 비활성 + 상위 10종·cadence 1회 | 10종 권고 발행, 프롬프트 실측 ≤20,500자, 매수/매도가 실제로 나옴 |
| **M3** | 라이브 관측 — 07:00 브리핑 대비 비교(D5) → 흡수/하이브리드 결정 + 비용 원장 검산 | 월 환산 ₩30,000 이내 확인, 판세 중복 해소 |

M1 부터 가는 이유: 판세가 C 의 입력이고, 그 자체로 사용자가 말한 "제일 중요한 것"이다.

## 5. 재사용 영향도 (가드 #11)

| 축 | 판정 |
|---|---|
| 신규 테이블 | **0** — `market_view_snapshot` 컬럼 확장 (rotation·leading·fading 은 이미 있음) |
| 신규 파이프라인 | **0** — 아침 재료는 `market_briefing_pre` 수집 stage 5개 재사용 |
| 신규 collector/connector | **0** |
| 신규 전략가 | Track C 1개 — **폴더 드롭**(plugin 패턴, 코드 2줄) |
| 신규 모듈 | `core/signal/market_stance.py` 1개 — 판세 LLM 은 기존 어느 모듈에도 속하지 않음 |
| 계약 | `strategist-recommendation-v1` **무변** — 2관점은 기존 `data` 필드 활용 |
| LLM 콜 | 30건/일(현 최대) → **12건/일** |

## 6. 미결 / 후속

- **2번 층(자산·시장·종목 배분)** — `ACCOUNT-MANAGER-001`·`sizing.py` 존재. Track C 안착 후 연결.
- **뉴스 다이제스트 10,781 → 4,000 압축** — M2 안에서 하되, 압축 규칙은 결정론(격상 이벤트 우선).
- **분석가 9** — 당분간 미운용(사용자 결정). 폴더·페르소나는 보존, 채팅 경로에서만 사용.
- **F2 근본(프롬프트 지연)** — Track C 가 ~1/3 크기라 87.7초 문제도 함께 해소될 전망. M2 에서 실측.
