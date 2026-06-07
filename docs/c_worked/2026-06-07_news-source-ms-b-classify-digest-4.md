---
date: 2026-06-07
topic: NEWS-SOURCE-001 MS-B 구현 (뉴스 LLM 분류 + 결정론 digest + canon N1~N5)
status: completed
plan_file: C:\Users\HOME\.claude\plans\drifting-sniffing-token.md
---

# 2026-06-07 · NEWS-SOURCE-001 MS-B (분류 + digest)

## 배경
MS-A(데이터 백본: 어댑터 + DB 2테이블)가 라벨 골격만 깔아둔 상태(전부 Optional, `labeled_by='rss_raw'`). MS-B = 그 라벨을 채우고(LLM) 거친 집계 규칙을 코드로 박는 **두뇌층**. 소비 배선(MS-C) 전 마지막 비-소비 단위라 회귀 안전. **핵심 판단 유지**(SPEC M4): 개별 뉴스 *판단*=LLM / *집계*=결정론, 정밀 0~10 점수는 폐기하고 거친 5단 tone tilt + raw 내러티브만 산출([[feedback_score_collapse_advisory]] 일관).

## 한 일
- `collectors/news_source.py` — 3 핵심 함수 + 헬퍼 추가:
  - `classify_news_items()` — 개별 뉴스 LLM 라벨(`anchors.py::select_anchors_via_llm` mirror): provider=gemini 명시·`thinking_budget=0`·`max_tokens=512`·`llm_call_cache type='news_classify'` url 멱등(TTL 365일=사실상 영속)·검증 실패/예외 시 기존 라벨 보존(graceful)·수동 affected 보존·`asyncio.gather` 병렬.
  - `build_news_digest(date, *, ticker/sector)` — 결정론 집계: tone 5단(`Σ부호×magnitude×conf/Σweight`→[-1,1]→config 임계)·category_counts·top_themes(affected_ref/category 클러스터)·catalyst_tilt(방향+강도)·raw_labels. 빈 입력→`source='empty'`. scope|date 멱등 영속.
  - `render_news_digest_md()` — `[8] 뉴스 종합` 주입 블록(`render_market_view_md` house style + 한국어 라벨 + M4 "정밀 점수 아님" 명시). `news_digest_metadata()` (MS-C hook용) 동반.
- `config/news_source.yaml` — `classify`(provider/model/max_tokens/cache_ttl) + `digest`(tone_bands·catalyst_strength·top_themes_n·lookback) 블록 외부화(하드코딩 0).
- `knowledge/canon/news/01-classification-doctrine.md` 신규 — **N1~N5**(카테고리6·시간축3·방향강도확신·범위귀속·tone 집계 철학). 9번째 0시드 지식부 첫 자료.
- `knowledge/canon/news/_category.yaml` 신규 — category_id=news, target_analysts=[news_curator].
- `docs/specs/NEWS-SOURCE-001-news-source.md` — 계약 테이블명 `news_items`→`news_source_items` 3곳 정정 + status는 implementing 유지(MS-C/D 남음).
- `tests/test_news_source.py` — 13→29(classify mock·캐시 히트·graceful·수동 보존 / digest tone 5단·counts·scope·날짜 필터·멱등 / render). TESTING=1 강제 + `call_llm` patch(anchors mirror).

## 검증 결과
- ✅ `tests/test_news_source.py` — 29 passed (13 MS-A + 16 MS-B)
- ✅ 전체 회귀 — **933 passed**(917+16), 1 warning(기존 yfinance, 무관)
- ✅ `scripts/validate.py` — 0 errors(teams/registry.yaml 1 warning=기존 무해)
- ✅ `scripts/project_status.py` — NEWS-SOURCE-001 `🔨 implementing` ACTIVE, drift 없음(미연결 14개 불변)

## 의도적으로 안 한 것
- **MS-C 소비 배선** — market_view 흡수·buy_score N 블렌드(`:221` SLOT)·news_curator hook(`reads_news_digest`)·persona SLOT S2 클로즈. digest를 아직 어디에도 안 흘림(회귀 안전 경계).
- **MS-D 라이브** — `_news_digest_probe.py` 실 Gemini 분류 + production-chat 검증.
- **top_themes 키워드 NLP 클러스터** — MVP는 affected_ref/category 키 클러스터(정직, 문서화). 의미 클러스터는 후속.

## 기술 부채/미완 (자가 발견)
- ⚠️ canon `news/01-...md`·`_category.yaml`이 dept 직하(서브카테고리 폴더 없음) — SPEC generates 경로 그대로. 타 dept는 `<dept>/<category>/` 구조. load_shared_canon은 rglob라 로드는 정상이나 구조 비대칭. MS-C에서 news_curator 주입 검증 시 확인.
- catalyst_tilt→buy_score N 블렌드 가중(`config digest`에 미추가) — MS-C에서 신고가 0.6/촉매 0.4 류 추가 필요.

## 다음에 이어서 할 작업 (우선순위)
1. **NEWS-SOURCE-001 MS-C** (소비 배선) — `run_analyst._maybe_build_news_digest_md`(+`reads_news_digest` flag, `_maybe_build_market_view_md` mirror @757/96/141) + `compose.build_pipeline_prompt(news_digest_md=...)` [8] 블록 + market_view 흡수(시장 scope tone·top_themes 내러티브) + buy_score N 블렌드(`buy_score_inputs.py:221` SLOT) + news_curator persona/manifest SLOT S2 클로즈. 끝나면 왼쪽 뇌 3/4.
2. **NEWS-SOURCE-001 MS-D** (라이브) — `scripts/_news_digest_probe.py`(`_market_view_probe.py` mirror) 실 Gemini 분류 + production-chat "오늘 뉴스 톤?" 검증 + 회귀. 끝나면 LB-MS3 완료 → SPEC verified.
3. **dev cron 미작동 근본 해소** (운영 부채) — 18:05 적재가 서버 미상주 시 미발동. 수동 트리거 endpoint(`POST /api/admin/refresh-snapshots` 류) 검토. NEWS 흐름과 직교, 라이브 누적 실 전제.

## 맥락 재진입 힌트
- classify는 url 멱등 캐시(type='news_classify')라 재실행 시 LLM 재호출 0. provider=gemini 명시(Anthropic 미결제 [[project_anthropic_unbilled_gemini_only]]).
- digest tone = `_net_tilt`(Σ부호가중/Σ가중)→`_tone_from_net`(config tone_bands). catalyst strength=`_catalyst_strength`(|net|→config). 같은 라벨→같은 산출(백테스팅 재현).
- MS-C hook 패턴: `run_analyst.py::_maybe_build_market_view_md`(757)/`reads_market_view`(96,141)/stream(840,852). `news_digest_metadata()` 이미 준비됨.
- 테이블명 = `news_source_items`(레거시 `news_items` 충돌). digest=`news_digest_snapshot`.

## 커밋 상태
- feat 코드(news_source/config/spec/tests + canon 2파일) + docs wrap-up → main 직접 + push (이 wrap-up 후반 수행).
