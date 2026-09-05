# macOS 이전 절차 (Windows 데스크탑 → 맥북)

작성: 2026-09-05 세션. 형태 = **완전 이사** (Windows 은퇴, 병행 운영 아님).

이 문서는 "맥북 앞에 앉아서 이것만 따라 하면 끝"을 목표로 한다.
Windows 쪽 사전 작업은 이미 완료되어 커밋에 반영돼 있다 (§1 참조).

---

## 0. 한눈에 — 뭘 옮기고 뭘 두고 가나

실측 기준(2026-09-05). **실제로 손으로 옮길 것은 150MB 미만**이다.

| 대상 | 크기 | 처리 |
|---|---|---|
| 코드 전체 | 4MB (packed) | `git clone` — 옮기지 않는다 |
| `.env` | 2KB | **수동 전송 필수** (git 밖. KIS·Gemini·Telegram 키) |
| `data/db/stock-advisor.sqlite` | **108MB** | **복사 필수.** 가상매매·자산곡선·`team_outputs`·`llm_call_cache` 전부 여기 = 유일한 진짜 자산 |
| `data/chroma/` | 31MB | 복사 권장. 재생성 가능하나 BGE-m3 재임베딩이 무겁다 |
| `data/notifications/` | 2.5MB | 복사 (텔레그램 미설정 시 폴백 기록) |
| `data/analyst_queries/`, `data/strategist_queries/` | 200KB | 복사 (분석가 질의 이력) |
| `data/backups/` | 2.5GB | **두고 간다.** DB 백업본. 맥에서 다시 쌓인다 |
| `knowledge/reference/` | 1.4GB | **두고 간다.** 원본 PDF에서 재생성 (§3-6) |
| `.venv/`, `node_modules/`, `.next/`, `__pycache__/` | — | **두고 간다.** 재생성 |

---

## 1. Windows 쪽 사전 작업 (2026-09-05 세션에서 완료됨)

기록용. 이미 코드에 반영돼 있으므로 다시 할 필요 없다.

- [x] **PreToolUse 훅 크로스 플랫폼화** — `.claude/hooks/pytest_safety.ps1` → `pytest_safety.py`.
      맥에는 `powershell` 이 없어 훅이 매 Bash 호출마다 실패했을 것. 이 훅은 "테스트가 실 BOT_TOKEN
      으로 실제 카톡에 스팸 발송" 사고를 막는 안전장치라 비활성화는 선택지가 아니었다.
      포팅하며 **bash heredoc 스트립**을 추가했다 — 원본은 PowerShell here-string 만 벗겨서,
      맥에서 heredoc 커밋 메시지 안의 "pytest" 가 오탐날 상황이었다.
- [x] **외부 자료 경로 env 화** — `config/knowledge_sources.yaml` 의 Windows 절대경로 하드코딩을
      `${KNOWLEDGE_SOURCE_ROOT}` 로 교체. 미설정 시 silent fallback 없이 즉시 실패한다.
- [x] **낡은 경로 정정** — 위 작업 중 발견: 기존 하드코딩 경로가 이미 존재하지 않았다
      (`OneDrive/Desktop/...` → 실제는 `Desktop/.../자산전략부/박종훈_팬딩`).
      `just knowledge-sync` 가 이미 깨져 있었다는 뜻. 정정 후 PDF 31개 정상 인식 확인.
- [x] **워크트리·브랜치 정리** — 잔존 워크트리 5개 제거, 병합 완료된 `claude/*` 브랜치 15개 삭제.
- [x] **`git gc`** — 루즈 오브젝트 4181개(1.34GiB) → 팩 1개(4.03MiB). `.git` 1.4GB → 9.4MB.

---

## 2. 전송 (Windows → 맥북)

서버가 떠 있으면 **먼저 끈다**. SQLite WAL 이 열린 채로 복사하면 불완전한 DB 를 옮기게 된다.

```bash
# Windows 쪽: 서버 중지 확인 후
git status                 # 작업 중 변경 없는지
git push origin main       # 커밋 전부 원격에 올림
```

옮길 것을 한 폴더로 모은다 (USB / AirDrop / 클라우드 아무거나):

```
transfer/
├── .env                          ← 절대 빠뜨리지 말 것
├── db/stock-advisor.sqlite
├── chroma/                       ← data/chroma/ 통째로
├── notifications/                ← data/notifications/
├── analyst_queries/
└── strategist_queries/
```

`.env` 는 시크릿이다. 공개 클라우드에 올린다면 전송 후 즉시 삭제할 것.

---

## 3. 맥북 쪽 설치

### 3-1. 도구 설치

```bash
# Homebrew 없으면 먼저
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install git uv just node
xcode-select --install        # python3 + 빌드 도구
```

버전 요구: Python ≥ 3.11 (`pyproject.toml`), Node ≥ 20 (Next 15 / React 19).

### 3-2. 클론

```bash
mkdir -p ~/claude && cd ~/claude
git clone https://github.com/sungwoowi/wevelStock.git
cd wevelStock
```

### 3-3. 의존성

```bash
just install          # uv sync --all-extras
cd webapp && npm install && cd ..
```

> `npm` 을 쓴다. Windows 에서 pnpm EPERM 이 잦아 npm 으로 통일했고, 맥에서도 락파일
> 일관성을 위해 그대로 간다.

### 3-4. 전송한 자산 복원

```bash
mkdir -p data/db data/chroma data/notifications
cp  ~/transfer/.env                       .env
cp  ~/transfer/db/stock-advisor.sqlite    data/db/
cp -R ~/transfer/chroma/                  data/chroma/
cp -R ~/transfer/notifications/           data/notifications/
cp -R ~/transfer/analyst_queries/         data/analyst_queries/
cp -R ~/transfer/strategist_queries/      data/strategist_queries/
```

### 3-5. `.env` 맥 경로로 수정

`KNOWLEDGE_SOURCE_ROOT` 한 줄만 맥 경로로 바꾼다. 나머지 키는 그대로 쓴다.

```bash
# 예 (실제 자료를 어디에 뒀는지에 맞출 것)
KNOWLEDGE_SOURCE_ROOT=/Users/<사용자>/Desktop/주식투자/0.주식프로그램학습용
```

`DB_PATH=./data/db/stock-advisor.sqlite` 는 상대경로라 손댈 필요 없다.

### 3-6. 지식 자료 재생성 (선택 — 자료 원본을 맥으로 옮긴 경우)

`knowledge/reference/` 1.4GB 는 옮기지 않았다. 원본 PDF 를 맥에 두고 재추출한다.

```bash
uv run python -m scripts.sync_knowledge wealth_compounding
```

원본 PDF 를 맥에 두지 않을 거라면 이 단계는 건너뛴다. RAG 인덱스(`data/chroma/`)는
이미 복사했으므로 검색은 동작하고, 새 자료 추가 시점에만 필요하다.

---

## 4. 검증 (여기가 진짜 체크리스트)

순서대로 실행하고 **각 기대값을 눈으로 확인**한다.

```bash
# 1) 구조 정합성
just validate
#    기대: 실패 0

# 2) 전체 테스트 — TESTING=1 필수
TESTING=1 uv run pytest -q
#    기대: 전부 green. 실 API 호출 0건

# 3) 안전 훅이 실제로 막는지 (가장 중요 — 조용히 죽어 있으면 사고로 이어진다)
pytest --version
#    기대: "[hook BLOCKED] pytest 호출에 TESTING=1 acknowledgment 가 없습니다" 로 차단
#    통과해 버리면 → python3 가 PATH 에 없는 것. `which python3` 확인.

TESTING=1 pytest --version
#    기대: 정상 실행 (버전 출력)

# 4) DB 가 온전히 넘어왔는지
uv run python -c "
import sqlite3
c = sqlite3.connect('data/db/stock-advisor.sqlite')
print('integrity:', c.execute('PRAGMA integrity_check').fetchone()[0])
for t in ('team_outputs', 'briefing_parts', 'llm_call_cache'):
    n = c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'{t}: {n} rows')
"
#    기대: integrity ok + 아래 Windows 기준값 이상 (2026-09-05 실측)
#      integrity: ok
#      team_outputs:   1312 rows
#      briefing_parts:  699 rows
#      llm_call_cache: 2823 rows
#    행 수가 크게 적으면 복사가 잘린 것 — 다시 옮긴다.

# 5) 외부 자료 경로 해석 (3-6 을 수행한 경우만)
uv run python -c "
import sys, yaml; sys.path.insert(0,'.')
from pathlib import Path
from scripts.sync_knowledge import resolve_source_root
cfg = yaml.safe_load(Path('config/knowledge_sources.yaml').read_text(encoding='utf-8'))
r = resolve_source_root('wealth_compounding', cfg['learning_depts']['wealth_compounding']['source'])
print(r, '| exists:', r.exists())
"
#    기대: exists: True

# 6) 서버 기동
just server
#    기대: http://127.0.0.1:8000 응답. 스케줄러 잡 등록 로그 확인

# 7) 웹앱
cd webapp && npm run dev
#    기대: http://localhost:3000 렌더
```

---

## 5. 알려진 함정

- **서버 중복 기동.** 코드 수정 후에는 서버를 반드시 **재시작**한다. hot reload 를 믿지 말 것 —
  stale 프로세스가 옛 코드로 응답해 중복 LLM 호출이 발생한 전적이 있다.
  기동 전 `ps aux | grep uvicorn` 과 `lsof -i :8000` 으로 기존 프로세스를 먼저 확인한다.
- **텔레그램 봇 중복 polling.** 완전 이사이므로 **Windows 쪽 서버·스케줄러를 반드시 끈다.**
  같은 `TELEGRAM_BOT_TOKEN` 으로 두 대가 동시에 `getUpdates` 를 하면 Conflict 가 난다.
  잠깐이라도 병행할 일이 생기면 `_dev` 봇을 따로 만들어 토큰을 분리할 것.
- **`KIS_IS_PAPER`.** 이전 직후 `.env` 에서 값을 눈으로 확인한다. 주문 관련 코드는 `true` 전제.
- **한글 파일명.** macOS 는 유니코드 NFD 정규화를 쓴다. `knowledge/reference/` 의 한글 파일명이
  Windows(NFC)와 바이트가 달라 git 이 변경으로 볼 수 있다. 해당 폴더는 gitignore 대상이라
  실무 영향은 없지만, 다른 한글 경로에서 이상 징후가 보이면 이걸 의심할 것.
- **대소문자 구분.** macOS 기본 파일시스템은 대소문자를 구분하지 않는다(Windows 와 동일).
  임포트 경로 대소문자 오류가 맥에서도 안 잡히니, 리눅스 배포 시에는 별도 확인이 필요하다.

---

## 6. 이전 후 정리

- Windows 쪽 레포는 **DB 검증(§4-4)이 끝날 때까지 지우지 않는다.** 롤백 경로다.
- 검증 완료 후 Windows 쪽 서버·스케줄러 자동 실행을 해제한다 (텔레그램 Conflict 방지).
