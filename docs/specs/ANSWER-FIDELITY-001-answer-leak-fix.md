---
spec_id: ANSWER-FIDELITY-001
title: 답변 누수 봉합 — analyst-only 경로 raw/코드라벨/잘림 차단 + 근거축 가변 + 비교 양종목
team: shared
type: feature
status: verified
level: implementation
parent: LEFT-BRAIN-COMPLETION-001       # LB-MS1
generates:
  - config/evidence_axes.yaml
  - tests/intent/test_answer_fidelity.py
modifies:
  - core/intent/formatter.py
  - core/intent/router.py
  - server/api/production_chat.py
depends_on:
  - PRODUCTION-UX-001 v1 (intent 라우팅 + format_answer + scrub_code_labels 스크러버 베이스라인)
  - LEFT-BRAIN-COMPLETION-001 (roadmap parent — LB-MS1)
contracts:
  - name: evidence-axes-v1
    version: "1.0"
    description: "질의 유형(route/scenario)별 근거축 사전. config/evidence_axes.yaml = {key: [axis_label, ...]}. formatter 가 고정 3요소(수급/차트/실적) 대신 이 사전으로 근거 축을 동적 선택. 종목=수급/차트/실적, 시장=국면/시장폭/매크로, 거시=환율·금리·지수, 온보딩=원칙·시대흐름. 미매칭 시 default(수급/차트/실적)."
---

# ANSWER-FIDELITY-001 — 답변 누수 봉합 (LB-MS1)

> roadmap parent: **LEFT-BRAIN-COMPLETION-001** / 마일스톤 **LB-MS1** (중요⊗시급, Q1).
> 왼쪽 뇌가 아무리 잘 판단해도 *입에서 새면 0점*. 본 SPEC = 답변층 누수 3종 봉합.

## 목적

production-chat 가이드 품질 검증(`docs/guide_quality_review_2026-06-04.md`, 8질의)에서 **본질 기능은 합격**(경로·정직성 8/8 실호출, 변별력: 삼성 6.5 vs NAVER 4.5 vs 하이닉스 7.5, 이번 배선 반영)인데 **답변 전달층에서 3종 누수**가 확인됨. 이미 고친 #1 발굴 제외, 본 SPEC = #2·#3 봉합.

## 배경 / 문제 (실 검증 근거)

**누수 ① analyst-only 경로 raw/코드라벨/잘림 노출** (검증 #4 "삼성전자랑 SK하이닉스 중 뭐가 나아?")
- `format_answer` 는 모든 route 에 호출됨(`production_chat.py` POST 162 / stream 298). 그러나 **전략가가 없는 analyst-only 경로(`analyst_direct`·비교)** 에서 압축 결과 대신 분석가 raw 가 그대로 사용자에 노출:
  - `## 사용자 발화 / ## 분석가 raw 응답 (prefetch 동시 호출)` 내부 헤더 노출
  - **코드라벨 누출**: `주도주 점수=7.33`, `'리더(leader)'`, `'매수 후보(buy_candidate)'`, `Supply Chain Alignment` 등 — `scrub_code_labels` 스크러버가 이 경로엔 미적용
  - **응답 잘림**: `* I (Institutional sponsorship): 6.5점 *` 에서 중간 절단
- 추정 원인: 전략가 결론이 없을 때 formatter 의 압축 분기가 raw 입력을 반환(또는 max_tokens 부족). **구현 시 진단 확정.**

**누수 ② 비교인데 한 종목만 분석** (검증 #4)
- scenario 4(비교) `route=analyst_direct` 인데 삼성 지표 미제공으로 **하이닉스만 분석**, 삼성은 "개별 지표 미제공" 한 줄로 스킵. 비교 질의 = 양 종목 prefetch 후 나란히 비교가 본질.

**누수 ③ 근거 3요소 템플릿 과적합** (검증 #3·#8)
- 시장·거시·온보딩 질의에도 "수급/차트/실적" 3축이 기계적으로 붙어 부실: 환율 질의(#8)에 `[수급] 정보 부족 / [차트] 정보 부족 / [실적] 정보 부족` 3줄 전부 공백. 질의 유형별 근거축 가변 필요.

## 핵심 결단 (3)

**F1 — analyst-only 경로 압축 보장 + 스크러버 전구간 + 잘림 방지**
- 전략가 없는 경로(`analyst_direct`·비교)도 formatter 가 **자연어 압축 결과**를 내도록 분기 수정(raw 반환 금지).
- `scrub_code_labels` 를 formatter 출력 **전 경로**에 통과(코드라벨 0 보장).
- formatter `max_tokens` 가 결론+근거를 담기에 충분한지 점검(잘림 0).

**F2 — 근거축 가변 (`config/evidence_axes.yaml`, 하드코딩 금지)**
- 고정 3요소(수급/차트/실적) → 질의 유형(route/scenario)별 동적 축 사전 주입.
  - 종목(track_a/b/both) = 수급 · 차트 · 실적
  - 시장(scenario 3 시장) = 국면(regime) · 시장폭(breadth) · 매크로
  - 거시(환율·금리) = 환율 · 금리 · 지수
  - 온보딩(주식 처음) = 투자원칙 · 시대 흐름
  - 미매칭 = default(수급/차트/실적)
- 빈 축은 "정보 부족" 나열 대신 **생략**(부실해 보이는 공백 3줄 제거).

**F3 — 비교 질의 양종목 prefetch + 비교 종합**
- scenario 4(비교)에서 분류된 **두 종목 모두** prefetch → formatter 가 나란히 비교 결론.
- 한쪽 지표 부재 시 "A는 X, B는 데이터 부족"을 *정직하게* 명시(스킵 금지).

## 판단 로직

<!-- SPEC:INTERVIEW-SLOT role="evidence-axes-taxonomy" -->
(질의 유형 → 근거축 매핑의 전체 분류표. F2 의 4종은 초안. `/spec-interview` 로 30 시나리오 전체 축 매핑 확정.)

<!-- SPEC:INTERVIEW-SLOT role="comparison-routing" -->
(F3 비교 질의에서 두 번째 종목 추출 방식 — classifier 가 ticker 1개만 반환하는 현 구조에서 양종목 파싱 위치. 구현 시 진단.)

## 검증

- `tests/intent/test_answer_fidelity.py` 신규:
  - F1: analyst-only 출력에 코드라벨 정규식(`점수=`, `leader`, `buy_candidate`, `Alignment`) 0 · raw 헤더(`## 분석가 raw`) 0 · 절단 마커 0
  - F2: 시장/거시/온보딩 질의에 "실적 정보 부족" 류 강제 부착 0 · evidence_axes.yaml 매핑 적용
  - F3: 비교 질의 = 두 종목 모두 prefetch 호출(mock 으로 호출 인자 검증)
- 라이브 스모크(`scripts/_guide_probe.py`) 재실행: #4 비교 · #8 환율 · #5 시장 → 코드라벨 0 · 공백 3줄 0 · 비교 양종목 등장
- 회귀: `TESTING=1 pytest tests/intent -q` (PRODUCTION-UX-001 골든 무파손) + 전체 suite
- `validate.py` 0 errors

## 구현 진행 (2026-06-06)

- **F1 ✅ 완료·라이브 검증** — anti-echo system 규칙 + scrub *이전* raw 에 echo 탐지(`_looks_like_echo`) + 1회 강제 재시도 + 최후 `_strip_echo` 결정론 정리. scrub 사전 확장(`leader`/`buy_candidate`/`moderate_bull`/`supply_chain`/`alignment`/`CAN SLIM` 등). 라이브 #4 비교 = raw 헤더·코드라벨·잘림 **0**.
- **F2 ✅ 완료·라이브 검증** — `config/evidence_axes.yaml` + `select_evidence_axes()` + 축-가변 `_formatter_system()` + 빈 축 생략 규칙. 라이브 #8 환율=`[거시 지표]` 단일, #5 시장=`시장 국면/시장 폭/거시 지표`. "정보 부족" 빈 줄 **0**.
- **F3 ✅ 완료·라이브 검증** — classifier `_extract_tickers_from_text`(등장순·중복/겹침 제거) + `IntentClassification.secondary_ticker` + 비교 scenario(4) return 주입. 라우터(`route_intent`+stream) analyst_direct 가 `secondary_ticker` 있으면 종목 점수 분석가(`_TICKER_SCORED_ANALYSTS`=stock_picker/stock_analyst)를 2번째 종목으로도 호출(market_state_analyzer 등은 1회). 라이브 #4 = 삼성·하이닉스 **양쪽이 각 근거축에서 나란히 비교**.
- 테스트 `tests/intent/test_answer_fidelity.py` 18 신규(F1·F2·F3), 전체 **868 passed**.

**LB-MS1 완료**: F1+F2+F3 모두 라이브 검증. status `verified`.

## 범위 밖 (의도적)

- KIS rate limiter 부채(검증 #4 배경 transient fetch 실패 → 점수 None 산재) — 별 백로그(`INFRA-KIS-RATELIMIT-001`). 본 SPEC 은 데이터 *있을 때* 누수만 봉합.
- 시장관 종합 / 순환매 판단 — LB-MS2 (`MARKET-VIEW-SYNTHESIS-001`).
- executive_mode synthesize 경로 — 본 SPEC 은 기본 `format_answer` 만(executive 는 후속).
