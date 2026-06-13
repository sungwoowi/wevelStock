---
date: 2026-06-13
topic: PAPER-DESK-UX-001 구현 — 시황 화면 + 시점 히스토리 LNB (RB-MS5)
status: partial
plan_file: C:\Users\HOME\.claude\plans\declarative-shimmying-owl.md
---

# 2026-06-13 · PAPER-DESK-UX-001 구현 — 시황 화면 + 시점 히스토리 LNB

## 배경
오른쪽 뇌(비중·가상매매·채점·복리)는 코드로 완성됐으나 "한눈에 보는 화면"이 없어 매일 도는 데스크를 사람이 쓸 수 없는 게 RIGHT-BRAIN 마지막 차단점. 이번 세션 = SPEC draft→implementing + Next.js 스캐폴딩 + **시황(홈) 화면 + 시점 히스토리 LNB**. 무게중심=프론트, 신규 백엔드는 시황 집계 read 1개. **핵심 판단: 시황 집계는 신규 build 아니라 `build_market_snapshot` DB-first 래핑 + run_id별 briefing_parts 재조립(라이브 어댑터 재사용)** — fetch 0·LLM 0.

## 한 일
### 백엔드 (신규 1 라우터)
- `server/api/market.py` (신규) — `GET /api/market/snapshot[?run_id=&pipeline_id=]`(라이브 DB-first / run_id별 point-in-time 재조립) + `GET /api/market/history`(시점 목록 장전/장개시/장중/장마감). KOSPI200 야간선물 DB-first 배선(브리핑 파트), date-keyed getter(macro·sector_rs·us_macro·market_view) 재사용.
- `server/main.py` — market 라우터 등록.

### 프론트 스캐폴딩
- `webapp/package.json`(+lock) — recharts + next-themes 추가(npm).
- `webapp/src/app/globals.css` — FractalSignal 팔레트(.pen 다크 실측 + 라이트 파생) + 시맨틱 토큰(up/down/flat/cta/surface/body/faint/amber/info), next-themes class 전략(dark 하드코딩 제거).
- `webapp/src/app/layout.tsx` — ThemeProvider + AppShell + Geist Mono.
- `webapp/src/components/theme/{ThemeProvider,ThemeToggle}.tsx` (신규).
- `webapp/src/components/nav/AppShell.tsx` (신규) — 5탭 셸(PC 상단/모바일 하단), 알림 종 배지, `max-w-7xl`, R&D 라우트(/dev·/production-chat) 크롬 바이패스.
- `webapp/src/lib/api.ts` — MarketSnapshot/MarketHistoryItem 타입.

### 시황 화면
- `webapp/src/app/page.tsx` (신규 production 루트) — 히스토리 LNB + 시황 보드, SWR(라이브 120s / 과거 off), **② 필+콘텐츠 정렬** 레이아웃.
- `webapp/src/components/market/MarketBoard.tsx` (신규) — 시황 한마디(+브리핑 상세 펼침 토글)·🇰🇷국내지수(거래대금)·참고지표 12+2타일(야간선물 2종)·등락 breadth+비례막대·거래대금 상위·강세 섹터(RS 한줄)·수급. **한국식 색상(빨강↑/파랑↓)**.
- `webapp/src/components/market/HistorySidebar.tsx` (신규) — 시점 LNB(폭 288·sticky·독립 스크롤), 지금(라이브)/과거 시점 선택.
- `webapp/src/components/Placeholder.tsx` + `app/{desk,chat,news,alerts,guide}/page.tsx` (신규 placeholder).
- R&D 보존: `app/page.tsx`→`dev/page.tsx`, `analyst-chat`→`dev/analyst-chat` (git mv). 백링크 갱신.
- `docs/specs/PAPER-DESK-UX-001-*.md` — status draft→implementing.

## 검증 결과
- ✅ TypeScript `tsc --noEmit` 0 (반복 확인)
- ✅ `/api/market/snapshot` 200 (source_map db/db·sector 15), `/history` 6시점(라벨·요약), `?run_id=` historical 재조립(KOSPI·overnight·breadth·야간선물 5.16% + graceful null)
- ✅ 라우트 `/`·`/desk`·`/dev` 200, 셸 렌더(FractalSignal·시황·가상매매)
- ✅ 전체 pytest **1145 passed** (회귀 0)

## 의도적으로 안 한 것
- `/desk`·`/desk/[id]` 본체, 채팅·뉴스·알림 본체 (2차) — placeholder만.
- 라이트 팔레트 `.pen` 정밀 추출 (다크만 실측, 라이트는 파생).
- recharts 차트 (설치만, /desk 자산곡선용).

## 기술 부채/미완
- **production-chat → /dev 물리 이동** — dev 서버가 디렉터리 락(Permission denied) 반복. `/production-chat` 그대로 동작(`/chat` placeholder가 링크). 서버 내려간 틈에 처리.
- 과거 시점 sector_rs/market_view 미적재 날짜 = graceful null (데이터 누적되며 채워짐).
- 라이브 market_view 비어 있어 한줄평/브리핑 상세는 과거 시점에서만 노출(데이터 의존).

## 맥락 재진입 힌트 (이번 세션 협의 결정)
- **디자인 정본 .pen은 픽셀 단위로 봐야** — 임의 배치 금지(사용자 정정). 시안에 없는 추가(섹터 RS 라인·국내지수 섹션 등)는 **협의 먼저**(사용자 룰). 색상 한국식 통일.
- **LNB 레이아웃 = ② 필+콘텐츠 정렬**(Gmail/노션/ChatGPT식) 채택 — ① 센터드 클러스터는 메인 폭 빠듯(656px). 대시보드 다열 타일엔 ②가 적합(메인 ~960px).
- 데이터는 다 있었음(국장 지수·KOSPI200 야간선물·색상) — UI 추가 전 DB-first 확인 패턴.

## 다음에 이어서 할 작업 (우선순위)
1. **`/desk` 본체 (가상매매 데스크)** — 자산곡선 recharts 2시리즈(realized vs equity)+목표선+기간 토글 / KPI 묶음(누적·승률·청산·alpha) / 4계좌 카드. API `/api/wealth/curve`·`/progress`·`/api/accounts`·`/api/guidance/kpi` 다 존재(recharts 설치됨).
2. **`/desk/[accountId]` 본체 (계좌 상세)** — 회차 사다리(평단·차수)·매수 대기·이익실현. `/api/accounts/{id}/holdings` + account_fills 파생.
3. **채팅·뉴스·알림 본체 + 마무리** — 채팅=`/dev/production-chat` SSE 재사용 / 알림=notifications 영속 / production-chat 물리 이동(락 풀릴 때) + 라이트 팔레트 `.pen` 대조.

## 커밋 상태
- 아직 안 됨 — wrap-up 에서 ① feat(구현) ② docs(wrap-up) 2커밋 → main push.
