---
spec_id: MARKET-VIEW-SYNTHESIS-001
title: 시장관 종합 — 섹터 RS·regime·매크로 결정론 종합 → 순환매 방향 + 진입 자세 상시 1줄
team: shared
type: feature
status: verified
level: implementation
parent: LEFT-BRAIN-COMPLETION-001        # LB-MS2
generates:
  - collectors/market_view.py
  - config/market_view.yaml
  - tests/test_market_view.py
  - scripts/_market_view_probe.py
modifies:
  - collectors/sector_rs.py
  - core/db/connection.py
  - core/inference/run_analyst.py
  - core/knowledge/compose.py
  - core/intent/formatter.py
  - agents/analysts/market_state_analyzer/persona.md
  - agents/analysts/market_state_analyzer/manifest.yaml
depends_on:
  - LEFT-BRAIN-COMPLETION-001 (roadmap parent — LB-MS2)
  - INFRA-SNAPSHOT-EXTEND-001 (섹터 RS compute_sector_rs · 매크로 compute_market_macro · classify_market_regime — 종합 입력 재료)
  - INFRA-SCORE-INPUTS-001 (분석가 hook _maybe_build_*_md · compose 주입 패턴 mirror)
  - WAVE-ALPHA-001 (anchors.py 2-Stage 하이브리드 + llm_call_cache 캐싱 패턴 — rotation 크로스체크 mirror)
  - PRODUCTION-UX-001 v1 (formatter format_answer — 1줄 prepend hook 대상)
contracts:
  - name: market-view-v1
    version: "1.0"
    description: "시장관 종합 산출물. MarketView = {date, market, regime, leading_sectors[], fading_sectors[], rotation{direction, from_sectors[], to_sectors[], strength, method, agreement}, entry_posture, one_liner, confidence, reasons[], source}. regime=classify_market_regime 재사용(결정론), leading/fading=sector_rs 다일 변화(결정론), rotation=결정론 다일 후보 + LLM 크로스체크(2-Stage 하이브리드, llm_call_cache type='market_rotation' 일 1회 캐싱, agreement 표기), entry_posture∈{aggressive,neutral,defensive}=regime+breadth+distribution 결정론. one_liner=formatter prepend용 한 줄. market_view_snapshot 테이블 DB-first upsert(멱등)."
---

# MARKET-VIEW-SYNTHESIS-001 — 시장관 종합 (LB-MS2)

> roadmap parent: **LEFT-BRAIN-COMPLETION-001** / 마일스톤 **LB-MS2** (중요⊗비시급, Q2).
> 완료 신호(roadmap): *"묻기 전에도 '현재 regime + 주도 섹터 + 순환 방향 + 진입 자세' 1줄 상존."*

## 목적

왼쪽 뇌 채점표상 **순환매(~40%)·시장 타이밍(~50%)** 이 *종합 판단*으로 안 올라온다. 재료(섹터 RS·regime·매크로)는 라이브인데 "돈이 A→B 섹터로 돈다 / 지금 들어갈 때냐"를 **하나로 종합하는 층이 비어 있다**. 본 SPEC = 그 한 겹을 **결정론 종합자**로 채우고, 기존 market_state_analyzer가 해석하고, formatter가 모든 답변 앞에 1줄로 상존시킨다.

## 배경 / 문제

- **부품은 있으나 종합이 없다**: `compute_sector_rs()`(14섹터 RS) · `classify_market_regime()`(6단계) · `compute_market_macro()`(4축)이 *따로* 산출될 뿐, "현재 시장을 한 문장으로" 묶는 산출물이 없다. 사용자 북극성 ②순환매·③타이밍이 답변에 안 떠오르는 근본 원인.
- **섹터 RS가 일자별로 안 남는다**: `compute_sector_rs()`는 lazy compute(DB 저장 X). "어제 대비 어느 섹터로 돈이 도는가"(순환매의 본질=*이동*)를 보려면 **일자 스냅샷 누적**이 선행이어야 한다.
- **regime 라벨만으론 진입 자세가 안 나온다**: market_state_analyzer가 `parabolic`/`moderate_bull` 라벨은 내지만, "그래서 공격이냐 방어냐"를 결정론으로 못박은 곳이 없다.

## 핵심 결단 (4 — 면담 확정)

**M1 — 결정론 종합 함수 + 기존 분석가 해석 (신규 분석가 X)**
- `collectors/market_view.py::synthesize_market_view()` 가 sector_rs(오늘/어제) + regime + macro 를 받아 구조화된 `MarketView` 산출. **LLM 없음** = 5점수(결정론 수치→LLM 해석) 패턴과 동일.
- 해석·내러티브는 기존 **market_state_analyzer** 가 `MarketView` 를 read 해서 수행(`reads_market_view`). 신규 분석가 폴더 안 만듦 → 역할 중복(regime vs 순환매 frame) 회피.

**M2 — formatter 가 모든 production-chat 답변 앞 시장관 1줄 prepend (답변 시점 비용 0)**
- `format_answer` 가 `build_market_view()` 의 `one_liner` 를 답변 머리에 항상 붙임. regime·entry_posture 는 결정론, 순환매는 **일 1회 캐싱된**(M4 Stage 2) 결과 read → 답변 시점 LLM 호출 0, 묻지 않아도 상존.
- `config/market_view.yaml::prepend.enabled` 토글로 끌 수 있음(하드코딩 금지).

**M3 — 미장 매크로는 depends_on 선행 X, MVP 한국 재료만 (SLOT 마커)**
- roadmap 지침("지금 있는 재료로 먼저 골격")대로 MVP = 국장(KOSPI) sector_rs + 한국 regime/macro. 미장 야간(SPX·NDX·VIX·DXY·US10Y) 진입축은 `INFRA-US-MACRO-SNAPSHOT-001`(별 자식 SPEC) 후 흡수 — 본 SPEC 안에 `INTERVIEW-SLOT` 위치만.

**M4 — 순환매 = 결정론 다일 후보 + LLM 크로스체크 (2-Stage 하이브리드, 캐싱)**
- *결정론 단독 = 하루치 오해* / *LLM 단독 = 환각* — 둘 다 피하려 교차 검증한다([[feedback_llm_intuition_distribution]] + [[feedback_backtest_essence]], WAVE-ALPHA anchor 패턴 mirror).
- **Stage 1 결정론 후보**: `rs_change_Nd`(오늘 rs_score − N일 전 rs_score, **다일 윈도우** — 1일 아님)로 `to_sectors`(상승 상위=돈 유입) / `from_sectors`(하락 상위=유출) / `direction="{from}→{to}"` 후보 산출. 다일이라 single-day overfitting 회피.
- **Stage 2 LLM 크로스체크**: Stage 1 후보를 LLM(FAST tier = **Gemini flash-lite**, provider 고정 — Anthropic 미결제)에 제시 → 다일 RS 추세·맥락으로 검증·보정. **결정론 후보가 앵커**라 LLM 환각 차단(후보 밖 섹터 날조 금지).
- **agreement 표기**: 두 결과 일치 → `confidence` 상향. 불일치 → `confidence` 하향 + `rotation.method` 에 양쪽 병기(결정론·LLM 다름 노출, 은폐 X).
- **일 1회 캐싱**: Stage 2 는 `llm_call_cache`(type='market_rotation', cache_key "market|date", TTL 1일)로 캐싱 → `build_market_view` 가 read. **답변 시점(prepend) 비용 0** 유지(M2).
- **첫날/이력 부족 graceful**: N일 스냅샷 누적 전이면 `rotation.strength="none"`, `leading_sectors` 만 발행(추정·LLM 호출 모두 skip).

## 구현 범위

### 하는 것 (MVP)
1. `MarketView` 데이터클래스 + `synthesize_market_view()`(결정론: leading/fading/entry_posture/rotation Stage1 후보) + `cross_check_rotation_via_llm()`(Stage2, collectors/anchors.py `select_anchors_via_llm` mirror — TESTING mock).
2. `sector_rs_snapshot` 테이블 + `sector_rs.py` 에 일자 persist (`persist_sector_rs(date, market, rows)`). market_macro_snapshot DB-first 패턴 mirror. (rotation 다일 윈도우의 누적 토대)
3. `market_view_snapshot` 테이블 + `build_market_view(market)` DB-first 하이브리드(오늘 row 있으면 즉시, 없으면 compute → Stage2 크로스체크(llm_call_cache) → upsert).
4. `entry_posture` 결정론 (regime + breadth_ratio + distribution_count_25d → aggressive/neutral/defensive, DD kill switch ≥ 4 → defensive 강제, market_state_analyzer 정합).
5. `one_liner` 결정론 포맷 + `render_market_view_md()` (분석가 주입용 [7] 블록).
6. formatter `format_answer` prepend hook (M2) + `config/market_view.yaml`.
7. market_state_analyzer read hook: `run_analyst._maybe_build_market_view_md` + `compose.build_pipeline_prompt(market_view_md=...)` + manifest `reads_market_view` + persona 순환매·진입 해석 지침(cited).
8. `tests/test_market_view.py` — synthesize 결정론 시나리오 + 첫날 graceful + entry_posture 매트릭스 + one_liner 포맷 + DB round-trip + prepend.

### 안 하는 것 (범위 밖 — SLOT 또는 별 SPEC)
- 미장 매크로 축 (`INFRA-US-MACRO-SNAPSHOT-001` 별 자식 SPEC).
- 뉴스부 내러티브 인용 (`NEWS-SOURCE-001` / LB-MS3 후 이 종합자에 먹임).
- KOSDAQ 시장관 (MVP=KOSPI, 확장 SLOT).
- team_outputs cross-team publish (전략가 read) — SLOT.
- sector_rs_snapshot 자동 cron 배선 (MVP=수동 `just` 명령 + 장후 적재; dev cron 미작동 이슈 연결, SLOT).
- entry_posture / rotation strength 임계 다일 캘리브레이션 (universe 누적 후, SLOT).

## 설계

### 데이터 흐름
```
[장후 1회] persist_sector_rs(today) ──┐  (sector_rs_snapshot 누적)
                                       │
build_market_view(KOSPI):             ▼
  sector_rs_snapshot(today … N일전) + classify_market_regime(macro) + compute_market_macro
        │
        ├─ leading/fading (rs_score 상위/하위, 결정론)
        ├─ rotation = Stage1 결정론 다일 후보(rs_change_Nd) ⨯ Stage2 LLM 크로스체크
        │             (llm_call_cache 일 1회) → to/from/direction/strength/method/agreement
        ├─ entry_posture (regime + breadth + distribution, 결정론)
        └─ one_liner ─────────────────────────────────┐
        ▼ upsert market_view_snapshot (DB-first 멱등)   │
                                                        │
   ┌────────────────────────────────────────┬──────────┘
   ▼ (M1 해석)                                ▼ (M2 상시 1줄)
 run_analyst._maybe_build_market_view_md   formatter.format_answer
 → market_state_analyzer 가 read·해석        → 모든 답변 머리에 prepend
```

### MarketView 계약 (market-view-v1)
<!-- SPEC:INTERVIEW-SLOT id=market-view-dataclass
필드 확정: date, market, regime, leading_sectors[{sector, rs_score, rs_change_Nd}],
fading_sectors[...], rotation{direction, from_sectors[], to_sectors[], strength∈{strong,mild,none},
method∈{deterministic, llm, hybrid}, agreement∈{agree, disagree, n/a}},
entry_posture∈{aggressive,neutral,defensive}, one_liner, confidence, reasons[], source∈{db,computed,stale}.
구현 시 dataclass + to_dict(JSON round-trip) 확정. rotation 윈도우 N(일) = config. -->

### entry_posture 결정론 매트릭스 (config 외부화)
<!-- SPEC:INTERVIEW-SLOT id=entry-posture-rules
초안: distribution_count_25d ≥ kill_switch(4) → defensive 강제.
regime∈{parabolic, strong_bear} → defensive.
regime∈{strong_bull, moderate_bull} AND breadth_ratio ≥ breadth_strong AND distribution < ceiling → aggressive.
그 외 → neutral. 임계는 config/market_view.yaml. 다일 캘리브레이션은 SLOT. -->

### one_liner 포맷
<!-- SPEC:INTERVIEW-SLOT id=one-liner-format
초안: "오늘 시장: {regime_kr} · 주도 {top_sector} · 순환 {from}→{to} · 진입 {posture_kr}"
빈 축(첫날 rotation=none) 생략 규칙 = ANSWER-FIDELITY F2 빈 축 생략 정신 계승. -->

### 미장 매크로 흡수 지점 (M3)
<!-- SPEC:INTERVIEW-SLOT id=us-macro-hook
INFRA-US-MACRO-SNAPSHOT-001 완료 후: entry_posture 에 '미장 야간(SPX/NDX 방향·VIX·DXY·US10Y)' 축 가산.
one_liner 에 '미장 <risk_on/off>' 토큰 추가. 본 SPEC 은 위치만 확보, 로직 미구현. -->

## 다른 팀/스키마 영향
- **DB 스키마 추가** 2: `sector_rs_snapshot`, `market_view_snapshot` (멱등 ALTER 마이그레이션, 기존 dev DB 호환 — connection.py `_apply_migrations` 패턴).
- **market_state_analyzer manifest** `status` 및 `reads_market_view` 추가 — 기존 reads=[market_macro] 유지, 추가 주입만.
- **formatter** 전 경로 prepend → ANSWER-FIDELITY-001 의 축 가변 로직과 공존(1줄은 머리, 근거축은 본문).
- 전략가/Track A·B 영향 없음(team_outputs publish 는 SLOT).

## 검증
- 단위: `tests/test_market_view.py` — synthesize 결정론(고정 입력→고정 leading/fading/entry_posture) · rotation Stage1 다일 후보 + Stage2 크로스체크 **mock**(agree/disagree → confidence·method·agreement 반영) · 캐싱 멱등(같은 market|date 재호출=캐시 hit, LLM 0) · 첫날 graceful(rotation none, LLM skip) · entry_posture 매트릭스(6 regime × DD kill switch) · one_liner 포맷·빈축 생략 · DB round-trip(snapshot 2 테이블) · formatter prepend on/off. **LLM 실호출 금지(TESTING=1 mock)**.
- 통합(라이브): production-chat 임의 질의 → 답변 머리에 시장관 1줄 상존 확인. "순환매 어때?"·"지금 들어가도 돼?" → market_state_analyzer 가 MarketView(결정론·LLM 크로스체크 결과) 인용 해석. 결정론·LLM 불일치 케이스 노출 확인.
- 회귀: 기존 전체 passed 유지 + validate 0 errors.
- 단계 지도: `scripts/project_status.py` → LEFT-BRAIN 트리에 MARKET-VIEW-SYNTHESIS draft 등재, 구현 후 implementing/verified 전이.

## 완료 정의 (이 SPEC)
production-chat 모든 답변 머리에 "오늘 시장: regime·주도섹터·순환방향·진입자세" 1줄 상존(국장, 한국 재료) + market_state_analyzer 가 MarketView 를 인용해 순환매·진입 해석 + 회귀/ validate 통과. (미장 매크로·뉴스 내러티브·전략가 publish 는 후속.)

## 구현 기록 (2026-06-06)
- **M1 결정론 코어**: `collectors/market_view.py`(MarketView/Rotation dataclass, synthesize_market_view, entry_posture, build_rotation_stage1, one_liner, build_market_view DB-first, render/metadata) + `collectors/sector_rs.py`(persist/load/load_prev 스냅샷) + `core/db/schema.sql` v10(sector_rs_snapshot, market_view_snapshot) + `config/market_view.yaml`.
- **M2 LLM 크로스체크**: `cross_check_rotation_via_llm`(검증 전용 — agree/disagree, 후보 생성 X) + `llm_call_cache` type='market_rotation' 일1회 캐싱 + `_apply_rotation_cross_check`(agree +10 / disagree −15, method=hybrid, agreement 노출).
- **M3 배선**: formatter `_market_view_prefix`(모든 답변 머리 1줄, DB 캐시 read only) + run_analyst `_maybe_build_market_view_md`(sync+stream) + compose `market_view_md` [3b] 블록 + market_state_analyzer manifest `reads_market_view: true` + persona/response_rules 해석 지침.
- **테스트**: `tests/test_market_view.py` 32 (결정론 매트릭스·rotation·DB round-trip·크로스체크 mock·캐싱 멱등·formatter prepend·analyst hook). `tests/test_project_status.py` stale 테스트 구조화 정정.
- **잔여(SLOT)**: 라이브 production-chat 검증 / sector_rs_snapshot 일1회 cron 배선(현 수동) / 미장 매크로(INFRA-US-MACRO-SNAPSHOT-001) / 전략가 publish / 임계 다일 캘리브레이션 / KOSDAQ.
