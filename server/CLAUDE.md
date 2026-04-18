# Server (상주 런타임)

## 역할
FastAPI + APScheduler + 오케스트레이터 진입점을 모두 담은 단일 Python 프로세스.

## 구성
- `main.py` — uvicorn 진입. lifespan 에서 config watcher + scheduler + gap filler 시작.
- `api/` — REST 엔드포인트 (teams, config, demo, notifications)
- `schedulers/loader.py` — 팀 manifest의 schedule 필드 읽어 APScheduler 에 등록.
- `schedulers/jobs/` — 팀에 속하지 않는 인프라 작업 (backup, rollup, cleanup, gap_filler).

## 규칙
- 이 폴더에 **팀 로직을 넣지 않는다**. 팀 실행은 `teams/<id>/src/agent.py` 만.
- api 엔드포인트는 얇게 — DB/오케스트레이터로 위임.
- config 값은 `core.config.get_config()` 로만 읽는다. 하드코딩 금지.

## 실행
```bash
just server        # 개발 (auto-reload)
just server-prod   # 프로덕션
```

## 추후 확장
- `api/telegram.py` — Telegram 봇 webhook 수신 (명령 처리)
- `schedulers/jobs/` 에 KIS 갭필링 실구현
- 장애 복구 로직 강화 (스케줄 누락 감지)
