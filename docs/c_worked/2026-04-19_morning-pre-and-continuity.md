---
date: 2026-04-19
topic: morning_pre 파이프라인 고도화 + 세션 연속성 시스템 구축 + git 초기화
status: completed
plan_file: C:\Users\HOME\.claude\plans\cheeky-kindling-tome.md
commit: fc84c4c
---

# 2026-04-19 · morning_pre 파이프라인 + 세션 연속성 시스템

## 배경
사용자가 docs/a_wanted + docs/b_plan 문서들을 읽고 "현재 어디까지 왔는지, 방향대로 가고 있는지" 진단을 요청. 진단 결과 Phase 1~2 뼈대는 완성됐으나 Phase 3(두뇌 이식)이 최대 공백. 이에 5개 시간대 브리핑(07:00/09:30/13:00/16:00/19:00) 중 07:00 장전부터 고도화하기로 결정. 작업 중 "세션 간격이 길어 맥락을 자꾸 잃는다"는 문제가 드러나 세션 연속성 시스템도 함께 구축.

## 한 일

### 1. 현재 상태 진단 (읽기 전용)
- `docs/a_wanted/user_want_spec.md` — 원 요구사항 (7 Agent)
- `docs/b_plan/architecture-review-workflow-restructure.md` — 하이브리드 6팀 3-Layer 결정 배경
- `docs/b_plan/pipeline-restructure-plan.md` — Phase 1~4 로드맵 v0.5
- Explore 에이전트 2개 병렬로 레포 상태 전수 조사 → 승인된 플랜 파일에 진단 리포트 작성

### 2. DB 스키마 (core/db/schema.sql)
- `watch_positions` — 사용자 수동 관심/보유 (평단·수량 미추적, 시그널 카운터만)
- `sim_trades` — AI 시뮬레이션 체결 로그 (append-only)
- `sim_positions` — sim_trades 누적 집계 (avg_price, total_quantity, 차수)
- `predictions` — 시나리오 예측 + AI 매매일지 겸용 (`related_trade_id` 로 sim_trades 연결)
- `news_items` — 수집 뉴스 + LLM 영향도 태깅 (본문 없이 title+url만)
- schema_version 2로 bump

### 3. 공용 수집 라이브러리 (collectors/ 신규)
- `collectors/us_markets.py` — `fetch_overnight()`: ^IXIC/^GSPC/^SOX/^VIX/DX-Y.NYB/^TNX/GC=F/CL=F
- `collectors/kr_futures.py` — `fetch_night_futures()`: CME KM=F 우선, EWY ETF 폴백
- `collectors/news_rss.py` — `fetch_news()`: Yahoo + CNBC + Google News RSS (httpx + xml.etree, feedparser 불필요)

### 4. 파이프라인 (pipelines/morning_pre/ 신규)
- `manifest.yaml` — cron `0 7 * * 1-5` Asia/Seoul, 8 stages 토폴로지컬 실행
- `prompts/analyst.md` — 07:00 전용 페르소나 (연속성 강조)
- `prompts/briefing.md` — 통합 JSON 출력 스키마
- `stages/collect_overnight_us.py` — us_markets 래퍼
- `stages/collect_night_futures.py` — kr_futures 래퍼
- `stages/collect_news.py` — 최대 20건
- `stages/load_positions.py` — watch_positions + sim_positions DB 로드
- `stages/check_principles.py` — sim_positions → 포트폴리오 변환 → 7계명 체크
- `stages/analyze.py` — LLM 1회 (canon + persona + memory 주입) → StandardOutput + MemoryRecord
- `stages/persist.py` — predictions / news_items / sim_trades / sim_positions / watch_positions 분해 저장
- `stages/notify.py` — 3분할 텔레그램 렌더 (간밤시황 / 시나리오+뉴스 / 포지션+신규)
- `tests/test_smoke.py` — manifest 로드 / stage import / E2E (mock LLM+RSS+yfinance)

### 5. API (server/api/ 신규)
- `briefings.py` — `GET /api/briefings/feed`, `/{run_id}`, `/by-pipeline/{id}/latest`
- `positions.py` — `watch_positions` CRUD + `GET /api/positions/sim`
- `server/main.py` — 라우터 등록 + legacy `demo` import 를 try/except 로 보호 (teams.orchestrator 잔재)

### 6. 세션 연속성 시스템 (신규)
- `docs/RESUME.md` — 1페이지 상태판 (Top 3, 현재 위치, 마지막 세션 링크)
- `docs/c_worked/` 폴더 — 세션별 일기 (오늘 이 파일이 첫 실데이터)
- `docs/SESSIONS.md` — 세션 목록 표 (claude -r 과 교차 확인용)
- `.claude/commands/resume.md` — `/resume` 슬래시 명령: a_wanted + RESUME + 최신 c_worked 병렬 읽기 → 플랜모드 진입 → Top 3 인터뷰 → 플랜 확정
- `.claude/commands/wrap-up.md` — `/wrap-up` 슬래시 명령: 빈-세션 방어 → c_worked 생성 → RESUME 갱신 → SESSIONS 행 추가 → MEMORY 판단 → 결과 요약. 끝날 때 `claude -r` 사용법 안내
- `CLAUDE.md` 루트 — "작업 전 반드시 읽어야 할 것" 최상단에 a_wanted + RESUME 추가, "세션 연속성" 섹션 신설

### 7. Git 초기화
- `.gitignore` — `.claude/settings.local.json` 추가
- `git init -b main`
- 첫 커밋: `fc84c4c Initial commit: wevelStock prototype foundation` (174 files)
- 원격(GitHub) 업로드는 보류 — 프로토타입 단계라 나중에 결정

## 검증 결과
- ✅ `pytest pipelines/morning_pre/tests/test_smoke.py` — 3/3 통과 (5.05s)
  - test_manifest_loaded / test_all_stages_importable / test_runner_executes_with_mocks
- ✅ DB 스키마 적용 확인 — 신규 5 테이블 모두 `PRAGMA table_info` 정상
- ✅ FastAPI 앱 부팅 — **17개 /api route** 정상 등록, legacy demo는 warning 후 skip
- ✅ Manifest 자동 탐색 — `list_all_pipelines` → `['morning_briefing', 'morning_pre']`
- ✅ Git working tree clean, 커밋 해시 `fc84c4c`

## 의도적으로 안 한 것 (승인된 플랜에 명시, 범위 밖)
- 09:30 / 13:00 / 16:00 / 19:00 파이프라인 — 각 인터뷰 필요
- 웹앱 feed UI — API만 노출
- `knowledge/canon/*.md` 내용 채우기 — 사용자 투자관 주입 필요
- `scripts/demo.py` / `tests/test_e2e.py` 의 `teams.orchestrator` 잔여 import 정리 (server/main.py 만 try/except 로 우회)
- GitHub 원격 push — 프로토타입 단계라 로컬 커밋만

## 다음에 이어서 할 작업 (우선순위)

### 즉시 실용 가치 (브리핑 퀄리티 직결)
1. **`knowledge/canon/` 내용 주입 인터뷰** — investment-principles / macro-framework / sector-insights / failure-lessons 의 TODO 를 사용자 실제 관점으로 채움. 이게 비면 LLM 판단이 일반론에 머뭄. 코드 변경 없음, MD 파일만 편집.
2. **morning_pre 실전 실행 + 결과 튜닝** — `POST /api/pipelines/morning_pre/run` 1회 → `data/notifications/YYYY-MM-DD.jsonl` 확인 → `pipelines/morning_pre/prompts/briefing.md` 조정. 전제: `ANTHROPIC_API_KEY` 설정, watch_positions 에 종목 1개 이상 등록.
3. **watch_positions 수동 등록** — `POST /api/positions/watch` 로 사용자 관심종목 3~5개 등록. positions_advice 가 의미 있으려면 필수.

### 다음 시간대 파이프라인 (하나씩 인터뷰)
4. **16:00 마감 후 파이프라인** — predictions 의 07:00 예측을 채점할 수 있어 적중률 사이클 완성에 가장 가치 큼
5. **09:30 개장 직후** — 07:00 시나리오 검증용
6. **13:00 장중**
7. **19:00 프리장 마감 전**

### 기술 부채
8. legacy `teams.orchestrator` 참조 정리 — `scripts/demo.py`, `tests/test_e2e.py`, `server/api/demo.py` 3곳
9. `docs/STRUCTURE.md` 를 `pipelines/` 기반으로 재작성 (현재는 `teams/` 중심 구버전)
10. `weekly_review` 파이프라인 골격 — predictions 채점 자동화

## 맥락 재진입 힌트 (다음 세션이 열어볼 파일)
- `pipelines/morning_pre/manifest.yaml` — 8 stage 흐름 한눈에
- `pipelines/morning_pre/prompts/briefing.md` — 출력 JSON 스키마 정의
- `pipelines/morning_pre/stages/analyze.py` — LLM 호출 + canon/persona/memory 주입 패턴
- `pipelines/morning_pre/stages/persist.py` — DB 분해 저장 패턴
- `pipelines/morning_pre/stages/notify.py` — 3분할 렌더 패턴
- `core/db/schema.sql` — 5 신규 테이블 정의
- `collectors/news_rss.py` — RSS 소스 추가/변경 지점
- `C:\Users\HOME\.claude\plans\cheeky-kindling-tome.md` — 이번 작업 승인된 플랜

## 커밋 상태
- ✅ 로컬 커밋 완료 — `fc84c4c Initial commit: wevelStock prototype foundation`
- ⏸️ GitHub 원격: 미연결 (프로토타입 안정화 후 결정)
- `main` 브랜치, working tree clean
