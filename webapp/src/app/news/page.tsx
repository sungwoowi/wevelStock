"use client";

import { CardSkeleton } from "@/components/desk/primitives";
import { NewsBoard } from "@/components/news/NewsBoard";
import { API_BASE, fetcher, type NewsDigest, type NewsItemsResp } from "@/lib/api";
import useSWR from "swr";

const OPTS = { refreshInterval: 300_000, revalidateOnFocus: false } as const;

export default function NewsPage() {
  const { data: digest } = useSWR<NewsDigest>("/api/news/digest", fetcher, OPTS);
  const { data: items, isLoading, error } = useSWR<NewsItemsResp>("/api/news/items?limit=40", fetcher, OPTS);

  if (isLoading) {
    return (
      <div className="mx-auto flex max-w-[1000px] flex-col gap-4">
        <div className="h-9 w-72 animate-pulse rounded bg-surface" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <CardSkeleton h="h-40" />
          <CardSkeleton h="h-40" />
        </div>
        <CardSkeleton h="h-48" />
      </div>
    );
  }
  if (error || !items) {
    return (
      <div className="mx-auto max-w-[1000px] rounded-2xl border border-border bg-card p-6">
        <p className="text-sm font-semibold text-foreground">뉴스를 불러오지 못했습니다.</p>
        <p className="mt-1 text-xs text-faint">
          백엔드({API_BASE}) 연결을 확인하세요. {error ? String(error) : ""}
        </p>
      </div>
    );
  }

  return <NewsBoard digest={digest} items={items.items} />;
}
