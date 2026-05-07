"use client";
import useSWR from "swr";
import { fetcher, Notification } from "@/lib/api";

export function AlertList() {
  const { data, isLoading } = useSWR<{ notifications: Notification[] }>(
    "/api/notifications/recent?limit=10",
    fetcher,
    { refreshInterval: 5000 }
  );

  const items = data?.notifications || [];

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-5">
      <h2 className="text-lg font-semibold">최근 자동 푸시 알림</h2>
      <p className="text-xs text-neutral-500 mb-3">
        notifications_log · 파이프라인 notify stage 가 텔레그램에 보낸 자동 알림만 (봇 명령 응답은 위 "브리핑 이력")
      </p>
      {isLoading && <p className="text-sm text-neutral-500">로딩…</p>}
      {!isLoading && items.length === 0 && (
        <p className="text-sm text-neutral-500">알림 없음</p>
      )}
      <ul className="space-y-3">
        {items.map((n) => (
          <li key={n.id} className="border-b border-neutral-800 pb-3 last:border-0">
            <div className="flex items-center gap-2 text-xs text-neutral-500 mb-1 font-mono">
              <span>{n.created_at.slice(0, 16)}</span>
              <span>·</span>
              <span>{n.team_id}</span>
              <span>·</span>
              <LevelBadge level={n.level} />
              <span className="ml-auto">{n.channel}</span>
            </div>
            <div className="text-sm font-semibold text-neutral-200">{n.title}</div>
            {n.body && (
              <div className="text-sm text-neutral-400 whitespace-pre-wrap">
                {n.body}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function LevelBadge({ level }: { level: string }) {
  const color = {
    info: "text-sky-400",
    warning: "text-amber-400",
    critical: "text-red-400",
  }[level] || "text-neutral-400";
  return <span className={color}>{level}</span>;
}
