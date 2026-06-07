---
spec_id: INFRA-US-MACRO-SNAPSHOT-001
title: 미장 매크로 스냅샷 — 미국 야간 지표 일자 영속 + risk-on/off 결정론 분류 → 시장관 흡수
team: shared
type: feature
status: verified
level: implementation
parent: LEFT-BRAIN-COMPLETION-001        # LB roadmap 마지막 자식 (③ MARKET-VIEW 에 흡수)
generates:
  - collectors/us_macro.py
  - config/us_macro.yaml
  - tests/test_us_macro.py
  - scripts/_us_macro_probe.py
modifies:
  - core/db/schema.sql                    # v12: us_macro_snapshot 테이블 (CREATE IF NOT EXISTS)
  - collectors/market_view.py             # us-macro-hook SLOT 충족 (entry_posture 축 + one_liner 토큰 + 흡수)
  - config/market_view.yaml               # us_macro 흡수 토글·임계
  - server/schedulers/jobs/snapshot_macro.py   # 18:05 허브에 us_macro 단계 append
  - pipelines/market_briefing_pre/...     # 아침 장전 persist 트리거 (정확 stage = INTERVIEW-SLOT)
  - agents/analysts/market_state_analyzer/persona.md   # 미장 야간 해석 지침 (cited)
depends_on:
  - LEFT-BRAIN-COMPLETION-001 (roadmap parent — 왼쪽 뇌 마지막 조각)
  - MARKET-VIEW-SYNTHESIS-001 (us-macro-hook SLOT 보유 — entry_posture·one_liner 흡수 지점. 본 SPEC 이 그 SLOT 충족)
  - INFRA-SNAPSHOT-EXTEND-001 (market_macro_snapshot DB-first hybrid 패턴 mirror)
  - INFRA-FUNDAMENTAL-DATA-001 (connectors/yfinance — get_indices 재사용. 신규 어댑터 X)
contracts:
  - name: us-macro-snapshot-v1
    version: "1.0"
    description: "미장 야간 매크로 스냅샷. USMacroSnapshot = {date(KST), nasdaq_change_pct, sp500_change_pct, sox_change_pct, vix, vix_change_pct, dxy, dxy_change_pct, us_10y, us_10y_change_bp, gold_change_pct, risk_signal∈{risk_on,neutral,risk_off}, signal_score, extreme∈{none,vix_panic}, reasons[], source∈{db,computed,stale,unavailable}}. risk_signal=classify_us_risk() 결정론(주식 모멘텀+VIX 레벨/급등+달러·금리 역풍, config 임계). us_macro_snapshot 테이블 DB-first upsert(date PK, 멱등). MarketView 에 흡수: entry_posture 단계 강등 + 극단(vix_panic) 방어 게이트 + one_liner 미장 토큰."
---

# INFRA-US-MACRO-SNAPSHOT-001 — 미장 매크로 스냅샷 (LEFT-BRAIN 마지막 조각)

> roadmap parent: **LEFT-BRAIN-COMPLETION-001** / ③ MARKET-VIEW-SYNTHESIS 의 미장 입력축.
> 이 SPEC 완료 = 왼쪽 뇌 자식 4/4 → **왼쪽 뇌(수집→분석→답변) 완성 선언 가능**.

## 목적

`user_want_spec` Task2(당일 시장 데이터)의 **미장 절반**(달러인덱스·미 10년물·VIX 공포지수·나스닥·필라델피아 반도체·국제 금)을 *일자 스냅샷으로 영속*하고, *risk-on/off 한 신호*로 결정론 분류해, **시장관 종합(MarketView)** 의 진입 자세·상시 1줄에 흡수한다. 국장은 미장 야간에 강하게 연동(특히 반도체)되는데 현재 그 입력이 시장관에 안 떠오른다 — 이 한 겹을 채운다.

## 배경 / 문제 (핵심 — 데이터는 이미 있다)

- **수집은 이미 된다, 영속·해석·흡수가 없다**: `connectors/yfinance/client.py::get_indices()` 와 `collectors/us_markets.py::fetch_overnight()` 가 이미 6 지표 전부(^IXIC·^SOX·^VIX·DX-Y.NYB·^TNX·GC=F + ^GSPC·^DJI·CL=F·KRW=X)를 가져온다. 그러나 **브리핑이 그때그때 호출**할 뿐 (1) 일자 영속 0 → 다일 비교·재현 불가, (2) "오늘 미장이 위험회피였나" 결정론 라벨 0, (3) 시장관/분석가 흡수 0.
- **MARKET-VIEW-SYNTHESIS-001 이 비워둔 SLOT**: 그 SPEC 의 `us-macro-hook` (id=us-macro-hook) INTERVIEW-SLOT 가 "본 SPEC 완료 후 entry_posture 에 미장 축 가산 + one_liner 에 미장 토큰" 으로 명시 — 본 SPEC 이 정확히 그 자리를 채운다.
- **FRED 는 불필요**: DXY(DX-Y.NYB)·US10Y(^TNX) 가 이미 yfinance 에 있어 권위 source 신규 의존은 한계효용. SLOT 으로 강등.

## 핵심 결단 (3 — 면담 확정 2026-06-07)

**U1 — yfinance 재사용, 신규 어댑터·FRED 없음 (FRED = SLOT)**
- 데이터는 기존 `connectors/yfinance/client.get_indices()` 재사용. 신규 코드 = **영속 + 분류 + 흡수**만. DXY·US10Y 도 yfinance 에 있어 FRED 신규 의존 안 넘김 (권위 값은 후속 SLOT).
- capability 인지 폴백([[feedback_silent_env_fallback]]): yfinance 미설치/네트워크 실패 → `source="unavailable"` + None 필드, 답변·시장관 막지 않음(graceful).

**U2 — risk-on/off 가 진입 자세에 "단계 강등 + 극단 게이트" (비대칭, 보수적)**
- 미장 `risk_off` → 기존 KR 결정론 entry_posture 를 **한 단계 강등**(aggressive→neutral→defensive). 극단(`vix_panic`) → **방어 강제 게이트**(기존 DD kill switch 패턴 mirror).
- **비대칭**: `risk_on` 은 자동 상향 안 함(미장 호조가 국장 약세를 덮어 공격으로 끌어올리지 않음 — 투자 7계명 보수성). 상향 허용 여부는 SLOT.
- raw 지표는 그대로 LLM(market_state_analyzer)에 주입 — 결정론은 advisory 강등·게이트만, 해석은 LLM([[feedback_score_collapse_advisory]] 일관: 게이트는 극단에 한정, 나머지는 원시 주입).

**U3 — 영속 트리거 둘 다 (18:05 허브 + 아침 장전)**
- 평일 **18:05 `snapshot_macro` 허브**에 us_macro 단계 append(MARKET-VIEW 가 그 허브에 합류한 방식 그대로) + **아침 장전 `market_briefing_pre`** 에서도 refresh.
- KST date 키 멱등 upsert — 같은 KST 날짜 = 그날 새벽 마감된 동일 미장 세션이라 두 트리거가 같은 값을 쓴다(충돌 X, 아침은 장전 보강·18:05 는 연속성 insurance). 세션 경계 정밀 의미는 SLOT.
- 파이프라인 간 import 금지 원칙 준수: 브리핑 stage 는 **collector(`compute_us_macro`) import**(공용 수집 모듈 — 허용)로 영속, 다른 파이프라인 코드 import 아님.

## 구현 범위

### 하는 것 (MVP)
1. `collectors/us_macro.py`:
   - `USMacroSnapshot` 데이터클래스 (us-macro-snapshot-v1) + `to_dict`.
   - `classify_us_risk(...)` **순수 결정론** (주식 모멘텀 + VIX 레벨/급등 + 달러·금리 역풍 → risk_on/neutral/risk_off + extreme=vix_panic, config 임계). 단위 테스트 대상.
   - `compute_us_macro(*, force_refresh=False)` DB-first hybrid (오늘 row 즉시 / 없으면 `get_indices` fetch → classify → upsert). `market_macro.compute_market_macro` mirror.
   - DB layer: `_get_today_us_macro`, `upsert_us_macro` (`us_macro_snapshot`, ON CONFLICT REPLACE 멱등).
   - `refresh_us_macro()` cron 진입점 + `render_us_macro_md()` (시장관 [7] 하위 "미장 야간" 라인용) + `us_macro_metadata()`.
2. `core/db/schema.sql` v12 — `us_macro_snapshot` 테이블 (`CREATE TABLE IF NOT EXISTS`, date PK). 신규 테이블이라 ALTER 불필요(connection.py `_apply_migrations` 주석 패턴 — v10/v11 과 동일).
3. `config/us_macro.yaml` — fetch 심볼·분류 임계(주식 가중·VIX elevated/panic·DXY/US10Y 역풍·signal 밴드) 외부화.
4. **MarketView 흡수** (us-macro-hook SLOT 충족, `collectors/market_view.py`):
   - `build_market_view` 가 `compute_us_macro()`(DB-first read, graceful) 호출 → `synthesize_market_view(us_macro=...)` 전달.
   - `entry_posture(...)` 에 us_risk 인자 — U2 단계 강등 + vix_panic 방어 게이트(기존 DD kill switch 와 우선순위 정합).
   - `build_one_liner(...)` 에 미장 토큰(예: "· 미장 위험회피") — 빈/중립 생략(ANSWER-FIDELITY F2 정신).
   - `MarketView.reasons` 에 미장 신호 근거 1줄 + `render_market_view_md` [7] 에 "미장 야간" 라인. → market_state_analyzer 가 기존 [7] read 로 해석(신규 분석가 hook 불필요).
5. **영속 배선** (U3): `snapshot_macro.run_snapshot_macro_refresh` 에 us_macro 단계(독립 try/except) + `market_briefing_pre` 에 장전 persist 트리거(정확 stage = SLOT).
6. `agents/analysts/market_state_analyzer/persona.md` — 미장 야간 해석 지침(반도체 연동·위험선호 cited, 미장 raw 직접 수치 인용 OK).
7. `tests/test_us_macro.py` — classify_us_risk 결정론 매트릭스(risk_on/neutral/risk_off + vix_panic) · entry_posture 미장 강등·게이트 매트릭스 · one_liner 미장 토큰·생략 · DB round-trip · graceful(unavailable) · MarketView 흡수. **LLM·외부 API 실호출 금지(TESTING=1, yfinance mock)**.
8. `scripts/_us_macro_probe.py` — 라이브 probe(capability 체크 + 실 yfinance fetch + 분류 + MarketView 흡수 실증, `_market_view_probe` mirror).

### 안 하는 것 (범위 밖 — SLOT 또는 별 SPEC)
- **FRED 권위 값** (DXY/DGS10) — yfinance 로 충분, SLOT.
- **buy_score 흡수** — 미장은 시장 레벨(종목 N축 아님). SLOT.
- **risk_on 자동 상향** — 비대칭 보수(U2). 허용 여부 SLOT.
- **KOSDAQ 별도 처리 / 전략가 team_outputs publish** — MARKET-VIEW 와 동일하게 SLOT.
- **분류 임계 다일 캘리브레이션** (VIX/DXY/signal 밴드) — 스냅샷 누적 후, SLOT([[feedback_backtest_essence]] — 보수적 기본만 커밋).
- **세션 경계 정밀 의미** (장전 vs 18:05 동일 세션 가정의 엣지) — SLOT.
- **브리핑 표시를 compute_us_macro 로 단일화**(double-fetch 제거) — MVP 는 persist 만, dedupe SLOT.

## 설계

### 데이터 흐름
```
[18:05 허브 + 아침 장전] compute_us_macro(force_refresh) ──┐ (us_macro_snapshot 누적, KST date 멱등)
                                                            │
build_market_view(KOSPI):                                   ▼
  ... (기존 regime·sector_rs·rotation) + compute_us_macro()(DB-first read)
        ├─ classify_us_risk → risk_signal / extreme
        ├─ entry_posture(regime, breadth, dd, us_risk) ── U2 단계 강등 + vix_panic 게이트
        ├─ one_liner ── 미장 토큰 추가
        └─ reasons / render [7] "미장 야간" 라인
        ▼ upsert market_view_snapshot (기존)
   ┌────────────────────────────┬───────────────────────┐
   ▼ (해석)                       ▼ (상시 1줄)             ▼
 market_state_analyzer [7] read  formatter prepend       (라이브 probe)
```

### USMacroSnapshot 계약 (us-macro-snapshot-v1)
<!-- SPEC:INTERVIEW-SLOT id=us-macro-dataclass
필드 확정: date(KST), nasdaq_change_pct, sp500_change_pct, sox_change_pct,
vix, vix_change_pct, dxy, dxy_change_pct, us_10y, us_10y_change_bp, gold_change_pct,
risk_signal∈{risk_on,neutral,risk_off}, signal_score(float), extreme∈{none,vix_panic},
reasons[], source∈{db,computed,stale,unavailable}. 구현 시 dataclass + to_dict(JSON round-trip).
get_indices 결과 키(nasdaq/philly_semi/sox/vix/dxy/us_10y/gold/sp500) → 필드 매핑 확정. -->

### classify_us_risk 결정론 (config 외부화)
<!-- SPEC:INTERVIEW-SLOT id=us-risk-rules
초안(보수적 기본, 다일 캘리브레이션은 SLOT):
- 주식 모멘텀 = w_sox·sox_change_pct + w_eq·avg(nasdaq,sp500)  (반도체 가중 — 국장 연동 큼).
- VIX: vix ≥ panic(예 30) → extreme=vix_panic (risk_off 강제). vix ≥ elevated(예 20) → 위험 가산.
- 역풍: dxy_change_pct ≥ dxy_jump(예 +0.5%) 또는 us_10y_change_bp ≥ rate_jump(예 +10bp) → 위험 가산.
- signal_score 합성 → bands: ≥ on_th → risk_on / ≤ off_th → risk_off / else neutral.
- 결측(unavailable/None 다수) → neutral + source 노출(추정 금지).
임계 전부 config/us_macro.yaml. -->

### entry_posture 미장 상호작용 (U2, config 외부화)
<!-- SPEC:INTERVIEW-SLOT id=us-posture-interaction
우선순위(기존 KR 결정론 posture 산출 후 적용):
1. us extreme=vix_panic → defensive 강제 (기존 DD kill switch 와 동급 하드 게이트).
2. us risk_off → 한 단계 강등 (aggressive→neutral, neutral→defensive). defensive 면 유지.
3. us risk_on / neutral / unavailable → 변경 없음 (비대칭 — 상향 SLOT).
기존 entry_posture() 시그니처에 us_risk 인자 추가(기본 None=하위호환). config/market_view.yaml us_macro.enabled 토글. -->

### one_liner 미장 토큰
<!-- SPEC:INTERVIEW-SLOT id=us-one-liner
초안: risk_off/vix_panic → " · 미장 위험회피", risk_on → " · 미장 위험선호".
neutral/unavailable → 생략(ANSWER-FIDELITY F2 빈 축 생략). _NEWS_TONE_KR 흡수(C2) 패턴 mirror. -->

### 영속 트리거 (U3)
<!-- SPEC:INTERVIEW-SLOT id=persist-wiring
1. snapshot_macro.run_snapshot_macro_refresh: 기존 3단계 뒤 4단계 us_macro(독립 try/except,
   compute_us_macro(force_refresh=True)). market_view 단계가 us_macro_snapshot DB-hit 하도록 us_macro 를 market_view 앞에 둘지 순서 확정.
2. market_briefing_pre: 장전 persist 트리거 stage 위치 확정(기존 fetch_overnight stage 재사용 vs 신규 작은 hook). double-fetch dedupe 는 SLOT. -->

## 다른 팀/스키마 영향
- **DB 스키마 추가 1**: `us_macro_snapshot` (신규 테이블, `CREATE TABLE IF NOT EXISTS` — 기존 dev DB 호환, ALTER 불필요).
- **market_view.py 흡수**: `entry_posture`/`build_one_liner`/`synthesize_market_view`/`build_market_view` 에 us_macro 인자 추가(기본값 None=하위호환). 기존 테스트 회귀 0 목표.
- **market_state_analyzer**: 기존 `reads_market_view` [7] 경로 재사용 → 신규 read flag·hook 불필요(persona 해석 지침만 추가).
- **snapshot_macro job / market_briefing_pre**: 단계 append(기존 단계 비파괴).
- 전략가/Track A·B 영향 없음(team_outputs publish SLOT).

## 검증
- 단위: `tests/test_us_macro.py` — classify_us_risk 고정 입력→고정 신호(risk_on/neutral/risk_off/vix_panic 매트릭스) · entry_posture 미장 강등·게이트(기존 6 regime × DD × us_risk) · one_liner 토큰·생략 · DB round-trip · graceful(yfinance mock 실패→unavailable, 시장관 안 막음) · MarketView 흡수 전후. **외부 API·LLM 실호출 금지(TESTING=1, yfinance mock)**.
- 통합(라이브): `_us_macro_probe.py` — 실 yfinance fetch → 분류 → us_macro_snapshot upsert → build_market_view 흡수(one_liner 미장 토큰·entry_posture 반영) 실증. production-chat "지금 미장 어때 / 들어가도 돼?" → market_state_analyzer 가 [7] 미장 야간 라인 인용.
- 회귀: 기존 전체 passed 유지(market_view 인자 추가가 기존 호출 안 깨뜨림) + validate 0 errors.
- 단계 지도: `scripts/project_status.py` → LEFT-BRAIN 트리 INFRA-US-MACRO-SNAPSHOT-001 [미작성]→[draft], 구현 후 implementing/verified → **미작성 0 / 완료 4/4**.

## 완료 정의 (이 SPEC)
미장 야간 6 지표가 일자 스냅샷으로 영속(18:05 + 장전 둘 다) + risk-on/off 결정론 분류 + MarketView entry_posture 단계 강등·vix_panic 게이트·one_liner 미장 토큰 흡수 + market_state_analyzer 가 [7] 미장 야간 라인 인용 해석 + 회귀/validate 통과. 이 시점에 **LEFT-BRAIN-COMPLETION-001 자식 4/4 = 왼쪽 뇌 완성**. (FRED·buy_score·risk_on 상향·KOSDAQ·전략가 publish·임계 캘리브레이션은 후속 SLOT.)

## 구현 기록 (2026-06-07 — MS-1~4, verified)
- **MS-1 코어** (`collectors/us_macro.py`): `USMacroSnapshot` 데이터클래스 + `classify_us_risk`(순수 결정론 — 주식 모멘텀 반도체 가중 + VIX 레벨/패닉 게이트 + 달러·금리 역풍 → risk_on/neutral/risk_off + extreme) + `compute_us_macro` DB-first hybrid(`get_indices` 재사용, U1) + DB layer(`us_macro_snapshot` date PK 멱등) + `refresh_us_macro` cron 진입점 + render/metadata/흡수 helper(`us_one_liner_token`/`us_macro_reason`/`render_us_macro_md`). `config/us_macro.yaml` 임계 외부화. `core/db/schema.sql` v12 테이블(CREATE IF NOT EXISTS, ALTER 불필요).
- **MS-2 흡수** (`collectors/market_view.py`): `apply_us_macro_to_posture`(U2 — risk_off 단계 강등 / vix_panic 방어 게이트 / 비대칭) + `entry_posture(us_macro=)` + `synthesize_market_view(us_macro=)` reason·one_liner 토큰 + `build_market_view` 가 `compute_us_macro` DB-first read(graceful) + `render_market_view_md` 미장 야간 라인(get_today_us_macro 디커플 — 스키마 변경 0). `config/market_view.yaml` us_macro.enabled 토글.
- **MS-3 배선** (U3 둘 다): `snapshot_macro` 18:05 허브 3단계 us_macro append(market_view 앞 — DB-hit) + `market_briefing_pre/collect_overnight_us` 장전 persist(graceful, double-fetch dedupe SLOT) + `market_state_analyzer/persona.md` 미장 야간 해석 지침(반도체 연동·raw 인용 OK).
- **테스트**: `tests/test_us_macro.py`(12 — classify 매트릭스·DB-first·graceful·vix_panic·흡수 helper) + `tests/test_market_view_us_macro.py`(10 — 강등·게이트·비대칭·synthesize 흡수·하위호환) + snapshot_macro job·briefing smoke 갱신. **전체 966 passed** / validate 0 errors.
- **MS-4 라이브** (`scripts/_us_macro_probe.py`): 실 yfinance 7/7 fetch → **risk_off**(필반 -10.26%·VIX 21.5·signal_score -8.335, 실제 risk-off 장 포착) → build_market_view 흡수(entry_posture neutral→**defensive** 강등, one_liner "· 미장 위험회피", reasons 미장 줄) → [7] 미장 야간 라인 실증. us_macro_snapshot·market_view_snapshot 오늘 행 적재(일일 refresh 보존).
- **잔여(SLOT)**: FRED 권위 값 / buy_score 흡수 / risk_on 자동 상향 / KOSDAQ / 전략가 publish / 임계 다일 캘리브레이션 / 세션 경계 정밀 의미 / 브리핑 double-fetch dedupe. + **dev cron 미작동 근본 해소**(18:05·장전 둘 다 서버 상주 전제 — Top 3 #2, 라이브 누적의 실 전제).
