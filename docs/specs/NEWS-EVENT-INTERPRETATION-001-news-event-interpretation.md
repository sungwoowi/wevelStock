---
spec_id: NEWS-EVENT-INTERPRETATION-001
title: 뉴스 중심 이벤트 격상 + LLM 해석 — 단기 공포 vs 변곡 판별이 전략가에 도달 (Tier 1)
team: news
type: feature
level: implementation
status: implementing
parent: MARKET-CONTEXT-BRAIN-001
generates:
  - tests/test_news_event_interpretation.py   # 메타발 06-23~07-02 리플레이 시나리오 포함
modifies:
  - collectors/news_source.py                 # M1-a 격상 레인(결정론) + M1-b 해석 스테이지(LLM 1콜) + digest 확장
  - core/strategist/run_strategist.py         # M1-c news_digest_md 파라미터 (alpha_posture_md 패턴)
  - core/signal/auto_signal.py                # M1-c 호출부 — digest md 조립·주입 (DB-first + lookback 폴백)
  - server/schedulers/jobs/__init__.py        # M1-b′ 장전 06:40 ingest cron (news_ingest::premarket, D5)
  - pipelines/market_briefing_pre/stages/analyze.py  # M1-c 07:00 브리핑 소비 배선 (digest md 컨텍스트 주입, D5)
  - config/news_source.yaml                   # elevation/interpretation/premarket 섹션 (임계·tier·시각·토글 외부화)
  - core/db/migrate.py                        # news_digest_snapshot.elevated_events_json 멱등 ALTER (기존 패턴)
  - knowledge/canon/news/01-classification-doctrine.md  # M2 — N5 개정 (해석된 격상 이벤트 예외 단서)
contracts:
  - name: news-digest-v1                      # 기존 digest 구조에 elevated_events 필드 가산 (하위 호환)
    version: "1.1"
depends_on:
  - AUTO-SIGNAL-INTEGRITY-001 (T0-d 뉴스 백필 — 해석 입력 품질 선행 수리, 완료)
  - NEWS-SOURCE-001 (수집·분류·digest 파이프라인 — 그 위에 해석층)
  - LLM-COST-LEDGER-001 (해석 콜 원장 라벨 `news_interpretation`)
---

# NEWS-EVENT-INTERPRETATION-001 — 뉴스 중심 이벤트 격상 + 해석 (Tier 1)

> **격상보다 해석 퀄리티가 본질** (사용자 결정 2026-07-05): "단기적 공포인가 시장 변곡인가,
> 시계열상 어떤 매매 포인트로 삼아야 하는가"를 판별해 전략가에 도달시킨다.
> 실사고 표본 = 메타발 AI capex 논란: 06-23 발생 → 06-23~28 대량 보도(다수 미라벨링·클러스터
> 희석) → 07-01~02 반도체 급락 실현. 시스템은 수집·라벨링까지만 하고 격상·해석·전달이 전무했다
> (news_curator = 어느 전략가도 안 읽는 dead-end, 부모 SPEC §1-④).
> 07-03 SK하이닉스 재구성(시스템 전층 wait vs 사용자 폭락 매수 +18.6%)이 "해석 능력 부재"를
> 숫자로 확정 — 해석 질문지 3축은 그 실판단에서 추출된 것.

## 면담 결정 (2026-07-05, 5라운드 압축)

| # | 결정 | 내용 |
|---|---|---|
| D1 | 격상 기준 | **mag3 단건 즉시 + mag2 × 서로 다른 출처 N건(config 기본 3) 동시 보도** — LLM 라벨 불안정성(같은 이벤트도 2/3 갈림)을 확산 감지가 보완. 결정론이라 백테스트·리플레이 가능 |
| D2 | 저장 위치 | **`news_digest_snapshot` 컬럼 확장** (`elevated_events_json`) — 이벤트마다 `event_key` 부여, 전일 스냅샷에서 같은 key 를 찾아 이전 해석을 memory 주입(M2). 신규 테이블 0 |
| D3 | LLM 비용 | **Flash 기본 + `llm_call_cache` 멱등 캐싱 + 원장 질의영역 `news_interpretation`** — 격상은 드묾(예상 일 0~2건), 해석 퀄 부족 시 config 로 Pro 승격(하이브리드 정책) |
| D4 | MVP 컷 | **M1 = 격상+해석+전략가 배선(advisory 전용, 게이트 미작동)** → 메타발 리플레이로 해석 퀄 검증 후 **M2 = lifecycle memory + 게이트(is_macro_inflection 제3트리거·entry_posture 기여) + N5 개정** — 해석이 틀린 채 게이트에 물리는 위험(노이즈 매매) 차단 |
| D5 | ingest 주기 (2026-07-06 추가 면담) | **장전 06:40 ingest 신설 + 18:05 유지 (하루 2회)** — 간밤 미장발 이벤트(메타발 유형)가 07:00 장전 브리핑·09:35 장중 회차에 해석된 상태로 도달. 소비 측은 최신 digest lookback 폴백(오늘 없으면 직전 것 + 시점 표기). 장중 회차별 재수집은 기각 — 장중 돌발 이벤트는 가격 기반 복합 위험 게이트가 이미 같은 회차에 반응(뉴스보다 가격이 빠름) |

## M1 — 격상 + 해석 + 전달 (advisory)

### M1-a 격상 레인 (결정론, LLM 0)
- `build_news_digest` 에 격상 감지 단계 추가: 당일 라벨링된 items 에서
  ① magnitude=3 단건 → 즉시 격상 ② magnitude≥2 이벤트가 **서로 다른 `source` N건**(config
  `elevation.multi_source_n`, 기본 3) 동시 보도 → 확산 격상.
- "같은 이벤트" 판별 = 결정론 클러스터(기존 `_top_themes` 테마 클러스터 재사용이 1차 후보).
  <!-- SPEC:INTERVIEW-SLOT: 클러스터 키의 정밀도 — theme 문자열 매칭으로 부족하면 affected_refs·category 결합. 구현 중 실데이터로 확정 -->
- 격상 0건 날 = `elevated_events: []`, 해석 콜 0 (비용 0). tone 평균·건수 클러스터 레인은 무변
  (별도 레인 — 희석 방지가 목적이지 대체가 아님).

### M1-b 해석 스테이지 (LLM 1콜/이벤트, Flash + 캐싱)
- 격상 이벤트에 한해 `interpret_elevated_event()` — 입력: 소속 기사들(제목·라벨) + 당일
  market_view 요약 + N2 시간축 canon 발췌 + **시장 실반응·파동 컨텍스트**(아래). 중앙
  `call_llm` 경유(원장 자동 기록).
- **시장 실반응·파동 컨텍스트 (사용자 통찰 2026-07-05 3세션)**: 기사 텍스트만이 아니라
  ① 그 이벤트에 영향받은 **주요 시장의 실제 움직임**(미장 나스닥·SOX·VIX = `us_macro_snapshot`
  기존 / 국장 지수·섹터 등락 = market snapshot 기존) ② 그 시장의 **현재 차트 추세·파동상
  위치**(정배열/이격/DD 카운트 = regime 입력 기존 — 조정이 나올 자리인가 상승 여력 자리인가)
  를 결정론 값으로 프롬프트에 주입 → 매크로(뉴스) × 업황(펀더 정합) × 파동 수학(가격 위치)의
  종합 해석. 뉴스가 같아도 "이미 과열·조정 임박 자리"면 빌미 확률↑, "추세 초입"이면 해석이
  달라진다 — 3축(특히 노이즈 반복=빌미)의 판별 정확도를 올리는 재료.
  <!-- SPEC:INTERVIEW-SLOT: 지수 레벨 WAVE-ALPHA α 적용 여부(현 anchor 는 종목 대상) — M1 은 기존 결정론(정배열·이격·DD)로 시작, 지수 α 는 효과 보고 확장 -->.
- **출력 스키마** (StandardOutput 이 아니라 digest 내장 JSON):
  - `event_key`: 이벤트 슬러그 (재보도 연결용 — M2 lifecycle 의 기초, M1 부터 부여)
  - `nature`: `transient_fear`(단기 공포=잠재 기회) | `structural_inflection`(구조 변곡) | `unresolved`
  - `axes`: 해석 질문지 4축 — ⑴ novelty(새 정보 vs 예고 재탕) ⑵ fundamental_alignment(사이클
    팩트와 내러티브 정합 — 마이크론 호가이던스 vs 셀오프 = 괴리) ⑶ noise_rotation(매일 다른
    악재 순환 = 고점 조정 빌미 시그니처) ⑷ market_reaction_alignment(시장 실반응·파동 위치와의
    정합 — 실제 미장/국장이 얼마나 반응했고, 그 시장이 추세·파동상 조정 나올 자리였는가 =
    뉴스가 원인인가 빌미인가). 각 축 = 판정 + 한 줄 근거
  - `impact_path`: 영향 섹터·주도 테마
  - `trade_implication`: posture 후보 서술 (관망/현금확보/눌림목 대기 등 — M1 에선 서술만, 액션 아님)
  - `reassess_condition`: 무엇이 확인되면 판정을 바꾸는가
  - `confidence`: 0~100
  <!-- SPEC:INTERVIEW-SLOT: nature 3분류 경계 사례(공포이면서 변곡의 시작인 경우) 프롬프트 지침 — 구현 중 메타발 리플레이로 튜닝 -->
- 멱등: `input_hash = sha256(event_key + 소속 기사 url 집합 + 일자 + model)` → 같은 날 재실행 LLM 0.
- Gemini thinking_budget=0 + max_tokens 충분히 ([[feedback_gemini_thinking_budget_json]] 결함 회피).

### M1-b′ 장전 ingest (D5 — 간밤 이벤트를 아침에 해석)
- `run_news_ingest` 를 평일 **06:40** cron 으로 1회 추가 발동 (`news_ingest::premarket`,
  misfire_grace 기존 패턴) — 간밤 미장발 신규 기사만 실비용(url 캐싱으로 기존 기사 분류 0,
  해석은 격상 시 0~2콜). us_macro "18:05+장전 둘 다 적재" 전례와 같은 패턴.
- 18:05 회차는 유지 — 장중 쌓인 뉴스로 digest·해석 갱신 (같은 event_key 는 캐시 히트,
  소속 기사 집합이 늘면 재해석 = 의도된 갱신).
- **일일 시간표**: 06:40 ingest → 07:00 장전 브리핑이 실음 → 09:35/12:35/14:35 회차 재사용
  → 18:05 갱신.

### M1-c 전달 배선 (이 SPEC 의 존재 이유 — 전략가 도달 첫 경로)
- `render_news_digest_md` 확장: 격상 이벤트가 있으면 **"오늘의 중심 이벤트" 섹션을 최상단**에
  (nature·3축·매매 함의·재평가 조건) — tone·테마 요약은 기존대로 후순위.
- `run_strategist(news_digest_md=)` 파라미터 신설 — `alpha_posture_md` 와 동일 패턴
  (`core/strategist/run_strategist.py:351`, compose 슬롯은 이미 존재).
- 호출부(auto_signal + production chat 전략가 경로)가 DB-first 로 digest 조립
  (`get_news_digest` — 소비 시 LLM 0) 후 전달. **최신 lookback 폴백**(D5): 오늘 digest 미존재
  시 직전 일자 것 + "N시간 전 해석" 시점 표기(stale 침묵 금지).
- **07:00 장전 브리핑 소비 배선**(D5): `market_briefing_pre` analyze 스테이지 컨텍스트에
  digest md(격상 이벤트 섹션) 주입 — 브리핑은 어차피 LLM analyze 라 추가 콜 0. 아침 텔레그램
  "시나리오+뉴스" 파트에 "오늘의 중심 이벤트" 해석이 실리는 것이 M1 의 사용자 체감 산출물.
- track_a/track_b manifest `reads_analysts` 에 news_curator 추가 (dead-end 해소 문서화).
- **M1 은 advisory 전용**: 게이트(is_macro_inflection·entry_posture) 기여 0 — N5 canon 원칙
  ("tone 을 게이트로 쓰지 않는다") 그대로. 전략가 LLM 이 해석을 읽고 스스로 반영하는 것까지만.

## M2 — lifecycle + 게이트 + N5 개정 (M1 해석 퀄 검증 후)

- **lifecycle memory**: 해석 시 전일(~lookback 7d) `elevated_events_json` 에서 같은 `event_key`
  를 찾아 이전 판정·재평가 조건을 프롬프트에 주입 → 판정 갱신(발생→확산→구조화/소멸).
  메타발 06-23 발생→07-02 실현의 경과 추적이 검증 표본.
- **게이트**: `structural_inflection` 으로 해석된 격상 이벤트만 ① `is_macro_inflection`
  (collectors/market_macro.py:215) 제3 트리거 ② entry_posture 기여. `transient_fear`/`unresolved`
  는 advisory 유지 — 노이즈 매매 차단. PANIC-REVERSAL 레인(Tier 2)의 "단기 공포 판정" 입력도
  이 nature 필드.
- **N5 canon 개정**: "뉴스 tone 을 게이트로 쓰지 않는다" 원칙 유지 + "**해석된**(3축 통과)
  structural_inflection 격상 이벤트는 예외" 단서 추가.
  <!-- SPEC:INTERVIEW-SLOT: M2 착수 시 게이트 기여 방식(변곡 트리거만 vs entry_posture 단계 강등까지)·confidence 하한 재면담 -->

## M1 구현 결과 (2026-07-06 — 리플레이·probe 실측)

- **메타발 리플레이 재현**: 06-23 발생(서킷브레이커·삼성 급락 mag3 격상) → 06-25~27 확산
  (KOSPI 급락·SK하이닉스 서킷브레이커 + **mag2×다중소스 레인 발화 1건**) → 07-02~03 실현
  (일 3~4건 격상). 리플레이 = `scripts/_replay_news_elevation.py` (읽기 전용·결정론).
- **해석 probe (07-03, 실 Gemini Flash 1콜 $0.0002)**: nature=transient_fear + 4축
  (재탕/괴리/악재 순환/빌미 — 시장 컨텍스트의 분산일 6건·필반 급락·야간선물 상승을 근거로
  인용) + 매매 함의 "관망/눌림목 대기" = **사용자 07-03 실판단과 동일 결**. 원장
  `news_interpretation` 라벨·캐시 기록 확인.
- **선행 데이터 수리**: 06-23~27 미라벨링 204건이 T0-d 백필 lookback 7d 밖에 남아 있던 것을
  lookback 16d 1회 백필로 해소 (잔량 0) — 표본이 살아있을 때 착수한 이유 그 자체.
- **관찰 (INTERVIEW-SLOT 재료)**: 클러스터 키가 "Samsung/tech/KOSPI/semiconductor/
  market_sentiment" 로 분산 — 사실상 한 거시 이벤트가 여러 키로 쪼개짐. M1 은
  max_events_per_day=3 상한으로 비용 유계, 키 정밀화(엔티티 정규화·영문/한글 수렴)는
  구현 중 확정 SLOT 대로 후속.

## 수용 기준 (테스트 시나리오)

1. **메타발 리플레이 (M1 핵심)**: 실 DB 06-23~07-02 기사(백필 완료분)로 격상 레인이 AI capex
   이벤트를 mag2×다중소스로 식별 — cutoff 결정론(격상 감지는 LLM 0 이라 완전 재현). 해석은
   실 LLM 1콜 probe 로 3축·nature 산출 확인.
2. **격상 0건 날**: elevated_events 빈 배열 + 해석 LLM 콜 0 (mock 카운트).
3. **멱등**: 같은 날 2회 실행 → 해석 LLM 콜 1회(캐시 히트), digest upsert 멱등.
4. **전달 증명**: run_strategist 에 news_digest_md 전달 시 compose 프롬프트에 "오늘의 중심
   이벤트" 섹션 포함(단위) + 자동 경로 라이브 probe 에서 전략가 사유에 이벤트 인용 관측.
4-b. **시간표 정합 (D5)**: 장전 ingest 후 07:00 브리핑 analyze 컨텍스트에 격상 섹션 포함(단위,
   mock LLM) + 오늘 digest 부재 시 lookback 폴백이 직전 일자 것 + 시점 표기로 동작(단위).
5. **advisory 경계 (M1)**: 격상 이벤트가 있어도 is_macro_inflection·entry_posture 무변 (게이트
   미작동 단위 증명 — M2 전까지의 안전선).
6. **원장**: 해석 콜이 `llm_cost_ledger` 에 질의영역 `news_interpretation` 으로 기록.
7. 전체 pytest 회귀 0 · validate 0.

## 재사용 영향도 (가드 #11 — DATA-MAP 확인 완료)

**신규 테이블 0 · 신규 collector/connector 0 · 신규 API 라우트 0.**
- 뉴스 도메인 home = `news_source_items`(라벨 자료층) + `news_digest_snapshot`(일자 집계) 기존
  2테이블 — 격상·해석은 **digest 의 (scope,date) 스냅샷에 `elevated_events_json` 컬럼 확장**
  (멱등 ALTER, 기존 마이그 패턴). 이벤트 단위 신규 테이블은 기각: 일자 스냅샷 + event_key 로
  lifecycle 재구성이 가능해 "확장 불가" 입증이 성립하지 않음.
- 해석 LLM = 기존 `call_llm` 중앙 경유 → `llm_call_cache`(멱등)·`llm_cost_ledger`(원장) 자동 재사용.
- 격상 클러스터 = 기존 `_top_themes` 결정론 재사용(collectors/news_source.py:909).
- 전달 = compose.py 기존 슬롯(`news_digest_md`, core/knowledge/compose.py:183) + run_strategist
  파라미터 1개 가산(기존 `alpha_posture_md`/`trade_plan_menu_md` 패턴 반복).
- 3층 파급: DB(컬럼 1 가산, 기존 read 하위 호환 — json 필드 없으면 빈 배열) → backend(digest
  builder·renderer 확장 + strategist 파라미터) → frontend(뉴스 탭이 digest 를 이미 소비 —
  격상 섹션 노출은 **후속 SLOT**, 본 SPEC 은 렌더 md 까지).

## SLOT (본 SPEC 범위 밖, 기록만)

- **장전 브리핑 레거시 뉴스 경로 수렴**: `market_briefing_pre` 의 `collect_news` 스테이지는
  레거시 `news_items`(run-scoped) 사용 — 정본(`news_source_items`→digest) 소비 배선(M1-c)이
  자리잡으면 레거시 스테이지 제거/수렴 검토 (별 작업, DATA-MAP "후속 정본" 노트 정리).
- 뉴스 탭 UI 에 "오늘의 중심 이벤트" 카드 (GATE-VISIBILITY 와 묶을 후보).
- Tier 2 연계: 격상 이벤트의 테마 클러스터 → LEADERSHIP-DISCERNMENT 주도주 판별 입력.
- Tier 3 연계: trade_implication → 포트폴리오 자세 액션 필드(contract bump 는 그쪽에서).
- 수동 인사이트 주입 채널(보류, 부모 SPEC Tier 3 방향 명시)과 해석 소비 경로 합류.
