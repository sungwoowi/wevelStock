---
date: 2026-06-13
topic: PAPER-DESK-UX-001 — /desk + /desk/[id] 본체 (RB-MS5 화면 3/3 완성)
status: completed
plan_file: C:\Users\HOME\.claude\plans\hazy-conjuring-bonbon.md
---

# 2026-06-13 · PAPER-DESK-UX-001 — /desk + /desk/[id] 본체 (화면 2·3)

## 배경
지난 세션(3세션)이 시황 화면 1/3 + 시점 히스토리 LNB + market API를 완성. 이번 세션 = 오른쪽 뇌 핵심 산출(4계좌·자산곡선·회고 KPI·보유/회차/청산)을 보는 **데스크 본체 + 계좌 상세** 2화면을 한 번에 채워 **RB-MS5 화면 3/3 완성**. 디자인 정본 `design-lightmode-spec.pen`의 `g1EUS`(02·가상매매)·`P88ZI`(02a·계좌 상세)를 픽셀 단위로 읽어 충실 구현. **핵심 판단**: 정본엔 있으나 API가 못 주는 5칸 → 사용자 결정 "기존 테이블 노출까지" — `account_fills`·`team_outputs` read 엔드포인트만 추가(신규 테이블 0, 가드 #11), 진짜 미산출(지수 오버레이 시계열·샤프·손익비 ratio)은 graceful 제외.

## 한 일
### 백엔드 (전부 기존 테이블 read — 신규 테이블 0)
- `core/guidance/kpi.py` — `get_kpi_summary(account_id=)` 필터 + `_compute_record_kpi` 출력에 account_id 보존 (계좌별 KPI).
- `server/api/guidance.py` — `/api/guidance/kpi?account_id=` 쿼리 통과.
- `core/strategist/recommendation.py` — `load_recommendation(rec_id)` 추가 (보유 포지션 원안 재구성용).
- `core/account/desk_view.py` (신규) — 데스크 read view 조립: `get_position_tranches`(회차 filled+pending 사다리)·`get_account_pending`(매수대기=사다리 대기+권고 관망)·`get_account_closed`(청산)·`recent_fills`(매매일지)·`active_recommendations_view`. pending 사다리 = `load_recommendation`+`size_position`(state 0 원안)+`compute_tranche_ladder` 재사용.
- `server/api/accounts.py` — `/accounts/{id}/holdings` 응답 enrich: holding마다 `tranches`, 최상위 `pending`·`closed`.
- `server/api/desk.py` (신규) + `server/main.py` — `/api/desk/feed`(활성 권고 + 최근 체결 일지) 라우터.
- `tests/test_guidance_kpi.py`(+account_scope) · `tests/test_account_desk_view.py`(신규 5케이스).

### 프론트 (지난 세션 패턴 재사용)
- `webapp/src/lib/format.ts` (신규) — MarketBoard 포맷 추출(fmtNum/fmtPct/wonM/wonB/tradeAmt/joM/changeClass) + 데스크 손익 헬퍼(`pnlClass`·`wonKR`·`wonKRSigned`·`manWon`). MarketBoard는 import 전환.
- `webapp/src/app/globals.css` — `--color-profit`/`--color-loss` 시맨틱 토큰(라이트/다크 쌍).
- `webapp/src/lib/api.ts` — 데스크 타입(WealthCurve/Progress·Account·Kpi·Holding·Tranche·Pending·DeskFeed 등).
- `components/desk/` (신규) — `primitives`(Card/Metric/TrackChip/ProgressBar/Badge) · `labels`(verdict/reason 한국어) · `WealthCurveCard`(recharts 2시리즈+목표/시드선+기간토글, CSS-var 테마색 hook) · `MetricStrip`(6, 샤프·손익비 graceful) · `DeskBoard`(헤더·KPI 4·4계좌카드·활성권고·매매일지) · `AccountDetail`(계좌탭·요약 5·보유 테이블+회차 펼치기·매수대기·이익실현).
- `webapp/src/app/desk/page.tsx`(placeholder→본체) · `app/desk/[accountId]/page.tsx`(신규).

## 검증 결과
- ✅ `tsc --noEmit` EXIT=0
- ✅ pytest **1150 passed** (+5 신규, 회귀 0)
- ✅ 백엔드 200 + 실데이터: `/desk/feed`(현대차·SK하이닉스 wait→관망), `/guidance/kpi?account_id=kr_long`(account 스코프), `/accounts/kr_long/holdings`(tranches·pending·closed enrich), wealth/curve(3점)·progress(alpha −5.08%)·accounts(4)
- ✅ Next 라우트 200: `/desk`·`/desk/kr_long`·`/desk/kr_swing`·`/`(시황 회귀), 셸 렌더(FractalSignal·가상매매), error boundary 없음

## 의도적으로 안 한 것
- 자산곡선 코스피/나스닥 **오버레이 라인**(벤치마크 시계열 미보유 → 2시리즈만), **샤프·손익비 ratio**(미산출 → "준비 중") — 진짜 신규 계산, 다음 SLOT.
- 채팅·뉴스·알림 본체(placeholder 유지) · production-chat 물리 이동(dev 서버 락) · 라이트 팔레트 `.pen` 정밀 재추출.

## 맥락 재진입 힌트
- **색상 = 의미색 vs 한국식 분리**: 데스크 손익은 수익 초록/손실 빨강(`pnlClass`), 시황 지수는 한국식 빨강↑/파랑↓(`changeClass`). 각 정본 프레임이 실제로 그렇게 그려져 있어 충실 매칭.
- **현재 라이브 = 방어장 빈 데이터**(보유 0·청산 0·자산 4억 flat·alpha −5.08%) → 화면은 정본의 예시 채움이 아니라 graceful 빈 상태로 렌더(의도). 시각 정본 대조는 사용자 육안(localhost:3000/desk)으로 완결 권장.
- **pending 사다리 원안 재구성**: 이미 열린 포지션 비중이 deployment_cap을 잠식 안 하게 `size_position(state=0)`으로 산출 → 체결 leg 제외 = pending.

## 다음에 이어서 할 작업 (우선순위)
1. **채팅·뉴스·알림 본체 + production-chat 물리 이동** — 5탭 placeholder 채우기. 채팅=`/dev/production-chat` SSE 재사용 / 알림=notifications 영속 리스트 / production-chat `git mv`(dev 서버 락 풀릴 때).
2. **라이트 팔레트 `.pen` 정밀 추출 + 다크 화면 대조** — 현 라이트는 파생값, design-darkmode-spec.pen 대조로 다크 정본 검증. 데스크 2화면 육안 시각 대조.
3. **데스크 미산출 지표 백엔드(다음 SLOT)** — 벤치마크 시계열(지수 오버레이)·샤프·손익비 ratio. 라이브 청산 누적되면 verified 게이트 동반.

## 커밋 상태
- 아직 안 됨 — wrap-up 에서 ① feat(구현) ② docs(wrap-up) 2커밋 → main push.
