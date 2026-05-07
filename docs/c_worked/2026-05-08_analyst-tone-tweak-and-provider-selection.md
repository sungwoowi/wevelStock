---
date: 2026-05-08
topic: 단계 1 자산전략가 톤 직설화 + LLM provider 선택 옵션 (CLI/API/webapp)
status: completed
plan_file: C:\Users\HOME\.claude\plans\kind-tumbling-squirrel.md
---

# 2026-05-08 · 자산전략가 톤 + LLM provider 선택

## 배경

전 세션 M3 검증 결과 자산전략가가 framework 명제 인용만 반복하는 패턴 발견 (다음 세션 Top 1). user_want_spec "분석팀에 도움이 되는 raw data" 본질 직결. 단계 1 (persona 톤·temp) 시도. 도중 Gemini 503 재발 + claude_code Windows·OAuth 결함 3건 노출 → 인프라 동시 정비. 사용자 추가 요청으로 **자동 fallback 외 명시 provider 선택** (Gemini/Claude Code 톤 비교) 까지 확장.

## 한 일

### 단계 1 — persona 톤·temp 조정
- `agents/analysts/wealth_strategist/persona.md` — L32 "명제 문장 그대로 인용" → "명제 ID 인용 필수, 설명·사례·적용은 사용자 맥락에 맞게 재구성" / L34 인접 명제 추론 허용 ("직접 답은 아니나 인접 명제로 추론하면…")
- `agents/analysts/wealth_strategist/manifest.yaml` — temperature 0.4 → 0.7 + response_rules 정합 갱신

### LLM 안정화 (3 결함 동시 해결)
- `core/llm/client.py` — `_dispatch_provider` 의 gemini except 분기에 claude_code 시도 삽입 (gemini → claude_code → mock 폴백 체인). `provider` kwarg + `allow_fallback` 플래그 추가
- `core/llm/claude_code_backend.py` — Windows cmd.exe argv 8K 한계 우회 (`system_text > 7K + Windows` → argv 비우고 stdin `[SYSTEM]/[USER]` 결합 전송) + `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` env strip (Pro/Max keychain OAuth 강제)

### Provider 선택 옵션 (CLI/API/webapp 3 채널 + 동적 라벨)
- `core/inference/run_analyst.py` — `provider` kwarg 패스스루 + metadata 에 `provider_requested`/`provider_used` 표면
- `scripts/ask_analyst.py` — argparse + `--provider {gemini,claude_code,anthropic,mock}`
- `scripts/chat_analyst.py` — argparse + `--provider` (conversation 단위 락) + meta 라인에 `[provider_used]` prefix
- `server/api/analyst_chat.py` — `ChatRequest.provider` Literal 필드
- `server/api/config.py` — **GET `/api/config/llm`** 신규 (현재 provider/model/fallback_chain 반환)
- `webapp/src/app/analyst-chat/page.tsx` — LLM 토글 3개 + `/api/config/llm` mount fetch 로 "자동 (gemini-2.5-flash)" 동적 라벨 + MetadataBar 에 `[provider_used ← req:provider_requested]` 표시
- `justfile` — `chat`/`ask` 가 `*flags=""` 받음 (`--provider` 패스스루)

### 사용자 피드백 메모리 1건
- `memory/feedback_ask_before_architecture_change.md` — fallback chain·옵션 분기 같은 구조적 결정은 사용자 명시 OK 후. 단순 치환으로 가지 말 것 (이번 세션 실수 흡수)

## 검증 결과
- ✅ pytest 60 passed (회귀 3회 모두)
- ✅ Next.js build 성공 (analyst-chat route 3.18 → 3.29 kB)
- ✅ 단계 1 톤 변화 사용자 검증 — "원달러 1500원" 질문에 인접 명제 추론 ("I6 평균가 회귀 가정 위험 → 분산 매집 전환") + "삼성전자 사면" 자산 비중 관점 재구성 동작
- ✅ provider 토글 검증 — Claude Code (Sonnet 4.6) 직설·단호·T-style / Gemini (2.5 Flash) 구조적·다각적 톤 분기 확인
- ✅ `/api/config/llm` 응답 정상 — `{"provider":"gemini","model":"gemini-2.5-flash","fallback_chain":["gemini","claude_code","mock"]}`
- ✅ claude_code OAuth 경로 — env 키 strip 후 Pro/Max 구독 인증으로 401 해결, cache hit 14,795 토큰 적중

## 의도적으로 안 한 것
- **단계 2 (시장 스냅샷 자동 주입)** — 사용자 결정으로 다음 세션 Top 1 으로 이월. `collectors/snapshot.py` + 5분 캐시 + `compose.py` 블록 주입 (1~1.5h)
- **claude_code cost 표시 라벨링** — Pro/Max 구독은 호출당 추가 비용 0인데 metadata 가 토큰 환산 $0.14 표시 (UX 백로그)
- **runtime.yaml 의 provider 변경** — 사용자 의도 대로 `gemini` 그대로 유지 (자동 폴백만 강화)

## 맥락 재진입 힌트
- Gemini 503 재발 시 자동으로 claude_code 폴백 (raw 에 `fallback_used: claude_code` 박힘). webapp 메타바에서 확인 가능
- Provider 선택 시 자동 폴백 X — 명시한 backend 가 실패하면 그대로 에러 노출 (의도)
- 단계 2 설계 = `collectors/snapshot.py` `async def build_market_snapshot(*, kis, krx, max_age_seconds=300) -> tuple[dict, bool]`. 5분 인메모리 캐시 + 신선 콜 시 stderr "[수집 중... ~30s]" 표시 / 캐시 히트 시 무표시 (사용자 요청 UX)

## 다음에 이어서 할 작업 (우선순위)

1. **단계 2 — 시장 스냅샷 자동 주입** (PC, 1~1.5h)
   - 왜: 단계 1 톤 변화는 살아남았으나 응답이 여전히 framework 적용에만 머물고 실제 수치 결합 안 됨. 본질 (오감+뇌) 직결
   - 범위: `collectors/snapshot.py` 신규 (8 collector 병렬 + 5분 캐시 + cache_hit 반환), `compose.py:build_pipeline_prompt` RAG 직전 새 블록, run_analyst metadata 에 `snapshot_age_seconds`/`snapshot_fetch_seconds`, CLI/webapp 진행 표시 ("[시장 스냅샷 수집 중... ~30s]")

2. **나머지 4명 분석가 분화** (PC, 2~3h)
   - 왜: 단계 1 + provider 선택 패턴 검증 끝남. 같은 manifest+persona 패턴으로 4명 복사. 매매코치 추가하면 자산전략가와 톤 비교로 분화 의미 즉시 입증
   - 범위: `agents/analysts/{principle_guardian, trade_coach, stock_analyst, news_curator}/{persona.md, manifest.yaml}` 4 set. 각 manifest `reads:` 학습부별 다름

3. **claude_code cost 라벨 + analyst-chat SSR 깜빡임** (PC, 30분)
   - 왜: Pro/Max 사용자가 webapp 에서 $0.14 보고 오해할 소지. SSR 첫 렌더 "분석가 메타 로드 실패" 빨간 텍스트도 누적
   - 범위: MetadataBar 에서 `provider_used==claude_code` 면 "$0 (subscription)" 라벨 / SSR 가드

추가 백로그 (이전 세션 그대로 유지):
- 종목분석부 자료 ingest + JSONL 매월 폴더 + 90일 retention cron
- NXT 통합 시세 SPEC, daily_briefing legacy 청소, 박종훈 Vol 2/3 OCR

## 커밋 상태
- ✅ 3 commits — `db875e8 feat(wealth_strategist)` / `af4f7e4 feat(llm)` / `a087744 feat(inference)`
- main 3 ahead of origin/main. push 미실시 (사용자 명시 시 실행)

## 세션 중 실 비용
- Gemini 호출 5~6회 × ~$0.0014 = ~$0.008
- Claude Code 호출 2회 (Pro/Max 구독 흡수, 실 비용 $0)
- 총: 약 $0.008 (Gemini)
