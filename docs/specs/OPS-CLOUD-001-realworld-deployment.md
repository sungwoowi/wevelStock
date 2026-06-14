---
spec_id: OPS-CLOUD-001
title: 설비 — 실전 운영환경 적용 (로컬 PC → 클라우드 이전) (roadmap)
team: shared
type: roadmap
level: roadmap
status: draft
generates: []
children: []
depends_on:
  - BODY-AUTOMATION-001 (가상매매가 검증되기 전엔 옮길 이유 적음 — 4는 검증 후)
---

# OPS-CLOUD-001 — 설비: 실전 운영환경 적용 (Phase 2 기둥 4)

> 4기둥 중 **4. 설비**. `PROJECT-NORTH-STAR-001` 직속.
> 로컬 PC 서버 → 클라우드 환경 이전(DB·데이터 마이그레이션·서버). 현재 ~20%(크로스플랫폼 설계만).

## 현 상태
- 로컬 PC 단일 프로세스(FastAPI+APScheduler+텔레그램 봇), SQLite, Windows 작업 스케줄러(`wevelStock-daily-refresh`, **로그온 시에만** 실행).
- 크로스플랫폼 설계는 돼 있음(pathlib 전용·justfile·어댑터 추상화). 메모리 기록: 작은 VM 1대로 통째 이전 가능(무료 티어 1~3년).

## 크럭스 — 기술 난도보다 타이밍·신뢰성
이전 자체 난도는 낮다. 핵심 결정:
1. **타이밍** — 가상매매가 검증(BODY-AUTOMATION verified)되기 전엔 옮길 이유 적음. 단 현재 "로그온 시에만 cron 도는" 불안정성이 거슬리면 24/7 클라우드가 그걸 해결(2 몸통의 신뢰성과 직결).
2. **DB** — SQLite 유지(파일 통째 이전) vs Postgres 마이그레이션(동시성·관리형). 현 규모는 SQLite로 충분.
3. **비밀키·KIS 실계좌 안전** — `.env` 시크릿 관리, OAuth 토큰 메모리 전용 유지, `KIS_IS_PAPER` 가드.
4. **24/7 가동** — VM/컨테이너 상주 + 프로세스 매니저(재기동) + 로그 영속(현재 cron stdout 미리다이렉트 부채).

## 후보 작업
- 24/7 상주 환경(VM/컨테이너) + 프로세스 매니저 + 헬스체크
- 데이터 마이그레이션 절차(SQLite 백업·복원, 필요 시 Postgres)
- 시크릿·환경 분리(dev/prod), 텔레그램 봇 dev/prod 분리([[project_telegram_bot_split]])
- 스케줄러 stdout 로그 래핑(현재 미리다이렉트 — 실패 진단 불가 부채)

## 완료 정의 (잠정)
사람 개입·로컬 PC 의존 0으로 24/7 클라우드에서 매일 도는 데스크가 안정 가동된다.
