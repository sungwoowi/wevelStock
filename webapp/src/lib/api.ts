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
