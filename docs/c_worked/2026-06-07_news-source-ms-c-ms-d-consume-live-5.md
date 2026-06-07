---
date: 2026-06-07
topic: NEWS-SOURCE-001 MS-C 소비 배선(C1·C2·C3) + MS-D 라이브 검증 → SPEC verified (LB-MS3 완료)
status: completed
plan_file: C:\Users\HOME\.claude\plans\drifting-sniffing-token.md
---

# 2026-06-07 · NEWS-SOURCE-001 MS-C + MS-D (소비 배선 + 라이브) → verified

## 배경
MS-B가 digest를 *산출·영속*까지만 했고 어디에도 안 흘렀다. MS-C = digest를 3 소비처(news_curator·market_view·buy_score N)로 흘려 9번째 지식부를 *활성화*, MS-D = 실 RSS+Gemini end-to-end 검증. **핵심 판단**: 뉴스부는 재료(digest)만 만들고, 소비는 분석/판단부서가 한다(종목 뉴스→buy_score N / 시장 뉴스→market_view, M7). digest 단일 산출물을 각 소비자가 read(파이프라인 간 import 금지 원칙 일관).

## 한 일
### MS-C1 — news_curator 활성화
- `core/inference/run_analyst.py` — `AnalystSpec.reads_news_digest` + `_maybe_build_news_digest_md` hook(`_maybe_build_market_view_md` mirror, target_ticker scope, graceful) + run_analyst·run_analyst_stream 양쪽 배선 + metadata 병합.
- `core/knowledge/compose.py` — `build_pipeline_prompt(news_digest_md=...)` + `[3c] 뉴스 종합` 블록(시장관 [3b] mirror, 뒤 위치).
- `agents/analysts/news_curator/{manifest.yaml,persona.md}` — `reads_news_digest:true` + `canon_categories:[news]` + 거부→digest 기반 해석 + cited v3.2(N1~N5) + 카테고리6/시간축3 정정 + M4 1줄. SLOT S2 클로즈.
- `tests/test_seed_analysts_v2.py` — stale SLOT S2 테스트 2개 갱신(canon=[news], reads_news_digest=True, "자료원 미결정" 부재).

### MS-C2 — market_view 흡수
- `collectors/market_view.py` — `synthesize_market_view(news_digest=...)` + 시장 scope tone·top_themes를 reasons + one_liner에 흡수(`_NEWS_TONE_KR`). `build_market_view`가 digest를 `persist=False` fetch(graceful). 빈/None 생략.

### MS-C3 — buy_score N 블렌드
- `collectors/buy_score_inputs.py` — `_news_catalyst_to_score` + `_blend_news_catalyst`. N축 = 52주 신고가 ⨯ 종목 scope catalyst_tilt 가중(config). 뉴스 없으면 신고가만(보존). `:221` SLOT 해소.
- `config/news_source.yaml` — `digest.n_axis_blend`(high 0.6/news 0.4 + tilt→score 매핑) 외부화.

### MS-D — 라이브 + verified
- `scripts/_news_digest_probe.py` 신규 — capability 체크 + 실 RSS 수집 + 실 Gemini 분류 + market/ticker digest + N 블렌드 실증(`_market_view_probe` mirror).
- `docs/specs/NEWS-SOURCE-001` status implementing→**verified** + 구현 완료(MS-A~D) 섹션.

## 검증 결과
- ✅ 전체 회귀 **944 passed**(937+7 C2/C3) / validate 0 errors / project_status `✅ NEWS-SOURCE-001 [verified]` · LEFT-BRAIN **3/4(75%)**.
- ✅ **MS-D 라이브 probe** — 실 RSS 50건 + 실 Gemini 분류 50건(AI셀오프=down3/conf95 등 정확) → market digest(tone neutral, 시장심리 8↑/15↓·산업 6↑/0↓·기업 8↑/1↓) → 005930 ticker scope catalyst_tilt **down/strong** → N 7.0→**4.5** 블렌드.
- ✅ **news_curator 실 대화 검증**(임시 demo, 실행 후 삭제) — "오늘 뉴스 톤?" → is_mock=False/gemini-2.5-flash 실답변: "혼재 — 시장심리·거시 악재 우세, 산업·기업 호재" + `cited:[N5]`, digest 카운트 정확 반영(환각 0), SLOT S2 거부 안 함.

## 의도적으로 안 한 것
- C2/C3는 사용자 "전부 진행" 선택. 별도 분리 안 함.
- UX/UI 어드민·Perplexity MCP·유튜브 자동·뉴스 RAG·일일 적재 cron 배선·브리핑 collect_news→news DB 통합 = SLOT(후속).

## 기술 부채/미완 (자가 발견)
- ⚠️ **gemini transient 503 + provider 명시 시 fallback 없음**: `provider="gemini"` 명시 호출은 503에서 죽음(probe·demo 첫 시도 503→재시도 성공). production-chat 경로에 retry 필요(기존 메모리 백로그 재확인).
- top_themes 클러스터 키가 category명·affected_ref 혼재(예: "market_sentiment"·"semiconductor"·"BRK.A") — _theme_key 설계상 정상이나, 친화 라벨링은 후속 다듬기 여지.
- probe가 dev DB에 실 뉴스 50건 분류 적재(영속) — 학습층 누적이라 의도적 보존(삭제 안 함).

## 다음에 이어서 할 작업 (우선순위)
1. **INFRA-US-MACRO-SNAPSHOT-001 SPEC 작성** — 왼쪽 뇌 마지막 조각(LEFT-BRAIN 3/4→4/4). 미장 매크로(yfinance/FRED: 달러인덱스·10년물·VIX·나스닥·필반지수). 아직 SPEC 미작성(draft 신설 → `/spec-interview`).
2. **dev cron 미작동 근본 해소** — 18:05 적재가 서버 미상주 시 미발동. 수동 트리거 endpoint or 상주 운영. 순환매·뉴스·universe 다일 누적의 실 전제.
3. **gemini 503 retry 배선** — production-chat·analyst 경로 `provider` 명시 호출에 transient 503 재시도(작은 부채, MS-D에서 재확인).

## 커밋 상태
- feat 코드(run_analyst/compose/market_view/buy_score_inputs/config/persona/manifest + probe + SPEC verified + tests) + docs wrap-up → main 직접 + push (이 wrap-up 후반).
