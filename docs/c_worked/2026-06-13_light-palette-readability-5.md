---
date: 2026-06-13
topic: 라이트 팔레트 정본 정밀 교정 + 가독성 보정 (회색 배경 + 흰 카드)
status: completed
plan_file: C:\Users\HOME\.claude\plans\hazy-conjuring-bonbon.md
---

# 2026-06-13 · 라이트 팔레트 정밀 + 가독성 보정

## 배경
PAPER-DESK-UX 화면 3/3 완성 후, `globals.css`의 **라이트 토큰이 다크 실측의 파생값**이라 정본 `design-lightmode-spec.pen`과 어긋남(border `#e5e7eb≠#dddddd`·상승색 `#e5484d≠#dc2626`·heading `#0a0a0a≠#222222` 등). 정본 라이트 프레임(`ZS1WM`·`g1EUS`·`P88ZI`)을 픽셀 읽어 토큰 ~9개 교정. **핵심 판단: 정본 픽셀 충실 → 실제 화면에서 회색이 너무 연해 안 띔(사용자 피드백) → 의도적으로 정본보다 대비 한 단계 올림 + 앱 배경 옅은 회색·흰 카드 채택(밀집 대시보드식, 에어비앤비 그림자식 기각).** 다크는 지난 세션 실측이라 변경 0.

## 한 일
- `webapp/src/app/globals.css` (`:root` 라이트 토큰만) —
  - **정본 정밀 교정**: foreground `#222222` · body → `#3f3f3f` · border/input `#dddddd` · surface `#f7f7f7` · up(상승) `#dc2626` · info `#2563eb` · amber-bg `#fff7ed` · active pill `#e5e7eb` · muted-fg/faint 톤.
  - **가독성 보정(정본 대비 의도적 deviation)**: border `#cfd1d5` · surface(타일) `#eef0f2` · muted-fg/flat `#595d63` · faint `#82868e` · body `#353535`.
  - **카드 분리**: `--background` `#ffffff → #f7f8fa`(옅은 회색) + 카드 흰색 유지 → 회색 배경 위 흰 카드로 분리(그림자 0).
- 다크(`.dark`) 토큰 변경 0 (실측 유지, 라이트 수정과 독립).

## 검증 결과
- ✅ `tsc --noEmit` 0 (CSS 변경, 회귀 0)
- ✅ 라우트 200: `/`·`/desk`·`/desk/kr_long` (CSS 재컴파일 정상)
- ✅ 사용자 육안 승인 — "훨씬 낫다, 잘 보인다, 이대로 가자" (라이트 모드)

## 의도적으로 안 한 것
- **다크 모드 .pen 정밀 대조** — 다크 토큰 미변경(실측)이라 라이트와 독립. 사용자 테마 토글 육안만 권고(미수행). 정식 대조는 `design-darkmode-spec.pen` 탭 활성화 필요.
- 호버 그림자(에어비앤비식) — 옵션 A(그림자 0) 채택으로 불요.
- 정본 보조색 토큰 신설(보합 바 `#d1d5db`·등락 구분선 `#ebebeb`) — 과잉 경계, 육안 OK라 보류.

## 맥락 재진입 힌트
- **정본 픽셀 ↔ 실제 가독성 충돌 시 가독성 우선**: .pen은 캔버스라 연한 회색도 또렷하나 실 브라우저 흰 배경에선 카드/보더/보조텍스트가 묻힘. 사용자 선호=대비 확보([[feedback_design_visual_preferences]] "침침 회피" 연장). → 정본보다 회색 한 단계 진하게 + 회색 앱 배경.
- **에어비앤비 = 흰 배경+흰 카드+그림자**(밀집 카드엔 그림자 노이즈) ≠ 우리 채택(회색 배경+흰 카드, Linear/Stripe식 밀집 대시보드 표준).
- 색은 전부 시맨틱 토큰 → `globals.css` 한 파일 수정이 전 화면 전파(컴포넌트 하드코딩 hex 0, WealthCurveCard도 getComputedStyle).

## 다음에 이어서 할 작업 (우선순위)
1. **채팅·뉴스·알림 본체 + production-chat 물리 이동** — 5탭 중 셋 placeholder. 채팅=`/dev/production-chat` SSE 재사용 / 뉴스=news digest / 알림=notifications 영속 / production-chat `git mv`.
2. **데스크 미산출 지표 백엔드** — 자산곡선 지수 오버레이 라인(벤치마크 시계열)·샤프(일별수익 std)·손익비 ratio. 라이브 청산 누적 시 verified 게이트 동반.
3. **다크 모드 .pen 정밀 대조** — `design-darkmode-spec.pen` 탭 활성화 후 `.dark` 토큰 대조 + 라이트 동일 가독성 점검. (잔여 시각: 보합 바·구분선 보조색)

## 커밋 상태
- 아직 안 됨 — wrap-up 에서 globals.css + 기록 파일 묶어 커밋 → main push.
