---
date: 2026-07-05
topic: Track A "시장을 느끼는 능력" 총체 진단 + MARKET-CONTEXT-BRAIN roadmap (문서만·코드 0)
status: completed
plan_file: C:\Users\HOME\.claude\plans\x-ipo-zany-meteor.md
---

# 2026-07-05 · Track A 시장 맥락 총체 진단 + MARKET-CONTEXT-BRAIN roadmap

## 배경
사용자가 6월말~7월초 고변동 장세(메타 클라우드 진출 보도→AI capex 논란→반도체 급락, SpaceX IPO 수급 블랙홀, 국민연금 리밸런싱)에서 추천을 지켜보고 통찰 5건 제기 — "내 분석이 맞았나 편향 없이 검증 + 궁극의 어드바이저 방향 제시". evolve-review(진화팀)로 Explore 3 에이전트 병렬 전수 조사(전략가 LLM 입력·DB 히스토리 후성 22행·뉴스부→매매 체인). **핵심 판단: 출력이 아니라 하네스가 얇다 — 재료 미주입 + 게이트 결핍이지 신규 대형 인프라 문제가 아님.** 단계: BRAIN-QUALITY-001(두뇌 기둥)에 새 자식 roadmap 추가.

## 진단 결과 (요지)
- 사용자 통찰 **4 CONFIRMED + 1 부분 지지**: ① 뉴스 digest·시장관 = compose 슬롯 있으나 run_strategist 미전달(물리적 미주입) ② α=순수 차트 가속·자동 경로는 α/거시/원칙수호자 우회 ③ 후성(093370) buy 3회 최다, 블로우오프 익일 buy→−12%, track_b는 동시 과열 wait(좌우 손 불일치) ④ 메타발 기사 다수 미라벨링·건수 클러스터 희석·news_curator dead-end·regime 후행(급락 후 07-03에야 sideways) ⑤ 자동 buy 11건 중 10건 거래대금 유니버스 출신(채점 비어 인과 미검증=track record 0).
- **추가 발견**: entry_posture=defensive(06-22~)인데 06-29 buy 5건 발령(deployment_cap=사이징 전용) / sector_rs·wave_alive=None→bear_override dead path / "현금 확보" 출력 경로 부재 / 뉴스→매매 단절 절반은 N5 canon 의도 설계.

## 한 일
- `docs/specs/MARKET-CONTEXT-BRAIN-001-market-context-brain.md` — 신규 roadmap SPEC (BRAIN-QUALITY 자식). 진단 전문 + Tier 0(정합)→1(뉴스 격상+**해석**)→2(주도주 판별)→3(포트폴리오 자세 액션+수동주입 인프라 설계)→4(채점 루프) + 사용자 결정 3건 + 재사용 영향도(신규 테이블 0 목표).
- `docs/specs/AUTO-SIGNAL-INTEGRITY-001-auto-signal-integrity.md` — 신규 Tier 0 implementation SPEC (draft). T0-a defensive 발행 게이트 / T0-b sector_rs·wave 배선(M3b 상환) / T0-c 결정론 7계명 체크 / T0-d 미라벨링 뉴스 백필. 수용 기준 = 후성 06-16 재현(defensive+과열→신호 미발행).
- `docs/specs/BRAIN-QUALITY-001-investment-quality.md` — children 에 MARKET-CONTEXT-BRAIN-001 등록.
- `docs/evolution-log.md` — 신규 (evolve-review 하네스 개선 이력, 첫 항목 = 본 점검).
- `docs/RESUME.md` — 현재 위치·세션 판단·Top 3 갱신 + 판단 블록 프루닝(20→9).
- 메모리: `project_market_context_diagnosis.md` 신규 + MEMORY.md 인덱스.

## 검증 결과
- ✅ `PYTHONIOENCODING=utf-8 uv run python scripts/validate.py` → **0 errors** (1 warning = 기존 registry.yaml missing, 무관). `type: fix` 미허용 발견 → `feature` 정정.
- (코드 0 세션 — pytest 해당 없음. 구현 세션 검증 기준은 SPEC에 명세: 후성 06-16 재현 + 메타발 06-23~26 기사 리플레이.)

## 의도적으로 안 한 것
- Tier 0 핫픽스 코드 — 사용자 결정 "이번엔 진단+로드맵 문서만". 결함 4건은 **지금도 라이브**라 다음 세션 최우선.
- N5 canon 개정·manifest reads_analysts 추가 — Tier 1 구현과 함께(문서만 먼저 바꾸면 code↔canon 불일치).
- 수동 인사이트 주입 채널 — 사용자 보류, 인프라 방향만 roadmap에 명시.

## 다음에 이어서 할 작업 (우선순위)
1. **AUTO-SIGNAL-INTEGRITY-001 spec-interview → TDD 구현** — 라이브 결함 4건(방어태세 중 buy·원칙 우회·dead path·미라벨링)이 매 cadence 노출 중. 핵심 결정 = 게이트 위치(알림 단 vs 후보 단).
2. **원장 하루 실측** — `just server` 켜두면 `/ops/llm-cost` 자동 누적, Tier 0 작업과 병행.
3. **NEWS-EVENT-INTERPRETATION-001 spec-interview** — 격상 레인+LLM 해석(N2 시간축·매매 함의·재평가 조건)+lifecycle. 메타발 급락(06-23→07-02)이 리플레이 표본으로 살아있을 때.

## 커밋 상태
- wrap-up 에서 문서 일괄 커밋 + main push (본 세션 산출물 = 전부 docs/메모리).
