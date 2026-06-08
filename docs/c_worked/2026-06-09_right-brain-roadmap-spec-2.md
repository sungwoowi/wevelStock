---
date: 2026-06-09
topic: 오른쪽 뇌 roadmap 착수 — RIGHT-BRAIN-COMPLETION-001 + 4 자식 SPEC (비중 판단 로직 확정)
status: completed
plan_file: C:\Users\HOME\.claude\plans\compressed-kindling-fountain.md
---

# 2026-06-09 · 오른쪽 뇌 roadmap 착수 (RIGHT-BRAIN-COMPLETION-001)

## 배경
왼쪽 뇌 4/4 완성(LEFT-BRAIN-COMPLETION-001) 후 `PROJECT-NORTH-STAR-001` 은 0/1 — 사용자 본질
"매일 도는 책임지는 페이퍼 트레이딩 데스크" 의 나머지 절반인 **오른쪽 뇌(비중→가상매매→채점→복리)**
가 통째로 미착수였다. `/resume` 인터뷰로 오른쪽 뇌 roadmap 착수 + 첫 자식 확정 결정.
**핵심 판단**: roadmap SPEC + 4 자식 의존 사슬을 세우고, 첫 자식(계좌관리자) 비중 판단 로직은
"보수 vs 공격 고정 선택"이 아니라 **리스크(고정)×regime(변조) 두 레버**로 — 사람이 안 정하고
시장상태가 공격성을 정하게. 본 세션 = 설계(SPEC)만, 코드 X (SDD).

## 한 일
- `docs/specs/RIGHT-BRAIN-COMPLETION-001-right-brain-completion.md` (신규 roadmap) — 4 마일스톤
  (RB-MS1 비중 / MS2 가상매매 / MS3 채점 / MS4 복리) + 경계 결단 4건(가상 전용·4계좌·코스피+미장
  벤치마크·7계명 하드 제약) + 완료 정의. children 4 등재.
- `docs/specs/ACCOUNT-MANAGER-001-position-sizing.md` (신규, RB-MS1 첫 자식) — 인터뷰로 판단 로직
  4건 **확정**: 비중=리스크R(stop 역산)×regime 변조 총한도 / 분할=과열도(extension) 함수
  (좋은타점 front-load·고점 back-load) / 게이트=비중초과 자동축소+손절누락만 하드차단 / MVP=풀.
  수치·스키마 디테일만 INTERVIEW-SLOT 잔존.
- `docs/specs/PAPER-TRADING-001-virtual-fills.md` (신규, RB-MS2 스켈레톤) — 비중 지시→가상 체결
  기록·계좌 책임 추적. INTERVIEW-SLOT(체결가·매도/손익·매일 데스크 루프).
- `docs/specs/WEALTH-COMPOUND-TRACKER-001-compounding-curve.md` (신규, RB-MS4 스켈레톤) — 실현손익
  →4계좌 자산 곡선·복리 목표 진척. INTERVIEW-SLOT(자산곡선·복리목표).
- `docs/specs/PROJECT-NORTH-STAR-001-master-roadmap.md` — RIGHT-BRAIN child 연결 + 두 기둥 표 갱신.
- `docs/specs/LEFT-BRAIN-COMPLETION-001-left-brain-completion.md` — status `draft→done` (4/4 종결).
- `docs/specs/GUIDANCE-ACCURACY-TRACKER-001-five-kpi-tracking.md` — `level:implementation` +
  `parent:RIGHT-BRAIN-COMPLETION-001` 편입(RB-MS3) → drift 14→13 해소.

## 검증 결과
- ✅ `scripts/project_status.py` — `PROJECT-NORTH-STAR-001 1/2(50%)` → `RIGHT-BRAIN-COMPLETION-001
  0/4(0%)` 4 자식 전부 draft·미작성 0. LEFT-BRAIN 4/4 done. drift 13(GUIDANCE 편입).
- ✅ `scripts/validate.py` — 0 errors (registry.yaml 경고는 기존·무관).
- ⚠️ YAML 함정: depends_on 항목 본문에 콜론(`:`) 있으면 dict 파싱 → string 검증 실패. 콜론 제거로 해소.

## 의도적으로 안 한 것
- 실 구현 코드 — roadmap+스켈레톤 설계까지(SDD: SPEC 없이 코드 X). ACCOUNT-MANAGER-001 SDD 는 다음 세션.
- RB-MS2/MS4 INTERVIEW-SLOT 채우기 — RB-MS1 구현 후 순차(의존 사슬).
- 503 retry·한국 뉴스 소스(직전 RESUME Top 2/3) — 오른쪽 뇌 착수 사인오프 우선이라 보류.

## 기술 부채/미완
- ACCOUNT-MANAGER-001 수치 SLOT: R값(1%/1.5%)·R배수 상한·regime 배포 밴드·과열도↔분할 비율·스키마
  컬럼 = 다일 누적 후 튜닝([[feedback_backtest_essence]]).
- GUIDANCE-ACCURACY-TRACKER-001 채점 벤치마크에 미장 지수(S&P/나스닥) 추가 정렬 필요(현 코스피만).
- gemini 503 retry·한국 뉴스 소스 미배선(이월).

## 다음에 이어서 할 작업 (우선순위)
1. **ACCOUNT-MANAGER-001 SDD 구현** — 판단 로직 확정됨. `/spec-interview` 로 수치 SLOT·스키마 마저
   채운 뒤 SDD: persona/manifest + core/account/sizing.py(리스크×regime) + config/accounts.yaml +
   account_state/positions 스키마 + 테스트. 첫 production 시연 = `swing:` 권고→계좌별 비중·분할.
2. **PAPER-TRADING-001 (RB-MS2)** — RB-MS1 후. 가상 체결 기록 + 매일 데스크 루프(run_daily_refresh 합류).
3. **gemini transient 503 retry 배선** — 이월 작은 부채(core/llm/client.py provider 명시 경로).

## 커밋 상태
- wrap-up docs 커밋(c_worked·RESUME·SESSIONS) + SPEC 7파일 커밋 → main 직접 + push 예정.
- `.claude/scheduled_tasks.lock`(untracked) 무관 산출물 → 커밋 제외.
