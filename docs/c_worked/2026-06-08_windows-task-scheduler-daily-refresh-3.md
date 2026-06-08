---
date: 2026-06-08
topic: Windows 작업 스케줄러 등록 — dev 일일 적재 cron 실가동 (운영 부채 3a 해소)
status: completed
plan_file: C:\Users\HOME\.claude\plans\calm-jingling-moth.md
---

# 2026-06-08 · Windows 작업 스케줄러 등록 — dev 일일 적재 실가동

## 배경
왼쪽 뇌 4/4 완성 + 직전 세션이 `run_daily_refresh()` 3-surface 단일 호출점을 완성했으나,
**OS 등록만 사용자 수동**으로 남아 미등록 상태였다. APScheduler 는 FastAPI lifespan 안에서만
살아 dev 머신 서버 미상주 시 18:05 허브가 미발동 → 순환매·universe ramp 의 다일 누적 전제가
깨진다. **핵심 판단**: schtasks 문자열 escaping 지옥을 피해 PowerShell `Register-ScheduledTask` +
`-WorkingDirectory` 로 `cd`/중첩따옴표 없이 `just.exe refresh-daily` 를 레포 cwd 에서 실행.
RESUME Top 3 #3 의 **3a 만** 수행(3b 뉴스 종목/섹터 scope 는 affected_refs↔ticker 정규화 설계
선행 필요 → 별도 세션으로 미룸). 코드/repo 변경 0, OS 작업 항목만 생성(가역).

## 한 일
- **Windows 작업 스케줄러 항목 생성** (레포 외부, OS 레벨) — `wevelStock-daily-refresh`:
  - Action: `just.exe refresh-daily`, `-WorkingDirectory C:\Users\HOME\claude\wevelStock`
  - Trigger: Weekly Mon–Fri 18:05 (bitmask 62)
  - Settings: `StartWhenAvailable` + 30분 ExecutionTimeLimit, 현재 사용자 "로그온 시에만"
- (코드/문서 파일 수정 없음 — 이 wrap-up 의 docs 갱신 제외)

## 검증 결과
- ✅ 등록 검증 — `Get-ScheduledTaskInfo`: State **Ready**, NextRunTime **2026-06-09 18:05**, Execute/Args/WorkingDir 정확.
- ✅ 테스트 런 — `Start-ScheduledTask` → Running→Ready 정상 복귀, **`LastTaskResult = 0`**.
- ✅ end-to-end 실증 — 작업이 돌리는 그 명령(`just refresh-daily`, repo cwd) foreground 직접 실행:
  `snapshot_ok=True / news_ok=True / failures=0`, 30.64s. us_macro **risk_off**(score −6.835) ·
  market_view `moderate_bull · 진입 방어 · 미장 위험회피` · **실 RSS 50 + 실 Gemini classify 50** · digest neutral.
- 참고: `created_at` 은 first-insert 만 찍혀(ON CONFLICT 미갱신) freshness 마커로 못 씀 → exit 0 + 명령 직접 실증으로 닫음.

## 의도적으로 안 한 것
- **3b 뉴스 종목/섹터 scope 적재** — `build_news_digest(ticker=)` 가 `ticker in affected_refs` 필터인데,
  RSS classify 의 affected_refs(LLM 자유 텍스트) ↔ universe 6자리 KRX 코드 형식 불일치 위험. 정규화 설계 선행 필요 + on-demand build 가 이미 답변 시점 커버 → 다일 누적 우선순위 낮아 미룸.
- **로그오프 상태 누적 설정** — "사용자 로그온 여부와 무관하게 실행"은 비밀번호 저장 요구 → dev 기본(로그온 시) 유지, 안내만.
- 코드 변경(justfile 로그 redirect 등) — 3a 무코드 범위 유지.

## 기술 부채/미완
- **로그온 시에만 실행** — PC 켜져 있어도 로그오프 시 미발동. 로그오프 누적 필요하면 별도 설정.
- 일일 cron 은 여전히 **market scope 뉴스만**(종목/섹터는 on-demand) — 3b 미해결.
- 기존 부채 그대로: gemini transient 503 retry / regime run간 흔들림 / KIS rate limiter 전역화.

## 다음에 이어서 할 작업 (우선순위)
1. **오른쪽 뇌 roadmap 착수 결정** — 북극성 미착수 절반(비중 Layer4→가상매매→코스피 대비 채점→복리). `RIGHT-BRAIN-*` roadmap SPEC 작성 + 첫 자식(Layer4 비중 vs 채점 루프 vs 가상매매) 우선순위 인터뷰. 사용자 사인오프 필요.
2. **gemini transient 503 retry 배선** — `provider="gemini"` 명시 호출 503 fallback 없이 죽음. `core/llm/client.py` 1~2회 재시도. production-chat·analyst·news_ingest classify 경로 노출.
3. **(선택) 뉴스 ticker/sector scope digest** — affected_refs↔ticker 정규화 설계 후 종목 루프 추가. 다일 누적 필요 시.

## 커밋 상태
- 코드 변경 0. 이 wrap-up docs(c_worked + RESUME + SESSIONS) → `docs:` 커밋 + main FF + push 예정.
- `.claude/scheduled_tasks.lock`(untracked)은 무관 산출물 → 커밋 제외.
