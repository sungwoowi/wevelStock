"use client";

import { DeskBoard } from "@/components/desk/DeskBoard";
import { CardSkeleton } from "@/components/desk/primitives";
import {
  API_BASE,
  fetcher,
  type AccountItem,
  type DeskFeed,
  type KpiSummary,
  type WealthCurve,
  type WealthProgress,
} from "@/lib/api";
import useSWR from "swr";

const OPTS = { refreshInterval: 120_000, revalidateOnFocus: false } as const;

export default function DeskHome() {
  const { data: curve } = useSWR<WealthCurve>("/api/wealth/curve", fetcher, OPTS);
  const { data: progress } = useSWR<WealthProgress>("/api/wealth/progress", fetcher, OPTS);
  const { data: accounts, isLoading, error } = useSWR<{ items: AccountItem[] }>("/api/accounts", fetcher, OPTS);
  const { data: kpi } = useSWR<KpiSummary>("/api/guidance/kpi", fetcher, OPTS);
  const { data: feed } = useSWR<DeskFeed>("/api/desk/feed", fetcher, OPTS);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-5">
        <div className="h-9 w-64 animate-pulse rounded bg-surface" />
        <CardSkeleton h="h-72" />
        <CardSkeleton h="h-28" />
        <CardSkeleton h="h-40" />
      </div>
    );
  }
  if (error || !accounts) {
    return (
      <div className="rounded-2xl border border-border bg-card p-6">
        <p className="text-sm font-semibold text-foreground">데스크 데이터를 불러오지 못했습니다.</p>
        <p className="mt-1 text-xs text-faint">
          백엔드({API_BASE}) 연결을 확인하세요. {error ? String(error) : ""}
        </p>
      </div>
    );
  }

  return (
    <DeskBoard
      curve={curve}
      progress={progress}
      accounts={accounts.items}
      kpi={kpi}
      feed={feed}
    />
  );
}
