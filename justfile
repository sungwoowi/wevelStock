# wevelStock — 크로스 플랫폼 태스크 러너
# 사용: just <command> [args]

# 메인 worktree 의 .venv 를 모든 worktree 에서 공유.
# worktree 안에서도 uv/python 이 항상 같은 가상환경을 보도록 강제 (google-genai 등 deps 재설치 불필요).
export VIRTUAL_ENV := `git rev-parse --git-common-dir | sed 's,/\.git/*$,,'` + "/.venv"

# 기본: 명령 목록 출력
default:
    @just --list

# === 환경 ===

# 의존성 설치
install:
    uv sync --all-extras

# DB 초기화
db-init:
    uv run python -m scripts.db_init

# DB 백업
db-backup:
    uv run python -m server.schedulers.jobs.backup

# === 서버 ===

# FastAPI 서버 구동 (개발 모드, 자동 리로드)
server:
    uv run uvicorn server.main:app --reload --host 127.0.0.1 --port 8000

# 프로덕션 모드 (리로드 없음)
server-prod:
    uv run uvicorn server.main:app --host 0.0.0.0 --port 8000 --workers 1

# === 스캐폴딩 ===

# 새 팀 생성 (runtime: rule | llm | hybrid)
new-team id runtime="rule":
    uv run python -m scripts.scaffold team {{id}} --runtime {{runtime}}

# 새 MCP 서버 생성
new-mcp id:
    uv run python -m scripts.scaffold mcp {{id}}

# 새 SPEC 뼈대 생성
new-spec team title:
    uv run python -m scripts.scaffold spec {{team}} "{{title}}"

# === 검증 ===

# 구조 정합성 검증
validate:
    uv run python -m scripts.validate

# SPEC↔코드 매핑 갱신
trace:
    uv run python -m scripts.trace

# 도메인 문서 생성
domain-doc spec_id:
    uv run python -m scripts.generate_domain_doc {{spec_id}}

# === 테스트 ===

# 전체 테스트
test:
    uv run pytest

# 파이프라인별 테스트
test-pipeline name:
    uv run pytest pipelines/{{name}}/tests

# 커버리지
test-cov:
    uv run pytest --cov=core --cov=pipelines --cov=server --cov-report=html

# === 지식 레이어 (KNOWLEDGE-SYNC-001 Phase 2 M3) ===
# 외부 소스(OneDrive 등) → knowledge/reference/<dept>/ 이동은 사용자 수동.
# (직접 호출 시: uv run python -m scripts.sync_knowledge <dept>)

# reference 와 chroma collection 비교 → added/modified/deleted 만 처리 (delta sync).
# 인자 없으면 8 dept 전체. dept 지정 시 해당 dept 만.
# 예: just knowledge-sync
#     just knowledge-sync wealth_compounding
knowledge-sync *args:
    uv run python -m core.knowledge.sync {{args}}

# 컬렉션 drop 후 전체 재구축 (임베딩 모델 변경, 카테고리 메타 대규모 갱신 등).
# 운영 로그(knowledge_index_runs)에 drop 직전 prev 카운트가 deleted 로 적재된다.
knowledge-rebuild dept:
    uv run python -m core.knowledge.sync --force {{dept}}

# knowledge_index_runs 최신 N row 출력. 인자에 dept 지정 시 해당 dept 만.
# 예: just knowledge-status
#     just knowledge-status wealth_compounding --limit 5
knowledge-status *args:
    uv run python -m core.knowledge.sync --status {{args}}

# standalone watcher (server 미구동 시). reference/** 변경 감지 → 60s debounce → 자동 sync.
# 평소엔 server 가 lifespan 에서 자동 등록하므로 별도 실행 불필요.
knowledge-watch:
    uv run python -m core.knowledge.watcher

# 청크 검색 (디버깅용, top-5 단편 출력)
knowledge-browse dept query:
    uv run python -m scripts.knowledge browse {{dept}} "{{query}}"

# === 차트 데이터 (INFRA-CHART-DATA-001) ===

# DB chart_ohlcv 의 모든 ticker 일일 refresh (수동 백업, cron `0 18 * * 1-5` 자동 실행)
refresh-charts:
    uv run python -m collectors.charts refresh

# 단일 ticker 차트 fetch + 적재 (디버깅용). 예: just fetch-chart 005930
fetch-chart ticker *flags="":
    uv run python -m collectors.charts fetch {{ticker}} {{flags}}

# === 펀더멘털 데이터 (INFRA-FUNDAMENTAL-DATA-001) ===

# KR_NAME_TO_TICKER 35종 + DB distinct ticker union 의 fundamental refresh
# (수동 백업, cron `0 18 * * 0` 일요일 18:00 KST 자동 실행)
refresh-fundamentals:
    uv run python -m collectors.fundamentals refresh

# 단일 ticker fundamental fetch + 적재 (디버깅용). market 기본 KS. 예: just fetch-fundamental 005930
# KOSDAQ: just fetch-fundamental 247540 --market KQ
fetch-fundamental ticker *flags="":
    uv run python -m collectors.fundamentals fetch {{ticker}} {{flags}}

# === 추론부 (Layer 2 분석가 호출) ===

# 분석가와 멀티턴 대화 (REPL). /exit /clear /save 명령. 종료 시 JSONL 자동 저장.
# provider 락 예: just chat wealth_strategist --provider claude_code
chat analyst_id *flags="":
    uv run python -m scripts.chat_analyst {{analyst_id}} {{flags}}

# 분석가에 일회성 단발 질문. JSONL 1 turn 저장.
# provider 명시 예: just ask wealth_strategist "질문" --provider claude_code
ask analyst_id query *flags="":
    uv run python -m scripts.ask_analyst {{analyst_id}} "{{query}}" {{flags}}

# === 전략가 (Layer 3 — Track A·B + plugin) ===

# 전략가와 멀티턴 대화 (REPL). /exit /clear /save /target <ticker> 명령. 종료 시 JSONL 자동 저장.
# 예: just chat-strategist track_a --target 005930 --provider claude_code
chat-strategist strategist_id *flags="":
    uv run python -m scripts.chat_strategist {{strategist_id}} {{flags}}

# 전략가에 일회성 단발 질문. JSONL 1 turn 저장.
# 예: just ask-strategist track_a "long: 삼성전자 어때" --target 005930 --provider claude_code
ask-strategist strategist_id query *flags="":
    uv run python -m scripts.ask_strategist {{strategist_id}} "{{query}}" {{flags}}

# === 린트 ===

lint:
    uv run ruff check .
    uv run mypy core server pipelines scripts

fmt:
    uv run ruff format .
    uv run ruff check --fix .

# === 웹앱 ===

webapp-install:
    cd webapp && npm install

webapp-dev:
    cd webapp && npm run dev

webapp-build:
    cd webapp && npm run build

# === 편의 ===

# 전체 품질 게이트 (커밋 전 실행 권장)
check: validate trace lint test
    @echo "✅ 모든 체크 통과"

# 서버 정지 (포트 8000 사용 프로세스 kill)
server-stop:
    -pkill -f "uvicorn server.main"
