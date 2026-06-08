---
date: 2026-06-09
topic: 뉴스 종목/섹터 scope digest 다일 누적 (affected_refs 정규화 + cron scope 루프)
status: completed
plan_file: C:\Users\HOME\.claude\plans\mossy-sleeping-crescent.md
---

# 2026-06-09 · 뉴스 종목/섹터 scope digest 다일 누적

## 배경
왼쪽 뇌 4/4 완성 후 RESUME Top 3 #3(뉴스 종목/섹터 scope 적재) 수행. 일일 cron 이
`market` scope 1개만 적재 → 종목·섹터 뉴스 다일 윈도우 누적 불가. **핵심 결함**: classify
LLM 이 `affected_refs` 를 자유 텍스트("삼성전자")로 반환하는데 universe ticker 는 6자리 KRX
코드("005930") → `"005930" in ["삼성전자"]=False` **조용한 누락**(종목 scope·on-demand
buy_score N 모두). **핵심 판단**: classify 시 종목명→코드 정규화·저장(read-time 아님)으로
데이터를 깨끗이 박고, digest 빌드는 결정론(추가 LLM 0)이라 scope 루프만 추가.

## 한 일
- `collectors/news_source.py` — affected_refs 정규화 레이어: `_norm_key`/`_build_sector_map`
  (DEFAULT_TRACKED_ETFS 풀네임+stem+ETF코드)/`_normalize_ticker_ref`(6자리 통과·name→code)/
  `_normalize_sector_ref`/`_normalize_affected_refs`(scope 힌트·미스 원본보존·dedup). classify
  3함수(`classify_news_items`/`_classify_one`/`_apply_classification`)에 `name_code_map`/
  `sector_map` 전파(수동 refs 보존 가드 안에서만 정규화). config getter 2개. **upsert quirk
  제거** — 빈 집계를 'computed'로 덮던 `"computed" if source=="empty"` → `digest.source` 정직 저장.
- `server/schedulers/jobs/news_ingest.py` — `_build_universe_and_name_map()`(KIS 거래대금 상위
  + 하드코딩 `KR_NAME_TO_TICKER` 병합) + 다중 scope 루프(market 1 + universe N + 섹터 15, 각
  독립 격리, market 하위호환 키 유지, universe 실패 fallback, persist_empty 토글).
- `config/news_source.yaml` — `digest.scope_universe_limit: 50` / `persist_empty_scopes: true`.
- `tests/test_news_source.py` — 정규화 11케이스(name→code/6자리통과/미매칭보존/섹터stem/dedup/
  scope=None/classify정규화/**ticker scope 매칭 회귀=핵심 결함**/빈 source 정직저장).
- `tests/test_news_ingest.py` — 루프 9케이스 재작성(scope 호출수/실패격리/name_code_map 수신/
  빈 scope persist/full_flow 하위호환/universe fetch fallback).

## 검증 결과
- ✅ `TESTING=1 pytest` 전체 **989 passed** (기존 966 + 신규 23), 회귀 0.
- ✅ 라이브 end-to-end (`run_news_ingest()`): scopes_persisted=66(market 1+universe 50+섹터 15),
  failures=0, ~28s. universe tickers=50/names=64.
- ✅ **멱등**: 재실행 → digest row 66 불변, 중복 scope 0.
- ✅ **정규화 실발화**: 실 뉴스 "Broadcom-Linked AI Selloff Hits Samsung, SK Hynix" →
  affected_refs `['semiconductor','005930','000660']`. 정규화 전이면 누락됐을 케이스. 미국
  티커(NVDA/DELL)는 KR 맵에 없어 원본 보존(정확).

## 의도적으로 안 한 것
- 마스터 테이블 `ticker_name_master` 신설 — injectable map 인터페이스만 열어두고 SLOT. 1차는
  거래대금 상위 50 + 하드코딩 ~30종 map 으로 충분(top-50 밖은 미스 시 원본 보존).
- `get_news_digest` 의 'db' 마커 변경 — 캐시 출처 마커는 의도적(소비자는 content 로 empty 구분).

## 기술 부채/미완
- **gemini transient 503 retry 미배선** — 라이브 재실행 중 1건 503(per-item graceful 49/50
  처리, 크래시 0). `provider="gemini"` 명시 경로에 retry 없음. RESUME Top 2 근거 강화.
- **뉴스 RSS 미국 편중** — 오늘 Yahoo/CNBC 위주라 한국 종목 scope 대부분 빈 누적. Google News
  한국 쿼리 보강 또는 한국 소스 추가는 SLOT(누적 다일이면 자연 채워짐).
- dev DB 기존 행 일부 'computed'(quirk 시절) — 다음 cron ON CONFLICT REPLACE 로 자연 교정.

## 다음에 이어서 할 작업 (우선순위)
1. **오른쪽 뇌 roadmap 착수 결정** — 북극성 미착수 절반(비중 Layer4→가상매매→코스피 대비 채점→
   복리). `RIGHT-BRAIN-*` roadmap SPEC 작성 + 첫 자식(Layer4 비중 vs 채점 루프 vs 가상매매)
   우선순위 인터뷰. 사용자 사인오프 필요.
2. **gemini transient 503 retry 배선** — `core/llm/client.py` provider 명시 경로에 503 1~2회
   재시도(KIS rate limiter 패턴 mirror). production-chat·analyst·news classify 노출.
3. **뉴스 한국 소스 보강 (선택)** — RSS Google News 한국 쿼리/한국 매체 추가로 종목 scope 실누적
   밀도 향상. config sources.rss.queries.

## 커밋 상태
- 코드(feat) + wrap-up docs(docs) 2 커밋 분리 예정 → main 직접 + push.
- `.claude/scheduled_tasks.lock`(untracked) 무관 산출물 → 커밋 제외.
