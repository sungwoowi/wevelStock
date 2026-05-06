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

# === 지식 레이어 ===

# 외부 source(OneDrive 등)의 PDF 를 reference/<learning_dept>/ 로 멱등 추출
# 이미 추출된 파일은 skip — 새 PDF 추가 시 재실행만 하면 됨
knowledge-sync dept:
    uv run python -m scripts.sync_knowledge {{dept}}

# 학습부 RAG 인덱싱 (knowledge/reference/<dept>/ → data/chroma/<dept>/, 멱등 upsert)
knowledge-ingest dept:
    uv run python -m scripts.knowledge ingest {{dept}}

# 학습부 RAG 강제 재인덱싱 (컬렉션 삭제 후 재생성 — 임베딩 모델 변경 시)
knowledge-reingest dept:
    uv run python -m scripts.knowledge ingest {{dept}} --force

# 청크 검색 (디버깅용, top-5 단편 출력)
knowledge-browse dept query:
    uv run python -m scripts.knowledge browse {{dept}} "{{query}}"

# === 추론부 (Layer 2 분석가 호출) ===

# 분석가와 멀티턴 대화 (REPL). /exit /clear /save 명령. 종료 시 JSONL 자동 저장.
chat analyst_id:
    uv run python -m scripts.chat_analyst {{analyst_id}}

# 분석가에 일회성 단발 질문. JSONL 1 turn 저장.
ask analyst_id query:
    uv run python -m scripts.ask_analyst {{analyst_id}} "{{query}}"

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
