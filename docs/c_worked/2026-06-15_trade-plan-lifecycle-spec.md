---
date: 2026-06-15
topic: 트레이드 플랜 생애주기 설계 SPEC (TRADE-PLAN-LIFECYCLE-001) + 결정론/판단 분업 원칙 확정
status: completed
plan_file: C:\Users\HOME\.claude\plans\dapper-hopping-volcano.md
---

# 2026-06-15 (6) · 트레이드 플랜 생애주기 설계 SPEC

## 배경
/resume → "관망 조건부 진입가" 착수 논의가 사용자 통찰로 더 큰 그림(목표·손절·분할매수·분할매도·대기
진입가를 시계열로 진화시키는 살아있는 플랜 + 목표 동적 수정 + 알림)으로 자람. 사용자가 "결정론으로
모든 상황을 다 맞출 수 있나?"를 반복 제기 → **핵심 원칙 확정**: 결정론은 *결정자*가 아니라 *후보 메뉴·
신호 계산기*, 판단(LLM·룰)이 선택·임계·수정. 코드 0, 설계 SPEC 으로만 박음(다음 세션부터 단계별).

## 한 일
- `docs/specs/TRADE-PLAN-LIFECYCLE-001-trade-plan-lifecycle.md` — 신규 설계 SPEC. 비전(종목×트랙 살아있는 플랜·상태 전이·다단 레벨) + 핵심 원칙(계산기/판단 분업) + prism 리포트 차용 + 5단계 로드맵(①손절+분할매수 레벨 ②대기 진입가 ③목표+분할매도 ④시계열 진화 ⑤알림) + 재사용 영향도(가드 #11) + INTERVIEW-SLOT 5. parent=BRAIN-QUALITY-001, status draft, generates [].
- `docs/specs/BRAIN-QUALITY-001-investment-quality.md` — children 에 TRADE-PLAN-LIFECYCLE-001 추가(0/2).
- `docs/specs/BRAIN-ALPHA-FLEXIBILITY-001-*.md` — conditional-entry-formula SLOT 을 본 SPEC 2단계로 이관 주석.

## 검증 결과
- ✅ `project_status.py`: BRAIN-QUALITY children = BRAIN-ALPHA-FLEXIBILITY(implementing)+TRADE-PLAN-LIFECYCLE(draft), 0/2. drift 없음.
- ✅ 코드 변경 0 → 테스트 무관(직전 1253 passed 유지).

## 의도적으로 안 한 것
- **구현 0** — 사용자 "설계만 SPEC 박고 단계별로". 5단계 로직은 INTERVIEW-SLOT 위치만.
- 플랜 영속 테이블 미확정(team_outputs 확장 vs 신규 = 4단계 SLOT, 가드 #11 확장 우선).

## 다음에 이어서 할 작업 (우선순위)
1. **1단계 — 손절 + 분할매수 레벨 (결정론 후보 메뉴)** — `extract_swing_candidates`(스윙 저점 다단)·`compute_indicators`(ma20/60/120)·`_atr` 로 후보 메뉴 계산 → buy 권고에 다단 실제 숫자 + 종가기준·−7% 절대 룰. 분할 사다리 sizing/paper_trading 재사용. TDD. (제일 쉬움·결정론)
2. **2단계 — 대기(관망) 진입가** — 눌림/돌파/추세 하단 방법 선택 + 가격(BRAIN-ALPHA-FLEXIBILITY 조건부진입 이관). compute_scorecard 에 price/ma 실어 conditional_entry 채움.
3. **M3b — sector_rs·wave LLM 입력** (BRAIN-ALPHA-FLEXIBILITY 잔여, 병행 가능) — 약세장 bear_override 활성.

## 맥락 재진입 힌트
- **핵심 원칙(이 SPEC 의 뼈대)**: 결정론=후보 메뉴·신호 계산기 / 판단=선택·임계·수정. 모든 레벨 동일. "결정론이 다 맞춰야 하나"=영원히 아니오. 손절도 단일 공식 아님(후보 多·객관적일 뿐), 목표는 후보 少·수정 잦음.
- **prism 트레이드 시나리오 리포트 = 산출물 목표 형태**(메모리 참조 박음): 다단 지지/저항·목표=마일스톤(regime 조건부 trailing/매도)·매도 AND 조합·종가기준 wick무시·−7% 절대·트리거 승률·보유 지속 조건.
- 1·2단계는 결정론 비중↑, 3·4단계 LLM 판단·수정↑. 한 번에 다 안 함.

## 커밋 상태
- 세션 중 미커밋 → 이 wrap-up 이 SPEC 3파일 + 문서 1커밋 + main(현 브랜치) + push 예정.
