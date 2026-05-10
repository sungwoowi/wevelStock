# 개발 방법론 회고 — a to z 차기 프로젝트 가이드

> 작성: 2026-05-10
> 맥락: wevelStock 한 달 개발 (2026-04-19 ~ 2026-05-10) 에서 추출한 본인 방법론
> 목적: 차기 프로젝트에서 동일 노하우로 더 빠른 생산성 확보
> 위치: idea_memo (SDD 와 별개의 자산)

---

## 0. 핵심 통찰 7개 (먼저 보기)

1. **본질 한 문서 (user_want_spec)** = 매 세션 회귀 점이 있어야 디테일에 안 잠긴다
2. **단방향 의존 + 계약 기반 통신** = 1인 + AI agent 시스템에 거의 유일한 합리적 구조
3. **세션 연속성 (CLAUDE.md + RESUME + memory + 슬래시 커맨드)** = 컨텍스트 단절 비용 0 으로 만드는 인프라. 1주일 쉬어도 5분 안에 복귀
4. **SDD (Spec-Driven Development)** + **마일스톤 단위 쪼개기** = AI 페어 시대의 표준. 큰 추상은 자주 길을 잃음
5. **plugin 패턴 (manifest drop-in)** = 도메인 변경 비용을 코드 변경 X / 폴더 추가 O 로 격리
6. **멱등성 우선 (input_hash, ON CONFLICT REPLACE)** = LLM 비결정성을 봉합하는 가장 단순한 방법
7. **본인 호소 = 위험 신호 인지** = 번아웃 / 페이스 / 함정 회피의 첫 신호. 무시하면 6개월 안에 무너짐

---

## Phase 0 — 프로젝트 시작 전 (Day 0)

### 0.1 본질 한 문서 명시 — `docs/a_wanted/user_want_spec.md` 패턴
- **사용자 자신이 직접 작성한 한 문서**. AI 가 윤색한 spec 이 아님
- 거친 자유서술 OK. 정제된 명세보다 **본질이 살아있는 거친 글**이 좋음
- 매 세션 첫 5분에 다시 읽음 → 디테일 누적이 본질에서 벗어났는지 점검
- wevelStock 사례: L209 "agent 간에 회사처럼 일하는가 — 이게 안되면 의미 없다" 이 한 줄이 한 달의 모든 결정에 회귀점이 됨

### 0.2 도구 결정 — 언어 / AI 페어 / 패키지매니저
도메인이 결정 — 언어가 아니라:
- **AI/agent 도메인** = Python (anthropic-sdk / langchain / chromadb 모두 first-class)
- **풀스택 / 모바일** = TypeScript
- **시스템 / 인프라** = Go
- **거래 엔진 / 백테스팅** = Rust
- **엔터프라이즈 트랜잭션** = Kotlin/JVM

**도구 표준 (1인 AI 프로젝트)**:
- AI 페어: **Claude Code** (단연. Cursor / Copilot 보다 컨텍스트 보존 압도)
- Python: `uv` (pip / poetry 보다 10x)
- Node: `npm` (Windows 에서 pnpm EPERM)
- DB: SQLite (1인) → Postgres (사업화)
- 테스트: pytest + ruff + mypy strict
- 런타임: FastAPI + APScheduler + asyncio (단일 프로세스)

### 0.3 폴더 구조 결정 — 가장 결정적 안전 장치
- **프로젝트명을 import path 에 넣지 마라**. `from <project_name>.foo` X
- 도메인 sub-package 만 사용: `core/`, `server/`, `pipelines/`, `agents/` 등
- 결과: **프로젝트 이름 변경 비용 = 폴더명 + DB 파일명 + pyproject.toml + package.json (총 30줄 안)**
- wevelStock 사례: 한 달 후 "이름 바꿀 수 있나?" 물었을 때 "치명적 X" 였던 결정적 이유

---

## Phase 1 — Day 1~7: 인프라 셋업

### 1.1 CLAUDE.md (또는 등가 단일 컨텍스트 파일)
**구성 필수 7항목**:
1. 프로젝트 개요 (한 문단)
2. 도메인 모델 (불변 골격, 표 형태)
3. 최상위 폴더 구조 (한 줄씩 주석)
4. 작업 전 반드시 읽어야 할 문서 목록
5. 절대 원칙 (10개 안)
6. 운영 환경 / 도구
7. 통신 계약 / 핵심 인터페이스

**팁**: AI 페어는 매 세션 시작 시 이 파일 자동 로드. 여기 쓴 게 가장 강한 컨텍스트. CLAUDE.md 길이 200줄 안에서 핵심만.

### 1.2 docs/ 구조 — 문서 분리 원칙
```
docs/
├── a_wanted/     # 본질 — 사용자가 원하는 것 (불변)
├── b_plan/       # 설계 / 플랜 / 아키텍처 결정
├── c_worked/     # 세션 로그 (시간 캡슐. 절대 수정 X)
├── specs/        # SDD 의 SPEC (frontmatter + generates)
├── raw_docs/     # 외부 자료 원본
├── CLAUDE.md     # AI 컨텍스트 단일 출처
├── RESUME.md     # 항상 최신 상태판
├── STRUCTURE.md  # 폴더 규약 원천
├── WORKFLOW.md   # SDD 사이클
└── CONTRACTS.md  # 메시지 계약
```

핵심:
- **a/b/c 접두사** 로 ABC 정렬 + 의미 분리
- **c_worked = 시간 캡슐**. 그대로 보존. 회고 자산
- **idea_memo (별도)** = SDD 와 분리된 아이디어 백로그

### 1.3 슬래시 커맨드 셋업 (Claude Code)
- `/resume` — 본질 + 상태 + 마지막 로그 자동 읽기 → 플랜 모드 → 오늘 할 일 인터뷰
- `/wrap-up` — 세션 끝, c_worked 작성 + RESUME 갱신
- `/spec-interview` — SPEC 작성 5라운드 면담
- `/knowledge-sync` — (도메인 별) 외부 자료 → reference DB 멱등 sync

이 4개가 **세션 연속성의 인프라**. 이거 없으면 매 세션 컨텍스트 재구축에 30분~1시간 낭비.

### 1.4 Memory 시스템 활용 (Claude Code)
4 종류:
- `user_*` — 사용자 프로필 (역할, 선호, 경험)
- `feedback_*` — 실시간 누적 (correction + confirmation 둘 다)
- `project_*` — 프로젝트 상태 (변동 있는 것)
- `reference_*` — 외부 시스템 위치 (Linear, Slack, GitHub 등)

핵심: **MEMORY.md 인덱스 1줄씩**. 본문은 별도 파일. 자동 로드되는 건 인덱스만.

### 1.5 안전 장치 (Day 1 부터)
- `.env` + `.env.example` 분리 — 시크릿 절대 commit X
- pytest hook — `TESTING=1` 강제 (외부 API 호출 차단)
- pre-commit hook — ruff / mypy
- DB: ON CONFLICT REPLACE (멱등성)
- LLM provider fallback chain (vendor lock-in 회피)

---

## Phase 2 — Week 2~4: 본질 골격 구축

### 2.1 단방향 의존 모델 (가장 결정적)
**원칙**: 모듈 A → 모듈 B 는 OK, B → A 는 절대 X. 순환 import 발견 즉시 중단.

wevelStock 5-Layer 사례:
```
학습부 → 분석가 → 전략가 → 계좌관리자 → 출력
```
- 각 Layer 간 **DB 테이블** 통해서만 통신
- 직접 함수 호출 X
- 결과: 디버그 단순 / 캐시 가능 / 부분 교체 가능

이 원칙은 도메인 무관 적용:
- 웹앱: route → service → repository → DB (단방향)
- 데이터 파이프: source → transform → load (단방향)
- agent 시스템: producer → contract → consumer (단방향)

### 2.2 계약 기반 통신 (StandardOutput JSON 패턴)
모든 모듈 간 통신은 **structured JSON 계약**. 자유 텍스트 X.

```json
{
  "module_id": "...",
  "timestamp": "...",
  "verdict": "...",
  "confidence": 0-100,
  "reasons": ["..."],
  "data": {...},
  "contract_version": "1.0"
}
```

핵심:
- `contract_version` 필드 = 미래 호환성
- `reasons` 배열 = 디버그 + LLM 종합 가능
- DB 테이블 1개 = 모든 모듈 INSERT, 다른 모듈 SELECT

### 2.3 Plugin 패턴 (manifest drop-in)
**원칙**: 새 도메인 = 폴더 + manifest.yaml + persona.md 만 추가. 코드 0줄 수정.

wevelStock 사례:
```
agents/analysts/<analyst_id>/
├── manifest.yaml  # reads: [학습부], temperature, max_tokens
└── persona.md     # 시스템 프롬프트
```
- 등록은 `glob("agents/analysts/*/manifest.yaml")` 자동 발견
- 새 분석가 = 폴더 추가 + 서버 재시작 만으로

이 패턴은 도메인 무관:
- 웹앱: route plugin = `routes/<name>/{handler.py, manifest.yaml}`
- ETL: source plugin = `sources/<name>/{extractor.py, manifest.yaml}`
- 게임: AI plugin = `ai/<name>/{behavior.py, manifest.yaml}`

### 2.4 멱등성 우선 (Idempotency First)
모든 외부 호출 / 부수 효과는 멱등하게:
- `input_hash = sha256(input + context + version)` → 캐시 키
- DB INSERT = ON CONFLICT REPLACE
- 파일 쓰기 = 같은 입력 = 같은 출력
- LLM 호출 = `llm_call_cache` 테이블 참조

결과: **재실행 안전**. 크래시 후 재시작이 두렵지 않음.

### 2.5 1인 운영 = 단일 프로세스
- microservices 함정 회피
- Kubernetes 환상 회피
- FastAPI + APScheduler + asyncio = 1 프로세스에 다 담김
- 디버그 = 1 로그 + 1 SQLite 브라우저로 종결
- 사업화 + 다중 사용자 단계까지는 단일 프로세스가 정답

---

## Phase 3 — 매일 작업 사이클 (운영)

### 3.1 세션 시작 (5분)
1. `/resume` (또는 수동)
2. 본질 (user_want_spec) 5초 훑기
3. 상태 (RESUME) Top 3 확인
4. 마지막 로그 (c_worked 최신 1개) 훑기
5. **오늘 Top 1 결정** (마일스톤 1 슬롯)

### 3.2 SDD 사이클 (SPEC → 코드 → 테스트 → 도메인 문서)
1. **SPEC 먼저** — `docs/specs/<NAME>-001.md`
   - frontmatter: status / generates / depends_on / contract_version
   - 5라운드 면담으로 작성 (`/spec-interview`)
2. **코드** — SPEC 의 `generates` 경로에만
3. **테스트** — `tests/test_*.py` (TESTING=1, mock 강제)
4. **도메인 문서** — `scripts/generate_domain_doc.py` 자동 생성
5. **검증** — `scripts/validate.py` 통과

핵심: **SPEC 없이 코드 X**. 면담이 길어 보여도 결국 더 빠름. SPEC 면담 30분 = 디버그 3시간 절약.

### 3.3 마일스톤 단위 쪼개기
- 큰 작업 = 4~6 마일스톤 (M1~M6)
- 각 마일스톤 = **2~5 시간 안에 끝나는 단위**
- 마일스톤 끝 = 짧은 요약 + 사용자 확인
- **5명 일괄 X** — 1명 검증 → 패턴 안정 → 4명 복사

wevelStock 사례:
- M1: 폴더 구조화 (1h)
- M2: 첫 학습부 정제본 (2h)
- M3: 첫 분석가 가동 (3h)
- M4: 전략가 (대기)
- M5: 계좌관리자 (대기)

### 3.4 세션 끝 (5분)
- `/wrap-up`
- c_worked 로그 (이번 세션에 한 일 + 결정 + 다음 Top 3)
- RESUME 갱신 (현재 위치 + 다음 Top 1~3)
- git commit + push

**절대 X**: "다음 세션에 정리" 미루기. wrap-up 즉시. 안 하면 24시간 후 본인 기억 0.

---

## Phase 4 — 외부 비교 학습

### 4.1 비슷한 오픈소스 / SaaS 정밀 분석 (월 1회)
- 같은 도메인의 오픈소스 / 경쟁 SaaS 1개 골라 README + 핵심 docs 읽기
- 비교 매트릭스 작성:
  - 본인이 우월한 영역
  - 상대가 우월한 영역
  - 차용 가능 패턴 (가치 순)
  - 본인 마일스톤에 매핑

wevelStock 사례: prism-insight 비교에서 **거래 저널 self-improvement loop** 발견 → M5 다음 마일스톤으로 박힘

### 4.2 idea_memo (SDD 와 분리)
- 아이디어 / 외부 비교 / 막연한 구상 = idea_memo/
- SPEC 으로 굳히기 전 단계
- 차용 시점 도래 시 → docs/specs/ 로 승격
- **SDD 흐름과 별개**. SDD 는 "할 일", idea_memo 는 "할 수도 있는 일"

### 4.3 외부 비교 = 객관 측정자
- 본인이 잘 짠 줄 알았는데 외부가 더 좋은 패턴 = 차용
- 본인이 못 한 줄 알았는데 본인 게 더 우월 = 신뢰
- "혼자 갇히지 않기" 의 가장 강한 방법

---

## Phase 5 — 검증 + 회고

### 5.1 검증 마일스톤 분리
- 인프라 마일스톤 vs 검증 마일스톤 명시 분리
- 인프라만 깔고 검증 안 하면 → 영원히 미증명
- wevelStock 사례: 인프라 6개월 + 검증 0 → prism-insight 가 검증 6개월 + 인프라 동일 → 결과 차이 극단
- 처방: **인프라 2 마일스톤 = 검증 1 마일스톤** 비율 유지

### 5.2 자가 학습 루프 (Self-Improvement)
검증 데이터가 쌓이면 → AI 시스템이 그 데이터로 자기 갱신:
- A/B 테스트 (같은 입력 / 다른 prompt or 모델)
- 거래 저널 / 작업 저널 (결과 → 다음 호출 prompt 갱신)
- 백테스팅 인프라 (`as_of: datetime` 인자 통일)

이게 "AI 호출 시스템" 에서 "AI 학습 시스템" 으로 가는 변곡점.

### 5.3 회고 문서 (이런 것)
- 마일스톤 끝 / 단계 끝 / 1개월 단위 회고
- "무엇을 했고 / 무엇을 배웠고 / 무엇을 다시 안 할 것인가"
- 차기 프로젝트 자산

---

## 메타 노하우 (가장 중요)

### M.1 본인 호소 = 위험 신호 인지
**"머리 복잡하다", "한 달 힘들다", "디테일에 길 잃을까" 같은 호소** = 그냥 푸념이 아니라 **번아웃 / 페이스 / 방향 신호**.

처방:
- 일주일에 1일 코드 안 보기 (강제)
- 마일스톤 사이 휴식
- 호소 자체를 메모리에 저장 (feedback type)
- AI 페어가 호소 감지 시 본질 점검 자동 수행

### M.2 마이그레이션 함정 회피
**절대 X**:
- 큰 리팩토링 한 번에
- 언어 갈아타기 (도메인 라이브러리 우선)
- 미증명 인프라 + 화려한 UI
- 너무 일찍 microservices

**OK**:
- 마일스톤 사이 작은 청산 (1~2개씩)
- 검증 통과 후 부분 이행 (예: 거래 엔진만 Go)
- 본질 동작 후 운영툴 강화

### M.3 헷지 없는 직설 답변 강제
AI 페어에게 "다만/그러나" 헷지 금지 명시. 평가/판단 질문엔 직설 결론 먼저.

이유: 헷지된 답은 의사결정에 가치 0. "정답 같은데 자신 없음" 응답 받으면 본인이 다시 판단해야 함 → AI 페어 없는 것과 같음.

### M.4 페이스 보호 (생존 우선)
- 1인 프로젝트는 마라톤. 6개월 + 1년 + 2년 가야 결과
- 첫 한 달 페이스 = 6개월 페이스의 1/6 으로 잡기
- 본인 호소 = 페이스 신호. 무시 금지

### M.5 외부 비교 = 객관 측정자
- 본인 시스템이 좋은지 / 나쁜지 = 외부 비교 없이 모름
- 월 1회 같은 도메인 1개 정밀 분석 = 정신 건강 + 자산 양쪽
- "혼자 만들고 있다" 의 외로움도 비교가 답

---

## 도구 스택 권고 (1인 AI 프로젝트 기준)

| 영역 | 권고 | 대안 |
|---|---|---|
| AI 페어 | **Claude Code** | Cursor (Pro) |
| 언어 (AI 도메인) | Python | TypeScript |
| 패키지매니저 (Py) | uv | poetry |
| 패키지매니저 (Node) | npm | pnpm (POSIX만) |
| DB (1인) | SQLite + WAL | Postgres |
| DB (사업화) | Postgres | MySQL |
| 웹 백엔드 | FastAPI | Express |
| 스케줄러 | APScheduler | Celery |
| 비동기 | asyncio | trio |
| 테스트 | pytest | unittest |
| 린터 | ruff | flake8 |
| 타입 | mypy strict | pyright |
| 프론트 | Next.js | Vite + React |
| RAG | Chroma | Qdrant |
| 임베딩 (한국어) | BGE-m3 | E5-multilingual |
| LLM provider | Anthropic primary + Gemini fallback + claude_code subscription | OpenAI |
| 메시지 채널 | Telegram (1인) | Slack (팀) |
| 배포 (사업화) | Docker on VPS | k8s on EKS |

---

## 함정 모음 (절대 X)

1. **큰 리팩토링 한 번에** — 마일스톤 사이 1~2개씩 흘려보내기
2. **언어 갈아타기** — 도메인 라이브러리 우선. AI = Python 외 선택지 없음
3. **미증명 인프라 + 화려한 UI** — 본질 우선
4. **너무 일찍 microservices** — 1인 운영자 = 단일 프로세스
5. **"다음 세션에 정리" 미루기** — wrap-up 즉시
6. **사용자(자기) 호소 무시** — 페이스 신호. 휴식 강제
7. **SPEC 없이 코드** — 디버그 비용이 SPEC 면담 비용의 6배
8. **5명 일괄 분화** — 1명 검증 → 패턴 안정 → 복사
9. **검증 없는 인프라 누적** — 인프라 2 = 검증 1 비율
10. **외부 비교 안 하기** — 월 1회 정밀 분석 강제
11. **"코드는 거짓말 안 한다" 신뢰** — LLM 호출은 비결정. 멱등성 + 캐시로 봉합
12. **AI 페어에게 작업 통째 위임** — 의도 먼저 확인. 막연 위임은 본인 통제 상실
13. **헷지된 AI 답변 수용** — 직설 강제. 헷지된 답은 의사결정 가치 0

---

## 한 줄 요약

**본질 (user_want_spec) → 단방향 (의존+계약) → 멱등성 (input_hash) → 마일스톤 (2~5h 단위) → wrap-up (즉시) → 외부 비교 (월 1회) → 검증 마일스톤 (인프라 2 = 검증 1 비율) → 페이스 (주 1일 휴식)**.

이 8개가 wevelStock 한 달의 진짜 자산. 차기 프로젝트 시작 첫 주에 인프라로 깔면 = 동일 한 달에 본인이 만든 것의 1.5~2배 가능.

---

## 부록: wevelStock 에서 했지만 다음엔 다르게 할 것

### 일찍 했더라면 좋았던 것
- 검증 인프라 (백테스팅 `as_of` 통일) — 분석가 분화 직후 깔았어야
- 외부 비교 — 한 달 만에 prism-insight 알았는데, 첫 주에 알았더라면 거래 저널 패턴 더 일찍 차용
- mypy strict — 처음부터 켜두는 게 정답. 나중에 켜면 수백 줄 오류

### 안 했더라면 좋았던 것
- 일부 SPEC 의 과도한 면담 (5라운드 → 3라운드로 충분한 경우 다수)
- streaming SSE 도입 (검증 안 끝났는데 UX 먼저 — 페이스 잡아먹음)
- 너무 일찍 brief_close 설계 (M3 끝나기 전엔 빈 박스)

### 다른 프로젝트엔 처음부터 적용
- 첫 주 = CLAUDE.md + docs/ 구조 + 슬래시 커맨드 + memory + 본질 문서
- 둘째 주 = 단방향 모델 + 첫 마일스톤 (가장 작은 검증 가능 단위)
- 첫 달 끝 = 외부 비교 1회 + 회고 문서 1회
