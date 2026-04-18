# 🔄 WORKFLOW.md — SDD 사이클 1페이지

> 새 기능 하나를 구상에서 완성까지 가져가는 절차. 이 페이지 하나만 따르면 됩니다.

---

## 🎯 SDD (Spec-Driven Development) 5단계 사이클

```
┌────────────────────────────────────────────────────────────┐
│                                                              │
│  [1] SPEC 면담          (무엇을·왜 정의)                      │
│         ↓                                                     │
│  [2] SPEC 문서 작성      (frontmatter + 뼈대 + INTERVIEW-SLOT)│
│         ↓                                                     │
│  [3] 코드 구현          (AI가 SPEC의 `generates` 경로에 생성) │
│         ↓                                                     │
│  [4] 테스트 & 검증       (pytest + just validate)             │
│         ↓                                                     │
│  [5] 도메인 문서 자동 생성 (just domain-doc <SPEC_ID>)         │
│         ↓                                                     │
│       (Git 커밋 → 다음 기능으로)                               │
│                                                              │
└────────────────────────────────────────────────────────────┘
```

---

## 1️⃣ SPEC 면담 — `/spec-interview`

Claude Code에서 실행:
```
/spec-interview
```

면담 5라운드:
1. **본질 파악** (What & Why)
2. **경계 확인** (Scope & Boundary)
3. **입출력 구체화** (I/O & Data)
4. **숨은 의도 발굴** (Hidden Intent)
5. **우선순위 & 제약** (Priority & Constraint)

면담이 끝나면 `teams/<team>/specs/<PREFIX>-NNN-<slug>.md` 가 **뼈대 상태**로 생성됩니다.

---

## 2️⃣ SPEC 문서 작성 / 보완

### SPEC 파일 예시 (뼈대)

```markdown
---
spec_id: PRINCIPLE-001
title: 7계명 체커
team: principles
type: feature
status: draft
generates:
  - teams/principles/src/commandments/weight_limit.py
  - teams/principles/src/commandments/__init__.py
  - teams/principles/tests/test_commandments.py
modifies: []
depends_on:
  - INFRA-001   # core/contracts/team_output.py 가 준비되어 있어야 함
contracts:
  - contract: team-output-v1
---

# PRINCIPLE-001: 7계명 체커

## 목적
포트폴리오 상태를 읽어 투자 7계명 위반 여부를 판정한다.

## 입력
- `data/seed/mock_portfolio.json` (초기) 또는 `portfolio_log` 테이블 (추후)

## 출력
- `team_outputs` 테이블에 StandardOutput 저장
- 위반 시 Telegram 알림

## 판단 로직
<!-- SPEC:INTERVIEW-SLOT role="judgment-logic" -->

## 엣지 케이스
<!-- SPEC:INTERVIEW-SLOT role="edge-cases" -->

## 완료 기준
- [ ] 4개 시나리오(정상/비중초과/손절없음/감정매매) 모두 검증
- [ ] `just validate` 통과
```

**규칙**:
- `generates` 경로에 있는 파일만 AI가 생성/수정
- `<!-- SPEC:INTERVIEW-SLOT -->` 마커는 `/spec-interview` 로만 채움 — 수동 편집 자제

---

## 3️⃣ 코드 구현

Claude Code에서:
```
이 SPEC PRINCIPLE-001을 구현해줘.
먼저 SPEC과 teams/principles/CLAUDE.md 를 읽고,
SPEC의 `generates` 에 명시된 파일만 만들어.
```

AI는:
1. SPEC frontmatter 검증 → `generates` 경로 확인
2. 팀의 `CLAUDE.md`, `manifest.yaml` 읽기
3. `core/contracts/` 의 관련 계약 Pydantic 모델 import
4. 파일 생성 (SPEC `generates` 경로 외에는 손대지 않음)
5. SPEC의 `status` 를 `implementing` → `implemented` 로 올림

---

## 4️⃣ 테스트 & 검증

### 팀 단위 테스트
```bash
just test principles           # 팀별
just test                      # 전체
```

### 구조 정합성 검증
```bash
just validate
```

체크 항목:
- 팀 표준 레이아웃 준수
- SPEC frontmatter 구비
- `generates` 파일 실제 존재
- registry.yaml ↔ 폴더 일치
- 팀 간 import 없음
- 계약 버전 충돌 없음

### SPEC↔코드 매핑 갱신
```bash
just trace
# → docs/traceability.md 자동 갱신
```

---

## 5️⃣ 도메인 문서 자동 생성

사용자(비개발자)가 **"이 기능이 무엇을 하는지"** 이해할 수 있는 설명서 생성:

```bash
just domain-doc PRINCIPLE-001
# → docs/domain/principles/seven-commandments.md 생성 또는 갱신
```

자동으로 조합되는 내용:
- SPEC의 목적·입출력
- 코드의 docstring
- 테스트 케이스의 시나리오 설명
- manifest.yaml 의 스케줄/출력 테이블

도메인 문서는 **이해 관계자(개발자 아님)용 설명서**입니다. Canon(compiled.md)과 다릅니다.

---

## 🌱 SPEC은 성장하는 문서

초기에 뼈대로 만들고, 시간이 지나면서 살을 붙입니다:

```
버전 1 (뼈대):      목적 + 입출력 + INTERVIEW-SLOT
  ↓  /spec-interview
버전 2 (1차 확장):  + 판단 로직
  ↓  구현 후 발견
버전 3 (엣지 보강): + 엣지 케이스
  ↓  /evolve-review
버전 4 (진화):      + 새로운 데이터 소스 반영
```

SPEC의 변경 이력은 Git이 추적합니다.

---

## 🆕 새 팀(에이전트) 추가 시나리오 (3분 튜토리얼)

```bash
# 1. 팀 스캐폴드
python scripts/scaffold.py team sentiment-analysis --runtime llm
# → teams/sentiment-analysis/ 표준 레이아웃 생성
# → teams/registry.yaml 자동 갱신
# → config/runtime.yaml 에 teams.sentiment-analysis.enabled: false 추가
# → SPEC-000-<team>-bootstrap.md 뼈대 생성

# 2. manifest.yaml 편집 (입출력, 스케줄, 의존성)
vim teams/sentiment-analysis/manifest.yaml

# 3. SPEC 면담으로 첫 기능 정의
claude
> /spec-interview
# → teams/sentiment-analysis/specs/SENTIMENT-001-*.md 생성

# 4. 구현
> SENTIMENT-001을 구현해줘

# 5. 테스트 + 검증
just test sentiment-analysis
just validate

# 6. 도메인 문서
just domain-doc SENTIMENT-001

# 7. 활성화
# config/runtime.yaml 에서 teams.sentiment-analysis.enabled: true 로 변경 → 저장
# 서버가 감지하여 다음 스케줄부터 실행
```

**기존 파일을 전혀 건드리지 않았음에 주목하세요.**

---

## 🔁 기존 기능 개선 시나리오

```bash
# 1. 기존 SPEC 찾기
just trace search "7계명"

# 2. SPEC의 INTERVIEW-SLOT을 /spec-interview 로 확장
/spec-interview PRINCIPLE-001

# 3. status 를 verified → implementing 로 내리고 구현 수정
# (AI가 자동 관리)

# 4. 재검증
just test principles
just validate

# 5. 변경 이력 기록
# teams/principles/CHANGELOG.md 에 자동 추가되거나 수동 추가
```

---

## 🛑 체크포인트 — 커밋 전에 확인

- [ ] `just validate` 통과
- [ ] `just test` 통과
- [ ] `just trace` 재실행 완료
- [ ] `docs/domain/<team>/` 에 해당 도메인 문서 최신 상태
- [ ] 팀 `CHANGELOG.md` 업데이트
- [ ] SPEC `status` 가 `implemented` 또는 `verified`
- [ ] 새 하드코딩 없음 (`config/runtime.yaml` 확인)

---

## 📝 명령어 치트시트

| 명령 | 역할 |
|---|---|
| `just new-team <id> [--runtime llm\|rule\|hybrid]` | 새 팀 스캐폴드 |
| `just new-mcp <id>` | 새 MCP 서버 스캐폴드 |
| `just new-spec <team> <title>` | 새 SPEC 뼈대 생성 |
| `just validate` | 구조 정합성 검증 |
| `just trace` | SPEC↔코드 매핑 갱신 |
| `just domain-doc <SPEC_ID>` | 도메인 문서 생성 |
| `just test [<team>]` | 테스트 (팀별 또는 전체) |
| `just server` | FastAPI 서버 구동 |
| `just demo <scenario>` | E2E 데모 실행 |
| `just knowledge-ingest <team>` | 팀 학습 자료 인덱싱 |
| `just knowledge-compile <team>` | 팀 Canon 재생성 |
| `just db-init` | DB 스키마 초기화 |
| `just db-backup` | DB 수동 백업 |

---

## 💡 핵심 철학 요약

1. **SPEC 없이 코드 없음** — 의도 먼저, 구현은 그 다음.
2. **AI에게 지도를 주지, 매뉴얼을 주지 마라** — CLAUDE.md는 짧고, 참조 경로만.
3. **출력을 고치지 말고 하네스를 고쳐라** — AI가 실수하면 CLAUDE.md/규약을 보강.
4. **확장은 삽입** — 새 기능 추가 시 기존 파일을 건드리지 않음.
5. **자동화**가 규약을 강제 — `just validate` 가 모든 것을 검증.
