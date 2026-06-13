"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

const ORDER = ["light", "dark", "system"] as const;
const ICON = { light: Sun, dark: Moon, system: Monitor };
const LABEL = { light: "라이트", dark: "다크", system: "시스템" };

/** 🌓 light → dark → system 순환 토글. 헤더 배치. */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // SSR/CSR 미스매치 회피 — 마운트 전엔 중립 자리표시.
  const current = (mounted ? theme : "system") as keyof typeof ICON;
  const Icon = ICON[current] ?? Monitor;

  const cycle = () => {
    const idx = ORDER.indexOf(current as (typeof ORDER)[number]);
    setTheme(ORDER[(idx + 1) % ORDER.length]);
  };

  return (
    <button
      type="button"
      onClick={cycle}
      aria-label={`테마: ${LABEL[current] ?? "시스템"}`}
      title={`테마: ${LABEL[current] ?? "시스템"} (클릭해 전환)`}
      className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1.5 text-xs text-muted-foreground transition hover:text-foreground"
    >
      <Icon className="size-4" />
    </button>
  );
}
