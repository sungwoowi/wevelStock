"use client";

import { HistorySidebar } from "@/components/market/HistorySidebar";
import { MarketBoard } from "@/components/market/MarketBoard";
import { API_BASE, fetcher, type MarketHistoryItem, type MarketSnapshot } from "@/lib/api";
import { useState } from "react";
import useSWR from "swr";

type Selection = { runId: string | null; pipelineId?: string };

export default function MarketHome() {
  const [selected, setSelected] = useState<Selection>({ runId: null });

  const { data: history } = useSWR<{ items: MarketHistoryItem[] }>(
    "/api/market/history?limit=8",
    fetcher,
    { refreshInterval: 300_000, revalidateOnFocus: false },
  );

  const snapshotKey = selected.runId
    ? `/api/market/snapshot?run_id=${encodeURIComponent(selected.runId)}&pipeline_id=${selected.pipelineId ?? "market_briefing_now"}`
    : "/api/market/snapshot";
  const { data, error, isLoading } = useSWR<MarketSnapshot>(snapshotKey, fetcher, {
    refreshInterval: selected.runId ? 0 : 120_000,
    revalidateOnFocus: false,
  });

  const items = history?.items ?? [];

  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:gap-6">
      {/* 모바일: 상단 가로 스크롤 / 데스크탑: 좌측 LNB */}
      <div className="lg:hidden">
        <HistorySidebar items={items} selected={selected} onSelect={setSelected} horizontal />
      </div>
      <div className="hidden lg:block">
        <HistorySidebar items={items} selected={selected} onSelect={setSelected} />
      </div>

      <div className="min-w-0 flex-1">
        {/* ② 필 + 콘텐츠 정렬: LNB 좌측 고정, 메인은 남은 폭을 넓게 사용 */}
        {isLoading ? (
          <div className="flex flex-col gap-4">
            <div className="h-7 w-24 animate-pulse rounded bg-surface" />
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-32 animate-pulse rounded-2xl bg-card" />
            ))}
          </div>
        ) : error || !data ? (
          <div className="rounded-2xl border border-border bg-card p-6">
            <p className="text-sm font-semibold text-foreground">시황 데이터를 불러오지 못했습니다.</p>
            <p className="mt-1 text-xs text-faint">
              백엔드({API_BASE}) 연결을 확인하세요. {error ? String(error) : ""}
            </p>
          </div>
        ) : (
          <MarketBoard snap={data} />
        )}
      </div>
    </div>
  );
}
