---
spec_id: BRAIN-ALPHA-FLEXIBILITY-001
title: 두뇌 알파 유연성 — regime blanket 억압 탈피·섹터/종목 차등 변조 + 조건부 진입 + 설명가능성
team: shared
type: feature
level: implementation
status: implementing
parent: BRAIN-QUALITY-001
generates:
  - core/signal/alpha_posture.py        # M1: 결정론 차등 변조 — (scorecard·regime·섹터RS·주도주·파동) → verdict 후보 + 조건부 진입가 + 선정 사유
  - tests/test_alpha_posture.py
modifies:
  - agents/strategists/track_a/persona.md   # M2: doctrine = blanket gate → 후보 소비자 + 사실근거 deviation 로그 + 차등
  - agents/strategists/track_b/persona.md   # M2: 동 (Track B kill-switch 는 유지, 단 차등 변조 적용)
  - core/signal/auto_signal.py              # M3: 후보·섹터/주도주/파동을 prefetched entries·directive 에 주입
  - core/signal/watchlist.py                # M4: 선정 기준에 파동·주도주·섹터RS 편입
  - collectors/screening.py                 # M4: rank_candidates 차등 가중(현 RS만 → +wave/sector/leader)
  - config/screening.yaml                   # M4: 선정 가중 + 차등 변조 임계 config
  - core/strategist/recommendation.py       # M5: data_json 확장(verdict_candidate·conditional_entry·selection_reason·llm_deviation_reason·web_check) — 가산 필드
contracts:
  - name: strategist-recommendation-v1   # team_outputs, 기존 — data_json 가산 확장(스키마 호환 유지)
    version: "1.0"
depends_on:
  - BRAIN-QUALITY-001 (parent roadmap — 두뇌 퀄리티의 첫 자식)
  - AUTO-SIGNAL-GENERATION-001 (본 SPEC 이 강화하는 funnel — Stage 1 전략가 호출에 차등 후보 주입)
  - WAVE-ALPHA-001 (파동 생존 판정 입력 — collectors/anchors.py α·verdict 매트릭스)
  - MARKET-VIEW-SYNTHESIS-001 (regime·섹터 RS·순환매 source — market_view/sector_rs/us_macro 스냅샷)
---

# BRAIN-ALPHA-FLEXIBILITY-001 — 두뇌 알파 유연성

> **BRAIN-QUALITY-001 roadmap 의 첫 자식.** 골격(왼쪽 뇌)은 섰고 자동 권고(몸통)도 돈다 — 그러나 **두뇌가 시장국면(regime)에 통째로 눌려 알파를 못 낸다.** 이 SPEC 이 그 억압을 푼다.

## 현상 (라이브로 증명, 2026-06-15)
- auto-signal `intraday1` 라이브: **regime=strong_bull 인데도 권고 32건 전부 `verdict=wait`.**
- 이전 회차도 동일 — `team_outputs` 권고 누적이 사실상 전부 wait. 매수 후보 0 → 체결 0 → 알파 검증 불가.

## 진단 — regime 3단 억압 (코드 실측)
| 단계 | 메커니즘 | 위치 |
|---|---|---|
| 1단 **범주 게이트** | `verdict=buy` 조건에 `regime ∈ {strong_bull, moderate_bull, parabolic}` 포함 → 다른 조건 미달 시 1개만 충족 → wait | `agents/strategists/track_a/persona.md:187-200` |
| 2단 **kill-switch** | `regime ∈ {moderate_bear, strong_bear}` 또는 DD≥4 → wait/sell 강제 | `agents/strategists/track_b/persona.md:184-208` |
| 3단 **confidence 가중** | `market_state_analyzer` bull=10/bear=0 → bear 시 confidence 강등 → verdict 강등 | `track_a/b persona.md` ~254-265 |

**근본**: regime 이 **binary blanket 필터**다. "약세장이면 다 막고, 강세장이면 다 연다"는 식이라 *섹터·종목 차이를 못 본다*. 실제 알파는 그 차이에 있다 — 약세장에도 강세섹터·주도주·파동 살아있는 종목의 눌림목은 타점이고, 강세장이라도 이미 급등한 추격은 손실이다.

## 본질 (사용자 의도)
regime 을 "전부 막기/열기"가 아니라 **섹터·종목 차등 변조(modulation)** 로 바꾼다:
- 약세장이어도 **강세섹터 + 주도주 + 파동 생존** 이면 단기 눌림 = 진입 허용.
- 강세장이라도 **추격 구간(과열·확장)** 이면 진입 회피.
- 섹터별 차등(섹터 RS 로 차등).
- 관망(wait)에도 **우선순위 + 조건부 진입가**(트리거 도달 시 buy 승격).
- watchlist **선정 자체**에 파동·주도주·섹터 RS 편입.
- **"왜 선정/관망/매수했는가" 설명가능성** 구조화.

## 확정 설계 결단 (면담 2026-06-15)

### 결단 1 — regime 작용 = 섹터·종목 차등 변조 (blanket gate 폐기)
regime 은 더 이상 verdict 의 hard 게이트가 아니다. **기본값(baseline posture)** 일 뿐이고, **섹터 RS·주도주 지위·파동 생존이 그 위에서 종목별로 override** 한다.

### 결단 2 — 가드레일 있는 C (결정론 후보 → LLM 검증자 → 사실근거 deviation)
> 사용자 논거: 결정론 로직은 완벽 보장 불가·개발 후 블랙박스 → LLM 이 최신 사실(웹)로 더블체크해야. 단 순수 C 는 **오늘 버그의 실패 모드**(LLM 이 모든 재료 받고도 보수적으로 전부 wait). 그래서 가드레일을 건다.

- **결정론(`alpha_posture.py`)이 raw 점수가 아니라 *verdict 후보 + 조건부 진입가 + 선정 사유*를 발행.** LLM 의 시작점이 "5개 조건 네가 평가해" → "이 후보를 반박할 사실 있나?"로 바뀐다.
- **LLM 은 후보를 뒤집을 때 *반드시 사실 근거를 `llm_deviation_reason` 으로* 남긴다.** buy 후보를 wait 로 강등하려면 명시 사유(악재 발견 등) 필수 — **blanket 보수 강등 금지.**
- **웹 더블체크는 verdict 결정자가 아니라 *입력 검증자*, buy 후보에만** (비용 통제). LLM 이 catalyst 진위·악재를 최신 검색으로 확인해 후보를 확정/반박.
- 점수 collapse 금지 원칙([[feedback_score_collapse_advisory]]) 유지 — 이건 점수 합산 게이트키핑이 아니라 *여러 결정론 지표의 차등 게이트 + advisory override 여지*다.

### 결단 3 — MVP = 4 스레드 전부
① regime 차등 변조(핵심) ② 관망 조건부 진입가 ③ watchlist 선정 강화 ④ 설명가능성. (사용자 전부 선택.)

### 결단 4 — 시장 = 국장 + 미장 동시
차등 변조 로직을 양 시장에 적용. ⚠️ **미장 watchlist/universe 데이터 경로 성숙도 확인 필요**(국장은 KIS 거래대금 상위 자동 적재, 미장은 universe API 불확실) → 구현 M4 에서 미장 선정 source 결정(보유+관심 우선, 미장 섹터 ETF RS).

## 흐름 (목표)
```
watchlist(국장+미장) → 결정론 컷(rank_candidates: +파동/주도주/섹터RS) ──┐
                                                                      ▼
  alpha_posture.derive(): regime baseline × 섹터RS × 주도주 × 파동  →  verdict 후보 + 조건부 진입가 + 선정 사유
                                                                      ▼
  전략가 LLM (후보 소비자): buy 후보면 웹 더블체크(catalyst/악재) → 후보 확정 or 사실근거 deviation 로그
                                                                      ▼
  persist(team_outputs data_json: 후보·진입가·사유·deviation·web_check 가산) → 알림 → [데스크 체결]
```

## 입력 / 출력 (I/O)
**입력 (전부 기존 자산 read — 신규 수집 0)**
- regime: `market_view_snapshot`·`market_macro_snapshot`(국장) / `us_macro_snapshot`(미장)
- 섹터 RS: `sector_rs_snapshot` (date, market, sector)
- 주도주 지위: S-Score·RS 랭킹 (`collectors/screening.py` rank_candidates, `compute_scorecard`)
- 파동 생존: `collectors/anchors.py` (WAVE-ALPHA α·verdict 매트릭스)
- 5점수·scorecard: `core/signal/auto_signal.py compute_scorecard`

**출력 (team_outputs data_json 가산 확장 — 신규 테이블 0)**
- `verdict_candidate`: 결정론 후보 (buy / wait / sell)
- `conditional_entry`: 관망 시 조건부 진입가 + 승격 트리거
- `selection_reason`: 선정/관망/매수 구조화 사유 (설명가능성)
- `llm_deviation_reason`: LLM 이 후보를 뒤집은 사실 근거 (없으면 null = 후보 추종)
- `web_check`: buy 후보 웹 더블체크 결과 (catalyst 확인/악재)

## 판단 로직 (구현 SLOT)
<!-- SPEC:INTERVIEW-SLOT name="differentiation-formula"
  결정론 차등 변조 식: regime baseline posture(시장별) × 섹터RS 차등 × 주도주 가산 × 파동 생존 게이트.
  - 약세장 + 강세섹터(RS≥?) + 주도주(S≥?) + 파동 생존(α≥? or 눌림목) → buy 후보 허용 임계
  - 강세장 + 과열/확장(extension_score≥?) → 추격 회피(buy→wait 강등)
  - 섹터 RS 구간별 차등 표
  임계는 config/screening.yaml. magic number 는 다일 누적 후 캘리브레이션(BRAIN-QUALITY 회고 루프).
-->
<!-- SPEC:INTERVIEW-SLOT name="conditional-entry-formula"
  관망 종목의 조건부 진입가 + 승격 트리거 산출식. entry→stop 보간(물타기 차단, RB-MS2 패턴 재사용)·
  트리거 도달 판정(지정가/돌파). wait 우선순위 랭킹(후보 근접도).
-->
<!-- SPEC:INTERVIEW-SLOT name="deviation-guardrail"
  LLM 이 verdict 후보를 deviation 할 수 있는 경계: buy→wait 강등은 사실근거 필수,
  wait→buy 승격 허용 조건, blanket 보수 강등 차단 규칙. floor/ceiling.
-->
<!-- SPEC:INTERVIEW-SLOT name="web-doublecheck"
  buy 후보 웹 더블체크 = Gemini search grounding 활성(또는 웹검색 connector). 트리거 종목 수 상한(비용),
  catalyst 진위/악재 프롬프트, 결과를 web_check 에 구조화. ⚠️ 현 판단 경로엔 라이브 웹검색 없음(뉴스=RSS) — 신규 capability.
-->
<!-- SPEC:INTERVIEW-SLOT name="watchlist-enrichment"
  rank_candidates 선정 가중에 파동·주도주·섹터RS 편입(현 RS 60일+ADR만). 미장 watchlist source 결정.
-->
<!-- SPEC:INTERVIEW-SLOT name="explainability-surface"
  selection_reason 구조(수급·차트·실적 3요소 자연어, 코드 라벨 금지 [[feedback_production_answer_brevity]]).
  감사 뷰(전략가 추론 펼침 — RESUME Top 3 와 연계 여지).
-->

## 재사용 영향도 (가드 #11, DATA-MAP 확인 완료)
- **신규 테이블 0.** 모든 출력은 `team_outputs.data_json` **가산 확장**(기존 권고 정본, DATA-MAP §6). 기존 권고 read 경로(데스크·KPI·브리핑) 호환 — 새 필드 무시 가능.
- **신규 collector/connector 0.** 입력은 `sector_rs_snapshot`·`market_view_snapshot`·`us_macro_snapshot`·`anchors`·`chart_ohlcv` 전부 기존 read.
- **신규 모듈 1개** `core/signal/alpha_posture.py` = 데이터 home 아닌 *로직 모듈*(funnel 의 차등 변조 단계). collector/테이블 중복 아님 — auto_signal funnel 확장.
- **유일한 신규 외부 의존** = buy 후보 웹 더블체크용 라이브 웹검색(Gemini grounding). 현 판단 경로에 없음 → M5 에서 capability 배선(비용·실패 폴백 가드 필수, [[feedback_silent_env_fallback]]).
- **3층 파급**: DB(가산 컬럼 없음, data_json 내부) → backend(auto_signal·recommendation·persona) → frontend(설명가능성 필드는 추후 감사 뷰가 read, 본 SPEC 은 데이터 발행까지).

## 마일스톤
- **M1 ✅ (2026-06-15) — 결정론 차등 변조**: `core/signal/alpha_posture.py` + 임계 config + 17 테스트. (regime baseline × 섹터RS × 주도주 × 파동 × 과열도 → 후보·조건부 진입 의도·사유)
- **M2 ✅ (2026-06-15) — persona doctrine 전환**: track_a/b = 범주 게이트 폐기 → AlphaPosture 후보 소비자 + `data: llm_deviation_reason:` 사실근거 로그 + blanket 강등 금지 anti-pattern. Track B kill-switch(DD≥4) 보존(deviation 불가).
- **M3a ✅ (2026-06-15) — funnel 결정론 배선**: `auto_signal.py` Scorecard(rs/ext 주입·screen 행에서, LLM 0) → `posture_inputs_from_scorecard` → `derive_alpha_posture` → `render_alpha_posture_md` 를 `run_strategist(alpha_posture_md=)` 로 주입 + `rec.data["alpha_posture"]` 영속(설명가능성). 92 테스트 GREEN.
- **M3b ⏳ — sector_rs·wave 입력**: `compute_scorecard` 에 종목 섹터 RS(theme classify) + 파동 생존(anchors α→bool) 추가(LLM Haiku·30일 캐시·graceful). bear_override·횡보 선별 활성화. (현재 None → bullish/neutral 만 차등)
- **M3 라이브 검증 ⏳**: 실 Gemini 1회 — strong_bull 종목 buy 후보 ≥1 (오늘 "전부 wait" 탈피) + data_json alpha_posture 확인.
- **M4 — watchlist 선정 강화**: rank_candidates 가중 + 미장 source. (별 마일스톤 가능 — 변조와 독립)
- **M5 — 웹 더블체크 + persist 확장**: buy 후보 Gemini grounding + data_json 가산 + 알림.
- **M6 — 라이브 검증**: 실 Gemini 1회 — 차등 변조로 buy 후보 ≥1 발생(오늘 "전부 wait" 탈피) 확인.

## 완료 정의
라이브 auto-signal 에서 **시장국면이 약세여도 강세섹터·주도주·파동 생존 종목은 buy 후보/조건부 진입**으로, 강세여도 **추격 구간은 회피**로 차등 산출되고, 모든 verdict 에 구조화 사유가 붙으며, LLM 의 후보 deviation 은 사실 근거로 로그된다. "regime 때문에 전부 wait" 가 재발하지 않는다. (임계 캘리브레이션은 BRAIN-QUALITY 회고 루프에 위임.)

## 비고 — 기존 백로그 흡수
본 SPEC 은 `BRAIN-QUALITY-001` roadmap 후보 중 **regime 히스테리시스**(경계 요동 sticky)·**WAVE-ALPHA watchlist 편입**과 일부 겹친다. 차등 변조가 섹터/종목 단위라 regime 경계 요동의 blanket 충격도 완화 — 히스테리시스는 보완 백로그로 잔존.
