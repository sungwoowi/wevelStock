"use client";

import type { KpiSummary } from "@/lib/api";
import { Metric } from "./primitives";

/** 성과 지표 스트립 (6) — 승률·익절·손절·손익비·MDD·샤프. 정본 충실.

손익비(R/R ratio)·샤프는 미산출 → graceful "준비 중"(다음 SLOT, PAPER-DESK-UX-001 결정).
*/
export function MetricStrip({
  kpi,
  mddPct,
  mddGuard = 8,
}: {
  kpi: KpiSummary | undefined;
  mddPct?: number | null;
  mddGuard?: number;
}) {
  const closed = kpi?.closed_count ?? 0;
  const records = kpi?.records ?? [];
  const wins = records.filter((r) => r.direction_hit).length;
  const losses = closed - wins;
  const win = kpi?.win_rate_pct;
  const mdd = typeof mddPct === "number" ? mddPct : null;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <Metric
        label="승률"
        value={win !== null && win !== undefined ? `${win.toFixed(0)}%` : "—"}
        sub={`청산 ${closed}건 기준`}
      />
      <Metric label="익절 횟수" value={`${wins}회`} valueClass="text-profit" sub="수익 청산" />
      <Metric label="손절 횟수" value={`${losses}회`} valueClass="text-loss" sub="손실 청산" />
      <Metric label="손익비" value="—" valueClass="text-faint" sub="준비 중 · 익절폭÷손절폭" />
      <Metric
        label="MDD (최대 낙폭)"
        value={mdd !== null ? `-${Math.abs(mdd).toFixed(1)}%` : "—"}
        valueClass="text-amber"
        sub={`자산 가드 -${mddGuard.toFixed(0)}% 안`}
      />
      <Metric label="샤프 지수" value="—" valueClass="text-faint" sub="준비 중 · 변동성 대비 효율" />
    </div>
  );
}
