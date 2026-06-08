---
date: 2026-06-09
topic: ACCOUNT-MANAGER-001 (RB-MS1) SDD 구현 — 비중 산정 두 레버 + 7계명 게이트
status: completed
plan_file: C:\Users\HOME\.claude\plans\compressed-kindling-fountain.md
---

# 2026-06-09 · ACCOUNT-MANAGER-001 SDD 구현 (RB-MS1 비중)

## 배경
오른쪽 뇌 roadmap 착수(같은 날 2번째 세션) 직후 첫 자식 ACCOUNT-MANAGER-001 SDD 구현.
전략가 권고(strategist-recommendation-v1) → 4계좌별 비중·자금액·분할매수(position-sizing-v1).
**핵심 판단(인터뷰 확정 유지)**: 비중 = 종목당 고정 리스크R(stop 역산, MDD 통제) × regime
변조 총 배포 한도(시장 추종) 두 레버 + 과열도(extension) 분할 + 7계명 게이트(축소 기본·손절
누락만 차단). TDD(test-driven-development skill)로 결정론 금융 로직을 RED→GREEN. 가상 전용.

## 한 일
- `core/account/sizing.py` (신규) — 결정론 코어. `resolve_risk_fraction`(레버1 R, 확신 ≥3점수
  교차 시 ×1.5)·`deployment_cap`(레버2 entry_posture 변조, vix_panic 동결)·`split_ratios`(과열도
  구간→차수, extension 높을수록 front-load)·`size_position`(통합 게이트) + dataclasses
  (AccountDef/AccountState/PositionTranche/PositionSizing) + config 로더(us_macro mirror) +
  `render_position_sizing_md`(코드라벨 0·금액 병기) + `_won` 만/억 표기.
- `core/account/portfolio.py` (신규) — `load_accounts`(config 4계좌)·`get_account_state`(DB-first,
  행 없으면 seed 0비중 부트스트랩)·`upsert_account_state`(RB-MS2용). `core/account/__init__.py`.
- `config/accounts.yaml` (신규) — 4계좌(국장/미장×중장기/단기 1000만) + sizing 파라미터(R 1%/1.5%·
  배포밴드 80/60/45·7계명 한도·과열도 분할 비율). 보수적 기본, 튜닝 SLOT.
- `core/db/schema.sql` — v13: `account_state`(account_id PK) + `account_positions`(account×ticker
  PK). MS1 정의/read, RB-MS2 write. 신규 테이블 CREATE IF NOT EXISTS 멱등.
- `agents/account_manager/{persona.md,manifest.yaml}` (신규) — Layer 4 8-섹션 페르소나(산정은
  결정론·LLM은 서술자, 두 레버·게이트·분할 doctrine, 종목 판단 금지·가상 전용 경계) + manifest
  (reads principles, temp 0.3, reads_recommendation).
- `scripts/_account_sizing_probe.py` (신규) — 실 config 4 시나리오 라이브 probe.
- `tests/test_account_{sizing,portfolio,manager_persona,render}.py` (신규) — 38 케이스.
- `docs/specs/ACCOUNT-MANAGER-001-...md` — status draft→implementing.

## 검증 결과
- ✅ `TESTING=1 pytest` 전체 **1027 passed**(+38 신규), 회귀 0. validate 0 errors.
- ✅ TDD: sizing·portfolio·render 각각 RED(import 실패) 확인 후 GREEN. 산수 오류 테스트 1건
  정정(raw_weight 10%를 100%로 오기 — 코드가 맞음).
- ✅ 라이브 probe(실 config/accounts.yaml): A 좋은타점 비중 9.8% front-load 58/29/10만 /
  B 고확신 R 2.2%(×1.5) 단일 15% 자동축소 / C 손절누락 차단 / D vix_panic 동결 차단.
- ✅ project_status `🔨 ACCOUNT-MANAGER-001 [implementing] ◀ 현재 작업`, NORTH-STAR 1/2.

## 의도적으로 안 한 것
- **production_chat 배선**(Layer 3 권고→Layer 4 자동 호출, 실 사용자 채팅 시연) — SPEC generates
  밖 통합. RB-MS2(가상매매)와 묶는 게 자연스러움(사용자 결정). 그래서 status=implementing 유지.
- 수치 캘리브레이션(R·밴드·분할 비율) — 다일 누적 후 백테스팅 튜닝 SLOT([[feedback_backtest_essence]]).

## 기술 부채/미완
- ACCOUNT-MANAGER-001 production_chat 배선 미완 → status implementing(generates 6파일은 완성).
- account_positions 테이블은 정의만(write는 RB-MS2). account_state 부트스트랩은 seed 가정.
- 수치 SLOT(R·regime 밴드·과열도↔분할) 다일 튜닝 대기.

## 다음에 이어서 할 작업 (우선순위)
1. **PAPER-TRADING-001 (RB-MS2 가상매매)** — 비중 지시→가상 체결 기록 + production_chat 배선
   (Layer3 권고→Layer4 size_position→가상 체결). "매일 도는 데스크"의 도는 부분. `/spec-interview`
   로 INTERVIEW-SLOT(체결가·매도/손익·데스크 루프) 채우고 SDD. ACCOUNT-MANAGER 배선도 여기서 묶음.
2. **ACCOUNT-MANAGER-001 수치 캘리브레이션** — universe 다일 누적 후 R·배포밴드·분할 비율 스윕.
3. **gemini transient 503 retry 배선** — 이월 작은 부채(core/llm/client.py provider 명시 경로).

## 커밋 상태
- 코드(feat: sizing/portfolio/persona/schema/config/probe/tests + SPEC status) + wrap-up docs(docs)
  2 커밋 분리 → main 직접 + push 예정.
- `.claude/scheduled_tasks.lock`(untracked) 무관 → 커밋 제외.
