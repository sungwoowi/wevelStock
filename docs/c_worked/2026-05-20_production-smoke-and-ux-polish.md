---
date: 2026-05-20
topic: cycle 6 production smoke 검증 + KIS 토큰 공유 + webapp UX 분할/select + 종목명 매핑 (cycle 6.5)
status: completed
plan_file: C:\Users\HOME\.claude\plans\elegant-moseying-cloud.md
---

# 2026-05-20 · production smoke 검증 + UX 보강 (cycle 6.5)

## 배경

cycle 6 (INFRA-CHART-DATA-001 풀세트 구현, commit `665796f`) 직후 사용자 깨어난 후
production smoke 검증 진행. 4 가지 본질 문제 순차 발견·해결: (1) KIS 토큰 분당 1회
한도 충돌 (2) webapp UI 가 분석가/전략가 비교 어려움 (3) placeholder 가 실제 값처럼
보여 사용자가 ticker 미입력 채로 호출 (4) ticker 강제 = production UX 본질 위반
(한글 종목명 입력 못 함). 본 사이클 = MS3 production smoke 완전 통과 베이스라인 + UX
production 한 발 진보.

## 한 일

- `connectors/kis/client.py` — KISClient process-wide 토큰 캐시 (class-level `_shared_token` + `asyncio.Lock` + `_get_token_lock` lazy init + `reset_token_cache` 테스트 helper). 같은 KIS_APP_KEY 모든 인스턴스가 단일 토큰 reuse (24h 만료까지). snapshot + chart burst 시 토큰 재발급 충돌 해소.
- `core/inference/run_analyst.py` — `resolve_ticker(raw)` 헬퍼 + `KR_NAME_TO_TICKER` 35종 (KOSPI 상위 25 + KOSDAQ 상위 10) + `KR_TICKER_TO_NAME` 역방향 + `_normalize_name` (공백·대소문자). `_maybe_build_chart_data_md` 가 resolve_ticker 통과 후 build_chart_data 호출. 미매핑 시 `chart_failures=['ticker_resolve_failed:<입력>']`. `render_chart_data_md(name=display_name)` 전달로 chart 헤더에 한글명 노출.
- `server/api/analyst_chat.py` — `ChatRequest.target_ticker: str | None` 필드 + chat / chat/stream 양쪽 `run_analyst`/`run_analyst_stream` 에 전달. INFRA-CHART-DATA-001 흐름 활성화.
- `webapp/src/components/ChatPane.tsx` (신규 ~370 줄) — 재사용 컴포넌트 (props: kind/title/agents/defaultAgentId/provider/showTickerField). MetadataBar 가 `chart_source` 컬러 (db/kis 녹색, stale_cache 황색, unknown 빨강) + ohlcv 봉 수 + failures tooltip 표시. 분석가 + stock_analyst 선택 시만 ticker 필드 노출 (조건부).
- `webapp/src/app/analyst-chat/page.tsx` — 단일 채팅 + layer 토글 (551줄) → 좌(분석가) / 우(전략가) 양쪽 ChatPane 인스턴스 (~125 줄). 9 분석가 + 2 전략가 하드코드 옵션 (한국어 라벨 + 권위 설명). lg:grid-cols-2 분할.
- ticker 필드 UX 개선 (`ChatPane.tsx`) — 라벨 "ticker" → "종목", placeholder "005930" → "예: 005930 또는 삼성전자", 빈 값 시 amber `⚠ 입력 필요 (미입력 시 chart 미주입)` 경고.
- `tests/test_run_analyst_chart_injection.py` — 신규 3 케이스: `test_resolve_ticker_unit` (6자리 / 한글 / 정규화 / 미매핑·빈값) / `test_stock_analyst_with_korean_name_resolves_ticker` (한글 → ticker 자동 매핑 후 build_chart_data 가 6자리 받음) / `test_stock_analyst_with_unmapped_name_yields_resolve_failure`.

## 검증 결과

- ✅ pytest **376 → 379 passed** (회귀 0, +3 신규 resolve_ticker 케이스)
- ✅ webapp typecheck (`npx tsc --noEmit`) errors 0
- ✅ Production smoke (mock provider, httpx 직접 호출):
  - "삼성전자" → chart_ticker=005930 (자동 매핑) / chart_source=db / chart_ohlcv_count=1825 / system_prompt_chars=31,474 (chart_data_md [4] 주입 +1,992)
  - "알수없는종목명" → chart_failures=['ticker_resolve_failed:알수없는종목명'] / system_prompt_chars=29,482 (chart 미주입, 정직 표기)
- ✅ KIS process-wide 토큰 공유 검증 (이전 RuntimeError = "1분당 1회" 해소, 5 영업일 DB cache hit 정상 동작)

## 의도적으로 안 한 것

- **claude_code silent HTTP 500** — provider="claude_code" 시 body 빈 message 의 500 발생. mock/gemini 정상. 이전 사용자 webapp 호출 시는 작동했음 (`[claude_code] · ... · 63.4s`). 원인 진단은 별도 사이클 (백로그). 본 사이클 = mock provider 로 chart 흐름 검증으로 충분.
- **`scripts/ask_analyst.py` CLI 의 `--target` 플래그** — RESUME 잔여. webapp 으로 검증 가능하므로 미루어둠.
- **종목명 매핑의 KRX 마스터 자동 sync** — 시총 상위 35종 하드코드는 일상 종목 커버. 동적 sync 는 별도 SPEC `INFRA-TICKER-RESOLVER-001` 후속 (백로그).
- **alias / 약칭 매핑** (삼전/네카오 등) — 정식 한글명만. 사용자 일상 어휘 데이터 쌓이면 보강.
- **gemini quota** 일일 free tier 20 req 소진 발견 — 환경 제약, 코드 변경 X.

## 다음에 이어서 할 작업 (우선순위)

1. **claude_code provider silent HTTP 500 진단** (~0.3 세션) — 새 발견. body=`{"detail":"inference failed: "}` (메시지 빈 string). mock/gemini 정상이라 claude_code subprocess 특정 실패. `core/llm/claude_code_backend.py` 의 exception 메시지 캡처 보강 + server log stderr trace 확인. cycle 6.5 production 시연 중 발견. webapp 사용자 호출에선 작동한 적 있으므로 일시적 또는 burst 한도 가능성.

2. **`ask_strategist`/`chat_strategist` httpx wrap** (~0.4 세션, 기존 Top 2 본체) — `scripts/ask_strategist.py`/`scripts/chat_strategist.py` 가 in-process `run_strategist` 임포트 → `POST /api/strategists/{id}/chat` httpx wrap. cycle 4 partial 의 `ask_analyst` 패턴 미러. `tests/test_ask_strategist_http.py` 신규. cycle 3 같은 메모리 압박 위험 잔존 제거.

3. **`operational_safeguards` 권위 SPEC 정정** (~0.2 세션, 기존 Top 3) — `ANALYST-PERSONAS-001` v2 매핑 표가 `operational_safeguards` 를 `trader` canon 으로 박았으나 실제 frontmatter `analyst: principle_guardian` + 본문은 principle_guardian verdict 알고리즘. SPEC v2 매핑 표 수정 + 회귀 테스트 갱신 + canon dir frontmatter 일관성 검사.

## 맥락 재진입 힌트

- **MS3 production smoke 완전 통과** — INFRA-CHART-DATA-001 구현 + KIS 토큰 공유 + API target_ticker + 종목명 매핑 4 본질 흐름 모두 검증. 사용자 webapp 호출 시 `종목` 필드에 한글 "삼성전자" 입력 시 자동 변환 + chart_data_md [4] 자동 주입 + MetadataBar 에 chart 메타 표시.
- **KIS 토큰 공유 패턴** — KISClient class-level `_shared_token` + `_get_token_lock` (lazy asyncio.Lock). 같은 process 내 모든 인스턴스 reuse. 24h 만료까지. snapshot.py + charts.py 가 각자 KISClient 만들어도 토큰 1번만 발급.
- **resolve_ticker 사용법** — `core.inference.run_analyst.resolve_ticker("삼성전자")` → `("005930", "삼성전자")`. 6자리 ticker / 한글 종목명 / 공백·대소문자 정규화 모두 지원. 미매핑 시 `(None, raw)`.
- **webapp ChatPane 컴포넌트** — `kind`, `title`, `agents`, `defaultAgentId`, `provider`, `showTickerField` props. 분할 화면 + 추가 분석가/전략가 옵션 추가는 `webapp/src/app/analyst-chat/page.tsx` 의 ANALYSTS/STRATEGISTS const 만 수정.
- **사용자 자율 의사 표명** — "테스트 항상 승인" + "uv 시작 명령 항상 수행" + "자러 가니 다 만들어놓아" 패턴. 자율 실행 시 자율 결정 박고 진입 OK (단, 본질 결정·destructive 액션은 묻기).

## 세션 중 실 비용

- gemini-2.5-flash production smoke 호출 ~3 회 (사용자 webapp 1 + 내 httpx 2): 합 ~$0.005 + gemini 일일 free tier 20 req 소진
- claude_code 호출 1 회 (사용자 webapp): $0 (Pro/Max 구독)
- mock provider 시연 2 회: $0

## 커밋 상태

- 코드 변경 6 파일 commit + push 완료: `27d788c` "feat: production smoke 보강 — KIS 토큰 공유 + API target_ticker + webapp 분할/select + 종목명 매핑 (cycle 6.5)"
- 본 wrap-up commit (c_worked + RESUME + SESSIONS) 진행
