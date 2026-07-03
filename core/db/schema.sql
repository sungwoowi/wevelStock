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
-- llm_cost_ledger — 비용 원장 (LLM-COST-LEDGER-001)
--   llm_call_cache 는 "중복제거 캐시"(unique input_hash 1행). 원장은 "모든 호출 1행씩"
--   기록해 벤더(provider)·모델(model)·질의영역(call_type)별 일단위 지출을 추적.
--   벤더/모델을 바꿔도 같은 축으로 추적 → 운영자 화면(/ops/llm-cost)이 소비.
-- ============================================================
CREATE TABLE IF NOT EXISTS llm_cost_ledger (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,                       -- ISO8601 (KST) 호출 시각
    day           TEXT NOT NULL,                       -- 'YYYY-MM-DD' (KST) 일단위 집계 키
    provider      TEXT NOT NULL,                       -- gemini | claude_code | anthropic | gemini+claude_code | mock
    model         TEXT NOT NULL,                       -- gemini-2.5-flash | claude-haiku-4-5 | ...
    call_type     TEXT NOT NULL DEFAULT 'general',     -- 질의영역: anchor_selection|analyst:<id>|strategist:<track>|briefing|news_classify|...
    target        TEXT,                                -- 종목코드 / 'global' (optional)
    tokens_in     INTEGER NOT NULL DEFAULT 0,
    tokens_out    INTEGER NOT NULL DEFAULT 0,
    cost_usd      REAL NOT NULL DEFAULT 0,
    cache_hit     INTEGER NOT NULL DEFAULT 0,          -- 1=캐시 히트(비용 0, 절감 가시화)
    success       INTEGER NOT NULL DEFAULT 1           -- 0=호출 실패(폴백/에러)
);

CREATE INDEX IF NOT EXISTS idx_llm_cost_ledger_day ON llm_cost_ledger(day);
CREATE INDEX IF NOT EXISTS idx_llm_cost_ledger_prov_model ON llm_cost_ledger(provider, model);
CREATE INDEX IF NOT EXISTS idx_llm_cost_ledger_type ON llm_cost_ledger(call_type);

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
    notification_type TEXT,               -- v16: market_briefing|trade_signal|account_safety|flow_idea|risk_alert
    is_read         INTEGER NOT NULL DEFAULT 0,  -- v16: 0=미독 1=읽음 (UI 종 배지 카운트)
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_notifications_log_created
    ON notifications_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read
    ON notifications_log (is_read);

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

-- 관심종목 리스트 일자별 멤버십 (TRADE-PLAN-LIFECYCLE 후속 · 체계적 종목 관리).
--   거래대금 상위 + 거래량 양봉 상위 두 큐레이션 리스트를 (date, market, ticker, list_type)으로 영속 →
--   ① 종목명 DB 조회(resolve_ticker 30종 매핑 한계 해소) ② "며칠 전 상위였나" 추적
--   ③ 관심종목 페이지의 관심→매수대기→매수진입 funnel 멤버십(team_outputs.funnel_stage 와 조인).
--   list_type = 'trade_value'(거래대금 상위) | 'volume_bull'(거래량 양봉 +3%).
--   멤버십 시계열을 담는 기존 테이블 없음(가드 #11, DATA-MAP 등재) → 신규.
CREATE TABLE IF NOT EXISTS universe_membership (
    date         TEXT NOT NULL,        -- YYYY-MM-DD (KST)
    market       TEXT NOT NULL,        -- KOSPI | KOSDAQ
    ticker       TEXT NOT NULL,
    list_type    TEXT NOT NULL DEFAULT 'trade_value',  -- trade_value | volume_bull
    name         TEXT,                 -- hts_kor_isnm (KIS 응답)
    rank         INTEGER,              -- 리스트 내 순위
    trade_amount INTEGER,              -- 누적 거래대금(원)
    volume       INTEGER,              -- 누적 거래량(주)
    change_pct   REAL,                 -- 전일 대비 등락률(%)
    concept      TEXT,                 -- 차트 컨셉 분류 (leader 주도주 | pullback 눌림 | base 바닥·소외 | unknown)
    source       TEXT NOT NULL DEFAULT 'kis',
    PRIMARY KEY (date, market, ticker, list_type)
);
CREATE INDEX IF NOT EXISTS idx_universe_membership_ticker
    ON universe_membership(ticker, date);
CREATE INDEX IF NOT EXISTS idx_universe_membership_list
    ON universe_membership(list_type, date);

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
    distribution_count_25d INTEGER,            -- v9: 25일 분산일 카운트 (regime/buy_score M축 입력)
    breadth_source  TEXT,                      -- v9: "krx"|"kis_index"|"kis_volrank_top30"|"unavailable"
    kospi200_night_change_pct REAL,            -- v16: KOSPI200 야간선물 (KIS best-effort, null 가능)
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
-- v9: 종목 레벨 5주체 수급 — INFRA-STOCK-SUPPLY-001
-- ============================================================
-- F-Score 세 축(theme_match·momentum·inflow_speed)을 시장 프록시 → 종목 실측 승급.
-- KRX 종목별 투자자별 거래실적 (5주체) on-demand 수집. (ticker, date) PK + REPLACE 멱등.
-- 시장 레벨 supply_demand_history 와 동일 5주체 스키마 (ticker 축만 추가) → 정합.
CREATE TABLE IF NOT EXISTS stock_supply_history (
    ticker          TEXT NOT NULL,           -- "005930"
    date            TEXT NOT NULL,           -- "2026-05-31" (KST)
    foreign_net     INTEGER NOT NULL,        -- 백만원 (음수 = 순매도)
    institution_net INTEGER NOT NULL,
    individual_net  INTEGER NOT NULL,
    financial_inv_net INTEGER NOT NULL,
    pension_net     INTEGER NOT NULL,
    source          TEXT NOT NULL DEFAULT 'krx',
    PRIMARY KEY (ticker, date)
);
CREATE INDEX IF NOT EXISTS idx_stock_supply_ticker_date ON stock_supply_history(ticker, date);

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
-- v10: 시장관 종합 (sector_rs_snapshot + market_view_snapshot) — MARKET-VIEW-SYNTHESIS-001
-- ============================================================
-- 섹터 RS 일자 스냅샷 — 순환매(어제 대비 이동)의 다일 누적 토대. (date, market, sector) PK + REPLACE.
CREATE TABLE IF NOT EXISTS sector_rs_snapshot (
    date             TEXT NOT NULL,           -- "2026-06-06" (KST)
    market           TEXT NOT NULL,           -- "KOSPI"
    sector           TEXT NOT NULL,           -- "AI반도체"
    etf_ticker       TEXT NOT NULL,           -- "390390"
    rs_score         REAL NOT NULL,           -- 0~10
    return_60d       REAL,
    kospi_return_60d REAL,
    rs_ratio         REAL,                    -- excess return
    PRIMARY KEY (date, market, sector)
);
CREATE INDEX IF NOT EXISTS idx_sector_rs_date ON sector_rs_snapshot(date, market);

-- 시장관 종합 산출물 — 결정론 regime/entry_posture + 결정론⨯LLM 크로스체크 rotation. (date, market) PK + REPLACE.
CREATE TABLE IF NOT EXISTS market_view_snapshot (
    date            TEXT NOT NULL,           -- "2026-06-06" (KST)
    market          TEXT NOT NULL,           -- "KOSPI"
    regime          TEXT,                    -- parabolic..strong_bear
    leading_json    TEXT,                    -- [{sector, rs_score, rs_change_nd}]
    fading_json     TEXT,                    -- [{sector, rs_score, rs_change_nd}]
    rotation_json   TEXT,                    -- {direction, from_sectors, to_sectors, strength, method, agreement}
    entry_posture   TEXT,                    -- aggressive | neutral | defensive
    one_liner       TEXT,
    confidence      INTEGER,
    reasons_json    TEXT,
    source          TEXT,                    -- db | computed | stale
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (date, market)
);
CREATE INDEX IF NOT EXISTS idx_market_view_date ON market_view_snapshot(date);

-- ============================================================
-- v11: 뉴스부 자료층 (news_items + news_digest_snapshot) — NEWS-SOURCE-001
-- ============================================================
-- 개별 뉴스 1건 + LLM 분류 라벨 (MS-B). 자료원=NewsSource 어댑터. url 멱등 PK.
-- 브리핑 일회성 RSS 를 영속·분류·다중소비자 학습층으로 승격 (중복 X).
-- 주: 레거시 run-scoped `news_items`(브리핑 persist, run_id PK)와 이름 충돌 회피 →
--     본 SPEC 영속 학습층은 `news_source_items` (collector 모듈명 일치).
CREATE TABLE IF NOT EXISTS news_source_items (
    url             TEXT PRIMARY KEY,        -- 멱등 키 (기사 URL)
    title           TEXT NOT NULL,
    source          TEXT,                    -- "Yahoo"|"CNBC"|"GoogleNews"|"manual"
    published_at    TEXT,                    -- RSS pubDate (원문)
    body            TEXT,                    -- 본문/유튜브 요약 (ManualNewsSource). RSS=NULL
    category        TEXT,                    -- macro_policy|industry_trend|geopolitics|policy_political|corporate_events|market_sentiment
    time_axis       TEXT,                    -- ephemeral_shock|short_theme|structural_trend
    direction       TEXT,                    -- up|neutral|down
    magnitude       INTEGER,                 -- 1|2|3
    confidence      INTEGER,                 -- 0~100
    affected_scope  TEXT,                    -- market|sector|ticker
    affected_refs_json TEXT,                 -- ["005930", ...]
    labeled_by      TEXT,                    -- llm|manual|rss_raw
    collected_at    TEXT,                    -- ISO8601 (UTC) 수집 시각
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_news_source_items_collected ON news_source_items(collected_at);
CREATE INDEX IF NOT EXISTS idx_news_source_items_category ON news_source_items(category);

-- build_news_digest(date[, ticker]) 단일 산출물 영속 — 결정론 집계 (M4/M5). (scope, date) 멱등 PK.
-- scope = "market" | "ticker:005930" | "sector:반도체". 정밀 점수 필드 없음 (거친 tilt).
CREATE TABLE IF NOT EXISTS news_digest_snapshot (
    scope           TEXT NOT NULL,           -- "market" | "ticker:<code>" | "sector:<name>"
    date            TEXT NOT NULL,           -- "2026-06-07" (KST)
    tone            TEXT,                    -- bearish|lean_bearish|neutral|lean_bullish|bullish (5단 tilt)
    category_counts_json TEXT,               -- {cat:{up,neutral,down}}
    top_themes_json TEXT,                    -- [{theme, time_axis, trigger_titles[]}]
    catalyst_tilt_json TEXT,                 -- {direction, strength} (종목/섹터 scope → buy_score N 블렌드)
    raw_labels      TEXT,                    -- LLM 주입용 분류 텍스트 묶음
    source          TEXT,                    -- db | computed | empty
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (scope, date)
);
CREATE INDEX IF NOT EXISTS idx_news_digest_date ON news_digest_snapshot(date);

-- ============================================================
-- v12: 미장 매크로 스냅샷 (us_macro_snapshot) — INFRA-US-MACRO-SNAPSHOT-001
-- ============================================================
-- 미국 야간 6 지표 일자 영속 + risk-on/off 결정론 분류. 데이터는 yfinance get_indices 재사용(U1).
-- 신규 테이블이라 ALTER 불필요 — CREATE IF NOT EXISTS 가 새 DB·기존 DB 모두 처리 (v10/v11 패턴).
-- date PK (KST). 같은 날짜 = 그날 새벽 마감된 동일 미장 세션 → 18:05·장전 두 트리거 멱등 동일값.
CREATE TABLE IF NOT EXISTS us_macro_snapshot (
    date              TEXT PRIMARY KEY,        -- "2026-06-07" (KST)
    nasdaq_change_pct REAL,
    sp500_change_pct  REAL,
    sox_change_pct    REAL,                    -- 필라델피아 반도체 (^SOX)
    vix               REAL,                    -- VIX 수준 (공포지수)
    vix_change_pct    REAL,
    dxy               REAL,                    -- 달러인덱스
    dxy_change_pct    REAL,
    us_10y            REAL,                    -- 미 10년물 금리 수준 (%)
    us_10y_change_bp  REAL,                    -- 전일 대비 bp
    gold_change_pct   REAL,
    risk_signal       TEXT,                    -- risk_on | neutral | risk_off
    signal_score      REAL,
    extreme           TEXT,                    -- none | vix_panic
    reasons_json      TEXT,
    source            TEXT,                    -- db | computed | stale | unavailable
    wti_change_pct        REAL,                -- v16: WTI 원유 야간선물 (INFRA-MARKET-ASSETS-002)
    brent_change_pct      REAL,                -- v16: 브렌트 원유 야간선물
    nq_futures_change_pct REAL,                -- v16: 나스닥100 야간선물
    es_futures_change_pct REAL,                -- v16: S&P500 야간선물
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- v13: 가상 계좌 상태 + 보유 (account_state + account_positions) — ACCOUNT-MANAGER-001 (RB-MS1)
-- ============================================================
-- 본 SPEC 가 스키마 *정의*. 비중 산정(MS1)은 DB-first read(없으면 seed 부트스트랩),
-- 가상 체결 *write* 는 RB-MS2(PAPER-TRADING-001). 신규 테이블 → CREATE IF NOT EXISTS 멱등.
-- 가상(페이퍼) 전용 — 실 KIS 주문 아님. 4계좌(config/accounts.yaml) account_id PK.
CREATE TABLE IF NOT EXISTS account_state (
    account_id              TEXT PRIMARY KEY,        -- kr_long | kr_swing | us_long | us_swing
    seed_krw                REAL NOT NULL,
    cash_krw                REAL,                    -- 가용 현금 (RB-MS2 갱신)
    deployed_weight         REAL NOT NULL DEFAULT 0, -- 총 누적 비중 0~1 (7계명 1번 추적)
    trading_deployed_weight REAL NOT NULL DEFAULT 0, -- 트레이딩(단기) 누적 비중 (7계명 3번)
    updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 계좌×종목 보유 (가상). RB-MS2 가 가상 체결로 write/갱신. MS1 은 read only.
CREATE TABLE IF NOT EXISTS account_positions (
    account_id     TEXT NOT NULL,
    ticker         TEXT NOT NULL,
    track          TEXT,                    -- A | B
    avg_price      REAL,                    -- 평단 (가상 체결 누적)
    shares         REAL,                    -- 보유 수량
    weight         REAL,                    -- 계좌 대비 비중 0~1
    tranche_count  INTEGER DEFAULT 0,       -- 진행된 분할 차수
    opened_at      TEXT,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (account_id, ticker)
);
CREATE INDEX IF NOT EXISTS idx_account_positions_account ON account_positions(account_id);

-- v14: 가상 체결 기록 (account_fills) — PAPER-TRADING-001 (RB-MS2), paper-fill-v1
-- ============================================================
-- 비중 지시(position-sizing) → 지정가 도달 판정 → 가상 체결 1 leg 기록.
-- 멱등 키 = (recommendation_id, account_id, side, leg). buy: leg=차수(1-3) /
-- sell: leg=목표단(1-3) 또는 0(손절). ON CONFLICT REPLACE 로 재실행 무해.
-- 가상(페이퍼) 전용 — 실 KIS 주문 아님. account_positions/account_state 는 본 기록에서 파생.
CREATE TABLE IF NOT EXISTS account_fills (
    recommendation_id  TEXT NOT NULL,
    account_id         TEXT NOT NULL,
    ticker             TEXT NOT NULL,
    track              TEXT,                    -- A | B
    side               TEXT NOT NULL,           -- 'buy' | 'sell'
    leg                INTEGER NOT NULL,        -- buy: 차수 1-3 / sell: 목표단 1-3·손절 0
    limit_price        REAL,                    -- 지정가 (도달 판정 기준)
    fill_price         REAL NOT NULL,           -- 가상 체결가
    shares             REAL NOT NULL,
    value_krw          REAL NOT NULL,
    reason             TEXT,                    -- 'entry' | 'add' | 'target_1' | 'stop' ...
    realized_pnl_krw   REAL NOT NULL DEFAULT 0, -- sell 만 (매도 실현손익)
    filled_date        TEXT NOT NULL,           -- YYYY-MM-DD (멱등 판정·보유기간)
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (recommendation_id, account_id, side, leg)
);
CREATE INDEX IF NOT EXISTS idx_account_fills_account ON account_fills(account_id, ticker);

-- v15: 일별 계좌 자산 스냅샷 (account_equity_snapshot) — WEALTH-COMPOUND-TRACKER-001 (RB-MS4)
-- ============================================================
-- 데스크가 매일 도는 끝에 계좌별 총자산 한 줄 저장(going-forward 마크투마켓 자산 곡선).
-- equity = seed + 누적 실현손익(account_fills) + 미실현(holdings 오늘 종가). equity-snapshot-v1.
-- 멱등 키 = (date, account_id). ON CONFLICT REPLACE. 가상(페이퍼) 전용.
CREATE TABLE IF NOT EXISTS account_equity_snapshot (
    date              TEXT NOT NULL,            -- YYYY-MM-DD
    account_id        TEXT NOT NULL,
    seed_krw          REAL NOT NULL,
    realized_cum_krw  REAL NOT NULL DEFAULT 0,  -- 누적 실현손익 (account_fills sell)
    unrealized_krw    REAL NOT NULL DEFAULT 0,  -- 미실현 (보유 평가손익, 오늘 종가)
    equity_krw        REAL NOT NULL,            -- seed + realized_cum + unrealized
    deployed_weight   REAL NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (date, account_id)
);
CREATE INDEX IF NOT EXISTS idx_equity_snapshot_account ON account_equity_snapshot(account_id, date DESC);

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
INSERT OR IGNORE INTO schema_version (version) VALUES (9);
INSERT OR IGNORE INTO schema_version (version) VALUES (10);
INSERT OR IGNORE INTO schema_version (version) VALUES (11);
INSERT OR IGNORE INTO schema_version (version) VALUES (12);
INSERT OR IGNORE INTO schema_version (version) VALUES (13);
INSERT OR IGNORE INTO schema_version (version) VALUES (14);
INSERT OR IGNORE INTO schema_version (version) VALUES (15);
INSERT OR IGNORE INTO schema_version (version) VALUES (16);
