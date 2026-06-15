---
date: 2026-06-15
topic: BRAIN-ALPHA-FLEXIBILITY-001 M2 persona doctrine 전환 + M3a funnel 결정론 배선
status: partial
plan_file: C:\Users\HOME\.claude\plans\dapper-hopping-volcano.md
---

# 2026-06-15 (4) · 두뇌 알파 유연성 M2 + M3a

## 배경
M1(결정론 차등 변조 alpha_posture)은 verdict 후보만 만들고 funnel·persona 에 미배선이라
라이브 무영향이었다. 이번 세션 = 그 후보를 **전략가 프롬프트에 주입 + 권고에 영속**하고
persona doctrine 을 **regime 범주 게이트 폐기 → 후보 소비자 + 사실근거 deviation 로그**로 전환.
핵심 판단: sector_rs·wave 는 LLM(Haiku) 입력이라 다음 마일스톤으로 미루고, 오늘 버그(strong_bull
전부 wait)의 bullish 경로는 결정론(rs/ext)만으로 즉시 탈피되므로 **결정론 절반(M3a) 먼저**.

## 한 일
- `core/signal/alpha_posture.py` — `render_alpha_posture_md(posture)` 순수 함수 추가(전략가 주입 md: verdict 후보·regime_class·변조 추적·선정 사유·조건부 진입 + deviation 규칙 지시).
- `core/signal/auto_signal.py` — Scorecard 에 `rs_score`·`extension_score`·`sector_rs_score`·`wave_alive` 필드 + `posture_inputs_from_scorecard` 헬퍼 + `run_signal_for_ticker` 가 posture derive→`alpha_posture_md` 주입→`rec.data["alpha_posture"]` 영속 + `run_signal_cadence._process_ticker` 가 screen 행의 rs/ext 를 scorecard 에 주입(LLM 0).
- `core/strategist/run_strategist.py` — `run_strategist` 에 `alpha_posture_md` optional kwarg + 분석가 블록 뒤 주입(채팅 경로 None=무변, run_strategist_stream 은 미변경).
- `agents/strategists/track_a/persona.md` — 진입 조건 #4 regime 범주 게이트 폐기 → AlphaPosture 후보 소비 + 품질 확인 + deviation 규칙. YAML `data: llm_deviation_reason` 예시 + anti-pattern(blanket 강등 금지).
- `agents/strategists/track_b/persona.md` — 동(체제 게이트 완화) + **kill-switch(DD≥4) 보존**(deviation 불가 명시).
- `docs/specs/BRAIN-ALPHA-FLEXIBILITY-001-*.md` — 마일스톤 M1✅·M2✅·M3a✅·M3b⏳·라이브⏳ 표기.
- `tests/test_alpha_posture.py`(+3 render/deviation) · `tests/test_auto_signal.py`(+2 posture_inputs·주입/영속).

## 검증 결과
- ✅ TDD RED→GREEN: `tests/test_alpha_posture.py`+`tests/test_auto_signal.py` **92 passed**.
- ✅ 전체 **1247 passed, 0 실패**(직전 환경성 snapshot 3건도 이번엔 통과 — 시각 의존). 회귀 0.
- ✅ 신규 테이블·파서 변경 0(persist `**rec.data` 가산 + 파서 `data:` 수용 재사용).

## 의도적으로 안 한 것 (다음 마일스톤)
- **M3b** sector_rs(theme classify)·wave(anchors α→bool) 입력 — funnel 핫패스 LLM Haiku 추가. 약세장 bear_override·횡보 선별 활성화. 현재 None → bullish/neutral 차등만 동작.
- **라이브 검증**(실 Gemini) — strong_bull buy 후보 발생 실증. 비용·시간(차트 fetch 병목) 들어 사용자 선택으로 보류.
- conditional_entry 가격화 — M1 심볼릭 유지.

## 다음에 이어서 할 작업 (우선순위)
1. **라이브 검증** — 실 Gemini 1회(`run_auto_signal_job("intraday1")` 또는 probe): strong_bull 종목 buy 후보 ≥1 + `rec.data.alpha_posture` 확인 = "전부 wait" 탈피 실증. (서버/스냅샷 필요)
2. **M3b — sector_rs·wave 입력 배선** — `compute_scorecard` 에 종목 섹터 RS(`classify_theme`→`get_theme_sector_mapping`→sector_rs max)·파동 생존(`compute_alpha_3tf` weekly/daily label=="sweet"→bool) 추가(LLM Haiku 30일 캐시·graceful). 약세장 bear_override 활성화.
3. **M4 watchlist 선정 강화 + M5 웹 더블체크** — rank_candidates 가중에 파동/주도주/섹터RS + 미장 source / buy 후보 Gemini grounding + data_json 가산.

## 맥락 재진입 힌트
- 주입 경로: `run_strategist`(non-stream)만 `alpha_posture_md` 받음. `run_strategist_stream`(채팅)은 미배선 — 채팅에도 후보 주입하려면 stream 함수도 동일 패치 필요.
- 후보는 LLM verdict 와 무관하게 `rec.data["alpha_posture"]` 에 항상 영속(설명가능성·deviation 감사 기준). LLM 이 후보를 뒤집으면 `data: llm_deviation_reason` 에 사유가 남도록 persona 가 지시.
- 임계는 전부 SLOT — buy/wait 경계 빡세/느슨하면 `config/screening.yaml alpha_posture` 조정(코드 0, watchdog).

## 커밋 상태
- 세션 중 미커밋 → 이 wrap-up 이 코드(M2·M3a)+SPEC+문서 1커밋 + main(현 브랜치) + push 예정.
