---
date: 2026-06-06
topic: SPEC 2-tier 거버넌스 + 단계 지도 drift 감시 + ANSWER-FIDELITY-001(LB-MS1) 답변 누수 봉합
status: completed
plan_file: C:\Users\HOME\.claude\plans\swirling-coalescing-pumpkin.md
---

# 2026-06-06 · 왼쪽 뇌 roadmap 거버넌스 + 답변 누수 봉합(LB-MS1)

## 배경
직전 세션 잔여(discovery 커밋) push 후, 사용자가 본질 점검을 던짐 — "이 프로그램이 실전 도움 단계에 못 이르렀다, 본질적으로 어떤 형태여야 하나?". 대화로 **북극성 = 매일 도는 책임지는 페이퍼 트레이딩 데스크**(주도주·순환매·타이밍·비중·채점) 합의. 시스템을 **왼쪽 뇌(수집→분석→답변, ~65%)/오른쪽 뇌(비중→가상매매→채점→복리, 0%)**로 나누고 **왼쪽 뇌 먼저 완성** 결정. 핵심 판단 1줄: "부품은 있는데 종합 판단이 안 올라왔고 답변이 샌다 → 답변 누수부터." 추가로 사용자가 "세션마다 단계 위치·drift 감시 장치"를 요청.

## 한 일

### SPEC 2-tier 거버넌스 (큰 방향 ↔ 다음다음 디테일 분리)
- `core/contracts/spec_frontmatter.py` — `type=roadmap` + `level`/`parent`/`children` 필드 + `status=done`
- `docs/STRUCTURE.md` — § SPEC 2-tier 규약(roadmap=점검용/implementation=코딩용) + scripts 표에 project_status 등재
- `docs/specs/PROJECT-NORTH-STAR-001-master-roadmap.md` — 최상위 마스터 roadmap(북극성 4목표→왼/오른쪽 뇌), 트리 뿌리
- `docs/specs/LEFT-BRAIN-COMPLETION-001-left-brain-completion.md` — 왼쪽 뇌 완성 roadmap(채점표+LB-MS1/2/3 마일스톤+자식 4)

### 단계 지도 + drift 감시
- `scripts/project_status.py` — roadmap 트리 파생: 진행도(done/total)+ACTIVE(roadmap연결+implementing만, legacy stale 제외)+drift 후보(미연결 미완)
- `.claude/commands/resume.md` Step 1.5 — 세션 시작 시 지도 읽고 후보가 ACTIVE 단계 맞는지 drift 점검
- `.claude/commands/wrap-up.md` Step 2.5 — 세션 끝에 SPEC status 갱신+전진 마일스톤 기록+drift 경고
- `tests/test_project_status.py` — 3 (뿌리 nesting, ACTIVE 거버넌스 필터)

### ANSWER-FIDELITY-001 (LB-MS1) — 답변 누수 봉합 (F1·F2·F3 라이브 검증)
- `docs/specs/ANSWER-FIDELITY-001-answer-leak-fix.md` — 자식 implementation SPEC(검증 기록 근거)
- `core/intent/formatter.py` — **F1**: anti-echo system 규칙 + scrub *이전* raw 에 echo 탐지(`_looks_like_echo`) + 1회 강제 재시도 + 최후 `_strip_echo`. **F2**: `select_evidence_axes`+축-가변 `_formatter_system`+빈 축 생략. `format_answer`에 route/scenario_id/ticker 인자
- `config/evidence_axes.yaml` — 질의유형별 근거축(종목=수급/차트/실적, 시장·거시=시장국면/시장폭/거시지표)
- `config/label_dictionary.yaml` — scrub 사전 확장(leader/buy_candidate/moderate_bull/supply_chain/alignment/CAN SLIM 등)
- `core/intent/classifier.py` — **F3**: `_extract_tickers_from_text`(등장순·중복/겹침 제거)+`IntentClassification.secondary_ticker`+비교 scenario(4) 주입
- `core/intent/router.py` — **F3**: analyst_direct(sync+stream)가 secondary_ticker 시 종목 점수 분석가(`_TICKER_SCORED_ANALYSTS`)를 2번째 종목으로도 호출
- `server/api/production_chat.py` — format_answer 에 분류 메타 전달(POST+stream)
- `scripts/_guide_probe.py` — 동일 메타 전달(라이브 검증 정합)
- `tests/intent/test_answer_fidelity.py` — 18 (F1 echo guard/retry/strip, F2 축 가변, F3 추출/라우터 양종목)

## 검증 결과
- ✅ 전체 **868 passed**, validate **0 errors** (847→868, +21)
- ✅ 라이브(gemini) before/after: #4 비교 raw헤더·코드라벨·잘림 0 + **삼성·하이닉스 양쪽 나란히 비교** / #8 환율 [거시지표] 단일 / #5 시장 시장국면/시장폭/거시지표 ("정보 부족" 빈줄 0)
- ✅ 단계 지도 자동 갱신: LEFT-BRAIN 완료 1/4(25%), ANSWER-FIDELITY verified, ACTIVE 없음

## 다음에 이어서 할 작업 (우선순위)
1. **LB-MS2 시장관 종합 (`MARKET-VIEW-SYNTHESIS-001` SPEC 작성)** — 섹터 RS·regime·매크로를 *상시 시장관 한 줄*(순환매+"지금 들어갈 때냐")로 종합. 자식 implementation SPEC. 입력 INFRA-US-MACRO-SNAPSHOT-001 흡수
2. **LB-MS3 뉴스부 (`NEWS-SOURCE-001` SPEC, `/spec-interview`)** — 가장 무거움. 6/5형 "버블/조정" 내러티브 + buy_score N 7/7
3. **magnitude 다일 튜닝** — universe 다일 누적 전제(여전히 dev cron 미작동, 매일 장후 수동 refresh 필요). 시급해 보이나 함정·보류

## 커밋 상태
- 코드 5커밋 전부 push: discovery `1a3fcef` / 2-tier+roadmap `9389b00` / ANSWER-FIDELITY SPEC `8bf0303` / F1+F2 `56bcc00` / 단계지도 `d9c6bfb` / F3 `2000175`
- 이 wrap-up docs = 별도 커밋 예정
