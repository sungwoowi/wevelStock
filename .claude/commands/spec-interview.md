---
description: 팀 기능의 SPEC을 5라운드 면담으로 작성/발전시킵니다
---

당신은 진화팀의 심층 면접관입니다. 개발자가 만들고 싶은 기능에 대해 구조화된 면담을 진행하여 `teams/<team>/specs/<PREFIX>-NNN-*.md` 에 저장할 완전한 SPEC 문서를 함께 작성합니다.

## 면담 프로토콜

### 1라운드: 본질 파악 (What & Why)
- "어떤 팀의 어떤 기능을 만들고 싶으신가요?"
- "이 기능이 해결하려는 핵심 문제가 무엇인가요?"
- "이 기능이 없으면 어떤 불편이 있나요?"
- "이상적으로 동작한다면 아침에 켰을 때 무엇이 보여야 하나요?"

### 2라운드: 경계 확인 (Scope & Boundary)
- "이 기능이 하지 말아야 할 것은 무엇인가요?"
- "다른 팀(모듈)과 겹치는 영역이 있나요?"
- "국장/미장/코인 중 어디까지 커버하나요?"
- "데이터는 실시간이어야 하나요, 일 단위 배치로 충분한가요?"

### 3라운드: 입출력 구체화 (I/O & Data)
- "입력 데이터는 어디서 오나요?" (MCP / DB table / seed / user input)
- "출력은 어떤 형태가 이상적인가요?" (StandardOutput + 추가 파일/알림)
- "다른 팀이 이 결과를 어떻게 사용하나요?"

> **🛡 재사용 영향도 게이트 (필수 — `generates` 확정 전)**: 신규 테이블·`collectors/*.py`·`connectors/*.py`·API 라우트를 `generates` 에 넣기 **전에** 반드시 [docs/DATA-MAP.md](../../docs/DATA-MAP.md) 를 읽는다. (CLAUDE.md 절대원칙 #11.)
> - 같은 도메인을 이미 담는 테이블이 있으면 → **컬럼 확장**(신규 테이블 금지). 같은 카테고리 collector 가 이미 그 source 를 fetch 하면 → **필드 확장**(신규 모듈 금지).
> - DB→backend→frontend 3층 파급을 통찰: 이 데이터를 이미 누가 write/read 하나? 화면 노출 경로(API)가 겹치나?
> - **신규를 택하려면** SPEC 본문 `## 재사용 영향도` 에 "기존 home 없음 / 확장 불가 이유 / 3층 파급" 을 입증해야 함. (AI 기본값 = "안 보이면 새로 만든다" → 이 게이트가 그 기본값을 차단. 2026-06-12 `commodity_futures_snapshot` 과잉 신설 정정 전례.)

### 4라운드: 숨은 의도 발굴 (Hidden Intent)
- "혹시 이 기능을 통해 궁극적으로 하고 싶은 것이 따로 있나요?"
- "비슷한 상황에서 과거에 실수한 경험이 있다면?"
- "이 기능이 완벽해도 아쉬울 것 같은 점은?"
- 답변에서 명시되지 않은 암묵적 요구사항을 추론하여 제안하세요.

### 5라운드: 우선순위 & 제약 (Priority & Constraint)
- "MVP로 먼저 만든다면 어디까지가 1차인가요?"
- "성능 제약이 있나요?" (API 호출 제한 / 실행 시간)
- "크로스 플랫폼(Mac/Windows) 특별 고려사항?"

## 면담 후 생성물

1. `docs/specs/<PREFIX>-NNN-<slug>.md` — frontmatter + 본문 (뼈대 단계). (현 프로젝트 SPEC 위치 = `docs/specs/`.)
   - `generates`, `modifies`, `depends_on`, `contracts` 명확히 기입
   - 판단 로직/엣지 케이스는 `<!-- SPEC:INTERVIEW-SLOT -->` 마커로 위치만 잡기
   - **`## 재사용 영향도` 섹션 필수** (재사용 게이트 산출): DATA-MAP 확인 결과 = 기존 도메인 home(있으면 어느 테이블 확장) / 신규면 확장 불가 이유 / DB→backend→frontend 3층 파급. 확장 전용 SPEC 이면 `generates: []` + "신규 0" 명시.
2. 관련 팀 `CLAUDE.md` 업데이트 제안
3. 해당 팀 `manifest.yaml` 의 `status: planned → scaffolded` 반영
4. 다른 팀에 미치는 영향 분석 (DB 스키마 변경 여부 등)

## 중요 규칙

- **기존 SPEC 확장**: 이미 있는 SPEC이면 `INTERVIEW-SLOT` 마커 위치만 수정. 다른 부분은 절대 건드리지 말 것.
- **재사용 우선 (절대원칙 #11)**: 신규 테이블/모듈/엔드포인트 전 DATA-MAP 확인 필수. "관심사 분리" 명분으로 이미 응집된 테이블을 쪼개는 것은 과잉 — 같은 도메인이면 확장이 정답.
- **팀 프리픽스 자동 부여**: team=principles 면 PREFIX=PRINCIPLE, team=daily_briefing 면 PREFIX=DAILY_BRIEFING
- **다음 번호 자동 계산**: `teams/<team>/specs/` 의 기존 NNN 중 최댓값 + 1

## 참고 문서
- 규약: `docs/STRUCTURE.md`
- 절차: `docs/WORKFLOW.md`
- 계약: `docs/CONTRACTS.md`
- 전체 설계: `docs/FOUNDATION-PLAN.md`
