"use client";

import type { WealthCurve, WealthProgress } from "@/lib/api";
import { fmtPct, pnlClass, wonKR } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useState } from "react";
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "./primitives";

const RANGES: { key: string; label: string; days: number | null }[] = [
  { key: "1M", label: "1M", days: 30 },
  { key: "3M", label: "3M", days: 90 },
  { key: "6M", label: "6M", days: 180 },
  { key: "1Y", label: "1Y", days: 365 },
  { key: "ALL", label: "전체", days: null },
];

/** CSS 변수(테마색) 실제 값 읽기 — recharts stroke 는 CSS var 미해석이라 computed 값 필요. */
function useThemeColors(names: string[]): Record<string, string> {
  const { resolvedTheme } = useTheme();
  const [vals, setVals] = useState<Record<string, string>>({});
  useEffect(() => {
    const cs = getComputedStyle(document.documentElement);
    const o: Record<string, string> = {};
    for (const n of names) o[n] = cs.getPropertyValue(n).trim() || "#888";
    setVals(o);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolvedTheme]);
  return vals;
}

function maxDrawdownPct(values: number[]): number {
  let peak = -Infinity;
  let mdd = 0;
  for (const v of values) {
    if (v > peak) peak = v;
    if (peak > 0) mdd = Math.min(mdd, (v / peak - 1) * 100);
  }
  return mdd; // ≤ 0
}

export function WealthCurveCard({
  curve,
  progress,
  title = "자산 곡선",
}: {
  curve: WealthCurve | undefined;
  progress?: WealthProgress;
  title?: string;
}) {
  const [range, setRange] = useState("3M");
  const colors = useThemeColors(["--profit", "--flat", "--down", "--border", "--faint"]);

  const points = curve?.points ?? [];
  const seed = curve?.total_seed_krw ?? 0;

  const filtered = useMemo(() => {
    const days = RANGES.find((r) => r.key === range)?.days ?? null;
    if (days === null || points.length === 0) return points;
    const last = new Date(points[points.length - 1].date).getTime();
    const cutoff = last - days * 86_400_000;
    return points.filter((p) => new Date(p.date).getTime() >= cutoff);
  }, [points, range]);

  const data = filtered.map((p) => ({ date: p.date, equity: p.equity_krw, realized: p.realized_equity_krw }));

  const lastEquity = points.length ? points[points.length - 1].equity_krw : seed;
  const equity = progress?.total_equity_krw ?? lastEquity;
  const returnPct = progress?.total_return_pct ?? (seed ? (equity / seed - 1) * 100 : 0);
  const mdd = progress?.mdd_pct ?? Math.abs(maxDrawdownPct(points.map((p) => p.equity_krw)));
  const mddGuard = progress?.mdd_guard_pct ?? 8;
  const alpha = progress?.alpha_pct ?? null;
  const targetEquity = progress ? seed * (1 + (progress.target_return_pct ?? 0) / 100) : null;

  const toggle = (
    <div className="flex gap-1 rounded-xl border border-border bg-card p-1">
      {RANGES.map((r) => (
        <button
          key={r.key}
          type="button"
          onClick={() => setRange(r.key)}
          className={cn(
            "rounded-lg px-2.5 py-1 text-xs font-semibold transition",
            range === r.key ? "bg-secondary text-foreground" : "text-faint hover:text-foreground",
          )}
        >
          {r.label}
        </button>
      ))}
    </div>
  );

  return (
    <Card title={title} action={toggle}>
      {/* 레전드 */}
      <div className="-mt-1 mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] font-semibold">
        <span className="text-profit">● 총자산 (평가 포함)</span>
        <span className="text-flat">● 실현만 (확정)</span>
      </div>

      {/* 수치 행 */}
      <div className="mb-4 flex flex-wrap items-baseline gap-x-3 gap-y-2">
        <span className="font-mono text-2xl font-bold text-foreground md:text-3xl">{wonKR(equity)}</span>
        <span className={cn("text-sm font-semibold", pnlClass(returnPct))}>{fmtPct(returnPct)}</span>
        <span className="text-xs text-faint">시드 {wonKR(seed)}</span>
        <div className="flex-1" />
        <span className="rounded-xl border border-border px-2.5 py-1 text-[11px] font-semibold text-body">
          최대 하락 -{mdd.toFixed(1)}% · 가드(-{mddGuard.toFixed(0)}%) {mdd <= mddGuard ? "안" : "이탈"}
        </span>
        {alpha !== null && (
          <span
            className={cn(
              "rounded-xl px-2.5 py-1 text-[11px] font-semibold",
              alpha >= 0 ? "bg-profit/10 text-profit" : "bg-loss/10 text-loss",
            )}
          >
            지수 대비 {fmtPct(alpha)}
          </span>
        )}
      </div>

      {/* 차트 */}
      <div className="h-48 w-full rounded-xl bg-surface p-2">
        {data.length >= 2 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: colors["--faint"] }}
                tickFormatter={(d: string) => d.slice(5)}
                minTickGap={40}
                axisLine={false}
                tickLine={false}
              />
              <YAxis hide domain={["auto", "auto"]} />
              <Tooltip
                contentStyle={{
                  background: "var(--card)",
                  border: `1px solid ${colors["--border"]}`,
                  borderRadius: 12,
                  fontSize: 12,
                }}
                labelStyle={{ color: colors["--faint"] }}
                formatter={(value, name) => [wonKR(value as number), name === "equity" ? "총자산" : "실현"]}
              />
              {targetEquity !== null && (
                <ReferenceLine
                  y={targetEquity}
                  stroke={colors["--profit"]}
                  strokeDasharray="4 4"
                  strokeOpacity={0.5}
                  label={{ value: "목표", fontSize: 10, fill: colors["--faint"], position: "insideTopRight" }}
                />
              )}
              {seed > 0 && (
                <ReferenceLine y={seed} stroke={colors["--faint"]} strokeDasharray="2 4" strokeOpacity={0.6} />
              )}
              <Line type="monotone" dataKey="realized" stroke={colors["--flat"]} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="equity" stroke={colors["--profit"]} strokeWidth={2.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full items-center justify-center text-center text-xs text-faint">
            아직 자산 스냅샷이 충분치 않아요 — 매일 18:05 데스크가 돌며 한 점씩 쌓입니다.
          </div>
        )}
      </div>
    </Card>
  );
}
