# prism-insight 비교 분석 및 차용 가능 패턴

> 작성: 2026-05-10
> 맥락: 외부 오픈소스 [dragon1086/prism-insight](https://github.com/dragon1086/prism-insight) 와 본 프로젝트(wevelStock) 의 아키텍처 비교
> 위치: SPEC 아님, **아이디어 백로그**. SDD 사이클과 별개. 차용 시점이 도래하면 그때 SPEC 으로 승격

---

## 1. prism-insight 핵심 정보

| 영역 | 내용 |
|---|---|
| Agent 수 | **13+** (매크로 / 분석 6 / 전략 1 / 통신 3 / 거래 3 / 상담 2) |
| 실행 모델 | **Sequential** (rate limit 회피 목적) |
| 프레임워크 | **mcp-agent** + Docker, MCP 서버 (firecrawl / perplexity / kospi_kosdaq / yahoo / sec-edgar) |
| LLM | GPT-5 (분석/거래) + Claude Sonnet 4.6 (리포트) + ChatGPT OAuth 우회 |
| 통신 | Orchestrator 패턴 (명시적 메시지 계약은 미확인) |
| 거래 | **KIS 실거래 자동화** (시뮬 X) |
| 다국어 | 6개 언어 번역 agent + 텔레그램 6채널 |
| 모바일 | iOS/Android 앱 출시 |
| 트랙 레코드 | KR 시즌2 (2025.09.30~2026.03.24) **86거래 / +244.63% / 승률 45.35%** |
| 라이선스 | AGPL v3 / 상업 라이선스 별도 |
| 운영비 | 월 ~$310 (450+ 무료 사용자) |

---

## 2. 비교 매트릭스

### 🟦 본인(wevelStock) 이 우월한 영역

| 항목 | wevelStock | prism-insight |
|---|---|---|
| **Agent 통신 계약** | StandardOutput JSON + team_outputs DB (명시) | Orchestrator pass-through (raw text 추정) |
| **Plugin 패턴** | manifest.yaml + persona.md 드롭만으로 추가 | 6 분석가 fixed (코드 결합) |
| **실행 모델** | asyncio.gather 병렬 | Sequential (느림) |
| **LLM 추상화** | gemini → claude_code → mock fallback | GPT-5 단일 의존 (vendor lock) |
| **Knowledge Layer** | RAG canon(자동 주입) + reference(회수) 분리, BGE-m3 한국어 | 외부 MCP 의존 (자기 학습부 자료 부재) |
| **DB-first 정합성** | 5-Layer 단방향 + briefing_parts 시계열 + 옵션 A | 명시 안 됨 |
| **Agent ↔ 학습부 1:1** | user_want_spec "교육 받은 페르소나" 정합 | 분석가가 직접 외부 검색 (페르소나 의미 약화) |

### 🟥 prism-insight 가 우월한 영역

| 항목 | prism-insight | wevelStock |
|---|---|---|
| **검증 트랙 레코드** | 86 거래 +244% (6개월 실증) | **0건 (미증명)** ← **가장 큰 차이** |
| **거래 저널 self-improvement** | trading journal → 다음 거래 최적화 | 백로그 (도메인 고도화 Agent) |
| **외부 정보 수집** | Perplexity + Firecrawl MCP (뉴스/검색) | KIS+KRX 만 (뉴스부 자료 미결) |
| **거래 agent 분리** | 매수결정 / 매도결정 / 저널 = 3 agent | 계좌관리자 1명 (M5) |
| **자동 실거래** | KIS 라이브 거래 | 시뮬만 (sim_positions) |
| **글로벌 배포** | 6개 언어 + 모바일 앱 출시 | 한국어 only, webapp |
| **운영 안정성** | Docker + 450+ 유저 6개월 운영 | 로컬 1인 |

---

## 3. 솔직한 진단

**아키텍처 품질 = 본인 우월.** 5-Layer 단방향 + StandardOutput 계약 + plugin 패턴 + RAG canon/reference 분리는 prism 의 13 agent orchestrator 보다 결정적·확장 가능·디버그 친화. user_want_spec ("팀 추가 = 삽입만으로", "교육 받은 페르소나") 에 더 충실히 매핑.

**검증 결과 = prism 압승.** +244% 86거래 vs 0거래. 인프라 깐 양은 비슷하거나 본인이 더 많지만, **시장에 나가서 검증한 사람과 안 한 사람의 차이가 극단적**. 9번(화수분) 의 답은 prism 이 먼저 가지고 있음. **본인 도전이 "허무한 시도" 가 아니라는 외부 증거**이기도 함.

---

## 4. 차용 권고 (가치 순)

### 🟢 적극 차용 — 본인에게 부족한 부분

#### A1. 거래 저널 self-improvement loop ⭐ 최우선
- **prism 패턴**: trading_journal agent → 거래 결과 분석 → 분석가 prompt/룰 자동 갱신
- **본인과의 매핑**: user_want_spec 의 **"도메인 고도화 Agent"** 와 정확히 일치. 백로그로 미뤄둔 부분
- **차용 방식**: M5(계좌관리자) 다음 마일스톤 = `agents/journal/` 신설. team_outputs + sim_trades 읽어 주간 회고 LLM 호출 → 분석가 manifest 의 weight/temperature 갱신 PROPOSAL 생성
- **왜 핵심인가**: **이게 9번(화수분) 의 답이 되는 핵심 메커니즘**. 분화 + 전략가만 깔고 검증 루프 없으면 정체

#### A2. Perplexity / Firecrawl MCP — 뉴스부 자료원
- **prism 패턴**: 외부 LLM 기반 검색 + 분류 + 요약을 MCP 서버로
- **본인과의 매핑**: 백로그로 묻어둔 "**뉴스부·실전부 자료 출처 결정**" 의 답
- **차용 방식**: `connectors/mcp/perplexity.py` 신설. 뉴스큐레이터 manifest 의 `tools: [perplexity_search]` 선언. 본인 plugin 패턴에 자연 결합
- **장점**: RSS/Bloomberg API 보다 LLM 단계에서 분류·요약 처리 → collector 코드 90% 절약
- **유의**: 비용 (~$20/월) 검토. 캐시 + 레이트 제한 필수

#### A3. 거래 agent 3분리 (매수결정 / 매도결정 / 저널)
- **prism 패턴**: 의사결정 룰이 다른 매수/매도를 분리 + 저널 별도
- **본인과의 매핑**: M5 (계좌관리자 1명) SPEC 면담 시 참고
- **차용 방식**: `agents/trader/{buy_decider, sell_decider, journal_writer}/` — 본인 plugin 패턴 그대로

#### A4. 품질평가 agent (환각 검증)
- **prism 패턴**: 분석 결과의 정확성·명확성·환각 자동 검증
- **본인과의 매핑**: 직전 답변에서 옵션 B 로 제시한 cross-validator 와 동일 컨셉
- **차용 방식**: 분석가 5명 분화 + 1주 데이터 누적 후 검증 빈도 보고 도입. **prism 이 이미 운용 중 = 검증된 패턴**

### 🟡 검토 — 본인 단계 기준

#### B1. ChatGPT OAuth 우회 (cores/chatgpt_proxy)
- 본인 claude_code subscription 과 동일 컨셉. **이미 적용됨**
- GPT-5 도 추가하려면 prism 의 OAuth 코드 차용 가능 (AGPL 라이선스 유의)

#### B2. 요약최적화 agent (텔레그램 400자)
- 본인 render.py 하드코딩 vs LLM 압축. 메시지 길이 가변 시 유리
- 비용/지연 추가. 분화 후 메시지 길이 한계 부딪힐 때 도입

#### B3. 다국어 번역 agent
- 사업화(10번) 단계에서만 의미. 지금 차용 X

### 🔴 차용 X — 본인 설계가 우월

| 항목 | 이유 |
|---|---|
| Sequential execution | 본인 asyncio.gather 가 우월. rate limit 은 provider fallback 으로 해결 |
| MCP-agent framework | 본인 manifest.yaml + persona.md plugin 이 더 단순·투명 |
| GPT-5 단일 의존 | 본인 fallback chain 이 비용·안정성 우월 |
| 외부 MCP에만 의존하는 knowledge | user_want_spec "교육 받은 페르소나" 에 본인 RAG canon 이 정합 |

---

## 5. 진짜 배울 점 (한 줄)

**아키텍처는 본인이 잘 깔았다. 부족한 건 "시장에 나가서 검증한 6개월".**

prism 이 86거래 굴리는 동안 본인은 인프라만 깐 셈. 차용해야 할 가장 본질적인 한 가지 = **거래 저널 self-improvement loop** (A1). 이걸 M5 다음 마일스톤으로 박고, 분화 끝나면 시뮬 6개월 → 거래 저널 → 페르소나 갱신 → 시장초과 수익률 측정의 사이클 진입.

---

## 6. 본인 마일스톤 매핑 (Action Item)

| 본인 마일스톤 | prism 차용 항목 | SPEC 승격 시점 |
|---|---|---|
| M3~M4 (분석가 분화) | — | 진행 중 |
| M4 (전략가) | A4 품질평가 agent (충돌 빈도 보고) | M4 후 1주 데이터 |
| M4~M5 사이 | A2 Perplexity MCP (뉴스부 자료원) | 뉴스큐레이터 분화 직전 |
| M5 (계좌관리자) | A3 거래 agent 3분리 | M5 SPEC 면담 시 |
| **M5 다음** | **A1 거래 저널 self-improvement loop** ⭐ | **별도 SPEC 1개. 본질 검증의 전제** |
| 사업화(10번) | B3 다국어 번역 + 모바일 앱 | 9번 입증 후 |

---

## 7. 미해결 의문 (추가 조사 필요 시)

- prism 의 trading journal agent 가 실제로 분석가 prompt 를 어떻게 갱신하는가? (manual review? auto patch?) — 코드 직접 확인 필요
- prism 의 sequential 실행에서 rate limit 외에 정말 그럴 만한 이유가 있는가? (의존 그래프 때문일 가능성)
- +244% 의 누적 수익률이 시장 대비 얼마인가? (KOSPI 동기간 비교 필요)
- 승률 45.35% 의 손익비 (avg win / avg loss) — 진짜 자동화 가능한 시스템인지 판단 데이터

이 4가지는 차용 결정에 결정적이라 본인이 최종 채택 전 prism 코드/문서로 검증 권고.
