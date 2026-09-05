---
date: 2026-09-05
topic: macOS 이전 준비 (Windows 종속 해소) + chart_ohlcv 증분 갱신 커밋
status: completed
---

# 2026-09-05 · macOS 이전 준비 + chart_ohlcv 증분 갱신

## 배경
사용자가 프로젝트를 Windows 데스크탑에서 **맥북으로 완전 이사**하기로 결정 (병행 운영 아님).
레포를 실측해 보니 옮길 실물은 150MB 미만이었고, **진짜 문제는 용량이 아니라 Windows 종속 3곳**이었다.
그중 하나는 맥에서 *모든 Bash 호출마다* 실패했을 안전 훅이라 조용히 무력화될 뻔했다.
작업 중 두 건의 잠복 결함이 함께 드러났다 — 이미 깨져 있던 knowledge-sync 경로, 메인 레포에서 틀린 값을 내던 justfile `VIRTUAL_ENV`.
아울러 3주간 미커밋으로 남아 있던 chart_ohlcv 증분 갱신 작업(2026-08-15)을 정리해 함께 커밋했다.

## 한 일

### 이전 준비 — Windows 종속 해소
- `.claude/hooks/pytest_safety.py` — 신규. `.ps1` 을 파이썬으로 포팅(의존성 0, `python3` 로 실행). 맥에는 powershell 이 없어 훅이 매 Bash 호출마다 실패했을 것이고, 이 훅은 "테스트가 실 BOT_TOKEN 으로 실제 카톡에 스팸 발송" 사고를 막는 장치라 비활성화는 선택지가 아니었다. 포팅하며 **bash heredoc 스트립 추가** — 원본은 PowerShell here-string 만 벗겨서, 맥에서 heredoc 커밋 메시지 안의 "pytest" 가 오탐날 상황이었다.
- `.claude/hooks/pytest_safety.ps1` — 삭제.
- `.claude/settings.json` — 훅 커맨드를 `python3 .claude/hooks/pytest_safety.py` 로 교체.
- `config/knowledge_sources.yaml` — Windows 절대경로 하드코딩 → `${KNOWLEDGE_SOURCE_ROOT}`. 머신 종속 루트만 env 로 빼고 학습부별 하위 폴더는 config 에 유지.
- `scripts/sync_knowledge.py` — `resolve_source_root()` 신규. `${VAR}`·`~` 확장 + **미설정 시 silent fallback 없이 즉시 실패**(잘못된 경로로 "PDF 0개" 오진 방지).
- `.env` / `.env.example` — `KNOWLEDGE_SOURCE_ROOT` 키 추가.
- `justfile` — `VIRTUAL_ENV` 계산에 `--path-format=absolute` 추가.
- `docs/MIGRATION-MACOS.md` — 신규. 맥에서 그대로 따라 할 절차 + 검증 체크리스트.

### chart_ohlcv 증분 갱신 (2026-08-15 작업, 이번에 커밋)
- `collectors/charts.py` — `refresh_all_tickers(full=)` 증분화, `_last_bar_dates`·`_incremental_period_days`·`prune_ohlcv_history` 신규. 불필요한 `get_current_price` 호출 제거.
- `collectors/screening.py` — `get_chart_refresh_config()` 신규 (기본값 fallback).
- `config/screening.yaml` — `chart_refresh` 정책 블록.
- `server/schedulers/jobs/charts.py` — `_should_run_full()` 요일 판단, 잡이 스스로 모드 선택.
- `server/schedulers/jobs/__init__.py` — cron `mon-fri` → `mon-fri,sun` (일요일 전체 재적재, 토요일은 새 봉 없어 제외).
- `tests/test_chart_refresh_incremental.py` — 신규 17 케이스.
- `docs/specs/INFRA-CHART-DATA-001-chart-data.md` — v2 → v3, 증분 노트 + generates/modifies 갱신.
- `.gitignore` — 스크래치 csv / Pencil 내보내기 PNG / webapp 런타임 백업 제외.

### 레포 정리
- 잔존 워크트리 5개 제거(제거 전 diff 백업), 병합 완료 `claude/*` 브랜치 15개 삭제.
- `git gc` — 루즈 오브젝트 4181개(1.34GiB) → 팩 4.03MiB. `.git` **1.4GB → 9.4MB**.

## 검증 결과
- ✅ 훅 단위 12 케이스 (차단 4 / 통과 6 / heredoc 오탐방지 1 / heredoc 밖 회귀 1) 전부 기대대로
- ✅ 훅 **라이브** 양방향 — `pytest --version` 차단됨, `TESTING=1 pytest --version` 통과
- ✅ `resolve_source_root` 양방향 — env 설정 시 실경로 해석(PDF 31개 인식), 미설정 시 명확한 실패
- ✅ `tests/test_chart_refresh_incremental.py` 17 passed
- ✅ 전체 **1649 passed** (회귀 0)
- ✅ `just validate` 0 errors (기존 warning 1건: `teams/registry.yaml` 부재 — 이번 작업과 무관)
- ✅ DB 무결성 `PRAGMA integrity_check` ok / team_outputs 1312 · briefing_parts 699 · llm_call_cache 2823

## 자가 발견 결함 2건 (이번 세션에서 드러남)
1. **knowledge-sync 가 이미 깨져 있었다** — `config/knowledge_sources.yaml` 의 하드코딩 경로(`OneDrive/Desktop/...`)가 실제로 존재하지 않았다. 실제 위치는 `Desktop/주식투자/0.주식프로그램학습용/자산전략부/박종훈_팬딩`. 정정 후 PDF 31개 인식 확인. 언제부터 깨졌는지는 미확인.
2. **justfile `VIRTUAL_ENV` 가 메인 레포에서 틀린 값** — `git rev-parse --git-common-dir` 이 상대경로 `.git` 을 내놓아 sed 가 미매치, `VIRTUAL_ENV=.git/.venv` 가 되고 있었다(워크트리 안에서만 정상). uv 가 무시하고 경고만 띄워 무해했지만 매 `just` 실행마다 노이즈였다.

## 다음에 이어서 할 작업 (우선순위)
1. **실제 이전 수행** — `docs/MIGRATION-MACOS.md` §2~§4 를 따라 맥북으로 이동. 옮길 것 = `.env`(2KB) + `stock-advisor.sqlite`(108MB) + `data/chroma/`(31MB) + notifications·queries(3MB). 검증은 §4 체크리스트, 특히 **§4-3 훅이 실제로 막는지**(조용히 죽으면 실 API 호출 사고로 이어진다)와 **§4-4 DB 행 수 기준값 대조**.
2. **F3 주도 종목 축 → M2 Track C** — 이전 전 세션(2026-08-12)의 원래 Top 1. 이전이 끝나면 여기로 복귀한다.
3. **증분 갱신 라이브 관측** — 첫 일요일 전체 재적재가 실제로 도는지, 평일 증분이 ≈4분에 끝나는지 로그로 확인(`chart_refresh_cron_done` 의 `mode`·`bars_requested`·`elapsed_s`). 코드는 테스트만 통과했고 **라이브 1주기를 아직 안 돌았다**.

## 커밋 상태
- `fcc9bb1` chore(migration): macOS 이전 준비 — Windows 종속 3곳 해소 + 이전 절차서 (push 완료)
- `5147191` perf(charts): chart_ohlcv 증분 갱신 — 18:00 갱신 73분 → 4분
- wrap-up 커밋은 아래 Step 6 에서

## 맥락 재진입 힌트
- 이전 절차·검증은 전부 `docs/MIGRATION-MACOS.md` 에 있다. 이 파일만 열면 된다.
- 제거한 워크트리 2개의 diff 는 **세션 스크래치패드**에 백업했다 — 세션용이라 맥으로 따라가지 않는다. `main` 대비 미반영 커밋 0, 내용도 `CLAUDE.md` 구버전 + 재생성 가능한 `knowledge/reference/` md 라 실질 손실 없음.
- 이번 세션은 roadmap 전진이 아닌 **인프라/이전 작업**이다. drift 아님 — 이전 완료 후 ADVISOR-CORE-001 F3 으로 복귀한다.
