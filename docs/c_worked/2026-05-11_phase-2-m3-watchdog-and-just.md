---
date: 2026-05-11
topic: KNOWLEDGE-SYNC-001 Phase 2 M3 — watchdog 자동 색인 + justfile 명령 셋 정리
status: completed
plan_file: C:\Users\HOME\.claude\plans\delightful-beaming-scott.md
---

# 2026-05-11 · KNOWLEDGE-SYNC-001 Phase 2 M3 (watchdog + just)

## 배경

같은 날 직전 세션의 M2 (`sync_dept` + DB run log) 가 동작점에 도달했으나 수동 호출만 가능했음. M3 = **자동 트리거 + 사용자 인터페이스** wrap → 종료 시 = "사용자 reference push → 60s 자동 색인" = Phase 2 풀세트 = 프로토타입 1차 동작점.
사용자 정정 반영: 외부(OneDrive 등) → `knowledge/reference/` 이동은 사용자 manual. just 명령은 **reference drop 이후의 인덱싱 자동화만** 담당.
핵심 판단: server lifespan 자동 등록 + standalone 둘 다 — `start_observer()` 함수 1개 정의로 2 진입점 wrap, 코드 비용 0.

## 한 일

- `core/knowledge/watcher.py` (신규) — watchdog Observer + `_Debouncer` (threading.Timer, dept 단위 coalesce, pending_depts/stop) + `_extract_dept` (`_` prefix dept None) + `_build_handler` (is_directory skip, moved 시 src+dest 둘 다 처리) + `start_observer` / `stop_observer` / `run_forever`(standalone) + CLI `--reference-root` / `--debounce`
- `core/knowledge/sync.py` — `sync_dept(force=False)` 추가 (drop 직전 indexed_state 카운트를 deleted 로 적재 → collection drop → 전체 added 재구축) + `recent_runs(limit, dept)` helper + `_format_status_row` 1줄 포맷 + CLI 확장 (`--force` / `--status` / `--limit`) + `_open_collection(drop_existing=)` 인자
- `server/main.py` lifespan — startup 에 `start_observer()` 자동 등록 + `sync_all()` fire-and-forget reconcile (절전 후 fsevents 누락 안전망, BGE-m3 cold load 회피) / shutdown 에 reconcile_task cancel + `stop_observer()`
- `justfile` — 기존 3 명령 (`knowledge-sync` 구 OneDrive 추출 / `-ingest` / `-reingest`) 제거. 신규 5 명령 (`knowledge-sync` delta / `-rebuild` force / `-status` DB log / `-watch` standalone / `-browse` 유지). 외부→reference manual 결정 주석
- `tests/test_knowledge_watcher.py` (신규) — 7 케이스 (`_extract_dept` 3: 정상/`_prefix`/외부 path + `_Debouncer` 3: coalesce/dept 분리/stop cancel + Observer 통합 1: tmp dir 파일 생성 → 0.2s debounce → callback)
- `docs/specs/KNOWLEDGE-SYNC-001-reference-canon-rag-sync.md` — Phase 2 M3 ✅ 섹션 추가 + 명령 셋 변경 (외부→reference 사용자 manual 결정)
- `.mcp.json` — sqlite-db MCP entry 제거 (`@modelcontextprotocol/server-sqlite` archived). 별도 chore commit.

## 검증 결과

- ✅ pytest **134 passed** in 25.9s (128 → +7 watcher, 회귀 0). 사전 부채 1건 `test_render_data_source_line_mixed` (시간-의존 mock 누락, M3 영역 무관) 분리
- ✅ 단위 회로: `_extract_dept` 3 cases / `_Debouncer` 3 cases / Observer 통합 1 case
- ✅ 수동 4-단계 회로 검증 (server `ba2nuguih` background + reference 파일 add/modify/delete):
  - `2026-05-11-1526` add: +1/~0/-0 files, +1/-0 chunks
  - `2026-05-11-1529` modify: +0/~1/-0 files, +1/-0 chunks
  - `2026-05-11-1554` delete: +0/~0/-1 files, +0/-1 chunks
- ✅ server log: `watcher_started reference_root=... debounce_seconds=60.0` + `server_ready` + `knowledge_reconcile_done` (BGE-m3 cold load 포함 ~32s) 자동 등록 확인

## 의도적으로 안 한 것

- Phase 3 (PROPOSAL + release note LLM 자동 정제) — M3 분석가 분화 SPEC 뒤로 (Phase 3 prerequisite)
- canon 자동 정제 — Phase 3 영역, 현재는 사용자 손편집
- watchdog 동시성 race 보강 (같은 dept 2 sync) — 운영 수동 트리거 + lifespan 단일 observer 라 비현실. `_allocate_sync_id` fallback 이 PK 안전
- standalone watcher 실 검증 — server 동시 띄우면 watcher 2개 race, 단위 테스트 7 케이스로 충분
- 사전 부채 `test_render_data_source_line_mixed` 시간-의존 mock 보강 — 별도 작은 백로그

## 맥락 재진입 힌트

- **watcher 진입점 함수 1개 = 2곳 호출**: `start_observer()` 가 server lifespan + `just knowledge-watch` 둘 다에서 호출. 코드 비용 0 패턴.
- **사용자 정정 = "외부→reference 는 manual"**: just 명령은 reference 이후 자동화만. `scripts/sync_knowledge.py` 는 파일만 남기고 just 에서 제거.
- **fire-and-forget reconcile**: `sync_all` 이 BGE-m3 cold load 가능성 있어 startup blocking 회피 (`asyncio.create_task(asyncio.to_thread(sync_all))`). gap_filler 와 패턴 다름 (gap_filler 는 lightweight 라 await).
- **logger keyword 주의**: `core.logging` 의 첫 positional 이 `event` 라 `log.debug("x", event=...)` 충돌. `event_type=` 로 회피.
- **windows 인코딩**: pytest 시 `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8` 안 주면 한글 assert 깨져 출력 (실패 메시지 자체가 cp949). 셋 다음 세션 진입 치트시트화.

## 다음에 이어서 할 작업 (우선순위)

1. **M3 분석가 분화 SPEC 작성** (3~5 세션) — 9 분석가 페르소나 8-섹션 portable 양식 + 자료 있는 3명 (원칙수호자/트레이더/종목분석가) 직행 + 자료 0 시드 5명 (시장상태/종목선정/매매저널/수급/뉴스) PROPOSAL 흐름. 페르소나의 `canon_categories: [<dept>/<category>, ...]` 가 Phase 2 자동 sync 와 결합 동작 확인 가능 시점. **프로토타입 가동 핵심**. 자산전략가 (현재 유일 활성) → 4명으로 확장.
2. **stock-analysis dept 첫 인덱싱 + 검증** (~1 세션) — 어댑터 5종 (md/txt/pdf/xlsx/png) 다 굴리는 첫 사례. `just knowledge-sync stock-analysis` 또는 reference drop 자동 sync. xlsx sheet 분리 여부 실 자료 (`4.로그차트_advanced/`) 보고 결정.
3. **사전 부채 보강** (~30min) — `tests/test_market_snapshot.py::test_render_data_source_line_mixed` 시간-의존 mock 누락. `kr/us_threshold_seconds(now_kst)` cron 발동 시각 freezegun mock 으로 stale 강제 + DB 적재 fixture.

## 커밋 상태

- `3228eb5 feat(knowledge): KNOWLEDGE-SYNC-001 Phase 2 M3 — watchdog + justfile 정리` — push 완료
- `c078541 chore(mcp): sqlite-db MCP entry 제거 — npm 패키지 archived` — push 완료
- wrap-up commit (이 파일 + RESUME + SESSIONS) 별도 진행 예정
