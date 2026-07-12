---
date: 2026-07-12
topic: 제미나이 비용 진단·감축 3커밋 + "길을 잃음" → 북극성 재초점(깔끔한 일일 루프+매매+검증)
status: completed
plan_file:
---

# 2026-07-12 · LLM 비용 진단·감축 + 북극성 재초점

## 배경
제미나이 과금일(12일)에 벌써 ₩16,000 → 사용자가 지출 확인 요청. 지난주 만든 LLM 비용
원장(LLM-COST-LEDGER-001)으로 실측하다 **요금표 버그·thinking 토큰·트랙 2배 구조**를 연쇄
발견 → 감축 3커밋. 이후 사용자가 "먼가 길을 잃었다"(거시 반쪽·승급 반쪽·두 트랙 토큰 낭비)며
멈춤 → 참조 사이트를 계기로 **방향을 하나로 재수렴**. 핵심 판단 = *폭을 멈추고 루프 하나를 닫는다.*

## 한 일
### 비용 진단·감축 (코드 3커밋, 전부 origin/main push)
- `core/llm/client.py` — 제미나이 요금표 정정: `gemini-2.5-flash` `0.075/0.30`(구 1.5/2.0-lite 요금)
  → GA 정식 `0.30/2.50` + `flash-lite 0.10/0.40` 추가 + 미지모델 fallback 상향. (`96736f0`)
- `data/db/stock-advisor.sqlite` — 원장 955행 **백필**(저장토큰+옛cost 역산으로 thinking 토큰 복원).
  백업 테이블 `llm_cost_ledger_bak_20260712` 보존. 8일 실비 $1.59→**$9.08(~₩12,500)**.
- `server/schedulers/jobs/auto_signal.py` — `INTRADAY_CADENCES` 에서 12:35(intraday2) 제거(4→3회). (`1ca4645`)
- `config/screening.yaml` — `band_score_width` 1.0→2.0 (재호출 둔감·중복 컷·flapping 완화).
- `tests/test_auto_signal.py` — 케이던스 3→2 단언 갱신 + band_fingerprint 게이트 테스트가 config 폭 읽도록 정렬.
- `core/watchlist_view.py` + `server/api/watchlist.py` — 바스킷 일자당 표시 상한 `per_date_limit`(기본 10) + `total` 보존. (`055fe15`)

### 북극성 재초점 (문서, `80faffa`)
- `idea_memo/2026-07-13-north-star-refocus-clean-loop-vision.md` — "길을 잃음"→참조 사이트
  (stock-analyzer-peach-chi)→"완벽히 원하는 것" 정의 + **충격표(그 사이트 기능=이미 다 구현, 더 깊게)**
  + 재초점 목표 + **착수 3택** + 이번 세션 완료·비용구조·보류 백로그 전부. 다음 세션이 이 파일부터 읽음.

## 검증 결과
- ✅ 요금표: 41 LLM 테스트 통과. 정정 후 8일 실비 재계산 $9.08 확인.
- ✅ 케이던스+밴드: `tests/test_auto_signal.py` 78 통과.
- ✅ watchlist 슬라이스: 22 통과 + 실 DB 확인(07-10 거래대금 21종→10 표시, ≤10 인 날 전부).
- ✅ 백필: 955행, 총합 $1.59→$9.08, 백업 테이블 생성 확인.
- 원장 실측(백필 후): 전략가 track_a/b = 비용 **95%**($8.58). thinking 토큰 = 비용 43%.
  news_classify 482콜은 ₩212(무시가능). "왜 많나" = **모든 종목 × 장기A+단기B 무조건 둘 다**(auto_signal.py:731).

## 의도적으로 안 한 것
- **thinking_budget cap**(전략가) — 사용자 보류. 전략가=핵심 판단이라 0으로 죽이는 건 비추, cap 은 별도 결정.
- **트랙 라우팅**(종목당 1트랙=콜 ~절반) — 약세장 bear_override 손상 위험 → 즉흥 수정 금지, 보수적 SPEC 필요.
- **라이브 확장 전반**(진입단계 0 규명 등) — 재초점 결정으로 폭 확장을 멈춤. 재시작 후 관측 우선.

## 기술 부채/미완
- **서버 재시작 필요** — 케이던스 제거(코드 상수)는 재시작해야 반영(band_width 는 watchdog 즉시). 재시작 후 원장에 감소폭 잡힘.
- **진입(buy) funnel 단계 0** — 최근30일 관심(59)↔매수대기(53) 전이는 활발(72/122)하나 아무도 "진입"까지 안 감. 전략가 buy verdict 희소 원인 규명 필요.
- **구버전 rec 10건**(funnel_stage 필드 없음) 사소한 부채.

## 다음에 이어서 할 작업 (우선순위)
1. **북극성 재초점 착수 3택 결정** ⭐ — idea_memo 문서부터 읽고 사용자에게 물어 시작: ①출력 루프 먼저(오늘 Top-5 깔끔한 한 화면, 완성형 가시화·동기부여·Claude 추천) ②매매층 먼저(프리즘식 진입/일지) ③검증 먼저(Track B 일봉 백테스트). **코드는 선택 후.**
2. **서버 재시작 → 비용 감소 관측** — 케이던스·밴드 변경 효과를 며칠 `/ops/llm-cost` 로 실측(하루 ~₩2,481→~₩1,600 예상 검증).
3. **트랙 라우팅 SPEC**(보류 해제 시) — 종목당 1트랙 결정론 사전 게이팅으로 전략가 콜 ~절반. bear_override 보존 위해 보수적 임계 + 작은 SPEC.

## 커밋 상태
- 코드/문서 4커밋 전부 origin/main push 완료: `96736f0`(요금표) `1ca4645`(케이던스+밴드) `055fe15`(watchlist 슬라이스) `80faffa`(재초점 문서). main tip=`80faffa`.
- 메모리: `project_north_star_refocus.md` 신설 + MEMORY.md 최상단 ★ 포인터.
