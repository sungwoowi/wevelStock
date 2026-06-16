---
date: 2026-06-16
topic: TRADE-PLAN-LIFECYCLE B-MS1 (결정론 다단 가격대 메뉴) 구현·라이브 + 다층 진입 단계 체계 SPEC
status: completed
plan_file: C:\Users\HOME\.claude\plans\drifting-zooming-feather.md
---

# 2026-06-16 · 트레이드 플랜 다단 메뉴(B-MS1) + 다층 진입 단계 funnel 설계

## 배경
/resume → TRADE-PLAN-LIFECYCLE 1단계 착수 직전, 사용자가 구현 철학 재점검: "매매 기준을 결정론에 하나하나
박는 게 의미 있나? 끝없는데. 차트는 어차피 LLM에 다 주는데 LLM이 판단하고 돌려보고 자가진화로 매꾸는
애자일이 낫지 않나?" → **합의: B→C 애자일 합본.** 결정론은 *객관 가격대 계산기*(후보 메뉴)일 뿐, 선택·조합은
LLM. 끝없는 "선택 룰 박기"는 안 함. 소수의 절대 가드레일(오닐 −7%·종가기준)만 결정론 강제. 환각은 "숫자
출처=결정론", 잦은 변경은 deviation 로그 + 측정 루프(C)로 막힘.

## 한 일
- `core/signal/trade_plan_menu.py` (신규) — 순수 모듈. TradePlanConfig/Inputs/Menu + `build_trade_plan_menu`(다단 손절/지지/저항/목표 후보 + 분할매수·매도 사다리) + `trade_plan_inputs_from_ohlcv`(어댑터, extract_swing/compute_indicators/_atr 재사용) + `render_trade_plan_menu_md` + `clamp_stop_to_oneill`·`is_menu_bound` 가드레일 + `_dedup_levels`(동일가 중복 제거) + stale 스윙저점 제외.
- `core/strategist/run_strategist.py` — `run_strategist(trade_plan_menu_md=)` 파라미터 추가 → scores_md 연결(alpha_posture 옆).
- `core/strategist/recommendation.py` — 파서가 다단 필드(scaled_buy/scaled_sell/stop_basis/stop_label/deviation_reason) → `data.trade_plan` 가산. 하위호환 유지.
- `core/signal/auto_signal.py` — funnel 배선: OHLCV→메뉴 빌드→md 주입→`data.trade_plan_menu` 영속 + `_apply_trade_plan_guardrails`(−7% clamp + menu_bound 감사).
- `collectors/screening.py` — `load_trade_plan_config()` (watchdog hot-reload).
- `config/screening.yaml` — `trade_plan` 섹션 (오닐·ATR·사다리·dedup·stale 임계, 전부 SLOT).
- `agents/strategists/track_a|track_b/persona.md` — 다단 발행 지시(메뉴에서 선택·조합, 숫자 발명 금지, −7%·종가 절대 룰) + YAML 예시에 scaled_buy/sell 추가.
- `tests/test_trade_plan_menu.py` (신규, 19) + `test_strategist_recommendation.py`(+2 다단 파싱) + `test_auto_signal.py`(+1 주입·영속·clamp 배선).
- `scripts/_trade_plan_probe.py` (신규) — 라이브 검증 프로브.
- `docs/specs/TRADE-PLAN-LIFECYCLE-001-*.md` — status draft→**implementing**, 1단계 generates/modifies 확정 + **다층 진입 단계(관심→매수대기→buy) 설계 박음**: 상태 모델 확장, legible funnel 섹션, 로드맵 재배열(2단계=매수대기 단계 격상, 단계 라벨·영속·UI 신설).

## 검증 결과
- ✅ TDD: trade_plan_menu 19 GREEN, 전체 **1275 passed**(+22, 회귀 0). validate 0 errors.
- ✅ 라이브 (실 Gemini, 000660 Track A): LLM이 메뉴 소비 → stop=2,198,520(메뉴 −7% floor 정확), stop_basis=close, stop_label="오닐 −7% 절대". **환각 0** = 가드레일 있는 C 작동. verdict=hold(F-Score 3.0 약수급 근거).
- ✅ 라이브가 메뉴 버그 2개 잡아냄 → 즉시 수정: stale 스윙저점(2.36M인데 808K) 제외 + 동일가(스윙고점==52주고가) dedup. 재검증 메뉴 깨끗.
- ⚠️ buy 케이스 미관측: 4종(신세계·삼성·현대차·SK텔레콤) + watchlist 전체 = **전부 wait/hold**. 오늘 국장 분산 방어국면(Distribution Day 5, 약수급)이라 정상 — 코드 아닌 시황. buy 풀 사다리는 모멘텀 장에서 cron이 자동 채움.

## 의도적으로 안 한 것
- 결정론 "선택 머신"(상황별 손절 룰 트리) — B→C 합의로 LLM+진화 영역. 안 만듦.
- anchor_b(measured-move 목표) 미배선 → 목표후보=과거 고점만. 신고가권 목표 한계 = 3단계.
- run_strategist_stream(채팅) 미주입 — funnel(non-stream)만. 채팅 경로는 alpha_posture도 미배선.

## 다음에 이어서 할 작업 (우선순위)
1. **2단계 = 매수대기 *단계* (대기진입가 + 승격사유 + 라벨)** — funnel의 가장 빈 칸·가치 최대. `alpha_posture.conditional_entry` 채우기(눌림/돌파/추세하단 방법선택+가격, compute_scorecard에 price/ma) + wait→"매수대기" 라벨·승격사유 파생 + 진입 시나리오 시계열.
2. **3단계 = 목표 + 분할매도** — measured-move(anchor_b) 결정론 후보 + LLM 수정 + **신고가권=목표 열림/trailing**(현대차 사례) + 분할매도 AND.
3. **M3b (BRAIN-ALPHA-FLEXIBILITY 잔여)** — sector_rs·wave LLM 입력 → 약세장 bear_override. 오늘 "전 종목 wait" = regime 극보수 재확인, 이 영역.

## 맥락 재진입 힌트
- **핵심 원칙(불변)**: 결정론=객관 가격대 *계산기*(후보 메뉴), 결정자 아님 / LLM=선택·조합·임계·수정. "결정론이 다 맞춰야 하나"=영원히 아니오. = alpha_posture "가드레일 있는 C"의 일반화.
- **다층 단계 = 파생 라벨**: 관심(watchlist+점수)→매수대기(wait+근접+conditional_entry)→buy(verdict). 새 판단 아니라 *이미 있는 판단을 조립·표면화*. "재료는 다 있고 연결만 없다." legibility=쓰는 데스크 차별화.
- 라이브 LLM = Gemini만(claude_code 폴백 죽음). 오늘 한 번 월 spend cap 429 났다가 사용자가 한도 올림.

## 커밋 상태
- 세션 중 미커밋(코드+SPEC) → 이 wrap-up이 전체 1커밋 + main FF + push 예정.
