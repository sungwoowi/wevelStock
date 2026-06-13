"use client";

import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

/** 데스크 공용 카드 컨테이너 (정본 .pen: rounded-2xl·border·bg-card). */
export function Card({
  title,
  subtitle,
  action,
  children,
  className,
}: {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("rounded-2xl border border-border bg-card p-5 md:p-6", className)}>
      {(title || action) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-baseline gap-3">
            {title && <h2 className="text-lg font-bold text-foreground">{title}</h2>}
            {subtitle && <span className="text-xs text-faint">{subtitle}</span>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

/** 라벨·큰값·부연 지표 카드 (회고 KPI·성과지표·계좌요약 공용). */
export function Metric({
  label,
  value,
  valueClass,
  sub,
}: {
  label: string;
  value: ReactNode;
  valueClass?: string;
  sub?: ReactNode;
}) {
  return (
    <div className="flex flex-1 flex-col gap-1.5 rounded-2xl border border-border bg-card p-4">
      <span className="text-xs text-faint">{label}</span>
      <span className={cn("font-mono text-xl font-bold leading-tight md:text-2xl", valueClass ?? "text-foreground")}>
        {value}
      </span>
      {sub && <span className="text-[11px] text-faint">{sub}</span>}
    </div>
  );
}

/** 트랙 칩 — A=중장기(파랑) / B=단기(amber). */
export function TrackChip({ track }: { track: string }) {
  const a = track === "A";
  return (
    <span
      className={cn(
        "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold",
        a ? "bg-info/15 text-info" : "bg-amber-bg text-amber",
      )}
    >
      {a ? "중장기" : "단기"}
    </span>
  );
}

/** 투입 비중 진행바. */
export function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface">
      <div className="h-full rounded-full bg-profit" style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
    </div>
  );
}

/** 둥근 칩 배지. tone = 상태색. */
export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "profit" | "loss" | "amber" | "neutral" }) {
  const cls =
    tone === "profit"
      ? "bg-profit/10 text-profit"
      : tone === "loss"
        ? "bg-loss/10 text-loss"
        : tone === "amber"
          ? "bg-amber-bg text-amber"
          : "bg-surface text-faint";
  return <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold", cls)}>{children}</span>;
}

export function EmptyNote({ children }: { children: ReactNode }) {
  return <p className="text-sm leading-relaxed text-faint">{children}</p>;
}

export function CardSkeleton({ h = "h-40" }: { h?: string }) {
  return <div className={cn("animate-pulse rounded-2xl bg-card", h)} />;
}
