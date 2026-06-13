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
