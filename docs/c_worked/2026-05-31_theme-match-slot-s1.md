---
date: 2026-05-31
topic: INFRA-SCORE-INPUTS-001 SLOT S1 — theme_match 2-Stage 하이브리드 골격 (시장 프록시 MVP)
status: completed
plan_file: C:\Users\HOME\.claude\plans\bright-wondering-raccoon.md
---

# 2026-05-31 · theme_match 2-Stage 골격 (F-Score 0.4 축)

## 배경
F-Score(수급 점수) 4축 중 **최대 가중(0.4) theme_match 가 중립(5.0)** 으로 박혀 있어 수급 점수에 종목 변별력이 없었다. theme_match = "이 종목 테마의 권위 주체(외인·기관·연기금·개인)가 실제로 순매수 중인가". 테마 분류는 결정론 공식이 안 떨어지는 직관 영역 → SLOT S1 = **2-Stage 하이브리드**(결정론 후보 + LLM 선택 + 캐싱), `anchors.py` 가 레퍼런스.
**핵심 판단**: theme 분류=LLM 직관 / 채점=결정론 분리 → 데이터 소스 무관 골격. 현재 수급이 **시장 레벨(KOSPI/KOSDAQ 집계) 프록시**뿐이라 MVP 한계 명시 — 종목 레벨 수급 collector(다음) 도입 시 `net_sums` **입력만** 시장→종목 교체하면 골격 100% 재사용.

## 한 일
- `collectors/theme_match.py` (신규) — `classify_theme`(manual override → Stage1 결정론 후보(config taxonomy 키) → Stage2 LLM `call_llm` temp 0.0 JSON + `llm_call_cache` type='theme_match' TTL 30일 + neutral fallback) / `score_theme_match`(권위 주체 net / (5주체 abs 합 +1) = -1..+1 → breakpoints 0~10, `_SUBJECT_ALIAS` 짧은이름→net키) / `resolve_theme_match`(결합 진입점). anchors.py 캐싱·mock 패턴 1:1 mirror. `_ticker_name` 은 KR_TICKER_TO_NAME lazy import(순환 회피).
- `collectors/score_inputs_config.py` — `get_theme_authority`/`get_theme_taxonomy`/`get_manual_theme` 로더 3개 (`get_rr_rule` 패턴).
- `config/score_inputs.yaml` — `flow.theme_match` breakpoints(placeholder, SLOT S2) + `flow.theme_authority`(10테마 초안) + `flow.theme_taxonomy`(키+한국어 라벨) + `flow.manual_theme: {}` 시드.
- `collectors/flow_inputs.py` — `compute_flow_inputs` 파라미터 `theme_match_neutral` → `theme_match_score|theme/source`(+neutral fallback) 정련 + `_sum_net` 헬퍼 + `build_flow_inputs`(async) 가 `resolve_theme_match` 호출(크래시 가드) + `FlowInputs` 2필드 + render 테마/source/score 표기.
- `tests/test_theme_match.py` (신규 16) — score 결정론 6 + classify(manual/LLM-mock/none/out-of-taxonomy/예외/빈taxonomy/빈ticker/캐시히트) 8 + resolve 2. **call_llm mock 필수**.
- `tests/test_flow_inputs.py` (+4) — 미해소 중립 / 주입 반영 / render 테마 노출.
- `docs/specs/INFRA-SCORE-INPUTS-001-...md` — `generates` 에 theme_match.py + test 추가, SLOT S1 "구현됨" 갱신.

## 검증 결과
- ✅ pytest **677 → 695 passed** (+18, 회귀 0, `TESTING=1`)
- ✅ `validate.py` **0 errors** (1 warning = 기존 teams/registry.yaml 무관)
- ✅ 프로덕션 통합 무수정 확인 — `run_analyst.py:539` `build_flow_inputs(ticker=target_ticker)` 이미 배선 + try/except 가드. 라이브 경로(run_analyst + stream) 자동 포함.

## 의도적으로 안 한 것
- **라이브 검증 (서버 005930 질의)** — 서버 재시작 중 8000 좀비 소켓(죽은 PID 18960 LISTEN) 으로 신규 서버 바인딩 실패 → 사용자 **재부팅 결정**. **다음 세션 확인용으로 남김** (서버 정상 기동 후 `POST /api/analysts/flow_analyzer/chat` 005930 → metadata `flow_inputs_failures` 의 `theme_match: <테마> (<source>) → <score>` 노출 확인).
- **theme_authority/taxonomy/breakpoints production 튜닝** — placeholder 초안 유지(운용 누적 후 사용자·회고분석가 합의, SLOT S2).
- **tier area 등록** — `_STAGE2_MODEL_DEFAULT` 하드코딩(anchors mirror), tiers.py 본 SPEC scope 밖.

## 기술 부채/미완
- 라이브 미검증 (위, 다음 세션 첫 확인).
- net_sums 시장 레벨 프록시 — theme_match 위력은 **종목 레벨 수급 collector** 후 발현.
- 8000 좀비 소켓 = uvicorn --reload 부모 kill 후 Windows 잔존, 재부팅으로 정리(환경 trivia).

## 맥락 재진입 힌트
- theme_match 임계·테마사전 조정 = `config/score_inputs.yaml::flow.theme_*` 만 수정(코드 무판단, watchdog). manual 오분류 정정 = `flow.manual_theme: {ticker: theme_key}`.
- 캐시 = `llm_call_cache` type='theme_match', cache_key=`theme|ticker|taxonomy_ver`(cutoff 미포함 — 테마 안정).

## 다음에 이어서 할 작업 (우선순위)
1. **theme_match 라이브 검증** — 재부팅 후 서버 8000 정상 기동 → flow_analyzer 005930 질의로 테마 분류+score+source end-to-end 확인 (이번 세션 미실시분).
2. **종목 레벨 5주체 수급 collector** — SPEC(가칭 INFRA-STOCK-SUPPLY-001) + KRX/KIS 종목별 투자자 매매동향. F-Score 세 축(momentum/inflow_speed/theme_match) 동시 실측 승급. theme_match 골격 입력만 교체.
3. **SLOT S2 임계 + S3 목표 정밀화** — score_inputs.yaml breakpoints·theme_authority·rr_rule floor/cap 실 분포 튜닝 + R/R ATH 근처 measured-move.

## 커밋 상태
- 코드(theme_match.py/flow_inputs.py/score_inputs_config.py/score_inputs.yaml/tests 2/SPEC) + wrap-up docs = 본 세션에서 커밋·push (main 직접, 솔로).
