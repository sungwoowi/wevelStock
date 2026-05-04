# RESUME — 작업 재진입 상태판

> 이 파일은 **항상 최신 상태**로 유지됩니다. 세션을 새로 열 때 `/resume` 만 치면 이 파일을 읽고 플랜모드로 브리핑합니다.
>
> 갱신 주기: 의미 있는 작업 완료 후 `/wrap-up` 실행 시 자동 갱신.
> 수동 편집도 자유 — 구조만 지키면 됩니다.

---

## 📍 지금 어디 있나

**현재 위치**: **5-Layer M1+M2 원칙부+R1+R2 완료**. 5 학습부 폴더 (`principles/`, `mechanics/`, `wealth_compounding/`, `stock-analysis/`, `news/`) + 5-Layer docs 정식 등재 + 원칙부 정제본 4 파일 + reference 원본 3 보존 + 박종훈 자료 24/29 PDF 추출 (540K tokens, RAG 필수임 정량 확인) + sync_knowledge 멱등 흐름. **자산복리부(wealth_compounding) + 자산전략가(wealth_strategist) 명명 합의**. 옵션 D 채택 (canon 사용자 손글 framework + reference RAG). 다음 세션 = **R3 RAG SPEC + Chroma ingest** (코드 골격 반쯤 있음, 5-Layer 리팩터 + 한국어 임베딩, 2~2.5h).

**마지막 작업일**: 2026-05-04
**마지막 세션 로그**: [2026-05-04_m1-r2-canon-and-rag-prep.md](c_worked/2026-05-04_m1-r2-canon-and-rag-prep.md)
**Git**: `main` 4 커밋 push 완료 (`e23edbd` M1 / `1f0d556` M2 원칙부 / `37b640d` R1 wealth_compounding / `a200f9b` R2 sync_knowledge). wrap-up 커밋 1건 추가.

---

## 🎯 다음에 할 일 (Top 3)

우선순위 순. 마음에 드는 것 하나를 `/resume` 인터뷰에서 고르세요.

### 1. R3 — RAG SPEC + Chroma ingest (PC, 2~2.5h)
- **왜**: 자산복리부 자료 540K tokens (Sonnet 200K의 270%) → RAG 없이 LLM 활용 불가. R2 의 `reference/wealth_compounding/` 24 파일이 인덱싱 대기 중. `core/knowledge/{ingest,retrieve}.py` 코드 골격 반쯤 있지만 legacy team 구조. 5-Layer 에 맞게 리팩터 + 한국어 임베딩 결정 + 첫 인덱싱 + 검증.
- **범위**: SPEC `INFRA-RAG-001` 작성. ingest 입력 `team.path/knowledge/sources` → `knowledge/reference/<dept>/` 변경. 인덱스 저장 `team.path/knowledge/vector-index` → `data/chroma/<dept>/`. `get_team()` 의존 제거. 한국어 임베딩 결정 (BGE-m3 / OpenAI text-embedding-3-small 검토). frontmatter 메타 → Chroma metadata 보존. `compose.py` 의 `query_for_rag` 흐름 검증. `just knowledge-ingest <dept>` + `knowledge-browse <dept> "질의"` 명령 동작.
- **예상**: **2~2.5h PC 단발**. R3 끝나면 박종훈 자료 자동으로 LLM 추론에 들어감.

### 2. R4 — wealth_compounding framework manifesto (PC/모바일, 1~1.5h 인터뷰)
- **왜**: canon 압축본 1~2 파일이 박종훈 framework + 사용자 시각 큰 그림 잡아줌. 5대 심법·국면 룰처럼 분석가의 정체성 형성. RAG 단편 청크의 약점 보완. 자료 추가에 안 흔들림 (framework 자체는 잘 안 바뀜).
- **범위**: `canon/wealth_compounding/01-framework-manifesto.md` (~2K tokens) 사용자 손글 인터뷰. 박종훈의 통화·사이클·위기 framework + 사용자가 받아들인 핵심 1~2 페이지. 옵션으로 `02-survival-imperatives.md` (다년 생존·복리 룰) 추가. 코드 변경 0, markdown Q&A.
- **예상**: **1~1.5h 인터뷰**. R3 후가 자연 (RAG 동작하는 상태에서 framework 작성).

### 3. M3 — 분석가 5명 페르소나 분화 + 매매일지 SPEC (PC, 2~3h)
- **왜**: "자료 ≠ 추론 품질, 자료 × 페르소나 × 피드백 = 곱셈". 자료에만 매몰되지 말고 페르소나·피드백 루프도 같은 무게. 현재 `analyst.md` 1개 → 5 분석가 (원칙수호자·매매코치·자산전략가·종목분석가·뉴스큐레이터) 분화. 매매일지 SPEC 은 user_want_spec "AI 매매일지 + 피드백" 영역의 첫 골격.
- **범위**: `analyst.md` split → 5 persona.md (`agents/analysts/<id>/persona.md`) + 각 manifest 의 `reads` 매핑 + analyze stage 가 5번 호출 (Layer 3 strategist 합성은 M4 별도) + 매매일지 SPEC `BRIEFING-JOURNAL-001` 골격 (사용자 매매 결과 누적 → 분석가 자기 평가).
- **예상**: **2~3h PC 단발**. R3+R4 후 진입 자연.

---

## 🌱 이 프로젝트의 본질 (매 세션 반드시 참조)

- **[docs/a_wanted/user_want_spec.md](a_wanted/user_want_spec.md)** — **원 요구사항**. 이 프로젝트가 무엇을 위한 것인지 사용자가 직접 서술한 문서. 작업 방향이 본질에서 벗어나지 않도록 매 세션 초반에 반드시 읽고 내재화.

## 📂 활성 설계/계획 문서

- **[SPEC: BRIEFING-TIMEBASED-002](specs/BRIEFING-TIMEBASED-002-timebased-briefings.md)** — draft. 3종 브리핑 + RAG. **다음 세션 Top 1**
- **[SPEC: BRIEFING-ON-DEMAND-001](specs/BRIEFING-ON-DEMAND-001-briefings-on-demand.md)** — implementing. v1 구현 완료 (참조용)
- **[플랜: v1→v2 이행](../../../.claude/plans/nested-booping-dream.md)** — 2026-04-23 세션 최종 플랜
- **[파이프라인 재구성 플랜](b_plan/pipeline-restructure-plan.md)** — Phase 1~4 로드맵
- **[아키텍처 리뷰](b_plan/architecture-review-workflow-restructure.md)** — 하이브리드 6팀 3-Layer 결정

---

## 🧩 마지막 세션이 남긴 맥락 (바로 쓸 수 있도록)

### 완성된 자산
- `pipelines/market_briefing_pre/` (← morning_pre) — 8 stages, 실 LLM 실증 완료. notify stage `skip_notify` 존중
- `pipelines/market_briefing_now/` — 3 stages, KIS 22콜 + KRX 1콜 ~28s, LLM 없는 raw 발송
- `collectors/kr_{indices,sectors,leading_stocks,supply_demand,futures_supply_demand}.py` — 5주체 수급(KIS) + KOSPI200 선물 3주체(KRX)
- `connectors/{kis,krx}/client.py` — KIS 토큰자동·rate limit + KRX `getJsonData.cmd` POST helper
- `core/briefing/render.py` — 5주체 세로 나래비 + `[KOSPI200 선물]` 블록 + 백만원→억/조 helpers
- `server/api/briefings_on_demand.py` 4 엔드포인트 + `server/telegram/` 4 명령
- **5 학습부 폴더 + 5-Layer docs 등재** (M1) — `knowledge/canon/{principles,mechanics,wealth_compounding,stock-analysis,news}/`, `agents/` 위치 합의, STRUCTURE/RUNTIME/CLAUDE 5-Layer 표 정식 등재
- **`core/knowledge/compose.py`** — `load_shared_canon()` rglob 재귀 + README 자동 제외
- **`knowledge/canon/principles/` 정제본 4 파일** (M2) — `01-philosophy-7-commandments.md` + `02-trading-doctrine.md` + `03-market-regime-rules.md` + `99-operational-safeguards.md`. canon 12,269 chars
- **`knowledge/reference/principles/` 원본 3** — `01-투자 7계명.md` + `02-투자 심법.md` + `03-거시적 트레이딩 기준.md`
- **`knowledge/reference/wealth_compounding/` 박종훈 24/29** (R2) — lectures 18 + materials 6 + ebooks 1(Vol 1). 541,627 chars (~540K tokens)
- **`scripts/sync_knowledge.py` + `config/knowledge_sources.yaml`** — OneDrive PDF 멱등 추출 sync. slugify(한글 보존) + 디자인 PDF 한글 글자공백 휴리스틱 정규화. `just knowledge-sync <dept>`
- **pytest 60 passed** (M1, M2, R1 직후 회귀 검증)
- SPEC 2종: **BRIEFING-ON-DEMAND-001** + **BRIEFING-TIMEBASED-002** (Phase 1·2 완료, Phase 3 설계만)

### 미완 또는 의도적 공백
- **`canon/wealth_compounding/` 정제본 미작성** — R4 인터뷰 (1~2 framework manifesto)
- **RAG 인덱스 미생성** — R3 (Chroma ingest, `data/chroma/wealth_compounding/`)
- **`core/knowledge/{ingest,retrieve}.py` legacy team 구조** — R3 에서 5-Layer 리팩터
- **한국어 임베딩 모델 미결정** — R3 (BGE-m3 / OpenAI text-embedding-3-small 검토)
- **박종훈 Vol 2/3 OCR 미실행** (4 파일 0 chars, 이미지 PDF) — `ocrmypdf` + tesseract 도입 백로그. Vol 1 만으로 framework 핵심 충분
- **영문 글자 사이 공백 정규화** — R3 RAG ingest 단계 검토
- **다른 학습부 자료 (실전·종목분석·뉴스) 미채움** — 별도 세션, M3 후 또는 병행
- **분석가 5명 페르소나 분화 (analyst.md 1 → 5)** — M3 단계 + 매매일지 SPEC 첫 골격
- **전략가 3 / 계좌관리자 / 출력 채널 확장** — M4~M6, 한참 후
- **선물 수급 3주체 → 5주체 확장** — KRX MDCSTAT bld 캡쳐, 백로그
- **Phase 3 `market_briefing_close`** — 5-Layer M3 이후 자연 진입
- **dead code 청산** (`market_investor_summary`/`foreign_institution_top`/`core/registry.py`/`rollup.py`) — 회귀 리스크 큰 별도 세션
- **KOSPI200 선물 정확 가격** — 지수(2001) 대체. 선물옵션 API 별도
- `.claude/settings.json` modified / `rag_docs/` untracked — 사용자 확인 후 처리

### 꼭 알아둘 판단

**기초·불변 원칙**
- **파이프라인 구조 = "시간대별 독립 폴더"**. 공통 수집은 `collectors/` 로만 공유, 파이프라인 간 코드 import 금지
- **수동 관심(`watch_positions`)과 AI 시뮬(`sim_positions` + `sim_trades`) 스키마 분리**
- **텔레그램은 3분할 렌더링**. 연속성 문제 없음
- **`docs/a_wanted/user_want_spec.md` 매 세션 초반 필수 읽기**. "뇌 이식 + 자동 수집 + 연속 판단" 이 본질
- **`force` = "cache/snapshot 우회 + 새 실행"**: default False, `market_briefing_now` 09:00 fallback 도 force=true 면 우회
- **데이터 무결성 우선**: KIS API 의 응답 정렬·필드 의미는 항상 의심하고 직접 검증

**이번 세션에 굳힌 판단 (2026-05-04)**
- **자산복리부(`wealth_compounding`) + 자산전략가(`wealth_strategist`) 명명**: "장기생존부" 가 단순 장기투자와 혼동 → 본질 = 10년·20년+ 생존 + 복리 자산 증식. 거시 framework 도 이 학습부 안에 흡수 (별도 거시분석가 X)
- **canon vs reference 분리 (옵션 D 채택)**: canon = 사용자 손글 압축 framework (1~2 파일, ~2~5K tokens, 매 호출 주입). reference = PDF 추출본 (LLM 비주입, RAG 인덱싱 대상). 자료가 늘어도 정제본은 잘 안 바뀜 — 갱신은 reference sync 만
- **자료 ≠ 추론 품질**: 자료 × 페르소나 × 피드백 = 곱셈. 자료에만 매몰되지 말고 페르소나·피드백 루프도 같은 무게로
- **RAG 우선순위 ↑ (M2.5)**: 박종훈 자료 540K tokens (Sonnet 200K의 270%) 가 RAG 의존. 기존 Phase 3 후순위 → R3 즉시 진입
- **NotebookLM/Gemini Gems 부적합**: 자동화 시스템에는 페르소나·메모리·스케줄·매매일지 통제가 본질. 우리 시스템 = 5 차원 곱셈 → 시중 솔루션과 비교 불가
- **sync 멱등 흐름이 정답**: OneDrive PDF 추가 → `just knowledge-sync <dept>` 1회. 디자인 PDF 한글 글자 공백은 휴리스틱 자동 감지·정규화. 사용자 부담 X
- **박종훈 자료 동적 추가**: 강의 진행 중, ~10+ PDF 추가 예정. canon 정제본 미세 갱신 X, reference sync + RAG 재인덱싱이 정상 흐름
- **평가 질문엔 hedging 금지**: 시스템·자료·결정 평가 시 직설적 결론 먼저, "다만/그러나" 우려 깔지 말 것

**직전 세션 판단 (2026-05-03)**
- **5-Layer 도메인 모델 합의**: 학습부 5 / 분석가 5 (1:1 매핑) / 전략가 3 (단타·스윙·중장기) / 계좌관리자 1 (4 계좌 + 자산배분 흡수) / 출력 채널. plugin 패턴, 분화는 trigger 시
- **분산투자 = 계좌관리자 흡수** (Layer 3 X, Layer 4 모드)
- **manifest list 기반** (`analysts: [...]` / `reads: [...]`) 시작 → 미래 1:N 확장 무비용
- **비용 신경 X**: 추정 월 1~3만원 (Sonnet 4 + cache). 토큰·비용 hook 만 둠

**기초·불변 원칙**
- **파이프라인 구조 = "시간대별 독립 폴더"**, 공통 수집은 `collectors/` 로만 공유, 파이프라인 간 코드 import 금지
- **수동 관심(`watch_positions`) vs AI 시뮬(`sim_positions` + `sim_trades`) 스키마 분리**
- **텔레그램 3분할 렌더링**, 연속성 문제 없음
- **`docs/a_wanted/user_want_spec.md` 매 세션 초반 필수 읽기**. "뇌 이식 + 자동 수집 + 연속 판단" 이 본질
- **`force` = "cache/snapshot 우회 + 새 실행"**: default False, `market_briefing_now` 09:00 fallback 도 force=true 면 우회
- **데이터 무결성 우선**: KIS API 의 응답 정렬·필드 의미는 항상 의심하고 직접 검증
- **시장 전체 vs 종목 단위 KIS 투자자 API 구분**: `inquire-investor-time-by-market` (FHPTJ04030000, 시장 전체 5주체) 만 시장 합계 신뢰
- **KIS OpenAPI 미제공 데이터는 KRX backend** (`data.krx.co.kr/comm/bldAttendant/getJsonData.cmd` POST + Referer/UA, `bld` 파라미터)
- **수급 표시 5주체 세로 나래비**: 개인→외인→기관→금융투자→연기금. 약자 X. 선물도 `[KOSPI200 선물]` 통일
- **`market_briefing_now` 는 LLM 없이 raw 발송** (장중 빈번 호출, 비용·지연 회피)
- **briefing_parts retention = 시계열 누적 + 90일 cleanup cron** (별도 작은 SPEC 백로그)
- **정확한 용어**: VIX≠공포탐욕(CNN FGI), 투신(투자신탁)≠금융투자(증권사 자기매매), 영문 약어는 괄호 한국어 병기
- **서버 `--reload` 비신뢰**: 수정 시마다 수동 재시작

---

## 🔑 재진입 치트시트

```bash
# 환경
.venv/Scripts/python.exe -m pytest pipelines/morning_pre/tests/ -v

# 파이프라인 조회
.venv/Scripts/python.exe -c "from pipelines._registry import list_all_pipelines; print([p.id for p in list_all_pipelines()])"

# 서버 부팅 확인
.venv/Scripts/python.exe -c "from server.main import app; print(len(app.routes))"

# 수동 실행 (서버 떠 있을 때)
curl -X POST http://localhost:8000/api/pipelines/morning_pre/run
```

---

## 🧠 세션 재진입 절차

### 케이스 A — 이전 세션 **그대로** 이어가기 (컨텍스트 보존)

```bash
cd C:\Users\HOME\claude\wevelStock
claude -r        # 세션 목록에서 선택
# 또는
claude -c        # 가장 최근 세션 자동 재개
```

- 내용 파악이 안 되면 에디터에서 [docs/SESSIONS.md](SESSIONS.md) 표를 먼저 확인
- 대화 이력이 그대로 복원되므로 `/resume` 추가로 칠 필요 없음

### 케이스 B — 새 세션에서 **맥락만** 이어받기

```bash
cd C:\Users\HOME\claude\wevelStock
claude
# 프롬프트 뜨면:
/resume
```

1. Claude가 `a_wanted/user_want_spec.md` + 이 파일 + 최신 c_worked 를 읽고 **플랜모드 진입**
2. "지난 세션에 X 했고, 다음 후보는 A/B/C 입니다. 오늘 뭐 하실래요?" 인터뷰
3. 답변 반영 → 플랜 확정 → ExitPlanMode → 구현
4. 마무리할 때 `/wrap-up` — c_worked + SESSIONS.md + 이 파일 자동 갱신

### 판단 기준
- 같은 주제 계속 파고들기 → **케이스 A**
- 다른 주제로 전환 / 오래 쉬었음 → **케이스 B**
