---
date: 2026-04-30
topic: market_briefing_now 시장수급 신뢰성 fix (5주체 시장전체) + KRX 선물수급 신규 + ETF 매핑 fix + KOSDAQ limit
status: completed
plan_file: C:\Users\HOME\.claude\plans\deep-dreaming-wall.md
---

# 2026-04-30 (2nd) · 시장수급 신뢰성 rework + KRX 선물수급 신규

## 배경

봇 `/briefing_now` 채팅 실증 중 사용자가 두 이상 신호 발견:
1. "시장 수급" KOSPI 외인 +1.48조 → "외인이 그만큼 사지 않았어" 직관 위배
2. 강세 섹터 1위 KODEX AI전력핵심 -1.31% → 실제 키움/네이버는 +3.62%

두 이상 모두 데이터 신뢰성 직결 → 진단 후 일괄 fix. 동시에 어제 백로그였던 KOSDAQ limit 확대도 묶음. 마지막에 사용자 요청으로 KOSPI200 선물 수급도 추가 (KIS 미제공 → KRX 정보데이터시스템 backend 활용). 핵심 판단: KIS `foreign-institution-total` 은 양수 편향 랭킹이라 시장 전체 합계 X — 시장 전체는 `inquire-investor-time-by-market` (FHPTJ04030000) 별도 endpoint.

## 한 일

### KIS 시장수급 — 양수편향 → 시장전체 5주체
- `connectors/kis/client.py` — `market_investor_total(market)` 신규 메서드. `/uapi/domestic-stock/v1/quotations/inquire-investor-time-by-market` (FHPTJ04030000), 단일 row 반환, 5주체 (개인/외인/기관/금투/연기금) 백만원 단위
- `collectors/kr_supply_demand.py` — 응답 구조 전체 교체. `top_30_raw` / `top_foreign_buys/sells` 제거, 5주체 필드 평면화
- `core/briefing/render.py` (supply_sectors 함수) — "(top30 합산)" → "(시장 전체 누적)", 5주체 세로 나래비 (개인→외인→기관→금융투자→연기금), 라벨 "금투" → "금융투자" 풀어쓰기, 안내 라인 위치 조정 (선물 블록 뒤로)

### ETF 티커 매핑 fix 3건
- `collectors/kr_sectors.py` — 거래량 비정상 (장중 1,000주 미만) ETF 3건 매핑 수정. 사용자 검증 후 확정:
  - `385590` → **`487240`** KODEX AI전력핵심
  - `400590` → **`0080G0`** KODEX 방산TOP10
  - `492060` → **`463250`** TIGER K방산&우주

### KOSDAQ 주도주 limit 확대
- `collectors/kr_leading_stocks.py` — `kosdaq_limit: int = 5` → `7` + note 문자열 동기화

### KRX 선물 수급 신규 (KIS 미제공)
- `connectors/krx/__init__.py` — 신규 패키지
- `connectors/krx/client.py` — 신규 `KRXClient` (httpx). `data.krx.co.kr/comm/bldAttendant/getJsonData.cmd` POST + Referer/UA/X-Requested-With 헤더. `k200_futures_investor_today()` = `prodId=KR___FUK2I` + `bld=dbms/MDC/MAIN/MDCMAIN00103` (KRX 메인 위젯, 3주체, 단위 십억원)
- `collectors/kr_futures_supply_demand.py` — 신규 collector (3주체 개인/외인/기관)
- `pipelines/market_briefing_now/stages/collect_kr_market.py` — KRX 호출 추가. 실패 시 `warning` 로그 + 빈 dict 로 fallback (KIS 흐름 안 막음)
- `pipelines/market_briefing_now/stages/persist.py` — `futures_supply_demand` 를 `supply_sectors` part 에 같이 저장
- `core/briefing/render.py` — 선물 블록 신규: `[KOSPI200 선물]` 헤더 (현물 [KOSPI]/[KOSDAQ] 와 통일감), 십억원 → 백만원 환산 후 기존 `_fmt_won_million` 재사용

### 테스트
- `tests/test_market_briefing.py` — supply 픽스처 5주체로 교체, futures 픽스처 신규, assert 갱신 (개인→외인→기관→금융투자→연기금 순서 + `[KOSPI200 선물]` + 안내 위치 검증)

## 검증 결과

- ✅ pytest **60 passed** (전체)
- ✅ KIS `market_investor_total("kospi")` ad-hoc — 외인 -1,455,933백만 = -1.456조, 합계 ~0 (시장 전체 합 정합)
- ✅ KIS ETF audit (15개) — 3건 매핑 fix 후 거래량 정상 (487240 vol 1,219만 / 0080G0 vol 669만 / 463250 vol 98만)
- ✅ KRX `k200_futures_investor_today` ad-hoc — 외인 +445 십억 / 개인 -41 / 기관 -400 (현물 외인 -1.46조 매도와 정반대 = 헷지 패턴, 신뢰성 OK)
- ✅ 봇 `/briefing_now` 다수 라운드 실증 — 사용자 시각 검증 통과 (현물 5주체, 선물 3주체, 안내 위치, 헤더 통일)
- ✅ 서버 부팅 4회 (코드 수정마다 재시작) 모두 정상

## 의도적으로 안 한 것

- **선물 수급 5주체 확장** — KRX 메인 위젯이 3주체 (개인/외인/기관) 만 제공. 5주체 (금투/연기금 분리) 는 KRX 상세통계 (MDCSTAT 시리즈) 의 다른 bld 캡쳐 필요 → 백로그
- **개인 수급 (현물)** — 이번에 추가됨 (FHPTJ04030000 응답에 prsn 포함). 별도 API 의존 안내 제거
- **canon 4 파일 인터뷰** — 원래 플랜의 Part B 였으나 사용자 요청 흐름 상 다음 세션으로 이연
- **`market_investor_summary`/`foreign_institution_top` 의 dead code 청산** — 호출처 제거됐지만 코드 자체 유지. 회귀 리스크 ↓ 다음 청산 세션
- **legacy `bash.exe.stackdump`** — 환경 잡음, 무시
- **`.claude/settings.json` modified** — 이번 세션과 무관, 별도 변경. 커밋 분리

## 맥락 재진입 힌트

- **시장 전체 vs 종목 단위 KIS 투자자 API**: `inquire-investor` (종목) ≠ `inquire-investor-time-by-market` (시장 전체 누적, FHPTJ04030000) ≠ `foreign-institution-total` (외인 매수 상위 30 랭킹, 양수 편향). 시장 전체 합계 필요할 땐 무조건 `time-by-market`
- **KRX backend 호출 패턴**: `data.krx.co.kr/comm/bldAttendant/getJsonData.cmd` POST + form-data `bld=...` + 화면별 추가 파라미터. Referer/UA 헤더 필수. KOSPI200 선물 메인 위젯 = `bld=dbms/MDC/MAIN/MDCMAIN00103` + `prodId=KR___FUK2I`
- **ETF 매핑 검증법**: KIS `inquire-price` 의 거래량/거래대금이 장중인데 1,000주 미만이면 매핑 의심 신호. KIS `bstp_kor_isnm` 은 분류명만 (예: "ETF(파생결합/액티브분류)") 으로 종목 식별 불가 → 사용자/외부 확인
- **KIS 토큰 1분 1회 발급 제한**: ad-hoc 디버그 시 process 재실행마다 토큰 새로 받음 → 60s 쿨다운 의식

## 다음에 이어서 할 작업 (우선순위)

1. **canon 4 파일 인터뷰** — `knowledge/canon/{investment-principles,macro-framework,sector-insights,failure-lessons}.md` Q&A 로 채움. `market_briefing_pre` analyze 의 "이 사용자의 에이전트" 진화. 코드 변경 0. **1.5~2h, 사용자 인터뷰 시간 필요**
2. **선물 수급 5주체 확장** — KRX 정보데이터시스템 [파생상품 → 통계 → 투자자별 거래실적] 페이지에서 DevTools Network 로 `getJsonData.cmd` payload 캡쳐 → `connectors/krx/client.py` 에 신규 메서드 + `collectors/kr_futures_supply_demand.py` 응답 5주체 확장 + render. **1h, 사용자 캡쳐 도움 필요**
3. **Phase 3 — `market_briefing_close` + RAG** — 장 마감 후 (`/briefing_close`) 예상 vs 실제 채점 + RAG 해석. SPEC L134~ Phase 3 기존. **4~6h, 독립 세션**

## 커밋 상태

- 코드 + 테스트 (KIS/KRX/render/pipeline) → 1 커밋 예정
- wrap-up docs (이 파일 + RESUME + SESSIONS + MEMORY) → 별도 1 커밋 예정
- `.claude/settings.json` 변경은 이번 세션과 무관 → 미스테이지 보존 (사용자 확인 필요)
- main 브랜치 직접 작업 중 (worktree 분기 없음) → FF merge 불필요
