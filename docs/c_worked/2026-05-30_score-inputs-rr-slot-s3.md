---
date: 2026-05-30
topic: INFRA-SCORE-INPUTS-001 SLOT S3 (R/R 산출) 구현 + risk-cap 품질 개선 + 라이브 검증 (같은 날 3번째 세션)
status: completed
plan_file: C:\Users\HOME\.claude\plans\effervescent-dazzling-goblet.md
---

# 2026-05-30 · SLOT S3 R/R 산출 (스윙+ATR risk-cap) + 라이브 smoke

## 배경
같은 날 2번째 세션이 INFRA-SCORE-INPUTS-001 MVP(T/F-Score 원시 지표 배선)를 구현했으나 R/R 축이 미산출(`rr=None`→advisory 중립)이라 T-Score 4축 중 1축이 비어 있었고, 배선이 단위·hook 테스트로만 검증됨. 본 세션은 둘을 닫음 — R/R 결정론 규칙(SLOT S3) 1개 구현 + 라이브 LLM smoke. **핵심 판단**: 진입/손절/목표는 원래 trader·전략가의 출력이라 collector R/R 은 어디까지나 **advisory 참고선**(LLM override 가능)임을 분명히 한 채 결정론 baseline 계산. 사용자 결정 = **스윙+ATR 하이브리드**.

## 한 일
- `collectors/technicals.py` — `_atr(df, period)`(True Range 평균) + `compute_rr(df, price, ...)` 순수 함수 신설. 진입=현재가, 손절=직전 스윙저점(`anchors.extract_swing_candidates` 재사용)을 `[atr_k_floor, atr_k_cap]×ATR` risk 밴드로 **clamp**, 목표=인근 스윙고점(없으면 52주 고가). 신고가권·risk≤0 → `None`+사유. `build_technicals` 가 non-cutoff 경로에도 `load_ohlcv_from_db` 로 df 확보 후 rr 배선.
- `config/score_inputs.yaml` — `technicals.rr_rule` 블록 신설(`atr_period:14`, `atr_k_floor:1.5`, `atr_k_cap:3.0`, `swing_timeframe:daily`). 하드코딩 금지·watchdog 반영.
- `collectors/score_inputs_config.py` — `get_rr_rule()` 로더(default 병합, `get_breakpoints` 패턴 mirror).
- `tests/test_technicals.py` — `_atr` 2 + `compute_rr` 5(스윙 clamp 정합 / cap 발동 / 신고가→None / no-price→None / deterministic).
- `tests/test_score_inputs_config.py` — `get_rr_rule` 2(타입·키 정합).

## 라이브 품질 검증 (실 LLM + KIS, 사용자 승인)
- 첫 라이브 호출(005930 swing)에서 **R/R 0.04 왜곡 발견** → 원인: 수직급등주(167k→317k)는 직전 스윙저점이 -47% 멀어 `min(스윙, ATR)` 이 risk 폭발. 손절 167,300(-47%) → target 323,000(+1.9%) → rr 0.04.
- **수정**: 손절을 `[1.5, 3.0]×ATR` risk 밴드로 clamp(floor=잔파동 털림 방지, cap=급등주 폭발 방지). 사용자 확인 후 적용.
- **재검증(서버 재시작 후 라이브)**: 005930 R/R **0.10**(risk -19.1%), `is_mock:False`/gemini/`technicals_failures:[]`. trader 가 R/R 0.10 을 확신도 95%로 박고 **advisory T-Score(5.0) 무시·R/R 로 직접 skip 판단** — "원시 지표=권위 / advisory=참고선" end-to-end 작동 확인.

## 검증 결과
- ✅ pytest **667 → 677 passed** (+10, 회귀 0)
- ✅ `validate.py` 0 errors (1 warning = teams/registry.yaml 무관)
- ✅ 라이브 005930 R/R 0.04→0.10 (서버 신규 코드 반영 확인)

## 의도적으로 안 한 것
- **ATH 근처 목표 과소평가**(돌파 시 열린 상단 = 인근 스윙고점이 목표라 과소) — 판단 무거운 설계(measured-move 등) → SLOT S3 튜닝 이연, trader override 로 비차단.
- **floor/cap·breakpoints production 분포 튜닝** — placeholder 유지(SLOT S2/S3 후속).
- 서버 lifecycle — 포트 8000 고아 소켓 + Telegram Conflict(중복 봇) 정리는 사용자 수동 처리(메모리 신규).

## 기술 부채/미완
- ATH 근처 목표 과소평가(위) — 가장 큰 R/R 정확도 잔여 약점.
- F-Score 종목 레벨 수급 미배선(시장 프록시만, 직전 세션 유지) / theme_match 중립(SLOT S1).
- pytest_safety hook 오탐 / validate cp949(둘 다 기존 부채 유지).

## 맥락 재진입 힌트
- R/R 규칙 = `compute_rr` 의 clamp 밴드. 임계 조정은 `config/score_inputs.yaml::technicals.rr_rule` 만 수정(코드 무판단, watchdog).
- 라이브 호출 = `POST /api/analysts/trader/chat` body `{messages, target_ticker}`, 응답 = `{text, metadata}`(top-level). 서버 코드 수정 후 **재시작 필수**(hot reload 불신).

## 다음에 이어서 할 작업 (우선순위)
1. **SLOT S1 theme_match 2-Stage 하이브리드** — F-Score 최대 가중 축(0.4)이 현재 중립. 종목 테마↔권위 주체 결정론 candidate + LLM 선택 + 캐싱 + manual override (`feedback_llm_intuition_distribution` 첫 적용). `collectors/flow_inputs.py` theme_match 축 배선.
2. **SLOT S2 매핑 임계 + SLOT S3 목표 정밀화** — `score_inputs.yaml` breakpoints·rr_rule floor/cap 을 실 분포로 튜닝 + ATH 근처 목표 measured-move 보강.
3. **buy_score/S-Score 후속 배선** — 나머지 점수 같은 α-mirror 패턴 배선(rs는 SCREEN-RS-EXTENSION-001).

## 커밋 상태
- 코드(`technicals.py`/`score_inputs_config.py`/`score_inputs.yaml`/tests 2) = 본 wrap-up 에서 커밋·push 예정 (main 직접, 솔로 프로젝트).
