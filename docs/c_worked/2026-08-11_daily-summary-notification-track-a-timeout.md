---
date: 2026-08-11
topic: 일일 요약 알림 종목명·사유 전개 (AUTO-SIGNAL-DIGEST-001) + Track A 90초 타임아웃 진단
status: completed
---

# 2026-08-11 · 일일 요약 알림 개선 + Track A 미산출 원인 확정

## 배경
사용자 지적 — 매일 오는 자동 권고 요약이 `"관심종목 5종 평가 → 매수 0 · 매도 0 · 관망 2 · 밴드 스킵 3"`
카운트만 와서 **어느 종목이 매수인지 관망인지 알 수 없다.** 재료(종목명·신뢰도·사유·점수·진입 조건)는
이미 `team_outputs` 에 전부 영속돼 있는데 알림 경로에서만 버려지고 있었다.

**이번 세션의 핵심 발견**: 그 압축이 결함을 가리고 있었다. 08-10 평가 10건인데 요약 숫자 합은 5 —
**나머지 5건(전부 Track A)이 어느 버킷에도 안 잡혀** 중장기 트랙이 두 달 가까이 죽어 있던 걸 아무도 몰랐다.
단계 = BODY-AUTOMATION-001 / AUTO-SIGNAL-GENERATION-001 의 알림 SLOT5 후속.

## 한 일
- `docs/specs/AUTO-SIGNAL-DIGEST-001-daily-summary-notification.md` — 신규 SPEC (결정 D1~D6 + 재사용 영향도 + §5 진단 결과)
- `core/signal/daily_digest.py` — **신규**. summary dict → 알림 본문 순수 함수 (LLM 0 · DB 0 · I/O 0)
  - 버킷 5개: 매수/매도 · 지켜볼 종목 · 변화 없음 · 미산출
  - 매수·매도 0 이어도 표시 + "왜 0인지" 결정론 근거 1줄 (근거 없으면 침묵 — 7계명 #6)
  - `_humanize()` — 사유에 새어나온 내부 용어 번역 (AlphaPosture · kill switch · regime 코드 · `*_score`)
  - 종목코드는 이름 폴백으로도 안 씀 (`이름 미상`)
- `core/signal/auto_signal.py` — 반환 dict 에 알림 재료 승계(추가 계산 0) / 밴드 스킵에 `_last_verdict` /
  summary 에 `failed`·`entry_posture`·`distribution_day_count`·`kill_switch_dd` / `_kill_switch_dd()` config 로더
- `collectors/market_view.py` — `_REGIME_KR`·`_POSTURE_KR` → public 승격 (재사용, 중복 정의 금지)
- `tests/test_daily_digest.py` — **신규 25**. 렌더 규칙 전건 + 종목코드 미노출 회귀 + 버킷합=총건수 정합
- `tests/test_auto_signal.py` — +5 (재료 승계 · 직전 판단 · summary 정합 · 알림 본문 종목명)

## 검증 결과
- ✅ 전체 **1460 passed** (기존 1457 + 신규 30, 회귀 0, 외부 API 실호출 0)
- ✅ `scripts/validate.py` 0 errors (warning 1 = 기존 teams/registry.yaml)
- ✅ 08-10 실 DB 데이터 재현 렌더 — 종목명·점수·조건 정상, 종목코드 0
- ✅ **텔레그램 실발송 성공** (`delivered_telegram=True`, 898자 1통, 분할 없음) — production `_emit_daily_summary` 경로 그대로

## Track A 미산출 진단 — 원인 확정

**`llm.claude_code.timeout_sec = 90` 에 Track A 가 붙어 있다.**

| 라이브 측정 (유휴 장비, 트랙당 1콜) | Track A | Track B |
|---|---|---|
| 응답 지연 | **87.69초** | 39.32초 |
| 입력/출력 토큰 | 78,813 / 6,349 | 54,983 / 2,481 |
| system 프롬프트 | 50,505자 · 7블록 | 38,009자 · 6블록 |

유휴 상태에서도 한도까지 **2.3초** 남는다. `concurrency: 3` 병렬 + 08-10 회차는 절전 미스파이어
따라잡기로 3 cadence 가 23:46~00:00 에 몰려 실행 → 90초 초과 → `claude_code timed out after 90s`.
`_is_transient` 가 재시도하지만 구조적으로 한도에 붙어 있어 재시도도 같이 죽는다.

**회귀 시점** = `0a23704`(07-17) `provider→claude_code`. Gemini 시절 Track A 출력은 1,136~1,460 토큰으로
빨랐다. 전환 후 track_a = 07-24 1 · 08-03 1 · 08-04 1 · 08-07 3 · 08-10 **0**. 같은 기간 track_b 는 3~7/일 안정.
**하루 40건→5건 급감은 두 원인의 합** — `max_candidates` 20→5(의도된 절감) + Track A 타임아웃(결함).

**두 달간 안 보인 이유 = 관측 구멍 3겹**
1. 요약 알림에 실패 버킷 부재 (이번에 해소)
2. `core/llm/client.py` `_record_ledger` 가 `success=True` **하드코딩** → 실패는 원장에 행 자체가 안 남음
   (`llm_cost_ledger` 에 `success=0` 역대 0건)
3. `core/logging/__init__.py` 가 `PrintLoggerFactory` — stdout 전용, 파일 미기록 → 실제 예외 문구 복구 불가

## 의도적으로 안 한 것
- **Track A 수정** — 설계 시 "원인 보고까지, 수정은 별도 판단" 합의. 원인에 따라 config/프롬프트/관측으로 갈림
- **길이 상한** — 사용자가 "상한 없음, 전부 다" 선택. 길면 기존 4096자 줄 경계 분할이 처리
- 렌더 규칙 3-c 는 점수 라벨만 다뤘으나 사유 줄 용어 번역(`_humanize`)은 취지상 추가 — 사용자에게 명시 보고함

## 다음에 이어서 할 작업 (우선순위)
1. **Track A 타임아웃 수정 (F1)** — `config/defaults.yaml` `llm.claude_code.timeout_sec` 90 → 180.
   코드 변경 0, 오늘 저녁 postclose 부터 중장기 권고 부활. 근본(F2 = Track A 프롬프트 78.8k 토큰 축소 =
   canon·RAG 주입량 재검)은 별건.
2. **관측 구멍 봉합 (F3·F4)** — `_record_ledger` 가 실패도 `success=0` 으로 기록(LLM-COST-LEDGER-001 소관) +
   로그 파일 핸들러 추가. 이번 결함이 두 달 숨은 직접 원인이고, 같은 종류가 또 숨는다.
3. **서버 재시작 → P0 라이브 체감 + 관측 체크** — 이월. 새 알림 형식도 재시작해야 라이브 반영.
   감사 발견 3건 중 ③"밴드 스킵 집계 착시"는 이번에 해소됨(①장전 scenario 빈 `{}` ②이중 발송 남음).

(4순위 이하 이월: P1 `KNOWLEDGE-INTAKE-001` spec-interview / P2 채점 루프 착수)

## 커밋 상태
- `5b09cad` docs(spec): AUTO-SIGNAL-DIGEST-001 SPEC
- `68f4b78` feat(notify): 일일 요약 알림 — 카운트만 → 종목명·사유·조건·실패버킷
