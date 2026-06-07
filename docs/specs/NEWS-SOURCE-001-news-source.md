---
spec_id: NEWS-SOURCE-001
title: 뉴스부 자료층 — 영속 분류·시간축 라벨 news_items + build_news_digest 단일 소스 → market_view·buy_score N축 촉매·뉴스큐레이터
team: shared
type: feature
status: implementing
level: implementation
parent: LEFT-BRAIN-COMPLETION-001          # LB-MS3
generates:
  - collectors/news_source.py
  - config/news_source.yaml
  - knowledge/canon/news/01-classification-doctrine.md
  - knowledge/canon/news/_category.yaml
  - tests/test_news_source.py
  - scripts/_news_digest_probe.py
modifies:
  - collectors/news_rss.py
  - core/db/schema.sql
  - core/db/connection.py
  - core/inference/run_analyst.py
  - core/knowledge/compose.py
  - collectors/buy_score_inputs.py
  - collectors/market_view.py
  - agents/analysts/news_curator/manifest.yaml
  - agents/analysts/news_curator/persona.md
depends_on:
  - LEFT-BRAIN-COMPLETION-001 (roadmap parent — LB-MS3)
  - ANALYST-PERSONAS-001 (news_curator persona v2 — 의사결정 SLOT S2 자료원 미결정을 본 SPEC 이 클로즈)
  - INFRA-SCORE-INPUTS-001 (buy_score CAN SLIM N축 — 현재 52주 신고가만, 신제품/뉴스 촉매 0시드를 본 SPEC 이 메움. _maybe_build_*_md / reads_* hook 패턴 mirror)
  - MARKET-VIEW-SYNTHESIS-001 (market_view 내러티브 흡수처 — 시장 전반 뉴스 톤·테마. build_* 단일 산출물 read 패턴 mirror)
  - INFRA-RAG-001 (canon/news/ RAG — 뉴스 본문 임베딩은 SLOT, 흡수 시 재사용)
contracts:
  - name: news-item-v1
    version: "1.0"
    description: "개별 뉴스 1건 + LLM 분류 라벨. NewsItem = {title, url, source, published_at, category∈{macro_policy,industry_trend,geopolitics,policy_political,corporate_events,market_sentiment}, time_axis∈{ephemeral_shock,short_theme,structural_trend}, direction∈{up,neutral,down}, magnitude∈{1,2,3}, confidence(0~100), affected{scope∈{market,sector,ticker}, refs[]}, labeled_by∈{llm,manual,rss_raw}}. 자료원=NewsSource 어댑터(RssNewsSource=fetch_news 흡수 / ManualNewsSource=본문·유튜브 요약 직접 / PerplexityNewsSource=drop-in SLOT). **`news_source_items` 테이블** DB-first upsert(URL 멱등) — 구현 시 레거시 브리핑 테이블 `news_items`(run_id PK, persist.py)와 충돌해 `news_source_items` 로 개명(MS-A 자가발견)."
  - name: news-digest-v1
    version: "1.0"
    description: "build_news_digest(date[, ticker]) 단일 산출물. NewsDigest = {date, scope, tone∈{bearish,lean_bearish,neutral,lean_bullish,bullish}(거친 5단 tilt — 정밀 점수 아님), category_counts{cat:{up,neutral,down}}, top_themes[{theme, time_axis, trigger_titles[]}], catalyst_tilt{direction, strength∈{weak,mid,strong}}(종목/섹터 scope 시 buy_score N 블렌드용), raw_labels(LLM 주입용 분류 텍스트 묶음), source∈{db,computed,empty}}. 시장 전반 → market_view 흡수 / 종목·섹터 → buy_score N축 촉매. news_digest_snapshot DB-first 멱등(scope|date 키)."
---

# NEWS-SOURCE-001 — 뉴스부 자료층 (LB-MS3)

> roadmap parent: **LEFT-BRAIN-COMPLETION-001** / 마일스톤 **LB-MS3** (왼쪽 뇌의 마지막 0시드 지식부).
> 완료 신호(roadmap): *"뉴스가 분류·시간축 라벨링되어 영속 누적되고, '오늘 뉴스 톤/테마'가 market_view 내러티브와 종목 촉매로 상시 흐른다."*

## 목적

왼쪽 뇌(수집→분석→답변)에서 **9번째 지식부 = 뉴스부만 자료 0 시드**다. 재료(RSS 헤드라인)는 매일 장전 브리핑이 *일회성으로* 긁어 쓰고 버리지만, "분류되어 누적되는 뉴스 학습층"이 없다. 그래서:
- `market_view`(LB-MS2)가 6/5형 *"버블 붕괴냐 조정이냐"* 같은 **내러티브 입력**을 못 받는다(SPEC 이 `NEWS-SOURCE-001 후 흡수` 로 SLOT 비워둠).
- `buy_score` CAN SLIM **N축(New = 신고가 + 신제품/뉴스 촉매)**의 *뉴스 촉매 절반*이 0시드(`buy_score_inputs.py:221` 가 직접 `SLOT: NEWS-SOURCE-001` 표시).
- `news_curator` 분석가가 "자료원 미결정(SLOT S2)" 상태로 자가 진단을 거부한다.

본 SPEC = 그 한 겹을 **영속 분류 뉴스 자료층 + 거친 종합(digest)** 으로 채운다. 개별 뉴스 *판단*은 LLM(정성적, 불가피), *집계*는 결정론(카운트·톤 tilt). 정밀 점수화는 의도적으로 폐기한다(아래 M4).

## 배경 / 문제 — 이미 도는 것과의 관계 (중복 아님, 승격)

장전 브리핑 `pipelines/market_briefing_pre/`(평일 07:00)가 이미 뉴스를 수집·해석한다 — 그게 사용자가 받은 *"시나리오+뉴스 2/3"* 알림:
- `collect_news` stage → `collectors/news_rss.py::fetch_news()` = Yahoo Finance RSS + CNBC RSS + Google News RSS(4 쿼리) **헤드라인(제목+URL+게시일, 본문 X)** dedup·20 cap.
- `analyze` stage(LLM) → 야간 미장+선물+뉴스 헤드라인 종합 → 시나리오 + 각 뉴스 방향(⬆️⬇️➡️) + 한 줄 해석.
- `persist`→`notify` → `briefing_parts` DB + 텔레그램.

**차이 = 영속성·분류·소비자**:

| | 현재 (브리핑 collect_news) | NEWS-SOURCE-001 |
|---|---|---|
| 영속성 | 일회성(브리핑 1회 소비 후 폐기) | `news_items` 시계열 DB 누적 |
| 분류 | 없음(LLM 즉석 방향만) | 카테고리 + 시간축 라벨 영속 |
| 본문 | 제목만 | 유튜브 요약 / 본문 직접 입력 채널 |
| 소비자 | 브리핑 1개 | **market_view + buy_score N + news_curator** |
| 자료원 | RSS 하드코딩 | `NewsSource` 어댑터(RSS=한 구현체) |

→ NEWS-SOURCE-001 = 일회성 브리핑 RSS 를 **영속·분류·다중 소비자 뉴스 학습층으로 승격**. `fetch_news()`/`NewsItem` 은 폐기하지 않고 **`RssNewsSource` 어댑터 첫 구현체로 흡수**(M1). 작동 중 브리핑은 안 깬다(브리핑→news DB read 통합은 SLOT).

## 핵심 결단 (7 — 면담 확정, 영구 권위)

**M1 — 기존 RSS(fetch_news) 를 NewsSource 어댑터 첫 구현체로 흡수 (중복 X, 승격)**
- `NewsSource` 추상(Protocol): `async def fetch() -> list[NewsItem]`. 구현체 = `RssNewsSource`(기존 `fetch_news` 래핑, 자동수집 1차 라이브) / `ManualNewsSource`(본문·유튜브 요약 직접 입력) / `PerplexityNewsSource`(인터페이스만, MCP 연결 시 drop-in — **이 환경 Perplexity MCP 미연결 확인**, capability gap 명시).
- 자료원에 코드 비종속 → 교체 자유. 시드 결정([[project-news-source-decision]]) 의 "Perplexity 기본" 은 *지향*, 현재 capability 는 RSS+수동.

**M2 — DB=사실 / canon=분류룰 (얕게 시작, 9지식부 1:1 대칭 유지)**
- `news_items` DB = 휘발성 시계열 *사실*(개별 뉴스 + LLM 라벨). `knowledge/canon/news/` = 안정적 *원리*(분류·시간축 판단 기준 1파일 + 명제 N1~N5) → LLM 분류 시 system prompt 주입(다른 8 분석가가 canon 주입받는 자리와 동일).
- canon 은 처음엔 얇게(1파일). 뉴스 본문 RAG 임베딩은 SLOT(리소스 + 뉴스 휘발성·RAG 적합성 의문).

**M3 — 카테고리 6 (user_want_spec 5종 + 시장심리)**
- `macro_policy`(통화·재정) / `industry_trend`(산업) / `geopolitics`(지정학) / `policy_political`(정치) / `corporate_events`(기업 이벤트) / `market_sentiment`(공포·탐욕·버블·조정 내러티브 — 6/5형 입력 수용, market_view 흡수에 최적).

**M4 — N축·digest 는 정밀 점수 폐기 → 거친 tilt + 내러티브 (정직성)**
- *뉴스는 상황의존·퀄리티편차·비선형상호작용·희소충격* 이라 단일 정밀 점수(0~10)로 누르는 건 정직하지 않다(사용자 직감 + Claude 무편향 판단 합치). 프로젝트 원칙([[feedback_score_collapse_advisory]]: 결정론 점수 게이트키핑 X, 원시 지표 LLM 주입, 점수 advisory)과 동일.
- **[1] 개별 뉴스 = LLM** 라벨 `{category, time_axis, direction(+/0/-), magnitude(1~3), confidence}` — 기사 단위 판단(브리핑이 이미 하는 일의 영속화).
- **[2] 집계 = 결정론** — 카테고리별 +/0/- 카운트 + 거친 톤 tilt(5단) + Top 테마. *결정론은 집계뿐, 판단은 LLM*. 같은 라벨 묶음 → 같은 tilt(백테스팅 재현).
- buy_score N 은 "숫자 N.N" 아님 → **거친 catalyst_tilt(방향+강도) + raw 라벨 텍스트** 를 LLM 에 주입(advisory). market_view 는 tone·테마를 **내러티브로** 흡수.

**M5 — build_news_digest(date[, ticker]) 단일 산출물 (시점 일관·중복 제거)**
- 모든 소비자(market_view·buy_score·news_curator)가 **하나의 digest** 를 read(5점수 `build_*` 단일 산출물 패턴 mirror). 각자 news_items 직접 쿼리 금지(집계 로직 중복·시점 불일치 회피).
- `scope`: 인자 없으면 시장 전반(market) → market_view. `ticker`/`sector` 주면 해당 종목·섹터 뉴스만 → buy_score N catalyst_tilt.

**M6 — 시간축 라벨 3단 (단발→지속 가변)**
- `ephemeral_shock`(단발 충격, 당일·수일) / `short_theme`(단기 테마, ~1~2주) / `structural_trend`(지속 흐름, 분기+). manifest 기존 표현("단기 테마성/장기 흐름/지정학 충격") 정밀화. 단발이 단기·장기로 분기 가능(가변). 판단 기준 = canon doctrine.

**M7 — buy_score N = CAN SLIM "New"(신고가 + 신제품/뉴스 촉매), 본 SPEC 이 뉴스 절반을 메움 (코드 발견)**
- `buy_score_inputs.py:221` 이 N축을 `52주 신고가만 (SLOT: NEWS-SOURCE-001)` 로 명시. N = New(신고가·신제품·신뉴스) 중 신고가만 라이브.
- 본 SPEC = **종목/섹터 scope digest 의 catalyst_tilt 를 기존 52주 신고가와 블렌드**(가중 합성, config). 시장 전반 뉴스는 N 에 안 넣음(그건 market_view 영역) — *종목 뉴스→종목 점수, 시장 뉴스→시장관* 분리.

## 구현 범위

### 하는 것 (MVP)
1. `collectors/news_source.py` — `NewsItem` 라벨 확장 계약 + `NewsSource` Protocol + `RssNewsSource`(fetch_news 흡수) + `ManualNewsSource` + `classify_news_items()`(LLM 라벨, Gemini FAST/BALANCED tier·`thinking_budget=0`·`llm_call_cache` 멱등) + `build_news_digest(date, scope, ticker=None)`(결정론 집계: tone tilt + category_counts + top_themes + catalyst_tilt) + `render_news_digest_md()`([8] 주입 블록).
2. DB: `news_source_items`(url 멱등 PK — **레거시 브리핑 `news_items` 충돌로 개명**) + `news_digest_snapshot`(scope|date 멱등) 테이블 — `schema.sql` + `connection.py` (v11 신규 테이블, ALTER 불필요. market_view v10 패턴 mirror).
3. `knowledge/canon/news/01-classification-doctrine.md`(분류·시간축 판단 기준 + 명제 N1~N5) + `_category.yaml` + news_curator manifest `canon_categories`/persona `## Knowledge Categories` 갱신.
4. 소비 배선:
   - market_view: `collectors/market_view.py::build_market_view` 가 시장 scope digest 의 tone·top_themes 를 `reasons`/`one_liner` 내러티브로 흡수(결정론, M5 단일 read).
   - buy_score: `collectors/buy_score_inputs.py` N축에 종목 scope catalyst_tilt 블렌드(52주 신고가 + 뉴스 촉매, config 가중) + raw 라벨 reasons.
   - news_curator: `run_analyst._maybe_build_news_digest_md`(+`reads_news_digest` flag) + `compose.build_pipeline_prompt(news_digest_md=...)` [8] 블록.
5. `news_curator` persona/manifest: "자료원 미결정 인지" 제거 → RSS+수동 자료원 + tilt 산출 인지 + tilt 정밀점수 아님 강조.
6. `config/news_source.yaml`(카테고리·시간축 labels·tone tilt 임계·catalyst 블렌드 가중·source 토글·digest 캐싱 — 하드코딩 0).
7. `scripts/_news_digest_probe.py`(라이브 probe, `_market_view_probe.py` mirror) + `tests/test_news_source.py`.

### 안 하는 것 (범위 밖 — SLOT 또는 별 SPEC)
- **UX/UI 어드민**(뉴스 추가·라벨·검색·삭제 화면) — 큰 인프라, 별 SPEC(`NEWS-ADMIN-001` 후보).
- **PerplexityNewsSource 구현체** — 인터페이스만. MCP 연결 시 drop-in.
- **유튜브 자동 트랜스크립트 추출** — 수동 요약 입력만(ManualNewsSource). 자동은 SLOT.
- **브리핑 collect_news → news DB read 통합** — 작동 중 브리핑 안 깸. 통합 SLOT(중복 fetch 제거는 후속).
- **뉴스 본문 RAG 임베딩**(INFRA-RAG-001 흡수) — SLOT.
- **정밀 N 점수(0~10)** — 의도적 폐기(M4).
- **일일 적재 cron 배선** — dev cron 미작동 이슈(LEFT-BRAIN Top 3 #3) 연결. MVP=수동 트리거 + 브리핑 cron 합류 후보. SLOT.
- **WebSearch/WebFetch 자동수집 구현체** — RssNewsSource 로 1차 충분. US-only WebSearch 보강은 SLOT.

## 설계

### 데이터 흐름
```
[자료원 어댑터]  RssNewsSource(fetch_news) │ ManualNewsSource(유튜브·본문)
        │  (제목·URL·게시일 + 본문 옵션)
        ▼
classify_news_items()  ← LLM 라벨 {category,time_axis,direction,magnitude,confidence,affected}
        │  (llm_call_cache 멱등, Gemini thinking_budget=0)
        ▼  upsert news_items (URL 멱등)
        │
build_news_digest(date, scope[, ticker]):     ← 결정론 집계 (점수 X, 카운트·톤)
        ├─ tone (5단 tilt)  + category_counts(+/0/-)  + top_themes  + catalyst_tilt  + raw_labels
        ▼  upsert news_digest_snapshot (scope|date 멱등)
        │
   ┌───────────────────────┬─────────────────────────┬──────────────────────┐
   ▼ scope=market          ▼ scope=ticker/sector      ▼ (분석가 해석)
 build_market_view 흡수    buy_score_inputs N축 블렌드   run_analyst._maybe_build_news_digest_md
 (tone·테마 내러티브)       (52주 신고가 + catalyst_tilt)  → news_curator read·해석
```

### NewsItem 계약 (news-item-v1)
<!-- SPEC:INTERVIEW-SLOT id=news-item-dataclass
필드 확정: title, url(멱등 키), source, published_at, category(6), time_axis(3),
direction∈{up,neutral,down}, magnitude∈{1,2,3}, confidence(0~100),
affected{scope∈{market,sector,ticker}, refs[]}, labeled_by∈{llm,manual,rss_raw}, collected_at.
dataclass + to_dict(JSON round-trip). 기존 collectors/news_rss.py NewsItem 을 확장(라벨 필드 추가, 하위호환). -->

### NewsDigest 계약 (news-digest-v1) + tone tilt 매트릭스
<!-- SPEC:INTERVIEW-SLOT id=news-digest-dataclass
tone 5단(bearish/lean_bearish/neutral/lean_bullish/bullish) = category_counts 의 방향 가중 카운트로 결정론 매핑(임계 config).
catalyst_tilt{direction∈{up,neutral,down}, strength∈{weak,mid,strong}} = scope=ticker/sector 시 magnitude·confidence·시간축 가중 거친 집계.
top_themes = 동일 테마(키워드/섹터) 클러스터 상위 N. raw_labels = LLM 주입용 분류 텍스트 묶음.
정밀 점수 필드 없음(M4). 빈 입력 graceful → source=empty, tone=neutral. -->

### LLM 분류 (classify_news_items)
<!-- SPEC:INTERVIEW-SLOT id=classify-llm
collectors/anchors.py select_anchors_via_llm / market_view cross_check mirror:
Gemini FAST(flash-lite) 또는 BALANCED(flash), thinking_budget=0, max_tokens≥512(JSON 잘림 방지 [[feedback_gemini_thinking_budget_json]]),
llm_call_cache type='news_classify' cache_key="url" TTL 영속(뉴스 라벨 불변). TESTING=1 mock 강제.
본문 grounding 강제(제목·본문 내 단어만, 학습데이터 환각 차단 — persona 기존 룰 계승). -->

### catalyst_tilt → buy_score N 블렌드 (config 외부화)
<!-- SPEC:INTERVIEW-SLOT id=n-axis-blend
buy_score_inputs.py N축: n_final = blend(n_high_proximity(52주 신고가), catalyst_tilt) — config 가중(예: 신고가 0.6 / 촉매 0.4).
뉴스 없으면 기존 신고가만(graceful, 현 동작 보존). catalyst_tilt advisory — 원시 라벨 reasons 동반.
시장 전반 뉴스는 N 에 안 들어감(market_view 영역). -->

### 시간축 라벨 판단 기준 (canon doctrine N1~N5)
<!-- SPEC:INTERVIEW-SLOT id=time-axis-doctrine
ephemeral_shock/short_theme/structural_trend 가르는 기준 명제화(canon/news/01).
단발 후 단기·장기 분기 규칙. 카테고리×시간축 디폴트 매핑(예: geopolitics→대개 ephemeral_shock, macro_policy→structural_trend 경향).
사용자 시간축 판단 직관을 canon 으로 흡수(자료 0 시드라 초안은 Claude 시드 + 사용자 확인). -->

## 다른 팀/스키마 영향
- **DB 스키마 추가 2**: `news_source_items`(레거시 브리핑 `news_items` 충돌로 개명), `news_digest_snapshot`(v11 신규 테이블, ALTER 불필요).
- **collectors/news_rss.py**: `NewsItem` 라벨 필드 확장(하위호환 — 브리핑 collect_news 는 라벨 없이도 동작) + `RssNewsSource` 래퍼. 브리핑 파이프라인 *동작 불변*.
- **collectors/market_view.py**: digest 내러티브 흡수(추가 입력, 기존 결정론 로직과 공존 — one_liner 머리·뉴스 톤 본문).
- **collectors/buy_score_inputs.py**: N축 블렌드(뉴스 없으면 현 동작 보존, graceful).
- **news_curator manifest/persona**: SLOT S2(자료원 미결정) 클로즈 — ANALYST-PERSONAS-001 의사결정 종료.
- 전략가/Track A·B 직접 영향 없음(buy_score 경유 간접). team_outputs publish 는 SLOT.

## 검증
- 단위: `tests/test_news_source.py` — 어댑터(RssNewsSource fetch mock / ManualNewsSource 파싱) · classify LLM **mock**(라벨 스키마·캐싱 멱등·thinking_budget=0) · build_news_digest 결정론(고정 라벨→고정 tone·counts·top_themes·catalyst_tilt) · 빈 입력 graceful(source=empty, tone=neutral) · tone 5단 매트릭스 · catalyst_tilt→N 블렌드(뉴스 유무 graceful) · DB round-trip(news_items url 멱등 + digest scope|date 멱등) · market_view 흡수 · analyst hook. **LLM 실호출 금지(TESTING=1 mock)**.
- 통합(라이브): `_news_digest_probe.py` → RSS 수집 → 분류 → digest. production-chat "오늘 뉴스 톤?" → news_curator 가 digest 인용 해석. market_view one_liner 에 뉴스 톤 반영 확인. 종목 질의 시 buy_score N 에 촉매 블렌드 확인.
- 회귀: 기존 전체 passed 유지 + validate 0 errors + **브리핑 collect_news 동작 불변**(NewsItem 하위호환).
- 단계 지도: `scripts/project_status.py` → LEFT-BRAIN 트리에 NEWS-SOURCE-001 draft 등재(미작성→draft), 구현 후 implementing/verified.

## 완료 정의 (이 SPEC)
RSS+수동 자료원으로 뉴스가 분류·시간축 라벨링되어 `news_items` 에 영속 누적 + `build_news_digest` 단일 산출물이 market_view 내러티브(시장 전반)·buy_score N 촉매(종목)·news_curator 해석에 동시에 흐른다 + news_curator 가 "자료원 미결정 거부" 를 벗어나 digest 기반 분류·해석 + 회귀/validate 통과 + 브리핑 동작 불변. (UX/UI 어드민·Perplexity·유튜브 자동·RAG·일일 cron·정밀 점수는 후속/의도적 제외.)

## 면담 5라운드 결단 요약 (영구 권위, 2026-06-07 spec-interview)
- **R1 본질**: 9번째 0시드 지식부(뉴스부) 자료층. market_view 내러티브 + buy_score N 촉매 + news_curator 활성. 브리핑 일회성 RSS 의 *영속·분류·다중소비자 승격*(중복 X).
- **R2 경계**: MVP=데이터 백본 우선(DB+분류+수동/유튜브+소비 배선). 자동수집=RssNewsSource 1차 라이브. UX/UI·Perplexity·유튜브자동·RAG·cron=SLOT.
- **R3 I/O**: 자료원=NewsSource 어댑터(RSS 흡수). 카테고리 6. 시간축 3. 소비=build_news_digest 단일 산출물.
- **R4 숨은 의도**: DB=사실/canon=분류룰(얕게). 뉴스 정밀 점수화는 정직하지 않다 → 거친 tilt+내러티브. N축은 CAN SLIM New(신고가+뉴스 촉매)의 뉴스 절반.
- **R5 우선순위/제약**: RSS 무료 + LLM 분류 Gemini(thinking_budget=0)·캐싱 멱등. 일단위 배치 충분(user_want_spec). 크로스플랫폼 pathlib. 브리핑 동작 불변 필수.
