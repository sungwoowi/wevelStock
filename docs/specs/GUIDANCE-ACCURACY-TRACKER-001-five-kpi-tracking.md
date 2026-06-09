---
spec_id: GUIDANCE-ACCURACY-TRACKER-001
title: 가이던스 적중도 5 KPI 추적 — 권고 ID + 가격 추적 + 트랙별 가중치 + 회고 자동 보고
team: shared
type: infra
status: implementing
version: 1
level: implementation
parent: RIGHT-BRAIN-COMPLETION-001   # RB-MS3 채점 — 오른쪽 뇌 roadmap 편입 (2026-06-09)
owner: agent_layer
# ── 슬림 MVP 재정렬 (2026-06-09 spec-interview, RB-MS2 기반). 하단 원 상세는 후속 참조. ──
generates:
  - core/guidance/benchmark.py                   # 트랙×시장 지수 보유기간 수익률 (chart_ohlcv/yfinance 재사용)
  - core/guidance/kpi.py                         # account_fills+team_outputs read → 핵심 KPI + 벤치마크 초과 집계 (집계 view, 복사 X)
  - core/guidance/retrospective.py               # `/회고` 양식 렌더
  - server/api/guidance.py                       # GET /api/guidance/kpi, /api/guidance/retrospective
modifies:
  - server/telegram/                             # `/회고` 명령 신설
depends_on:
  - PAPER-TRADING-001 (account_fills 실현손익·체결일·매도사유 = 채점 입력 — RB-MS3 핵심 의존)
  - STRATEGY-TRACK-001 (전략가 권고 = strategist-recommendation-v1, team_outputs 영속)
  - RIGHT-BRAIN-COMPLETION-001 (소속 roadmap — RB-MS3)
contracts:
  - name: guidance-kpi-v1
    version: "1.0"                               # 본 SPEC 신규 — KPI 집계 결과 구조 (집계 view 산출)
# (후속 SLOT: core/guidance/{recorder,tracker}.py·guidance_records 테이블·독립 30/60/90 KIS 가격 추적
#  = 비체결 wait/hold 권고 채점 + 자가진단 정확도 KPI 용. MVP 는 account_fills 실현 기반만.)
---

# GUIDANCE-ACCURACY-TRACKER-001 — 적중도 5 KPI 추적

## 목적

**자산 복리 구조 보장** 이 wevelStock 의 궁극 목표. 그 달성 = 일관된 수익률 = **가이던스 적중도** 가 보장. 본 SPEC = 적중도 추적 인프라.

- 전략가 (Track A·B) 권고 발행 시 → DB 에 권고 ID + 메타 자동 적재
- 30·60·90일 후 실제 가격 추적 → 5 KPI 자동 계산
- 트랙별 가중치 차별 (A: 수익금 게임 / B: 손익비 게임)
- `회고` 단축어 → 90일 보고 자동 출력
- Layer 5 회고분석가 (별도 SPEC) 의 PROPOSAL 입력 원천

## 슬림 MVP 재정렬 (2026-06-09 spec-interview — 권위, 하단 원 상세보다 우선)

> 본 SPEC 은 RB-MS2 전 작성(prism 차용). RB-MS2(PAPER-TRADING-001)가 권고→가상체결→**실현손익**을
> 이미 영속하므로, 독립 가격 추적·별도 테이블을 폐기하고 **RB-MS2 데이터를 읽어 채점**한다.

**① 데이터 원천 = RB-MS2 재사용** (신규 가격 추적 cron 0):
- `account_fills`(PAPER-TRADING-001) — 실제 가상 체결·**realized_pnl_krw**·filled_date·매도 사유(target/stop).
- `team_outputs`(track_a/track_b) — 권고 entry/stop/target/track/verdict (`load_active_recommendations` 패턴).
- `account_positions`/`holdings` — 미실현 평가손익·보유기간.
- 채점 대상 = **데스크가 실제 체결·청산한 권고**("책임지는 데스크"=자기가 한 매매 채점). 비체결(wait/hold)은 후속 SLOT.

**② 벤치마크 = 시장 대비 정직한 검산** (잣대이지 공격 목표 아님):
- 트랙×시장 지수: 국장(KR)=코스피, 미장(US)=S&P500(또는 나스닥, config). 보유기간 [체결일, 청산일] 구간 지수 수익률.
- **초과수익(알파) = 권고 실현수익률 − 동기간 지수수익률**. "이 시스템이 그냥 지수 사두는 것보다 나은가" 의 검산. 여러 KPI 중 하나(MDD·적중률과 나란히), 알파 최대화 강박 X.
- 지수 데이터 = chart_ohlcv/yfinance 재사용(신규 수집 0).

**③ 핵심 KPI (MVP — 전부 account_fills 실현 기반, +5% 가정 임계 아님)**:
1. **실현 수익률(%)** — 청산 권고의 realized_pnl / 투입 자본.
2. **벤치마크 초과(알파, %p)** — 실현수익률 − 보유기간 지수수익률.
3. **방향 적중률(%)** — 청산 권고 중 realized_pnl > 0 비율 (실제 익절/손절 결과로 판정).
4. **R/R 실현율(%)** — 실제 (청산가−진입가)/(진입가−stop) vs 권고 R/R.
5. **트랙 분리** — A vs B 승률·평균 보유일·MDD(일중 저점 기준) 분리 노출.

**④ 저장 = 집계 view (복사 0, 진실 원천 하나)**:
- `core/guidance/kpi.py::get_kpi_summary(track, period_days)` 가 team_outputs+account_fills 를 **read·계산**. 별도 guidance_records 테이블 폐기(중복·drift 회피, CLAUDE.md 절대원칙 1). KPI 스냅샷 영속도 MVP 는 불요(on-demand 집계).

**MVP 비목표(후속 SLOT)**: 독립 30/60/90 KIS 가격 추적 / wait·hold 비체결 권고 채점 / 자가진단 정확도 KPI#4(권고에 🔴 라벨 부재) / KPI 가중치 자동학습 / 회고분석가 PROPOSAL / KPI 스냅샷 영속·일일 cron.

**의사결정 SLOT 해소** (하단 S1~S6):
- S1 가격 출처 → **RB-MS2 account_fills 실현(독립 KIS 추적 폐기, MVP)**. S2 자가진단 → **MVP 제외**(라벨 부재).
- S3 추적 기간 → **실제 체결일~청산일**(고정 30/60/90 폐기, 데스크 실현 기준). S4 `회고` → production_chat + 텔레그램.
- S5 MDD → 일중 저점 기준(보수, account_fills/holdings 기반). S6 회고분석가 입력 → `get_kpi_summary` 집계 view.

## 배경 / 문제

- v3.0 이원 트랙 설계서 (자료 B) § 6 = 적중도 측정 프레임워크 = 본 SPEC 의 원천.
- prism-insight 의 누적 수익률 +244% 는 인상적이나 **승률 45%** = 한 번의 큰 수익이 9 번 손실 메꿈 → 일관성·재현성·복리 구조 약함.
- wevelStock 차별점 = **점진 누적 +100~150% / 적중률 70%+ (Track A) / 50%+ (Track B)** + MDD -8% 이하. 5 년 후 = 1억 → 2.3억 (꾸준한 18%/년 + 견딜만한 MDD).
- 적중도 데이터 부재 시 = 시스템 자가 진화 (Layer 5 회고분석가의 PROPOSAL) 가 grounding 0. **추적 인프라 = 자가 진화의 전제**.
- 본 SPEC 은 추적·계산만. 회고분석가의 PROPOSAL 발행은 별도 SPEC (`RETROSPECT-ANALYST-001` 백로그).

## 핵심 정의

| 용어 | 의미 |
|---|---|
| **권고 (recommendation)** | STRATEGY-TRACK-001 의 strategist-recommendation-v1 객체. 진입가·목표가 3단·stop_loss·트랙·점수. |
| **권고 ID** | `REC-YYYYMMDD-<ticker>-<track>` 형식. 본 SPEC 의 추적 단위. |
| **5 KPI** | 방향 적중률 / 타점 정밀도 / R/R 실현율 / 자가 진단 정확도 / 트랙 분리 효과. |
| **트랙별 가중치** | Track A·B 의 본질 게임이 다르므로 같은 KPI 라도 가중치 차별. |
| **가격 추적** | 30·60·90일 후 실제 가격 + 실제 최고가·최저가. cron 으로 daily 갱신. |
| **자가 진단 정확도** | 시스템이 🔴 (추정·차트확인필요) 라벨 단 항목이 실제로 부정확했던 비율. |

## 비목표

- **회고분석가 (Layer 5) PROPOSAL 자동 발행** — `RETROSPECT-ANALYST-001` 백로그.
- **실 매매 실행** — Layer 4 계좌관리자 별도 SPEC.
- **KPI 가중치 자동 학습** — 운용 데이터 누적 후 PROPOSAL 영역.
- **사용자 정정 패턴 자동 학습** — 후속 SPEC (v3.1 자기 학습 마일스톤).
- **차트 데이터 인프라** — `INFRA-CHART-DATA-001` 백로그. 본 SPEC 은 가격 추적 = 일봉 종가만 (KIS 일봉 API 활용).

## 5 KPI 정의 + 트랙별 가중치

### KPI #1. 방향 적중률 (Direction Hit Rate)

**정의**: 권고 후 N 일 (default 30) 내 예측 방향 도달 비율.

```
매수 권고 후 +5% 이상 도달 → Hit
매도 권고 후 -5% 이상 하락 → Hit
대기 권고 후 박스 유지 (-3% ~ +3%) → Hit
```

- **Track A 목표**: 70%+ (수익금 게임의 핵심)
- **Track B 목표**: 55%+ (손익비 게임 — R/R 로 보상)
- **가중치**: Track A 30% / Track B 15%

### KPI #2. 타점 정밀도 (Entry Precision)

**정의**: 권고 진입가 vs 실제 30 일 내 저점 차이.

```
타점_오차율 = (권고진입가 - 실제30일저점) / 실제30일저점 × 100%
±3% 이내 → A급 / ±5% 이내 → B급 / ±10% 이내 → C급 / 10%+ → D급
```

- **목표**: A+B 합계 60%+
- **가중치**: Track A 15% / Track B 20% (단기는 타점 = 손익비 핵심)

### KPI #3. R/R 실현율 (R/R Realization)

**정의**: 권고 R/R 대비 실제 실현 R/R.

```
실현_R_R = (실제최고가 - 진입가) / (진입가 - stop_loss)
실현율 = 실현_R_R / 권고_R_R × 100%
```

- **목표**: 50%+ 시스템 신뢰 / 80%+ 시스템 우월 / 30% 미만 재검토
- **가중치**: Track A 15% / Track B 35% (손익비 게임의 핵심)

### KPI #4. 자가 진단 정확도 (Self-Diagnosis Accuracy)

**정의**: 시스템이 🔴 (추정·차트확인필요) 라벨링한 부분이 실제로 부정확했던 비율.

```
진단_정확도 = (🔴 라벨 중 실제 부정확 항목 수) / (총 🔴 라벨 수) × 100%
```

- **목표**: 70%+ (메타 인지 정상 작동) / 30% 미만 = 라벨링 무의미
- **가중치**: Track A 15% / Track B 15%

### KPI #5. 트랙 분리 효과 (Track Separation Effect)

**정의**: Track A vs Track B 권고의 본질에 맞는 성과 분리.

| 지표 | Track A 목표 (수익금) | Track B 목표 (손익비) |
|------|-------------------|-------------------|
| 1순위 | 절대 수익금 (KRW 누적) | R/R 실현율 (%) |
| 2순위 | 승률 70%+ | 월 회전율 5-15회 |
| 3순위 | 평균 보유 60일+ | 평균 보유 7-14일 |
| 4순위 | MDD -8% 이하 (복리 보호) | 손절 절대룰 준수율 100% |
| 5순위 | 자산 베이스 증가율 | 월 인컴 안정성 (변동계수) |

- **가중치**: Track A 25% / Track B 15%
- **실패 시그널**: Track A 수익금 ↑ 인데 MDD ↑↑ / Track B 회전율 ↑ 인데 R/R 실현 ↓

### 트랙별 종합 점수 공식

```
Track A 종합 = 방향적중률×0.30 + 타점×0.15 + R/R×0.15 + 자가진단×0.15 + 트랙분리×0.25
   → 강조: 방향적중률 + MDD (복리 구조 보호)

Track B 종합 = 방향적중률×0.15 + 타점×0.20 + R/R×0.35 + 자가진단×0.15 + 트랙분리×0.15
   → 강조: 손익비 실현 + 타점 정밀도 (월 인컴 안정성)
```

## guidance-record-v1 데이터 구조

```json
{
  "recommendation_id": "REC-20260513-005930-A",
  "issued_at": "2026-05-13T09:30:00+09:00",
  "ticker": "005930",
  "display_name": "삼성전자",
  "track": "A",
  "verdict": "buy",
  "entry_price": 285000,
  "target_price_1": 320000,
  "target_price_2": 380000,
  "target_price_3": 450000,
  "stop_loss": 270000,
  "risk_reward": 3.2,
  "cited_scores": {
    "s_score": 8.5,
    "t_score": null,
    "alpha": 1.6,
    "buy_score": null,
    "f_score": 7,
    "cited_propositions": ["W1", "SP1", "M2"]
  },
  "reliability_label": "🟢",
  "red_label_items": [],
  "confidence": 80,
  "tracking": {
    "day_30": {
      "tracked_at": null,
      "close_price": null,
      "highest": null,
      "lowest": null,
      "direction_hit": null,
      "entry_grade": null,
      "rr_realization": null
    },
    "day_60": { /* ... */ },
    "day_90": { /* ... */ }
  },
  "actual_outcomes": {
    "max_drawdown_pct": null,
    "actual_holding_days": null,
    "final_pnl_pct": null
  },
  "contract_version": "1.0"
}
```

## DB 스키마 (guidance_records 테이블)

```sql
CREATE TABLE IF NOT EXISTS guidance_records (
  recommendation_id TEXT PRIMARY KEY,
  issued_at         TEXT NOT NULL,                  -- ISO 8601
  ticker            TEXT NOT NULL,
  display_name      TEXT,
  track             TEXT NOT NULL,                  -- "A" | "B" | "<custom>"
  verdict           TEXT NOT NULL,                  -- "buy" | "hold" | "sell" | "wait"
  entry_price       REAL NOT NULL,
  target_price_1    REAL,
  target_price_2    REAL,
  target_price_3    REAL,
  stop_loss         REAL,
  risk_reward       REAL,
  cited_scores_json TEXT,                           -- JSON 직렬화
  reliability_label TEXT,                           -- 🟢🟡🔴
  red_label_items_json TEXT,
  confidence        INTEGER,
  tracking_json     TEXT,                           -- day_30/60/90 누적
  actual_outcomes_json TEXT,
  contract_version  TEXT NOT NULL DEFAULT '1.0',
  created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_guidance_ticker_issued ON guidance_records (ticker, issued_at DESC);
CREATE INDEX IF NOT EXISTS idx_guidance_track_issued ON guidance_records (track, issued_at DESC);
```

**ON CONFLICT REPLACE 멱등 보장** (recommendation_id PK).

## 가격 추적 cron

`core/guidance/tracker.py` 가 매일 KIS 일봉 API 호출:

1. `guidance_records` 에서 `issued_at + 30·60·90 일 < today` 이면서 `tracking[day_N].tracked_at IS NULL` 인 권고 조회
2. KIS 일봉 API 로 해당 ticker 의 `issued_at ~ issued_at + N` 구간 종가 + 최고가·최저가 회수
3. `direction_hit / entry_grade / rr_realization` 계산
4. `tracking_json` UPDATE

**APScheduler 등록**: `daily 18:00 KST` (장 마감 + 1 시간 후 KIS 일봉 데이터 안정).

## `회고` 단축어 출력 양식

```
📊 최근 90일 가이던스 적중도 회고

【총 권고 건수】 28건 (Track A 12 / Track B 16)

【KPI 결과】
1. 방향 적중률: Track A 75% / Track B 62%  ✅
2. 타점 정밀도: A+B급 65%  ✅
3. R/R 실현율: Track A 평균 82% / Track B 평균 58%  ⚠️
4. 자가 진단 정확도: 71%  ✅
5. 트랙 분리 효과: 승률 분리 정상 (A 75% vs B 62%)  ✅

【가장 적중한 권고 Top 3】
1. 삼성전자 5/13 매수 → +18% 도달 (목표가 1 달성). cited: [W1, SP1, M2]
2. SK하이닉스 4/20 매수 → +24% 도달. cited: [W1, W5]
3. 한화에어로 3/15 매수 → +12% 도달. cited: [SP1]

【가장 빗나간 권고 Top 3】
1. 카카오 4/02 매수 → -8% 도달 (stop_loss 발동). 사유: 일봉 위계만 보고 월봉 위계 무시
2. ...

【시스템 진화 권장】
→ Track B 의 R/R 실현율 58% 로 낮음. trailing stop 임계값 재조정 필요.
→ 회고분석가 (Layer 5) PROPOSAL 검토 권장.
```

## 마일스톤 (세션 단위)

| 세션 | 범위 | 통과 기준 |
|------|------|----------|
| 세션 1 (현재) | 본 SPEC 신설 | frontmatter / 본문, validate.py 통과 |
| 세션 2 | DB 마이그레이션 + `recorder.py` 골격 + STRATEGY-TRACK-001 의 권고 발행 시 자동 적재 | guidance_records 1 행 적재 검증 |
| 세션 3 | `tracker.py` + APScheduler 등록 + KIS 일봉 회수 | 1 일 cron 발동 → 30 일 도달 권고 1 건 자동 갱신 |
| 세션 4 | `kpi.py` 5 KPI 계산 + `retrospective.py` 90일 보고 | `회고` 단축어 출력 검증 |
| 세션 5 | `server/api/guidance.py` + 텔레그램 `/회고` 명령 + webapp 회고 페이지 | end-to-end |

## 검증 방법

| 검증 | 방법 | 통과 기준 |
|------|------|----------|
| 권고 자동 적재 | STRATEGY-TRACK-001 권고 발행 → guidance_records INSERT | 1 권고 = 1 row |
| 가격 추적 cron | 30 일 도달 권고 1 건 → tracker.py 수동 호출 | KIS 일봉 회수 → tracking[day_30] 갱신 |
| 5 KPI 계산 | 가상 28 권고 데이터 → kpi.py 호출 | Track A·B 종합 점수 0~100, 각 KPI 0~100% |
| 회고 보고 | `회고` 단축어 입력 | 위 양식대로 출력 |
| 멱등성 | 같은 권고 ID 2회 INSERT → ON CONFLICT REPLACE | 1 row 유지 |
| 회귀 | `TESTING=1 pytest tests/ -q` | 135 passed 유지 (신규 테스트 추가 시 +N) |

## 의사결정 SLOT

- (S1) 가격 추적 데이터 출처 — KIS 일봉 (무료, 토큰 작동 중) vs pykrx (백업) vs FRED+yfinance (해외 종목). 초안 = KIS 일봉 단독, 부족 시 pykrx fallback
- (S2) 자가 진단 정확도 (KPI #4) 의 "실제 부정확" 판정 방법 — 사용자 manual 평가 vs LLM 자동 평가. 초안 = 사용자 manual + LLM 후보 추출 보조
- (S3) 추적 기간 — default 30·60·90 일. Track A 는 60·90·180 일이 더 적합할 수도. 초안 = 트랙별 차별 (A: 60/90/180 / B: 30/60/90)
- (S4) `회고` 단축어 응답 — 텔레그램 + webapp + REPL 어디서? 초안 = 모두 (UNIFIED API)
- (S5) MDD 추적 — `actual_outcomes.max_drawdown_pct` 계산은 일봉 종가 기준 vs 일중 저점 기준. 초안 = 일중 저점 (보수적)
- (S6) 회고분석가 (Layer 5) 입력 인터페이스 — guidance_records 직접 read vs kpi.py 의 집계 view. 초안 = 집계 view (`get_kpi_summary(track, period_days)`)

## 관련 문서

- [ANALYST-PERSONAS-001](ANALYST-PERSONAS-001-nine-analyst-portable-personas.md) — 점수 인용 양식 (cited_scores 의 출처)
- [STRATEGY-TRACK-001](STRATEGY-TRACK-001-two-track-strategists.md) — depends_on. 권고 객체 (strategist-recommendation-v1)
- [docs/CONTRACTS.md](../CONTRACTS.md) — 계약 버전 관리 원칙
- [idea_memo/prism-insight-비교차용2.md](../../idea_memo/prism-insight-비교차용2.md) — § 6 적중도 측정 프레임워크 (본 SPEC 원천)
- [idea_memo/2026-05-17-wevelstock-rd-meta-design-by-chat-claude-opus.md](../../idea_memo/2026-05-17-wevelstock-rd-meta-design-by-chat-claude-opus.md) — Layer 5 회고분석가 영감
