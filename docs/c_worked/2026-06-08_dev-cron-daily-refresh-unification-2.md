---
date: 2026-06-08
topic: dev cron 미작동 부채 해소 — 일일 적재 통합(CLI·endpoint·cron 단일 호출점) + 뉴스 cron 합류
status: completed
plan_file: C:\Users\HOME\.claude\plans\async-munching-pillow.md
---

# 2026-06-08 · dev cron 미작동 해소 — 일일 적재 3-surface 통합

## 배경
왼쪽 뇌 4/4 완성 후 RESUME Top 3 중 #2(운영 부채) 착수. APScheduler 가 FastAPI lifespan
내부에만 살아 있어 dev 머신 서버 미상주 시 18:05 허브가 미발동 → us_macro/sector_rs/chart/뉴스
다일 누적이 막혀 순환매·universe ramp 의 실 전제가 깨짐. 추가로 **뉴스 적재는 함수만 있고 cron
미등록**이었다. **핵심 판단**: cron·CLI·endpoint **세 surface 가 동일한 `run_daily_refresh()`
단일 호출점을 공유** + 뉴스를 허브에 합류. 모든 refresh 가 ON CONFLICT REPLACE 멱등이라 안전.
(사용자 선택: CLI 원샷 + endpoint 둘 다 + 뉴스 합류)

## 한 일
- `server/schedulers/jobs/news_ingest.py` — 신규. `run_news_ingest(date=None)`: collect(RSS)→upsert(raw)→classify(LLM gemini)→upsert(labeled)→build_news_digest. 단계별 try/except 격리, 결과 dict.
- `server/schedulers/jobs/daily_refresh.py` — 신규. `run_daily_refresh()`: run_snapshot_macro_refresh() + run_news_ingest() 순차·격리·집계. 세 surface 단일 호출점.
- `server/schedulers/jobs/__init__.py` — 18:05 cron 등록을 `run_snapshot_macro_refresh`→`run_daily_refresh`(id `infra::daily_refresh`)로 교체 + import/export 갱신.
- `server/api/infra.py` — 신규. `POST /api/infra/refresh-snapshots` → run_daily_refresh 위임(얇게). 멱등.
- `server/main.py` — infra 라우터 등록(`/api`, tags=infra).
- `justfile` — `refresh-daily` 레시피 신규(서버 없이 1회 실행). `refresh-snapshot-macro` 주석에 "macro 만" 명시.
- `tests/test_news_ingest.py`(4) + `tests/test_daily_refresh.py`(3) + `tests/test_infra_endpoint.py`(1) — collector/서브잡/endpoint mock, 흐름·집계·격리 검증.

## 검증 결과
- ✅ 신규 8 + 전체 회귀 **974 passed**(966→+8) / `validate.py` 0 errors(기존 무관 warning 1).
- ✅ **라이브 `just refresh-daily` ×2** — 실 RSS 50건 + 실 Gemini classify 50건 + us_macro risk_off(필반 -10.26%·VIX +39.68%) + market_view defensive 흡수. 34.99s→22.13s(분류 캐시 hit 멱등). 2회차 one_liner 에 "뉴스 약세 기울기" 신규(첫 회 digest read 흡수 = 부서 간 DB read 실증).
- ✅ **라이브 endpoint** — `POST /api/infra/refresh-snapshots` 200(이미 떠 있던 서버 PID 25060), 18.07s 집계 JSON. 세 surface 전부 작동.

## 의도적으로 안 한 것
- 서버 상주 운영(systemd/Task Scheduler 등록) — Windows 작업 스케줄러에 `just refresh-daily` 거는 건 **사용자 OS 액션**(코드 아님). plan 말미 안내만.
- 신규 SPEC — feature 아닌 운영 배선 부채 fix. macro 트리거=INFRA-SNAPSHOT-EXTEND 운영 보강, 뉴스 cron=NEWS-SOURCE-001 명시 SLOT 충족(기존 generates/패턴 내).
- 브리핑 collect_news 통합 / 장전 double-fetch dedupe / KOSDAQ — 전부 기존 SLOT 유지.

## 기술 부채/미완
- **Windows 작업 스케줄러 등록은 사용자 수동** — `just refresh-daily` 평일 18:05 트리거 미등록 시 여전히 누적 안 됨(코드는 준비 완료).
- gemini transient 503 retry(RESUME Top 3 #3, 미착수) / regime run간 흔들림 / KIS rate limiter 전역화 — 기존 부채 그대로.

## 다음에 이어서 할 작업 (우선순위)
1. **오른쪽 뇌 roadmap 착수 결정** — 왼쪽 뇌 4/4 + 운영 누적 배관 완성 → `RIGHT-BRAIN-*`(비중 Layer4→가상매매→채점→복리) roadmap SPEC 작성. 첫 자식(Layer4 비중 vs 채점 루프 vs 가상매매) 사용자 우선순위 인터뷰 필요. 북극성 미착수 절반.
2. **gemini transient 503 retry 배선** — `provider="gemini"` 명시 호출 503 fallback 없이 죽음. `core/llm/client.py` 1~2회 재시도. 작은 부채(news_ingest classify·production-chat 경로 노출).
3. **(선택) 뉴스 ticker/sector scope digest 적재** — 현재 일일 cron 은 market scope 만. buy_score N(종목 catalyst_tilt)·섹터 뉴스는 답변 시점 on-demand build. 다일 누적 필요하면 cron 에 종목 루프 추가 검토.

## 커밋 상태
- feat 코드(news_ingest/daily_refresh/__init__/infra/main/justfile/tests 3) → `feat:` 커밋. wrap-up 문서 → `docs:` 커밋. main 직접 + push (이 wrap-up 후반).
