# wevelStock — 크로스 플랫폼 태스크 러너
# 사용: just <command> [args]

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

# === 데모 ===

# E2E 데모 실행 (scenario: normal | over-allocation | no-stop-loss | emotional)
demo scenario="over-allocation":
    uv run python -m scripts.demo {{scenario}}

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

# 팀별 테스트
test-team team:
    uv run pytest teams/{{team}}/tests

# 커버리지
test-cov:
    uv run pytest --cov=core --cov=teams --cov=server --cov-report=html

# === 지식 레이어 ===

# 팀 학습 자료 인덱싱
knowledge-ingest team:
    uv run python -m scripts.knowledge ingest {{team}}

# 팀 Canon 재컴파일
knowledge-compile team:
    uv run python -m scripts.knowledge compile {{team}}

# 팀 지식 상태 확인
knowledge-status team:
    uv run python -m scripts.knowledge status {{team}}

# 청크 검색 (디버깅용)
knowledge-browse team query:
    uv run python -m scripts.knowledge browse {{team}} "{{query}}"

# === 린트 ===

lint:
    uv run ruff check .
    uv run mypy core server teams scripts

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
