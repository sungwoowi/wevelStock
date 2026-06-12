---
date: 2026-06-12
topic: INFRA-MARKET-ASSETS-002 SPEC 신설(린 정정) + 재사용 가드(DATA-MAP·원칙11·spec-interview 게이트)
status: completed
plan_file: C:\Users\HOME\.claude\plans\jiggly-baking-beacon.md
---

# 2026-06-12 · INFRA-MARKET-ASSETS-002 SPEC + 재사용 가드 신설

## 배경
PAPER-DESK-UX-001 이 예약한 후속 SPEC(자산군 수집 + 알림 영속)을 `/spec-interview` 로 작성. **핵심 전환**: 작성 직후 사용자가 "기존 스키마 재사용 가능한데 무분별 신규 확장 아니냐"고 제동 → 코드 확인 결과 **신규 테이블이 과잉**임을 확인하고 린 정정. 그 미스의 재발 방지를 위해 **개발-타임 재사용 가드** 3종을 신설(런타임 에이전트 아님 — 빌더를 레일 위에 두는 하네스).

## 한 일
### SPEC 신설 (확장 전용으로 정정)
- `docs/specs/INFRA-MARKET-ASSETS-002-commodity-futures-and-alert-persistence.md` — **신규 SPEC**(status draft, parent=RIGHT-BRAIN-COMPLETION-001). 야간자산(브렌트 BZ=F·NQ=F·ES=F + WTI 기존·KOSPI200 야간) + 알림 영속. **generates: []** (신규 파일 0, 전부 기존 확장). `## 재사용 영향도` 섹션 = 가드 적용 레퍼런스 예시. 6 INTERVIEW-SLOT.
- `docs/specs/RIGHT-BRAIN-COMPLETION-001-*.md` — children 에 INFRA-MARKET-ASSETS-002 추가(RB-MS5 지원 인프라) → roadmap 1/6.

### 재사용 가드 (Layer 1+2, 코드 0)
- `docs/DATA-MAP.md` — **신규**. 30개 테이블 = 도메인/write/backend read/frontend·API 1행, 8군 분류 + 마이그레이션 패턴 부록. "안 보이면 새로 만든다" 차단하는 load-bearing 지도.
- `CLAUDE.md` — 절대원칙 **#11 신설**(신규 테이블/모듈/엔드포인트 전 DATA-MAP 확인 + 확장 불가 입증). 매 세션 자동 로드 = 항상 켜진 가드.
- `.claude/commands/spec-interview.md` — 3라운드에 🛡재사용 영향도 게이트 + SPEC 본문 `## 재사용 영향도` 섹션 필수화 + 중요규칙 추가. SPEC 위치 `teams/<team>/specs/` → `docs/specs/` 정정.

## 검증 결과
- ✅ `scripts/validate.py` — 0 errors (registry.yaml 1 warning = 무관 기존).
- ✅ `scripts/project_status.py` — INFRA-MARKET-ASSETS-002 RIGHT-BRAIN 자식 draft(1/6, 17%), 미연결 drift 아님.
- ✅ 코드 근거: `us_macro_snapshot` 이 gold·wti 이미 보유 / `us_markets.py` OVERNIGHT_SYMBOLS 가 wti 매일 fetch(컬럼 부재로 버려짐) / `notifications_log` + `/api/notifications/recent` 기존 / 멱등 컬럼 = `connection.py` `_apply_migrations` 가드(v9 전례, 신규 .sql 파일 아님).

## 의도적으로 안 한 것
- **자동 백스톱(Layer 3: validate.py WARNING)** — 보류. 가드를 과하게 짓는 게 바로 이 세션이 정정한 실수의 재발이라, 맵+원칙+게이트(프롬프트 레벨)로 충분. 맵이 자리잡은 뒤 백스톱.
- **reuse-critic 서브에이전트(Layer 4)** — 정적 맵으로 대부분 잡히므로 과잉.
- **코드 구현** — SPEC draft 골격만. KOSPI200 야간 source(KIS)는 구현 SLOT.
- **메모리 파일** — 가드가 CLAUDE.md #11 에 박혀 repo 정본이라 중복 저장 회피.

## 맥락 재진입 힌트
- INFRA-MARKET-ASSETS-002 구현 = us_macro/us_markets 확장 + market_macro KOSPI200 야간(KIS, graceful null) + notifications_log ALTER + market.py 자산군 섹션 + notifications mark-read. 신규 테이블·collector 0.
- 앞으로 **모든 SPEC 작성은 DATA-MAP 확인 + `## 재사용 영향도` 섹션 필수** (원칙 #11). INFRA-MARKET-ASSETS-002 가 본보기.

## 다음에 이어서 할 작업 (우선순위)
1. **PAPER-DESK-UX-001 구현 착수 (RB-MS5)** — Next.js production 화면. next-themes+recharts → FractalSignal 팔레트 → `/api/market/snapshot` → 시황·가상매매·계좌상세 3화면. 무게중심=프론트.
2. **INFRA-MARKET-ASSETS-002 구현** — 야간자산 컬럼 확장(us_macro/market_macro) + 알림 영속(notifications_log type·is_read) + mark-read. PAPER-DESK-UX 시황 자산군·알림 탭 백엔드.
3. **오른쪽 뇌 verified 게이트 모니터링 (organic)** — WEALTH 스냅샷 ≥5영업일(~06-16)/체결 ≥1/청산 ≥3, 매일 18:05 cron.

## 커밋 상태
- 2커밋 분리: ① `docs`: SPEC 신설 + 재사용 가드(DATA-MAP·#11·게이트) + roadmap 연결 ② `docs: wrap-up`. → main push.
