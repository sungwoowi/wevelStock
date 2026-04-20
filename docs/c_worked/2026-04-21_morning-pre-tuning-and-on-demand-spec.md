---
date: 2026-04-21
topic: morning_pre 실전 실행·포맷 튜닝 + briefings-on-demand SPEC 작성 (첫 SPEC)
status: completed
plan_file: C:\Users\HOME\.claude\plans\reflective-dancing-sun.md
---

# 2026-04-21 · morning_pre 실전 튜닝 + briefings-on-demand SPEC

## 배경
지난 세션(2026-04-19)에 morning_pre 파이프라인 8 stages 뼈대와 스모크(mock) 통과까지 완료. 이번 세션은 **실제 Gemini 호출을 한 번도 못 한 상태**에서 출발 → 실전 실행 → 발견된 이슈 순차 해결 → 텔레그램 메시지 포맷을 사용자 피드백 반영해 정제. 후반엔 "스케줄 브리핑을 사용자가 원할 때 종류별로 받을 수 있게" 하는 공통 플랫폼을 SPEC(BRIEFING-ON-DEMAND-001) 으로 정리. 프로젝트 첫 SPEC 문서.

## 한 일

### 1. 환경 셋업 + 누락 의존성
- `.env` — 메인 레포 `C:/Users/HOME/claude/wevelStock/.env` 를 워크트리로 복사 (gitignore 로 독립 필요). Gemini provider + GOOGLE_AI_API_KEY 로드 확인.
- `data/db/stock-advisor.sqlite` — `just db-init` 로 생성, schema v2.
- `pyproject.toml` — `google-genai>=0.3` 을 base dep 에 추가 (선언 누락이었음 — config 는 gemini provider 인데 패키지 미설치 상태였음). `yfinance>=0.2` 는 이미 market extra 에 있어 `uv sync --all-extras` 로 일괄 설치.

### 2. 파이프라인 실전 실행 & LLM 튜닝
- `pipelines/morning_pre/stages/analyze.py` — `max_tokens=3000 → 8000`. 근본 원인: Gemini 응답 JSON 이 3000 토큰 한도에서 잘려 `parse_json_response` 파싱 실패 → briefing 필드 전부 빈 값으로 저장. 8000 으로 늘리니 `tokens_out=3521` 로 완전 JSON 생성 + 파싱 성공.

### 3. 텔레그램 메시지 HTML 볼드 전환
- `core/notification/service.py`
  - `import html` 추가
  - `_send_telegram` 에 `parse_mode=HTML` 파라미터 추가
  - `_format_message` 에 `html.escape(title/body, quote=False)` 적용 (템플릿의 `<b>` 태그는 유지하면서 사용자 내용만 escape — `&` → `&amp;` 자동 처리)
  - 기본 템플릿 `*{title}*\n{body}` → `<b>{title}</b>\n{body}`
- `config/defaults.yaml` — `telegram.formats` 의 principles / daily_briefing / default 3줄에서 `*{title}*` → `<b>{title}</b>`

### 4. morning_pre 알림 본문 포맷 정제 (사용자 요청 반영)
- `pipelines/morning_pre/stages/notify.py`
  - 섹션 헤더: `📊 미국 지수` → `🇺🇸 미국 지수`, `💱 거시` → `🌐 거시경제 지표`
  - 각 항목에 글머리 `* ` 추가 (미국 지수 블록 + 거시경제 블록 둘 다)
  - VIX 라벨: 한 번 `공포지수` 로 잘못 번역 → 사용자 정정 → `변동성 지수` 로 교정 (VIX 는 변동성, 공포탐욕은 별개 지표)
  - SOX 라벨: `SOX(반도체)` → `SOX (반도체)` (공백 일관성)
  - 거시경제 라벨들: `DXY` → `💵 (달러인덱스)`, `美10Y` → `美10Y (10년 국채금리)`, `金` → `🥇 (국제금시세)`, `WTI` → `WTI (서부 텍사스산 원유 선물)`

### 5. 원달러 환율 추가
- `collectors/us_markets.py` — `OVERNIGHT_SYMBOLS` 에 `"usdkrw": "KRW=X"` 1줄 추가.
- `pipelines/morning_pre/stages/collect_overnight_us.py` — macro 튜플에 `"usdkrw"` 포함.
- `pipelines/morning_pre/stages/notify.py` — 거시경제 루프 라벨 리스트에 `("usdkrw", "🇰🇷 (원달러환율)")` 을 달러인덱스 바로 다음 위치로 삽입.

### 6. CNN Fear & Greed Index 수집·표시 (신규 데이터 소스)
- `collectors/fear_greed.py` **신규** — 비공식 JSON endpoint `production.dataviz.cnn.io/index/fearandgreed/graphdata` 호출. Chrome 스타일 User-Agent + Referer/Origin 헤더로 418 차단 우회. rating 한국어 매핑(`_RATING_KR`) 포함. score/previous_close 에서 change_pct 계산. 실패 시 `{"error": ...}` graceful.
- `pipelines/morning_pre/stages/collect_overnight_us.py` — `fetch_fear_greed()` 호출 추가, `indices_keys` 에 `fear_greed` 포함.
- `pipelines/morning_pre/stages/notify.py` — 미국 지수 루프 뒤 FGI 특수 렌더 블록 (`공포·탐욕 지수 69.2 [탐욕] (+1.68%)` 형식. score + rating_kr + change_pct).

### 7. BRIEFING-ON-DEMAND-001 SPEC 작성 (첫 SPEC)
- `docs/specs/BRIEFING-ON-DEMAND-001-briefings-on-demand.md` **신규** — `docs/specs/` 폴더도 새로 생성. 크로스 레이어 기능(파이프라인 + API + 알림) 이라 특정 팀 귀속 대신 `team: shared`.
- 5라운드 면담 결과 정리:
  - 스코프: 스케줄 파이프라인의 파트 조회/재실행/재전송 공통 플랫폼. 종목분석/Q&A 는 별도 SPEC 으로 분리.
  - 데이터: `briefing_parts` 테이블 신규 (DB v3 bump).
  - API: 4 엔드포인트, JSON 통일 응답, 클라이언트가 렌더링.
  - UX v1: 텔레그램 3개 명령어 (`/briefing`, `/briefing_now`, `/help`). inline 버튼·웹앱 UI·파트별 명령어는 v2+.
  - 수신: long-polling (python-telegram-bot). webhook push 는 **v3 최종 목표**로 기록.
  - 보호: chat_id 화이트리스트 + 60초 중복방지 캐시.
  - 사용자 멘탈모델 "2뎁스"(브리핑 유형 × 파트) 를 SPEC 구조에 반영.

## 검증 결과

- ✅ `morning_pre` 파이프라인 8 stages 전부 ok, 실제 Gemini 호출 (`gemini-2.5-flash-lite`, cost=$0.00151)
- ✅ JSON 파싱 통과 (`tokens_out=3521 / 8000`), `raw_unparsed=False`
- ✅ `scenario.bias=neutral_negative`, `expected_open=gap_down_small` 스키마 준수
- ✅ `reasons` 3개, 수치 포함 (-2.23%, -0.7%, 10.98%, 3.47%)
- ✅ `positions_advice` 3/3 (삼성전자·SK하이닉스·삼성SDI HOLD)
- ✅ `new_candidates` 3개, `news_impact` 20/20 입력 뉴스 전체 커버
- ✅ DB persist: predictions 13행, news_items 100행, team_outputs 5행
- ✅ Telegram 3분할 발송 성공, HTML 볼드 렌더 확인
- ✅ Fear & Greed Index 실시간 수집 (score=69.2 / rating=greed / change=+1.68%)
- ✅ 원달러 환율 수집 (1,469~1,470원 범위)
- ✅ 메시지 본문 최종 포맷:
  ```
  🇺🇸 미국 지수
    * 나스닥/S&P500/SOX (반도체)/VIX (변동성 지수)
    * 공포·탐욕 지수 69.2 [탐욕] (+1.68%)
  🌐 거시경제 지표
    * 💵 (달러인덱스) / 🇰🇷 (원달러환율) / 美10Y (10년 국채금리) / 🥇 (국제금시세) / WTI (서부 텍사스산 원유 선물)
  ```

## 의도적으로 안 한 것

- **`knowledge/canon/*` TODO 채우기** — 별도 세션. 사용자 투자관 주입은 집중 인터뷰 필요.
- **BRIEFING-ON-DEMAND-001 구현** — SPEC 만 작성. 구현은 새 세션(3~5h 예상)에서 신선한 눈으로.
- **legacy `teams.orchestrator` 잔재 정리** (`scripts/demo.py`, `tests/test_e2e.py`, `server/api/demo.py`) — 기술 부채. 기능 진전 우선.
- **`docs/STRUCTURE.md` 재작성** — 현재 `teams/` 기준이지만 실제는 `pipelines/`. 기술 부채.
- **커밋** — 이번 세션까지 포함 전부 워킹트리. 다음 세션 정리 겸 한 번에 묶어서 커밋 예정.
- **서버 `--reload` 의존** — uvicorn `--reload` 가 이 레이아웃에서 파일 변경 감지를 잘 못함. 수정 시마다 수동 재시작으로 가는 게 안정.

## 다음에 이어서 할 작업 (우선순위)

### 즉시 실용 가치 (SPEC → 구현 사이클)
1. **BRIEFING-ON-DEMAND-001 구현** — SPEC의 `generates` 10개 파일 + `modifies` 7개 파일. DB v3 마이그레이션 포함. 텔레그램 봇 long-polling 이 가장 큰 신규 컴포넌트. 완료 기준 체크리스트 SPEC 본문 참조. 예상 3~5h.
2. **`knowledge/canon/*.md` 내용 주입 인터뷰** — investment-principles / macro-framework / sector-insights / failure-lessons 4파일 TODO. 사용자 실제 투자관 Q&A → 편집. 코드 변경 없음. 1.5~2h.
3. **`new_candidates` ticker 정확도 개선** — 오늘 Gemini 응답에서 `ticker="000000"` placeholder 반환. 해결 선택지: (a) 프롬프트에 "모르면 ticker 비워라" 지시, (b) KIS API 종목 마스터 연동, (c) 종목명→ticker 매핑 로컬 테이블. (a) 가 가장 저비용.

### 다음 단계 후보
4. **16:00 close_review 파이프라인 신규** — predictions 채점 → 적중률 사이클 완성. briefings-on-demand v1 에 자연스럽게 합류 (manifest 에 `parts:` 추가하면 끝).
5. **09:30 market_open 파이프라인** — 07:00 시나리오 검증용.
6. **Gemini retry / fallback** — 503 high demand 시 지수 백오프 2~3회 재시도 후 anthropic fallback. 현재는 즉시 mock.

### 기술 부채
7. legacy `teams.orchestrator` 참조 정리 (scripts/demo.py, tests/test_e2e.py, server/api/demo.py)
8. `docs/STRUCTURE.md` 를 `pipelines/` 기반으로 재작성
9. `weekly_review` 파이프라인 골격 — predictions 채점 자동화
10. 워킹트리 누적 변경 커밋 정리 — 오늘+지난 세션 전부 미커밋 상태

## 맥락 재진입 힌트 (다음 세션이 열어볼 파일)

- `docs/specs/BRIEFING-ON-DEMAND-001-briefings-on-demand.md` — 새 SPEC 전체. `generates`/`modifies` + 엔드포인트 사양 + DB 스키마 + 봇 명령어
- `pipelines/morning_pre/stages/notify.py` — 현재 메시지 포맷 레퍼런스. `core/briefing/render.py` 공용화 대상
- `pipelines/morning_pre/stages/analyze.py` — `max_tokens=8000` 수정 지점 + LLM 호출 패턴
- `core/notification/service.py` — HTML 볼드 + html.escape 경로. 봇 sendMessage 도 여기 경유
- `collectors/fear_greed.py` — CNN 비공식 API 호출 패턴 (User-Agent 위장). 향후 다른 비공식 소스 추가 시 참고
- `core/llm/client.py` — gemini/anthropic/mock 분기. retry/fallback 개선 대상
- `C:\Users\HOME\.claude\plans\reflective-dancing-sun.md` — 이번 세션 승인된 플랜

## 커밋 상태
아직 git 커밋 안 됨. 지난 Phase 2 결과물 포함 이번 세션 전부 워킹트리에 누적. 다음 세션 시작 시 정리 겸 묶음 커밋 예정.
