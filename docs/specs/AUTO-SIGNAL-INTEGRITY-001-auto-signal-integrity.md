---
spec_id: AUTO-SIGNAL-INTEGRITY-001
title: 자동 신호 정합 핫픽스 — defensive 게이트·원칙수호자 복원·죽은 배선 수리 (Tier 0)
team: shared
type: feature
level: implementation
status: implementing
parent: MARKET-CONTEXT-BRAIN-001
generates:
  - tests/test_auto_signal_integrity.py   # 후성 06-16 시나리오 재현 포함
modifies:
  - core/signal/auto_signal.py            # T0-a 발행 게이트 / T0-b scorecard 배선 / T0-c 결정론 원칙 체크
  - core/signal/alpha_posture.py          # (필요 시) posture 게이트 결과 노출 확장
  - collectors/news_source.py             # T0-d 미라벨링 재분류 백필
  - config/screening.yaml                 # 게이트 임계 config 외부화 (하드코딩 금지)
contracts:
  - name: strategist-recommendation-v1    # 기존 — verdict 필드 의미 무변, 발행 조건만 강화
    version: "1.0"
depends_on:
  - AUTO-SIGNAL-GENERATION-001 (수리 대상 funnel)
  - BRAIN-ALPHA-FLEXIBILITY-001 (AlphaPosture — M3b 잔여인 sector_rs·wave 배선을 T0-b 가 상환)
---

# AUTO-SIGNAL-INTEGRITY-001 — 자동 신호 정합 핫픽스 (Tier 0)

> **새 능력 추가가 아니라 결함 수리.** 2026-07-05 진단(부모 SPEC §1~2)에서 확인된 "배선이 약속한 것과 실제 동작의 불일치" 4건. 실사고 표본 = 후성(093370) 06-16 buy(블로우오프 고점 익일 → −12%), 06-29 buy 5건(defensive 태세 중 발령 → 07-02 반도체 급락 직격).
>
> **설계 확정 (2026-07-05 인터뷰, 사용자 의도 확인)**: T0-a 는 **차등 게이트** — blanket 아님.
> defensive 면 buy 후보에 주도주·강세섹터·건강 위치·파동 생존(bear_override 와 같은 결)을 추가
> 요구, 미충족은 **wait 강등 + 원판단 기록**(`pre_defensive_candidate`/`posture_blocked` — Tier 4
> 채점 재료). LLM 이 `llm_deviation_reason` 사실 근거를 로그하면 buy 존중(가드레일 있는 C —
> "공포를 기회로" 판단 경로 보존), 근거 없으면 코드가 강등(persona 는 강제 불가 교훈).
> 근거: 사용자 철학 "급락 시 발 뺄지 공포를 기회로 삼을지 고도의 전문가적 추론"(2026-07-05) +
> "약세장이어도 주도주 눌림목=타점"(2026-06-15) — blanket 은 그 반대라 기각.

## 결함과 수리

### T0-a — defensive/vix_panic 시 자동 buy 신호 발행 게이트
- **결함**: `entry_posture`(market_view)는 06-22부터 계속 defensive 였는데 06-29 자동 buy 5건 + 07-02 buy 1건 발령. deployment_cap 은 계좌관리자 사이징에만 작동 — **신호 발행 단에는 시장 태세 게이트가 없다.**
- **수리**: `auto_signal.py` 의 persist/notify 직전에 entry_posture 를 읽어, `defensive`(또는 vix_panic freeze) 상태에서는 자동 경로의 buy 신호를 **보류(hold-back) 처리** — verdict 자체는 기록하되(설명가능성) 🟢 매수 알림·데스크 actionable 승격을 차단하거나, AlphaPosture 게이트 입력에 posture 를 결합해 후보 단계에서 강등. **어느 층에서 막을지(알림만 vs 후보 강등)는 인터뷰 결정 사항.**
- **주의**: blanket 재도입 아님 — BRAIN-ALPHA-FLEXIBILITY 가 폐기한 "regime 범주 게이트"와 달리, 이것은 *시장 전체 방어 태세*(복합 위험 게이트가 이미 소유한 판단)와 *신호 발행*의 정합을 맞추는 것. 게이트 소유권은 여전히 AlphaPosture/entry_posture 한 곳.

### T0-b — sector_rs_score·wave_alive 배선 (M3b 잔여 상환)
- **결함**: `compute_scorecard` 가 두 필드를 안 채움(None) → `derive_alpha_posture` 의 약세장 눌림목 bear_override·강세섹터 차등이 **코드상 절대 발동 불가** (dead path). 후성 같은 volume_bull 급등주와 진짜 강세섹터 주도주가 구분되지 않는 원인의 절반.
- **수리**: 결정론 소스는 이미 존재 — 섹터 RS(`screening_inputs` supply_chain 경로)·파동 생존(WAVE-ALPHA anchor, 결정론 anchor 기본화됨) → scorecard 에 주입. LLM 콜 0 목표(결정론 값 우선, LLM 판별이 필요한 부분은 Tier 2 로 이관).

### T0-c — 자동 경로 principle_guardian 우회 해소 (결정론 최소 체크)
- **결함**: `_TRACK_BYPASSED_IDS` 가 원칙수호자까지 우회 → 자동 buy 가 투자 7계명 검증 없이 발행. 후성 buy 근거 전문에 "의도적으로 우회되어 점수 미발행" 문구가 그대로 남아 있음.
- **수리**: 분석가 LLM 풀콜 복원이 아니라(배치 비용 설계 유지) **결정론 7계명 체커**(checkers/ 순수 규칙: 비중 한도·손절선 존재·과열 이격 등 계산 가능 항목)를 신호 발행 전 통과. 위반 시 신호 보류 + 사유 기록.

### T0-d — 미라벨링 뉴스 재분류 백필
- **결함**: 06-23~26 메타/AI버블 기사 다수가 direction/magnitude=None — 수집은 됐으나 신호로 변환 안 됨(classify 실패분 방치). Tier 1 해석 스테이지의 입력 품질을 갉아먹는 선행 결함.
- **수리**: `classify_news_items` 실패분 재시도 백필(멱등 — `llm_call_cache` 재사용) + 일일 cron 에 미라벨링 잔량 리포트. 라벨링 실패율을 관측 가능하게.

## 수용 기준 (테스트 시나리오)

1. **후성 06-16 재현**: entry_posture=defensive + extension 과열(이격 +37%↑) 상태의 scorecard 입력 → 자동 경로에서 🟢 buy 알림 미발행 + 보류 사유 기록. (실 OHLCV 06-10~16 픽스처.)
2. **06-29 재현**: defensive 태세 + strong_bull regime 조합에서 buy 5건이 발행되지 않거나 보류로 기록됨.
3. **bear_override 활성 증명**: 약세 regime + sector_rs≥7 + 주도주 + wave_alive + 눌림목 입력 시 bear_override buy 후보가 실제 산출(기존엔 None 으로 불가능했던 경로의 단위 증명).
4. **7계명 체커**: 과열 이격/손절선 부재 입력 → 신호 보류.
5. **뉴스 백필**: 미라벨링 행 → 재분류 후 direction/magnitude 채워짐(mock LLM, TESTING=1).
6. 전체 pytest 회귀 0 · validate 0.

## 재사용 영향도 (가드 #11)

신규 테이블 0·신규 모듈 0(테스트 제외). 전부 기존 파일 수정: auto_signal.py 게이트 추가, scorecard 필드 채움(필드 자체는 기존), checkers/ 기존 순수 규칙 패턴 재사용, news_source.py 재시도 로직. 게이트 임계는 `config/screening.yaml` 외부화(watchdog 반영).
