-- ============================================================
-- v3 마이그레이션: 브리핑 온디맨드 (briefing_parts)
-- ============================================================
-- SPEC: BRIEFING-ON-DEMAND-001
-- 파이프라인 1회 실행 = "브리핑". 그 내부 UI 섹션 = "파트".
-- 동일 (pipeline_id, run_id, part_key) 재실행 시 덮어쓰기 (멱등성).
-- ============================================================

CREATE TABLE IF NOT EXISTS briefing_parts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id   TEXT NOT NULL,
    run_id        TEXT NOT NULL,
    part_key      TEXT NOT NULL,       -- overnight | scenario | positions | ...
    part_label    TEXT NOT NULL,
    part_order    INTEGER NOT NULL,
    data_json     TEXT NOT NULL,        -- 파트별 구조화 데이터 (JSON 문자열)
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(pipeline_id, run_id, part_key)
);

CREATE INDEX IF NOT EXISTS idx_briefing_parts_lookup
    ON briefing_parts(pipeline_id, created_at DESC);

INSERT OR IGNORE INTO schema_version (version) VALUES (3);
