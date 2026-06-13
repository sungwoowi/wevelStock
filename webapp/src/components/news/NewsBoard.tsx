"use client";

import type { NewsDigest, NewsItem, NewsTheme } from "@/lib/api";
import { cn } from "@/lib/utils";

const TONE_KR: Record<string, { label: string; cls: string }> = {
  bearish: { label: "약세 (악재 우세)", cls: "bg-down/10 text-down border-down/40" },
  lean_bearish: { label: "약세 기울기", cls: "bg-down/10 text-down border-down/40" },
  neutral: { label: "중립", cls: "bg-surface text-faint border-border" },
  lean_bullish: { label: "강세 기울기", cls: "bg-up/10 text-up border-up/40" },
  bullish: { label: "강세 (호재 우세)", cls: "bg-up/10 text-up border-up/40" },
};
const CATEGORY_KR: Record<string, string> = {
  macro_policy: "거시·통화",
  industry_trend: "산업",
  geopolitics: "지정학",
  policy_political: "정치·정책",
  corporate_events: "기업",
  market_sentiment: "시장심리",
};

function dirArrow(d: string | null): { ch: string; cls: string } | null {
  if (d === "up") return { ch: "▲", cls: "text-up" };
  if (d === "down") return { ch: "▼", cls: "text-down" };
  return null;
}

function InsightCard({
  title,
  subtitle,
  themes,
}: {
  title: string;
  subtitle: string;
  themes: NewsTheme[];
}) {
  return (
    <section className="flex flex-1 flex-col gap-2.5 rounded-2xl border border-border bg-card p-5">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-base font-bold text-foreground">{title}</h2>
        <span className="text-[11px] text-faint">{subtitle}</span>
      </div>
      {themes.length === 0 ? (
        <p className="text-sm text-faint">분류된 테마가 아직 없어요.</p>
      ) : (
        themes.map((t, i) => (
          <div key={i} className="flex flex-col gap-1 border-t border-border pt-2 first:border-t-0 first:pt-0">
            <span className="text-sm font-semibold text-foreground">{t.theme}</span>
            {t.trigger_titles.slice(0, 3).map((title, j) => (
              <span key={j} className="flex gap-1.5 text-[12px] leading-relaxed text-body">
                <span className="text-faint">·</span>
                <span className="min-w-0 truncate">{title}</span>
              </span>
            ))}
          </div>
        ))
      )}
    </section>
  );
}

function NewsRow({ item }: { item: NewsItem }) {
  const cat = (item.category && CATEGORY_KR[item.category]) || "기타";
  const arrow = dirArrow(item.direction);
  const when = (item.published_at || item.collected_at || "").slice(0, 10);
  return (
    <div className="flex items-center gap-2.5 rounded-xl bg-surface px-3 py-2">
      <span className="shrink-0 rounded-full bg-card px-2 py-0.5 text-[11px] font-semibold text-body">{cat}</span>
      {arrow && <span className={cn("shrink-0 text-[11px]", arrow.cls)}>{arrow.ch}</span>}
      <span className="min-w-0 flex-1 truncate text-[13px] text-foreground">{item.title}</span>
      <span className="shrink-0 text-[11px] text-faint">
        {item.source}
        {when ? ` · ${when.slice(5)}` : ""}
      </span>
    </div>
  );
}

export function NewsBoard({ digest, items }: { digest: NewsDigest | undefined; items: NewsItem[] }) {
  const tone = (digest && TONE_KR[digest.tone]) || TONE_KR.neutral;
  const themes = digest?.top_themes ?? [];
  const shortThemes = themes.filter((t) => t.time_axis !== "structural_trend");
  const longThemes = themes.filter((t) => t.time_axis === "structural_trend");

  return (
    <div className="mx-auto flex max-w-[1000px] flex-col gap-4">
      {/* 헤더 */}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">뉴스부 — 시장 인사이트</h1>
        <span className={cn("rounded-full border px-3 py-1 text-[11px] font-semibold", tone.cls)}>{tone.label}</span>
        {digest && <span className="text-xs text-faint">기준 {digest.date} 수집분</span>}
      </div>

      {/* 단기 / 장기 2단 */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <InsightCard title="단기 — 오늘의 테마·호재" subtitle="단발 충격 · 단기 테마" themes={shortThemes} />
        <InsightCard title="장기 — 구조 변화" subtitle="지속 흐름" themes={longThemes} />
      </div>

      {/* 수집 뉴스 리스트 */}
      <section className="flex flex-col gap-2.5 rounded-2xl border border-border bg-card p-5">
        <h2 className="text-base font-bold text-foreground">수집 뉴스 (RSS — 영향 라벨은 LLM 분류)</h2>
        {items.length === 0 ? (
          <p className="text-sm text-faint">
            수집된 뉴스가 아직 없어요 — 매일 자동 수집되고 종목·시장 영향으로 분류됩니다.
          </p>
        ) : (
          <div className="flex flex-col gap-1.5">
            {items.map((it) => (
              <NewsRow key={it.url} item={it} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
