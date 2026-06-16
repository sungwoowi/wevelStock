"use client";

import {
  fetcher,
  type AccountItem,
  type ActiveRec,
  type DeskFeed,
  type FillEntry,
  type HoldingsResp,
  type KpiSummary,
  type WealthCurve,
  type WealthProgress,
} from "@/lib/api";
import { fmtPct, pnlClass, wonKR, wonKRSigned } from "@/lib/format";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { STAGE_ORDER, fillReasonKR, stageKR, stageTone, universeKR } from "./labels";
import { Badge, Card, EmptyNote, Metric, ProgressBar, TrackChip } from "./primitives";
import { MetricStrip } from "./MetricStrip";
import { WealthCurveCard } from "./WealthCurveCard";

// ── 회고 KPI 스트립 (4) ───────────────────────────────────────────────────────
function KpiStrip({ kpi }: { kpi: KpiSummary | undefined }) {
  const closed = kpi?.closed_count ?? 0;
  const realizedSum = kpi?.realized_pnl_sum_krw ?? 0;
  const avgRet = kpi?.realized_return_avg_pct;
  const alpha = kpi?.alpha_avg_pct;
  const win = kpi?.win_rate_pct;
  const rr = kpi?.rr_realization_avg_pct;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Metric
        label="누적 실현 수익 (최근 90일)"
        value={wonKRSigned(realizedSum)}
        valueClass={pnlClass(realizedSum)}
        sub={`청산 ${closed}건${avgRet !== null && avgRet !== undefined ? ` · 평균 ${fmtPct(avgRet)}` : ""} — 시즌 누적`}
      />
      <Metric
        label="그냥 지수 샀을 때보다"
        value={alpha !== null && alpha !== undefined ? fmtPct(alpha) : "—"}
        valueClass={alpha !== null && alpha !== undefined ? pnlClass(alpha) : "text-faint"}
        sub="같은 기간 지수 보유 대비 초과"
      />
      <Metric
        label="승률"
        value={win !== null && win !== undefined ? `${win.toFixed(0)}%` : "—"}
        sub="익절로 끝난 매매 비율 (정직 공개)"
      />
      <Metric
        label="손익비 실현율"
        value={rr !== null && rr !== undefined ? `${rr.toFixed(0)}%` : "—"}
        valueClass="text-amber"
        sub="계획한 손익비 대비 실제 달성"
      />
    </div>
  );
}

// ── 4계좌 그리드 ───────────────────────────────────────────────────────────────
function AccountCard({ acct }: { acct: AccountItem }) {
  const { data } = useSWR<HoldingsResp>(`/api/accounts/${acct.account_id}/holdings`, fetcher, {
    refreshInterval: 120_000,
    revalidateOnFocus: false,
  });
  const unreal = data?.summary.unrealized_pnl_krw ?? 0;
  const real = data?.summary.realized_pnl_krw ?? 0;
  const positions = data?.summary.position_count ?? 0;
  const equity = acct.seed_krw + real + unreal;
  const deployedPct = acct.deployed_weight * 100;
  const evalPct = acct.seed_krw ? (unreal / acct.seed_krw) * 100 : 0;

  return (
    <Link
      href={`/desk/${acct.account_id}`}
      className="flex flex-col gap-2 rounded-2xl border border-border bg-card p-4 transition hover:border-primary/50"
    >
      <div className="flex items-center gap-2">
        <span className="text-sm font-bold text-foreground">{acct.label}</span>
        <TrackChip track={acct.track} />
        <div className="flex-1" />
        <span className="text-xs text-faint">상세 →</span>
      </div>
      <span className="font-mono text-lg font-bold text-foreground">
        {wonKR(equity)} <span className="text-xs font-normal text-faint">/ 시드 {wonKR(acct.seed_krw)}</span>
      </span>
      <span className="text-xs text-body">
        투입 {deployedPct.toFixed(1)}% · 보유 {positions}종
        {positions > 0 && (
          <>
            {" · 평가 "}
            <span className={pnlClass(unreal)}>
              {wonKRSigned(unreal)} ({fmtPct(evalPct)})
            </span>
          </>
        )}
        {positions === 0 && " · 진입 대기"}
      </span>
      <ProgressBar pct={deployedPct} />
    </Link>
  );
}

function AccountGrid({ accounts }: { accounts: AccountItem[] }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {accounts.map((a) => (
        <AccountCard key={a.account_id} acct={a} />
      ))}
    </div>
  );
}

// ── 하단: 지켜보는 권고(장기/단기 × 단계 그룹) + 매매 일지 ──────────────────────
/** 단계 파생 — funnel_stage 우선, 누락(구버전 rec) 시 verdict 폴백. */
function stageOf(r: ActiveRec): string {
  return r.funnel_stage ?? (r.verdict === "buy" ? "entering" : "interest");
}

function RecRow({ r }: { r: ActiveRec }) {
  const stage = stageOf(r);
  const priceText =
    stage === "entering"
      ? `${r.entry_price ? wonKR(r.entry_price) : "—"}${r.stop_loss ? ` / ${wonKR(r.stop_loss)}` : ""}`
      : stage === "watching"
        ? `대기 ${r.watching_entry ? wonKR(r.watching_entry) : "—"}${r.watching_label ? ` · ${r.watching_label}` : ""}`
        : "—";
  const uni = universeKR(r.universe_days_ago);
  return (
    <div className="flex items-center gap-2 border-b border-border py-2 last:border-0">
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-sm font-semibold text-foreground">{r.display_name || r.ticker}</span>
        {uni && <span className="truncate text-[11px] text-faint">{uni}</span>}
      </span>
      <span className="shrink-0 text-right font-mono text-xs text-body">{priceText}</span>
    </div>
  );
}

/** 단계 소그룹 — 진입/매수대기는 펼침, 관심은 개수+펼치기 토글(노이즈 컷). */
function StageGroup({ stage, recs }: { stage: string; recs: ActiveRec[] }) {
  const [open, setOpen] = useState(stage !== "interest");
  if (recs.length === 0) return null;
  return (
    <div className="flex flex-col border-t border-border first:border-t-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 py-2 text-left"
        aria-expanded={open}
      >
        <Badge tone={stageTone(stage)}>{stageKR(stage)}</Badge>
        <span className="text-xs font-semibold text-faint">{recs.length}</span>
        {stage === "interest" && (
          <span className="ml-auto text-xs text-info">{open ? "접기" : "펼치기"}</span>
        )}
      </button>
      {open && (
        <div className="flex flex-col">
          {recs.map((r) => (
            <RecRow key={r.recommendation_id} r={r} />
          ))}
        </div>
      )}
    </div>
  );
}

/** 트랙별 카드 — 단계 순(진입▸매수대기▸관심) 그룹. 해당 트랙 권고 0이면 숨김. */
function TrackWatchCard({ track, recs }: { track: "A" | "B"; recs: ActiveRec[] }) {
  if (recs.length === 0) return null;
  return (
    <Card title="지켜보는 권고" subtitle={track === "A" ? "중장기 (Track A)" : "단기 (Track B)"}>
      <div className="flex flex-col">
        {STAGE_ORDER.map((s) => (
          <StageGroup key={s} stage={s} recs={recs.filter((r) => stageOf(r) === s)} />
        ))}
      </div>
    </Card>
  );
}

/** 지금 지켜보는 권고 — 장기/단기 2카드 스택. 둘 다 비면 안내. */
function WatchlistSection({ recs }: { recs: ActiveRec[] }) {
  if (recs.length === 0) {
    return (
      <Card title="지금 지켜보는 권고" subtitle="활성 · 최근 30일">
        <EmptyNote>아직 활성 권고가 없어요 — 전략가가 매수/관망 신호를 내면 여기에 표시됩니다.</EmptyNote>
      </Card>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      <TrackWatchCard track="A" recs={recs.filter((r) => r.track === "A")} />
      <TrackWatchCard track="B" recs={recs.filter((r) => r.track === "B")} />
    </div>
  );
}

function FillJournalCard({ fills }: { fills: FillEntry[] }) {
  return (
    <Card title="매매 일지" subtitle="체결 · 청산">
      {fills.length === 0 ? (
        <EmptyNote>
          아직 체결이 없어요 — 시장이 신호를 주면 가상매매가 먼저 움직이고 여기 기록됩니다.
        </EmptyNote>
      ) : (
        <div className="flex flex-col gap-2">
          {fills.map((f, i) => {
            const action = fillReasonKR(f.side, f.reason, f.leg);
            const profit = f.side === "sell";
            return (
              <div key={`${f.recommendation_id}-${f.side}-${f.leg}-${i}`} className="rounded-xl bg-surface px-3 py-2">
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span className="min-w-0 truncate font-semibold text-foreground">
                    {f.filled_date.slice(5)} · {f.ticker} {action}
                  </span>
                  {profit ? (
                    <span className={cn("shrink-0 font-mono text-xs font-bold", pnlClass(f.realized_pnl_krw))}>
                      {wonKRSigned(f.realized_pnl_krw)}
                    </span>
                  ) : (
                    <span className="shrink-0 font-mono text-xs text-faint">{wonKR(f.value_krw)}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

// ── 메인 ─────────────────────────────────────────────────────────────────────
export function DeskBoard({
  curve,
  progress,
  accounts,
  kpi,
  feed,
}: {
  curve: WealthCurve | undefined;
  progress: WealthProgress | undefined;
  accounts: AccountItem[];
  kpi: KpiSummary | undefined;
  feed: DeskFeed | undefined;
}) {
  const updated = progress ? `${kpi?.as_of ?? ""}` : "";
  return (
    <div className="flex flex-col gap-5">
      {/* 헤더 */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">가상매매 (페이퍼 트레이딩)</h1>
          <p className="text-sm text-faint">
            권고 → 체결 → 청산 → 채점까지 시스템이 책임지는 가상 4계좌 · 매일 18:05 자동으로 돕니다
          </p>
        </div>
        {updated && (
          <span className="rounded-xl border border-border px-3 py-1.5 text-xs text-body">마지막 갱신 {updated}</span>
        )}
      </div>

      <WealthCurveCard curve={curve} progress={progress} />
      <KpiStrip kpi={kpi} />
      <MetricStrip kpi={kpi} mddPct={progress?.mdd_pct} mddGuard={progress?.mdd_guard_pct} />
      <AccountGrid accounts={accounts} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <WatchlistSection recs={feed?.active_recommendations ?? []} />
        <FillJournalCard fills={feed?.recent_fills ?? []} />
      </div>
    </div>
  );
}
