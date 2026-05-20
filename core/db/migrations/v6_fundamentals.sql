-- ============================================================
-- v6 마이그레이션: 펀더멘털 데이터 (fundamentals)
-- ============================================================
-- SPEC: INFRA-FUNDAMENTAL-DATA-001
-- yfinance Default 8 필드 (TTM 5 ratio + 분기 5분기 매출·영업이익·EPS) 캐시.
-- ticker PK + ON CONFLICT REPLACE 멱등성. fetched_at 24h TTL.
-- quarterly_data = JSON column (revenue/operating_income/eps × 5분기 + quarter_labels).
-- YoY 산출 위해 5분기 저장 (render 표는 최근 4분기 노출).
-- ============================================================

CREATE TABLE IF NOT EXISTS fundamentals (
    ticker            TEXT NOT NULL PRIMARY KEY,
    market            TEXT NOT NULL,                -- "KS" | "KQ" | "US"
    fetched_at        TEXT NOT NULL,                -- ISO8601 적재 시각 (UTC)
    eps_ttm           REAL,                         -- TTM 5 ratio (F2)
    pe_ratio          REAL,
    roe               REAL,                         -- 0~1 (15% = 0.15)
    operating_margin  REAL,                         -- 0~1
    debt_to_equity    REAL,                         -- % (100 기준)
    quarterly_data    TEXT NOT NULL,                -- JSON: {"revenue":[...5], "operating_income":[...5], "eps":[...5], "quarter_labels":[...5]}
    source            TEXT NOT NULL DEFAULT 'yfinance'
);

CREATE INDEX IF NOT EXISTS idx_fundamentals_fetched_at
    ON fundamentals (fetched_at DESC);

INSERT OR IGNORE INTO schema_version (version) VALUES (6);
