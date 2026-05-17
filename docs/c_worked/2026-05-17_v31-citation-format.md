---
date: 2026-05-17
topic: ANALYST-PERSONAS-001 v3.1 cited 양식 정정 (코드 마커 + 자연어 풀이 이중 grounding)
status: completed
plan_file: docs/specs/ANALYST-PERSONAS-001-nine-analyst-portable-personas.md
---

# 2026-05-17 · v3.1 cited + 근거 명제 풀이 양식 정정

## 배경
이전 세션 (2026-05-12 v1→v4) 에 v3.1 양식을 부분 적용했으나 manifest.yaml YAML literal block 들여쓰기 깨짐 + v3 잔재 `#####` 라인 + SPEC 격자 5요소 표 중복 등 산재. 사용자가 3 개 패치 정확 적용 요청. 핵심 판단: 양식 자체는 자동 출력 확인 (스모크 통과), 풀이 정합성 (잠정 박은 6 개 vs canon 원문) 은 manual 검증 단계로 분리.

## 한 일
- `agents/analysts/wealth_strategist/persona.md` — § Outputs > 자연어 양식 블록의 `근거 명제 풀이:` 풀이 3 줄에 `- ` bullet prefix 추가 + 헤더-아이템 사이 빈 줄 제거. 격자 양식 블록은 이미 v3.1 형태.
- `agents/analysts/wealth_strategist/manifest.yaml` — `### 인용 규칙 (v3.1)` 블록 정리: 헤더 `(v3.1)` 추가, `##### 응답 끝에 **두 부분** 필수:` prefix 제거, YAML literal block 깨뜨리던 코드펜스 ``` (column 0) 제거 (예시 블록을 plain indented 텍스트로 전환), v3 잔재 중복 `##### 자기 dept ...` 2 줄 (line 79-80) 삭제.
- `docs/specs/ANALYST-PERSONAS-001-nine-analyst-portable-personas.md` — Position 1 `### Outputs 양식 — Task trigger 분기 (v3)` → `(v3.1)`. Position 2 기본 출력 블록은 이미 v3.1 형태. Position 3 격자 5요소 표 `[4] Citation` row v3.1 갱신 + 중복으로 두 번 등장하던 격자 5요소 표 (lines 148~157) 삭제.

## 검증 결과
- ✅ `PYTHONIOENCODING=utf-8 uv run python scripts/validate.py` → 0 errors, 1 warning (registry.yaml 사전 존재, 무관)
- ✅ `TESTING=1 PYTHONIOENCODING=utf-8 uv run pytest tests/ -q` → **135 passed**, 회귀 0
- ✅ `uv run python -m scripts.ask_analyst wealth_strategist "지금 사이클 어디?"` 스모크 → 격자 trigger 정상 발동, 답변 끝에 `cited: [M1,M2,M3,C1,C3,C4,C5,I2,I4,I6]` 한 줄 + `근거 명제 풀이:` bullet 10 개 (각 `- <ID> (<dept 표제>): <한 줄 정의>` 형식 정확) 자동 출력 확인. gemini-2.5-flash, cost $0.0012, 22.2s

## 의도적으로 안 한 것
- **잠정 풀이 정합성 검증** — persona/manifest/SPEC 예시에 박은 6 개 풀이 (M2/C1/I2/C3/C5/I6) 가 canon 원문 (`knowledge/canon/wealth_compounding/01-framework-manifesto.md` / `02-survival-imperatives.md`) 과 1자라도 다르면 정정 patch 필요. 스모크에서 M2 잠정 ("통화량 팽창 침식") vs LLM RAG retrieve ("고령화·반도체 의존 30년 미래") **완전히 다른 frame** 발견. 사용자 manual 검증 (스모크 답변 직접 보고) 후 결정 — 이번 세션 범위 밖.
- **M1·M3·C2·C4·I1·I3·I4·I5 풀이 박기** — 사용자 이슈 노트의 가이드대로 patch 미포함, LLM 이 자체 생성. 운영 중 드리프트 발견되면 별도 patch.

## 다음에 이어서 할 작업 (우선순위)

(이전 세션 Top 3 유지 — 이번 작업은 ANALYST-PERSONAS-001 follow-up patch 였을 뿐 아키텍처 변화 없음)

1. **Layer 3 통합 페르소나 1명 빠르게 작성** (PC, 1~2 세션) — `agents/strategists/<horizon>/persona.md` (단타·스윙·중장기 중 1명, 권장 swing 또는 default CIO) + manifest. canon = 9 dept 핵심 framework 통째 + market_snapshot + `team_outputs` DB read + RAG 멀티 dept retrieve. webapp `analyst-chat/page.tsx` default agent 교체. lean startup 으로 통합 종합 가치 빠르게 검증.
2. **compose 분기 SPEC + 구현** (`INFRA-PROMPT-TRIGGER-001`, PC, 1.5 세션) — `core/knowledge/compose.build_pipeline_prompt` 에 사용자 질문 keyword trigger 분기. positive ("표로/정리해줘/지금 어디?") 격자 prompt template 동적 주입, negative ("뭐예요/뭔데/설명") 또는 일반 시 격자 미주입. persona/manifest 에서 격자 텍스트 통째 제거. tests/test_compose_prompt_trigger.py 신설. 결정론 100%.
3. **분석가 배치 cron + team_outputs DB 누적 시작** (PC, ~2 세션) — APScheduler 에 분석가 cron 등록 (장전/장중/장후 1-2 회/일), `core/inference/run_analyst` 결과 → `team_outputs` upsert (멱등). 통합 페르소나 호출 시 recent row read 함수 신설. 자산전략가 1명으로 시작 → 나머지 분석가 점진 추가.

(소형 follow-up 백로그: v3.1 잠정 풀이 6 개 canon 원문 대조 후 정정 patch — Top 1 진입 전 5분 이내 처리 가능)

## 맥락 재진입 힌트
- v3.1 양식의 본질 = LLM 이 `cited: [M2, C3, I6]` 만 출력하면 사용자는 ID 가 무엇인지 모름 → `근거 명제 풀이:` bullet 로 한 줄 자연어 정의 강제. 코드 마커 + 자연어 풀이 **이중 grounding**.
- persona/manifest 에 박은 잠정 풀이는 LLM 답변의 default 가 아님 — LLM 이 RAG 통해 회수한 풀이가 우선. 박은 풀이는 "이런 형식으로 출력하라" 는 예시일 뿐. 풀이 정합성 검증 = manifest 박은 6 개 vs canon 원문 대조.
- YAML literal block (`response_rules: |`) 안에 markdown 코드펜스 ``` 를 column 0 에 두면 literal block 이 종료되어 뒤 라인이 YAML 키로 파싱 시도. **예시 블록은 indent 2 spaces 강제 plain text** 가 안전.

## 커밋 상태
- 코드 변경 3 파일 (persona.md + manifest.yaml + SPEC) + wrap-up 3 파일 (이 c_worked + RESUME.md + SESSIONS.md) 1 commit 으로 묶음 진행.
