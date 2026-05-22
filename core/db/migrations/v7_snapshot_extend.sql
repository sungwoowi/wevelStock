-- ============================================================
-- v7 마이그레이션: 시장 스냅샷 확장 (market_macro_snapshot + supply_demand_history)
-- ============================================================
-- SPEC: INFRA-SNAPSHOT-EXTEND-001
-- A 시장매크로 (지수 위계·breadth·MA·Distribution Day) + C 5주체 수급 60일 시계열.
-- (date, market) 복합 PK → ON CONFLICT REPLACE 멱등성.
-- cron snapshot_macro_refresh (평일 18:00 KST) 가 매일 KOSPI/KOSDAQ 2 row 적재.
-- ============================================================

-- A 시장매크로 일별 적재 (cron snapshot_macro_refresh 가 매일 18:00 KST 1 row insert)
CREATE TABLE IF NOT EXISTS market_macro_snapshot (
    date            TEXT NOT NULL,           -- "2026-05-21" (KST)
    market          TEXT NOT NULL,           -- "KOSPI" | "KOSDAQ"
    -- 지수 위계
    index_close     REAL NOT NULL,
    ma_36m          REAL,
    ma_60m          REAL,
    position        TEXT,                    -- "above_both" | "between" | "below_both"
    -- 등락 추세
    ma_20d          REAL,
    ma_60d          REAL,
    ma20_slope_pct_5d  REAL,
    ma60_slope_pct_20d REAL,
    trend           TEXT,                    -- "uptrend" | "sideways" | "downtrend"
    -- breadth
    advancing       INTEGER,
    declining       INTEGER,
    unchanged       INTEGER,
    breadth_ratio   REAL,
    -- Distribution Day (당일 발동 여부)
    is_distribution_day  INTEGER NOT NULL DEFAULT 0,
    change_pct      REAL,
    volume_change_pct REAL,
    PRIMARY KEY (date, market)
);

CREATE INDEX IF NOT EXISTS idx_macro_date ON market_macro_snapshot(date);
CREATE INDEX IF NOT EXISTS idx_macro_dd ON market_macro_snapshot(market, is_distribution_day);

-- C 5주체 수급 일별 시계열 (KIS 5 주체 EOD fetch, 60일 누적은 collector get_supply_60d 가 sum)
CREATE TABLE IF NOT EXISTS supply_demand_history (
    date            TEXT NOT NULL,           -- "2026-05-21" (KST)
    market          TEXT NOT NULL,           -- "KOSPI" | "KOSDAQ"
    foreign_net     INTEGER NOT NULL,        -- 백만원 (음수 = 순매도)
    institution_net INTEGER NOT NULL,
    individual_net  INTEGER NOT NULL,
    financial_inv_net INTEGER NOT NULL,
    pension_net     INTEGER NOT NULL,
    source          TEXT NOT NULL DEFAULT 'kis',
    PRIMARY KEY (date, market)
);

CREATE INDEX IF NOT EXISTS idx_supply_history_date ON supply_demand_history(date);

INSERT OR IGNORE INTO schema_version (version) VALUES (7);
