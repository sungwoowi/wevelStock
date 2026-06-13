"use client";

import type { MarketHistoryItem } from "@/lib/api";
import { cn } from "@/lib/utils";

type Selection = { runId: string | null; pipelineId?: string };

function HistoryCard({
  timeLabel,
  summary,
  selected,
  isLive,
  onClick,
}: {
  timeLabel: string;
  summary: string;
  selected: boolean;
  isLive?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex shrink-0 flex-col gap-1 rounded-xl border px-3.5 py-3 text-left transition",
        "min-w-[200px] md:min-w-0",
        selected
          ? "border-primary/50 bg-primary/10"
          : "border-transparent bg-card hover:bg-accent",
      )}
    >
      <span className={cn("text-[13px] font-bold leading-tight", selected ? "text-primary" : "text-foreground")}>
        {isLive ? "지금 · 라이브" : timeLabel}
      </span>
      <span className="truncate text-[11px] leading-tight text-muted-foreground">
        {selected ? "← 보는 중" : summary}
      </span>
    </button>
  );
}

export function HistorySidebar({
  items,
  selected,
  onSelect,
  horizontal,
}: {
  items: MarketHistoryItem[];
  selected: Selection;
  onSelect: (sel: Selection) => void;
  horizontal?: boolean;
}) {
  const liveSelected = selected.runId === null;
  return (
    <aside
      className={cn(
        "rounded-2xl border border-border bg-sidebar",
        horizontal
          ? "flex gap-2.5 overflow-x-auto p-3"
          : "flex w-72 shrink-0 flex-col gap-2.5 self-start p-4 lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto",
      )}
    >
      {!horizontal && (
        <div className="mb-1 flex items-baseline justify-between border-b border-border/70 px-1 pb-3">
          <h2 className="text-[13px] font-bold text-body">최근 스냅샷</h2>
          <span className="text-[11px] text-faint">{items.length + 1}개 시점</span>
        </div>
      )}
      <HistoryCard
        timeLabel="지금 · 라이브"
        summary="실시간 집계 (최신 DB)"
        selected={liveSelected}
        isLive
        onClick={() => onSelect({ runId: null })}
      />
      {items.map((it) => (
        <HistoryCard
          key={it.run_id}
          timeLabel={it.time_label}
          summary={it.summary}
          selected={selected.runId === it.run_id}
          onClick={() => onSelect({ runId: it.run_id, pipelineId: it.pipeline_id })}
        />
      ))}
    </aside>
  );
}
