"use client";

import type { MarketSnapshot, PricePoint, SectorRsItem } from "@/lib/api";
import { changeClass, fmtNum, fmtPct, joM, tradeAmt, wonB, wonM } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ChevronDown } from "lucide-react";
import { useState } from "react";

function isPoint(v: unknown): v is PricePoint {
  return typeof v === "object" && v !== null && !("error" in (v as object));
}
function rec(v: unknown): Record<string, unknown> {
  return (typeof v === "object" && v !== null ? v : {}) as Record<string, unknown>;
}

// ── 공통 UI ────────────────────────────────────────────────────────────────
function Card({
  title,
  subtitle,
  children,
  accent,
  className,
}: {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  accent?: "amber" | "info" | "none";
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-2xl border bg-card p-5",
        accent === "amber" && "border-amber/70",
        accent === "info" && "border-info/70",
        (!accent || accent === "none") && "border-border",
        className,
      )}
    >
      {title && (
        <div className="mb-3 flex items-baseline justify-between gap-2">
          <h2 className="text-base font-bold text-foreground">{title}</h2>
          {subtitle && <span className="text-xs text-faint">{subtitle}</span>}
        </div>
      )}
      {children}
    </section>
  );
}

function Pending({ label = "수집 대기" }: { label?: string }) {
  return <p className="text-sm text-faint">{label}</p>;
}

// ── 한 줄 평 ─────────────────────────────────────────────────────────────────
function OneLiner({ snap }: { snap: MarketSnapshot }) {
  const [open, setOpen] = useState(false);
  const mv = snap.market_view;
  if (!mv?.one_liner) {
    return (
      <Card accent="amber">
        <Pending label="오늘 시장관(한 줄 평) 미수집 — 장 마감 후 집계됩니다." />
      </Card>
    );
  }
  const reasons = mv.reasons ?? [];
  return (
    <Card accent="amber">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-amber-bg px-2.5 py-0.5 text-xs font-medium text-amber">
          {mv.regime} · 진입 {mv.entry_posture}
        </span>
        <span className="text-xs text-faint">신뢰도 {mv.confidence}</span>
      </div>
      <p className="text-lg font-semibold leading-relaxed text-foreground">{mv.one_liner}</p>

      {reasons.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className={cn(
              "mt-3 flex w-full items-center justify-between gap-2 rounded-xl border px-3.5 py-2.5 text-sm font-semibold transition",
              open
                ? "border-info/50 bg-info/10 text-info"
                : "border-info/40 bg-info/5 text-info hover:bg-info/10",
            )}
          >
            <span>브리핑 상세 {open ? "접기" : "펼쳐보기"}</span>
            <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} />
          </button>
          {open && (
            <ul className="mt-3 space-y-2 border-t border-border pt-3">
              {reasons.map((r, i) => (
                <li key={i} className="flex gap-2 text-sm leading-relaxed text-body">
                  <span className="text-info">·</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Card>
  );
}

// ── 국내 지수 ────────────────────────────────────────────────────────────────
function KrIndexRow({ name, point, suffix, amount }: { name: string; point: unknown; suffix?: string; amount?: unknown }) {
  const value = isPoint(point) ? point.value : null;
  const chg = isPoint(point) ? point.change_pct : null;
  return (
    <div className="flex items-baseline justify-between gap-3 border-t border-border pt-2.5 first:border-t-0 first:pt-0">
      <div className="flex items-baseline gap-2">
        <span className="text-sm font-semibold text-foreground">{name}</span>
        {suffix && <span className="text-xs text-faint">{suffix}</span>}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-base font-bold text-foreground">{fmtNum(value, 2)}</span>
        <span className={cn("font-mono text-sm font-semibold", changeClass(chg))}>{fmtPct(chg)}</span>
        {amount !== undefined && (
          <span className="ml-1 whitespace-nowrap text-right text-xs text-faint">거래대금 {joM(amount)}</span>
        )}
      </div>
    </div>
  );
}

function KrIndices({ snap }: { snap: MarketSnapshot }) {
  const idx = rec(snap.kr_indices);
  const kospi = rec(idx.kospi);
  const kosdaq = rec(idx.kosdaq);
  if (!isPoint(idx.kospi) && !isPoint(idx.kosdaq)) {
    return (
      <Card title="🇰🇷 국내 지수">
        <Pending />
      </Card>
    );
  }
  return (
    <Card title="🇰🇷 국내 지수" subtitle="KRX 정규장 전일 종가 대비">
      <div className="flex flex-col gap-2.5">
        <KrIndexRow name="KOSPI" point={idx.kospi} amount={kospi.trade_amount} />
        <KrIndexRow name="KOSDAQ" point={idx.kosdaq} amount={kosdaq.trade_amount} />
        <KrIndexRow name="KOSPI200" point={idx.kospi200} suffix="선물 기초" />
      </div>
    </Card>
  );
}

// ── 참고 지표 (타일 + 등락 종목 수) ──────────────────────────────────────────
function Tile({ label, value, pct }: { label: string; value: string; pct: number | null }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-xl bg-surface p-3">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <span className={cn("font-mono text-[15px] font-bold leading-tight", changeClass(pct))}>
        {value}
        {pct !== null && <span className="ml-1 text-xs">{fmtPct(pct)}</span>}
      </span>
    </div>
  );
}

function pointTile(label: string, p: unknown, decimals = 0): React.ReactElement {
  const v = isPoint(p) ? (p.price ?? p.value) : null;
  const pct = isPoint(p) ? (p.change_pct ?? null) : null;
  return <Tile key={label} label={label} value={fmtNum(v, decimals)} pct={pct ?? null} />;
}
function pctOnlyTile(label: string, pct: unknown): React.ReactElement {
  const v = typeof pct === "number" ? pct : null;
  return <Tile key={label} label={label} value={v !== null ? fmtPct(v) : "—"} pct={null} />;
}

function BreadthRow({ name, macro }: { name: string; macro: Record<string, unknown> }) {
  const adv = typeof macro.advancing === "number" ? macro.advancing : 0;
  const flat = typeof macro.unchanged === "number" ? macro.unchanged : 0;
  const dec = typeof macro.declining === "number" ? macro.declining : 0;
  const total = adv + flat + dec || 1;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-foreground">{name}</span>
        <div className="flex items-center gap-2.5 font-mono text-xs">
          <span className="text-up">▲{fmtNum(adv)}</span>
          <span className="text-flat">─{fmtNum(flat)}</span>
          <span className="text-down">▼{fmtNum(dec)}</span>
        </div>
      </div>
      {/* 비례 막대 */}
      <div className="flex h-1.5 overflow-hidden rounded-full bg-surface">
        <div className="bg-up" style={{ width: `${(adv / total) * 100}%` }} />
        <div className="bg-flat" style={{ width: `${(flat / total) * 100}%` }} />
        <div className="bg-down" style={{ width: `${(dec / total) * 100}%` }} />
      </div>
    </div>
  );
}

function Indicators({ snap }: { snap: MarketSnapshot }) {
  const ov = rec(snap.overnight);
  const um = rec(snap.us_macro);
  const macro = rec(snap.market_macro);
  const fg = rec(snap.fear_greed);
  const fgScore = typeof fg.score === "number" ? fg.score : null;
  const k200night = rec(rec(snap.night_futures).kospi200_cme_night);

  return (
    <Card title="참고 지표" subtitle="전일 종가 대비">
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        {pointTile("원/달러", ov.usdkrw)}
        {pointTile("달러인덱스", ov.dxy, 2)}
        {pointTile("나스닥", ov.nasdaq)}
        {pointTile("S&P500", ov.sp500)}
        {pointTile("필라델피아 반도체", ov.sox)}
        {pointTile("VIX", ov.vix, 2)}
        <Tile label="공포·탐욕" value={fgScore !== null ? String(fgScore) : "—"} pct={null} />
        {pointTile("미 10년물", ov.us_10y, 2)}
        {pointTile("WTI", ov.wti, 2)}
        {pctOnlyTile("브렌트유", um.brent_change_pct)}
        {pointTile("금", ov.gold, 1)}
        {/* 야간선물 2종 */}
        <Tile
          label="KOSPI200 야간선물"
          value={fmtNum(k200night.price, 2)}
          pct={typeof k200night.change_pct === "number" ? k200night.change_pct : null}
        />
        {pctOnlyTile("나스닥 야간선물", um.nq_futures_change_pct)}
      </div>

      {/* 등락 종목 수 */}
      <div className="mt-5 border-t border-border pt-4">
        <div className="mb-3 flex items-baseline justify-between">
          <h3 className="text-sm font-bold text-foreground">등락 종목 수</h3>
          <span className="text-xs text-faint">장 마감 기준 · 시장 폭(breadth)</span>
        </div>
        <div className="flex flex-col gap-3.5">
          <BreadthRow name="코스피" macro={rec(macro.KOSPI)} />
          <BreadthRow name="코스닥" macro={rec(macro.KOSDAQ)} />
        </div>
      </div>
    </Card>
  );
}

// ── 수급 ─────────────────────────────────────────────────────────────────────
function SupplyBlock({ label, supply, futures }: { label: string; supply: unknown; futures?: boolean }) {
  if (!isPoint(supply)) return null;
  const s = supply as Record<string, unknown>;
  const rows: [string, string][] = futures
    ? [
        ["외인", wonB(s.foreign_net_amount_b)],
        ["기관", wonB(s.institution_net_amount_b)],
        ["개인", wonB(s.individual_net_amount_b)],
      ]
    : [
        ["외인", wonM(s.foreign_net_amount_m)],
        ["기관", wonM(s.institution_net_amount_m)],
        ["개인", wonM(s.individual_net_amount_m)],
      ];
  return (
    <div className="flex flex-1 flex-col gap-1.5 rounded-xl bg-surface p-3.5">
      <span className="text-xs font-semibold text-muted-foreground">{label}</span>
      {rows.map(([k, v]) => (
        <div key={k} className="flex items-center justify-between text-sm">
          <span className="text-faint">{k}</span>
          <span className={cn("font-mono font-semibold", v.startsWith("+") ? "text-up" : v === "—" ? "text-flat" : "text-down")}>
            {v}
          </span>
        </div>
      ))}
    </div>
  );
}

function Supply({ snap }: { snap: MarketSnapshot }) {
  const sup = rec(snap.kr_supply);
  const fut = snap.kr_futures_supply;
  const hasAny = isPoint(sup.kospi) || isPoint(sup.kosdaq) || isPoint(fut);
  return (
    <Card title="수급" subtitle="5주체 순매수 · 억원">
      {hasAny ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <SupplyBlock label="코스피" supply={sup.kospi} />
          <SupplyBlock label="코스닥" supply={sup.kosdaq} />
          <SupplyBlock label="KOSPI200 선물" supply={fut} futures />
        </div>
      ) : (
        <Pending />
      )}
    </Card>
  );
}

// ── 거래대금 상위 + 강세 섹터 ───────────────────────────────────────────────
type LeadRow = { name?: string; ticker?: string; change_pct?: number; trade_amount?: number; cap_tier?: string; match?: string };

function TopVolume({ snap }: { snap: MarketSnapshot }) {
  const lead = rec(snap.kr_leading);
  const rows: LeadRow[] = [
    ...((lead.kospi as LeadRow[]) ?? []),
    ...((lead.kosdaq as LeadRow[]) ?? []),
  ]
    .filter((r) => r && typeof r.trade_amount === "number")
    .sort((a, b) => (b.trade_amount ?? 0) - (a.trade_amount ?? 0))
    .slice(0, 5);
  return (
    <Card title="당일 거래대금 상위" className="flex-1">
      {rows.length === 0 ? (
        <Pending />
      ) : (
        <div className="flex flex-col gap-1">
          {rows.map((r, i) => (
            <div key={`${r.ticker}-${i}`} className="flex items-center gap-2.5 py-1">
              <span className="w-4 shrink-0 font-mono text-xs font-bold text-faint">{i + 1}</span>
              <span className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground">{r.name ?? "—"}</span>
              <span className={cn("shrink-0 font-mono text-sm font-bold", changeClass(r.change_pct))}>
                {fmtPct(r.change_pct ?? null)}
              </span>
              <span className="w-24 shrink-0 truncate text-right text-xs text-faint">
                {tradeAmt(r.trade_amount)}
                {r.match ? ` · ${r.match}` : ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function StrongSectors({ snap }: { snap: MarketSnapshot }) {
  const sectors = rec(snap.kr_sectors);
  const strong = (sectors.strong as { name?: string; ticker?: string; change_pct?: number }[]) ?? [];
  const rs = [...(snap.sector_rs ?? [])]
    .filter((s) => typeof s.rs_score === "number")
    .sort((a, b) => (b.rs_score ?? 0) - (a.rs_score ?? 0))
    .slice(0, 3);
  return (
    <Card title="강세 섹터" subtitle="ETF +1% 이상" className="flex-1">
      {strong.length === 0 ? (
        <p className="text-sm text-faint">오늘 +1% 이상 섹터 ETF 없음</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {strong.map((s) => (
            <span
              key={s.ticker}
              className="inline-flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/10 px-3 py-1 text-xs"
            >
              <span className="font-medium text-foreground">{s.name}</span>
              <span className="font-mono font-semibold text-up">{fmtPct(s.change_pct ?? null)}</span>
            </span>
          ))}
        </div>
      )}
      {rs.length > 0 && (
        <p className="mt-3 border-t border-border pt-3 text-xs text-faint">
          섹터 RS 상위(60일):{" "}
          {rs.map((s, i) => (
            <span key={s.etf_ticker}>
              {i > 0 && " · "}
              <span className="text-body">{s.sector}</span>{" "}
              <span className="font-mono text-foreground">{fmtNum(s.rs_score, 1)}</span>
            </span>
          ))}
        </p>
      )}
    </Card>
  );
}

// ── 메인 ─────────────────────────────────────────────────────────────────────
export function MarketBoard({ snap }: { snap: MarketSnapshot }) {
  const srcKr = snap.source_map?.kr;
  const srcUs = snap.source_map?.us;
  const historical = snap.is_historical;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-bold tracking-tight">시황</h1>
          {historical && (
            <span className="rounded-full border border-amber/60 bg-amber-bg px-2 py-0.5 text-[11px] font-medium text-amber">
              과거 시점
            </span>
          )}
        </div>
        <span className="text-xs text-faint">
          {snap.fetched_at_iso?.replace("T", " ").slice(0, 16)}
          {!historical && srcKr && ` · 한국 ${srcKr === "db" ? "DB" : "수집"} / 미국 ${srcUs === "db" ? "DB" : "수집"}`}
        </span>
      </div>
      <OneLiner snap={snap} />
      <KrIndices snap={snap} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TopVolume snap={snap} />
        <StrongSectors snap={snap} />
      </div>
      <Supply snap={snap} />
      <Indicators snap={snap} />
    </div>
  );
}
