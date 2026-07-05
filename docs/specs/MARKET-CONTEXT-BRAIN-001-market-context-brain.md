---
spec_id: MARKET-CONTEXT-BRAIN-001
title: 시장을 느끼는 두뇌 — 이벤트 해석·주도주 판별·포트폴리오 자세 (roadmap)
team: shared
type: roadmap
level: roadmap
status: draft
parent: BRAIN-QUALITY-001
generates: []
children:
  - AUTO-SIGNAL-INTEGRITY-001        # Tier 0: 자동 신호 정합 핫픽스 (defensive 게이트·우회 해소·배선 결함)
  - NEWS-EVENT-INTERPRETATION-001    # Tier 1: 중심 이벤트 격상 + LLM 해석 (미작성 — 착수 시 /spec-interview)
  - LEADERSHIP-DISCERNMENT-001       # Tier 2: 주도주 판별 (미작성)
  - MARKET-POSTURE-ACTION-001        # Tier 3: 포트폴리오 자세 액션 — 현금비중·de-risk (미작성)
depends_on:
  - BRAIN-QUALITY-001 (부모 — 두뇌 퀄리티 기둥)
  - AUTO-SIGNAL-GENERATION-001 (자동 권고 funnel 위에 정합·맥락을 올림)
  - NEWS-SOURCE-001 (뉴스 수집·분류·digest 파이프라인 — Tier 1 이 그 위에 해석층을 올림)
  - EVOLUTION-001 (Tier 4 학습 루프 — 채점→회고 PROPOSAL)
---

# MARKET-CONTEXT-BRAIN-001 — 시장을 느끼는 두뇌 (roadmap)

> **진화팀 진단 SPEC (2026-07-05, 팩트 기반).** 사용자가 6월 말~7월 초 고변동 장세(메타발 AI capex 논란 → 반도체 급락, SpaceX IPO 수급 블랙홀, 국민연금 리밸런싱)에서 시스템 추천을 지켜보고 제기한 5가지 통찰을, 코드 배선·LLM 프롬프트·DB 추천 히스토리 전수 조사로 검증했다. **결론: 출력이 틀린 게 아니라 하네스가 얇다** — 전략가가 시장을 "느낄" 재료가 프롬프트에 물리적으로 들어가지 않는다.

## 1. 진단 — 사용자 통찰 검증 (2026-07-05 실측)

| # | 사용자 주장 | 판정 | 핵심 증거 |
|---|---|---|---|
| ① | 시장 맥락(이벤트·수급·거시)을 반영 못 한다 | **CONFIRMED** | Track A LLM 입력에 뉴스 digest·종합 시장관 미주입 — `core/knowledge/compose.py` 에 `news_digest_md`·`market_view_md` 슬롯이 **있으나** `core/strategist/run_strategist.py` 가 전달하지 않음. 시장 맥락 = regime 라벨 + DD 카운트 + 당일 폭락 게이트뿐 |
| ② | 월봉 7월선·추세·가속만 보고 추천한다 | **CONFIRMED** | α = 순수 가격·시간 기울기 비율(`collectors/scoring.py` — 주도주·섹터·뉴스 0). 자동 권고 경로(`_TRACK_BYPASSED_IDS`)는 stock_analyst(α)·wealth_strategist(거시)·**principle_guardian 까지 의도적 우회** |
| ③ | 후성 같은 변두리 고변동주를 고점에 buy | **CONFIRMED (강)** | 후성(093370) buy 3회 = **기간 내 최다 추천 종목**. 첫 buy(06-16 18:08)는 3일 +38% 블로우오프 고점(06-15) **다음날** → 즉시 −12%. **같은 시각 track_b 는 "이격도 +37~60% 과열, kill switch" 로 wait** — 좌우 손 불일치 |
| ④ | 뉴스부 = 기사 나열, 변곡 이벤트 추론 없음 | **CONFIRMED** | 메타/AI버블 기사 06-23~28 대량 수집됐으나 다수 **미라벨링**(direction/magnitude=None). `top_themes` = 건수순이라 1건짜리 초대형 이벤트가 노이즈 클러스터에 밀리고, magnitude 3 이벤트는 net_tilt 평균에 희석. news_curator 출력은 **어느 전략가 manifest `reads_analysts` 에도 없는 dead-end** |
| ⑤ | 맞은 종목은 거래대금 상위가 섞여서일 뿐 | **부분 지지** | 자동 buy 알림 11건 중 10건이 거래대금 상위 유니버스 출신(전제 성립). 단 `predictions` 사후 채점(actual_outcome/score)이 비어 있어 인과 정량 검증 불가 — **그 자체가 track record 부재 결함** |

### 조사 중 추가 발견 (사용자 미인지)

1. **defensive 인데 buy 발령 모순**: entry_posture 는 06-22부터 계속 defensive 였는데 06-29 자동 buy 5건 + 07-02 buy 1건 발령. `deployment_cap` 은 사이징(계좌관리자)에만 작동하고 **신호 발행 게이트가 아님**.
2. **regime 후행 실증**: 반도체 급락 시작일(07-01)에도 strong_bull(conf 70), 급락 **이후** 07-03에야 sideways. `classify_market_regime` 입력 = 지수 MA·기울기·breadth·DD 전부 가격 후행 지표, 뉴스 기여 0. SK하이닉스 07-01→02 −14.6%, 삼성전자 −9.1%.
3. **AlphaPosture dead path**: `compute_scorecard`(auto_signal.py)가 `sector_rs_score`·`wave_alive` 를 안 채움(None, L71 주석 "다음 마일스톤") → 약세장 눌림목 bear_override·강세섹터 차등이 **코드상 절대 발동 불가**. (기존 M3b 잔여와 동일 항목.)
4. **"현금 비중 확보" 출력 경로 부재**: 전략가 권고 스키마(`core/strategist/recommendation.py`)는 종목 단위 매매 계획뿐. 기존 보유 de-risk / 현금화 명령을 낼 주체·필드가 없다. vix_panic 도 신규 진입 동결만.
5. **의도된 설계 철학과의 충돌**: 뉴스부 N5 canon 이 "뉴스 tone 을 매수/관망 게이트로 쓰지 말라" 명시 — 뉴스→매매 단절의 절반은 버그가 아니라 설계 결정. 바꾸려면 canon 개정이 선행 (§4 사용자 결정 참조).

## 2. 근본 원인 구조

- **입력 결핍**: 전략가가 시장을 느낄 재료(이벤트·시장관·섹터RS·파동)가 프롬프트에 안 들어감 — 슬롯 미배선 3곳(news_digest_md·market_view_md·sector_rs/wave) + 자동 경로 우회 3인(α·거시·원칙).
- **격상 결핍**: 뉴스부는 건별 라벨까지는 하나 "오늘의 중심 이벤트"를 식별·승격하는 단계가 없음(빈도 클러스터 + 평균 희석).
- **게이트 결핍**: 시장 방어 태세(defensive)가 신호 발행을 막지 못하고, 원칙수호자가 자동 경로에서 빠짐.
- **주도주 결핍**: S-Score = 60일 상대강도 순위 + 정배열 + 섹터RS 프록시(theme 매핑 실패 시 중립 5.0 fallback) — "지금 시장을 끄는 것이 무엇인가"를 판별하는 입력이 없어 volume_bull 급등주(후성)가 주도주로 오인됨.
- **학습 결핍**: predictions 채점 미가동 → 후성 −12% 같은 실패가 시스템에 피드백되지 않음(track record 0 — AUTO-SIGNAL 진단과 동일 뿌리).

## 3. 로드맵 (Tier 0 → 4, 의존 순서)

### Tier 0 — 정합 핫픽스 (`AUTO-SIGNAL-INTEGRITY-001`, implementation SPEC 작성됨)
지금 배선이 약속한 것부터 지키게 한다. 새 능력 0, 결함 수리 4건: defensive 신호 게이트 / sector_rs·wave 배선 / principle_guardian 결정론 체크 복원 / 미라벨링 뉴스 백필. → 상세는 자식 SPEC.

### Tier 1 — 뉴스부: 중심 이벤트 격상 + **해석** (`NEWS-EVENT-INTERPRETATION-001`, 미작성)
사용자 결정(2026-07-05): 격상 이벤트만 게이트 허용. 단 **격상보다 해석 퀄리티가 본질** — "단기적 공포인가 시장 변곡인가, 시계열상 어떤 매매 포인트로 삼아야 하는가"를 판별해야 한다.
- **격상 레인**: `build_news_digest` 에 magnitude=3(또는 mag≥2 × 다수 소스 동시 보도) 단일 이벤트를 tone 평균·건수 클러스터와 **별도 레인**으로 승격 — 희석 방지.
- **해석 스테이지 (핵심 신설)**: 격상된 이벤트에 한해 LLM 심층 해석 1콜 — N2 시간축 3단(ephemeral_shock / short_theme / structural_trend)을 **기존 canon 축 그대로 재사용**하되, 출력에 ① 성격(단기 공포 vs 구조 변곡) ② 영향 경로(어느 섹터·주도 테마) ③ 매매 함의(관망/현금확보/눌림목 대기 등 posture 후보) ④ 재평가 조건(무엇이 확인되면 판정 변경). 2-Stage 하이브리드 패턴(결정론 격상 감지 + LLM 해석 + 캐싱) 재사용.
- **해석 질문지 3축 (사용자 통찰 2026-07-05 — 07-03 SK하이닉스 실판단에서 추출)**: 해석 LLM 이 반드시 답해야 할 채점 축 — ⑴ **novelty**: 새 정보인가 이미 예고됐던 재탕인가 (메타 클라우드는 연초 예고 재탕 → 임팩트 할인) ⑵ **펀더 정합**: 사이클 팩트(실적·가이던스)와 뉴스 내러티브가 정합하는가 (마이크론 호가이던스 vs 셀오프 내러티브 = 괴리 → 뉴스가 빌미일 확률) ⑶ **노이즈 반복 패턴**: 매일 다른 악재가 돌아가며 나오는가 (= 메이저의 고점 조정 빌미 찾기 시그니처). 3축이 "단기 공포" 쪽으로 정렬되면 급락 = 잠재 기회로 해석.
- **시계열 추적**: 격상 이벤트는 스냅샷이 아니라 lifecycle(발생→확산→구조화/소멸)로 추적 — 동일 이벤트 재보도 시 이전 해석을 memory 로 주입해 판정 갱신 (메타발 급락: 06-23 발생 → 07-02 실현의 경과 추적이 표본).
- **배선**: `run_strategist` 가 `news_digest_md`(격상 이벤트+해석 포함)를 전달(compose 슬롯 기존) + track_a/track_b manifest `reads_analysts` 에 news_curator 추가.
- **게이트**: structural_trend/변곡으로 **해석된** 격상 이벤트만 `is_macro_inflection` 제3 트리거 + entry_posture 기여. ephemeral_shock 판정이면 advisory 유지(노이즈 매매 차단). → **N5 canon 개정**: "뉴스 tone 을 게이트로 쓰지 않는다" 원칙 유지 + "해석된 격상 이벤트는 예외" 단서.

### Tier 2 — 주도주 판별 (`LEADERSHIP-DISCERNMENT-001`, 미작성)
- S-Score supply_chain 축의 theme 매핑 중립 fallback 해소 + 뉴스 테마 클러스터(Tier 1 산출) × 섹터 RS × 수급(F-Score) 결합.
- 2-Stage 하이브리드: 결정론 후보(시총·거래대금 최상위 × 섹터RS × 신고가 근접) + LLM 이 "시장 중심축 종목인가" 정성 판별 + 캐싱.
- **변두리 고변동주 가드**: volume_bull 출신 & 시총/거래대금 중위권 종목은 Track A 자동 제외 또는 "트레이딩 영역" 라벨로 격리(Track B 전용). 후성 재발 방지의 구조적 방벽.
- **주도주 사이클 위치 게이지 (사용자 통찰 2026-07-05)**: "신고가가 100점이라면 지금 몇 점 위치인가" — 주도주 자격(who)과 별개로 **파동 내 위치(where)** 를 0~100 으로 상시 산출. 재료 = WAVE-ALPHA anchor 구조(A 바닥→B 정점→C 되돌림→current) + 52주 신고가 이격(기수집). 이 게이지가 있어야 "주도주 100→75 눌림 = 기회" vs "잡주 40 급등락 = 함정"이 갈리고, 폭락 때 매수의 기준선이 생긴다. 눈금은 백테스트로 검증.
- **패닉 역발상 진입 레인 (PANIC-REVERSAL, 07-03 SK하이닉스 사각의 해소)**: 현 위험 게이트는 폭락일 진입을 blanket 차단 — "주도주의 패닉 저점 = 기회" 전략의 자리가 없음(07-03 재구성: 시스템 wait vs 사용자 매수 적중). 요건 = Tier 1 해석("단기 공포" 판정) AND 주도주 자격 AND 사이클 위치 상위 AND **반전 확인 트리거**(장중 저점 대비 반등·거래량 결정론). blanket 예외를 뚫는 일이므로 **백테스트 edge 증명 후에만 활성**. 관련 부채: extension_score 가 ma20-아래 이격을 거의 감점 안 해(k_below 튜닝 백로그) 폭락 직후에도 9.5 로 나옴 — "건강한 눌림"과 "패닉 이탈"을 지표가 구분 못 하는 상태(2026-07-05 실측), 본 레인 설계 시 함께 해소.

### Tier 3 — 시장을 느끼고 액션으로 (`MARKET-POSTURE-ACTION-001`, 미작성)
- 전략가/계좌관리자 출력 스키마에 **포트폴리오 자세 액션** 필드(현금비중 목표·기존 보유 de-risk 권고) 신설 — 종목 단위를 넘는 첫 출력 경로. contract_version bump 필요.
- market_view(이벤트 격상 + 지표)를 종합 시장관 md 로 전략가에 주입(`market_view_md` 슬롯 기존).
- **시장 인사이트 수동 주입 채널** — 사용자 결정: **보류하되 인프라 방향만 설계로 명시**. 방향: 박종훈 canon 패턴 재사용, `knowledge/canon/market_macro/narrative/` 수동 드롭 + frontmatter 에 `stated_at`(발화 시점)·`horizon`(유효기간)·`stance` 메타 필수(오래된 인사이트가 현재 판단을 오염하지 않도록) → 격상 이벤트 해석과 동일 소비 경로(market_state_analyzer·전략가 read)로 합류. 신규 테이블 0, KNOWLEDGE-SYNC watchdog 색인 재사용.

### Tier 4 — 학습 루프 (EVOLUTION-001 과 합류, 별도 자식 없음)
- predictions 사후 채점 백필 + 일일 자동 채점 → 후성 사례 같은 실패가 회고분석가 PROPOSAL 로 흐르는 진화 루프.
- 백테스트 인프라로 Tier 1~3 각 개선의 edge 를 개선 전/후 비교 검증 (2026-06-20 백테스트 1차의 연장).

## 4. 사용자 결정 기록 (2026-07-05)

1. **이번 세션 = 진단 + 로드맵 문서만** (코드 0). 구현은 Tier 0 → Tier 1 순, implementation SPEC 은 착수 시 `/spec-interview` 로 확정.
2. **뉴스→매매 철학**: 격상 이벤트만 게이트 허용. 단 단순 격상이 아니라 **해석**(단기 공포 vs 변곡 vs 시계열 매매 포인트)이 본질이라는 조건 부가.
3. **수동 인사이트 주입**: 보류. 인프라 방향(canon narrative + 시점 메타)만 로드맵에 명시.

## 5. 재사용 영향도 (가드 #11)

**신규 테이블 0 목표.** 본 roadmap 전체가 기존 자산 위 배선·확장:
- compose.py `news_digest_md`·`market_view_md` 슬롯 (기존, 미배선) → 전달 인자만 추가.
- N2 시간축 3단 canon 축 (기존) → 해석 스테이지가 그대로 판별 축으로 사용.
- 2-Stage 하이브리드·캐싱(`llm_call_cache`)·비용원장(`llm_cost_ledger`) 패턴 (기존) → 해석 LLM 콜에 재사용.
- `news_source_items`·`news_digest_snapshot` (기존) → 격상 레인은 digest 구조 확장(컬럼/필드), 신규 테이블 아님.
- `universe_membership.list_type`·concept (기존) → 변두리주 가드의 판별 소스.
- `predictions` 채점 컬럼 (기존, 미가동) → Tier 4 는 백필+cron 이지 신규 스키마 아님.
- 예외 후보: Tier 3 포트폴리오 자세 액션은 contract 확장(StandardOutput/recommendation 필드 추가) — 착수 시 spec-interview 에서 재사용 영향도 재입증.

## 6. 완료 정의 (잠정)

메타발 급락 같은 격상 이벤트가 발생하면 시스템이 ① 당일 중심 이벤트로 식별·해석하고(단기 공포/변곡 판별) ② 그 해석이 entry_posture·변곡 트리거·전략가 프롬프트에 도달하며 ③ 방어 태세에서는 자동 buy 가 발행되지 않고 ④ 후성류 변두리주는 Track A 에 오르지 않으며 ⑤ 각 권고의 사후 성적이 채점되어 회고 루프로 흐른다 — 를 06-23~07-04 실데이터 리플레이와 forward 라이브로 증명.
