---
date: 2026-06-09
topic: WEALTH-COMPOUND-TRACKER-001 (RB-MS4) — 매일 자산 스냅샷 복리 곡선 (오른쪽 뇌 4 자식 코드 완성)
status: completed
plan_file: C:\Users\HOME\.claude\plans\drifting-foraging-yeti.md
---

# 2026-06-09 · WEALTH-COMPOUND-TRACKER-001 (RB-MS4) 복리 추적

## 배경
오른쪽 뇌 넷째(마지막) 자식. 같은 날 RB-MS3 직후 `/spec-interview`. 사용자가 SDD 이해도 약해
"슬림/풀세트 차이가 뭐냐"를 깊게 되물었고, 그 과정에서 **사용자가 핵심 통찰 제시**:
"매일 종가 한 번 받아 평가→저장하면 되는 거 아냐?" → 맞음. **going-forward 마크투마켓 스냅샷은
싼 것(MVP)**, 비싼 건 **과거 매일 평가 소급(가격 시계열)** 뿐. + 사용자 요청으로 **두 곡선**(실현만
vs 실현+평가). 추적만(복리 *전략 판단*은 왼쪽 뇌 wealth_strategist).

## 한 일
- `core/account/compounding.py` (신규) — `snapshot_equity`(매일 계좌별 총자산 한 줄, equity=seed+누적
  실현(account_fills)+미실현(holdings 오늘 종가), 멱등) / `get_equity_curve`(**두 시리즈**: realized_equity·
  equity, 4계좌 통합·계좌별) / `compute_mdd`(순수) / `get_compound_progress`(연 18% 목표곡선 대비·MDD
  가드 -8%·벤치마크 알파, benchmark.py 재사용) / `render_compound_summary`(코드라벨 0).
- `core/db/schema.sql` — v15 `account_equity_snapshot`(date×account PK, 멱등). equity-snapshot-v1.
- `server/api/wealth.py` (신규) + main 등록 — GET /api/wealth/curve, /progress.
- `server/schedulers/jobs/daily_refresh.py` — 데스크 직후 `snapshot_equity` 합류(매일 한 점 누적).
- `server/telegram/{bot,commands}.py` — `/wealth` 자산 추적 명령.
- `scripts/_wealth_probe.py` (신규) + `tests/test_{account_compounding,wealth_api}.py` — 13 신규.
- `docs/specs/WEALTH-COMPOUND-TRACKER-001-...md` — SLOT 채움(매일 스냅샷·두 곡선) + status draft→implementing.

## 검증 결과
- ✅ `TESTING=1 pytest` 전체 **1110 passed**(+13, 회귀 0). validate 0 errors.
- ✅ TDD RED→GREEN. probe(두 곡선: 06-05 실현만 10,001,500 vs 총 10,003,000 + 복리 진척·MDD·코스피 대비).
- ✅ project_status `🔨 WEALTH-COMPOUND-TRACKER-001 [implementing]`. **RIGHT-BRAIN 4 자식 전부 코드 완성**(1 verified·3 implementing), 1/4(25%) verified.

## 의도적으로 안 한 것 (SLOT)
- **과거 매일 평가 소급** — 보유 종목 과거 가격 시계열 인프라 필요(비쌈). 첫 스냅샷이 누적 실현 다 포함하므로 going-forward 로 충분.
- **박종훈 framework 사이클 인용** — wealth_strategist(왼쪽 뇌) 영역, 추적만.
- **일/주/월 고정 롤업** — 체결/스냅샷 이벤트 시점 그대로.

## 기술 부채/미완
- WEALTH·GUIDANCE·ACCOUNT-MANAGER 모두 implementing — 라이브 데스크 청산/스냅샷 다일 누적 후 verified.
- **자산복리부 정체성 재정의**([[project_wealth_dept_identity]]) — 사용자 제기: "복리"가 지식부(박종훈 거시 frame)와 RB-MS4 추적(실현손익 곡선)에서 의미 충돌. 다음 지식부 정비 라운드에서 ①거시 길잡이 ②복리 전략 재정의 ③워딩 분리 결정.
- **PAPER-DESK-UX-001** — 오른쪽 뇌 UI/UX(webapp 대시보드·텔레그램) 별도 SPEC ("날 잡아서").

## 다음에 이어서 할 작업 (우선순위)
1. **오른쪽 뇌 verified 마감 + 라이브 청산 누적** — ACCOUNT-MANAGER/GUIDANCE/WEALTH implementing→verified(라이브 데스크 청산·스냅샷 다일 누적 후). 실 매수 verdict 권고로 데스크 체결 라이브 관찰.
2. **PAPER-DESK-UX-001** — 오른쪽 뇌 기능을 한눈에 보는 webapp 대시보드 + 텔레그램 다듬기. `/spec-interview`.
3. **자산복리부 정체성 재정의** — 지식부 9 정비 라운드에서 "복리부" 정체성·워딩 충돌 해소.

## 커밋 상태
- 코드(feat `12f9871`) 완료. 본 wrap-up docs → main 직접 + push 예정.
