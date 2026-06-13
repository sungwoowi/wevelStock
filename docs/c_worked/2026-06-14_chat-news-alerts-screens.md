---
date: 2026-06-14
topic: 채팅·뉴스·알림 본체 — 5탭 전부 활성 (PAPER-DESK-UX 화면 마감)
status: completed
plan_file: C:\Users\HOME\.claude\plans\hazy-conjuring-bonbon.md
---

# 2026-06-14 · 채팅·뉴스·알림 본체 (5탭 완성)

## 배경
PAPER-DESK-UX 화면 3/3(시황·데스크·계좌상세) + 라이트 팔레트 완성 후, 5탭 중 **채팅·뉴스·알림이 placeholder**. 이 셋을 본체로 채워 **5탭 전부 활성**. 정본 라이트 프레임 `T8fhu`(채팅)·`L45yjk`(뉴스)·`OWnxc`(알림) 픽셀 읽어 충실. **핵심 판단: 백엔드는 뉴스 REST 라우터 1개만 신규(기존 build_news_digest·get_news_items·get_news_digest 조립, 신규 테이블 0·가드 #11) — 채팅 SSE·알림 API는 이미 완비라 백엔드 변경 거의 0. 채팅은 R&D production-chat 비의존 자체 구현(production-clean, 디버그 크롬 0).**

## 한 일
### 백엔드 (뉴스 라우터 1 — 전부 기존 함수/테이블 read)
- `server/api/news.py`(신규) — `GET /api/news/digest`(DB-first `get_news_digest`, 부재 시 `build_news_digest(persist=False)` 폴백) + `GET /api/news/items`(`get_news_items`). 위임만, `collectors/news_source.py` 변경 0.
- `server/main.py` — news 라우터 등록.
- `tests/test_news_api.py`(신규 3) — items·digest 폴백·empty graceful.

### 프론트 (3 화면 + 공용)
- `webapp/src/lib/api.ts` — News 타입(NewsDigest·NewsItem·NewsItemsResp·NotificationsResp) + Notification에 `notification_type`/`is_read` 보강.
- `webapp/src/components/nav/AppShell.tsx` — TABS `/chat`·`/news`·`/alerts` `active:true`(「곧」 제거).
- **채팅** `components/chat/useChatStream.ts`(신규 SSE 훅 — `/api/chat/production/stream` 소비, text_delta 프리뷰·formatted 최종·analyst_prefetch/agent_done 근거 수집, **디버그 미노출**) + `ChatColumn.tsx`(말풍선 사용자 green/어시스턴트 흰카드+근거 토글·입력바) + `app/chat/page.tsx`(시장 한줄 카드=market_view.one_liner 재사용).
- **뉴스** `components/news/NewsBoard.tsx`(톤 배지·단기/장기 2단 top_themes by time_axis·수집 뉴스 리스트 category 한글 태그) + `app/news/page.tsx`(SWR digest·items).
- **알림** `components/alerts/AlertsBoard.tsx`(필터 칩·날짜 그룹·type→아이콘/보더 🔴위험/🟢매매/🔵시장·미독 강조) + `app/alerts/page.tsx`(SWR `/recent?limit=50` + 진입 시 mark-read → 종 배지 클리어).

## 검증 결과
- ✅ `tsc --noEmit` EXIT=0
- ✅ pytest **1153 passed**(+3 news, 회귀 0)
- ✅ 백엔드 200 + 실데이터: `/news/items`(CNM earnings 등 실 RSS), `/notifications/recent`(주도주 브리핑), `/news/digest`(오늘 empty→graceful)
- ✅ 라우트 200 + 셸 렌더 무에러: `/chat`·`/news`·`/alerts`·`/`

## 의도적으로 안 한 것
- **채팅 라이브 1문(실 Gemini)** — 비용상 생략. SSE 계약은 R&D production-chat 경로로 검증됨 + tsc 가 이벤트 핸들링 타입 검증. localhost 직접 시연 가능.
- production-chat `git mv`→/dev (dev 서버 락) — `/chat` 자체 구현이라 비차단, 이동 잔여.
- 가이드(06) 화면·다크 정밀 대조·데스크 미산출 지표 — 별도/다음.

## 맥락 재진입 힌트
- **뉴스 digest는 오늘 날짜 기준** — 일일 cron 미적재 시 단기/장기 테마 empty(graceful), 수집 뉴스 리스트는 최근 데이터 노출. cron 돌면 채워짐. (오늘 날짜 폴백을 최신일자로 바꾸는 건 SLOT)
- **채팅 production-clean = 종합답변+근거만** — classification·token·cost 등 R&D 디버그는 production 경로에서 표면화 X([[feedback_webapp_production_ux]]). 근거 토글에 raw 분석가/전략가만.
- **알림 type→아이콘**: risk_alert=🔴 / trade_signal=🟢 / (account_safety·market_briefing·flow_idea)=🔵. 진입 시 mark-read는 limit=1 배지 키만 revalidate(리스트 미독 강조는 방문 중 유지).

## 다음에 이어서 할 작업 (우선순위)
1. **데스크 미산출 지표 백엔드** — 자산곡선 지수 오버레이(벤치마크 시계열)·샤프(일별수익 std)·손익비 ratio. 정본 graceful 제외분 라이브화. 라이브 청산 누적 시 verified 게이트 동반.
2. **다크 모드 `.pen` 정밀 대조 + 잔여** — `design-darkmode-spec.pen` 탭 활성화 → `.dark` 토큰 대조 + 5화면 다크 육안 + production-chat `git mv`→/dev + 뉴스 digest 최신일자 폴백.
3. **오른쪽 뇌 verified 게이트 마감** — WEALTH 스냅샷 ≥5영업일 / ACCOUNT-MANAGER 체결 ≥1 / GUIDANCE 청산 ≥3 라이브 누적 후 implementing→verified 승격.

## 커밋 상태
- 아직 안 됨 — wrap-up 에서 ① feat(구현) ② docs(wrap-up) 2커밋 → main push.
