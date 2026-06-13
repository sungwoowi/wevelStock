"use client";

import type { Notification } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useState } from "react";

// notification_type → 아이콘·보더·필터그룹 (정본 OWnxc: 🔴위험 / 🟢매매 / 🔵시장).
type Meta = { icon: string; border: string; group: "위험" | "매매" | "시장" };
const TYPE_META: Record<string, Meta> = {
  risk_alert: { icon: "🔴", border: "border-loss/40", group: "위험" },
  trade_signal: { icon: "🟢", border: "border-profit/40", group: "매매" },
  account_safety: { icon: "🔵", border: "border-border", group: "시장" },
  market_briefing: { icon: "🔵", border: "border-border", group: "시장" },
  flow_idea: { icon: "🔵", border: "border-border", group: "시장" },
};
const DEFAULT_META: Meta = { icon: "🔵", border: "border-border", group: "시장" };

const FILTERS = ["전체", "위험", "매매", "시장"] as const;
type Filter = (typeof FILTERS)[number];

function metaOf(n: Notification): Meta {
  return (n.notification_type && TYPE_META[n.notification_type]) || DEFAULT_META;
}

/** ISO/sqlite datetime → {dateKey:"YYYY-MM-DD", time:"HH:MM"} (문자 슬라이스, TZ 무가공). */
function parseTs(ts: string): { dateKey: string; time: string } {
  return { dateKey: ts.slice(0, 10), time: ts.slice(11, 16) };
}

function dateLabel(dateKey: string): string {
  const today = new Date().toISOString().slice(0, 10);
  const yest = new Date(Date.now() - 86_400_000).toISOString().slice(0, 10);
  if (dateKey === today) return "오늘";
  if (dateKey === yest) return "어제";
  const [, m, d] = dateKey.split("-");
  return `${Number(m)}/${d}`;
}

export function AlertsBoard({ notifications }: { notifications: Notification[] }) {
  const [filter, setFilter] = useState<Filter>("전체");

  const shown = notifications.filter((n) => filter === "전체" || metaOf(n).group === filter);

  // 날짜 그룹 (최신 우선). created_at DESC 전제.
  const groups: { key: string; items: Notification[] }[] = [];
  for (const n of shown) {
    const { dateKey } = parseTs(n.created_at);
    const last = groups[groups.length - 1];
    if (last && last.key === dateKey) last.items.push(n);
    else groups.push({ key: dateKey, items: [n] });
  }

  return (
    <div className="mx-auto flex max-w-[900px] flex-col gap-4">
      {/* 헤더 */}
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">알림</h1>
        <p className="text-sm text-faint">텔레그램 발송분과 동일 — 여기는 보관함</p>
      </div>

      {/* 필터 칩 */}
      <div className="flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={cn(
              "rounded-full px-3 py-1.5 text-xs font-semibold transition",
              filter === f
                ? "bg-secondary text-foreground"
                : "border border-border bg-card text-faint hover:text-foreground",
            )}
          >
            {f}
          </button>
        ))}
      </div>

      {/* 날짜 그룹 */}
      {shown.length === 0 ? (
        <p className="rounded-2xl border border-border bg-card p-6 text-sm text-faint">
          {notifications.length === 0
            ? "아직 알림이 없어요 — 브리핑·체결·위험 신호가 발생하면 텔레그램과 함께 여기에 쌓입니다."
            : "이 필터에 해당하는 알림이 없어요."}
        </p>
      ) : (
        groups.map((g) => (
          <div key={g.key} className="flex flex-col gap-3">
            <span className="text-[13px] font-bold text-faint">{dateLabel(g.key)}</span>
            {g.items.map((n) => {
              const meta = metaOf(n);
              const { time } = parseTs(n.created_at);
              return (
                <div
                  key={n.id}
                  className={cn(
                    "flex items-start gap-3 rounded-2xl border bg-card p-4",
                    meta.border,
                    n.is_read === 0 && "ring-1 ring-primary/20",
                  )}
                >
                  <span className="text-xl leading-none">{meta.icon}</span>
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <span className="text-sm font-bold text-foreground">{n.title}</span>
                    {n.body && <span className="text-[13px] leading-relaxed text-body">{n.body}</span>}
                  </div>
                  <span className="shrink-0 font-mono text-[11px] text-faint">{time}</span>
                </div>
              );
            })}
          </div>
        ))
      )}

      <p className="border-t border-border pt-3 text-[11px] text-faint">
        알림 정책: 🔴 즉시 · 🟢 발생 시 · 🔵 하루 정해진 횟수만. 종 배지 카운트 = 안 읽은 🔴+🟢.
      </p>
    </div>
  );
}
