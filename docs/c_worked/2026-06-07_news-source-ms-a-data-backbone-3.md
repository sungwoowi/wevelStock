---
date: 2026-06-07
topic: NEWS-SOURCE-001 MS-A 구현 (뉴스부 데이터 백본 — 어댑터 + DB 2테이블)
status: partial
plan_file: C:\Users\HOME\.claude\plans\generic-forging-lighthouse.md
---

# 2026-06-07 · NEWS-SOURCE-001 MS-A (데이터 백본)

## 배경
직전 세션이 NEWS-SOURCE-001 SPEC을 frozen(draft)했고, 본 세션은 **그 구현 본체에 착수**. SPEC이 멀티세션 규모라 4 마일스톤(A 데이터 백본 / B 분류·digest / C 소비 배선 / D 라이브 검증)으로 쪼갰고, **본 세션은 MS-A만**(사용자 선택). MS-A = LLM·소비자 없는 순수 데이터·어댑터·DB 층 → 회귀 안전. **핵심 판단**: 개별 뉴스 판단=LLM(MS-B)·집계=결정론, 정밀점수 폐기(SPEC M4)는 유지하되 MS-A는 그 골격만.

## 한 일
- `collectors/news_rss.py` — `NewsItem`에 라벨 9필드 추가(category/time_axis/direction/magnitude/confidence/affected_scope/affected_refs/labeled_by/collected_at + body, 전부 Optional). `to_dict()`는 기존 4키 유지(브리핑 하위호환), `to_record()`/`from_record()` 신규(affected 중첩 round-trip). `fetch_news_items()` 추출 → `fetch_news()`는 dict 래퍼(동작 불변).
- `collectors/news_source.py` 신규 — config 로더(score_inputs 패턴 mirror) + `NewsSource` Protocol + `RssNewsSource`(fetch_news_items 흡수, labeled_by='rss_raw') + `ManualNewsSource`(본문·유튜브 요약, 결측 skip) + `PerplexityNewsSource`(NotImplemented stub) + `collect_from_sources`(url dedup·소스 graceful) + DB 헬퍼(upsert/get news_source_items, NewsDigest upsert/get).
- `core/db/schema.sql` — v11: `news_source_items`(url 멱등 PK) + `news_digest_snapshot`((scope,date) 멱등 PK) 2테이블 + 인덱스 + schema_version 11.
- `core/db/connection.py` — v11=신규 테이블이라 ALTER 불필요 주석(v10 market_view 동일 방식).
- `config/news_source.yaml` 신규 — 카테고리 6·시간축 3·방향/강도·자료원 토글(rss enabled / manual enabled / perplexity disabled).
- `tests/test_news_source.py` 신규 — 13 테스트(to_dict 하위호환·라벨 기본값·record round-trip·RSS/Manual/Perplexity 어댑터·collect dedup·news_source_items url 멱등·category 필터·digest scope|date 멱등·config 6/3).
- `docs/specs/NEWS-SOURCE-001-news-source.md` — status draft→implementing(2-tier 거버넌스).

## 검증 결과
- ✅ `tests/test_news_source.py` — 13 passed.
- ✅ 전체 회귀 — **917 passed**(904 + 신규 13), 1 warning(기존 yfinance deprecation, 무관). 브리핑 collect_news 동작 불변.
- ✅ `scripts/validate.py` — 0 errors, 1 warning(기존 teams/registry.yaml, 무관).
- ✅ `scripts/project_status.py` — `🔨 NEWS-SOURCE-001 [implementing] ◀ 현재 작업`, ACTIVE 등재, drift 없음.

## 의도적으로 안 한 것
- **MS-B/C/D 전부** — 사용자가 MS-A만 선택. classify_news_items(LLM)·build_news_digest(집계)·render_md·canon doctrine·소비 배선(market_view·buy_score·news_curator)·probe는 다음 세션.

## 기술 부채/미완 (자가 발견)
- ⚠️ **SPEC 계약 테이블명 변경**: SPEC `news-item-v1`은 테이블명을 `news_items`로 명시했으나 **레거시 브리핑 테이블 `news_items`(run_id PK, `pipelines/market_briefing_pre/stages/persist.py:149`가 INSERT)와 충돌**. 신규 영속 학습층을 **`news_source_items`**로 개명(collector 모듈명 일치). 코드 주석에 박음. **SPEC 본문 계약 노트도 정정 필요**(다음 세션 또는 MS-B 시작 시).
- NewsItem `to_dict`(4키)/`to_record`(전체) 이원화 — 브리핑은 to_dict, news DB는 to_record. 혼용 주의.

## 다음에 이어서 할 작업 (우선순위)
1. **NEWS-SOURCE-001 MS-B** — `classify_news_items()`(LLM 라벨, anchors.py mirror: Gemini thinking_budget=0·llm_call_cache type='news_classify'·TESTING=1 mock) + `build_news_digest(date,scope,ticker)` 결정론 집계(tone 5단·category_counts·top_themes·catalyst_tilt) + `render_news_digest_md()` + `knowledge/canon/news/01-classification-doctrine.md`(N1~N5). **시작 시 SPEC 계약 테이블명 `news_source_items`로 정정**.
2. **NEWS-SOURCE-001 MS-C** — 소비 배선: market_view 내러티브 흡수 + buy_score N축 블렌드(`:221` SLOT 해소) + news_curator hook(reads_news_digest) + persona/manifest SLOT S2 클로즈.
3. **NEWS-SOURCE-001 MS-D** — `_news_digest_probe.py` 라이브 + production-chat 검증 + 회귀. 끝나면 LB-MS3 완료(왼쪽 뇌 3/4).

## 맥락 재진입 힌트
- 신규 테이블 = `news_source_items`(NOT news_items — 레거시 충돌). digest = `news_digest_snapshot`.
- 어댑터 흡수: `RssNewsSource`가 `fetch_news_items()` 래핑. 브리핑은 `fetch_news()`(dict) 그대로 → 동작 불변.
- MS-B classify는 `collectors/anchors.py::select_anchors_via_llm` mirror(thinking_budget=0 + llm_call_cache type 분리 + TESTING mock).
- 5점수 배선 패턴(MS-C용): `run_analyst.py::_maybe_build_market_view_md`(757)/`reads_market_view`(96,141)/stream hook(840,994).

## 커밋 상태
- 2 커밋(feat 코드 + docs wrap-up) → main 직접 + push (이 세션 후반 수행).
