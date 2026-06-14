---
date: 2026-06-14
topic: Phase 2 실전화 4기둥 roadmap 박음 + 자동 권고 생성 공백 진단
status: completed
plan_file: (없음 — 완성도 점검 대화 → 구조화)
---

# 2026-06-14 (2) · Phase 2 4기둥 roadmap + 자동 권고 공백 진단

## 배경
채팅·뉴스·알림 5탭 완성 후 사용자가 "전체 흐름에서 얼마나 완성됐나?" 점검 → 두 축(지어진 정도 ~85% / 검증된 정도 ~65%) 평가 → 사용자가 **남은 일을 4기둥(두뇌·몸통·진화·설비)으로 분류**. 이어 사용자 핵심 질문 **"몸통은 도는데 왜 매수/매도/관망 리포트·알림이 하나도 없었나?"** 를 코드·DB로 팩트 진단. **핵심 발견: 자동 권고 생성 잡 부재 = 두뇌↔몸통 빠진 연결**(권고는 채팅 트리거만, 데스크는 소비만). 4기둥을 roadmap SPEC 트리에 박아 단계 지도에 표시 + 공백을 실행 가능한 SPEC으로 정리.

## 한 일
### 자동 권고 공백 — 팩트 진단 (코드·DB 실측)
- `persist_strategist_recommendations` 호출처 = `server/api/production_chat.py` **단 하나**(사용자 채팅 트리거 전용).
- 스케줄 잡 = 시황 브리핑만(`market_briefing_pre/now`). 데스크(`run_desk_today`, daily_refresh 18:05)는 권고 **소비만**.
- DB 실측: `track_a/b` 권고 **4건 전부 wait** · `account_fills` **0** · 알림 `market_briefing`만(trade_signal 0).
- → "매일 스스로 종목 스크리닝→분석가→전략가→권고 발행" 잡이 **통째로 없음**(미구현, 버그 아님).

### Phase 2 roadmap SPEC 5개 신설 (docs/specs/)
- `BRAIN-QUALITY-001`(roadmap) — 두뇌: 투자 퀄리티 실전급. 통찰=3 진화가 1의 엔진(수동 튜닝 한계).
- `BODY-AUTOMATION-001`(roadmap) — 몸통: 자율 운전. 자식=AUTO-SIGNAL-GENERATION-001.
- `AUTO-SIGNAL-GENERATION-001`(implementation, draft) — **빠진 연결 팩트 SPEC** + 6 INTERVIEW-SLOT(watchlist·시점·LLM 비용·멱등·관망 알림·기존 경로).
- `EVOLUTION-001`(roadmap) — 진화: 도메인 회고(RETROSPECT-ANALYST-001)↔시스템 자기감시(SYSTEM-SELF-MONITOR-001) **분리**(둘 다 미작성 placeholder).
- `OPS-CLOUD-001`(roadmap) — 설비: 로컬→클라우드, 타이밍·신뢰성 크럭스.
- `PROJECT-NORTH-STAR-001` — children 에 4기둥 추가(Phase 2) + 본문 Phase 2 표·의존·팩트.
- `docs/RESUME.md` — Top 3 를 Phase 2 프레임으로 갱신(①자동 권고 ②진화 ③데스크 폴리시).

## 검증 결과
- ✅ `project_status.py` — NORTH-STAR **1/2→1/6(17%, 정직)**, 4기둥 표시, AUTO-SIGNAL-GENERATION-001 draft □ (몸통 자식, drift orphan 아님).
- ✅ 커밋·푸시 완료(`bd3c80b`).

## 맥락 재진입 힌트
- **두 축 평가**: 지어진 정도(골격) ~85% / 검증된 정도(실전 증명) ~65%. "만드는 일"은 막바지, "증명·자율·진화·운영"이 남음.
- **권장 순서**: 2 몸통 자율화(자동 권고) → 3 진화 → 1 두뇌 퀄리티 동반 상승 → 4 설비. 근거=2가 데이터 뱉음→3이 먹음→1을 자동으로 올림→4는 검증 후.
- **3 진화 = 도메인↔시스템 분리** 필수(매매 결과 vs 에러 로그, 다른 입력·소비자). user_want_spec 도 별 Agent.
- **재료는 다 있다**: 거래대금 상위 50 매일 적재·분석가9·전략가·5점수 라이브. 빠진 건 "매일 엮어 돌리는 지휘자 잡" 하나.

## 다음에 이어서 할 작업 (우선순위)
1. **자동 권고 생성 (`AUTO-SIGNAL-GENERATION-001`)** — `/spec-interview` 로 6 SLOT 채움 → 매일 watchlist→권고→데스크. 북극성 "스스로 판단" 핵심. **사용자 우선순위 고민 후 결정.**
2. **진화 착수 (`EVOLUTION-001`/`RETROSPECT-ANALYST-001`)** — 차별화 핵심, 청산 누적 후. 두뇌 퀄리티의 엔진.
3. **데스크 폴리시 + 다크 대조** — 미산출 지표·다크 5화면·production-chat git mv·뉴스 digest 폴백(잔여).

## 커밋 상태
- Phase 2 SPEC + RESUME Top 3 = 이미 커밋(`bd3c80b`). 본 c_worked·SESSIONS·현재위치 = wrap-up 커밋.
