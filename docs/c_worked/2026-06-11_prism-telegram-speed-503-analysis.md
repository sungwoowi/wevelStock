---
date: 2026-06-11
topic: Gemini 503 진단 + prism-insight 텔레그램 응답속도 코드 분석 (조사 세션)
status: completed
---

# 2026-06-11 · Gemini 503 진단 + prism 텔레그램 속도 분석

## 배경
cron 로그에 Gemini 503 warning 8건이 동시에 찍혀 사용자가 원인·심각도를 물음. 이어서 "prism-insight 는 분석가가 더 많은데 왜 텔레그램 답변이 20~30초로 빠른가 (대신 환각 있음)" — 추측 금지, 코드 확인 요청. 핵심 판단: **503 = 피해 0 (조치 불필요)** + **prism 속도 = 사용자 경로에 multi-agent 없음 (우리 DB-first 패턴과 동일)**.

## 한 일
- `idea_memo/prism-insight-텔레그램-응답속도-분석.md` — 신규. prism shallow clone 후 응답 경로 코드 추적 결과 영구 기록 (이전 세션 커밋 a17ff79 에 이미 포함됨)
- 코드 변경 없음 (조사/진단 세션)

### 진단 결과 (이 세션의 산출 = 지식)
1. **Gemini 503**: 유료 tier 는 쿼터(429)만 올려주고 서버 용량은 보장 안 함. cron 이 분석가 8명을 같은 밀리초에 fan-out → 동시 8발이 전부 503 순간을 맞음. 전부 attempt=1 재시도 성공, `llm_call_failed` 0건 → **조치 불필요**. `AFC is enabled...` 로그 = google-genai SDK 의 Automatic Function Calling 안내 (노이즈, `logging.getLogger("google_genai.models").setLevel(logging.WARNING)` 로 끌 수 있음)
2. **prism 503 대응**: ① Sequential 실행 ("rate limit friendly" 문서 명시) ② Gemini 미사용 (GPT-5 + Claude Sonnet). retry/backoff 코드 없음 — 우리 3회 retry + claude_code 폴백이 구조적으로 더 강함
3. **prism 텔레그램 20~30초의 정체** (`report_generator.py` 코드 확인):
   - 13-agent orchestrator = 배치 전용, md 파일 저장. `/report` = 24h 파일 캐시 hit 시 **LLM 0콜**
   - `/evaluate` = `generate_evaluation_response()` — **Sonnet 4.6 단일 1콜** + MCP 도구(perplexity/OHLCV/time) 왕복. 캐시 보고서를 프롬프트에 통째 주입
   - 환각의 원인 = 같은 경로: 검증 레이어·결정론 점수 없이 LLM 혼자 검색→해석→수익률 계산. "년도를 꼭 참고하세요" 3회 반복 = 날짜 환각과 싸운 흔적

## 검증 결과
- ✅ prism-insight shallow clone (`%TEMP%\prism-insight`) 후 `telegram_ai_bot.py`(3121줄) + `report_generator.py:351,756~933` 직접 읽어 확인 — 추측 아닌 코드 근거
- ✅ 우리 retry 로직 확인: `core/llm/client.py:451~468` (3회, 0.8s×n backoff, 503/UNAVAILABLE transient 분류)

## 다음에 이어서 할 작업 (우선순위)
1. **PAPER-DESK-UX 화면 구현 이어가기** — .pen 드래프트(2026-06-10) 다음 단계. 이번 세션이 설계 원칙 보강: **사용자 경로에서 분석가 fan-out 실시간 금지, 미리 계산된 team_outputs read + 서술 1콜** (prism 검증 패턴과 동일 구조)
2. **라이브 청산 cron organic 누적 관찰** — RB-MS2 verified 마감용. 방어장 wait 지속 중, 청산 데이터 쌓이면 RIGHT-BRAIN 잔여 3 자식 verified 전환
3. **(조건부) LLM 호출 semaphore** — `llm_call_failed` (3회 전부 실패) 가 실제 로그에 보일 때만: 동시 LLM 호출 3~4개 제한. full sequential 은 과잉 대응이라 배제 결정

## 커밋 상태
- idea_memo 파일: 이미 커밋됨 (a17ff79 에 포함)
- 본 wrap-up 기록: 이 세션에서 커밋 예정
