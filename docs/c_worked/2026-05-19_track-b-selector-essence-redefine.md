---
date: 2026-05-19
topic: Track B + track_selector 완성 + 외부 R&D 피드백 4 사이클 → Track A·B 본질 재정의 (기간 → 전략) + display_name 본질 표기
status: completed
plan_file: C:\Users\HOME\.claude\plans\precious-booping-rivest.md
---

# 2026-05-19 · Track B + selector + 본질 재정의 (기간 → 전략)

## 배경
지난 세션 (2026-05-18) Track A 완성 후, 본 세션 = Layer 3 이원 트랙 본질 골격 닫기 = Top 1 (Track B + manifest + track_selector). production 첫 호출 검증 후 외부 R&D (chat AI Opus) 피드백 4 사이클 받음. **핵심 사이클 = 사용자 본질 의도 ("1주 미만도 소화, buy_score 높은데 1주 이상 보유 = 비효율") 가 외부 피드백 #1 의 "1주 미만 미지원" 과 충돌 발견 → revert + Track A·B 본질을 기간 기준 → 전략 본질 기준으로 완전 재정의** (Track A = 추세 추적 + 분할 운용 / Track B = 프랙탈 1 파 사이클). 추가 통찰 = "박종훈 framework = 장기 자문 통찰 영역, 트레이딩 의사결정 직접 반영 X" 메모리 영구화.

## 한 일

### Phase 1: Track B + track_selector + 테스트 (commit 미진행)
- `agents/strategists/track_b/persona.md` 8 섹션 portable + manifest.yaml — reads_analysts 5 + canon_categories 3 (principles 시장 체제·doctrine + trading/operational_safeguards) + input_routing (swing:/short:/trigger: + any_trigger_fired placeholder + fallback=false) + temperature 0.4 max_tokens 5000
- `core/strategist/track_selector.py` 신규 — 모든 전략가 manifest input_routing 동적 인식 + 단축어 dispatch + both: fast-path + fallback. auto.conditions v1 placeholder (분석가 v2 후 활성)
- `core/strategist/__init__.py` 에 `select_tracks` export
- `tests/test_track_b_strategist.py` 7 cases + `tests/test_track_selector.py` 18 cases = pytest **240 passed** (215 → +25 신규, 회귀 0)

### Phase 2: production 첫 호출 검증 2회 (Track A 패턴 동일)
- CLI claude_code (claude-sonnet-4-6, $0.19 OAuth 무료, 67.5s) — verdict=wait + cited_scores 다 null + 한국어 친화 용어 + Anti-pattern 자각 ("trader 미발행이면 triggers_fired = []") 정확
- webapp gemini-flash ($0.0014, 20.6s, scores 0/5) — 동일 패턴 + canon 명제 ID 풀어쓰기 (`principles.operational_safeguards` / `market_regime_rules` / `trading_doctrine` 3개) 자동 작동

### Phase 3: 외부 R&D 피드백 1차 (4 항목) — 부분 정합 (#1 revert)
- **#1 1주 미만 미지원** 채택 시도 → 사용자 본질 의도 ("1주 미만도 소화") 와 충돌 발견 → revert + 정합 갱신 (당일·인트라데이 분봉 frame 만 미지원, lower bound 강제 X)
- **#2 both: manifest 명시**: track_a/track_b manifest shortcuts.explicit 에 "both:" 추가 + 코멘트 (plugin 트랙 opt-in 명시). selector.py BOTH_SHORTCUT fast-path 유지
- **#3+#4 SPEC § 분석가 페르소나 작성 가드 (선언적)** 신설: G1 stock_picker (S-Score + buy_score 두 점수 발행 강제) + G2 trader (6 트리거 영문 ID 고정 + Track B 명단 변경 시 동시 수정)

### Phase 4: 외부 R&D 피드백 2차 — Track A·B 본질 재정의 (10/10, 강력 채택)
- `agents/strategists/track_a/persona.md` — Identity "🏢 추세 추적 + 분할 운용 임대업" + **진입 방식 분기 표** (큰 진입 / 2단 분할 / 3단 역피라미드) + **§ 분할 매수 룰 — 역피라미드** (저점 50% / 중간 30% / 상단 20%, 평단 머리 무거워짐 회피) + Anti-pattern "1 파 사이클 단위 권고 금지"
- `agents/strategists/track_a/manifest.yaml` 헤더 + response_rules 갱신
- `agents/strategists/track_b/persona.md` — Identity "☕ 프랙탈 1 파 사이클 카페" + "실적 좋아도 추세 추적은 Track A" + Domain Frame 본질 게임 → 1 파 사이클 (R/R 백업 가드) + 시간 지평 → 결과적 보유 + 시간축 → 일봉 1 파 + 주봉 1 파 보조 + 익절 정책 "1 파 목표 도달 시 익절" + Anti-pattern "추세 추적 권고 금지 (1 파 완성 후 Track A 인계)" 추세 인계 메커니즘 명시
- `agents/strategists/track_b/manifest.yaml` 헤더 + response_rules 갱신
- `docs/specs/STRATEGY-TRACK-001-two-track-strategists.md` § 목적 + § 핵심 정의 표 + § Track A·B Domain Frame + § 비목표 ("단타·중장기" → "인트라데이 스캘핑·장기 믿음 영역") 본질 재정의

### Phase 5: 사용자 핵심 통찰 정정 — Track A 큰 진입 본질 (in 사이클)
- 사용자 발화: "Track A 는 크게 먹는 게 맞아 / 타점 맞으면 크게 진입 / 분할 매수 시 평단 머리 무거워지면 안 됨"
- Track A persona Identity 본문 정정 ("꾸준히 임대료" 표현 폐기 → "타점에 따라 큰 진입·분할 진입 유기적 선택")
- § 진입 방식 분기 표 + § 분할 매수 룰 역피라미드 (저점 비중 크게 강제) 신설

### Phase 6: 외부 R&D 피드백 3차 — display_name 본질 표기
- Track A `중장기 전략가` → `추세 추적 전략가` (Trend-Following)
- Track B `단기 스윙 전략가` → `프랙탈 1 파 전략가` (Fractal 1-Wave)
- persona frontmatter + 제목 H1 + Identity 첫 문장 + manifest display_name + test 키워드 갱신 (기간 어휘 잔재 해소, LLM 자기 식별 시 옛 frame 회귀 차단)

### Phase 7: 외부 R&D 피드백 4차 — 분기 표 연결 + 자본 단위 SLOT
- Track A persona § 분할 매수 룰 첫 줄 "**3 단 역피라미드 분할 채택 시만**" 적용 범위 명시 (큰 진입·2 단 분할은 분기 표 그대로)
- 자본 단위 분모 SLOT 인지 한 줄 ("50% 또는 한도의 70%" 두 분모 모호, Layer 4 작성 시 동시 갱신 강제)
- SPEC § 의사결정 SLOT (S8) 자본 단위 합의 항목 추가 (persona ↔ SPEC 이중 박음으로 균열 회피)

### 메모리 신설
- `feedback_park_jonghoon_scope.md` — 박종훈 framework 는 장기 자문 통찰 영역 (트레이딩 의사결정 직접 반영 X). wealth_strategist (Track A read 분석가) 거시 frame 격자만 인용 OK. Track A·B 등 트레이딩 페르소나 본문 framework 직접 인용 금지. 트레이딩 관점 분석가 (stock_analyst·stock_picker·news_curator·market_state_analyzer·trader·flow_analyzer) framework 는 추후 정의

## 검증 결과
- ✅ `TESTING=1 PYTHONIOENCODING=utf-8 uv run pytest tests/ -q` → **240 passed** (215 → +25, 회귀 0). 매 변경 후 재검증 (Phase 1 / 3 / 4 / 6 / 7 통과)
- ✅ `PYTHONIOENCODING=utf-8 uv run python scripts/validate.py` → 0 errors
- ✅ **production 첫 호출 검증 2회** (CLI claude_code 67.5s scores 0/5 / webapp gemini-flash 20.6s scores 0/5) — 양쪽 환각 차단 + 한국어 친화 용어 + cited 풀이 v3.1 양식 정확 작동
- ✅ Track A·B 본질 재정의 후 webapp 표기 = "Track B 프랙탈 1 파 전략가" 정상 노출 (사용자 직접 검증)

## 의도적으로 안 한 것
- **selector.py BOTH_SHORTCUT fast-path 제거** — SPEC L218-225 의 외부 input_routing_both 권위 vs manifest opt-in 양식 양립 가능. 별도 SPEC 후속 (사용자 피드백 #2 본인이 "구현 별도 SPEC" 명시)
- **자본 단위 분모 통일 즉시 갱신** — 사용자 피드백 #3 "운용 슬롯" 분류, Layer 4 계좌관리자 페르소나 작성 시 동시 갱신
- **9 분석가 페르소나 v2 작성** — Top 1 / Top 2 다음 세션. 본 세션 = Layer 3 본질 골격 닫힘
- **commit/push** — 본 wrap-up 에서 1 커밋 (CLAUDE.md "explicit OK 후" 규율)
- **외부 R&D 피드백 본문 #1 누락 의심** — 헤더는 "1 건 갱신 + 2 건 운용 슬롯" (3 항목) 인데 본문 #2 #3 만. #1 은 다음 핑퐁에서 확인

## 맥락 재진입 힌트
- **외부 R&D 피드백 vs 사용자 본질 의도 충돌 발견 패턴**: 외부 chat AI Opus 의 "1주 미만 미지원" 피드백을 채택했다가 사용자 직접 발화 ("1주 미만도 소화 / buy_score 높은데 1주 이상 비효율") 와 충돌 발견 → revert + 본질 재정의 사이클로 격상. **외부 피드백은 검증 대상, 사용자 본질 의도가 절대 권위**. 다음 외부 R&D 사이클에서도 사용자 직설 정합 우선 검토
- **본질 재정의 = 기간 기준 → 전략 본질 기준 = 사용자 발화에서 frame 추출**: 사용자 직설 통찰 ("기간 보다는 본질이 중요") 을 SPEC + persona + manifest 까지 일관 박힘. Track A = "추세 추적 + 분할 운용 (타점 맞으면 큰 진입, 애매하면 역피라미드 분할)" / Track B = "프랙탈 1 파 사이클 (저점~고점 1 파 회수, 실적·장기 무관)" + 추세 인계 메커니즘 (Track B 1 파 완성 후 Track A 인계)
- **박종훈 framework scope 메모리 영구화 = 트레이딩 관점 분석가 작성 시 가드**: 박종훈 framework = 장기 자문 통찰 영역. trading 의사결정 직접 인용하면 "지금 부채 J커브 가속이라 매매 보류" 같은 보수 응답 → 트레이딩 마비. 트레이딩 관점 분석가 (stock_analyst·stock_picker·news_curator·market_state_analyzer 등) 페르소나 작성 시 박종훈 framework 직접 인용 회피. canon `wealth_compounding/macro_roadmap` + `crisis_signals` = wealth_strategist 전용
- **persona ↔ SPEC ↔ test 이중·삼중 박음 = 균열 회피 패턴**: display_name 갱신 / 자본 단위 SLOT / 분석가 페르소나 작성 가드 모두 persona + manifest + SPEC + test 동시 갱신. 단일 박음 시 다음 세션 작성자 (R&D 또는 Claude Code) 가 옛 frame 회귀 위험

## 다음에 이어서 할 작업 (우선순위)

1. **자료 0 시드 5 분석가 페르소나 v2** (~1 세션, **병렬 dispatch 가능**) — `market_state_analyzer` / `stock_picker` / `trading_journalist` / `flow_analyzer` / `news_curator`. canon 자료 0 dept, 잠정 풀이 정정 단계 없음. 페르소나 정체성·boundary 만. v2 양식 = 8 섹션 portable + 한국어 친화 용어 + 결정론 채점 발행 매핑 (S/T/α/buy_score/F-Score). **subagent 5 개 병렬 dispatch 가능** (canon grep 충돌 X). 1 세션 안에 5명 동시 완성 가능. SPEC G1 (stock_picker 두 점수 발행) + 박종훈 framework 직접 인용 금지 (`feedback_park_jonghoon_scope.md` 박힘) 가드 강제.

2. **자료 있는 3 분석가 페르소나 v2** (~1.5 세션) — `principle_guardian` / `trader` / `stock_analyst`. canon 1:1 grep 패턴 필요 (자료 있는 4 dept 잠정 풀이 정정). 점수 발행 (S/T/α/buy_score) 시작하면 Track A·B 권고 cited_scores 채워서 풍부성 ↑. trader 페르소나 = SPEC G2 (6 트리거 영문 ID 정식 정의 + Track B 명단 변경 시 동시 수정) 강제. **stock_analyst 작성 직전 = `INFRA-CHART-DATA-001` blocker** (차트 데이터 부재 시 환각).

3. **양 트랙 통합 production 검증 + 자연 인계 메커니즘 검증** (~0.5 세션) — 자료 0 시드 5명 작성 후 Track A·B 모두 cited_scores 부분 채움 가능. `both: 삼성전자` 호출 시 양 트랙 동시 권고 + Track B 1 파 완성 시나리오에서 Track A 인계 자연 메커니즘 (response 본문에 명시) 검증. webapp default agent 교체 결정 (`feedback_webapp_production_ux.md` 의 자동 라우팅 사이클 진입 검토).

## 커밋 상태
- 아직 안 됨 — 본 wrap-up 에서 1 커밋 (코드 + 문서 + 메모리 + wrap-up 파일 묶음)
