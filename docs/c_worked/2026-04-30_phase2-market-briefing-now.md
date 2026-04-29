---
date: 2026-04-30
topic: BRIEFING-TIMEBASED-002 Phase 2 + 파이프라인 ID 리네이밍 + KIS 정렬·rate-limit fix
status: completed
plan_file: C:\Users\HOME\.claude\plans\sequential-twirling-horizon.md
---

# 2026-04-30 · Phase 2 (`market_briefing_now`) + ID 리네이밍 + KIS fix

## 배경

Phase 1 (`/briefing_pre`) 완성 상태에서 시작. 다음 단계 = "장중 실시간 관찰" (`/briefing_now`)
신규 파이프라인. 사용자 결정으로 **LLM 없이 raw 데이터만 발송** (장중 9:30/12:00/14:00 등 빈번
호출 → LLM 비용·지연 회피, 객관 사실 표시로 충분). 데이터 소스 = **KIS API 단일** (실서버 키
보유, 실시간성 + 합법성 + 수급 포함). 봇 채팅 실증 후 사용자 피드백 다수 라운드 반영
(레이아웃·이모지·대형/중소형 분리·조건 변경). 마지막에 KIS volume_rank 가 거래대금 순서가
아니란 의문 → 제룡전기/LS머트리얼즈 등 누락 추적 → `FID_BLNG_CLS_CODE=0`(평균거래량) 사용 중인
**KIS 파라미터 매핑 버그** 발견·수정. 핵심 판단: 봇은 항상 force=True 호출, fallback 분기에
`not force` 검사 추가해 사용자가 새 KIS 호출 강제 가능.

## 한 일

### Phase 2 신규 (`market_briefing_now`)
- `collectors/kr_indices.py` — KOSPI/KOSDAQ/KOSPI200 지수 수집 (3 콜)
- `collectors/kr_sectors.py` — 15종 섹터 ETF + ≥1% 강세 추출
- `collectors/kr_leading_stocks.py` — 거래대금 상위 + cap_tier 별 조건 필터
- `collectors/kr_supply_demand.py` — 외인/기관/투신/연기금 수급 (top30 합산)
- `pipelines/market_briefing_now/{manifest,stages/{collect_kr_market,persist,notify}}` — LLM 없는 3 stage 파이프라인
- `tests/test_market_briefing.py` — persist + render + 단위 변환 9 케이스

### 디렉터리 rename / 삭제
- `pipelines/morning_pre/` → `pipelines/market_briefing_pre/` (git mv)
- `pipelines/market_briefing/` → `pipelines/market_briefing_now/` (mv)
- `pipelines/morning_briefing/` 삭제 (레거시 청산, cron 30 8 * * 1-5 동시 제거)

### 핵심 코드 수정
- `connectors/kis/client.py` — (1) `_CALL_INTERVAL` 1.0→1.1s + rate-limit 응답 1회 retry, (2) `volume_rank` 의 `FID_BLNG_CLS_CODE` 0(평균거래량)→3(거래금액) 정렬 fix, (3) `foreign_institution_top` 응답에 `pension_net_amount_m` 추가 + summary 합산
- `core/briefing/render.py` — `render_market_briefing` + helpers 신규. KOSPI200 표시, 수급 KOSPI/KOSDAQ 분리 헤더, 투신=투자신탁 안내, 연기금 추가, 강세 섹터 10개까지 채움(📊+⭐), 주도주 KOSPI 대형주(시총20위)/중소형 분리 표시, 선별 조건 안내, 단위 변환(억/조)
- `core/briefing/__init__.py` — `render_market_briefing` export
- `server/api/briefings_on_demand.py` — `market_briefing_now` 09:00 이전 fallback (DB latest 우선, miss 시 새 run + `note=market_closed`). force=true 면 fallback 우회. 09:00~09:19 → `market_briefing_early` note
- `server/telegram/commands.py` — `cmd_briefing_now` → `market_briefing_now force=True notify=False` + `_PIPELINE_RENDERERS` dispatch + `market_closed`/`market_briefing_early` prefix 케이스
- `server/telegram/bot.py` — `/briefing_now` 설명 갱신
- DB 마이그레이션 — briefing_parts/predictions/news_items 의 pipeline_id 새 값으로 UPDATE (legacy 행 0)

### 사용자 조건 변경
- KOSPI 시총20위 내: 등락률 ≥ 3% → **2%**
- 강세 섹터 표시: ≥1% 만 → 등락률 순으로 10개까지 채움
- 주도주: KOSPI 단일 표 → **대형주(시총20위) / 중소형(시총20위 외)** 별도 그룹

## 검증 결과

- ✅ pytest **64 passed** (기존 44 → 58 → 62 → 64 단계적 추가, 회귀 0)
- ✅ KIS 4 collector 통합 호출 ad-hoc — 9개 핵심 필드 모두 정상 (이전 `kospi_foreign_m=None` 누락 해결)
- ✅ KIS volume_rank fix 후 KOSDAQ 거래대금 1위 = 채비(+83.33%), 3위 고영(+5%), 4위 LS머트리얼즈(+16%), 6위 서진시스템(+10%) — 사용자 키움 데이터와 일치
- ✅ 봇 채팅 실증 (`/briefing_now`) 다수 라운드 → 3 분할 메시지 정상 도착, fallback prefix 정확
- ✅ 서버 부팅 OK (26 routes, scheduler 6 jobs, telegram_bot_started)

## 의도적으로 안 한 것

- **개인 수급 추가**: KIS 별도 시장 투자자별 매매동향 API 필요. 현재 외인/기관/투신/연기금 4종으로 충분
- **KOSPI200 선물 정확 가격**: 선물옵션 API 별도. 지수(2001) 로 대체 (선물 기초자산이라 의미 유사)
- **KOSDAQ 풀 limit 증가**: 5%+ 충족 종목이 5개 초과 시 짤림. 현재 limit=5 유지 (다음 백로그)
- **SPEC/RESUME 외 docs (BRIEFING-ON-DEMAND-001 SPEC, STRUCTURE.md, pipeline-restructure-plan.md, wrap-up.md) 의 morning_pre/market_briefing 텍스트 갱신**: 코드 동작 무관, 다음 wrap-up 또는 별도

## 다음에 이어서 할 작업 (우선순위)

1. **KOSDAQ 주도주 limit=5 → 7~10 증가** — 현 fix 후 5%+ 매칭 종목이 5개 초과 자주 발생 (오늘 7개+ 인데 5개만 표시). KOSPI 도 동일 검토. 단순 limit 변경 + 텔레그램 메시지 길이 확인. **30분**
2. **canon 4 파일 인터뷰** — `knowledge/canon/{investment-principles,macro-framework,sector-insights,failure-lessons}.md` Q&A 로 채움. Phase 1 의 LLM 분석이 일반론 → "이 사용자의 에이전트" 진화. 코드 변경 0. **1.5~2h**
3. **Phase 3 `market_briefing_close` + RAG** — 장 마감 후 채점 + 누적 학습. SPEC L134~ 기존. close_briefing 신규 파이프라인 + `core/knowledge/{ingest,retrieve}.py` 완성 + RAG 청크 주입. **4~6h, 독립 세션**

## 맥락 재진입 힌트

- 봇 핸들러는 `cmd_briefing_now` 가 항상 `force=True` 호출. 09:00 이전이면 fallback 우회 + 새 KIS run. force=False 호출 (다른 클라이언트) 시만 DB latest 재사용
- KIS `volume_rank` 정렬 기준 = `FID_BLNG_CLS_CODE` (0:평균거래량 / 3:거래금액). **다른 KIS 순위 API 도 비슷한 quirk 가능, 검증 필요**
- `pipelines/market_briefing_pre/` 의 함수명 `render_morning_pre` 는 의도적 유지 (내부 함수명, 사용자 명시 안 함)
- 메모리 백로그: `project_retention_spec_backlog.md` (briefing_parts 90일 retention SPEC)

## 커밋 상태

- 코드 + 테스트 + DB 마이그레이션 → 1 커밋 (Phase 2 + ID rename + KIS fix)
- wrap-up docs (이 파일 + RESUME + SESSIONS) → 별도 1 커밋
- 사용자 명시 요청으로 main push 진행
