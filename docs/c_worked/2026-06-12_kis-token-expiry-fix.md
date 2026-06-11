---
date: 2026-06-12
topic: KIS 토큰 만료 타임존 버그 수정 + 모의/실전 키 정합 + chart_refresh 배치 복구
status: completed
---

# 2026-06-12 · KIS 토큰 만료 버그 + 키 정합 + 배치 복구

## 배경
사용자가 chart_refresh 배치(평일 18:00 KST cron) 실행마다 `기간이 만료된 token 입니다` 경고가 158종목 전수에서 반복된다고 제보. 로그 분석 결과 **토큰 만료 시각 타임존 버그**가 근본 원인 — KIS 가 내려주는 `access_token_token_expired`(KST)를 코드가 UTC 로 오인(`.replace(tzinfo=timezone.utc)`)해, 로컬 캐시가 토큰을 **실제보다 9시간 늦게 만료**로 믿고 만료된 토큰을 계속 재사용. 18:00 배치가 도는 9시간 창에 정확히 걸려 전수 실패. 토큰 버그를 고치자 그 아래 가려져 있던 **모의/실전 키 불일치**(`EGW02004` "실전투자 도메인은 모의투자 앱키로 호출하실 수 없습니다")가 드러남. 핵심 판단: 한 증상 아래 두 결함이 겹쳐 있었고, 위층(토큰)을 고쳐야 아래층(키)이 보였다.

## 한 일
- `connectors/kis/client.py` — ① 만료시각 KST 파싱(`_KST=UTC+9`) + 10분 선제 재발급 마진(`_TOKEN_REFRESH_MARGIN`) / ② 만료 응답(`만료된 token`) 시 실패 토큰 문자열 키로 캐시 무효화 후 1회 강제 재발급·재시도(`_get`) / ③ 토큰 발급 "1분당 1회" 제한(`1분당`/`EGW00133`) 시 ~62초 대기 후 재시도(`_TOKEN_ISSUE_BACKOFF`, lock 내) — 다중 프로세스 충돌 시 배치 전수 실패 방지 / ④ 만료시각 부재 시 보수적 6h 가정
- `tests/test_kis_token.py` — 신규 4건: KST 파싱 / KST 만료시각이 UTC 기준 이미 지났으면 재발급 / `만료된 token` 응답 시 재발급·재시도 / 10분 마진 stale 판정. httpx mock, 실 API 0.

## 검증 결과
- ✅ `pytest tests/test_kis_token.py tests/test_charts.py tests/test_market_snapshot.py` — 43 passed (회귀 0)
- ✅ 라이브 진단: 실전 키 교체 후 `stock_price('005930')` = price 299,000 / market kospi / vol 31,420,307 (토큰 `expires=2026-06-12 21:55 KST` 정상 미래)
- ✅ chart_refresh 수동 재실행 = **refreshed=158, failed=0, 토큰 충돌 0** (전 종목 `source=kis`, 토큰 1회 발급 후 재사용)
- ✅ 텔레그램 강세 섹터 "?" → 서버 재시작(고친 .env 로드) 후 정상 표시 확인(사용자)

## 운영 조치 (사용자 수행)
- `.env` `KIS_APP_KEY/SECRET` 을 모의→**실전 키**로 교체. 1차 시도 AppSecret 오타(181자 `=v`)로 `유효하지 않은 AppSecret` → 재입력(180자 `==`)으로 해소.
- 서버 재시작 = 메모리의 옛 키 교체. 강세 섹터(ETF `etf_price` 호출)·온디맨드 KIS 호출 정상화.

## 다음에 이어서 할 작업 (우선순위)
1. **PAPER-DESK-UX-001 `/spec-interview`** — 디자인 쌍·네이밍 완성으로 전제 충족. SPEC 신설 후 Next.js 구현 (이번 KIS 작업과 무관, 원 Top 1 복귀).
2. **CTA 액센트 통일 결정** — 다크 에메랄드 vs 라이트 Rausch(로고색). 사용자 확인 후 일괄 치환 ~5분.
3. **오른쪽 뇌 verified 게이트 모니터링** — WEALTH 스냅샷 ≥5영업일(~06-16)/ACCOUNT-MANAGER 체결 ≥1/GUIDANCE 청산 ≥3. 매일 18:05 cron 누적.

## 맥락 재진입 힌트
- KIS 토큰은 **한 프로세스 안에서만** 만료 전까지 재사용(class-level 인메모리 캐시). `just refresh-charts` 등 수동 배치를 서버와 동시에 띄우면 별 프로세스라 각자 토큰 발급 → "1분당 1회" 충돌. 이제 발급 재시도가 자동 회복하나, 정석은 **서버 1개만** 운용.
- `connectors/kis/client.py` 의 `KIS_IS_PAPER` 와 .env 키 종류(모의/실전)는 반드시 **짝이 맞아야** 함 — 불일치 시 토큰은 발급되나 데이터 호출이 `EGW02004` 로 전수 실패.

## 커밋 상태
- 코드 픽스 + 테스트 = 본 wrap-up 에서 별도 커밋(`fix(kis): ...`), wrap-up docs = 후속 커밋. (어제 리미트로 미커밋 보존돼 있던 것 확정 커밋)
