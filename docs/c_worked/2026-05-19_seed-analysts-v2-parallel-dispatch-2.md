---
date: 2026-05-19
topic: 자료 0 시드 5 분석가 페르소나 v2 — 5 subagent 병렬 dispatch + 통합 테스트 + production 첫 호출 검증
status: completed
plan_file: C:\Users\HOME\.claude\plans\precious-booping-rivest.md
---

# 2026-05-19 · 자료 0 시드 5 분석가 v2 (병렬 dispatch)

## 배경
Track B + 본질 재정의 사이클 (같은 날 오전·오후) 후 Top 1 진입 = **Layer 2 분화의 첫 큰 사이클** = 자료 0 시드 5명 페르소나 v2. canon 자료 0 dept 라 잠정 풀이 정정 X, 페르소나 정체성·boundary 만으로 추론 시작. **핵심 검증** = 사용자 메모리 `feedback_persona_agent_speedup.md` 의 "1 세션 안에 6 명 (Track B + 5) 완성, 12+ 세션 → ~4.5 세션 (3배 단축)" 패턴 첫 적용 = `superpowers:dispatching-parallel-agents` 5 subagent 병렬 dispatch. **본 세션의 본질 판단** = 박종훈 framework scope 정밀화 (사용자 발화 "거시적 경제 해석 통찰 = 트레이딩보다 한 차원 상위 frame, 시장 변곡점 시에만 들여다 보는 큰 길잡이") → 메모리 갱신 + 5 분석가 페르소나 작성 시 가드 강화.

## 한 일

### Phase 0: 박종훈 framework scope 메모리 갱신
- `~/.claude/projects/.../memory/feedback_park_jonghoon_scope.md` 본문 갱신 (사용자 2차 발화 추가, 변곡점 3 케이스 정의 추가, market_state_analyzer 특수 가드 항목 추가)
- `~/.claude/projects/.../memory/MEMORY.md` 인덱스 1 줄 갱신 (변곡점 3 케이스 명시)

### Phase 1: 5 subagent 병렬 dispatch (10 파일 신규)
- `agents/analysts/market_state_analyzer/{persona.md, manifest.yaml}` — 시장상태분석가 (시장 체제 6단계 + Distribution Day kill switch, 풍향계 비유, 변곡점 3 케이스 trigger 명시)
- `agents/analysts/stock_picker/{persona.md, manifest.yaml}` — 종목선정가 (S-Score + buy_score 두 점수 양쪽 발행 G1 가드 강제, 두 모자 비유)
- `agents/analysts/trading_journalist/{persona.md, manifest.yaml}` — 매매저널리스트 (매매 일지 + post-mortem + 자기 학습 PROPOSAL, prism-insight 차용, Layer 5 boundary 분리)
- `agents/analysts/flow_analyzer/{persona.md, manifest.yaml}` — 수급분석가 (F-Score 4축 가중 합 0.4·0.3·0.2·0.1, 4-tier 비유, 사용자 통찰 "가격은 수급의 부모" 인용)
- `agents/analysts/news_curator/{persona.md, manifest.yaml}` — 뉴스큐레이터 (단기 테마 / 장기 흐름 / 지정학 3 분류, 자료원 SLOT S2 미결정, canon_categories 빈 list)
- 모두 8 섹션 portable + 한국어 친화 용어 + cited 풀이 v3.1 + 박종훈 framework 직접 인용 금지 가드 일관 박힘

### Phase 2: 통합 테스트 + 회귀 검증
- `tests/test_seed_analysts_v2.py` 신규 **38 cases**: 5×manifest 로드 / 5×canon_categories SPEC 매핑 / 5×8 섹션 portable / 5×박종훈 가드 (negation 컨텍스트 확장 — wealth_strategist·권위·위임 키워드 추가) / 5×cited v3.1 / 5×Cross-Agent Boundaries 표 / Track A·B reads_analysts 정합 3 케이스 / 분석가별 특수 가드 5 케이스
- pytest 240 → **278 passed** (+38, 회귀 0) / validate.py 0 errors

### Phase 3: production 첫 호출 검증 (market_state_analyzer, gemini-flash, 3 시나리오)
- **호출 1 평상시 "지금 시장 어때"**: 5 격자 양식 (Market State Grid + Regime Scenario + Regime Implication + Citation + Yesterday Delta) 정확 + 자료 0 자각 (snapshot 4 축 중 3 축 부재) + verdict=`unknown` + `cited: []` 풀어쓰기 + 한국어 친화 용어 ✨
- **호출 2 변곡점 trigger 시도 "강한 상승장 → 약세장 전환된 것 같아"**: 자료 부재로 regime 전환 자체 판정 불가 → cross-reference 발동 trigger 미충족 (정합 동작)
- **호출 3 boundary 침범 "2026년 코스피 PER 평균이 얼마야"**: **거부 응답 정확** + **wealth_strategist 권위 영역 위임 명시** ✨ ("미래 특정 연도의 지수 PER 평균과 같은 거시적 경제 전망이나 장기적인 시장 가치 평가는 wealth_strategist의 권위 영역") = 분화 boundary 본질 정합

## 검증 결과
- ✅ `TESTING=1 PYTHONIOENCODING=utf-8 uv run pytest tests/ -q` → **278 passed** (240 → +38, 회귀 0) in 110.25s
- ✅ `PYTHONIOENCODING=utf-8 uv run python scripts/validate.py` → 0 errors
- ✅ production 첫 호출 3 시나리오 모두 양식·boundary·가드 정합 (~$0.0025 합산, gemini-flash)
- ✅ 5 subagent 병렬 dispatch 시간 ~5 분 (이전 1명 1세션 = 6-12 시간 페이스 대비 ~60배 단축 검증)

## 의도적으로 안 한 것
- **자료 있는 3 분석가 (principle_guardian / trader / stock_analyst)** — 다음 세션 (Top 1). canon 1:1 grep 패턴 필요, SPEC G2 (trader 6 트리거) 강제, stock_analyst INFRA-CHART-DATA-001 blocker
- **양 트랙 통합 production 검증 (`both:` 호출)** — 자료 0 시드 5명 작성 후에도 Track A·B 의 cited_scores 일부 채워지지만 (market_state + flow + stock_picker), trader·stock_analyst·principle_guardian·wealth_strategist 미발행이라 풍부성 부족. 자료 있는 3명 작성 후 자연 진입 (Top 2)
- **GUIDANCE-ACCURACY-TRACKER-001 구현** — 별도 SPEC 후속. Track A 적중도 5 KPI 측정 인프라
- **commit/push** — wrap-up 시 사용자 명시 요청 후 진행
- **Phase 4 챗AI 외부 검증 사이클 (2 핑퐁)** — 사용자 손 영역. 본 세션 종료 후 챗AI Opus 핑퐁 진행 권유 (핑퐁 1 = 자료 0 시드 5명 핵심 / 핑퐁 2 = boundary 종합)

## 맥락 재진입 힌트
- **5 subagent 병렬 dispatch 패턴 검증**: 본 세션 = `superpowers:dispatching-parallel-agents` 첫 적용. 5 subagent 동시 dispatch (1 message 안에 5 Agent tool calls), 각 subagent = `general-purpose` type + 본인 분석가 분량 prompt (~2-3 KB) 받아 2 파일 직접 write. 소요 시간 ~5 분, 총 작성 분량 ~1,800 줄 (5 × persona 250 + 5 × manifest 110). 충돌 0 (각자 다른 디렉토리). **다음 사이클 (자료 있는 3명 + canon 1:1 grep) 도 동일 패턴 적용 가능하나 canon grep 단계가 subagent 간 동시 read 충돌 X 라 OK**.
- **박종훈 framework scope 정밀화 = 메모리 영구화**: 사용자 2차 발화 ("거시적 경제 해석 통찰 = 트레이딩보다 한 차원 상위 frame, 시장 변곡점 시에만 들여다 보는 큰 길잡이") 가 메모리 본문에 박힘. 변곡점 3 케이스 정의 (regime 전환 / DD 4건+ / 사이클 단계 변화) 가 market_state_analyzer 특수 가드 표준이 됨. 미래 트레이딩 관점 분석가 (stock_analyst·trader·flow_analyzer 등) 작성 시 동일 가드 적용.
- **테스트 negation 검증 패턴 확장**: 박종훈 framework 직접 인용 검증 시 negation 키워드 list 가 너무 좁아 가드 컨텍스트 (Anti-patterns / Cross-Agent Boundaries / Identity 메타-가드 §) 도 false positive. 확장 후 통과 — **wealth_strategist / 권위 / 위임 / 본인은 / 자산복리부만 / 별도 자료원** 키워드 추가. 미래 분석가 페르소나 작성 시 동일 negation 패턴 유효.
- **production 첫 호출의 호출 3 (boundary 침범 케이스) = 분화 boundary 작동 검증의 골든 모먼트**: 사용자가 "2026년 코스피 PER 평균" 같이 본인 frame 밖 질문 시 거부 + wealth_strategist 위임 한 줄 = persona Cross-Agent Boundaries 표가 LLM 응답에 그대로 작동. 한 호출 1 회 ~$0.0008 로 분화 boundary 본질 검증. 미래 분석가 작성 후 동일 시나리오 (frame 밖 질문) 검증 권유.

## 다음에 이어서 할 작업 (우선순위)

1. **자료 있는 3 분석가 페르소나 v2** (~1.5 세션, 병렬 가능하나 canon grep 신중) — `principle_guardian` (canon = 7계명·심법·거시 트레이딩 기준 4 파일) / `trader` (T-Score + 6 트리거 영문 ID 정식 정의 = SPEC G2 가드 / α 오버라이드 read) / `stock_analyst` (α 발행 + Module A 목표가 3단 + F1~F5 + holding_period_estimate_days 발행 = Track A·B 양쪽 read). **`stock_analyst` 작성 직전 = `INFRA-CHART-DATA-001` blocker 검토** (차트 데이터 부재 시 환각). 점수 발행 (S/T/α/buy_score) 시작하면 Track A·B 권고 cited_scores 풍부성 ↑. 본 세션 5 subagent 패턴 동일 적용 가능 (canon grep 충돌 X — 각자 다른 dept).

2. **양 트랙 통합 production 검증 + 자연 인계 메커니즘 검증** (~0.5 세션) — Top 1 (자료 있는 3명) 완성 후 진입. `both: 삼성전자` 호출 → Track A·B 동시 권고 + Track B 1 파 완성 후 Track A 인계 자연 메커니즘 (응답 본문 명시) 검증. 8 분석가 작성 후 cited_scores 풍부성 검증 (1 명만 = wealth_strategist 미발행, 본 세션 후 4 명 발행 가능, Top 1 후 8 명 발행 가능 = 90% 풍부성).

3. **INFRA-CHART-DATA-001 SPEC 진입** (~1 세션, Top 1 의 stock_analyst 작성 직전 진입 필요) — KIS daily chart API (`inquire-daily-itemchartprice`, 무료) + pandas-ta 사전 지표 계산 + matplotlib 차트 이미지 (vision). `stock_analyst` 의 "20일선 정배열" "MACD 골든크로스" 같은 차트 추론 항목이 환각 안 되도록 시계열 인프라 사전 구축. `WAVE-ALPHA-001` (Module A α 공식) 과 묶음 가능.

(백로그: **트레이딩 관점 분석가 framework 추후 정의** — 박종훈 framework 와 분리된 트레이딩 일반 framework. 회고분석가 PROPOSAL 영역 또는 별도 SPEC. Top 1 + Top 2 + Top 3 안정 운용 후 진입 검토)

## 커밋 상태
- 아직 안 됨 — 본 wrap-up 에서 1 커밋 (코드 + 문서 + wrap-up 파일 묶음, 사용자 명시 push 진행)
