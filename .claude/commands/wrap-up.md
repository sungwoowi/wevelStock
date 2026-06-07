---
description: 이번 세션에서 한 일을 docs/c_worked/에 기록하고 docs/RESUME.md를 갱신하여 다음 세션이 즉시 이어갈 수 있게 만듭니다
---

당신은 wevelStock 프로젝트의 작업 세션을 **마무리**하는 역할입니다. 이 대화에서 한 일을 외부 파일(c_worked + RESUME)에 기록하여, 다음 번에 사용자가 `/resume` 만 쳐도 맥락이 완벽히 복원되도록 합니다.

## 실행 절차

### Step 0 — 빈-세션 방어
먼저 현재 대화에 **실제 작업 내용**이 있는지 판단합니다. 의미 있는 작업 = 파일 편집/생성, 코드 실행, 명령 수행, 설계 결정 등.

대화가 방금 시작되어 작업 내용이 거의 없다면 **기록하지 말고** 다음 안내만 출력하고 종료:

```
⚠️  현재 세션에 기록할 작업 내용이 없습니다.

▸ 이전 세션을 이어가고 싶다면:
    터미널을 닫고 다음 명령으로 세션을 재개하세요:
      cd C:\Users\HOME\claude\wevelStock
      claude -r     (최근 세션 목록에서 선택)
      claude -c     (가장 최근 세션 자동 이어가기)

  각 세션의 내용 요약은 docs/SESSIONS.md 표에서 확인할 수 있습니다.

▸ 새로운 주제로 시작하려면:
    /resume 을 불러 프로젝트 맥락을 복원하세요.

▸ 다른 CLI/에디터 창의 세션에서 이미 작업한 내용을 기록하려면:
    그 내용을 이 채팅에 붙여넣어 주세요. 그 후 다시 /wrap-up 호출.

사실 기반 기록 원칙상 대화에 없는 작업을 추측으로 적지 않습니다.
```

안내 출력 후 **즉시 종료**. 추가 질문을 던지지 마세요.

작업 내용이 있다면 Step 1 로 진행.

### Step 1 — 이번 세션 한 일 요약
현재 대화 기록에서 다음을 뽑아내세요:

- **주제**: 한 줄 (예: "07:00 장전 브리핑 고도화")
- **배경**: 왜 이 작업을 했나 (2~4줄)
- **한 일**: 실제로 변경/추가한 파일을 **파일 경로별로** 나열. 각 파일마다 한 줄 설명.
- **검증 결과**: 돌린 테스트/커맨드 + 통과 여부
- **의도적으로 안 한 것**: 플랜에는 있었지만 이번에 제외한 것 + 이유
- **기술 부채/미완**: 이번에 생긴 새로운 공백

### Step 2 — docs/c_worked/ 파일 생성
파일명 규칙: `docs/c_worked/YYYY-MM-DD_<kebab-slug>.md`
- 날짜는 오늘(로컬 기준). `Bash` 로 `date +%Y-%m-%d` 또는 환경 프롬프트의 currentDate 사용.
- slug 는 주제를 영어/영한 혼합 kebab-case로 (예: `morning-pre-pipeline`, `knowledge-canon-injection`).
- **동일 날짜에 이미 파일이 있으면** 뒤에 `-2`, `-3` 붙이기. 덮어쓰지 말 것.

**분량 가이드**: 전체 **60~100줄 권장**. 150줄 넘으면 불릿을 합치거나 하위 섹션을 줄여라. "다음 세션이 맥락 복원" 에 필요한 최소면 충분 — 상세 diff 는 `git show` 가 담당한다.

필수 섹션 (빠지면 안 됨): `배경`, `한 일`, `검증 결과`, `다음에 이어서 할 작업`, `커밋 상태`
선택 섹션 (해당 있을 때만): `의도적으로 안 한 것`, `맥락 재진입 힌트`, `세션 중 실 비용`

포맷 (필수만 표시, 선택은 필요 시 삽입):
```markdown
---
date: YYYY-MM-DD
topic: <한 줄 주제>
status: completed | partial | blocked
plan_file: <관련 플랜 파일 경로 있으면>
---

# YYYY-MM-DD · <주제>

## 배경
<2~4줄. 왜 이 작업을 했나 + 이번 세션의 핵심 판단 1줄>

## 한 일
- `path/to/file.py` — 설명 (파일별 1줄)
- ...
(영역 구분(###) 은 파일이 많을 때만)

## 검증 결과
- ✅ <테스트/커맨드 + 결과>

## 다음에 이어서 할 작업 (우선순위)
1. **<제목>** — 왜 + 범위 (1~2줄)
2. ...
3. ...
(Top 3 권장. 4+ 는 RESUME.md 에 안 들어가므로 여기서만.)

## 커밋 상태
- <커밋 여부 + 해시 또는 "아직 안 됨">
```

### Step 2.5 — 프로젝트 단계 지도 갱신 + drift 기록 (필수)
`Bash` 로 `PYTHONIOENCODING=utf-8 uv run python scripts/project_status.py` 실행 후:

1. **SPEC status 갱신**: 이번 세션이 어떤 implementation SPEC 을 전진시켰으면, 그 SPEC frontmatter `status` 를 실제에 맞게 올린다 (draft→implementing, implementing→verified 등). 마일스톤의 자식이 완료됐으면 roadmap 의 자식 상태판 행도 갱신. 새 작업이 **roadmap 에 안 매달린 implementation SPEC** 을 만들었으면 `parent:` 를 채워 연결(미연결 = drift).
2. **단계 위치 확정**: 이번 세션이 **어느 roadmap / 마일스톤**을 전진시켰는지 한 줄로 정리 (c_worked 배경 + 아래 Step 7 요약에 포함).
3. **drift 점검**: 이번 작업이 ACTIVE roadmap 밖으로 샜으면 (의도된 전환이 아닌데 미연결 SPEC 증가) c_worked "다음에 이어서 할 작업" 에 "단계 복귀" 항목을 박는다.

> 단계 지도는 roadmap SPEC 에서 파생되므로, 손으로 % 를 적지 말고 **SPEC status 를 정확히 유지**하는 것이 곧 진행도 갱신이다.

### Step 3 — docs/RESUME.md 갱신
기존 RESUME.md 를 읽고 다음 섹션을 **교체**:

1. **"📍 지금 어디 있나"** 섹션:
   - `마지막 작업일` → 오늘 날짜
   - `마지막 세션 로그` → 방금 만든 c_worked 파일 링크
   - 본문 1~2줄 갱신 (Phase 위치 묘사)

2. **"🎯 다음에 할 일 (Top 3)"** 섹션:
   - c_worked 의 "다음에 이어서 할 작업" Top 3 를 그대로 복사
   - 각 항목: 제목 / 왜 / 범위 / 방식 / 예상 산출

3. **"🧩 마지막 세션이 남긴 맥락"** 섹션:
   - **완성된 자산**: 이번 세션에 추가된 것 포함하여 재작성
   - **미완 또는 의도적 공백**: 업데이트
   - **꼭 알아둘 판단**: 이번 세션 결정 1~3개 추가. **프루닝 룰**:
     - "기초·불변 원칙" 블록은 늘리지 말 것 (이미 확립된 것만)
     - "이번 세션에 굳힌 판단" → 다음 /wrap-up 때 "직전 세션 판단" 으로 이동
     - "직전 세션 판단" 블록이 4주 넘은 항목은 제거 (파일 날짜 대비). 총 8~10개 이내 유지
     - 제거 판단 기준: 해당 결정이 이미 코드·문서에 박혀 있으면 중복 — 제거 가능

**절대 하지 말 것**:
- "📂 활성 설계/계획 문서", "🌱 이 프로젝트의 본질", "🔑 재진입 치트시트", "🧠 세션 재진입 절차" 섹션은 건드리지 마세요. 상단 링크와 하단 절차는 고정.
- Top 3 를 6개로 늘리지 말 것. 우선순위 흐릿해짐. 4순위+는 c_worked 에만 두고 RESUME 에는 3개만.

### Step 4 — docs/SESSIONS.md 인덱스 갱신
`docs/SESSIONS.md` 파일을 읽고, "세션 로그" 표의 **맨 위 데이터 행**에 새 항목을 삽입:

```
| YYYY-MM-DD | <status> | <주제 한줄 — 핵심 3~5개 키워드> | [log](c_worked/<파일명>.md) |
```

- 날짜는 오늘 (c_worked 파일명과 동일)
- status 는 completed / partial / blocked / paused 중 하나 (frontmatter 값 그대로)
- 주제 줄은 "무엇을 했나"가 한눈에 보이도록 키워드 위주로 압축 (예: `07:00 장전 브리핑 morning_pre 신규, DB 5테이블, collectors, API 2라우터, 스모크 3/3`)
- 기존 행은 건드리지 말 것. 맨 위 행에만 삽입.

### Step 5 — MEMORY.md 갱신 판단
이번 세션에 **메모리로 올릴 가치**(사용자 프로필 변화 / 새 피드백 / 프로젝트 상태 변화)가 있었나?
- 있으면 해당 `memory/*.md` 파일 편집 + `MEMORY.md` 인덱스 갱신.
- 없으면 이 Step 스킵.

기준: c_worked 에 기록된 "작업 내용" 은 메모리 금지. "사용자가 새로 밝힌 선호/원칙/피드백" 만 메모리 대상.

### Step 6 — 커밋 & main FF 머지 & push (조건부)

`git status` + `git log main..HEAD` 를 먼저 확인해 **필요할 때만** 진행. 둘 다 비어있으면 이 Step 스킵.

**A. 미커밋 변경이 있으면** — 이번 /wrap-up 이 생성·수정한 파일(c_worked 새 로그, RESUME.md, SESSIONS.md, 필요 시 project_state.md 등)을 **1 커밋**으로 묶음. 메시지 형식:
```
docs: wrap-up YYYY-MM-DD <주제 한줄 요약>
```
이번 세션이 따로 커밋하지 않은 코드 변경까지 섞여 있으면 **wrap-up 파일만 add** 해서 분리 (코드 커밋 누락은 사용자에게 확인).

**B. `main` 보다 앞선 커밋이 있으면** — 메인 worktree 루트에서 FF merge:
```bash
git -C "<메인 worktree 루트>" merge --ff-only <현재-브랜치>
```
(메인 worktree 루트는 `git rev-parse --git-common-dir | sed 's,/\.git/*$,,'` 로 획득)

**C. push (기본 동작)** — 커밋/FF 머지 후 `git push` 로 원격 동기화까지 자동 수행.
> 사용자 상시 선호 (2026-06-07): wrap-up 은 **커밋·푸시까지 한 번에**. 매번 "푸시 해줘" 라고 안 적어도 됨. push 실패(원격 거부·인증·non-FF) 시 **중단하고 사용자에게 알림** — 자동 재시도·force 금지.

**안전장치**:
- FF 불가(`main` 이 독립 커밋 받음) 시 머지 **중단**하고 사용자에게 알림 — 자동으로 merge commit 만들지 말 것
- `git push --force` 류 파괴적 푸시 금지(일반 push 만). push 거부 시 자동 force 금지 — 사용자 확인.
- 사용자가 /wrap-up 초기에 "커밋 말고 세션 기록만" / "push 하지마" 라고 한 경우 해당 부분만 스킵

커밋 해시 + `main` 새 tip + push 결과 를 다음 Step 요약에 포함.

### Step 7 — 결과 요약 출력
사용자에게 다음을 간결히 보고:

```
✅ 세션 기록 완료

📝 새 로그: docs/c_worked/YYYY-MM-DD_<slug>.md
📋 SESSIONS.md: 새 행 추가됨
🔄 RESUME.md: Top 3 / 마지막 작업일 / 맥락 섹션 갱신
🗺  단계: {{전진시킨 roadmap/마일스톤 + SPEC status 변화 (예: ANSWER-FIDELITY-001 implementing→verified) / drift 없음}}
🧠 MEMORY.md: {{갱신 or 변경 없음}}
💾 커밋: {{<해시> <메시지> or "커밋 대상 없음"}}
🚀 main/push: {{FF merge → <새 tip> + push <remote/branch> or "이미 최신" or "skip (사용자 요청)"}}

다음 세션 열 땐:
  cd C:\Users\HOME\claude\wevelStock
  claude -r   (세션 목록에서 선택)
  → 첫 명령으로 /resume
```

## 중요 규칙

- **사실 기반**. 대화에 없는 작업을 추측으로 적지 말 것. 애매하면 사용자에게 확인.
- **플랜 파일 경로 보존**. `C:\Users\HOME\.claude\plans\<name>.md` 가 있었으면 `plan_file:` frontmatter 에 명시.
- **파일 경로는 절대경로 대신 레포 기준 상대경로**. (`pipelines/morning_pre/stages/analyze.py` 처럼)
- **"다음에 할 일" 은 진짜 구체적으로**. "리팩터링" X → "pipelines/morning_pre/stages/persist.py 의 sim_trades 가격 0.0 → KIS API 실시간가 반영" O.
- **TodoWrite 는 사용하지 말 것**. 이 명령은 기록 작업이지 작업 진행이 아님.
- **토큰 효율**: RESUME.md 는 같은 파일에 여러 Edit 이 필요해도 **병렬 Edit 금지** (순차 수행). old_string 은 고유성이 확보되는 최소 범위만. c_worked 는 Write 한 번으로 작성 (Edit 반복 금지).
