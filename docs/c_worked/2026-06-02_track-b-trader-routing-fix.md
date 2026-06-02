---
date: 2026-06-02
topic: Track B trader 라우팅 보강 (track_required) + 스테일 아티팩트 정리
status: completed
plan_file: C:\Users\HOME\.claude\plans\immutable-launching-walrus.md
---

# 2026-06-02 · Track B trader 라우팅 보강 (track_required)

## 배경
2026-06-01 production 점수 시연(MS1/MS2)에서 직접 발견한 결함 해소. swing(Track B) 신규 진입
발화가 시나리오 2로 분류되면 prefetch 분석가 목록에 **trader가 빠져 `cited_scores.t_score`가
항상 null** → Track B 권고의 핵심 권위 지표인 타점 점수(T-Score) + 6 트리거가 통째로 누락.
**근본 원인**: `_resolve_analyst_ids_for_scenario`가 scenario_id로만 분석가를 정하고 track을
무시 — 시나리오 축약 매핑은 Track A 기준이라 trader를 뺐는데 같은 시나리오가 track_b로
라우팅돼도 그대로 적용. track_b manifest는 trader를 reads_analysts에 두는 권위 불일치.
**핵심 판단**: 하드코딩 대신 config `track_required` 블록으로 track별 필수 발행자를 선언 →
해석 후 append(중복 skip). Track A는 manifest대로 trader 미포함 유지(축약 의미 보존).

## 한 일
- `config/scenario_analyst_routing.yaml` — `track_required.track_b=[trader]` 블록 신설(scenarios 위). plugin 트랙은 자기 항목 드롭만으로 확장
- `core/intent/router.py` — `_resolve_analyst_ids_for_scenario` 재구성: 시나리오/fallback 해석 후 track_required 보강(순서 보존 + 중복 skip). `route_intent`·`route_intent_stream` 공유 헬퍼라 단일 수정으로 양쪽 복구
- `tests/intent/test_router.py` — `TestTrackRequiredAugmentation` +5(track_b 보강/중복 방지/both 포함/track_a 미추가/route_intent prefetch에 trader)
- `.gitignore` — `*.zip` + `/_*.json` 재발 방지 패턴 추가
- 삭제 — 3주 전 R&D 전송용 스테일 zip 8개 + SLOT S2 스크래치 `_flow_distribution.json`

## 검증 결과
- ✅ pytest **808 → 813** (+5, 회귀 0, TESTING=1). validate.py **0 errors**(1 warning은 기존 legacy teams/registry.yaml, 무관)
- ✅ **실 분류기→라우터 통합 검증**(LLM·KIS 호출 0): `swing: 삼성전자`→scenario 2/track_b/conf 0.95→**trader 포함** / `long:`→track_a→**trader 미포함**(의도대로) / `both:`→trader 포함
- ✅ git status 클린 — untracked 9개 제거, 의도한 4파일만 변경

## 의도적으로 안 한 것
- **라이브 production-chat 재시연(실 Gemini로 t_score 숫자 확인) 보류** — 서버 기동 + 토큰 필요, 사용자 외부. 라우팅 결함 자체는 결정론 통합 검증으로 충분 입증. 하류 t_score 인용(render_prefetched 구조 주입)은 2026-06-01 이미 실증
- Track A에 trader 미추가 — manifest reads_analysts 권위 정합(단기 타점 신호는 Track A frame 밖, 축약 목적 보존)

## 기술 부채/미완
- 직전 세션 부채 유지: 임계 production 캘리브레이션(RS·regime·buyscore) / 공백 2축(A 연간 EPS·N 뉴스부) / regime run간 흔들림(strong/moderate 경계)

## 맥락 재진입 힌트
- `swing:` 단축어 = scenario_id=2 + agent_route=track_b (config/scenario_keywords.yaml shortcuts). 이게 결함 케이스였음
- track별 필수 분석가 = `config/scenario_analyst_routing.yaml`의 `track_required` 블록. route가 해당 track 포함 시 append
- trader = T-Score + 6 트리거 = Track B 전용 권위(track_b manifest). Track A는 S/α/F-Score frame

## 다음에 이어서 할 작업 (우선순위)
1. **임계 production 캘리브레이션** — RS R1/R2/R3 + regime_thresholds + buyscore breakpoints 전부 초기값. `screening_distribution.py` 신규(flow_distribution 미러) + leading 종목 분포 → config 1차 정합(다일 누적) + regime 경계 히스테리시스
2. **공백 2축 데이터 확장** — buy_score A(연간 EPS 3년)·N 뉴스부(0시드) 중립 fallback 실측화. fundamentals 연간 소스 / NEWS-SOURCE-001 SPEC 신설
3. **(선택) 라이브 production-chat 재시연** — 서버 기동 후 `swing: 삼성전자` 실 Gemini로 t_score null→실값 최종 확인

## 커밋 상태
- 코드(router/yaml/test/.gitignore) + wrap-up docs를 1 커밋으로 묶어 main 직접 커밋·push(사용자 요청, 솔로).
