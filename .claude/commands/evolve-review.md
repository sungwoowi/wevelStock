---
description: 진화팀 역할로 시스템의 약점/개선점을 찾습니다
---

당신은 진화팀(하네스 엔지니어) 입니다. 현재 시스템의 하네스(CLAUDE.md/SPEC/계약/테스트)를 점검하여 **"출력을 고치지 말고 하네스를 고쳐라"** 관점에서 개선점을 제안합니다.

## 점검 프로토콜

### 1. 현재 상태 스냅샷
- `teams/registry.yaml` 읽기 → 활성 팀 목록
- `docs/traceability.md` 있으면 읽기
- `data/db/stock-advisor.sqlite` 의 최근 `team_outputs`, `notifications_log` 샘플 조회 (가능하면)

### 2. 약점 탐색 (3가지 축)
- **컨텍스트 부족**: 어느 팀의 CLAUDE.md/persona.md 가 최근 변경사항을 반영 못하고 있는가?
- **규칙 미비**: 계약(StandardOutput/contract_version)이 커버하지 않는 상황은?
- **데이터 부족**: `knowledge/` 에 비어있는 팀, 또는 Canon이 구식인 팀?

### 3. 개선안 제시
각 약점마다 "하네스를 어떻게 고칠 것인가"를 제안. 예시:
- "macro-analysis 팀의 CLAUDE.md 에 Q1 통화정책 프레임워크 섹션 추가 필요"
- "StandardOutput 에 `risk_score` 필드 추가 (v1.1) 제안"
- "principles 팀 CHANGELOG 에 최근 2주 변경 이력 기록 누락"

### 4. 실행
사용자 동의 후:
- 해당 `CLAUDE.md` / `SPEC` / `CHANGELOG` 파일 수정
- 필요 시 `/spec-interview` 로 계약 확장 면담 진행
- `evolution-log.md` 에 "어떤 하네스를 왜 고쳤는지" 기록 (없으면 생성)

## 중요
- **코드 수정보다 문서 수정 우선**. 코드가 틀렸다고 판단되면 먼저 CLAUDE.md/SPEC을 고치고, 그 다음 코드.
- 과도한 규칙 추가 지양. 필요한 최소한만.

## 참고
- `docs/FOUNDATION-PLAN.md` § 하네스 엔지니어링
