export function VerdictBadge({ verdict }: { verdict: string }) {
  const colorMap: Record<string, string> = {
    compliant: "bg-emerald-900/40 text-emerald-300 border-emerald-700",
    positive: "bg-emerald-900/40 text-emerald-300 border-emerald-700",
    neutral: "bg-slate-800/60 text-slate-200 border-slate-600",
    warning: "bg-amber-900/40 text-amber-300 border-amber-700",
    caution: "bg-amber-900/40 text-amber-300 border-amber-700",
    violation: "bg-red-900/40 text-red-300 border-red-700",
    alert: "bg-red-900/60 text-red-200 border-red-600",
  };
  const cls = colorMap[verdict] || "bg-neutral-800 text-neutral-300 border-neutral-700";
  return (
    <span className={`inline-block rounded-md border px-2 py-0.5 text-xs font-mono ${cls}`}>
      {verdict}
    </span>
  );
}
