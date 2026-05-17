---
date: 2026-05-17
topic: collectors/scoring.py 5 함수 결정론 채점 + wealth_strategist 잠정 풀이 4 정정 (M2/C1/I2/C3)
status: completed
plan_file: C:\Users\HOME\.claude\plans\glistening-crafting-bunny.md
---

# 2026-05-17 · scoring.py + 잠정 풀이 정정 (Top 2 첫 실체)

## 배경
오늘 두 번째 세션. 직전 세션이 v3.0 메타 아키텍처 재설계 (SPEC 3 + docs) 로 마쳤지만 코드 실체 0. 다음 본질 작업 = Track A persona 작성이지만, 페르소나 안에 `(S-Score=8, cited: [W1])` 양식이 박히려면 **점수 함수 시그니처가 먼저 잠겨야 안전**. 동시에 `wealth_strategist` persona/manifest 의 잠정 풀이 6 개가 canon 원문 frame 과 충돌 (2026-05-17 스모크에서 M2 잠정 "통화량 팽창 침식" vs LLM RAG "고령화·반도체 의존 30년" 식별) — Track A 직전 사전 부채 청산.

사용자 인터뷰에서 Top 2 → Top 1 순서 확정. 사이클 가시화 우선 vs 엔지니어링 정합의 trade-off 를 명시한 뒤 사용자가 "시그니처 잠금 먼저" 선택.

## 한 일
- `collectors/scoring.py` 신규 — 5 함수 결정론 채점 (`s_score` / `t_score` / `alpha` / `buy_score` / `f_score`). 모두 순수 함수 (LLM 호출 X), 0~10 + 0.5 단위, `_clamp` / `_round_to_half` / `_validate_unit_score` 헬퍼. 시그니처 = ANALYST-PERSONAS-001 SPEC 권위 그대로. **공식 정합**: F-Score = SPEC v2 명시 4 축 가중 합 (0.4·테마+0.3·모멘텀+0.2·자금속도+0.1·일치도) / α 오버라이드 = STRATEGY-TRACK-001 명시 (1.3-1.5/1.5-2.0/2.0+ 구간별 보정) 그대로. `t_score` 내부에서 α 인자 받아 적용. **placeholder**: s_score (3축 균등 평균) / buy_score (CAN SLIM 7축 균등 평균) / alpha 본체 (ln(C/B)/ln(B/A)) — 정식 공식은 분석가 manifest 작성 시 또는 WAVE-ALPHA-001 SPEC 에서 확정 (S7 SLOT)
- `tests/test_scoring.py` 신규 — 60 cases (5 함수 × happy + min + max + 0.5 단위 라운딩 + 입력 검증 (음수·10 초과·잘못된 타입) + 재현성 100~500회 반복 동일 + α 오버라이드 3 구간 boundary (1.3 / 1.5 / 2.0 정확값) + 전체 결정론 회귀 1 테스트)
- `agents/analysts/wealth_strategist/persona.md` — 자연어 양식 cited 풀이 (M2/C1/I2) + 격자 양식 cited 풀이 (M2/C3) **canon 원문 frame 으로 정정**. M2 = ~~"통화량 팽창 침식"~~ → **"원화 구조적 약세 (인구·산업)"** / C1 = ~~"단기·장기 사이클 중첩"~~ → **"부채 J커브 가속 곡선"** / I2 = ~~"실물 자산 헷지"~~ → **"달러 자산 50% (미국 주식+단기채)"** / C3 = ~~"부채 사이클 후반 디레버리징"~~ → **"위기는 짧고 결정적 (6개월~3년 반)"**. C5 / I6 는 canon 과 일치 → 유지
- `agents/analysts/wealth_strategist/manifest.yaml` — `response_rules` 인용 규칙 (v3.1) 예시 블록의 M2/C3 풀이 정정 (위와 동일 정정안). I6 유지

## 검증 결과
- ✅ `TESTING=1 PYTHONIOENCODING=utf-8 uv run pytest tests/ -q` → **195 passed** (135 → +60 신규 scoring, 회귀 0) in 47.32s
- ✅ `PYTHONIOENCODING=utf-8 uv run python scripts/validate.py` → 0 errors, 1 warning (registry.yaml 기존 무관)
- ✅ scoring 단독 회로 검증 `pytest tests/test_scoring.py -v` → 60 / 60 통과 in 0.53s (α 오버라이드 boundary 3 구간 + 재현성 500회 반복 동일 모두 통과)

## 의도적으로 안 한 것
- **SPEC `ANALYST-PERSONAS-001` line 207-212 격자 예시 표 정정** — 표 안 `| 부채 사이클 | 후반/디레버리징 | C3 |` + `| 통화 가치 | 침식 가속 | M2 |` 의 frame 축 자체가 canon 과 충돌이지만, 격자 5요소 표의 frame 축 재설계는 Track A persona 작성 세션에 통합 처리하는 게 자연 (페르소나의 격자 ground truth 와 SPEC 예시가 한 사이클 안에 같이 결정). 본 세션은 cited 풀이 정정만, SPEC 격자 표는 백로그
- **scoring 정식 공식 확정** — s_score (rs, supply_chain, alignment) / buy_score (c, a, n, s, l, i, m) 의 가중치 + alpha 본체 식 = 분석가 manifest 작성 시 또는 WAVE-ALPHA-001 SPEC 진입 시. 현재 placeholder (균등 평균) 로도 시그니처 잠금 충분
- **production 사이클 가시화** — scoring.py 는 호출처 0 (분석가 미 import). 사용자 → webapp → 답변 사이클 가시화는 다음 세션 Track A persona 작성부터. 본 세션 = 다음 세션 토대만

## 맥락 재진입 힌트
- **잠정 풀이 정정 패턴 정립**: persona/manifest 예시 박은 cited 풀이는 LLM 추종력으로 응답에 그대로 나간다 (검증된 행동). 박힌 풀이가 canon frame 과 충돌하면 사용자가 응답을 받아도 박종훈 강의 frame 매칭 안 됨. 패턴 = canon 원문 (`macro_roadmap/01-framework-manifesto.md` + `crisis_signals/01-survival-imperatives.md`) 과 1:1 grep 후 정정. 향후 8 분석가 페르소나 작성 시 동일 패턴 적용
- **결정론 함수 의도 동작 = production 사이클 변화 0 명시**: 사용자 "지금 뭐 수정한 거야? 기대 동작이 뭐지?" 질문에 production 사이클 변화 0 / 다음 세션 토대 잠금이라는 trade-off 솔직히 설명. 동일 패턴 (선행 부채 청산 vs 가시화 우선) trade-off 다음에 다시 등장 시 처음부터 명시
- **scoring 시그니처 = SPEC 권위 그대로**: `t_score(divergence, macd, volume, rr, alpha)` / `alpha(anchor_a, anchor_b, anchor_c, current)` / `buy_score(c, a, n, s, l, i, m)` / `f_score(theme_match, momentum, inflow_speed, agreement)` / `s_score(rs, supply_chain, alignment)`. Track A persona 작성 시 cited_scores 양식이 이 인자명 기반으로 박힘

## 다음에 이어서 할 작업 (우선순위)
1. **Track A persona.md + manifest.yaml + `core/strategist/run_strategist.py` 골격 (~2 세션)** — STRATEGY-TRACK-001 첫 실체, lean startup production 가치 검증. canon = 9 dept framework + market_snapshot + `team_outputs` DB read + RAG. manifest `input_routing` 블록 (`long:`/`core:`/`wave:` 단축어 + auto.conditions 월봉 7월선). webapp `analyst-chat/page.tsx` default agent = `track_a` 또는 `both` 교체. 동시에 SPEC `ANALYST-PERSONAS-001` line 207-212 격자 예시 frame 충돌도 같이 정정 (격자 표 ground truth 재설계)
2. **Track B persona.md + manifest.yaml + `core/strategist/track_selector.py` (~1.5 세션)** — Trigger Hunter 6 가지 + CAN SLIM buy_score + α 오버라이드 + trailing stop. Track Selector = manifest `input_routing` 동적 인식 + 우선순위 라우팅 (명시 단축어 > auto > fallback). 양 트랙 동시 평가 `both:` 지원
3. **자료 있는 3 분석가 페르소나 v2 양식 작성 (principle_guardian / trader / stock_analyst)** — Track A/B 안정 후. 8 섹션 portable + 한국어 친화 용어 강제 § + 결정론 채점 발행 매핑 (S/T/α/buy_score). 자료 있는 dept 3 (principles / trading / stock-analysis). canon 대조 후 잠정 풀이 박는 패턴 동일

(추가 백로그: 자료 0 시드 5 분석가 (market_state_analyzer / stock_picker / trading_journalist / flow_analyzer / news_curator) 페르소나 / `guidance_records` DB 마이그레이션 + `core/guidance/recorder.py` (STRATEGY-TRACK-001 권고 발행 시 자동 적재) / `INFRA-CHART-DATA-001` KIS 일봉 + pandas-ta + matplotlib vision (stock_analyst·trader 페르소나 직전 blocker) / `INFRA-US-MACRO-SNAPSHOT-001` 미 매크로 collector / `WAVE-ALPHA-001` Module A α 정식 공식 + scoring.py 본체 / Layer 4 계좌관리자 1+ N (M5) / Layer 5 회고분석가 SPEC (M4) / scoring s_score·buy_score 정식 가중치 / SPEC 격자 예시 표 frame 충돌 정정 (Track A 안)

## 커밋 상태
- 1 commit 진행 (코드 4 파일 + wrap-up 3 파일 묶음). 사용자 명시 = push 도 수행
