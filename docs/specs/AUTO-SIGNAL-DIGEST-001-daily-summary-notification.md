---
spec_id: AUTO-SIGNAL-DIGEST-001
title: 자동 권고 일일 요약 알림 — 숫자만 보내던 것을 종목명·사유·조건으로
team: shared
type: feature
level: implementation
status: verified
parent: AUTO-SIGNAL-GENERATION-001
generates:
  - core/signal/daily_digest.py            # summary dict → 알림 본문 (순수 함수, LLM 0·DB 0)
  - tests/test_daily_digest.py             # 렌더 규칙 + 종목코드 미노출 회귀
modifies:
  - core/signal/auto_signal.py             # 반환 dict 확장 / 밴드 스킵 직전 판단 / summary 시장 컨텍스트 / _emit_daily_summary
  - collectors/market_view.py              # _REGIME_KR·_POSTURE_KR public 승격 (한국어 라벨 재사용, 중복 정의 금지)
  - tests/test_auto_signal.py              # 반환 dict·스킵 직전 판단·알림 배선
contracts:
  - name: strategist-recommendation-v1     # 기존 — read only, 계약 변경 없음
    version: "1.0"
depends_on:
  - AUTO-SIGNAL-GENERATION-001 (M4 알림 SLOT5 의 후속 개선)
  - BRAIN-ALPHA-FLEXIBILITY-001 (alpha_posture.conditional_entry — 진입 조건 문구 출처)
  - TRADE-PLAN-LIFECYCLE-001 (funnel_stage 관심/매수대기 라벨)
---

# AUTO-SIGNAL-DIGEST-001 — 자동 권고 일일 요약 알림 개선

> **새 판단을 만들지 않는다. 이미 만들어 DB 에 넣어둔 판단을 알림에서 버리지 않을 뿐이다.**
> LLM 콜 0, 신규 테이블 0, 신규 수집 0.

## 1. 문제

매일 오는 알림 전문(2026-08-10 실물):

```
🔵 자동 권고 일일 요약 (2026-08-10)
관심종목 5종 평가 → 매수 0 · 매도 0 · 관망 2 · 밴드 스킵 3
시장 체제: moderate_bear
```

사용자 지적 그대로 — **"뭐가 매수고 뭐가 관망인지 종목을 알 수가 없다."**

세 가지 결함이 겹쳐 있다.

### 1-a. 종목명이 없다 (본 SPEC 의 주 문제)

`run_signal_for_ticker` 는 종목명·신뢰도·사유·점수·진입 조건을 전부 계산해 `team_outputs`
에 영속한다. 그런데 `run_signal_cadence` 가 그 결과를 `len()` 으로 접어 카운트만 남기고
(`core/signal/auto_signal.py:814-821`), `_emit_daily_summary` 가 그 카운트만 렌더한다
(`:492-507`). 재료는 다 있는데 알림 경로에서만 버려진다.

### 1-b. "밴드 스킵" 이 판단 없음처럼 보인다

밴드 게이트는 "지문이 직전과 같다 = verdict 가 바뀔 수 없는 구간" 일 때 전략가 호출을
생략하는 **비용 최적화**다. 판단이 없는 게 아니라 **직전 판단이 유효하다**는 뜻이다.
그런데 알림은 "관망 2 · 밴드 스킵 3" 으로 나란히 세어, 스킵된 3종은 판단이 실종된 것처럼
읽힌다. (2026-07-18 DB 감사에서 "밴드 스킵 집계 착시" 로 이미 등록된 항목 —
`ENGINE-FUNNEL-REWIRE-001` §6 관측 체크 3건 중 ③.)

### 1-c. 실패 버킷이 아예 없다 — 숫자가 안 맞는다

08-10 postclose 는 `screened=5`, `tracks=("A","B")` → `evaluated=10`. 그런데 요약 숫자 합은
`관망 2 + 스킵 3 = 5`. **나머지 5건은 persist 도 skip 도 안 됐는데 요약에 그 버킷이 없다.**

DB 대조 결과 사라진 5건은 전부 Track A(중장기)다:

| team_id | 일자별 건수 (최근) |
|---|---|
| `track_a` | 08-07 **3** / 08-04 1 / 08-03 1 / 07-24 1 / 07-14 10 / 07-13 40 / 07-10 42 |
| `track_b` | 08-11 1 / 08-10 4 / 08-07 6 / 08-06 5 / 08-05 3 / 08-04 4 |

7월 40건/일 → 8월 0~3건. **중장기 트랙이 사실상 죽어 있는데 알림은 그 사실을 한 글자도
전달하지 않는다.** 알림이 정직했다면 진작 드러났을 결함이다. → §5 진단 범위.

## 2. 결정 (2026-08-11 인터뷰)

| # | 결정 | 근거 |
|---|---|---|
| D1 | **실전 워딩형 + 종목별 상세 둘 다** — "오늘 할 일" 순으로 버킷 정렬하고, 지켜볼 종목엔 점수·신뢰도 줄까지 붙이고, 변화없음·미산출도 종목명·사유 전개 | 사용자 선택("둘 다"). 압축이 문제였으므로 압축으로 되돌아가지 않는다 |
| D2 | **길이 상한 없음** — 전 종목 전개. 길어지면 기존 4096자 줄 경계 분할이 여러 통으로 보냄 | 사용자 선택. 정보 손실 0 우선 |
| D3 | **실패 버킷 신설** (`미산출`) — persist 도 skip 도 아닌 결과를 전부 노출 | 1-c. 조용한 실패가 두 달을 갔다 |
| D4 | **밴드 스킵 → "변화 없음 (직전 판단 유지)"** + 직전 verdict 표기 | 1-b. 착시 해소 |
| D5 | **렌더는 순수 함수 별도 모듈** (`core/signal/daily_digest.py`) | 테스트가 fixture dict 만으로 전건 커버 |
| D6 | **Track A 미산출은 원인 진단까지, 수정은 별도 판단** | 원인에 따라 페르소나·파서·config 로 갈림 |

## 3. 설계

### 3-a. 버킷 (렌더 순서 = 오늘 할 일 우선)

| 버킷 | 소스 조건 | 표기 |
|---|---|---|
| 매수 / 매도 | `persisted` ∧ verdict ∈ {buy, sell} | 종목명·트랙·진입/손절/목표·사유·신뢰도 (전건 상세) |
| 지켜볼 종목 | `persisted` ∧ 그 외 verdict | 종목명·트랙·단계(관심/매수대기)·신뢰도·점수 4종·사유 1줄·진입 조건 |
| 변화 없음 | `skipped` (밴드 게이트) | 종목명·트랙 + **직전 판단** + "점수대 동일" |
| 미산출 | 나머지 전부 | 종목명·트랙 + 실패 사유 한국어 |

매수·매도는 0건이어도 섹션을 표시한다("신규 진입 없음"이 그 자체로 정보). 나머지 버킷은
비면 섹션 생략.

### 3-b. 헤더 + "왜 0인지" 한 줄

```
🔵 자동 권고 일일 요약 (2026-08-10)
시장 체제: 약세(moderate_bear) · 진입 자세: 방어

■ 매수 0 · 매도 0 — 신규 진입 없음
분산일 7건(임계 4) — 신규 진입 차단 국면
```

"왜 0인지" 줄은 **결정론 규칙**으로만 만든다 (LLM 0, 근거 없으면 침묵):

1. `distribution_day_count ≥ kill_switch_dd` → `분산일 N건(임계 K) — 신규 진입 차단 국면`
2. 아니고 `entry_posture == "defensive"` → `시장 방어 태세 — 신규 진입 보수적`
3. 둘 다 아니면 **줄 자체를 생략** (문장을 지어내지 않는다 — 투자 7계명 #6)

임계 K 는 `config/market_view.yaml` 의 `entry_posture.kill_switch_dd` 를 읽는다(하드코딩 금지).

### 3-c. 점수 줄 — 코드 라벨 금지

`feedback_production_answer_brevity` 규칙(α/F-Score/S-Score 같은 코드 라벨을 사용자에게
노출 금지)에 따라 한국어로 번역하고, 값이 `None` 인 항목은 그 항목만 생략한다.

| 원본 | 표시 |
|---|---|
| `t_score` | 타점 |
| `buy_score` | 매수 |
| `f_score` | 수급 |
| `s_score` | 주도주 |

→ `타점 5.5 · 매수 6.0 · 수급 4.0 · 주도주 6.2`

### 3-d. 진입 조건 줄

`rec.data["alpha_posture"]["conditional_entry"]` 를 그대로 문장화한다.

- `entry_zone` 있으면 → `→ 12,300~12,800 눌림 시 진입 검토`
- 없으면 `note` → `→ 시장 위험 해소되면 재평가`
- 둘 다 없으면 줄 생략

### 3-e. 실패 사유 한국어 사전

원문은 괄호에 짧게(60자) 남겨 디버깅 가능성을 보존한다.

| 원본 패턴 | 표시 |
|---|---|
| `no_yaml` | 전략가가 권고 형식을 못 냈음 (재시도 후 실패) |
| `_TRANSIENT_MARKERS` 매칭 (503·timeout·rate…) | 전략가 응답 실패 — 일시적 (서버 과부하·타임아웃) |
| `scorecard:*` | 점수표 계산 실패 — 지표 수집 오류 |
| `bad_track` | 트랙 설정 오류 |
| 그 외 | 권고 미발행 — `원문[:60]` |

일시적 판정은 `auto_signal._is_transient` 를 **재사용**한다(패턴 중복 정의 금지).

### 3-f. 서식

- 종목명 `<b>` 볼드 — `core/notification/service.py` 의 `_SAFE_TAG_RE` 가 이미 보존하고,
  `_strip_html_for_log` 가 DB·파일 폴백용 plain 으로 벗겨준다 (웹앱 알림 탭 태그 노출 없음).
- 종목 간 빈 줄 (`feedback_briefing_practical_output` 가독성 규칙).
- **종목코드 노출 금지** — 종목명만. 이름 해석은 `resolve_stock_name` 중앙 통과
  (`feedback_no_stock_code_in_display`). 테스트로 회귀 방지(§4).
- 4096자 분할은 줄 경계에서 일어나고 `<b>` 는 한 줄을 넘지 않으므로 분할이 태그를 깨지 않는다.
- 푸터: `관심종목 5종 × 2트랙 = 10건 평가.`

### 3-g. 배선 변경 3곳 (`core/signal/auto_signal.py`)

1. **`run_signal_for_ticker` 반환 dict 확장** — 이미 메모리에 있는 `rec` 값을 버리지 않고
   넘기기만 한다: `display_name` · `confidence` · `headline_reason`(= `reasons[0]`) ·
   `funnel_stage` · `conditional_entry` · `scores`(cited 4종) · `entry_price` · `stop_loss` ·
   `target_prices`. 추가 계산·추가 호출 0.
2. **밴드 스킵 경로에 직전 판단** — `_last_verdict(ticker, track)` 신규(작은 DB read 1회).
   기존 테스트 주입점 `last_fingerprint_reader(ticker, track) -> str|None` 은 **시그니처
   불변**으로 두고 별도 함수를 쓴다(회귀 차단).
3. **summary 에 시장 컨텍스트** — `entry_posture` · `distribution_day_count` ·
   `kill_switch_dd`. Scorecard 가 이미 계산해 둔 값을 cadence 루프에서 최초 1건만 승계.

`_emit_daily_summary` 는 본문 조립을 `render_daily_digest(summary)` 에 위임한다.

### 3-h. 한국어 라벨 재사용

`collectors/market_view.py` 의 `_REGIME_KR` · `_POSTURE_KR` 를 public(`REGIME_KR` ·
`POSTURE_KR`)으로 승격해 import 한다. **새로 정의하지 않는다** (CLAUDE.md #11 재사용 우선).
기존 내부 참조는 새 이름으로 갱신.

## 4. 테스트

`tests/test_daily_digest.py` (신규) — 순수 렌더러라 fixture dict 만으로 전건 커버, 외부 호출 0:

1. 매수 있을 때 진입·손절·목표 전건 상세
2. 매수·매도 0 + 분산일 kill 초과 → 이유 줄 출력 / 근거 없을 땐 줄 생략
3. 점수 일부 `None` → 그 항목만 생략, 줄은 유지
4. 진입 조건 — `entry_zone` 있음 / `note` 만 / 둘 다 없음 3분기
5. 변화 없음 버킷에 직전 판단 표기
6. 실패 사유 매핑 5종 전부
7. **종목코드 미노출 단언** — 본문에 6자리 숫자 티커가 없음 (메모리 규칙 회귀 방지)
8. 빈 입력(평가 0종·전건 실패) graceful

`tests/test_auto_signal.py` (추가):

- `run_signal_for_ticker` 반환에 `display_name`·`confidence`·`headline_reason`·`scores` 포함
- 밴드 스킵 시 직전 판단이 반환에 채워짐 (reader stub)
- `_emit_daily_summary` 가 렌더 결과를 `notify` body 로 전달 (notify mock — 실 Telegram 금지)

회귀: `TESTING=1 pytest` 전체.

## 5. Track A 미산출 진단 — 결과 (2026-08-11)

### 원인 확정: `claude_code` 타임아웃 90초에 Track A 가 걸린다

| 측정 (2026-08-11 라이브 1콜씩, 유휴 장비) | Track A | Track B |
|---|---|---|
| 응답 지연 | **87.69초** | 39.32초 |
| 입력 토큰 | 78,813 | 54,983 |
| 출력 토큰 | 6,349 | 2,481 |
| system 프롬프트 | 50,505자 · 7블록 | 38,009자 · 6블록 |
| `llm.claude_code.timeout_sec` | **90** (`config/defaults.yaml:31`) | 90 |

**Track A 는 유휴 장비에서도 한도까지 2.3초 남기고 통과한다.** cadence 는 종목 병렬
`concurrency: 3` 으로 돌고, 게다가 08-10 회차는 절전 미스파이어 따라잡기로 3 cadence 가
23:46~00:00 사이에 몰려 실행됐다. 그 부하에서 90초를 넘기면
`claude_code timed out after 90s` 예외 → 그 종목·트랙만 실패.

`_is_transient` 가 "timeout" 을 일시적으로 보고 1회 재시도하지만, 원인이 부하가 아니라
**구조적으로 한도에 붙어 있는 것**이라 재시도도 같이 죽는다.

### 회귀 시점

`0a23704`(2026-07-17) `provider→claude_code + max_candidates 20→5`. 그 전 Gemini 시절
Track A 출력은 1,136~1,460 토큰으로 빨랐다(07-14). 전환 이후 Track A 는 07-24 1건 ·
08-03 1건 · 08-04 1건 · 08-07 3건 · 08-10 **0건** — 가끔 90초 안에 들어올 때만 산다.
같은 기간 Track B 는 3~7건/일로 안정. **하루 40건 → 5건 급감은 두 원인의 합**이다:
`max_candidates` 20→5 (의도된 비용 절감) + Track A 타임아웃 (의도 안 된 결함).

### 왜 두 달 가까이 안 보였나 — 관측 구멍 2개

1. **비용 원장이 실패를 기록할 수 없다.** `core/llm/client.py` `_record_ledger` 가
   `success=True` 를 **하드코딩**한다. 실패는 예외로 빠져나가 원장에 행 자체가 안 남는다.
   `llm_cost_ledger` 에 `success=0` 행이 **역대 0건**인 이유.
2. **로그가 안 남는다.** `core/logging/__init__.py` 가 `PrintLoggerFactory` — stdout 전용,
   파일 미기록. 08-10 실제 예외 문구는 복구 불가.

여기에 **요약 알림에 실패 버킷이 없던 것**(§1-c)이 겹쳐, 세 겹으로 가려졌다.

### 후속 (본 SPEC 범위 밖 — 사용자 판단 대기)

| # | 조치 | 성격 |
|---|---|---|
| F1 | `llm.claude_code.timeout_sec` 90 → 180 상향 (config 값, 코드 변경 0) | 즉효·최소 |
| F2 | Track A system 프롬프트 축소 (78.8k 토큰 = canon·RAG 주입량 재검) | 근본 |
| F3 | `_record_ledger` 가 실패도 기록 (`success=0`) — LLM-COST-LEDGER-001 소관 | 관측 |
| F4 | 로그 파일 핸들러 추가 | 관측 |

F3·F4 는 이번 알림 개선이 사후적으로 드러내 준 것과 같은 종류의 구멍이다.

## 6. 재사용 영향도 (CLAUDE.md #11)

| 축 | 판정 |
|---|---|
| 신규 테이블 | **0** — `team_outputs` · `notifications_log` read/write 그대로 |
| 신규 collector/connector | **0** |
| 신규 API 라우트 | **0** |
| 신규 LLM 콜 | **0** — 렌더는 순수 함수 |
| 신규 DB read | 밴드 스킵 종목당 1회(`_last_verdict`) — 스킵은 원래 LLM 을 아낀 경로라 순증 무시 가능 |
| 한국어 라벨 | `market_view` 것 **재사용**(승격), 재정의 금지 |
| 계약 | `strategist-recommendation-v1` 무변 (read only) |

신규 모듈 `core/signal/daily_digest.py` 1개만 추가한다. `auto_signal.py` 안에 넣지 않는
이유는 **순수성**이다 — 렌더가 I/O 없는 함수여야 fixture dict 만으로 8개 시나리오를 전부
테스트할 수 있고, `auto_signal.py`(832줄, 이미 지휘자 역할로 충분히 큼)를 더 키우지 않는다.

## 7. 비고 — 알림이 정직해야 하는 이유

이번 건의 교훈은 서식이 아니다. **집계가 결함을 가렸다.** "관망 2 · 밴드 스킵 3" 은 틀린
숫자가 아니지만, 합이 10 이 아니라는 사실을 숨겼고 그래서 중장기 트랙이 두 달 가까이
죽어 있는 것을 아무도 몰랐다. 요약은 항상 **평가 총건수와 버킷 합이 맞아떨어지게** 쓴다 —
남는 건 반드시 어딘가에 표시된다.
