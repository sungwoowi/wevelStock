---
date: 2026-06-15
topic: 텔레그램 알림 실패 진단(노트북 절전·DNS) + 놓친 오전 잡 재실행 + cron 미스파이어 내성
status: completed
plan_file:
---

# 2026-06-15 (2) · 텔레그램 절전 사고 대응 + APScheduler 미스파이어 내성

## 배경
/resume 중 사용자가 "어제까지 잘 돌던 텔레그램이 오늘 오전에 실패" + `[Errno 11001] getaddrinfo failed`
스택트레이스를 던짐 → /resume 중단하고 디버깅. **핵심 판단: 코드 버그 아님 = 노트북 덮개 닫음에
의한 절전(sleep)으로 망/DNS가 끊긴 환경 문제.** 어제 코드 푸시 0건(회귀 배제) + 로그 마지막
`run_auto_signal_job ... was missed by 0:33:18`(스케줄러 33분 멈춤=절전 신호)으로 확정.

## 한 일
### 진단 (읽기 전용)
- `nslookup`/`ping` 실측 — DNS 서버(KT 168.126.63.1) 간헐 타임아웃이나 ping 0% 손실 = 망 경로 정상, 이름해석만 흔들림.
- 라이브 `getMe` 실호출 → `miracle_w_bot` OK = 봇 도달 정상 복구 확인. 서버(PID 74660) 상주·폴링 자동 복구(`network_retry_loop` 무한 재시도) 확인.
- `core/notification/service.py` 코드 확인 — `_send_telegram` 이 예외 잡아 `False` 반환 → 파일+DB 폴백 항상 기록. **절전 창 알림 손실 0(파일/DB 보존, 단지 텔레그램 push 만 누락)**.

### 놓친 오전 잡 재실행 (사용자 선택 B = 시황 먼저 → auto-signal)
- `POST /api/briefings/market_briefing_now/run?force=true&cache=false` — 시황 강제 갱신, run `10:41`, 3파트 **텔레그램 발송 성공(tg=True)**.
- `run_auto_signal_job("intraday1")` 수동 재실행 — watchlist 49→컷 20→**persist 32건(전부 wait)**·buys 0·band-skip 8·**regime=strong_bull**(fresh 스냅샷 효과). 장중 cadence라 🔵요약/🟢신호 미발송 = 설계(관망뿐).

### 미스파이어 내성 패치 (재발 방지)
- `server/schedulers/jobs/auto_signal.py` — `MISFIRE_GRACE_SEC = 3600` 상수 + 근거 주석.
- `server/schedulers/jobs/__init__.py` — 장중 3 cadence(`auto_signal::intraday1/2/3`) + postclose(`infra::daily_refresh` 18:05)에 `misfire_grace_time=3600`·`coalesce=True`·`max_instances=1` 추가. (근본: 스케줄러가 `job_defaults` 없이 생성돼 **기본 grace=1초** → 절전 1초만 지나도 영구 스킵.)
- `tests/test_auto_signal.py` — 등록 검증 테스트 1건(4잡 전부 내성 설정 확인, 비기동 스케줄러 `get_job`).

## 검증 결과
- ✅ 라이브 `getMe` OK / 시황 3파트 tg=True / auto-signal intraday1 exit 0·persist 32.
- ✅ 전체 **1225 passed**(+1, 회귀 0). 경고 1건은 기존 yfinance deprecation 무관.
- ✅ 사용자가 서버 재시작 완료 → 미스파이어 내성 라이브 반영.

## 다음에 이어서 할 작업 (우선순위) — 변동 없음(이 세션은 인터럽트성 사고대응)
1. **두뇌 알파 유연성 — regime 극보수 탈피 + 종목별 매매계획 (BRAIN-QUALITY-001 착수, `/spec-interview`)** — "전부 관망"은 알파 저해. 약세장도 강세섹터·주도주·파동 살아있으면 단기 눌림=타점 / 강세장은 추격 회피 / 섹터 차등. + 관망에도 우선순위·조건부 진입가 + watchlist 선정에 파동/주도주/섹터 + "왜 선정" 설명가능성. **(오늘 intraday1 라이브가 strong_bull인데도 32건 전부 wait = 이 문제 재확인.)**
2. **자동 권고 잔여 폴리시 + 요약 풍부화** — 보유 always-eval / regime=None fallback / 🔵 요약 "상위 후보 N + 진입 대기가" / 차트 DB-first(technicals 캐시 충실화).
3. **전략가 추론 감사 뷰** — 3줄 뒤 full 추론(기간·거시·regime·cited) 펼침 + 권고 상태 필터·정렬.

## 맥락 재진입 힌트
- **외부 API 한계는 "조사 결론"이 아니라 "실호출"로 확정** — getaddrinfo는 코드 아닌 OS 이름해석. 라이브 getMe/ping으로 즉시 환경 vs 코드 분리됨.
- **수동 재실행 경로**: 시황 = `POST /api/briefings/market_briefing_now/run?force=true&cache=false`(라이브 서버). auto-signal = `uv run python -c "...run_auto_signal_job('intraday1')..."`(별도 프로세스, 공유 DB read). 장중 cadence는 관망뿐이면 무알림이 정상.
- **스케줄러 등록은 기동 시 1회** — cron kwargs 변경은 서버 재시작 필수(hot reload X).

## 커밋 상태
- 세션 중 코드 미커밋 → 이 wrap-up 이 코드(미스파이어 패치) + 문서를 분리 2커밋으로 + main FF + push 예정.
