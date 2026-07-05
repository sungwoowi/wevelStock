---
date: 2026-07-06
topic: NEWS-EVENT-INTERPRETATION-001 spec-interview + M1 구현 (격상 레인·LLM 해석·장전 cron·전략가 배선)
status: completed
plan_file: C:\Users\HOME\.claude\plans\happy-hatching-firefly.md
---

# 2026-07-06 · NEWS-EVENT-INTERPRETATION-001 M1 — 뉴스 중심 이벤트 격상 + 해석이 전략가에 도달

## 배경
Tier 0(정합) 완료 직후 Tier 1 본진 착수. 07-03 SK하이닉스 재구성이 확정한 사각 = **이벤트 해석 능력 부재**(news_curator dead-end). /spec-interview 로 결단 5건(D1~D5) 확정 후 같은 세션에 M1 TDD 구현. 핵심 판단: **사용자 통찰 2건이 세션 중 설계에 합류** — ① 해석 4축째(시장 실반응·파동 정합 = "뉴스가 원인인가 빌미인가") ② 07:00 장전 브리핑과 결 맞춤(장전 06:40 ingest 신설, 하루 2회 해석).

## 면담 결단 (SPEC D1~D5)
D1 격상=mag3 단건+mag2×다중소스3 / D2 저장=digest 컬럼 확장(신규 테이블 0) / D3 비용=Flash+캐싱+원장 라벨 / D4 MVP=격상+해석+배선(advisory), lifecycle·게이트는 M2 / D5 ingest=장전 06:40+18:05 하루 2회+lookback 폴백.

## 한 일
- `docs/specs/NEWS-EVENT-INTERPRETATION-001-news-event-interpretation.md` — 신규 SPEC (draft→implementing, M1 구현 결과·리플레이 실측 기록)
- `docs/specs/MARKET-CONTEXT-BRAIN-001-market-context-brain.md` — 자식 상태 갱신 + Tier 1 에 4축 통찰 기록
- `collectors/news_source.py` — `detect_elevated_events`(결정론 격상)+`interpret_elevated_events`(4축 해석, 캐시 멱등)+`_detect_and_merge_elevated`(재계산 시 해석 보존 병합)+render 최상단 "⚡ 오늘의 중심 이벤트" 섹션+`render_market_news_digest_md`(lookback 폴백+시점 표기)+캐시 헬퍼 cache_type 일반화
- `core/db/schema.sql` + `core/db/connection.py` — `news_digest_snapshot.elevated_events_json` v20 멱등 ALTER
- `config/news_source.yaml` — elevation/interpretation/premarket 섹션 (임계·tier·시각 외부화)
- `server/schedulers/jobs/news_ingest.py` — 5.5단계(격상 이벤트 해석+재영속) + `_interpretation_market_context`(market_view 재사용, 4축 ⑷ 재료)
- `server/schedulers/jobs/__init__.py` — `news_ingest::premarket` 06:40 평일 cron (misfire 내성)
- `core/strategist/run_strategist.py` — `news_digest_md` 파라미터 (동기+stream, compose [3c] 기존 슬롯 배선 — 진단 ① 상환)
- `core/intent/router.py` — `_today_news_digest_md` + production chat 동기·스트림 배선
- `core/signal/auto_signal.py` — `_market_news_digest_md`(as_of point-in-time) + 전략가 runner 주입
- `pipelines/market_briefing_pre/stages/analyze.py` — 07:00 브리핑 analyze 에 digest md 주입 (아침 텔레그램 체감 산출)
- `agents/strategists/track_a|track_b/manifest.yaml` — reads_analysts 에 news_curator 합류 (dead-end 진단 ④ 해소)
- `tests/test_news_event_interpretation.py` — 신규 28건 RED→GREEN (TDD)
- `tests/test_seed_analysts_v2.py`·`tests/test_track_b_strategist.py`·`tests/intent/test_router.py` — 구 계약(news_curator 배제) 단언을 새 계약으로 갱신 5건
- `scripts/_replay_news_elevation.py` — 메타발 리플레이 (읽기 전용·결정론, --interpret probe)

## 검증 결과 (3겹)
- ✅ 전체 pytest **1395 passed** · 회귀 0 · validate 0 errors
- ✅ **메타발 리플레이**: 06-23~27 미라벨링 204건이 T0-d 백필 lookback 7d 밖에 남은 걸 발견 → lookback 16d 백필(잔량 0) 후 **06-23 발생→06-25~27 확산(mag2×다중소스 레인 발화)→07-02~03 실현** 전 구간 결정론 재현
- ✅ **해석 probe** (07-03, 실 Gemini Flash 1콜 $0.0002): nature=transient_fear + 4축(재탕/괴리/악재순환/빌미 — 분산일 6건·필반 급락·야간선물 실측 인용) + "관망/눌림목 대기" = **사용자 07-03 실판단과 동일 결**. 원장 `news_interpretation` 라벨·캐시 확인

## 의도적으로 안 한 것
- lifecycle memory·게이트(변곡 트리거+entry_posture)·N5 canon 개정 = **M2** (해석 퀄 라이브 관측 후 — 노이즈 매매 차단)
- 클러스터 키 정밀화 (한 거시 이벤트가 Samsung/KOSPI/semiconductor 로 분산 — INTERVIEW-SLOT, max_events_per_day=3 으로 비용 유계)
- 07:00 브리핑 레거시 `collect_news`(news_items run-scoped) 수렴 — SLOT 기록만

## 세션 중 실 비용
- 백필 classify 204콜(Flash, 캐시 영속) + 해석 probe 1콜 $0.0002 — 원장에서 확인 가능

## 다음에 이어서 할 작업 (우선순위)
1. **서버 재시작 + 라이브 관측 (평일)** — Tier 0 게이트 + M1 장전 cron 이 둘 다 라이브 미반영. 월요일 06:40 ingest→07:00 브리핑(중심 이벤트 섹션)→09:35 회차(전략가 사유에 이벤트 인용) 로그 확인 + `/ops/llm-cost` 원장 실측.
2. **M2 — lifecycle + 게이트 + N5 개정** — 해석 퀄 며칠 관측 후: 전일 elevated_events 의 같은 event_key 이전 판정 memory 주입 / structural_inflection 만 is_macro_inflection 제3 트리거+entry_posture 기여 / N5 canon "해석된 격상 이벤트 예외" 단서.
3. **GATE-VISIBILITY UI** — Tier 0 게이트+M1 중심 이벤트를 화면에 (데스크 wait 카드 🛡 배지·시황 태세 칩·뉴스 탭 중심 이벤트 카드). 백엔드 신규 ~0.

## 커밋 상태
- feat(코드+테스트+config+SPEC+스크립트) + docs(wrap-up) 2 커밋, main push (아래 wrap-up 수행).
