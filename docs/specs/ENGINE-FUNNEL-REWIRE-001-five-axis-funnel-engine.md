---
spec_id: ENGINE-FUNNEL-REWIRE-001
title: 5축 깔때기 엔진 — 위원회→깔때기 재배선 + 동적 구조 사다리 (roadmap)
team: shared
type: roadmap
level: roadmap
status: draft
parent: PROJECT-NORTH-STAR-001
generates: []
children:
  - KNOWLEDGE-INTAKE-001        # P1: 지식 반입 동적화 — 자료 드롭→LLM 정제→승인→canon 반영 (미작성)
  - FUNNEL-TOPDOWN-001          # P3a: 탑다운 배선 — 섹터 신호→종목 압축 연결 + regime 슬롯 (미작성)
  - DEEP-DIVE-REPORT-001        # P3b: 압축 생존자 심층 리포트 — 위원회 YAML→임원식 종합 (미작성)
  - LENS-REGISTRY-001           # P4: 렌즈 레지스트리 — 판단 구조의 제한 선언형 데이터화 (미작성)
depends_on:
  - PROJECT-NORTH-STAR-001 (부모 — 마스터 로드맵)
  - MARKET-CONTEXT-BRAIN-001 (병행 트랙 — 관측→M2→Tier2 순서 존중, 본 SPEC 은 청사진이며 간섭하지 않음)
  - EVOLUTION-001 (P2 채점 루프 = 여기와 합류, 신규 SPEC 아님)
  - AUTO-SIGNAL-GENERATION-001 (압축기 현물 — watchlist→rank_candidates 컷)
  - ARCHITECTURE-HYBRID-EXECUTIVE-001 (P0 심층 판단자의 씨앗 — 채팅 임원 배선 2026-07-18 완료)
  - SCREEN-RS-EXTENSION-001 (prism #289 차용 트리거 보강 — P3a 에서 흡수 검토)
  - KNOWLEDGE-SYNC-001 (P1 이 그 위에 LLM 정제 스테이지를 올림)
  - ANALYST-PERSONAS-001 (페르소나 13 → 렌즈 섹션으로 접히는 대상)
---

# ENGINE-FUNNEL-REWIRE-001 — 5축 깔때기 엔진 (roadmap)

> **2026-07-18 제로베이스 사고 세션의 산출.** 사용자가 "분석가/전략가 구조가 없다 치고" 직관으로 그린 5축 모델(공간·시간·뉴스검색·실행·복기)이 원안(`docs/a_wanted/user_want_spec.md`의 수집→Advisor→실전매매→피드백/고도화)과 사실상 동일함을 확인 — **5축 = 초심.** 프로토타입(9분석가+2전략가)은 Advisor 한 축을 정교화하다 축 사이의 흐름(깔때기)을 잃은 것. 본 SPEC 은 재건축이 아니라 **재배선 청사진**이다.
>
> 같은 날 선행 작업: LLM 판단 구조 전면 감사(13 에이전트 워크플로우, 코드·프롬프트·DB 교차검증) + 채팅 임원 배선(P0) 완료. 사람용 요약 = `idea_memo/2026-07-18-five-axis-funnel-engine-refocus.md`.

## 1. 진단 요약 (2026-07-18 감사 — 팩트)

### 1.1 "함수자판기" 채팅의 원인 사슬 5

| # | 원인 | 증거 |
|---|---|---|
| ① | 최종 답변층 = "압축기" (자기 선언 원문 "자연어 답변 압축기", 결론 ≤3줄, flash-lite, max_tokens 800, 고정 3축 bullet, `📊 시장관` 결정론 prefix) | `core/intent/formatter.py:195-226,485,532` |
| ② | 통찰 경로(executive persona = "점수 합산 기계가 아니다", 5-layer chain, 시나리오 3, 수혜/피해 매트릭스, max_tokens 3500 — formatter 800 대비)가 **존재하는데 production 미배선** | `agents/executive/persona.md:15,51-59` + `core/executive/synthesize.py:11,230` + `webapp .../useChatStream.ts:53-57` → **P0 에서 해소** |
| ③ | 상쇄 배선: 상류 페르소나가 코드라벨 병기 강제(20회)·cited footer·hedging 금지(26회) → 하류가 3겹 장치로 다시 제거 | `agents/**/persona.md` ↔ `formatter.py:153-270` |
| ④ | 내용 단일음: 전체 이력 verdict = track_b 506/506 wait(100%)·track_a 462/480 wait(96%) (감사 시점 실측) + 채팅 산출 미저장(대화 연속성 0) | team_outputs 실측, `server/api/production_chat.py` INSERT 0 |
| ⑤ | 지식이 규칙표: canon 실질 10파일 60.9KB, 36 카테고리 중 27 빈 폴더, **3부서(market_macro·flow_analysis·trading_journal) md 0개** | `knowledge/canon/` 실측 |

반증 실물: 같은 모델의 장전 브리핑 내러티브는 유창("갭업 시 추격보다 관망하며 조정 시 주도 섹터 눌림목…") — **모델 능력이 아니라 경로 설계 문제.**

### 1.2 오버엔지니어링 판정

- **골격 무죄**: 지식부 9 / 분석가 9 / 전략가 2 구조 자체는 유지 가치 (계약·1,430 테스트·plugin 패턴).
- **유죄 목록**: 형식 강제 레이어(페르소나 텍스트 30~40%가 금지 목록) / 빈 canon 위 정교한 형식 / formatter↔executive 이중 종합 / `run_analyst`·`run_strategist` stream 준복제(~150줄, 시그니처 표류) / 죽은 배선(`core/strategist/track_selector.py` 전체, `areas.analyst/strategist` tier 선언 미소비, Gemini 하 Anthropic 캐싱 기계장치, crosscheck config) / 스테일 프롬프트(`config/analyst_subtasks.yaml:257` news_curator "NEWS-SOURCE-001 미구현" 거짓 선언).
- **중복 매트릭스**: 순환매 3중(시장상태·종목선정가·수급) / 유동성 3중 / 자금유입 3중 / 산업트렌드 3중 / 7계명 4중(판정·확인·적용·코드).

### 1.3 V1~V8 (사용자 요구 능력) 커버리지

V1 기술적 주도주 🟢 유일하게 깊음(WAVE-ALPHA 21명제+MA-ride+백테스트 edge) / V2 섹터 순환매 🔴 / V3 매크로·글로벌·IPO 달러수급 🔴('IPO' grep 0) / V4 선반영·버퍼 🟡(정량 임계만) / V5 이슈→수혜주 🔴(news_curator 가 스스로 금지, 받을 theme_play canon 0) / V6 외자·환율 🟡(종목 단위만) / V7 유동성 국면 🔴(데이터부터 없음) / V8 통찰 서술 🟠(있는데 잠김→P0 해소).

## 2. 목표 아키텍처 — 소프트 깔때기

```
[공간축×시간축 깔때기 — 코드]
  시장 게이트(regime·kill switch·유동성) → 섹터(자금 유입·순환매) → 종목(압축기) 
        ↓ 각 단계는 "잘라버림"이 아니라 [기본값+이유+잘린 것 요약] 발행
        ↓ LLM 이 게이트 기본값을 뒤집으면 deviation 플래그+사유를 출력에 기록
          (기존 `llm_deviation_reason` 패턴 확장 — P2 채점에서 "게이트 vs 오버라이드 누가 맞았나" 귀속)
[생존 3~5 종목]
        ↓
[심층 판단 LLM 1콜] — 전체 그림(게이트 판단·잘린 후보 요약 포함) + 단계별 canon 선별 주입
   · 다단 구조화 출력(시장 판단/섹터 판단/종목 판단 — 복기 귀속용) + 통찰 서사
   · 게이트를 사실 근거로 뒤집을 권한 (가드레일 있는 C 의 확장)
[예외 레인] — PANIC-REVERSAL 등 역방향 (MARKET-CONTEXT-BRAIN Tier 2 와 동일 항목)
[복기 LLM 1콜 — 판단자와 분리] — 채점·교훈·PROPOSAL
[마이크로 콜] — 뉴스 분류 등 fast tier (현행 유지, 월 ~$0.2)
```

### 2.1 확정 결단 (본 세션)

| ID | 결단 | 근거 |
|---|---|---|
| D1 | **하드 깔때기 기각, 소프트 깔때기 채택** — 게이트는 기본값·이유 발행, LLM 이 사실 근거로 뒤집기 가능 + 역방향 예외 레인 | 07-03 SK하이닉스: kill switch blanket 이 전 층 wait, 사용자 통찰(주도주 패닉=기회)은 시스템 밖에서만 적중. 하드 깔때기는 이 실패의 제도화 |
| D2 | **판단 LLM 은 1~2개 유지, 복기 LLM 은 반드시 분리** — 자기 채점 오염 방지. 콜은 안 나눠도 출력은 단계별 구조화(귀속) | 현재 실질 판단 콜 = 채팅(임원)+자동(전략가) 2개. 1개로 접을지는 **채점 데이터로 결정** (빅뱅 금지) |
| D3 | **규칙은 코드로, LLM 은 해석·예외·서사** — 프롬프트 깊이의 병명은 깊이가 아니라 지시 추종 희석 | 자산전략가 v1→v4 교훈(페르소나만으론 결정론 분기 불가) + 백테스트(결정론 스크리닝 edge 실증, LLM anchor 기여 0) |
| D4 | **위원회 의식 폐기** — "9명 각자 verdict 발행→취합" 패턴만 죽고, 페르소나 13 은 판단자·복기자의 프롬프트 섹션(렌즈)으로 접힘. 지식부 9 = 서재로 유지, 단계별 선별 주입 | 비용 95% = 모든 종목×양트랙 위원회. wait 단일음도 동근 |
| D5 | **동적 진화(구조 자가 개편)는 채점 루프(적합도 함수) + 사용자 승인 게이트 전제** — 무허가 자가 수정 금지, 반영 대상은 데이터 레이어(P4 레지스트리)만 | 채점 없는 진화 = 무작위 표류. LLM 자가 개편은 규칙 추가만 하는 비대화 경향 — 가지치기 압력 필수 |
| D6 | **압축기 신규 제작 금지 — 기존 재사용** (가드 #11): universe 큐레이션+거래량양봉+rank_candidates+트리거·MA-ride·백테스트 edge 가 프리즘 5단계 압축기와 이미 대등 이상 | §3 대응표. 빠진 건 부품이 아니라 배선(탑다운)과 출구(심층) |
| D7 | **다른 세션 로드맵과 비간섭** — MARKET-CONTEXT-BRAIN 의 관측→M2→Tier2 순서 존중. 본 SPEC 은 청사진·좌표계 제공만. 채점(P2)=Tier 4/EVOLUTION 합류, PANIC-REVERSAL·사이클 게이지=Tier 2 소속 유지 | 두 트랙은 내용(두뇌) vs 구조(엔진 배선)로 상보 |

## 3. 압축기 현황 — prism-insight 실측 대비 (2026-07-18 fetch)

prism 압축기 5단계(전부 결정론): ① 공통 필터(거래대금 100억+·시총 5000억+·등락률 20%↓) ② 6 트리거×상위10(거래량 급증 30%+·갭상승 1%+·시총 대비 자금유입·일중 3%+·마감강도 0.5+·거래량 증가 횡보) ③ 하이브리드 점수(복합 30%+산식 70%) ④ **탑다운**: LLM 매크로(regime·leading_sectors)로 풀 필터 + regime 별 슬롯(강세 2탑/1바텀·횡보 1/2·약세 0/3) ⑤ **최종 3종목** → 13 에이전트 심층 리포트. 비용 ~$310/월(OpenAI 235+Anthropic 11+Perplexity/Firecrawl 35+서버 30). 성과 모의 +244.63%(86건·승률 45.35%)·450+ 사용자. "트리거 승률 자동 반영"은 문서 확인 결과 **수동 재검토** — 자동 복기는 미구현(우리가 넘어설 지점).

| prism 단계 | wevelStock 대응물 | 상태 |
|---|---|---|
| ① 공통 필터 | `collectors/universe_curation.py` (잡주 floor 차등·정배열·컨셉 분류) | 🟢 더 정교 |
| ② 트리거 6×10 | 거래대금 상위 50 + `collectors/volume_bull.py` + trader 트리거 6 + 신고가·MA-ride | 🟢 대응물 존재 (마감강도·갭 등 일부 부재 — SCREEN-RS-EXTENSION-001 에서 흡수 검토) |
| ③ 하이브리드 점수 | `rank_candidates` 결정론 컷 (50→20→**5**, 커밋 0a23704) + 백테스트 실증 edge(이평정배열+RS — prism 에 없는 검증) | 🟢 우위 |
| ④ 탑다운 슬롯 | 강세섹터 ETF·sector_rs·rotation 방향 **계산은 됨** | 🔴 **종목 선별에 미배선** → P3a |
| ⑤ 출구: 심층 리포트 | 전략가 양트랙 YAML(3,000자 truncate 재료) → wait 단일음 | 🔴 **출구 오연결** → P3b |

stock-analyzer(참고 벤더 2): 카테고리별 이슈 해석 리포트가 강점(뉴스/검색축의 교본), 수급·파동 없음. prism 의 Perplexity/Firecrawl $35/월 = **능동 검색축의 실재 증거** (우리 공백).

## 4. 로드맵 — 사다리 (P0~P5)

### P0 — 채팅 임원 배선 ✅ (2026-07-18 완료)
`chat.executive_mode_default: true` (config, hot reload, 요청 명시가 우선) — `core/config/schema.py` ChatConfig + `server/api/production_chat.py` `_resolve_executive_mode` + `config/defaults.yaml`. 전체 1430 passed. 심층 판단자(§2)의 채팅쪽 첫 조각. 서버 재시작 필요.

### P1 — 지식 반입 동적화 (`KNOWLEDGE-INTAKE-001`, 미작성 — 원안 "교육팀"의 구현)
자료 드롭 → LLM 정제(canon 명제 추출·배치 제안·양질도 점수) → **사용자 승인 화면** → canon 반영 → 색인(KNOWLEDGE-SYNC 재사용). 반복되는 "자료 배선 세션 논의" 비용의 직접 해소.
- 첫 표본 = 사용자 보유 강의 문서 6종 = 신고가advanced·가격수급이론 2종(**저장소 미보유 신규**, V2/V3 프레임: 산업확산 vs 수급압축·100년 자금이동 4단계·체류도·밀집가격·종가회귀·360분봉) + 프랙탈파동 basic/advanced·로그차트 basic/advanced 4종(reference 원본 有, canon 정제본 0). 별도로 월가 멘토 시스템프롬프트는 지식이 아니라 어조 명세 — executive persona 어조 섹션에 병합.
- 반입 시점 주의: canon 투입은 분석가 프롬프트를 즉시 바꾸므로 MARKET-CONTEXT-BRAIN 관측 창과 겹치지 않게.

### P2 — 채점 루프 = 적합도 함수 (신규 SPEC 아님 — EVOLUTION-001 / MARKET-CONTEXT-BRAIN Tier 4 합류)
권고→결과→채점→track record. 구조 중립(위원회든 깔때기든 동일)이라 지금 만들면 재배선 후에도 그대로 사용. **P4·P5 의 전제조건.** 재배선(P3) 판단도 "어느 렌즈·단계가 기여하나"를 채점 데이터로 하게 됨.

### P3 — 깔때기 재배선
- **P3a 탑다운 배선** (`FUNNEL-TOPDOWN-001`): 이미 계산 중인 섹터 신호(강세섹터·sector_rs·rotation)를 `rank_candidates` 에 연결 + regime 별 슬롯(prism ④ 차용) + 시장 게이트 닫힘 시 하위 단계 스킵(**비용 절감 — 앞당김 가능**). 소프트 원칙(D1): 스킵 시에도 "무엇이 왜 잘렸나" 요약 발행.
- **P3b 심층 리포트 출구** (`DEEP-DIVE-REPORT-001`): 압축 생존 3~5종목에 위원회 YAML 대신 임원식 종합 리포트(다단 구조화 출력 — 시장/섹터/종목 판단 분리 + 서사). prism 리포트·`idea_memo/prism-trade-scenario-report-sample.md`(TRADE-PLAN-LIFECYCLE 목표 형태)가 참조 형식. 상쇄 배선 해체(코드라벨 병기 강제 제거·스테일 sub-task 정정)를 이때 페르소나 개정과 합본(M2 N5 개정과 같은 세션 권장 — 파일 충돌 회피).

### P4 — 렌즈 레지스트리 (`LENS-REGISTRY-001`, 제한 선언형)
렌즈(구 분석가)의 {이름, 깔때기 단계, canon 카테고리, 결정론 입력, 프롬프트 섹션 파일}을 선언 데이터로 — 기존 manifest 패턴의 확장이지 신규 플랫폼 아님. 감사에서 잡힌 "슬롯 1개 추가 = 4곳 수동 수정"(reads_* 플래그 1:1:1 배선) 부채도 해소. **범용 워크플로 엔진화 금지(inner platform 가드).**

### P5 — 동적 통폐합 (EVOLUTION-001 합류 — 회고분석가 PROPOSAL)
채점 데이터를 근거로 회고 LLM 이 "렌즈 X 통폐합/추가" PROPOSAL 을 **데이터로 발행** → 사용자 승인 → P4 레지스트리 반영 → 결과 보고. 원안 Layer 5 그대로. D5 가드 적용.

## 5. 가드 (하지 않는 것)

1. 전면 재건축 금지 — 부품(지식부·계산기·실행축·데스크·텔레그램/웹) 전부 유지, 배선만 교체.
2. 하드 깔때기 금지 (D1) / 무허가 LLM 자가 개편 금지 (D5) / inner platform 금지 (P4).
3. 판단 콜 빅뱅 통합 금지 — 2개 유지 후 채점 데이터로 결정 (D2).
4. 압축기·스크리너 신규 제작 금지 — 기존 확장 (D6, 가드 #11).
5. JSON 강제 콜 thinking=0 원칙은 유지하되, **판단·해석 콜(뉴스 이벤트 해석·장전 시나리오)에 thinking 캡이 걸려 있으면 품질 판정 전에 설정부터 재검** (관측 교란변수 — `collectors/news_source.py:1173`·`pipelines/market_briefing_pre/stages/analyze.py:227`).
6. 실행축(사이징·손절·심법 수치)은 코드 유지 — 가장 완성된 축, 건드리지 않음.

## 6. 미해결 / 후속 인터뷰

- **라이브 관측 체크 3건** (2026-07-18 DB 감사 발견 — MARKET-CONTEXT-BRAIN 관측 창에서 확인): ① `market_briefing_pre` scenario 파트 최근 2회 연속 빈 dict `{}` (07-13 이후 'general' 콜 미발생) ② 이중 발송(브리핑 3파트 03:30/05:30, 자동 요약 02:00/09:23) ③ 밴드 스킵 집계 착시(평가 20종 중 12종 스킵인데 요약엔 "관망 0" — 산출 있는데 없어 보임).
- 유동성 게이지(고객예탁금·신용융자·M2)·섹터별 외인 수급 = **데이터 수집부터 필요** (V7·V6) — 별도 인프라 SPEC 감. DATA-MAP 확인 후 기존 테이블 확장 우선.
- 능동 검색축(prism 의 Perplexity/Firecrawl 상당) = 신설 후보 — 비용·소스 선정 인터뷰 필요.
- 채팅 이력 영속(대화 연속성) = 소형 갭, P3b 즈음 함께.
- 판단 LLM 1개 통합 여부 = P2 채점 데이터 확보 후 결정.
