---
date: 2026-05-04
topic: 5-Layer M1·M2 원칙부 + R1 자산복리부 명명 + R2 박종훈 자료 추출
status: completed
plan_file: C:\Users\HOME\.claude\plans\jolly-wondering-stonebraker.md
---

# 2026-05-04 · 5-Layer 폴더 구조화 + 원칙부 자료 + 박종훈 자료 RAG 준비

## 배경

2026-05-03 모바일 토론에서 5-Layer 도메인 모델 합의 후 첫 PC 세션. 4 마일스톤 (M1 / M2 원칙부 / R1 / R2) 을 한 세션에 묶어 진행. 핵심 판단: **자료 ≠ 추론 품질, 자료 × 페르소나 × 피드백 = 곱셈**. canon (사용자 손글, 1~2 압축 framework) + reference (RAG retrieve) 혼합(옵션 D) 채택, RAG 우선순위 앞당김.

## 한 일

### M1 — Layer 1 폴더 구조화 (커밋 e23edbd)
- `knowledge/canon/` flat 4 파일 → 5 학습부 폴더 마이그레이션 (`principles/`, `mechanics/`, `long-term/`, `stock-analysis/`, `news/`)
- `core/knowledge/compose.py` — `load_shared_canon()` `glob` → `rglob` 재귀 + README 자동 제외 + 결정론적 정렬
- `docs/STRUCTURE.md` — "🧠 5-Layer 도메인 모델" 섹션 신설, 최상위 폴더 표에 `agents/` `knowledge/` 추가
- `docs/RUNTIME.md` — Knowledge Layer 섹션 5 학습부 구조 + 재귀 동작 명시
- `CLAUDE.md` — 프로젝트 개요 5-Layer 표 + `teams/` 잔재 제거
- `.gitignore` — `*.stackdump` 추가 (Windows bash 크래시 덤프)

### M2 원칙부 자료 채우기 (커밋 1f0d556)
사용자 사전 자료 3건 reference 보존 + LLM 친화 정제본 4 파일 신설:
- `knowledge/reference/principles/` — 원본 3 파일 (투자 7계명 / 투자 심법 / 거시적 트레이딩 기준) 한국어 파일명 그대로
- `knowledge/canon/principles/01-philosophy-7-commandments.md` — 불변 철학 7계명 (★ + 한 줄 + 왜 + 분석가 체크)
- `knowledge/canon/principles/02-trading-doctrine.md` — 5대 심법 (국면·수급·진입·청산·심리) + 매매 직전 3초 체크리스트
- `knowledge/canon/principles/03-market-regime-rules.md` — 상승/조정/하락장 + 종목·수급 루틴
- `knowledge/canon/principles/99-operational-safeguards.md` — 비중·손절·3교차 시스템 자동검증 룰 (기존 `investment-principles.md` 흡수 후 삭제)
- 정제 방침: 사용자 어조·표현 보존 ("골수까지 발라먹는다"), 구조만 LLM 친화 (헤더 일관, 표, 분석가 활용 가이드 섹션)
- canon: 1,601 → 12,260 chars (7.6배)

### R1 — long-term → wealth_compounding (커밋 37b640d)
"장기생존부" 명칭이 단순 장기투자와 혼동 → **자산복리부** 로 본질 표기:
- 폴더 rename: `knowledge/canon/long-term/` → `wealth_compounding/`
- 분석가 ID: `macro_analyst` → `wealth_strategist` (자산전략가)
- 5-Layer 표 갱신 (STRUCTURE.md / CLAUDE.md / RUNTIME.md)
- `knowledge/canon/wealth_compounding/README.md` 재작성 — 자산복리부 본질(10년+ 생존 + 복리) + canon framework / reference RAG 흐름
- `reference/principles/` 사용자 OneDrive 동기화로 prefix `01-`, `02-`, `03-` 반영, 정제본 frontmatter `source` 갱신

### R2 — sync_knowledge + 박종훈 자료 추출 (커밋 a200f9b)
- `config/knowledge_sources.yaml` — 학습부 → 외부 source(OneDrive) 매핑 (plugin)
- `scripts/sync_knowledge.py` — PDF→text 멱등 추출, slugify (한국어 보존·이모지 제거), 디자인 PDF 한국어 글자 사이 공백 휴리스틱 정규화, frontmatter 메타
- `justfile` — `just knowledge-sync <dept>` 명령 추가
- `knowledge/reference/wealth_compounding/` — 박종훈 29 PDF 추출:
  - `lectures/` 18 파일 453,850 chars
  - `materials/` 6 파일 61,826 chars
  - `ebooks/` 5 파일 25,951 chars (Vol 1 만 텍스트, Vol 2/3 4개는 0 chars — 이미지 PDF, OCR 백로그)
  - **총 541,627 chars (~540K tokens)** — Sonnet 4(200K)의 270%, Opus 4.7(1M)의 54%. RAG 필수임 정량 확인.

### 메모리 추가
- `project_park_jonghoon_dynamic.md` — 박종훈 강의 진행 중, ~10+ PDF 추가 예정. canon framework + reference sync 흐름.
- `feedback_no_hedging_on_judgment.md` — 평가·판단 질문엔 직설적 결론 먼저, "다만/그러나" 헷지 금지.

## 검증 결과

- ✅ pytest 60 passed (M1, M2, R1 직후 각각)
- ✅ `load_shared_canon()` 재귀 동작 — canon 12,269 chars (4 정제본 + 기존 placeholder 재귀 합산)
- ✅ sync_knowledge 멱등성 — 재실행 = 0 추출, 29 skip
- ✅ 한국어 정규화 효과 — 정규화 후 592K → 541K chars (-9%, 디자인 PDF 자동 감지)
- ✅ 4 커밋 모두 push 완료 (`a200f9b` 최신)

## 의도적으로 안 한 것

- **R3 RAG SPEC + Chroma ingest** — 다음 라운드 (M2.5 우선순위 ↑)
- **R4 wealth_compounding framework manifesto** — RAG 도입 후 1~2 정제본 인터뷰
- **Vol 2/3 OCR** — `ocrmypdf` + tesseract 의존성, 백로그 (Vol 1 만으로 framework 핵심 충분)
- **영문 글자 사이 공백 정규화** — RAG ingest 단계에서 처리 검토
- **M3 분석가 5명 페르소나 분화** — 자료 작업 후 진입 (analyst.md 1 → 5 split)
- **다른 학습부 (실전·종목분석·뉴스) M2 자료 채우기** — 별도 라운드
- **`core/registry.py` 등 dead code 청산** — 회귀 리스크, 별도 세션
- **미스테이지 `.claude/settings.json` modified, `rag_docs/`** — 이번 세션 무관, 보존

## 다음에 이어서 할 작업 (우선순위)

1. **R3 — RAG SPEC + Chroma ingest** (PC 2~3h) — `core/knowledge/{ingest,retrieve}.py` 가 반쯤 만들어져 있음. SPEC 작성 + Chroma 셋업 + reference/wealth_compounding/ 인덱싱 + retrieve 동작 검증. 자산복리부 자료 540K tokens 가 RAG 의존이므로 즉시 필요.
2. **R4 — wealth_compounding framework manifesto** (1~1.5h 인터뷰) — `canon/wealth_compounding/01-framework-manifesto.md` 1~2 파일만 사용자 손글로 압축 (박종훈 시각 + 사용자 시각). 디테일은 RAG 위임. 가변 자료 추가에 안 흔들림.
3. **M3 — 분석가 5명 페르소나 분화 + 매매일지 SPEC** (PC 2~3h) — `analyst.md` 1 → 5 persona.md split + 각 페르소나 본인 학습부 read binding. 동시에 매매일지 SPEC 첫 골격 (user_want_spec 의 "AI 매매일지 + 피드백" 영역). 자료에만 매몰되지 말고 페르소나·피드백 루프도 같은 무게로.

## 맥락 재진입 힌트

- **자산복리부 자료 운영 흐름**: OneDrive 박종훈_팬딩 → `just knowledge-sync wealth_compounding` (멱등) → `reference/wealth_compounding/` 갱신 → (Phase 3 도입 후) RAG 재인덱싱. 정제본은 framework 변동 시에만 손글 갱신.
- **canon vs reference 분리 원칙**: canon = LLM 매 호출 주입 (사용자 손글 압축, 변하지 않는 framework). reference = LLM 비주입, RAG 인덱싱 대상 (자동 sync, 디테일·시기 전망).
- **5-Layer 모델은 plugin 패턴**: 새 학습부/분석가/전략가 추가 = 폴더 + manifest 드롭만. 분화는 trigger 시.
- **NotebookLM/Gemini Gems 같은 SaaS 솔루션은 자동화 부적합** — 우리 시스템은 자료(canon+RAG) + 페르소나 + 메모리 + 시계열 누적 + 자동화 = 곱셈 효과.
- **단일 결정적 변수**: 사용자가 매매일지 + 자료 추가 흐름을 유지하느냐. 시스템 통제 외 영역.

## 커밋 상태

4 커밋 모두 push:
- `e23edbd` M1 5 학습부 폴더 + 5-Layer docs
- `1f0d556` M2 원칙부 정제본 + reference 원본
- `37b640d` R1 wealth_compounding rename
- `a200f9b` R2 sync_knowledge + 박종훈 24/29 추출

main 동기화 완료. wrap-up 커밋 1건 추가 예정.
