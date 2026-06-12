---
date: 2026-06-12
topic: PAPER-DESK-UX-001 SPEC 신설 (RB-MS5) + 디자인 .pen 리네임 + 정본 혼동 정정
status: completed
plan_file: C:\Users\HOME\.claude\plans\wobbly-jingling-puppy.md
---

# 2026-06-12 · PAPER-DESK-UX-001 SPEC 신설 + 디자인 파일 리네임

## 배경
디자인 전제(테마 쌍·FractalSignal·CTA 결정)가 모두 끝나 원 Top 1(페이퍼 데스크 화면 SPEC)으로 복귀. `/spec-interview`로 PAPER-DESK-UX-001 골격을 작성. **핵심 발견: 무게중심이 백엔드가 아니라 프론트 빌드** — 데스크가 쓸 API(`/api/accounts`·`/api/guidance/*`·`/api/wealth/*`)는 대부분 이미 존재, 신규 백엔드는 시황 집계 read 엔드포인트 1개뿐. **핵심 정정 2건**: ① `uiux-sample-draft.pen`은 IA 드래프트일 뿐 시각 정본이 아님(사용자 지적) — 정본 = design-spec 쌍 ② 사용자가 디자인 파일을 `design-darkmode-spec.pen`/`design-lightmode-spec.pen`으로 리네임 요청.

## 한 일
- `docs/specs/PAPER-DESK-UX-001-paper-desk-webapp-ui.md` — **신규 SPEC**(status draft, parent=RIGHT-BRAIN-COMPLETION-001). generates 13(webapp 화면·셸·테마·차트·시황 엔드포인트) + modifies 6 + contracts 4(market-snapshot-v1 신규). 5 INTERVIEW-SLOT(시황 집계 엔드포인트/테마 토큰 이식/데스크 곡선·KPI/계좌 상세/5탭 셸).
- `docs/specs/RIGHT-BRAIN-COMPLETION-001-*.md` — children에 PAPER-DESK-UX-001(RB-MS5) 추가 → roadmap 1/5(20%).
- `webapp/design-spec.pen` → `webapp/design-darkmode-spec.pen` (git mv, 다크 정본)
- `webapp/design-spec2.pen` → `webapp/design-lightmode-spec.pen` (git mv, 라이트 정본)
- `webapp/uiux-sample-draft`(확장자 없는 에디터 오저장 아티팩트, 15105줄) 삭제 — 정리. 진짜 `uiux-sample-draft.pen`(406KB)은 보존.
- `docs/RESUME.md` — 파일명 참조 전수 갱신 + 리네임 경고 박음 + `uiux-sample-draft.pen` "디자인 정본" 오라벨 → "IA 탐색 드래프트(시각 정본 아님)" 정정.
- 메모리 3종 갱신: `reference_pencil_mcp_active_tab`(정본=리네임 쌍·draft 프레이밍 해소)·`feedback_design_visual_preferences`(파일명)·`MEMORY.md`(인덱스).

## 면담 확정 결정 (SPEC 골격 시드)
- **MVP = 시황(홈) + 가상매매(데스크) + 계좌 상세** 3화면. 채팅·뉴스·알림은 탭만 두고 2차.
- **신규 수집(WTI·브렌트·야간선물 + 알림 영속)은 별 INFRA SPEC 분리** — UI SPEC이 collector까지 키우지 않음.
- **차트 = Recharts** (shadcn 공식 기반·테마 토큰 연동).
- **R&D 3페이지 → `/dev/*` 이전** 보존(삭제 X). production 루트: `/`(시황)·`/desk`(가상매매)·`/desk/[accountId]`.
- **시황 충실도 = "거의 풀"** (DB에 있으면 다 렌더 — 지수·등락·5주체 수급·섹터RS·자산군). 미수집 3종만 후속. (1차 "핵심만" 추천을 사용자가 정당하게 반박 → 상향)
- **지금 빌드 + graceful empty** (게이트 미충족이어도 UI는 빈 상태로 빌드, 차트는 데이터 누적되며 채워짐).
- **용어 = "가상매매"** (탭 라벨, "데스크" 아님).
- **시각 정본 = design-darkmode-spec.pen/design-lightmode-spec.pen 쌍** (uiux-sample-draft = IA만).

## 검증 결과
- ✅ `scripts/project_status.py` — PAPER-DESK-UX-001 이 RIGHT-BRAIN 자식 draft로 표시(1/5, 20%), 미연결 drift 아님, frontmatter 파싱 에러 0.
- ✅ 리네임: `git mv` 히스토리 보존, 디스크 정본 3개(darkmode/lightmode/uiux-sample-draft.pen)만 잔존.
- ✅ 에디터 재저장 스트레이 `design-spec.pen`(darkmode와 바이트 동일, hash ba353bc) 삭제 확인.
- ✅ SPEC 옛 파일명 잔재 0 (grep).

## 의도적으로 안 한 것
- SPEC INTERVIEW-SLOT 세부(엔드포인트 응답 필드·화면 카드 구성)는 구현 세션에 design-spec 쌍 노드 read로 확정 — 골격만.
- 신규 수집 INFRA SPEC 미작성(별 SPEC 분리 결정).

## 맥락 재진입 힌트
- **Pencil 에디터 옛 탭 주의**: 리네임 직후 에디터가 옛 이름(`design-spec.pen`)으로 재저장하는 사고 있었음 — 디자인 작업 전 옛 이름 탭이 안 열렸는지 확인. 정본 = darkmode/lightmode-spec.pen.
- 다음 구현 = PAPER-DESK-UX-001 draft→implementing. Next.js: next-themes·recharts 설치 → globals.css FractalSignal 팔레트 이식 → `/api/market/snapshot` 신규 → 시황·가상매매·계좌상세 3화면.

## 다음에 이어서 할 작업 (우선순위)
1. **PAPER-DESK-UX-001 구현 착수** — SPEC draft→implementing. next-themes+recharts 설치 → 테마 토큰 이식 → `/api/market/snapshot` read 엔드포인트 → 시황·가상매매·계좌상세 3화면(PC+모바일). design 정본 쌍 노드 read로 화면별 확정.
2. **신규 수집 INFRA SPEC 신설** — WTI·브렌트·야간선물 수집 + 알림 영속 테이블 (자산군 3종·알림 탭 전제).
3. **오른쪽 뇌 verified 게이트 모니터링 (organic)** — WEALTH 스냅샷 ≥5영업일(~06-16)/체결 ≥1/청산 ≥3.

## 커밋 상태
- 2커밋 분리: ① `feat(webapp)`: SPEC 신설 + roadmap 연결 + .pen 리네임 + 아티팩트 정리 ② `docs: wrap-up`. → main push.
