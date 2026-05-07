---
date: 2026-05-07
topic: 브리핑 이력 UI 재정비 + market_briefing_now 자동 cron + KRX 정규장 라벨 명시
status: completed
plan_file: (없음 — 사용자 의구심 흐름 따라 점진 진행)
---

# 2026-05-07 · 브리핑 이력 UI + 자동 cron + KRX 라벨

## 배경

전 세션 (M3 자산전략가 추론부) 직후 사용자가 webapp 메인을 직접 검증하다가 4가지 의구심을 던짐:

1. **AlertList "최근 알림" 가 4월 25일 데이터** — 봇 응답이 안 보임 → SPEC 정합 (notifications_log vs briefing_parts 분리). 카드 라벨 명확화 필요
2. **BriefingPartsCard 가 JSON pretty-print** — 사람이 읽기 어려움 + 단일 latest run 만 (시계열 X)
3. **market_briefing_now 자동 발송 안 옴** — manifest `schedule: []` (의도된 공백)
4. **SK하이닉스 등락률 KIS 와 키움 HTS 차이** (3.31% vs -0.30%) → KRX 정규장 종가 vs NXT 통합 가격 차이

핵심 판단: 추론부·알림·브리핑 이력 **3차원 분리** 명확화 + KIS=KRX only 한계 명시 (NXT 통합 도입은 KIS 미지원이라 보류).

## 한 일

### backend
- `pipelines/market_briefing_now/manifest.yaml` — schedule cron `30 9,12,14 * * 1-5` 평일 정규장 3회 추가 (시초가 정리 09:30 / 점심 12:30 / 마감 1시간 전 14:30). 임시 cron 18:37 발동 검증 + 원복 검증 통과
- `core/briefing/parts_store.py` — `get_recent_runs(pipeline_id, limit)` 신규 (DISTINCT run_id 최근 N개)
- `core/briefing/render.py` — `render_pipeline(pipeline_id, parts, status)` dispatcher 신규 (텔레그램·webapp 공용 진입점). 5군데 라벨 명시 — KRX 데이터 영역에 "KRX 정규장 전일 종가 대비" prefix
- `server/api/briefings_on_demand.py` — `GET /api/briefings/{pipeline_id}/recent?limit=N` endpoint 신규 (parts + rendered 텔레그램 텍스트 동시 반환)

### webapp
- `webapp/src/components/BriefingPartsCard.tsx` — 전면 재작성. 좌측 run 리스트 (날짜 그룹 + AUTO/BOT 뱃지) + 우측 텔레그램 텍스트 (`rendered` 그대로 표시) + JSON 디버그 토글 + 5초 polling. 시계열 누적 가시화
- `webapp/src/components/AlertList.tsx` — 제목 "최근 알림" → "최근 자동 푸시 알림" + 부제 추가 ("봇 명령 응답은 위 브리핑 이력")
- `webapp/src/components/BriefingCard.tsx` — **삭제** (legacy `/api/teams/daily_briefing/latest`, 5-Layer 도입 전 잔재)
- `webapp/src/app/page.tsx` — BriefingCard import 제거 + BriefingPartsCard 가 메인 자리

### 라벨 변경 상세
- "🇰🇷 국내 지수 (KRX 정규장 전일 종가 대비)"
- "📊 강세 섹터 (조건 ≥1% + KRX 정규장 전일 종가 대비 상승률 순)"
- "🚀 주도주 (괄호 % = KRX 정규장 전일 종가 대비 등락)"
- 미국 지수·거시경제는 yfinance 라 KRX 명시 X (그대로 "전일 종가 대비")

## 검증 결과
- ✅ pytest 60 passed (회귀 없음)
- ✅ market_briefing_now 임시 cron `37 18 * * 1-5` 발동 검증 — 18:37:31 KST `#sched-455d03` run_id INSERT 3 parts + 텔레그램 발송 + 사용자 확인
- ✅ 정식 cron `30 9,12,14 * * 1-5` 원복 후 server 재시작 — `pipeline::market_briefing_now::0` 재등록 확인
- ✅ `GET /api/briefings/market_briefing_pre/recent?limit=2` — 461 chars rendered 텔레그램 텍스트 (이모지 + 숫자 포맷) 반환
- ✅ Next.js build 성공 (legacy BriefingCard 제거 후)
- ✅ KIS prdy_ctrt 정합 검증 — inquire-price raw `stck_sdpr` (1,601,000) + 일봉 `stck_clpr` (1,601,000) → 직접 산술 +3.3104% = KIS prdy_ctrt 3.31% 정확 일치

## 의도적으로 안 한 것

- **NXT 통합 시세 도입** — KIS API 가 명시 미지원 (`_AL`/`_NX` suffix 빈 응답, GitHub repo NXT 키워드 0건). 도입 비용 큼 (KRX + 키움 OpenAPI 등 다중 source 결합 필요) → 별도 SPEC 백로그
- **KRX backend 직접 종가 검증** — KIS 일봉 vs KRX 공식 종가 100% 일치 추가 보강 (1분 작업) — 백로그
- **server/config 측 daily_briefing legacy 잔재** (`core/registry.py`, `core/config/schema.py`, `config/defaults.yaml`) — 의존성 그래프 큰 cleanup 세션 백로그
- **webapp `analyst-chat` 페이지의 SSR "분석가 메타 로드 실패" 깜빡임** — hydrate 후 fetch 가 채우는 정상 동작이지만 첫 렌더 시 빨간 텍스트 보임. 작은 UX 백로그
- **분석가 응답 원론·반복 패턴 개선** — 다음 세션 Top 1 그대로 유지 (이번 세션 X)

## 이번에 굳힌 판단

- **3차원 분리** (SPEC 정합):
  - 추론부 조회 = `core/inference/run_analyst.py` + analyst_chat endpoint (별도 호출 흐름)
  - 알림 (자동 푸시) = `notifications_log` (`notify()` INSERT, AlertList 가 표시)
  - 브리핑 이력 = `briefing_parts` (run_id 단위 시계열, BriefingPartsCard 가 표시)
- **봇 명령 응답은 알림 X = 브리핑 이력**: commands.py 가 `notify=False` 명시 호출. 자체 send_message + briefing_parts INSERT. notifications_log 안 들어감 (의도)
- **briefing_parts 시계열 누적** (일자 단위 upsert X): UNIQUE(pipeline_id, run_id, part_key). 같은 날 force 여러 번 = 다른 run_id = 새 row. 사용자 합의 = "현행 유지 + 5명 분화 직전 매월 폴더 + 90일 retention 도입"
- **KIS API 의 KRX 한계**: prdy_ctrt 는 KRX 정규장 종가 대비로 정확 (검증). 키움 HTS 차이는 NXT 통합 가격 표시 때문. **KIS 가 NXT 통합 endpoint 미지원** → 라벨에 "KRX 정규장" 명시로 혼동 회피
- **render dispatcher 1개 함수 → 모든 채널 wrap**: `render_pipeline(pipeline_id, parts, status)` 가 텔레그램 봇·webapp recent endpoint 동시 사용. 신 파이프라인 추가 시 `_PIPELINE_RENDERERS` 에 1줄만 추가

## 맥락 재진입 힌트

- 자동 cron 시각 (KST): `market_briefing_pre` 평일 07:00 / `market_briefing_now` 평일 09:30 + 12:30 + 14:30
- briefing_parts run_id 형식: `<ISO timestamp>#<sched-XXXXXX | manual-XXXXXX>`. `sched-` = 자동 / `manual-` = 봇 또는 API 호출
- BriefingPartsCard 의 [AUTO]/[BOT] 뱃지는 run_id 의 `#sched-` vs `#manual-` 패턴으로 분류
- KRX 정규장 종가 검증 명령 (필요 시): `uv run python -c "import asyncio; from connectors.kis import KISClient; ..."` (이번 세션 c_worked 의 일봉 호출 패턴)

## 세션 중 실 비용
- LLM 호출 0건 (이번 세션은 인프라·UI·라벨 작업, 분석가 호출 없음)
- KIS API 호출: 임시 cron 검증 1회 + 진단용 일봉/inquire-price 5~6 회 = ~10 콜 (rate limit 안)

## 다음에 이어서 할 작업 (우선순위)

이전 세션 Top 3 그대로 유지 (이번 세션이 본질 작업이 아닌 인프라 정비라 우선순위 변동 없음):

1. **분석가 응답 원론·반복 패턴 개선** (PC, 1.5~2.5h)
   - 단계 1 (5분): persona 톤 직설 강화 + response_rules cited 강제 제거 + temp 0.4 → 0.7
   - 단계 2 (1~1.5h): `collectors/` (KIS/KRX 환율·지수·VIX·수급) 스냅샷 → user/system 컨텍스트 자동 첨부

2. **나머지 4명 분석가 분화** (PC, 2~3h)
   - `agents/analysts/{principle_guardian, trade_coach, stock_analyst, news_curator}/{persona, manifest}` 4 set 패턴 복사
   - 매매코치 우선이면 자산전략가와 응답 톤 비교로 분화 의미 즉시 입증

3. **JSONL 매월 폴더 + 90일 retention 도입** (5명 분화 직전, 30분)
   - `data/analyst_queries/<id>/<YYYY-MM>/<dt>.jsonl` 폴더 분리 + retention cron

추가 백로그:
- NXT 통합 시세 도입 (KIS 고객센터 문의 또는 KRX/키움 source) — 별도 SPEC
- daily_briefing legacy 잔재 청소 (registry/schema/yaml) — 의존성 그래프 cleanup 세션
- analyst-chat SSR 깜빡임 (작은 UX)
- KRX backend 정규장 종가 일치 검증 (KIS 일봉 보강)

## 커밋 상태

이번 wrap-up 에서 2 커밋 + push 예정:
1. `feat(briefing): market_briefing_now 자동 cron + 브리핑 이력 UI 재정비 + KRX 라벨 명시`
2. `docs: wrap-up 2026-05-07 브리핑 이력 UI + 자동 cron + KRX 라벨`
