---
date: 2026-06-07
topic: sector_rs/market_view 일일 적재 cron 배선 (LB-MS2 운영 ramp 마감)
status: completed
plan_file: C:\Users\HOME\.claude\plans\enumerated-squishing-fern.md
---

# 2026-06-07 · sector_rs 일일 적재 cron (LB-MS2 운영 ramp 마감)

## 배경
지난 세션(6/6) `MARKET-VIEW-SYNTHESIS-001`로 시장관 종합 코드는 완성됐으나 **순환매(rotation)가 매일 안 돌았다.** `build_market_view`는 답변 시점 첫 호출 때만 오늘 sector_rs를 자가적재 → 과거 스냅샷(`prev`)이 없어 `load_prev_sector_rs`가 비고, `rotation.direction="—"`/`strength="none"`으로 영구 정지. 즉 시장관의 절반이 죽어 있었다. **핵심 판단**: 별도 job 신설 없이 이미 평일 18:05 cron으로 등록된 `run_snapshot_macro_refresh`에 3단계로 합류 — `build_market_view`가 내부에서 `compute_market_macro`를 부르므로 macro refresh **뒤**에 와야 DB-hit로 싸게 읽힌다.

## 한 일
- `server/schedulers/jobs/snapshot_macro.py` — `run_snapshot_macro_refresh`에 3단계 추가: `build_market_view("KOSPI", force_refresh=True)`. 기존 1·2단계(supply·macro)와 동일 try/except 격리, 반환 dict `market_view` 키, docstring 3단계 흐름 갱신. KOSPI만(KOSDAQ은 SLOT).
- `tests/test_snapshot_macro_job.py` — 신규 3 (이 job 테스트 0이었음). 세 collector mock(함수 내부 import라 원 소스 모듈 패치): 3단계 호출·`force_refresh=True` 단언 / market_view 예외 격리 / macro 실패해도 market_view 실행.

## 검증 결과
- ✅ 신규 단위 3 passed (`tests/test_snapshot_macro_job.py`)
- ✅ 회귀 **904 passed** (901 + 3), `validate.py` 0 errors (warning은 기존 teams/registry.yaml)
- ✅ **순환매 활성화 격리 DB 실증**(외부호출 0, 동일 persist/load 함수 사용): prev 없음 → `rotation="—"` / 5일 전 스냅샷 누적 후 → `"바이오→금융"(strong)`, one_liner에 `순환 바이오→금융` 등장

## 의도적으로 안 한 것
- **실 KIS+Gemini 라이브 ramp 호출** — production 경로(외부 API 비용)라 보류. dev cron 미작동(서버 18:05 미상주) 환경에선 수동 ramp가 별 후속. cron 자체는 코드상 정상 등록.
- KOSDAQ market_view — `build_market_view`의 명시 SLOT, 본 작업 범위 밖.

## 다음에 이어서 할 작업 (우선순위)
1. **LB-MS3 뉴스부 NEWS-SOURCE-001 SPEC 착수** (가장 무거움) — 6/5형 "버블/조정" 내러티브 입력 + buy_score N 마지막 0시드 축 + LB-MS2 시장관에 먹일 재료. `/spec-interview`. 멀티세션. LEFT-BRAIN 다음 자식.
2. **INFRA-US-MACRO-SNAPSHOT-001 (미장 매크로) SPEC 착수** — entry_posture에 미장 야간(SPX/NDX/VIX/DXY/US10Y) 축 가산. MARKET-VIEW가 `us-macro-hook` SLOT 확보해 둠. `/spec-interview`. LEFT-BRAIN 자식.
3. **dev cron 미작동 근본 해소** (운영 부채) — 서버 18:05 미상주 시 cron 미발동 → sector_rs/chart/fundamentals 적재 전부 영향. 진짜 다일 누적의 전제. 서버 상주 or 수동 트리거 endpoint 검토.

## 맥락 재진입 힌트
- 순환매가 라이브로 돌려면 **≥2 평일** sector_rs_snapshot 누적 필요. 18:05 cron이 매일 적재. 누적 전엔 `rotation="—"`가 정상(버그 아님).
- 수동 ramp 1회: `uv run python -c "import asyncio; from collectors.market_view import build_market_view; v=asyncio.run(build_market_view('KOSPI', force_refresh=True)); print(v.one_liner)"` (실 KIS+Gemini).

## 커밋 상태
- `c32e358` feat: sector_rs/market_view 일일 적재 cron 배선 — feat 브랜치 → main FF → **push 완료**.
