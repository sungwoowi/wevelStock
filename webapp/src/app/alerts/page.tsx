"use client";

import { AlertsBoard } from "@/components/alerts/AlertsBoard";
import { CardSkeleton } from "@/components/desk/primitives";
import { API_BASE, fetcher, type NotificationsResp } from "@/lib/api";
import { useEffect } from "react";
import useSWR, { mutate } from "swr";

export default function AlertsPage() {
  const { data, isLoading, error } = useSWR<NotificationsResp>(
    "/api/notifications/recent?limit=50",
    fetcher,
    { refreshInterval: 60_000, revalidateOnFocus: false },
  );

  // 진입 시 전체 읽음 처리 → 종 배지(AppShell SWR limit=1)만 revalidate.
  // (limit=50 리스트는 갱신 안 함 → 미독 강조는 이번 방문 동안 유지)
  useEffect(() => {
    fetch(`${API_BASE}/api/notifications/mark-read`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ all: true }),
    })
      .then(() => mutate(`${API_BASE}/api/notifications/recent?limit=1`))
      .catch(() => {});
  }, []);

  if (isLoading) {
    return (
      <div className="mx-auto flex max-w-[900px] flex-col gap-4">
        <div className="h-9 w-32 animate-pulse rounded bg-surface" />
        <CardSkeleton h="h-20" />
        <CardSkeleton h="h-20" />
        <CardSkeleton h="h-20" />
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="mx-auto max-w-[900px] rounded-2xl border border-border bg-card p-6">
        <p className="text-sm font-semibold text-foreground">알림을 불러오지 못했습니다.</p>
        <p className="mt-1 text-xs text-faint">
          백엔드({API_BASE}) 연결을 확인하세요. {error ? String(error) : ""}
        </p>
      </div>
    );
  }

  return <AlertsBoard notifications={data.notifications} />;
}
