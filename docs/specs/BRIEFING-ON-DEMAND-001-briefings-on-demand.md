---
spec_id: BRIEFING-ON-DEMAND-001
title: 브리핑 온디맨드 — 스케줄 파이프라인의 파트 조회/재실행/재전송 공통 플랫폼
team: shared
type: feature
status: scaffolded
version: 1
owner: platform
generates:
  - core/briefing/__init__.py
  - core/briefing/render.py
  - core/briefing/parts_store.py
  - core/db/migrations/v3_briefing_parts.sql
  - core/contracts/briefing_part.py
  - server/api/briefings_on_demand.py
  - server/telegram/__init__.py
  - server/telegram/bot.py
  - server/telegram/commands.py
  - tests/test_briefings_on_demand.py
  - tests/test_briefing_render.py
modifies:
  - core/db/schema.sql
  - pipelines/morning_pre/stages/persist.py
  - pipelines/morning_pre/stages/notify.py
  - pipelines/morning_pre/manifest.yaml
  - server/api/briefings.py
  - server/main.py
  - pyproject.toml
depends_on: []
contracts:
  - briefing-part-v1
  - team-output-v1
---

# BRIEFING-ON-DEMAND-001: 브리핑 온디맨드

## 목적
스케줄로 자동 실행되는 파이프라인(morning_pre / 장시작 / 장중 / 장마감 등) 의 **결과를 사용자가 원할 때 꺼내 쓸 수 있게** 한다. 텔레그램 봇과 웹앱이 **동일한 REST API** 를 소비하는 공통 컨트롤 플레인을 제공한다.

## 배경 / 문제
- 현재는 cron 스케줄대로 3분할 텔레그램 메시지가 푸시되고 끝. 사용자가 놓치면 다시 볼 방법이 **jsonl 파일 직접 열기** 외에 없음.
- 스케줄 시간이 아닐 때 "지금 기준으로" 보고 싶어도 수동으로 파이프라인을 재호출하는 CLI/API 가 분절돼 있음.
- 향후 파이프라인(장시작 09:30 / 장중 12:30 / 장마감 16:00) 추가 시 동일 패턴을 반복 구현하는 것은 낭비.

## 핵심 정의 (용어)

| 용어 | 의미 |
|---|---|
| **브리핑(Briefing)** | 파이프라인 1회 실행 = LLM 1회 호출의 결과 묶음. `run_id` 로 식별. |
| **파트(Part)** | 브리핑 내부의 UI 섹션 (예: morning_pre → `overnight`/`scenario`/`positions`). 같은 LLM 컨텍스트 · 같은 메모리에서 파생. |
| **파이프라인 유형** | 시간대별 브리핑 유형 (장전 / 장시작 / 장중 / 장마감). `pipeline_id` 로 식별. |
| **온디맨드(on-demand)** | 스케줄이 아닌 사용자 이벤트로 트리거된 실행 또는 재전송. |

## 스코프

### 포함 (v1 MVP)
- `briefing_parts` 테이블 신설 (DB 스키마 v3 bump)
- 공용 파트 렌더 함수 (`core/briefing/render.py`) — 기존 `notify.py` 의 `_build_msg_1/2/3` 을 이동
- REST API 엔드포인트 4종 (`/api/briefings/{pipeline_id}/...`)
- 텔레그램 봇 (long-polling) + 명령어 3개 (`/briefing`, `/briefing_now`, `/help`)
- chat_id 인증 + 1분 내 동일 요청 캐시
- `morning_pre` 파이프라인을 첫 번째 소비자로 연결

### 제외 (Non-goals in v1)
- 과거 날짜 조회 (오늘자만)
- 파트별 개별 명령어 (`/briefing_overnight` 등) — v1.1 로
- 텔레그램 inline 버튼 (callback_query) — v2 로
- 웹앱 UI — API 만 공개, UI 는 별도 세션
- 텔레그램 webhook (공개 URL 배포) — **v3 최종 목표로 기록**
- 사용자 입력 종목 분석, 자유 Q&A — **별도 SPEC**. 이 SPEC 의 응답 스키마만 재활용.

## 입력
- `team_outputs` 테이블 (기존) — 파이프라인 실행 결과 JSON
- `briefing_parts` 테이블 (신규) — 파트 단위 스토어
- `pipelines/{id}/manifest.yaml` (기존 + 확장) — `parts:` 필드 추가
- 텔레그램 메시지 (long-polling 수신) — 슬래시 명령
- HTTP 요청 (웹앱/클라이언트) — REST API

## 출력

### API 응답 스키마 (contract: `briefing-part-v1`)
모든 API 는 `application/json` 만 반환. 렌더링(텔레그램 텍스트 / 웹앱 컴포넌트) 은 **클라이언트 책임**.

```json
{
  "pipeline_id": "morning_pre",
  "run_id": "2026-04-20T14:34:09.548599+00:00#manual-276815",
  "generated_at": "2026-04-20T14:34:16Z",
  "status": "ok",
  "cache_hit": false,
  "parts": [
    {
      "key": "overnight",
      "label": "간밤시황",
      "order": 1,
      "data": { /* 파이프라인별 구조 */ }
    },
    { "key": "scenario",  "label": "시나리오+뉴스", "order": 2, "data": {...} },
    { "key": "positions", "label": "포지션+신규", "order": 3, "data": {...} }
  ]
}
```

- `data` 필드 내부 스키마는 **파이프라인별 자유**. 공통 필드는 `key/label/order` 만.
- 단일 파트 조회 시엔 `parts` 대신 단일 객체 반환.

### 텔레그램 메시지 (내부 렌더)
서버가 `core/briefing/render.py` 의 렌더러로 JSON → 텍스트 변환 후 `sendMessage` 호출. 이 함수는 파이프라인별 전용(예: `render_morning_pre(parts)`) 과 공용 헬퍼(`_fmt_pct`, `_fmt_num`) 로 구성.

## API 엔드포인트 (server/api/briefings_on_demand.py)

| Method | Path | 설명 | 주요 응답 |
|---|---|---|---|
| `GET`  | `/api/briefings/{pipeline_id}/latest` | 가장 최근 run 의 파트 전체 | `{pipeline_id, run_id, parts[...]}` |
| `GET`  | `/api/briefings/{pipeline_id}/latest/parts/{key}` | 단일 파트 | `{key, label, data}` |
| `POST` | `/api/briefings/{pipeline_id}/run` | 새 run 실행 후 파트 반환 | `{run_id, parts[...], status}` |
| `POST` | `/api/briefings/{pipeline_id}/resend` | 기존 run 을 채널로 재전송 | `{delivered:["telegram"], run_id}` |

**쿼리 파라미터**:
- `POST .../run`: `force=true` (default) → 새 run. `cache=true` → 최근 run 재사용.
- `POST .../resend`: `channel=telegram|file`, `part_key=overnight|...|all`, `run_id=...` (생략 시 latest).

## DB 스키마 변경 (v3 bump)

### 신규 테이블: `briefing_parts`
```sql
CREATE TABLE briefing_parts (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  pipeline_id   TEXT NOT NULL,
  run_id        TEXT NOT NULL,
  part_key      TEXT NOT NULL,       -- overnight | scenario | positions | ...
  part_label    TEXT NOT NULL,
  part_order    INTEGER NOT NULL,
  data_json     TEXT NOT NULL,        -- 파트별 구조화 데이터
  created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(pipeline_id, run_id, part_key)
);
CREATE INDEX idx_briefing_parts_lookup
  ON briefing_parts(pipeline_id, created_at DESC);
```

`ON CONFLICT REPLACE` 로 동일 (pipeline_id, run_id, part_key) 재실행 시 덮어쓰기 (멱등성).

### manifest.yaml 확장
```yaml
# pipelines/morning_pre/manifest.yaml
parts:
  - key: overnight
    label: 간밤시황
    order: 1
  - key: scenario
    label: 시나리오+뉴스
    order: 2
  - key: positions
    label: 포지션+신규
    order: 3
```

## 텔레그램 봇 사양

### v1 명령어 세트 (3개)
| 명령 | 동작 |
|---|---|
| `/briefing` | 현재 시각에 가장 가까운 과거 파이프라인의 오늘자 마지막 run 을 재전송 (cache=true). 없으면 "아직 실행된 적 없음" 안내. |
| `/briefing_now` | 현재 시각에 적합한 파이프라인을 **강제 새 run** (force=true). 시작 시 "⏳ 내용 생성 중… (약 30초)" 중간 메시지. 완료 후 파트 전송. |
| `/help` | 명령어 목록 + 간단 설명 |

### v1.1+ (확장 준비)
- `/briefing_pre`, `/briefing_open`, `/briefing_mid`, `/briefing_close` — 파이프라인 유형별
- `/briefing_<pipeline>_<part>` — 파트별 (필요 시)

### 구동 방식 (v1)
- **long-polling**: `server/telegram/bot.py` 가 `python-telegram-bot` 의 `Application` 으로 `getUpdates` 주기 호출
- `server/main.py` 의 FastAPI `lifespan` 에서 봇 폴링 태스크 기동 (`asyncio.gather`)
- 봇은 내부에서 REST API (`/api/briefings/...`) 를 호출 → JSON 수신 → `core/briefing/render.py` 로 텍스트 변환 → `sendMessage`

### 봇 초기 setup
- 서버 부팅 시 `setMyCommands` 호출로 슬래시 자동완성 등록 (1회)
- 등록 실패(네트워크·토큰 오류) 시 warning 로그, 봇 기능 계속

## 보호 장치

### 인증 (chat_id 화이트리스트)
- `.env` 의 `TELEGRAM_CHAT_ID` 와 일치하는 chat 만 응답
- 불일치 시 **무시** (응답 없음 — 정보 노출 방지)

### 중복 방지 (in-memory TTL 캐시)
- 동일 `pipeline_id` + 동일 `force` 플래그의 호출이 60초 이내 반복되면 이전 결과 JSON 을 그대로 반환
- 캐시 키: `f"{pipeline_id}:force={force}"`, TTL 60s
- 캐시는 프로세스 메모리 (서버 재시작 시 초기화). DB 백업 불필요.

### Gemini 무료 티어 보호 (선택)
- `/briefing_now` 의 일일 호출 수 카운터 (in-memory 또는 `daily_counter` 테이블)
- 한도(예: 일 100회) 초과 시 "오늘 강제 재실행 한도 도달. 캐시 버전 보여드릴게요" 안내 후 fallback

## 실행 시나리오

### 시나리오 A: 놓친 아침 브리핑 재조회
1. 사용자 09:00 에 일어나 텔레그램 열음
2. `/briefing` 입력 → 슬래시 자동완성에서 선택
3. 봇이 `GET /api/briefings/morning_pre/latest` 호출 → 오늘 07:00 생성 parts 3개 수신
4. `render_morning_pre(parts)` → 3분할 텍스트 → sendMessage 3회
5. 사용자 폰에 오늘 브리핑 도착 (원본과 동일)

### 시나리오 A-cache-miss: 아예 스케줄 놓침 (주말 등)
1. `/briefing` → `GET /api/briefings/morning_pre/latest` → **404** (오늘자 run 없음)
2. 봇이 "오늘 아직 실행되지 않았습니다. `/briefing_now` 로 지금 실행할 수 있어요" 안내

### 시나리오 B: 오후에 지금 기준 시황 궁금
1. `/briefing_now` 입력
2. 봇이 `POST /api/briefings/morning_pre/run?force=true` 호출 (시간 걸림)
3. 봇이 즉시 "⏳ 내용 생성 중… (약 30초)" 메시지 먼저 전송
4. API 응답 수신 (30~60초 후) → render → sendMessage 3회
5. 사용자에게 최신 데이터 도착

### 시나리오 C: 웹앱 피드 (v2, 별도 구현)
1. 웹앱이 `GET /api/briefings/morning_pre/latest` 호출
2. JSON parts 를 React 컴포넌트로 렌더 (섹션 카드)
3. `[지금 기준 다시 실행]` 버튼 → `POST .../run?force=true`
4. 로딩 스피너 → 결과 렌더

## 판단 로직
<!-- SPEC:INTERVIEW-SLOT role="judgment-logic" -->

- **기본 파이프라인 선택 규칙** (현재 시각 기준):
  - 07:00 ~ 09:29 → `morning_pre`
  - 09:30 ~ 12:29 → `market_open` (v2, 미구현 시 fallback `morning_pre`)
  - 12:30 ~ 15:29 → `market_mid` (v2, fallback `morning_pre`)
  - 15:30 ~ 익일 06:59 → `market_close` (v2, fallback `morning_pre`)
- **v1 에선 `morning_pre` 하나만** 존재하므로 시간 무관 고정.
- 새 run 실행 중 동일 `pipeline_id` 요청이 오면 **진행 중 run 의 결과를 기다리게 함** (중복 실행 방지).

## 엣지 케이스
<!-- SPEC:INTERVIEW-SLOT role="edge-cases" -->

- **Gemini 503 장애**: `core/llm/client.py` 의 mock 폴백으로 떨어짐. API 응답의 `status` 필드에 `"degraded"` + `metadata.model` 에 `*-mock` 노출. 봇은 텍스트 앞에 `⚠️ 일시적 LLM 장애 — mock 응답입니다` 태그.
- **텔레그램 토큰 미설정**: 봇 구동 시점에 경고 로그 후 **봇만 비활성**. API 는 정상 동작.
- **파이프라인 미존재** (`pipeline_id` 오타): API 404. 봇은 `/briefing close_review` 처럼 오타 시 `/help` 로 안내.
- **chat_id 불일치**: 응답 완전 억제 (attack 벡터 최소화).
- **run_id 없음** (오늘 한 번도 안 돌았음): 시나리오 A-cache-miss 참조.
- **briefing_parts insert 실패 (persist stage)**: 해당 run 만 `team_outputs` 에 저장되고 `briefing_parts` 는 비어있는 상태 → API `/latest` 가 404 로 빠짐. 재실행 유도 필요. persist stage 에서 이 상황을 `warning` 상태로 표시.
- **동시에 `/briefing_now` 2회 호출**: 60초 캐시로 두 번째는 첫 번째 결과 반환 (중복 LLM 호출 방지).

## 보안 / 크로스 플랫폼

- `TELEGRAM_BOT_TOKEN` 은 `.env` 만. 하드코딩·로그 출력 금지.
- long-polling 구현은 표준 asyncio — Mac/Windows 공통 동작.
- 봇 태스크는 `server/main.py` 의 `lifespan` 이 관리. 서버 종료 시 graceful stop.
- `pyproject.toml` 에 `python-telegram-bot>=21.0` 추가 (현재 base dep 의 httpx 와 충돌 없음).

## v2 / v3 로드맵 (별도 SPEC 후보)

| 버전 | 범위 |
|---|---|
| **v1 (이 SPEC)** | API 4종 + 봇 3명령어 + briefing_parts 테이블 + morning_pre 통합 |
| **v1.1** | 파트별 명령어 (`/briefing_overnight` 등) + 파이프라인 유형별 명령어 (`/briefing_pre`) |
| **v2** | 텔레그램 inline 버튼 (callback_query) + 웹앱 `/briefings` UI |
| **v3 (최종 목표)** | 텔레그램 **webhook push** (공개 URL 배포) + 여러 파이프라인 유형 완비 (market_open/mid/close) |

## 완료 기준 (v1 MVP)

- [ ] 스키마 v3 마이그레이션 성공 (`just db-init` 후 `briefing_parts` 테이블 존재 확인)
- [ ] `pipelines/morning_pre/stages/persist.py` 가 `briefing_parts` 에 3행 insert
- [ ] `pipelines/morning_pre/stages/notify.py` 가 `core/briefing/render.py` 의 공용 함수 사용 (기능 동일, 코드 중복 제거)
- [ ] REST API 4 엔드포인트 모두 200 OK + 스키마 일치 확인
- [ ] `/briefing` 명령어 → 오늘자 재전송 동작
- [ ] `/briefing_now` 명령어 → 강제 새 run + 중간 "생성 중…" 메시지 + 완료 파트 전송
- [ ] chat_id 불일치 시 응답 없음 (무시) 검증
- [ ] 60초 캐시 동작 검증 (동일 요청 2회 → 2번째는 즉시 반환)
- [ ] Gemini mock 폴백 시 `status: degraded` + 경고 태그 붙는지 확인
- [ ] `pytest tests/test_briefings_on_demand.py` + `tests/test_briefing_render.py` 통과
- [ ] `just validate` 통과

## 다른 팀·파이프라인 영향

- **DB 스키마 v3**: 기존 `team_outputs` / `watch_positions` 등 변경 없음. 신규 테이블만 추가 → 호환성 유지. 단 `core/db/schema.sql` 버전 bump 필요.
- **morning_pre 파이프라인**: `persist.py` 와 `notify.py` 변경. 기존 동작 유지하면서 공용 함수 도입.
- **향후 파이프라인 (market_open 등)**: 이 SPEC 의 API/스키마를 그대로 상속. 파이프라인 별 `render_<id>` 함수만 추가 작성.
- **core/notification/service.py**: 변경 없음 (메시지 송신은 기존 경로 유지).
