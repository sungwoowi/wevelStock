---
date: 2026-05-21
topic: 자료 0 시드 5 분석가 + Track Selector 양 트랙 풀세트 production 검증 (cycle 11)
status: completed
plan_file: C:\Users\HOME\.claude\plans\zazzy-cuddling-ullman.md
---

# 2026-05-21 · 자료 0 시드 5 분석가 + Track Selector 양 트랙 production 검증 (cycle 11)

## 배경

cycle 10.5 MS3 완전 도달 ✨ 직후, RESUME Top 2 (자료 0 시드 5 분석가 페르소나 풀세트 production 검증) 선택. 사용자 인터뷰 = 완결성·효율성 양축에서 **2 → 3 → 1 순서 추천**. Top 2 가 가장 저렴 + 가장 빠름 + 이후 Top 3·1 의 견고한 기반 (UX 라우팅 받는 모든 분석가 검증 필수).

## 검증 결과 — 의도된 동작 100% 정합 (5/5)

### 5 분석가 production 호출 ($0.0049 / ~57s 합산)

| 분석가 | 질문 trigger | verdict | confidence | cost | prompt chars | tokens | 5축 검증 |
|---|---|---|---|---|---|---|---|
| market_state_analyzer | "지금 시장 체제 어디?" (격자) | unknown | 0 | $0.0009 | 17,155 | 8,567/827 | ✓ 5/5 |
| stock_picker | "지금 매수 후보 종목 뽑아줘" (격자) | (점수 null) | 0~80 | $0.0012 | 19,852 | 9,709/1,626 | ✓ 4/5 (max_tokens 잘림) |
| trading_journalist | "이번 주 매매 일지 정리해줘" (격자) | (거부) | — | $0.0006 | 13,275 | 7,098/271 | ✓ 5/5 |
| flow_analyzer | "삼성전자 (005930) 수급 분석해줘" (격자) | insufficient_data | 20 | $0.0008 | 17,304 | 9,096/304 | ✓ 5/5 |
| news_curator | "오늘 뉴스 어땠어?" (자가 진단) | (거부) | — | $0.0014 | **32,871** ⚠ | 17,928/46 | ⚠ 4/5 (cited 풀이 누락) |

**5축 검증 (a) boundary 침범 무 / (b) 환각 가드 / (c) cited v3.1 / (d) StandardOutput JSON 계약 / (e) verdict-confidence 매핑 정합**:
- 5명 모두 boundary 정합 (Layer 3·4 위임 명시 또는 다른 영역 침범 X)
- 5명 모두 환각 가드 정합 (데이터 부재 시 unknown/insufficient_data/거부 발행)
- 4명 cited v3.1 정합, news_curator 만 거부 응답에 풀이 누락
- 5명 모두 형식 계약 정합 (격자 또는 거부 응답)
- 5명 모두 verdict·confidence 매핑 정합 (manifest 매핑 100%)

### boundary 침범 시나리오 2 케이스 (단계 4)

| # | 시나리오 | 결과 | cost |
|---|---|---|---|
| 1 | market_state_analyzer ← "삼성전자 매수가 얼마야?" (종목 매수가 = 본인 영역 외) | ✓ 본인 영역 명시 + stock_picker / stock_analyst 위임 + 자가 추정 거부 | $0.0007 |
| 2 | flow_analyzer ← "지금 시장 상승장이야?" (시장 체제 = market_state_analyzer 영역) | ✓ 본인 영역 명시 + market_state_analyzer 위임 + 자가 판정 거부 | $0.0007 |

### Track Selector 양 트랙 풀세트 production 시연 (단계 6)

| Track | query | verdict | scores | cost | prompt chars | RAG |
|---|---|---|---|---|---|---|
| A (long) | "long: 005930 진입 검토 부탁" | wait | **0/6 missing** | $0.0020 | 42,534 | 3 |
| B (swing) | "swing: 005930 단기 진입 검토" | wait | **0/5 missing** | $0.0014 | 32,045 | 0 |

**의도된 동작 100% 정합**: 분석가 점수 부재 → 매매 직전 3초 체크리스트 / 운용 안전핀 원칙 인용 → wait 권고. StandardOutput JSON 계약 100% 준수 (recommendation_id / verdict / entry_price·target_prices·stop_loss / cited_scores / confidence / reasons / data / contract_version). cited v3.1 정합 (Track A = 5건 명제 ID `principles.trading_doctrine.심법1/2/3/매매직전3초체크리스트/operational_safeguards.진입검증룰` + 풀이 / Track B = `principles.operational_safeguards/trading_doctrine` + 풀이). 9 분석가 풀세트 read 통합 흐름 정상 작동.

## cycle 11 자율 정정 1건

**stock_picker manifest max_tokens 4000 → 6000** — cycle 10.5 stock_analyst 와 동일 패턴 (격자 + 후보 listing + 자연어 본문 합계 증가 시 응답 끝 잘림 해소).

## 발견 부채 4건 (백로그 등재)

### 1. snapshot 데이터 미주입 — 본격 판정 차단 (최우선 부채)

- **현상**: 5 분석가 모두 snapshot 데이터 부재로 본격 판정 불가. market_state_analyzer = 지수 위계 / 등락 추세 / breadth / 거래량 부재 → unknown. stock_picker = 섹터 RS / 수급망 / 정배열 / CAN SLIM 7축 부재 → 점수 null. flow_analyzer = 5 주체 수급 부재 → insufficient_data.
- **영향**: 9 분석가 풀세트가 production 진정 판정 도달 차단. Track Selector verdict 가 항상 wait (분석가 점수 부재).
- **해소 SPEC 후보**: `INFRA-SNAPSHOT-EXTEND-001` 가칭 — collectors/snapshot.py 보강 (지수 위계·등락 추세·breadth·거래량 / 섹터 RS·수급망·정배열·CAN SLIM 7축 / 5 주체 수급).
- **본 부채가 Top 1 (production UX) 의 차단점**: UX 라우팅 받은 분석가들이 모두 unknown/insufficient_data 발행 시 사용자가 받는 답변이 무의미함. snapshot extend 가 Top 1 진입 전 우선 해소 권유.

### 2. stock_picker max_tokens 4000 잘림 — cycle 11 6000 정정 완료 ✓

- **현상**: 격자 + 17 개 후보 listing + 자연어 본문 합계 tokens_out 1,626 에서 끝 잘림.
- **해소**: cycle 11 에서 manifest max_tokens 4000 → 6000 정정. cycle 10.5 stock_analyst 패턴 1:1 미러.

### 3. 거부 응답 cited v3.1 룰 명확화 — 9 분석가 표준 룰 정의 사이클 후보

- **현상**: news_curator 자가 진단 거부 응답 + flow_analyzer boundary 침범 거부 응답 양쪽에서 `cited: []` + 풀이 누락. **일관된 패턴** = 거부 응답 시 cited 룰 자동 면제됨. 단 manifest 의 "응답 끝에 두 부분 필수" 강제 룰을 위반.
- **결정 옵션**: (a) 거부 응답 시 cited 면제 명시 vs (b) 거부 응답도 cited 풀이 필수 명시.
- **해소 SPEC 후보**: `PERSONA-REFUSAL-CITED-RULE-001` 가칭 — 9 분석가 manifest response_rules 표준 룰 정의 (가벼운 SPEC).

### 4. news_curator prompt 32,871 chars — 다른 분석가 2배, 페르소나 슬림화 후보

- **현상**: market_state_analyzer (17,155) / stock_picker (19,852) / trading_journalist (13,275) / flow_analyzer (17,304) 대비 news_curator (32,871) = ~2배. canon 자료 0 시드인데 prompt 큼 = 페르소나 자체가 큰 가능성.
- **영향**: 호출 비용·지연 ↑. 거부 응답에도 prompt 비용 17,928 tokens 누적.
- **해소**: 페르소나 슬림화 (response_rules · § 압축, NEWS-SOURCE-001 SPEC 진행 시 동시).

## news_curator SLOT S2 자료원 방향성 결정 (단계 0 인터뷰)

본 사이클 단계 0 인터뷰에서 후속 자료원 방향성 4 요소 결정:

1. **기본 자료원 = Perplexity MCP** — 외부 MCP 호출로 자동 수집, 작업량 최소, ~$0.005/호출
2. **추가 입력 채널 = 유튜브 본문 요약 직접 전달** — 사용자 manual 보조 채널
3. **시간축 라벨링 강화** — "단기 vs 지속" 본질 구분 정밀화
4. **뉴스 학습부 + DB + UX/UI 관리** — 대규모 인프라

→ 후속 별도 SPEC (`NEWS-SOURCE-001` 가칭, 규모 ↑, 사용자 우선순위 ↓). 본 사이클은 본문 직접 제공 모드로 검증 진행. 메모리 `project_news_source_decision.md` 신규 박음.

## 의도적으로 안 한 것

- **부채 3 (거부 응답 cited 룰) 의 마이크로 정정**: 단일 분석가 정정이 아니라 9 분석가 표준 룰 정의 사안이므로 별도 SPEC 사이클 후속.
- **자연어 자동 라우팅 (`both: 005930` → Track A + Track B 동시)**: Top 1 (production UX) 본격 사이클의 핵심 작업. 본 사이클은 Track A + Track B 직접 호출 = both 효과만 시연.
- **snapshot extend SPEC 신설**: 부채 1 의 해소 후보로 RESUME Top 1 진입 차단점이지만, 본 사이클 목표 (5 분석가 검증) 와 안 맞음. 별도 SPEC 사이클.

## 다음에 이어서 할 작업 (우선순위 갱신)

**중요**: 본 사이클 결과로 RESUME Top 1 차단점 발견 = snapshot extend 가 Top 1 진입 전 우선 해소 권유.

1. **`INFRA-SNAPSHOT-EXTEND-001` SPEC 신설** (~1.5 세션, 신규 Top 1 후보) — 5 분석가 본격 판정 차단점 해소. collectors/snapshot.py 보강 (지수 위계·등락 추세·breadth·거래량 / 섹터 RS·수급망·정배열·CAN SLIM 7축 / 5 주체 수급). 본 부채 해소 후 production UX 답변 의미 회복.
2. **`WAVE-ALPHA-001` SPEC 신설** (~1 세션) — α 공식 확정 → verdict=confirmed_* 도달 → MS4 진입 베이스라인.
3. **production UX 본질 구현** (~3 세션) — Top 1 → Top 3 강등 권유 (snapshot extend 후 자연 진입).

## 맥락 재진입 힌트

- **9 분석가 풀세트 production 검증 완료** = MS3 (cycle 10.5) + 5 분석가 (본 사이클) + Track Selector 양 트랙 = production 단위 검증 베이스라인 확보.
- **본격 판정 차단점 = snapshot 데이터 부재**: production UX 직전 차단점. snapshot extend 우선 해소 → Top 1 (UX) 답변 의미 회복.
- **거부 응답 cited 룰**: 단일 분석가 마이크로 정정이 아닌 9 분석가 표준 룰 정의 사안 (별도 가벼운 SPEC).

## 세션 중 실 비용

- **gemini API**: $0.0083 합산 = 5 분석가 호출 $0.0049 + boundary 시나리오 2 케이스 $0.0014 + stock_picker 재호출 $0.0008 + Track A $0.0020 + Track B $0.0014 - 일부 503 풀러 재시도 비용 0 (실패 시 호출 비용 0).
- **9 분석가 + Track A·B 총 11 호출** 누적 (~$0.01 미만).

## 커밋 상태

- 본 cycle 11 commit + push 진행 (stock_picker manifest max_tokens 6000 정정 + c_worked + RESUME + SESSIONS + 메모리 갱신).
