-- ============================================================
-- v8 마이그레이션: WAVE-ALPHA-001 = manual_anchors + llm_call_cache.type
-- ============================================================
-- SPEC: WAVE-ALPHA-001 (cycle 14.1)
-- 1. manual_anchors 테이블 신규 — 황제주 후보군 ~10 종목 사용자 직접 박기 용.
--    Stage 1+2 (결정론 candidate + LLM 직관) 보다 우선 (anchor 산출 hybrid 의 최상위 layer).
-- 2. llm_call_cache 에 type 컬럼 추가 — 'anchor_selection' / 'general' / 'analyst' 등 구분.
--    cache_key + type 으로 entry 분리, 캐시 분석 시 type 별 통계 가능.
-- ============================================================

-- 1. manual_anchors — 사용자 직접 박은 anchor (Stage 1+2 보다 우선)
CREATE TABLE IF NOT EXISTS manual_anchors (
    ticker             TEXT NOT NULL,           -- "005930" / "NVDA" / "0001" 등
    timeframe          TEXT NOT NULL,           -- "daily" | "weekly" | "monthly"
    anchor_a_date      TEXT NOT NULL,           -- "2022-10-25"
    anchor_a_price     REAL NOT NULL,
    anchor_b_date      TEXT NOT NULL,
    anchor_b_price     REAL NOT NULL,
    anchor_c_date      TEXT NOT NULL,
    anchor_c_price     REAL NOT NULL,
    note               TEXT,                    -- 사용자 메모 (선택)
    updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (ticker, timeframe)
);

CREATE INDEX IF NOT EXISTS idx_manual_anchors_ticker ON manual_anchors(ticker);

-- 2. llm_call_cache 에 type 컬럼 추가 (기존 DB 용 ALTER; 신규 DB 는 schema.sql 의 CREATE 정의가 처리)
-- SQLite 는 IF NOT EXISTS for ALTER TABLE ADD COLUMN 미지원 → 이미 컬럼 있으면 에러 raise.
-- 멱등 보장 위해 sqlite_master 체크 또는 try/except 가 호출자 책임.
ALTER TABLE llm_call_cache ADD COLUMN type TEXT NOT NULL DEFAULT 'general';

CREATE INDEX IF NOT EXISTS idx_llm_call_cache_type ON llm_call_cache(type);

INSERT OR IGNORE INTO schema_version (version) VALUES (8);
