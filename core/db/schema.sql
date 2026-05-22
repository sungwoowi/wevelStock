-- wevelStock — 전체 DB 스키마
-- 멱등성: 모든 CREATE 는 IF NOT EXISTS, INSERT 는 ON CONFLICT REPLACE

-- ============================================================
-- team_outputs — 팀 판단의 표준 저장소
-- ============================================================
CREATE TABLE IF NOT EXISTS team_outputs (
    run_id            TEXT NOT NULL,
    team_id           TEXT NOT NULL,
    timestamp         TEXT NOT NULL,
    target            TEXT NOT NULL,
    verdict           TEXT NOT NULL,
    confidence        INTEGER NOT NULL,
    reasons_json      TEXT NOT NULL,
    data_json         TEXT NOT NULL,
    contract_version  TEXT NOT NULL,
    metadata_json     TEXT NOT NULL,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (run_id, team_id, target)
);

CREATE INDEX IF NOT EXISTS idx_team_outputs_team_time
    ON team_outputs (team_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_team_outputs_target
    ON team_outputs (target, timestamp);

-- ============================================================
-- team_memory — LLM 팀 판단 메모리 (원본)
-- ============================================================
CREATE TABLE IF NOT EXISTS team_memory (
    team_id           TEXT NOT NULL,
    date              TEXT NOT NULL,
    target            TEXT NOT NULL,
    input_hash        TEXT NOT NULL,
    verdict           TEXT,
    confidence        INTEGER,
    reasons_json      TEXT,
    narrative         TEXT,
    data_json         TEXT,
    model             TEXT,
    contract_version  TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (team_id, date, target, input_hash)
);

CREATE INDEX IF NOT EXISTS idx_team_memory_team_date
    ON team_memory (team_id, date);

-- ============================================================
-- memory_rollup — 일/주/월/분기/연 요약
-- ============================================================
CREATE TABLE IF NOT EXISTS memory_rollup (
    team_id          TEXT NOT NULL,
    period_type      TEXT NOT NULL,   -- daily | weekly | monthly | quarterly | yearly
    period_key       TEXT NOT NULL,   -- '2026-04-16' | '2026-W16' | '2026-04' | '2026-Q2'
    summary_md       TEXT,
    key_events_json  TEXT,
    metrics_json     TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (team_id, period_type, period_key)
);

-- ============================================================
-- llm_call_cache — 멱등성 + 비용 절감
-- ============================================================
CREATE TABLE IF NOT EXISTS llm_call_cache (
    input_hash    TEXT PRIMARY KEY,
    model         TEXT,
    response_json TEXT,
    tokens_in     INTEGER,
    tokens_out    INTEGER,
    cost_usd      REAL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    ttl_days      INTEGER DEFAULT 7,
    type          TEXT NOT NULL DEFAULT 'general'   -- v8: 'general' | 'anchor_selection' | 'analyst'
);

CREATE INDEX IF NOT EXISTS idx_llm_call_cache_type ON llm_call_cache(type);

-- ============================================================
-- notifications_log — 알림 발송 이력 (webapp 조회용)
-- ============================================================
CREATE TABLE IF NOT EXISTS notifications_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id         TEXT NOT NULL,
    level           TEXT NOT NULL,     -- info | warning | critical
    title           TEXT NOT NULL,
    body            TEXT,
    channel         TEXT,              -- telegram | file | stdout
    delivered       INTEGER DEFAULT 0,
    related_run_id  TEXT,
    related_target  TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_notifications_log_created
    ON notifications_log (created_at DESC);

-- ============================================================
-- scheduler_runs — 스케줄러 작업 실행 로그 (디버깅용)
-- ============================================================
CREATE TABLE IF NOT EXISTS scheduler_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id        TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    status        TEXT,                -- success | failed | partial
    error         TEXT,
    metadata_json TEXT
);

-- ============================================================
-- 추후 팀들이 사용할 테이블 (Phase 2-4 에선 스켈레톤만)
-- ============================================================

CREATE TABLE IF NOT EXISTS portfolio_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT NOT NULL,
    account_type TEXT,                 -- asset | trading | cash
    total_value  REAL,
    data_json    TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS watchlist (
    ticker       TEXT PRIMARY KEY,
    market       TEXT,                 -- KR | US
    strategy     TEXT,                 -- daytrade | swing | asset
    added_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_macro (
    date         TEXT PRIMARY KEY,
    data_json    TEXT,
    verdict      TEXT,
    confidence   INTEGER,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- watch_positions — 사용자 수동 관심/홀딩 종목
-- 종목 + 관심가 + 시그널 누적 카운터만 관리 (평단/수량 X)
-- ============================================================
CREATE TABLE IF NOT EXISTS watch_positions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker           TEXT NOT NULL,
    name             TEXT,
    market           TEXT,                -- KR | US
    status           TEXT NOT NULL,       -- watching | holding | closed
    watch_price      REAL,
    buy_signal_cnt   INTEGER DEFAULT 0,
    sell_signal_cnt  INTEGER DEFAULT 0,
    hold_signal_cnt  INTEGER DEFAULT 0,
    last_signal_at   TEXT,
    last_signal_type TEXT,                -- BUY_ADD | SELL_PART | SELL_ALL | HOLD
    notes            TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_watch_positions_ticker
    ON watch_positions (ticker, status);

-- ============================================================
-- sim_trades — AI 시뮬레이션 매매 체결 로그 (append-only)
-- ============================================================
CREATE TABLE IF NOT EXISTS sim_trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker       TEXT NOT NULL,
    name         TEXT,
    side         TEXT NOT NULL,           -- buy | sell
    price        REAL NOT NULL,
    quantity     INTEGER NOT NULL,
    trade_no     INTEGER NOT NULL,        -- 1차, 2차, 3차 ...
    run_id       TEXT NOT NULL,
    pipeline_id  TEXT NOT NULL,
    reason       TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sim_trades_ticker ON sim_trades (ticker);
CREATE INDEX IF NOT EXISTS idx_sim_trades_run ON sim_trades (run_id);

-- ============================================================
-- sim_positions — AI 시뮬레이션 현재 포지션 (sim_trades 누적 결과)
-- ============================================================
CREATE TABLE IF NOT EXISTS sim_positions (
    ticker            TEXT PRIMARY KEY,
    name              TEXT,
    avg_price         REAL,
    total_quantity    INTEGER,
    buy_count         INTEGER DEFAULT 0,
    sell_count        INTEGER DEFAULT 0,
    realized_pnl      REAL DEFAULT 0,
    unrealized_pnl    REAL,
    status            TEXT,                -- holding | partial_exit | closed
    first_entry_at    TEXT,
    last_trade_at     TEXT,
    updated_at        TEXT
);

-- ============================================================
-- predictions — 시나리오 예측 + AI 매매일지 겸용
-- related_trade_id 로 sim_trades 연결
-- ============================================================
CREATE TABLE IF NOT EXISTS predictions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id      TEXT NOT NULL,
    run_id           TEXT NOT NULL,
    date_predicted   TEXT NOT NULL,
    target_date      TEXT,
    ticker           TEXT,
    prediction_type  TEXT NOT NULL,       -- scenario | verdict | sector | action
    prediction       TEXT NOT NULL,
    confidence       INTEGER,
    reason           TEXT,
    related_trade_id INTEGER,             -- sim_trades.id (soft FK)
    actual_outcome   TEXT,
    score            REAL,
    scored_at        TEXT,
    metadata_json    TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_predictions_pipeline_date
    ON predictions (pipeline_id, date_predicted);
CREATE INDEX IF NOT EXISTS idx_predictions_target
    ON predictions (target_date);

-- ============================================================
-- news_items — 수집된 뉴스 + LLM 영향도 태깅
-- 본문은 저장하지 않고 링크만 (title + url)
-- ============================================================
CREATE TABLE IF NOT EXISTS news_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           TEXT NOT NULL,
    pipeline_id      TEXT NOT NULL,
    published_at     TEXT,
    source           TEXT,                -- Reuters | Yahoo | CNBC | GoogleNews
    title            TEXT NOT NULL,
    url              TEXT NOT NULL,
    impact_direction TEXT,                -- bullish | bearish | neutral
    impact_magnitude INTEGER,             -- 1~3
    impact_note      TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(url, run_id)
);
CREATE INDEX IF NOT EXISTS idx_news_items_run ON news_items (run_id);

-- ============================================================
-- v3: 브리핑 온디맨드 (briefing_parts)
-- ============================================================
-- 파이프라인 1회 실행 = "브리핑". 그 내부 UI 섹션 = "파트".
-- 같은 LLM 컨텍스트·메모리에서 파생된 하위 조각.
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

-- ============================================================
-- knowledge_index_runs — KNOWLEDGE-SYNC-001 Phase 2 M2
-- 한 번의 sync run 단위 운영 로그. delta = collection metadata 비교.
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_index_runs (
    sync_id           TEXT PRIMARY KEY,        -- "YYYY-MM-DD-HHMM" (충돌 시 -SS)
    dept              TEXT NOT NULL,
    started_at        TEXT NOT NULL,
    ended_at          TEXT,
    status            TEXT NOT NULL,           -- running | success | partial | failed
    files_added       INTEGER DEFAULT 0,
    files_modified    INTEGER DEFAULT 0,
    files_deleted     INTEGER DEFAULT 0,
    chunks_upserted   INTEGER DEFAULT 0,
    chunks_deleted    INTEGER DEFAULT 0,
    proposal_path     TEXT,
    release_note_path TEXT,
    error             TEXT
);
CREATE INDEX IF NOT EXISTS idx_kir_dept_started
    ON knowledge_index_runs (dept, started_at DESC);

-- ============================================================
-- v5: 차트 데이터 (chart_ohlcv) — INFRA-CHART-DATA-001
-- ============================================================
-- KIS daily OHLCV historical 5 년 1825 봉 캐시. (ticker, date) PK + REPLACE.
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
    adjusted       INTEGER NOT NULL DEFAULT 1,  -- 수정주가 (1=adj, 0=원주가)
    fetched_at     TEXT NOT NULL,  -- ISO8601 적재 시각
    PRIMARY KEY (ticker, date)
);
CREATE INDEX IF NOT EXISTS idx_chart_ohlcv_ticker_date
    ON chart_ohlcv (ticker, date DESC);
CREATE INDEX IF NOT EXISTS idx_chart_ohlcv_fetched
    ON chart_ohlcv (fetched_at DESC);

-- ============================================================
-- v6: 펀더멘털 데이터 (fundamentals) — INFRA-FUNDAMENTAL-DATA-001
-- ============================================================
-- yfinance Default 8 필드 (TTM 5 ratio + 분기 5분기) 캐시. ticker PK + 24h TTL.
CREATE TABLE IF NOT EXISTS fundamentals (
    ticker            TEXT NOT NULL PRIMARY KEY,
    market            TEXT NOT NULL,                -- "KS" | "KQ" | "US"
    fetched_at        TEXT NOT NULL,                -- ISO8601 (UTC)
    eps_ttm           REAL,
    pe_ratio          REAL,
    roe               REAL,                         -- 0~1
    operating_margin  REAL,                         -- 0~1
    debt_to_equity    REAL,                         -- %
    quarterly_data    TEXT NOT NULL,                -- JSON: revenue/operating_income/eps × 5분기 + labels
    source            TEXT NOT NULL DEFAULT 'yfinance'
);
CREATE INDEX IF NOT EXISTS idx_fundamentals_fetched_at
    ON fundamentals (fetched_at DESC);

-- ============================================================
-- v7: 시장 스냅샷 확장 (market_macro_snapshot + supply_demand_history) — INFRA-SNAPSHOT-EXTEND-001
-- ============================================================
-- A 시장매크로 (지수 위계·breadth·MA·Distribution Day) + C 5주체 수급 60일 시계열.
-- (date, market) 복합 PK + ON CONFLICT REPLACE 멱등성. cron snapshot_macro_refresh 평일 18:00 KST.
CREATE TABLE IF NOT EXISTS market_macro_snapshot (
    date            TEXT NOT NULL,           -- "2026-05-21" (KST)
    market          TEXT NOT NULL,           -- "KOSPI" | "KOSDAQ"
    index_close     REAL NOT NULL,
    ma_36m          REAL,
    ma_60m          REAL,
    position        TEXT,                    -- "above_both" | "between" | "below_both"
    ma_20d          REAL,
    ma_60d          REAL,
    ma20_slope_pct_5d  REAL,
    ma60_slope_pct_20d REAL,
    trend           TEXT,                    -- "uptrend" | "sideways" | "downtrend"
    advancing       INTEGER,
    declining       INTEGER,
    unchanged       INTEGER,
    breadth_ratio   REAL,
    is_distribution_day  INTEGER NOT NULL DEFAULT 0,
    change_pct      REAL,
    volume_change_pct REAL,
    PRIMARY KEY (date, market)
);
CREATE INDEX IF NOT EXISTS idx_macro_date ON market_macro_snapshot(date);
CREATE INDEX IF NOT EXISTS idx_macro_dd ON market_macro_snapshot(market, is_distribution_day);

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

-- ============================================================
-- manual_anchors (v8) — 사용자 직접 박은 anchor (WAVE-ALPHA-001)
-- Stage 1+2 (결정론 candidate + LLM Haiku 직관) 보다 우선
-- ============================================================
CREATE TABLE IF NOT EXISTS manual_anchors (
    ticker             TEXT NOT NULL,           -- "005930" / "NVDA" / "0001" 등
    timeframe          TEXT NOT NULL,           -- "daily" | "weekly" | "monthly"
    anchor_a_date      TEXT NOT NULL,
    anchor_a_price     REAL NOT NULL,
    anchor_b_date      TEXT NOT NULL,
    anchor_b_price     REAL NOT NULL,
    anchor_c_date      TEXT NOT NULL,
    anchor_c_price     REAL NOT NULL,
    note               TEXT,
    updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (ticker, timeframe)
);

CREATE INDEX IF NOT EXISTS idx_manual_anchors_ticker ON manual_anchors(ticker);

-- ============================================================
-- 스키마 버전 (마이그레이션 용)
-- ============================================================
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO schema_version (version) VALUES (1);
INSERT OR IGNORE INTO schema_version (version) VALUES (2);
INSERT OR IGNORE INTO schema_version (version) VALUES (3);
INSERT OR IGNORE INTO schema_version (version) VALUES (4);
INSERT OR IGNORE INTO schema_version (version) VALUES (5);
INSERT OR IGNORE INTO schema_version (version) VALUES (6);
INSERT OR IGNORE INTO schema_version (version) VALUES (7);
INSERT OR IGNORE INTO schema_version (version) VALUES (8);
