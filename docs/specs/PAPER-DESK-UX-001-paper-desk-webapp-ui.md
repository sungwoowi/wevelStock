---
spec_id: PAPER-DESK-UX-001
title: 페이퍼 트레이딩 데스크 webapp UI/UX — 시황·가상매매·계좌 상세 (FractalSignal, 1차)
team: shared
type: feature
status: implementing
version: 1
level: implementation
parent: RIGHT-BRAIN-COMPLETION-001
owner: account_manager
generates:
  - webapp/src/app/page.tsx                         # 01 시황(홈) — production 루트
  - webapp/src/app/desk/page.tsx                    # 02 가상매매(데스크) — 4계좌·자산곡선·KPI
  - webapp/src/app/desk/[accountId]/page.tsx        # 02a 계좌 상세 — 회차 사다리·매수대기·이익실현
  - webapp/src/components/theme/ThemeProvider.tsx   # next-themes provider (light/dark/system)
  - webapp/src/components/theme/ThemeToggle.tsx     # 🌓 토글 (헤더)
  - webapp/src/components/nav/AppShell.tsx          # 5탭 셸 (PC 사이드바 / 모바일 하단 탭바) + 헤더 ❔ 가이드
  - webapp/src/components/charts/EquityCurve.tsx    # Recharts 자산곡선 2시리즈(실현 vs 총)+목표선
  - webapp/src/components/charts/IndexLine.tsx      # Recharts 지수 라인(코스피·나스닥)
  - webapp/src/components/desk/KpiSummary.tsx       # 회고 KPI 묶음(누적 수익·승률·건수·벤치마크 초과)
  - webapp/src/components/desk/AccountCard.tsx      # 4계좌 카드(비중·여력·평가손익)
  - webapp/src/components/market/MarketBoard.tsx    # 시황 집계 카드 묶음(지수·등락·수급·섹터RS·자산군)
  - server/api/market.py                            # 시황 집계 read 엔드포인트 (/api/market/snapshot)
modifies:
  - webapp/src/app/layout.tsx                       # ThemeProvider 도입·dark 하드코딩 제거·AppShell 적용
  - webapp/src/app/globals.css                      # FractalSignal 팔레트(light/dark) 토큰 이식 (현 OKLCH 그레이스케일 교체)
  - webapp/package.json                             # recharts + next-themes 추가
  - webapp/src/app/analyst-chat/                    # → webapp/src/app/dev/analyst-chat/ 이전 (R&D 보존)
  - webapp/src/app/production-chat/                 # → webapp/src/app/dev/production-chat/ 이전 (R&D 보존)
  # 시각 정본(읽기 전용 참조, generate/modify 아님): webapp/design-darkmode-spec.pen / webapp/design-lightmode-spec.pen
  - server/main.py                                  # market 라우터 등록
depends_on:
  - RIGHT-BRAIN-COMPLETION-001 (소속 roadmap — 가상 전용·4계좌 경계 상속)
  - PAPER-TRADING-001 (account_state/positions/fills — /api/accounts·holdings read)
  - GUIDANCE-ACCURACY-TRACKER-001 (회고 KPI — /api/guidance/kpi·retrospective read)
  - WEALTH-COMPOUND-TRACKER-001 (자산 곡선 — /api/wealth/curve·progress read)
  - "INFRA-MARKET-ASSETS-002 (별 SPEC, 후속): WTI·브렌트·야간선물 수집 + 알림 영속 테이블. 자산군 3종·채팅/뉴스/알림 탭은 이 SPEC 후 2차"
contracts:
  - name: market-snapshot-v1
    version: "1.0"                                  # 본 SPEC 신규 — 시황 집계 read 응답 구조
  - name: position-sizing-v1
    version: "1.0"                                  # ACCOUNT-MANAGER-001 (read)
  - name: paper-fill-v1
    version: "1.0"                                  # PAPER-TRADING-001 (read)
  - name: equity-snapshot-v1
    version: "1.0"                                  # WEALTH-COMPOUND-TRACKER-001 (read)
---

# PAPER-DESK-UX-001 — 페이퍼 트레이딩 데스크 webapp UI/UX (1차)

> **이 문서는 implementation-level SPEC 이다.** RIGHT-BRAIN-COMPLETION-001 의 자식 — 오른쪽 뇌(비중·가상매매·채점·복리)가 **코드로는 완성됐으나 "한눈에 보는 화면"이 없어** 매일 도는 데스크를 사람이 쓸 수 없는 차단점을 해소한다.
>
> **무게중심은 백엔드가 아니라 프론트 빌드.** 데스크가 소비할 API 는 대부분 이미 존재(`/api/accounts`·`/api/guidance/*`·`/api/wealth/*`). 신규 백엔드는 시황 집계 read 엔드포인트 1개뿐. 나머지는 Next.js 화면·테마·차트.
>
> **시각 정본 = `webapp/design-darkmode-spec.pen`(다크)/`design-lightmode-spec.pen`(라이트) FractalSignal 테마 쌍.** (옛 `uiux-sample-draft.pen` 은 IA 탐색 드래프트 — 시각 근거 아님.) 모바일 수치 = `.pen` ÷2(캔버스 2× 배율).

## 목적
- 오른쪽 뇌 산출(4계좌 보유·평가손익·회고 KPI·자산 곡선·시황)을 **production UI 한 벌**로 노출 — backend 노출 0 ([[feedback_webapp_production_ux]]).
- 1차 = **시황(홈) + 가상매매(데스크) + 계좌 상세** 3화면 (PC+모바일). 채팅·뉴스·알림은 셸에 탭만 두고 2차.

## 경계 (scope)
- **포함 (1차)**: 화면 01 시황 · 02 가상매매 · 02a 계좌 상세 + 5탭 셸 + 테마 토글(next-themes) + Recharts + 시황 집계 read 엔드포인트.
- **제외 (2차/별 SPEC)**:
  - 채팅(03)·뉴스(04)·알림(05) 화면 본체 — 탭/라우트만 두고 placeholder. (채팅은 기존 `/dev/production-chat` SSE 재사용 예정)
  - **신규 수집 (별 INFRA SPEC)**: WTI·브렌트·야간선물 자산군 3종, 알림 영속 테이블.
- **R&D 페이지 보존**: 기존 `/`·`/analyst-chat`·`/production-chat` → `/dev/*` 로 이전(삭제 X).
- **데이터 게이트 무관 빌드**: 자산 스냅샷·체결이 아직 적음(방어장) — UI 는 graceful empty 로 지금 빌드, 차트는 데이터 누적되며 채워짐. 시각 검증은 dev seed fixture.
- **일배치 기준**: 데이터는 18:05 cron 일 단위 — 실시간 틱 아님. SWR 폴링으로 충분(채팅만 SSE).

## 라우트 매핑
| 구분 | 기존 | 수정 후 | 1·2차 |
|---|---|---|---|
| Production 시황(홈) | — | `/` | 1차 |
| Production 가상매매 | — | `/desk` | 1차 |
| Production 계좌 상세 | — | `/desk/[accountId]` | 1차 |
| Production 채팅·뉴스·알림 | — | `/chat`·`/news`·`/alerts` | 2차(탭 placeholder) |
| R&D 데모 홈 | `/` | `/dev` | 보존 |
| R&D 분석가 비교 | `/analyst-chat` | `/dev/analyst-chat` | 보존 |
| R&D 자연어 채팅 | `/production-chat` | `/dev/production-chat` | 보존(→ `/chat` 원천) |

## 소비 데이터 (대부분 기존 API read)
| 화면 영역 | 엔드포인트 | 상태 |
|---|---|---|
| 4계좌·여력·비중 | `GET /api/accounts` | 기존 |
| 계좌 보유·평가손익 | `GET /api/accounts/{id}/holdings` | 기존 |
| 회고 KPI·벤치마크 | `GET /api/guidance/kpi`·`/retrospective` | 기존 |
| 자산 곡선·목표 진척 | `GET /api/wealth/curve`·`/progress` | 기존 |
| 브리핑 한줄평/펼치기 | `GET /api/briefings/feed`·`/{run_id}` | 기존 |
| **시황 집계(지수·등락·수급·섹터RS·자산군)** | `GET /api/market/snapshot` | **신규 (본 SPEC)** |

---

## 판단·구현 로직 (INTERVIEW-SLOT)

<!-- SPEC:INTERVIEW-SLOT role="market-snapshot-endpoint" -->
**시황 집계 read 엔드포인트 `/api/market/snapshot` (market-snapshot-v1).**
DB 에 이미 있는 것 전부 한 응답으로 집계(섹션별 partial 허용, 미수집은 null):
- 지수: `market_macro_snapshot`(KOSPI/KOSDAQ index_close·MA position·trend) + `us_macro_snapshot`(nasdaq·sox·sp500 등락·risk_signal·vix)
- 등락 종목 수: `market_macro_snapshot`(advancing·declining·unchanged·breadth_ratio)
- 5주체 수급: `supply_demand_history`(foreign·institution·individual·financial_inv·pension net)
- 섹터 RS: `sector_rs_snapshot`/`market_view_snapshot`
- 자산군: 금(`chart_ohlcv` KRX금)·환율(`us_macro` dxy)·금리(`us_macro` us_10y)·VIX. **WTI·브렌트·야간선물 = null (별 INFRA SPEC 후)**
- 한줄평: `team_outputs` 최신 브리핑 narrative (DB-first, fan-out 금지)
> 시황 충실도 = "거의 풀"(DB 에 있으면 다 렌더), 미수집 3종만 후속. 결정론 read 만, LLM 호출 0.
<!-- /SPEC:INTERVIEW-SLOT -->

<!-- SPEC:INTERVIEW-SLOT role="theme-token-port" -->
**FractalSignal 팔레트 이식 (globals.css).**
현 `globals.css` 는 shadcn 기본 OKLCH 그레이스케일 — 디자인 정본 쌍의 실색으로 교체.
- light/dark 두 테마 토큰 쌍 정의, next-themes `class` 전략(현 `dark` 하드코딩 제거).
- **CTA/액센트 = 테마별 듀얼**: 다크 에메랄드 `#10B981` / 라이트 Rausch `#FF385C` ([[feedback_design_visual_preferences]] 확정).
- 다크 가독성 수렴값 적용(본문 #C2C7CE·보조 #9AA0A8·파랑 #6FBAFF).
- 색 추출 = design-darkmode-spec.pen(다크)/design-lightmode-spec.pen(라이트) 노드 read 로 화면별 확정 (구현 시).
<!-- /SPEC:INTERVIEW-SLOT -->

<!-- SPEC:INTERVIEW-SLOT role="desk-kpi-and-curve" -->
**가상매매(데스크) 화면 = 자산 곡선 + KPI 묶음 + 4계좌.**
- 자산 곡선: Recharts 2시리즈(realized_equity 실현 vs equity 총=마크투마켓) + 목표선(연 18%) + 기간 5단 토글(1M~전체). 출처 `/api/wealth/curve`·`/progress`.
- KPI 묶음(정직한 묶음 — [[project_state]]): 누적 실현수익 · 승률 · 청산 건수 · 벤치마크 초과(alpha). closed_count 0 시 전 지표 null graceful.
- 4계좌 카드: 비중·여력·평가손익(`/api/accounts`). 클릭 → `/desk/[accountId]`.
> 곡선/KPI 정의·라벨 자연어는 디자인 정본 02 프레임 read 로 확정.
<!-- /SPEC:INTERVIEW-SLOT -->

<!-- SPEC:INTERVIEW-SLOT role="account-detail" -->
**계좌 상세(02a) = 회차 사다리 + 매수 대기 + 이익실현.**
- 보유 종목 회차(tranche) 사다리(평단·차수·수량) — `/api/accounts/{id}/holdings`.
- 매수 대기(지정가 도달 전 차수) + 이익실현(청산 내역) — `account_fills` 파생.
> 구체 카드 구성은 디자인 정본 02a(P88ZI) read 로 확정.
<!-- /SPEC:INTERVIEW-SLOT -->

<!-- SPEC:INTERVIEW-SLOT role="app-shell-nav" -->
**5탭 셸 + 헤더 ❔ 가이드.**
- 탭 5축 = 시황 · **가상매매** · 채팅 · 뉴스 · 알림 (라벨 "데스크" 아님 — [[project_wevelstock]] 용어 확정).
- PC = 좌측 사이드바(또는 상단) / 모바일 = 하단 탭바(5개). 가이드(06) = 헤더 ❔ 진입(탭 아님). 알림 = 종 배지 미독 카운트.
- 1차 = 시황·가상매매 활성, 채팅·뉴스·알림 탭은 placeholder 라우트.
> 레이아웃·반응형 분기는 디자인 정본 PC 프레임 + M-* 모바일(2× 배율) read 로 확정.
<!-- /SPEC:INTERVIEW-SLOT -->

## 검증 방법
- `webapp` 빌드/실행 후 `/`(시황)·`/desk`(가상매매)·`/desk/[id]`(상세) 렌더 + 테마 토글(light/dark/system) 동작 + Recharts 곡선/지수 렌더.
- graceful empty: 체결 0·스냅샷 1일 상태에서 크래시 0, KPI null 일관.
- `/api/market/snapshot` 라이브 응답에 지수·등락·수급·섹터RS·자산군(미수집 3종 null) 포함 확인.
- 디자인 정본 쌍과 화면 대조(색·타입·레이아웃) — 모바일 ÷2 패리티.
- `PYTHONIOENCODING=utf-8 uv run python scripts/project_status.py` 에서 RIGHT-BRAIN 자식으로 PAPER-DESK-UX-001 표시(미연결 drift 아님).

## 비목표
- 실시간 틱/WebSocket (일배치 + SWR 폴링으로 충분).
- 채팅·뉴스·알림 화면 본체 (2차).
- 신규 수집(WTI·브렌트·야간선물·알림 영속) — 별 INFRA SPEC.
- 주문 실행 (가상 전용, roadmap 경계 상속).
