"use client";

import { ChatColumn } from "@/components/chat/ChatColumn";
import { fetcher, type MarketSnapshot } from "@/lib/api";
import useSWR from "swr";

/** 채팅 상단 시장 한 줄 카드 — market_view.one_liner 재사용 (없으면 graceful). */
function MarketContextCard() {
  const { data } = useSWR<MarketSnapshot>("/api/market/snapshot", fetcher, {
    refreshInterval: 300_000,
    revalidateOnFocus: false,
  });
  const oneLiner = data?.market_view?.one_liner;
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <span className="text-xs font-semibold text-faint">오늘 시장</span>
      <p className="mt-1 text-sm leading-relaxed text-body">
        {oneLiner || "오늘 시장 한 줄 평은 장 마감 후 집계됩니다 — 무엇이든 물어보세요."}
      </p>
    </div>
  );
}

export default function ChatPage() {
  return <ChatColumn header={<MarketContextCard />} />;
}
