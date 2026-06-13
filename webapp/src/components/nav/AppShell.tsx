"use client";

import { API_BASE } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Bell, HelpCircle, LineChart, MessageSquare, Newspaper, Wallet } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import useSWR from "swr";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

type Tab = {
  href: string;
  label: string;
  icon: typeof LineChart;
  active: boolean; // 1차 활성 여부 (placeholder 면 false)
};

const TABS: Tab[] = [
  { href: "/", label: "시황", icon: LineChart, active: true },
  { href: "/desk", label: "가상매매", icon: Wallet, active: true },
  { href: "/chat", label: "채팅", icon: MessageSquare, active: true },
  { href: "/news", label: "뉴스", icon: Newspaper, active: true },
  { href: "/alerts", label: "알림", icon: Bell, active: true },
];

function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function FractalMark({ className }: { className?: string }) {
  // 작은 파동 → 큰 파동 → 시그널 도트 (FractalSignal 로고 마크).
  return (
    <svg viewBox="0 0 28 28" className={className} fill="none" aria-hidden>
      <path
        d="M2 17c2.2 0 2.2-3 4.4-3s2.2 3 4.4 3 2.2-6 4.4-6 2.2 6 4.4 6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="25" cy="9" r="2.4" fill="currentColor" />
    </svg>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data } = useSWR<{ unread_count: number }>(
    `${API_BASE}/api/notifications/recent?limit=1`,
    (url: string) => fetch(url).then((r) => r.json()),
    { refreshInterval: 60_000 },
  );
  const unread = data?.unread_count ?? 0;

  // R&D 페이지(/dev, 미이전 /production-chat)는 자체 풀폭 레이아웃 유지 — production 크롬 미적용.
  if (pathname.startsWith("/dev") || pathname.startsWith("/production-chat")) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* ── 글로벌 네비 (PC: 상단 / 모바일: 상단 축약) ── */}
      <header className="sticky top-0 z-40 flex h-16 items-center gap-6 border-b border-border bg-background/95 px-4 backdrop-blur md:px-8">
        <Link href="/" className="flex items-center gap-2">
          <FractalMark className="size-6 text-primary" />
          <span className="text-base font-bold tracking-tight">FractalSignal</span>
        </Link>

        {/* PC 탭 */}
        <nav className="hidden items-center gap-1 md:flex">
          {TABS.map((t) => {
            const active = isActivePath(pathname, t.href);
            return (
              <Link
                key={t.href}
                href={t.href}
                className={cn(
                  "rounded-full px-3 py-1.5 text-sm transition",
                  active
                    ? "bg-secondary font-semibold text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                  !t.active && "opacity-60",
                )}
              >
                {t.label}
                {!t.active && <span className="ml-1 text-[10px] text-faint">곧</span>}
              </Link>
            );
          })}
        </nav>

        <div className="flex-1" />

        <Link
          href="/guide"
          aria-label="가이드"
          className="hidden items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1.5 text-xs text-muted-foreground transition hover:text-foreground md:inline-flex"
        >
          <HelpCircle className="size-4" />
        </Link>
        <Link
          href="/alerts"
          aria-label="알림"
          className="relative inline-flex items-center rounded-full border border-border bg-card p-1.5 text-muted-foreground transition hover:text-foreground"
        >
          <Bell className="size-4" />
          {unread > 0 && (
            <span className="absolute -right-1 -top-1 inline-flex min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold leading-4 text-white">
              {unread > 99 ? "99+" : unread}
            </span>
          )}
        </Link>
        <ThemeToggle />
      </header>

      {/* ── 본문 (모바일 하단 탭바 높이만큼 패딩) ── */}
      <main className="mx-auto w-full max-w-7xl px-4 pb-24 pt-5 md:px-8 md:pb-10">
        {children}
      </main>

      {/* ── 모바일 하단 탭바 ── */}
      <nav className="fixed inset-x-0 bottom-0 z-40 flex h-16 items-stretch border-t border-border bg-background/95 backdrop-blur md:hidden">
        {TABS.map((t) => {
          const active = isActivePath(pathname, t.href);
          const Icon = t.icon;
          return (
            <Link
              key={t.href}
              href={t.href}
              className={cn(
                "flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] transition",
                active ? "text-primary" : "text-muted-foreground",
              )}
            >
              <Icon className="size-5" />
              <span>{t.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
