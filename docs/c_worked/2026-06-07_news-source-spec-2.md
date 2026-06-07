---
date: 2026-06-07
topic: NEWS-SOURCE-001 SPEC 작성 (뉴스부 자료층, LB-MS3) + wrap-up 커밋·푸시 기본화
status: completed
plan_file: C:\Users\HOME\.claude\plans\toasty-juggling-moore.md
---

# 2026-06-07 · NEWS-SOURCE-001 SPEC (뉴스부 자료층, LB-MS3)

## 배경
왼쪽 뇌(LEFT-BRAIN-COMPLETION-001)의 **9번째이자 마지막 0시드 지식부 = 뉴스부**. `/resume`에서 LB-MS3을 골라 `/spec-interview`로 SPEC을 작성. **핵심 판단**: 뉴스를 정밀 점수(0~10)로 누르는 건 정직하지 않다(상황의존·비선형·희소충격) → 개별 뉴스 *판단*은 LLM, *집계*만 결정론(카운트·거친 tilt). 세션 중 사용자가 텔레그램 "시나리오+뉴스" 알림을 물어 **이미 도는 브리핑 RSS 수집을 발견** → 중복 구현 회피, 어댑터로 흡수하는 *승격* 구조로 재설계.

## 한 일
- `docs/specs/NEWS-SOURCE-001-news-source.md` — 신규 SPEC (draft). frontmatter(generates 6·modifies 9·depends_on 5·contracts 2) + 7 핵심 결단 + INTERVIEW-SLOT 마커 6개 + 5라운드 결단 요약. parent=LEFT-BRAIN-COMPLETION-001.
- `.claude/commands/wrap-up.md` — Step 6에 **push 기본 동작(C)** 추가 + 제목/Step 7 요약 갱신. 사용자 상시 선호(커밋·푸시 한 번에) 반영. force 금지·실패 시 중단 안전장치.
- (메모리) `project_news_source_decision` SPEC draft 반영 / `project_state` LB-MS3 SPEC 착수 / `project_score_inputs_gap` N축=CAN SLIM New 정밀화 주석.

## 면담 7 결단 (영구 권위)
- **M1** 기존 RSS(`fetch_news`)→`RssNewsSource` 어댑터 흡수(중복 X, 승격). 수동/유튜브 별 구현체, Perplexity drop-in(이 환경 MCP 미연결 확인).
- **M2** DB=사실(`news_items`)/canon=분류룰(얕게, 명제 N1~N5). RAG SLOT.
- **M3** 카테고리 6 = 거시·산업·지정학·정치·기업이벤트 + **시장심리**(버블/조정 내러티브).
- **M4** 정밀 점수 폐기 → 거친 tilt(5단) + 내러티브. 집계만 결정론, 판단은 LLM. advisory.
- **M5** `build_news_digest(date[, ticker])` 단일 산출물 → market_view·buy_score·news_curator 모두 read.
- **M6** 시간축 3단(단발충격/단기테마/지속흐름, 가변).
- **M7** *(코드 발견)* buy_score **N축 = CAN SLIM "New"(신고가+신제품/뉴스 촉매)** — 52주 신고가만 라이브, 코드가 직접 `SLOT: NEWS-SOURCE-001` 표시한 뉴스 절반을 본 SPEC이 메움. **종목 뉴스→buy_score N / 시장 뉴스→market_view** 분리.

## 검증 결과
- ✅ `scripts/project_status.py` — LEFT-BRAIN 트리에 `□ NEWS-SOURCE-001 [draft]` 등재(미작성 1=INFRA-US-MACRO만 남음). drift 없음.
- ✅ `scripts/validate.py` — 0 errors, 1 warning(기존 teams/registry.yaml, 무관).

## 의도적으로 안 한 것
- **코드 구현 전부** — SPEC 작성 세션. 어댑터·분류 파이프라인·DB 2테이블·digest·3소비자 배선은 별도 구현 세션. (generates/modifies는 INTERVIEW-SLOT으로 위치만.)
- news_curator manifest/persona 수정 — `modifies` 대상이나 구현 시 손댐.

## 기술 부채/미완
- **buy_score "N 뉴스부" 모호함** (자가 발견) — RESUME/메모리는 "N=뉴스부"로 서술했으나 코드상 N=CAN SLIM New(신고가+촉매). M7에서 정밀화·SPEC에 박음. 메모리도 정정.
- NEWS-SOURCE-001 구현 자체가 큰 다음 작업(어댑터→분류→DB→digest→소비 배선).

## 다음에 이어서 할 작업 (우선순위)
1. **NEWS-SOURCE-001 구현 착수** — SPEC INTERVIEW-SLOT 6개 채우며: NewsSource 어댑터(RSS 흡수)+`classify_news_items`(LLM mock)+`news_items`/`news_digest_snapshot` 2테이블+`build_news_digest`+3소비자 배선(market_view 흡수·buy_score N 블렌드·news_curator hook). 멀티세션. LEFT-BRAIN LB-MS3 본체.
2. **INFRA-US-MACRO-SNAPSHOT-001 SPEC 착수** — 미장 야간(SPX/NDX/VIX/DXY/US10Y) entry_posture 가산. MARKET-VIEW가 `us-macro-hook` SLOT 확보. LEFT-BRAIN 마지막 자식(이거 끝나면 왼쪽 뇌 4/4).
3. **dev cron 미작동 근본 해소** — 서버 18:05 미상주 → 적재 전부 미발동. 순환매·universe·뉴스 일일 누적의 실 전제. 수동 트리거 endpoint or 서버 상주.

## 맥락 재진입 힌트
- SPEC의 핵심 = "정밀 점수 폐기, 거친 tilt + 내러티브"(M4) + "단일 build_news_digest 소스"(M5) + "종목뉴스→N / 시장뉴스→market_view"(M7). 구현 시 5점수 `build_*`/`_maybe_build_*_md`/`reads_*` 패턴(run_analyst.py:90~) + market_view DB-first 멱등(schema v10) mirror.
- 기존 `collectors/news_rss.py`(fetch_news/NewsItem) + `pipelines/market_briefing_pre/stages/collect_news.py`가 RSS 자산. 브리핑 동작 불변 보존(NewsItem 하위호환).

## 커밋 상태
- `docs: wrap-up 2026-06-07 NEWS-SOURCE-001 SPEC + wrap-up push 기본화` — main 직접 커밋 + push (이 세션 후반 수행).
