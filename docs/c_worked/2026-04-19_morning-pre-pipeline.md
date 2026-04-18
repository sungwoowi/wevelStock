---
date: 2026-04-19
topic: 07:00 장전 브리핑 (morning_pre 파이프라인) 고도화
status: completed
plan_file: C:\Users\HOME\.claude\plans\cheeky-kindling-tome.md
---

# 2026-04-19 · morning_pre 파이프라인 고도화

## 배경
사용자가 5개 시간대 브리핑(07:00 장전 / 09:30 개장 / 13:00 장중 / 16:00 마감 / 19:00 프리장)을 운영하고자 함. 품질 우선순위는 **(1) 브리핑 신뢰도 (2) 수정 간섭 없음**. 이번은 **07:00만 먼저 고도화**하고, 향후 시간대별 독립 파이프라인으로 확장 가능한 뼈대를 구축.

## 한 일

### DB 스키마 (core/db/schema.sql)
- 신규 5개 테이블: `watch_positions` / `sim_trades` / `sim_positions` / `predictions` / `news_items`
- schema_version 2로 bump
- 사용자 통찰 반영: 수동 관심/보유(평단·수량 미추적, 시그널 카운터)와 AI 시뮬 매매(평단·수량·차수) 스키마 분리

### 공용 수집 라이브러리 (collectors/ 신규)
- `collectors/us_markets.py` — `fetch_overnight()`: ^IXIC, ^GSPC, ^SOX, ^VIX, DX-Y.NYB, ^TNX, GC=F, CL=F
- `collectors/kr_futures.py` — `fetch_night_futures()`: CME KM=F 우선, EWY ETF 폴백
- `collectors/news_rss.py` — `fetch_news()`: Yahoo + CNBC + Google News RSS (제목+URL만, 본문 X)

### 파이프라인 (pipelines/morning_pre/ 신규)
- `manifest.yaml` — cron `0 7 * * 1-5` Asia/Seoul, 8 stages, topological waves
- `prompts/analyst.md` — 07:00 전용 페르소나 (연속성 강조)
- `prompts/briefing.md` — 통합 JSON 출력 스키마
- `stages/collect_overnight_us.py`
- `stages/collect_night_futures.py`
- `stages/collect_news.py` (최대 20건)
- `stages/load_positions.py` — watch_positions + sim_positions DB 로드
- `stages/check_principles.py` — sim_positions → 포트폴리오 변환 → 7계명
- `stages/analyze.py` — LLM 1회 (canon + persona + memory) → StandardOutput + MemoryRecord
- `stages/persist.py` — predictions / news_items / sim_trades / sim_positions / watch_positions 분해 저장
- `stages/notify.py` — 3분할 텔레그램 (간밤시황 / 시나리오+뉴스 / 포지션+신규)
- `tests/test_smoke.py` — manifest 로드 / stage import / E2E (mock LLM+RSS+yfinance)

### API (server/api/ 신규)
- `briefings.py` — `GET /api/briefings/feed`, `GET /api/briefings/{run_id}`, `GET /api/briefings/by-pipeline/{id}/latest`
- `positions.py` — watch_positions CRUD + `GET /api/positions/sim`
- `server/main.py` — 라우터 등록 + legacy `demo` import를 try/except 로 보호 (teams.orchestrator 잔재)

## 검증 결과
- ✅ `pytest pipelines/morning_pre/tests/test_smoke.py` 3/3 통과 (5.05s)
- ✅ DB 스키마 적용, 신규 5 테이블 확인 (`PRAGMA table_info`)
- ✅ FastAPI app boot OK, **17개 /api route** 정상 등록 (legacy demo는 warning 로그 + 스킵)
- ✅ Manifest 자동 탐색 OK (`pipelines found: ['morning_briefing', 'morning_pre']`)

## 의도적으로 안 한 것 (승인된 플랜에 명시, 범위 밖)
- 09:30 / 13:00 / 16:00 / 19:00 파이프라인 — 각 인터뷰 필요
- 웹앱 feed UI — API만 노출
- knowledge/canon/ 내용 채우기 — 사용자 투자관 필요
- `scripts/demo.py` / `tests/test_e2e.py` 의 `teams.orchestrator` 잔여 import 정리

## 다음에 이어서 할 작업 (우선순위)

### 즉시 실용 가치 (브리핑 퀄리티 직결)
1. **knowledge/canon/ 내용 주입 인터뷰** — investment-principles / macro-framework / sector-insights / failure-lessons 의 TODO를 사용자 실제 관점으로 채움. 이게 비면 LLM 판단이 일반론.
2. **실전 실행 1회 + 결과 튜닝** — `POST /api/pipelines/morning_pre/run` → `data/notifications/YYYY-MM-DD.jsonl` 확인 → 프롬프트/스키마 미세조정
3. **watch_positions 수동 등록** — `POST /api/positions/watch` 로 관심종목 3~5개. 이게 있어야 positions_advice 의미 있음.

### 다음 시간대 파이프라인 (하나씩 인터뷰)
4. **16:00 마감 후** — predictions 의 07:00 예측을 채점할 수 있어 적중률 사이클 완성에 가장 가치 큼
5. **09:30 개장 직후** — 07:00 시나리오 검증용
6. **13:00 장중**
7. **19:00 프리장 마감 전**

### 기술 부채
8. legacy `teams.orchestrator` 참조 정리 (`scripts/demo.py`, `tests/test_e2e.py`, `server/api/demo.py`)
9. `docs/STRUCTURE.md` 를 `pipelines/` 기반으로 재작성
10. `weekly_review` 파이프라인 골격 — predictions 채점 자동화

## 맥락 재진입 힌트 (다음 세션이 열어볼 파일)
- `pipelines/morning_pre/manifest.yaml` — 8 stage 흐름 한눈에
- `pipelines/morning_pre/prompts/briefing.md` — 출력 JSON 스키마
- `pipelines/morning_pre/stages/analyze.py` — LLM 호출 패턴
- `pipelines/morning_pre/stages/persist.py` — DB 분해 저장 패턴
- `pipelines/morning_pre/stages/notify.py` — 3분할 렌더
- `core/db/schema.sql` — 5 신규 테이블 정의
- `collectors/news_rss.py` — RSS 추가/변경 지점
- `C:\Users\HOME\.claude\plans\cheeky-kindling-tome.md` — 이번 작업 승인된 플랜

## 커밋 상태
- 아직 git 커밋 안 됨.
