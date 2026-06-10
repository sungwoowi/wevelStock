# prism-insight 텔레그램 응답 속도 분석 (코드 확인)

> 작성: 2026-06-10
> 맥락: "prism 은 텔레그램 답변이 왜 20~30초로 빠른가? (대신 환각 있음)" — 추측 아닌 실제 코드 확인 결과
> 확인 방법: `dragon1086/prism-insight` shallow clone 후 응답 경로 직접 추적
> 위치: SPEC 아님, **아이디어 백로그**. PAPER-DESK-UX / production 채팅 설계 시 참조

---

## 1. 결론 (한 줄)

**13-agent 파이프라인이 사용자 응답 경로에 아예 없다.** 무거운 분석은 배치(cron)가 미리 md 파일로 저장하고, 텔레그램 질문은 **Sonnet 4.6 단일 1콜**(캐시 보고서 프롬프트 주입 + MCP 도구 3~4회 왕복)로 처리. 빠름과 환각은 같은 설계의 양면.

---

## 2. 코드 증거

| # | 사실 | 위치 |
|---|---|---|
| 1 | 13+ agent orchestrator 는 아침/오후 **배치 전용**, 결과를 `{코드}_{회사명}_{날짜}_analysis.md` 파일로 저장 | `stock_analysis_orchestrator.py` |
| 2 | `/report` 는 `get_cached_report()` 가 **24시간 이내 md 캐시 hit 시 LLM 0콜** 즉시 전송 | `report_generator.py:351` |
| 3 | `/evaluate` (사용자 평가 질문) = `generate_evaluation_response()` — agent 1개 → `attach_llm(AnthropicAugmentedLLM)` → `generate_str(model="claude-sonnet-4-6", maxTokens=8000)` **1콜이 전부** | `report_generator.py:756~933` |
| 4 | 캐시 보고서가 있으면 프롬프트에 **통째로 붙여넣어** 참고 자료로 주입 | `report_generator.py:917~927` |
| 5 | 그 1콜 안에서 MCP 도구(perplexity / kospi_kosdaq OHLCV / time) 왕복 → 20~30초의 정체 | `report_generator.py:910` |
| 6 | 후속 질문도 동일하게 단일 1콜 (`generate_follow_up_response`) | `report_generator.py` |

### 환각의 구조적 원인 (같은 경로)

- 캐시 보고서 없으면: *"시장 데이터 조회와 perplexity 검색을 통해 최신 정보를 수집하여 평가해주세요"* (`report_generator.py:927`) — **검증 레이어 없이 LLM 혼자 검색→해석→계산 한 방에**.
- 수익률 계산도 프롬프트로 LLM 에게 위임 ("극단값이면 재검증하세요" 수준의 부탁).
- 날짜 환각과 싸운 흔적: "년도를 꼭 참고하세요" 가 프롬프트에 3회 반복.
- 결정론 점수·교차 검증·검증 agent 전무 (evaluator/optimizer agent 는 채널 요약 전용, Q&A 경로 아님).

---

## 3. 부수 확인: 503 / rate limit 대응 (이전 질문 연장)

- prism 의 rate limit 해법 = **① Sequential 실행** ("Sequential execution (rate limit friendly)" 문서 명시) + **② Gemini 미사용** (분석/전략 GPT-5, 상담 Claude Sonnet).
- retry/backoff 코드 없음 — OpenAI SDK 내장 재시도 의존. **wevelStock 의 3회 retry + claude_code 폴백 체인이 구조적으로 더 강함.**
- 호출량 자체는 prism 이 더 많음 (13+ agent × GPT-5). 차이는 양이 아니라 **동시성** (우리 8발 동시 vs prism 1발씩).

---

## 4. wevelStock 시사점

1. **속도 비결 = 우리가 이미 깔아둔 패턴과 동일**: "무거운 분석은 cron 미리 계산 + 저장, 사용자 경로는 저장 결과 read + 가벼운 서술 1콜" = 우리의 DB-first 스냅샷 + `team_outputs` read + 전략가 종합 구조.
2. **차이**: prism 은 환각을 감수하고 검증을 뺐고, 우리는 결정론 점수(산정=코드)를 LLM 에 구조 주입(`render_prefetched_analyst_outputs`)해 그 환각 축을 막음.
3. **PAPER-DESK-UX / production 채팅 설계 원칙**: 미리 계산된 team_outputs read + 서술 1콜 유지 → 속도는 따라오고 환각 축은 이미 차단. 사용자 경로에서 분석가 fan-out 을 실시간으로 돌리지 말 것.
4. 503 대응은 현행 유지. 실제 `llm_call_failed` 가 보이기 시작하면 그때 **LLM 호출 semaphore (동시 3~4개 제한)** 한 가지만 도입 (full sequential 은 병렬 아키텍처 장점 버리는 과잉 대응).
