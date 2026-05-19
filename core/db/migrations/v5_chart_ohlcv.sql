-- ============================================================
-- v5 마이그레이션: 차트 데이터 (chart_ohlcv)
-- ============================================================
-- SPEC: INFRA-CHART-DATA-001
-- KIS daily OHLCV historical (5 년 1825 봉) 캐시 테이블.
-- (ticker, date) 복합 PK → ON CONFLICT REPLACE 멱등성.
-- ============================================================

CREATE TABLE IF NOT EXISTS chart_ohlcv (
    ticker         TEXT NOT NULL,
    date           TEXT NOT NULL,  -- YYYY-MM-DD
    open           REAL NOT NULL,
    high           REAL NOT NULL,
    low            REAL NOT NULL,
    close          REAL NOT NULL,
    volume         INTEGER NOT NULL,
    change_rate    REAL NOT NULL DEFAULT 0,  -- 등락률 (%)
    value          INTEGER NOT NULL DEFAULT 0,  -- 거래대금 (원)
    adjusted       INTEGER NOT NULL DEFAULT 1,  -- 수정주가 여부 (1=adj, 0=원주가)
    fetched_at     TEXT NOT NULL,  -- ISO8601 적재 시각
    PRIMARY KEY (ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_chart_ohlcv_ticker_date
    ON chart_ohlcv (ticker, date DESC);
CREATE INDEX IF NOT EXISTS idx_chart_ohlcv_fetched
    ON chart_ohlcv (fetched_at DESC);

INSERT OR IGNORE INTO schema_version (version) VALUES (5);
