---
date: 2026-05-22
topic: WAVE-ALPHA-001 SPEC 5 라운드 면담 신설 (cycle 14 SPEC only)
status: completed
plan_file: C:\Users\HOME\.claude\plans\drifting-noodling-nova.md
---

# 2026-05-22 · WAVE-ALPHA-001 SPEC 신설 (cycle 14)

## 배경

cycle 13 (`bd1daaf`→`5bbfc92`, 같은 날 오전) `INFRA-SNAPSHOT-EXTEND-001` 풀세트 + production smoke 실증 직후 본 세션 = **잔여 차단점 1 개 = α=null + stock_analyst verdict=inconclusive 고정** 해소. RESUME Top 2 진입. `/spec-interview` skill ritual 4 회 누적 검증 (cycle 5/9/12/14). 사용자 결단 = 본 사이클 = SPEC frozen 만, 구현 = cycle 14 sub-cycle 14.1/14.2/14.3 (다음 ~1 세션). MS4 (실 매매 시연) 베이스라인 도달의 인프라 SPEC.

## 한 일

### 면담 5 라운드 결단 14 건 (영구 권위)

- **R1 (5건)**: anchor 정의 = 후보 ① (1차 발산 시작 / 정점 / 되돌림 저점 = 2차 발산 시작) — 사용자 **고유 파동분석 영역 (박종훈 X)** / 3 timeframe (daily/weekly/monthly) 동시 산출, 월봉 황제주 알림 cron 은 SLOT S2 분리 / anchor 산출 = **2-Stage 하이브리드** (결정론 candidate + LLM Haiku 4.5 직관 + 3 단 캐싱 + manual override) / **백테스팅 본질** = alpha() 가 cutoff_date 인자 + 결정론 = 친화 설계, 본체는 SLOT S3 분리 / 출력 surface = Layer 2 발행만 + webapp 자연어 가이드 부록
- **R2 (4건)**: 정식 공식 = 시간 정규화 기울기 비율 `α = (ln(current/C)/days(C→current)) / (ln(B/A)/days(A→B))` / 5 단계 label (trend_broken / weak / modest / sweet / overheated) + timeframe 별 차등 임계 테이블 / current 외삽 검증 메타데이터 2 (progress_to_b + duration_ratio) / 엣지 케이스 7 건 (E1~E7) + TIMEFRAME_LIMITS 권고
- **R3 (2건)**: 명제 ID 체계 = **WA/WF/WL/WE** (영역별 prefix, principle_guardian 21 명제 패턴과 정합) / canon 범위 분리 (본 SPEC = `01-anchor-and-alpha-formula.md` 1 장 21 명제 / 풀세트 = SLOT S4 후속 SPEC `WAVE-ALPHA-CANON-001` 가칭)
- **R4 (3건)**: verdict 분기 매트릭스 = long: (weekly+monthly) / swing: (daily) / 중립 (보수적 OR) / holding_period 매핑 = monthly sweet → 장기 / weekly sweet → 중기 / daily sweet → 단기 / 환각 가드 2 중 → **3 중** (WA·WF·WL·WE cited 강제 + chart_data_md 출처 유지 + anchor 출처 명시 신설)
- **R5 (3건)**: 테스트 풀세트 ~60 케이스 (정량 UT 56 + 통합 5) / SLOT 6 건 (S1 targets / S2 watch 알림 / S3 backtest / S4 canon-full / S5 anchor fine-tune / S6 LLM prompt 튜닝) / 구현 순서 = sub-cycle 분할 14.1/14.2/14.3 (cycle 13 패턴 재현)

### 산출물

- `docs/specs/WAVE-ALPHA-001-wave-alpha.md` 신설 (~360 줄) — frontmatter (`spec_id` / `title` / `status: frozen` / `version: 1` / `owner: stock_analyst` / `generates 5` / `modifies 6` / `depends_on 3` (INFRA-CHART-DATA-001 v2 + ANALYST-PERSONAS-001 v2 + INFRA-SNAPSHOT-EXTEND-001 v1) / `contracts 1` (`wave-alpha-v1`)). § 11 (목적 / 배경 / 핵심 정의 11 sub-§ / 라운드 결단 14 / SLOT 6 / 구현 순서 sub-cycle 3 / 부록 A webapp 자연어 가이드 / 부록 B depends_on 의존 상세)
- 코드 변경 0 (SPEC frozen 단독, cycle 5/9/12 패턴 정합)

## 검증 결과

- ✅ SPEC frontmatter 단독 파싱 통과 (`status: frozen` / `version: 1` / contracts 1 dict)
- ✅ 라운드 결단 14 건 ↔ SPEC 본문 § 1:1 박힘 (영구 권위)
- ✅ cycle 13 와 비슷한 규모 (DB 1 테이블 + 코드 모듈 2 + 테스트 60 + persona 정정 § 4) → sub-cycle 분할 패턴 정합

## 의도적으로 안 한 것

- **구현 (sub-cycle 14.1/14.2/14.3)** — 다음 사이클 ~1 세션, cycle 5/9/12 분할 패턴 정합
- **target_prices 3 단 산출 룰** — SLOT S1 분리 (verdict=confirmed_high_quality 진입 후 별 SPEC)
- **풀세트 canon W5+ 자료** — SLOT S4 분리 (`WAVE-ALPHA-CANON-001` 가칭, 사용자 chat Claude Opus 핑퐁)
- **백테스팅 본체** — SLOT S3 분리 (`WAVE-ALPHA-BACKTEST-001` 가칭, 사용자 본질 의도)
- **월봉 황제주 알림 cron** — SLOT S2 분리 (`WAVE-ALPHA-WATCH-001` 가칭, watchlist + telegram + cron)

## 맥락 재진입 힌트

- **사용자 framework 본질 정정** = 라운드 1 Q1-a 에서 사용자가 "프랙탈 + 로그 함수 해석은 본인의 고유 파동분석 영역" 으로 정정 (박종훈 X). canon `knowledge/canon/stock-analysis/fractal_wave/` 채움은 사용자 자가 정리만 (W5+ SLOT S4).
- **LLM 직관 분포 통찰** = 라운드 1 Q1-c 사용자 본질 = "anchor 추출은 인간 직관 영역, LLM 이 통계적 유사 답변으로 여러 사람 생각 취합한 표준 분포 역할 가능". 2-Stage 하이브리드 (결정론 candidate + LLM 직관 + 캐싱) 으로 비용·결정론 흔들림 해소.
- **백테스팅 본질 발견** = 라운드 1 Q1-d 사용자 강조 = "미래 성과 보기 전에 과거 백테스팅이 본 SPEC 질문 다 해소". 본 SPEC alpha() 함수가 cutoff_date 인자 + 결정론 + 캐싱 = 백테스팅 친화. 후속 SPEC S3 분리.
- **sub-cycle 분할 패턴 4 회 누적** = cycle 5 (chart) / 9 (fundamental) / 12 (snapshot extend) / 14 (wave-alpha) 모두 동일 = ~0.5 세션 SPEC + ~1~2 세션 구현 분할. **영구 ritual 격상**.

## 다음에 이어서 할 작업 (우선순위)

### 1. WAVE-ALPHA-001 구현 풀세트 (sub-cycle 14.1/14.2/14.3, ~1 세션) — MS4 진입 베이스라인
- **왜**: 본 SPEC frozen 직후 자연 진입. stock_analyst verdict=confirmed_* 정식 발행 + target_prices 활성 + holding_period 매핑 = MS4 (실 매매 시연) 베이스라인 도달
- **범위**: cycle 13 sub-cycle 분할 패턴 그대로. **14.1** (canon 21 명제 + DB v8 + scoring.py alpha 정식) → **14.2** (anchors.py 신규 + α 3 timeframe 통합) → **14.3** (persona v3→v4 + manifest + 테스트 60 + smoke + wrap-up). commit 3 개
- **선행 의존**: INFRA-CHART-DATA-001 v2 = chart_ohlcv 종목별 일봉 fetch 깊이 1년→5~10년 확장. 14.1 또는 별 마이크로 commit

### 2. production UX 본질 구현 (Top 1 옛, ~3 세션) — webapp 자연어 채팅창
- **왜**: cycle 13 MS3 차단점 해소 후 자연 진입. WAVE-ALPHA-001 구현 후 stock_analyst 풀세트도 입력 OK → production UX 본격 가능
- **범위**: 자연어 intent extractor + Track Selector 자동 라우팅 + 종합 답변 형식 + webapp 단일 채팅창 UI. 본 SPEC 부록 A 의 자연어 변환 사전 활용

### 3. SLOT S4 (KRX breadth bld) 정정 (~0.3 세션 소규모) — production UX 또는 WAVE-ALPHA 와 묶기
- **왜**: cycle 13 잔여. market_macro breadth 축 활성 = market_state_analyzer 4축 풀세트
- **범위**: KRX 데이터시스템 manual devtools 추출 → connectors/krx/client.py bld 교체. 단독 진행 X, Top 1/2 와 묶음

(추가 백로그: WAVE-ALPHA-CANON-001 (S4 풀세트 canon W5+) / WAVE-ALPHA-WATCH-001 (S2 월봉 황제주 알림) / WAVE-ALPHA-BACKTEST-001 (S3 백테스팅 본체) / NEWS-SOURCE-001 / PERSONA-REFUSAL-CITED-RULE-001 / news_curator 슬림화 / Layer 4·5 / GUIDANCE-ACCURACY-TRACKER-001 구현 / INFRA-US-MACRO-SNAPSHOT-001 / 박종훈 Vol 2/3 OCR / png vision / xlsx sheet 분리 / canon 정수 추출 자동화)

## 커밋 상태

- 본 wrap-up commit 진행 예정 = SPEC 1 + c_worked + RESUME.md + SESSIONS.md + 메모리 3 신규 (1 commit, cycle 5 ad6ec07 / cycle 9 / cycle 12 패턴 정합)
