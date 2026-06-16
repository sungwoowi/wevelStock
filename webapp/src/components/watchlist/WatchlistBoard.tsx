"use client";

import type {
  WatchlistBasket,
  WatchlistConceptGroup,
  WatchlistFunnel,
  WatchlistItem,
  WatchlistStageGroup,
  WatchlistTrack,
} from "@/lib/api";
import { eokKR, fmtPct, volKR, wonKR } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useState } from "react";
import Link from "next/link";
import { stageKR, stageTone } from "@/components/desk/labels";
import { Badge, Card, EmptyNote } from "@/components/desk/primitives";

const TRACK_STAGES = ["entering", "watching"] as const;

function changeClass(v: number | null): string {
  if (v === null || v === undefined || v === 0) return "text-flat";
  return v > 0 ? "text-up" : "text-down"; // 한국식 (상승=빨강·하락=파랑)
}

/** 후보 출처 라벨 — 교집합(둘 다)이면 강조 타일, 아니면 단일 칩. */
function SourceTag({ it }: { it: WatchlistItem }) {
  if (it.is_dual) {
    return (
      <span className="shrink-0 rounded-full bg-profit/15 px-2 py-0.5 text-[10px] font-bold text-profit">
        거래대금+거래량
      </span>
    );
  }
  const s = it.sources[0];
  const cls = s === "trade_value" ? "bg-info/15 text-info" : "bg-amber-bg text-amber";
  return (
    <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold", cls)}>
      {s === "trade_value" ? "거래대금" : s === "volume_bull" ? "거래량" : s}
    </span>
  );
}

function ScenarioDetail({ it }: { it: WatchlistItem }) {
  const lines: string[] = [];
  if (it.funnel_stage === "watching") {
    if (it.watching_entry) lines.push(`대기 진입가 ${wonKR(it.watching_entry)}${it.watching_label ? ` (${it.watching_label})` : ""}`);
    if (it.stage_scenario) lines.push(`조건: ${it.stage_scenario}`);
  } else if (it.funnel_stage === "entering") {
    if (it.scaled_buy?.length) lines.push("분할매수 " + it.scaled_buy.map((l) => `${l.leg}차 ${wonKR(l.price)}(${Math.round(l.ratio * 100)}%)`).join(" → "));
    else if (it.entry_price) lines.push(`진입 ${wonKR(it.entry_price)}`);
    if (it.stop_loss) lines.push(`손절 ${wonKR(it.stop_loss)}`);
    if (it.target_prices?.length) lines.push("목표 " + it.target_prices.map((t) => wonKR(t)).join(" · "));
    if (it.stage_scenario) lines.push(it.stage_scenario);
  }
  if (lines.length === 0) lines.push("아직 매매 시나리오 없음 — 단계 승격 시 진입가·분할·손절·목표가 채워집니다.");
  return (
    <div className="flex flex-col gap-0.5 border-l-2 border-border py-1.5 pl-3 text-[11px] text-body">
      {lines.map((l, i) => <span key={i}>{l}</span>)}
      <Link href={`/chat?ticker=${it.ticker}`} className="mt-0.5 text-[11px] text-info hover:underline">
        이 종목 채팅으로 이어가기 →
      </Link>
    </div>
  );
}

function ItemRow({ it }: { it: WatchlistItem }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-col border-b border-border last:border-0">
      <button type="button" onClick={() => setOpen((v) => !v)} className="flex items-center gap-2 py-2 text-left">
        <span className="w-7 shrink-0 text-right font-mono text-[11px] text-faint">{it.rank ?? "—"}</span>
        <span className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground">{it.display_name || it.ticker}</span>
        <SourceTag it={it} />
        {it.funnel_stage === "watching" && it.watching_entry ? (
          <span className="shrink-0 font-mono text-[11px] text-body">대기 {wonKR(it.watching_entry)}</span>
        ) : it.funnel_stage === "entering" && it.entry_price ? (
          <span className="shrink-0 font-mono text-[11px] text-body">{wonKR(it.entry_price)}</span>
        ) : (
          <span className={cn("w-14 shrink-0 text-right font-mono text-[11px]", changeClass(it.change_pct))}>{fmtPct(it.change_pct)}</span>
        )}
        <span className="w-3 shrink-0 text-center text-[10px] text-faint">{open ? "▾" : "▸"}</span>
      </button>
      {open && <ScenarioDetail it={it} />}
    </div>
  );
}

/** 단계/컨셉 그룹 공용 (제목·개수·접기) */
function Group({ title, tone, count, items, defaultOpen }: {
  title: string; tone: "profit" | "amber" | "neutral"; count: number; items: WatchlistItem[]; defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (count === 0) return null;
  return (
    <div className="flex flex-col border-t border-border first:border-t-0">
      <button type="button" onClick={() => setOpen((v) => !v)} className="flex items-center gap-2 py-2 text-left">
        <Badge tone={tone}>{title}</Badge>
        <span className="text-xs font-semibold text-faint">{count}</span>
        <span className="ml-auto text-xs text-info">{open ? "접기" : "펼치기"}</span>
      </button>
      {open && <div className="flex flex-col">{items.map((it) => <ItemRow key={it.ticker} it={it} />)}</div>}
    </div>
  );
}

/** 트랙 카드 — 진입·매수대기만 (관심은 공용). */
function TrackCard({ track }: { track: WatchlistTrack }) {
  const total = track.stages.reduce((n, s) => n + s.count, 0);
  return (
    <Card title={`${track.label} (Track ${track.track})`} subtitle={`${total}종목 · 진입·매수대기`}>
      {total === 0 ? (
        <EmptyNote>아직 골라서 진입·매수대기로 올라온 종목이 없어요. (아래 관심에서 승격됩니다)</EmptyNote>
      ) : (
        <div className="flex flex-col">
          {TRACK_STAGES.map((s) => {
            const g = track.stages.find((x) => x.stage === s) as WatchlistStageGroup | undefined;
            return g ? <Group key={s} title={stageKR(s)} tone={stageTone(s)} count={g.count} items={g.items} defaultOpen /> : null;
          })}
        </div>
      )}
    </Card>
  );
}

const CONCEPT_TONE: Record<string, "profit" | "amber" | "neutral"> = {
  leader: "profit", pullback: "amber", base: "neutral", unknown: "neutral",
};

/** 관심 = 공용 1곳. 컨셉(주도주/눌림/바닥)별 분류. */
function InterestSection({ interest }: { interest: WatchlistFunnel["interest"] }) {
  return (
    <Card title="관심 (공용)" subtitle={`${interest.count}종목 · 컨셉 분류 · 아직 트랙 미배정`}>
      {interest.count === 0 ? (
        <EmptyNote>관심 후보가 없어요 — 바스킷이 채워지면 컨셉별로 분류됩니다.</EmptyNote>
      ) : (
        <div className="flex flex-col">
          {interest.concepts.map((c: WatchlistConceptGroup) => (
            <Group key={c.concept} title={c.label} tone={CONCEPT_TONE[c.concept] ?? "neutral"} count={c.count} items={c.items} defaultOpen={false} />
          ))}
        </div>
      )}
    </Card>
  );
}

const BASKET_COND: Record<string, string[]> = {
  trade_value: ["KIS 거래대금 상위에서 큐레이션:", "· 시총 ≥ 5,000억", "· 일 거래대금 ≥ 100억", "· 등락 ≤ 20% (상한가 제외)", "· 정배열 (현재가 > 60·120일선)"],
  volume_bull: ["KIS 거래량 상위 + 등락률 ≥ 3% + 양봉(종가>시가),", "큐레이션:", "· 시총 ≥ 1,000억 (중소형 허용)", "· 일 거래대금 ≥ 100억", "· 정배열 (현재가 > 60·120일선)"],
};

function ConditionTooltip({ listType }: { listType: string }) {
  return (
    <span className="group relative inline-flex items-center">
      <span className="flex size-4 cursor-help items-center justify-center rounded-full border border-border text-[10px] text-faint">?</span>
      <span className="invisible absolute right-0 top-6 z-30 w-64 rounded-lg border border-border bg-card p-3 text-left text-[11px] leading-relaxed text-body shadow-lg group-hover:visible">
        <b className="mb-1 block text-foreground">포함 조건</b>
        {(BASKET_COND[listType] ?? []).map((l, i) => <span key={i} className="block">{l}</span>)}
      </span>
    </span>
  );
}

function BasketCard({ basket }: { basket: WatchlistBasket }) {
  const [open, setOpen] = useState(false);
  return (
    <Card
      title={basket.label}
      subtitle={`${basket.count}종목${basket.latest_date ? ` · 최신 ${basket.latest_date}` : ""}`}
      action={<ConditionTooltip listType={basket.list_type} />}
    >
      <button type="button" onClick={() => setOpen((v) => !v)} className="text-xs text-info">
        {open ? "접기" : "펼쳐서 종목 보기"}
      </button>
      {open && (
        <div className="mt-2 flex flex-col gap-3">
          {basket.dates.length === 0 && <EmptyNote>수집된 종목이 없어요.</EmptyNote>}
          {basket.dates.map((dg) => (
            <div key={dg.date} className="flex flex-col">
              <div className="border-b border-border pb-1 text-[11px] font-semibold text-faint">{dg.date} · {dg.count}종</div>
              {dg.items.map((m, i) => (
                <div key={m.ticker} className="flex items-center gap-2 border-b border-border py-1.5 last:border-0">
                  <span className="w-6 shrink-0 text-right font-mono text-[11px] text-faint">{i + 1}</span>
                  <span className="min-w-0 flex-1 truncate text-[13px] text-foreground">{m.display_name || m.ticker}</span>
                  {m.is_dual && (
                    <span className="shrink-0 rounded-full bg-profit/15 px-1.5 py-0.5 text-[9px] font-bold text-profit">거래대금+거래량</span>
                  )}
                  {/* 상승률 (양쪽 공통, 한국식 색) */}
                  <span className={cn("w-12 shrink-0 text-right font-mono text-[11px]", changeClass(m.change_pct))}>{fmtPct(m.change_pct)}</span>
                  {/* 거래대금(억 반올림) / 거래량(주) */}
                  <span className="w-20 shrink-0 text-right font-mono text-[11px] text-body">
                    {basket.list_type === "trade_value" ? eokKR(m.trade_amount) : volKR(m.volume)}
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export function WatchlistBoard({ funnel }: { funnel: WatchlistFunnel | undefined }) {
  const tracks = funnel?.tracks ?? [];
  const baskets = funnel?.baskets ?? [];
  const interest = funnel?.interest ?? { count: 0, concepts: [] };
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">관심종목 (종목 관리)</h1>
        <p className="text-sm text-faint">
          후보 바스킷 → 컨셉 분류된 관심 → 골라서 장기·단기 트랙별 매수대기·진입 · 종목별 매매 시나리오
        </p>
      </div>
      {/* 골라서 진입·매수대기 (트랙별) */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {tracks.map((t) => <TrackCard key={t.track} track={t} />)}
      </div>
      {/* 관심 = 공용 (컨셉 분류) */}
      <InterestSection interest={interest} />
      {/* 후보 바스킷 (소스) */}
      <div className="flex flex-col gap-1.5 pt-2">
        <h2 className="text-sm font-semibold text-faint">후보 바스킷 (큐레이션 소스)</h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {baskets.map((b) => <BasketCard key={b.list_type} basket={b} />)}
        </div>
      </div>
    </div>
  );
}
