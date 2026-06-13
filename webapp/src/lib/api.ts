export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export async function fetcher<T = unknown>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export type StandardOutput = {
  team_id: string;
  run_id: string;
  timestamp: string;
  target: string;
  verdict: string;
  confidence: number;
  reasons: string[];
  data: Record<string, unknown>;
  contract_version: string;
  metadata: Record<string, unknown>;
};

export type Team = {
  id: string;
  name: string;
  runtime: string;
  status: string;
  depends_on: string[];
  schedule: unknown[];
};

export type Notification = {
  id: number;
  team_id: string;
  level: "info" | "warning" | "critical";
  title: string;
  body: string | null;
  channel: string;
  delivered: number;
  related_run_id: string | null;
  related_target: string | null;
  created_at: string;
};

// --- market-snapshot-v1 (GET /api/market/snapshot) ---------------------------
// 섹션별 partial — 미수집은 빈 dict/list 또는 {error}. 프론트는 graceful 처리.

/** 가격·등락 한 항목 (지수/자산). 수집 실패 시 {error}. */
export type PricePoint = {
  price?: number | null;
  value?: number | null;
  change_pct?: number | null;
  change?: number | null;
  trade_amount?: number | null;
  error?: string;
};

export type MarketViewBlock = {
  date: string;
  market: string;
  regime: string;
  entry_posture: string;
  one_liner: string;
  confidence: number;
  reasons: string[];
  leading_sectors: Record<string, unknown>[];
  fading_sectors: Record<string, unknown>[];
  rotation: Record<string, unknown>;
  source: string;
};

export type SectorRsItem = {
  sector: string;
  etf_ticker: string;
  rs_score: number | null;
  return_60d: number | null;
  kospi_return_60d: number | null;
  rs_ratio: number | null;
};

export type MarketHistoryItem = {
  run_id: string;
  pipeline_id: string;
  kst_iso: string | null;
  label: string; // 장전/장개시/장중/장마감
  time_label: string; // "6/13 (금) 09:30 · 장개시"
  summary: string;
};

export type MarketSnapshot = {
  fetched_at_iso: string | null;
  cache_hit: boolean;
  is_historical?: boolean;
  run_id?: string;
  pipeline_id?: string;
  source_map: Record<string, string>;
  db_age_seconds: Record<string, number>;
  kr_indices: Record<string, PricePoint | unknown>;
  overnight: Record<string, PricePoint | unknown>;
  fear_greed: Record<string, unknown>;
  market_macro: Record<string, Record<string, unknown>>;
  kr_supply: Record<string, unknown>;
  kr_supply_60d: Record<string, unknown>;
  kr_futures_supply: Record<string, unknown>;
  kr_sectors: Record<string, unknown>;
  sector_rs: SectorRsItem[];
  kr_leading: Record<string, unknown>;
  us_macro: Record<string, unknown> | null;
  night_futures: Record<string, unknown> | null;
  market_view: MarketViewBlock | null;
  failures: string[];
  snapshot_extend_failures: string[];
};

// --- 가상매매 데스크 (PAPER-DESK-UX-001) -------------------------------------

/** GET /api/wealth/curve — 자산 곡선 시계열. */
export type WealthCurve = {
  account_id: string;
  total_seed_krw: number;
  points: { date: string; equity_krw: number; realized_equity_krw: number }[];
};

/** GET /api/wealth/progress — 성장 목표 진척 + MDD + 알파. */
export type WealthProgress = {
  total_equity_krw: number;
  total_seed_krw: number;
  total_return_pct: number;
  target_return_pct: number;
  progress_pct: number | null;
  mdd_pct: number;
  mdd_guard_pct: number;
  mdd_breached: boolean;
  benchmark_return_pct: number | null;
  alpha_pct: number | null;
  elapsed_days: number;
  points: number;
};

/** GET /api/accounts — 4계좌 상태. */
export type AccountItem = {
  account_id: string;
  label: string;
  market: "KR" | "US";
  track: "A" | "B";
  horizon: "long" | "swing";
  seed_krw: number;
  deployed_weight: number;
  trading_deployed_weight: number;
  available_weight: number;
  deployed_krw: number;
};

/** GET /api/guidance/kpi — 청산 권고 KPI 집계. */
export type KpiSummary = {
  track: string;
  account_id: string | null;
  period_days: number;
  as_of: string;
  closed_count: number;
  realized_return_avg_pct: number | null;
  benchmark_return_avg_pct: number | null;
  alpha_avg_pct: number | null;
  win_rate_pct: number | null;
  rr_realization_avg_pct: number | null;
  avg_holding_days: number | null;
  realized_pnl_sum_krw: number;
  records: KpiRecord[];
  by_track?: Record<string, unknown>;
};

export type KpiRecord = {
  recommendation_id: string;
  account_id: string;
  ticker: string;
  track: string;
  entry_date: string;
  exit_date: string;
  holding_days: number;
  invested_krw: number;
  realized_pnl_krw: number;
  realized_return_pct: number;
  benchmark_return_pct: number | null;
  alpha_pct: number | null;
  direction_hit: boolean;
  rr_realization_pct: number | null;
};

/** 회차 1건 (체결 또는 미체결 사다리). */
export type Tranche = {
  leg: number;
  fill_price?: number;
  shares?: number;
  value_krw: number;
  filled_date?: string;
  reason?: string;
  limit_price?: number; // pending 만
  ratio?: number; // pending 만 (배분)
};

export type Holding = {
  account_id: string;
  ticker: string;
  track: string;
  shares: number;
  avg_price: number;
  weight: number;
  tranche_count: number;
  eval_price: number;
  priced: boolean;
  unrealized_pnl_krw: number;
  unrealized_pct: number;
  realized_pnl_krw: number;
  opened_at: string | null;
  holding_days: number;
  tranches: { ticker: string; recommendation_id: string | null; stop_loss: number | null; filled: Tranche[]; pending: Tranche[] };
};

export type PendingItem = {
  ticker: string;
  display_name: string;
  leg: number;
  limit_price: number;
  value_krw: number;
  ratio: number;
};

export type WatchingItem = { ticker: string; display_name: string; verdict: string; reason: string };

export type ClosedFill = {
  ticker: string;
  leg: number;
  fill_price: number;
  shares: number;
  value_krw: number;
  reason: string;
  realized_pnl_krw: number;
  filled_date: string;
};

/** GET /api/accounts/{id}/holdings — enriched. */
export type HoldingsResp = {
  account_id: string;
  holdings: Holding[];
  pending: { ladder_waiting: PendingItem[]; watching: WatchingItem[] };
  closed: ClosedFill[];
  summary: {
    position_count: number;
    unrealized_pnl_krw: number;
    realized_pnl_krw: number;
    total_pnl_krw: number;
    any_unpriced: boolean;
  };
};

export type ActiveRec = {
  recommendation_id: string;
  ticker: string;
  display_name: string;
  track: string;
  verdict: string;
  entry_price: number | null;
  stop_loss: number | null;
  target_prices: number[];
  risk_reward: number | null;
  confidence: number;
  date: string;
  reason: string;
};

export type FillEntry = {
  recommendation_id: string;
  account_id: string;
  ticker: string;
  track: string;
  side: "buy" | "sell";
  leg: number;
  fill_price: number;
  shares: number;
  value_krw: number;
  reason: string;
  realized_pnl_krw: number;
  filled_date: string;
};

/** GET /api/desk/feed. */
export type DeskFeed = { active_recommendations: ActiveRec[]; recent_fills: FillEntry[] };
