"use client";

import { CardSkeleton } from "@/components/desk/primitives";
import { WatchlistBoard } from "@/components/watchlist/WatchlistBoard";
import { API_BASE, fetcher, type WatchlistFunnel } from "@/lib/api";
import useSWR from "swr";

const OPTS = { refreshInterval: 120_000, revalidateOnFocus: false } as const;

export default function WatchlistPage() {
  const { data: funnel, isLoading, error } = useSWR<WatchlistFunnel>(
    "/api/watchlist/funnel",
    fetcher,
    OPTS,
  );

  if (isLoading) {
    return (
      <div className="flex flex-col gap-5">
        <div className="h-9 w-72 animate-pulse rounded bg-surface" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <CardSkeleton h="h-96" />
          <CardSkeleton h="h-96" />
        </div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="rounded-2xl border border-border bg-card p-6">
        <p className="text-sm font-semibold text-foreground">관심종목 데이터를 불러오지 못했습니다.</p>
        <p className="mt-1 text-xs text-faint">
          백엔드({API_BASE}) 연결을 확인하세요. {error ? String(error) : ""}
        </p>
      </div>
    );
  }

  return <WatchlistBoard funnel={funnel} />;
}
