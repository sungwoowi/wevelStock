# Agent Architecture — 통신 패턴의 본질

## 한 줄 정의

**wevelStock 의 multi-agent 통신은 hierarchical orchestration (분석가 단독 → 통합 agent 종합) + DB-mediated 약한 협업** 패턴을 따른다. 분석가 간 직접 LLM 호출은 금지, DB `team_outputs` 통한 read-only 공유만 허용.

이 문서는 *왜* 그 패턴이 옳은지의 근거·trade-off·도메인 본질을 영구 보존한다. CLAUDE.md 의 "절대 원칙 1번" 의 근거 문서.

## 두 패턴 비교

| 측면 | A. 분석가 간 직접 소통 (mesh / cross-call) | B. 통합 agent + 분석가 독립 (hierarchical) |
|---|---|---|
| 시점 일관성 | ❌ A→B 호출 시 B 가 다른 t 의 데이터로 답해 시점 drift | ✅ 모든 분석가 같은 snapshot 기반 |
| frame 응집 | ❌ A 가 B 결과 보고 자기 frame 흐릿해짐 (frame 오염) | ✅ 각 분석가 자기 frame 에 집중 |
| debugging | ❌ 호출 그래프 = 사이클 가능, "왜 이 결론?" 추적 지옥 | ✅ fan-out → fan-in 단방향, 추적 쉬움 |
| 비용 통제 | ❌ A→B→C→A 무한 호출 위험, sub-호출 폭증 | ✅ 호출 횟수 = 분석가 수, 예측 가능 |
| 부분 실패 | ❌ 한 agent 실패가 그래프 전체로 전파 | ✅ 한 분석가 실패 시 나머지 정상, 통합 agent 가 결락 명시 |
| 재현성 | ❌ race condition·호출 순서 의존 | ✅ 같은 입력 → 같은 출력 |
| 캐싱·idempotency | 어려움 | 쉬움 (각 출력 단위 캐시) |
| 추론 깊이 | ✅ 반복 정제 가능 | ❌ 한 번의 종합 |
| 창발적 협업 | ✅ agent 간 challenge·정제 | ❌ 사전 정의된 흐름만 |
| 테스트 | ❌ 통합 테스트 필요 | ✅ 각 agent 단독 테스트 가능 |

## 도메인 본질이 답을 결정한다

| 도메인 | 본질 | 적합 패턴 |
|---|---|---|
| **주식 매매 분석** | 시점 일관성 + frame 분리. 모든 판단은 *같은 t 의 시장 snapshot* 기반이어야 통합 가능 | **B (hierarchical)** |
| 수학 증명 / 코드 디버깅 | 추론 깊이가 본질. 반복 challenge·정제로 정확도 ↑ | A (multi-agent debate) |
| 분류·태깅·요약 | 단순 처리 | B |

주식 매매 분석에서 A 패턴 쓰면:
- 9:00 macro 분석가 결과 → 9:03 종목분석가가 받아 자기 분석 → 9:05 trader 호출 시 snapshot 시점이 흐려져 통합 시 어느 t 기준인지 불명
- 종목분석가가 macro 분석가 결과로 자기 frame 보정 → 종목 frame ≠ 순수 종목 분석 = **frame 오염**
- "왜 이 결론?" 추적 시 B,C,D 의 결과까지 거슬러 가야 함

→ B 패턴이 시간 일관성·frame 응집·debugging 모두 우월.

## "분석가 간 소통" 의 절충 — DB read 는 OK

A vs B 는 흑백이 아니다. 의미 있는 중간:

| 방식 | 평 |
|---|---|
| 분석가 A 가 분석가 B 를 직접 LLM 호출 | ❌ A 패턴 함정 다수 |
| **분석가 A 가 분석가 B 의 *이전 sync 결과*를 DB 에서 read** | ✅ 시점 명시 + frame 유지 + 약한 의존 |
| **분석가 A 가 같은 sync 의 분석가 B 결과를 read** (sync orchestrator 가 보장) | ✅ 같은 시점 보장 |
| 분석가들 단독 → 통합 agent 종합 | ✅ B 패턴 순수형 |

→ **"DB read 는 OK, 직접 호출은 X"** 가 실용적 답. 정확한 이름 = *"단방향 hierarchical + DB-mediated 약한 협업"*.

## 통합 agent 의 정체

B 패턴에선 *통합 agent* 가 핵심. 분석가는 *영역 판단*, 통합 agent 는 *의사결정·종합*.

이게 자연스러운 2-Layer 분리:

| Layer | 책임 | 통신 |
|---|---|---|
| **Layer 분석가** | 자기 frame 영역 판단, StandardOutput JSON 으로 DB 기록 | 분석가 간 직접 호출 X. *이전 sync 결과* DB read 는 OK |
| **Layer 통합** | 모든 분석가 출력 read 해 의사결정. horizon (단타/스윙/중장기) 별 또는 책임 (실행) 별 분화 가능 | DB read only. 분석가 호출 X (분석가는 단독 sync 단위로 실행) |
| **Layer 실행** | 의사결정 받아 계좌·비중·주문 집행 | DB read |

## 실제 구현 사례

| 시스템 | 패턴 | 비고 |
|---|---|---|
| **prism-insight** | B 순수형 | 6 분석가 → Investment Strategist 통합. 분석가 간 직접 호출 0 |
| **AutoGen** | A | multi-agent debate. 추론 깊이 도메인에 적합 |
| **LangGraph state graph** | 둘 다 가능 | 도메인이 결정 |
| **wevelStock** | **B + DB read 절충** | 5-Layer 모델: 분석가(Layer 2) → 전략가(Layer 3, 통합) → 계좌관리자(Layer 4, 실행) |

prism-insight 가 의도적으로 B 를 선택한 결정과 wevelStock 의 단방향 규칙이 같은 본질에서 도출 — 주식 분석 도메인의 시간 일관성·frame 응집 우선.

## wevelStock 적용

- **Layer 2 (분석가 9명)**: 원칙수호자 / 트레이더 / 시장상태분석가 / 종목선정가 / 종목분석가 / 자산전략가 / 매매저널리스트 / 수급분석가 / 뉴스큐레이터 — 각자 자기 frame 영역 판단, StandardOutput 을 `team_outputs` 테이블에 기록
- **Layer 3 (전략가 3명)**: 단타 / 스윙 / 중장기 — 분석가 출력 read 해 horizon 별 의사결정 종합
- **Layer 4 (계좌관리자 1명)**: 4 계좌 + 자산배분 + 실 주문 집행
- **분석가 간 통신**: 직접 호출 ❌. DB `team_outputs` row read 만.

## 한 줄 정리

**주식 매매 분석은 시점 일관성·frame 응집이 본질이라 hierarchical (통합 agent) 패턴이 본질적으로 맞다. 분석가 간 *직접 호출* 은 함정이지만, *DB 통한 read-only 공유* 는 안전하고 가치 있는 절충이다.**

CLAUDE.md 의 단방향 규칙은 따라야 할 도그마가 아니라 도메인 본질의 자연스러운 결과물이다.
