# 구조 재편: "팀 기반" → "파이프라인 + Knowledge 중심"

---

## 사용자 요구사항 (불변)

### 본질
나는 투자 지식은 있지만, **판단 속도, 자료 수집력, 감정 통제, 실전 매매 실행력**이 부족하다.
이 시스템은 **내 두뇌를 AI에 이식**하여, 내 지식으로 감정 없이 빠르게 판단하는 어드바이저를 만드는 것이다.

### 핵심 기능 요구
1. **두뇌 이식 (Knowledge Injection)**: 내가 가진 투자 지식(매크로 관점, 차트 해석법, 섹터 인사이트, 매매 원칙, 실패 교훈)을 MD/PDF/이미지로 주입하면, AI가 **내 관점에서** 판단한다.
2. **시장 데이터 자동 수집**: 매일 시세, 환율, 금리, ETF, 뉴스, 거래대금 등을 자동으로 모아준다.
3. **연속적 판단**: AI가 매일 컨텍스트를 휘발하지 않고, 어제의 판단을 기억하며 오늘 이어서 판단한다. 시장의 흐름을 읽는 연속성이 핵심.
4. **실전 매매 어드바이저**: 단기/장기 관점 분리, 분할매수/매도 전략, 차트 지지/저항 판단, 버블/바닥 시그널 등 구체적 매매 가이드.
5. **적중률 기반 고도화**: 판단 결과를 추적하고, 맞았는지 틀렸는지 채점하여 시스템을 지속 개선한다. 시장 수익률을 이기는 것이 목표.
6. **안정적 자동 운용**: 서버 띄워놓으면 스케줄대로 돌아가고, 텔레그램으로 알림 받는다. 수동 트리거도 가능.

### 꿈 (향후)
- 계정별 커스텀: 각 사용자가 자신만의 페르소나/지식을 주입하여 개인화된 어드바이저를 갖는다.
- 외부 오픈: 페르소나 부여 기능 + 투자 적중률이 차별점. 수익화는 광고.

### 시장에 대한 관점
- 시장은 조울증 환자다. 이에 대한 판단을 지속적으로 내려줄 수 있어야 한다.
- "지금 매수할까?" 물으면 → 단기/장기 분리 답변, 원칙/계좌관리 기반 비중 제안, 차트 기술적 판단까지 종합적으로.

---

## Context (구현 방향)
현재 `teams/` 중심의 도메인팀 구조를 **파이프라인 중심**으로 재편한다.
핵심 동기: 사용자의 투자 지식을 AI에 이식하고, 그 지식으로 감정 없이 빠르게 판단하는 시스템.
`core/` 인프라는 거의 그대로 재활용. `teams/` → `pipelines/` + `knowledge/` + `checkers/`로 교체.

---

## 새 폴더 구조

```
wevelStock/
├── knowledge/                    # 🧠 사용자의 두뇌 (핵심 자산)
│   ├── canon/                    #   항상 주입되는 핵심 지식 (system prompt)
│   │   ├── investment-principles.md   # 투자 7계명 + 매매 원칙
│   │   ├── macro-framework.md         # 매크로 경제 관점/프레임워크
│   │   ├── sector-insights.md         # 섹터별 분석 관점
│   │   └── failure-lessons.md         # 과거 실패 교훈
│   ├── sources/                  #   RAG 대상 원본 자료 (PDF, MD, 이미지)
│   │   ├── charts/
│   │   ├── macro/
│   │   ├── sectors/
│   │   └── journals/
│   └── vector-index/             #   Chroma DB (gitignore)
│
├── pipelines/                    # 🔄 실행 파이프라인 (teams/ 대체)
│   ├── _base.py                  #   Stage, StageContext, StageResult, PipelineRunner
│   ├── _registry.py              #   파이프라인 자동 탐색
│   │
│   ├── morning_briefing/         #   파이프라인 1: 아침 브리핑 (MVP)
│   │   ├── manifest.yaml
│   │   ├── stages/
│   │   │   ├── collect_market.py #     시세/환율/금리/지수 수집
│   │   │   ├── collect_news.py   #     뉴스/시황 수집 + LLM 분류
│   │   │   ├── check_principles.py #   7계명 체크
│   │   │   ├── analyze.py        #     LLM 종합 분석 (두뇌 이식 적용)
│   │   │   └── notify.py         #     텔레그램 발송
│   │   ├── prompts/
│   │   │   ├── analyst.md        #     이 파이프라인의 페르소나
│   │   │   └── briefing.md       #     분석 요청 프롬프트 템플릿
│   │   └── tests/
│   │
│   ├── watchlist_scan/           #   파이프라인 2: 관심종목/섹터 스캔
│   │   ├── manifest.yaml
│   │   ├── stages/
│   │   │   ├── scan_sectors.py   #     강세 ETF 스캔
│   │   │   ├── scan_volume.py    #     거래대금 상위 종목
│   │   │   ├── analyze.py        #     종목별 LLM 판단
│   │   │   └── notify.py
│   │   ├── prompts/
│   │   └── tests/
│   │
│   └── weekly_review/            #   파이프라인 3: 주간 성적표 + 학습
│       ├── manifest.yaml
│       ├── stages/
│       │   ├── gather_week.py
│       │   ├── score_predictions.py  # 적중률 채점
│       │   ├── synthesize.py         # LLM 복기
│       │   └── notify.py
│       ├── prompts/
│       └── tests/
│
├── checkers/                     # ✅ 순수 함수 라이브러리 (principles에서 추출)
│   ├── principles.py             #   7계명 통합 체커
│   └── commandments/             #   개별 계명 구현체 (기존 코드 이동)
│
├── core/                         # 🧱 공유 인프라 (거의 UNCHANGED)
│   ├── config/
│   ├── contracts/                #   + PipelineManifest, StageResult 추가
│   ├── db/                       #   + predictions 테이블 추가
│   ├── knowledge/                #   compose.py에 load_shared_canon() 추가
│   ├── llm/
│   ├── memory/
│   ├── notification/
│   ├── outputs.py
│   ├── registry.py               #   파이프라인 스캔으로 확장
│   └── scheduler/
│
├── server/                       # 🖥️ FastAPI (파이프라인 API로 전환)
│   ├── main.py
│   ├── api/
│   │   ├── pipelines.py          #   GET/POST /api/pipelines/*
│   │   ├── knowledge.py          #   GET/POST knowledge 관리
│   │   ├── predictions.py        #   적중률 조회
│   │   ├── config.py
│   │   └── notifications.py
│   └── schedulers/               #   파이프라인 manifest에서 스케줄 등록
│
├── webapp/                       # 🌐 Next.js (후순위, 나중에 개편)
├── config/
├── data/
├── scripts/
└── docs/
```

---

## 파이프라인 실행 모델

### manifest.yaml 예시 (morning_briefing)
```yaml
id: morning_briefing
name: "아침 시황 브리핑"
schedule:
  - trigger: cron
    expr: "30 8 * * 1-5"
    timezone: Asia/Seoul

knowledge:
  shared_canon: true        # knowledge/canon/*.md 주입
  rag_enabled: true         # knowledge/sources/ RAG 활성화

stages:
  - id: collect_market
    module: stages.collect_market
    type: collect
    timeout_sec: 30

  - id: collect_news
    module: stages.collect_news
    type: collect
    parallel_with: collect_market

  - id: check_principles
    module: stages.check_principles
    type: check
    depends_on: [collect_market]

  - id: analyze
    module: stages.analyze
    type: analyze
    runtime: llm
    depends_on: [collect_market, collect_news, check_principles]
    memory:
      context_id: morning_briefing
      budget_tokens: 4000

  - id: notify
    module: stages.notify
    type: act
    depends_on: [analyze]
```

### 실행 흐름
```
PipelineRunner.run("morning_briefing")
  │
  ├─ Wave 1 (병렬): collect_market + collect_news
  ├─ Wave 2: check_principles (Wave 1 의존)
  ├─ Wave 3: analyze (LLM 호출, 모든 이전 결과 + 지식 + 메모리 주입)
  └─ Wave 4: notify (텔레그램 발송)
```

### Stage 추상 클래스
```python
class Stage(ABC):
    stage_id: str
    stage_type: str  # collect | check | analyze | act

    @abstractmethod
    async def run(self, ctx: StageContext) -> StageResult: ...

class StageContext:
    run_id: str
    pipeline_id: str
    date: str
    data: dict[str, Any]              # 이전 스테이지들의 결과 누적
    knowledge_bundle: SystemPromptBundle | None
    config: RuntimeConfig

class StageResult:
    stage_id: str
    status: str       # ok | warning | error
    data: dict        # 이 스테이지의 출력
    verdict: str | None
    confidence: int | None
    reasons: list[str]
```

---

## Knowledge 아키텍처 (두뇌 이식)

### 현재 → 변경
- **현재**: 팀별 `knowledge/compiled.md` + 팀별 `persona.md` (흩어져 있음)
- **변경**: 공유 `knowledge/canon/*.md` + 파이프라인별 `prompts/analyst.md`

### LLM 호출 시 system prompt 조립
```
[1] 공유 Canon (knowledge/canon/*.md)          ← 항상 주입, 캐시됨
[2] 파이프라인 페르소나 (prompts/analyst.md)     ← 파이프라인별 역할
[3] 메모리 컨텍스트 (최근 14일 + 롤업)          ← 연속성, 캐시됨
[4] RAG 검색 결과 (knowledge/sources/)          ← 필요시
[5] 응답 규칙 (JSON 포맷 등)                    ← 고정
```

### core/knowledge/compose.py 수정
- `load_shared_canon()` 함수 추가: `knowledge/canon/*.md` 전체 로드
- `build_system_prompt()` 확장: `team_id` 대신 `context_id` + `persona_path` 지원
- 기존 팀 방식도 하위 호환 유지

---

## 메모리 연속성

**변경 없음.** 기존 3-tier 메모리가 그대로 동작:
- `team_memory` 테이블의 `team_id` 컬럼에 `"morning_briefing"` 문자열 사용
- 14일 최근 기록 + 주간/월간 롤업이 매 분석 시 system prompt에 주입
- "어제 코스피 하락 판단했고, 오늘도 이어지는지 확인" → 자연스럽게 연속

---

## 적중률 추적 (predictions 테이블)

```sql
CREATE TABLE IF NOT EXISTS predictions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id     TEXT NOT NULL,
    run_id          TEXT NOT NULL,
    date_predicted  TEXT NOT NULL,
    target_date     TEXT,
    ticker          TEXT,
    prediction_type TEXT NOT NULL,    -- direction | level | action
    prediction      TEXT NOT NULL,    -- "up" | "support_2600" | "buy_dca"
    confidence      INTEGER,
    actual_outcome  TEXT,             -- 나중에 채움
    score           REAL,            -- 0.0~1.0, 나중에 채움
    scored_at       TEXT,
    metadata_json   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

`weekly_review` 파이프라인의 `score_predictions` 스테이지가 주기적으로 채점.

---

## 기존 코드 마이그레이션

| 현재 위치 | → 새 위치 | 방법 |
|-----------|----------|------|
| `teams/principles/src/commandments/*` | `checkers/commandments/*` | 파일 이동 |
| `teams/principles/src/agent.py` | `checkers/principles.py` | 순수 함수로 리팩터 |
| `teams/daily_briefing/src/agent.py` | `pipelines/morning_briefing/stages/analyze.py` | 분해 |
| `teams/daily_briefing/persona.md` | `pipelines/morning_briefing/prompts/analyst.md` | 이동 |
| `teams/daily_briefing/knowledge/compiled.md` | `knowledge/canon/` 으로 분리 | 내용 분리 |
| `teams/orchestrator/src/runner.py` | `pipelines/_base.py` PipelineRunner | topological sort 로직 재활용 |
| `core/registry.py` | 확장 | `list_all_pipelines()` 추가 |
| `core/knowledge/compose.py` | 확장 | `load_shared_canon()` 추가 |
| `server/schedulers/loader.py` | 수정 | 파이프라인 manifest 스캔으로 전환 |
| `server/api/teams.py` | `server/api/pipelines.py` | 새로 작성 |

---

## 구현 순서

### Phase 1: 뼈대 (1-2일)
1. `pipelines/_base.py` 작성 (Stage, StageContext, StageResult, PipelineRunner)
2. `pipelines/_registry.py` 작성 (manifest.yaml 스캔)
3. `checkers/` 디렉토리 생성, principles 코드 이동
4. `knowledge/canon/` 디렉토리 생성, 초기 MD 파일 배치
5. `core/knowledge/compose.py`에 `load_shared_canon()` 추가
6. `core/registry.py` 확장 (파이프라인 지원)

### Phase 2: morning_briefing 파이프라인 (2-3일)
1. `pipelines/morning_briefing/manifest.yaml` 작성
2. 5개 스테이지 구현 (collect_market, collect_news, check_principles, analyze, notify)
3. analyze 스테이지: `teams/daily_briefing/src/agent.py` 로직 분해해서 이식
4. `server/api/pipelines.py` 엔드포인트 작성
5. `server/schedulers/loader.py` 파이프라인 스케줄 등록
6. 테스트: `POST /api/pipelines/morning_briefing/run` → 텔레그램 수신 확인

### Phase 3: Knowledge 고도화 (1일)
1. 사용자 투자 지식 MD 파일 작성/정리 (canon/)
2. RAG 소스 자료 정리 (sources/)
3. `just knowledge-ingest shared` 로 벡터 인덱스 구축

### Phase 4: 정리 (1일)
1. `teams/` 디렉토리 삭제 (또는 archive/)
2. docs/STRUCTURE.md 업데이트
3. CLAUDE.md 업데이트
4. webapp API 연결 변경

---

## 검증 방법
1. `POST /api/pipelines/morning_briefing/run` → StageResult 4개 + 텔레그램 알림 수신
2. `GET /api/pipelines/morning_briefing/latest` → 최신 분석 결과 조회
3. DB 확인: `team_outputs`에 `team_id="morning_briefing"` 행 존재
4. DB 확인: `team_memory`에 메모리 기록 존재 (연속성)
5. 기존 `just validate` 통과 (스크립트 수정 후)
6. 기존 테스트 통과 (checkers/ 이동 후)
