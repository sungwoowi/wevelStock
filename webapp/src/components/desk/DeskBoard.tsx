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
import useSWR from "swr";
import { fillReasonKR, verdictKR } from "./labels";
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

// ── 하단: 활성 권고 + 매매 일지 ───────────────────────────────────────────────
function ActiveRecsCard({ recs }: { recs: ActiveRec[] }) {
  return (
    <Card title="지금 지켜보는 권고" subtitle="활성 · 최근 30일">
      {recs.length === 0 ? (
        <EmptyNote>아직 활성 권고가 없어요 — 전략가가 매수/관망 신호를 내면 여기에 표시됩니다.</EmptyNote>
      ) : (
        <div className="flex flex-col">
          <div className="flex items-center gap-2 border-b border-border pb-2 text-[11px] font-semibold text-faint">
            <span className="min-w-0 flex-1">종목</span>
            <span className="w-14 shrink-0 text-center">트랙</span>
            <span className="w-14 shrink-0 text-center">상태</span>
            <span className="w-28 shrink-0 text-right">진입 / 손절</span>
          </div>
          {recs.map((r) => (
            <div key={r.recommendation_id} className="flex items-center gap-2 border-b border-border py-2 last:border-0">
              <span className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground">
                {r.display_name || r.ticker}
              </span>
              <span className="w-14 shrink-0 text-center">
                <TrackChip track={r.track} />
              </span>
              <span className="w-14 shrink-0 text-center">
                <Badge tone={r.verdict === "buy" ? "profit" : "neutral"}>{verdictKR(r.verdict)}</Badge>
              </span>
              <span className="w-28 shrink-0 text-right font-mono text-xs text-body">
                {r.entry_price ? wonKR(r.entry_price) : "—"}
                {r.stop_loss ? ` / ${wonKR(r.stop_loss)}` : ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
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
        <ActiveRecsCard recs={feed?.active_recommendations ?? []} />
        <FillJournalCard fills={feed?.recent_fills ?? []} />
      </div>
    </div>
  );
}
