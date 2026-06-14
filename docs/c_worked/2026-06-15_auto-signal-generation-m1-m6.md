---
date: 2026-06-15
topic: 두뇌 구조 점검 → AUTO-SIGNAL-GENERATION-001 M1~M6 구현 + 라이브 검증
status: completed
plan_file: C:\Users\HOME\.claude\plans\calm-splashing-falcon.md
---

# 2026-06-15 · 자동 권고 생성 (두뇌↔몸통 빠진 연결) M1~M6 + 라이브

## 배경
/resume 중 사용자가 두뇌 구조 근본 질문(분석가 LLM이 도움 되나? 전략가 3줄이 전부?)을 던짐 → 코드·DB 실측으로 답함: **분석가=라벨 아닌 5필드·결정론 점수는 LLM 우회 보존 / 전략가 3줄=Flash 압축(full은 DB+R&D)**. 못 믿는 진짜 이유 = 얕아서가 아니라 **track record 0(권고 4건 전부 채팅 산물·wait·Track A 0건)**. 사용자 결정: ①자동 권고 생성 ②전략가 추론 감사 뷰 순. **작업 1 착수** → AUTO-SIGNAL SPEC 6 SLOT freeze → M1~M6 구현 + 라이브 검증.

## 한 일
- `docs/specs/AUTO-SIGNAL-GENERATION-001-*.md` — spec-interview 6 SLOT freeze(watchlist·cadence·funnel·밴드게이트·알림·채팅공존) + 재사용 영향도(신규 테이블 0). draft→implementing.
- `core/signal/watchlist.py` (M1) — `build_watchlist`(거래대금 상위50 ∪ 보유 ∪ 관심, 국장) + `screen_watchlist`(rank_candidates 결정론 컷) + `get_current_regime`. LLM 0.
- `core/signal/auto_signal.py` (M2·2.5·4·6) — `compute_scorecard`(build_* 컬렉터 직접=분석가 우회) + `build_prefetched_entries`(점수 metadata 주입) + `band_fingerprint`/게이트(M2.5) + `run_signal_for_ticker`(전략가 직접→persist source/cadence/track + 🟢알림 + 재시도) + `run_signal_cadence`(병렬 bounded + 🔵일일요약).
- `collectors/screening.py` + `config/screening.yaml` — signal_gate 로더(min_score·max_candidates·band_gate·concurrency 3·retries). 하드코딩 0.
- `server/schedulers/jobs/auto_signal.py` (M3) + `__init__.py` — 장중 3 cron(09:35/12:35/14:35) + 마스터 스위치.
- `server/schedulers/jobs/daily_refresh.py` — 18:05 postclose 권고 생성을 데스크 *앞에* 삽입.
- `tests/test_auto_signal.py` — 69 테스트(M1 23·M2 10·M2.5 15·M3 6·M4 5·M6 12 - 일부 중복카운트) + `tests/test_daily_refresh.py` signal 단계.
- `scripts/_auto_signal_probe.py` — M5 라이브 검증 프로브.

## 검증 결과
- ✅ 전체 **1224 passed** (회귀 0, 외부 호출 0 — collectors·전략가·notify 모킹).
- ✅ **M5 라이브 (실 Gemini)**: watchlist 50 → 컷 20 → 평가 40 → **persist 34건(src=auto·cadence=postclose, Track A·B)** · 전부 wait(방어장·regime=None) · 🔵 텔레그램 일일요약 실발송(delivered=1). 6건 미persist(no_yaml 5·503 1) → M6 재시도로 보완.

## 맥락 재진입 힌트
- **funnel**: watchlist → 결정론 컷 → 밴드게이트 → 전략가 직접(분석가 우회) → persist → 🟢/🔵 → [18:05 데스크 체결]. cron 09:35/12:35/14:35 + 18:05.
- **자율 실행 현실**: 18:05 postclose는 Windows 작업(`just refresh-daily`)으로 서버 없이 돎. 장중 3 cadence는 **서버가 장중 떠 있어야** 발화(APScheduler in lifespan). 현 서버는 구버전 코드 — 재시작해야 새 cron 로드.
- **병렬화**: asyncio 코루틴·동시성 기본 3(8GB 보수). RAM 영향 0, 제약=KIS rate-limit. 첫 라이브 후 차트 캐시 warm → 다음 회 DB-first 빨라짐.

## 다음에 이어서 할 작업 (우선순위)
1. **두뇌 알파 유연성 — regime 극보수 탈피 + 종목별 매매계획 (심층 인터뷰, BRAIN-QUALITY-001 착수)** — "전부 관망"은 regime을 극보수로 봄. 알파 목적엔 유연해야: **약세장이어도 강세섹터·주도주·파동 살아있으면 단기 눌림=타점 허용 / 강세장이면 이미 급등이라 추격 회피 / 대형주 조정국면 주의 / 섹터별 차등.** + 관망에도 **우선순위 랭킹 + 종목별 조건부 진입 트리거 가격**(체계적 매매계획). + watchlist **선정 기준에 파동·주도주·섹터 반영**(현재 거래대금+RS만) + 종목별 "왜 선정" **설명가능성**.
2. **자동 권고 잔여 폴리시 + 요약 풍부화** — 보유종목 always-eval(컷에서 안 빠지게, 매도관리) / regime=None 시 직전 영업일 fallback / 🔵 요약을 "상위 후보 N + 진입 대기가"로 / 차트 DB-first(technicals 풀히스토리 요건 캐시 충실화).
3. **전략가 추론 감사 뷰 (원래 작업 2)** — 3줄 뒤 full 추론(기간·거시·regime·cited)을 데스크/채팅에서 펼쳐 감사 + "지켜보는 권고" track·상태(진입/존속/청산) 필터·정렬.

## 커밋 상태
- 세션 중 코드는 미커밋 (이번 wrap-up 이 코드+문서 함께 커밋·push 예정).
