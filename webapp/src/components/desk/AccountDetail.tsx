"use client";

import type { AccountItem, ClosedFill, Holding, HoldingsResp, KpiSummary, WealthCurve } from "@/lib/api";
import { fmtPct, manWon, pnlClass, wonKR, wonKRSigned } from "@/lib/format";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { useState } from "react";
import { fillReasonKR, verdictKR } from "./labels";
import { Badge, Card, EmptyNote, Metric } from "./primitives";
import { MetricStrip } from "./MetricStrip";
import { WealthCurveCard } from "./WealthCurveCard";

function maxDrawdownPct(values: number[]): number {
  let peak = -Infinity;
  let mdd = 0;
  for (const v of values) {
    if (v > peak) peak = v;
    if (peak > 0) mdd = Math.min(mdd, (v / peak - 1) * 100);
  }
  return Math.abs(mdd);
}

// ── 계좌 탭 ────────────────────────────────────────────────────────────────────
function AccountTabs({ accounts, current }: { accounts: AccountItem[]; current: string }) {
  return (
    <div className="flex flex-wrap gap-1 rounded-2xl border border-border bg-card p-1">
      {accounts.map((a) => (
        <Link
          key={a.account_id}
          href={`/desk/${a.account_id}`}
          className={cn(
            "rounded-xl px-3.5 py-2 text-sm font-medium transition",
            a.account_id === current ? "bg-secondary font-semibold text-foreground" : "text-faint hover:text-foreground",
          )}
        >
          {a.label}
        </Link>
      ))}
    </div>
  );
}

// ── 계좌 요약 스트립 (5) ──────────────────────────────────────────────────────
function SummaryStrip({
  acct,
  equity,
  realized,
  unrealized,
}: {
  acct: AccountItem;
  equity: number;
  realized: number;
  unrealized: number;
}) {
  const evalPct = acct.seed_krw ? (equity / acct.seed_krw - 1) * 100 : 0;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      <Metric label="시드" value={wonKR(acct.seed_krw)} />
      <Metric label="총자산 (평가 포함)" value={wonKR(equity)} valueClass={pnlClass(equity - acct.seed_krw)} sub={fmtPct(evalPct)} />
      <Metric label="실현손익 (확정)" value={wonKRSigned(realized)} valueClass={pnlClass(realized)} />
      <Metric label="평가손익 (미실현)" value={wonKRSigned(unrealized)} valueClass={pnlClass(unrealized)} />
      <Metric label="투입 비중" value={`${(acct.deployed_weight * 100).toFixed(1)}%`} sub="한도 80%" />
    </div>
  );
}

// ── 보유중 카드 (테이블 + 회차 펼치기) ────────────────────────────────────────
function TrancheLadder({ h }: { h: Holding }) {
  const t = h.tranches;
  return (
    <div className="mt-2 flex flex-col gap-2 rounded-xl bg-surface px-4 py-3">
      <p className="text-xs font-semibold text-body">
        {h.ticker} — 회차별 체결 내역 (분할 사다리: 진입가→손절가 보간, 물타기 차단)
      </p>
      {t.filled.map((f) => (
        <div key={`f${f.leg}`} className="flex items-center gap-3">
          <Badge tone="profit">도달</Badge>
          <span className="font-mono text-xs text-body">
            {f.leg}차 · {f.filled_date?.slice(5)} · {manWon(f.fill_price)} × {(f.shares ?? 0).toFixed(0)}주 = {wonKR(f.value_krw)}
          </span>
        </div>
      ))}
      {t.pending.map((p) => (
        <div key={`p${p.leg}`} className="flex items-center gap-3">
          <Badge tone="neutral">대기</Badge>
          <span className="font-mono text-xs text-faint">
            {p.leg}차 · {manWon(p.limit_price)}
            {p.ratio ? ` (배분 ${Math.round(p.ratio * 100)}%)` : ""} — 지정가 미도달, 대기 중
          </span>
        </div>
      ))}
      {t.stop_loss !== null && (
        <p className="text-[11px] text-loss">손절선 {manWon(t.stop_loss)} — 종가 이탈 시 전량 청산</p>
      )}
    </div>
  );
}

function HoldingsCard({ holdings }: { holdings: Holding[] }) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  const toggle = (t: string) =>
    setOpen((prev) => {
      const n = new Set(prev);
      if (n.has(t)) n.delete(t);
      else n.add(t);
      return n;
    });

  return (
    <Card title="보유중">
      {holdings.length === 0 ? (
        <EmptyNote>현재 보유 종목이 없어요 — 방어장에선 진입을 미루고 기다립니다.</EmptyNote>
      ) : (
        <div className="overflow-x-auto">
          <div className="min-w-[640px]">
            <div className="flex items-center gap-2 border-b border-border pb-2 text-[11px] font-semibold text-faint">
              <span className="min-w-0 flex-1">종목</span>
              <span className="w-20 shrink-0 text-right">평단</span>
              <span className="w-20 shrink-0 text-right">현재가</span>
              <span className="w-16 shrink-0 text-right">수익률</span>
              <span className="w-24 shrink-0 text-right">평가금액</span>
              <span className="w-16 shrink-0 text-right">비중</span>
              <span className="w-28 shrink-0 text-right">매수 회차</span>
            </div>
            {holdings.map((h) => {
              const evalAmt = h.eval_price * h.shares;
              const isOpen = open.has(h.ticker);
              return (
                <div key={h.ticker}>
                  <div className="flex items-center gap-2 border-b border-border py-2.5 text-sm last:border-0">
                    <span className="min-w-0 flex-1 truncate font-semibold text-foreground">
                      {h.ticker}
                      {!h.priced && <span className="ml-1 text-[10px] text-amber">시세대기</span>}
                    </span>
                    <span className="w-20 shrink-0 text-right font-mono text-xs text-body">{manWon(h.avg_price)}</span>
                    <span className="w-20 shrink-0 text-right font-mono text-xs text-body">{manWon(h.eval_price)}</span>
                    <span className={cn("w-16 shrink-0 text-right font-mono text-xs font-bold", pnlClass(h.unrealized_pct))}>
                      {fmtPct(h.unrealized_pct)}
                    </span>
                    <span className="w-24 shrink-0 text-right font-mono text-xs text-body">{wonKR(evalAmt)}</span>
                    <span className="w-16 shrink-0 text-right font-mono text-xs text-body">{(h.weight * 100).toFixed(1)}%</span>
                    <button
                      type="button"
                      onClick={() => toggle(h.ticker)}
                      className="w-28 shrink-0 text-right text-xs text-faint hover:text-foreground"
                    >
                      <Badge tone="neutral">{h.tranche_count}회</Badge> {isOpen ? "접기 ▴" : "펼치기 ▾"}
                    </button>
                  </div>
                  {isOpen && <TrancheLadder h={h} />}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
}

// ── 매수 대기 ──────────────────────────────────────────────────────────────────
function PendingCard({ pending }: { pending: HoldingsResp["pending"] }) {
  const { ladder_waiting, watching } = pending;
  const empty = ladder_waiting.length === 0 && watching.length === 0;
  return (
    <Card title="매수 대기">
      {empty ? (
        <EmptyNote>대기 중인 매수가 없어요 — 지정가 도달·진입 조건이 충족되면 자동 체결됩니다.</EmptyNote>
      ) : (
        <div className="flex flex-col gap-2">
          {ladder_waiting.map((w, i) => (
            <div key={`l${i}`} className="flex items-center gap-3 rounded-xl bg-surface px-3 py-2">
              <Badge tone="amber">사다리 대기</Badge>
              <span className="text-sm text-body">
                {w.display_name || w.ticker} {w.leg}차 — {manWon(w.limit_price)} 도달 시 자동 체결
              </span>
            </div>
          ))}
          {watching.map((w, i) => (
            <div key={`w${i}`} className="flex items-center gap-3 rounded-xl bg-surface px-3 py-2">
              <Badge tone="neutral">권고 관망</Badge>
              <span className="text-sm text-body">
                {w.display_name || w.ticker} — &ldquo;{verdictKR(w.verdict)}&rdquo;{w.reason ? ` (${w.reason})` : ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ── 이익실현 ──────────────────────────────────────────────────────────────────
function ClosedCard({ closed, realizedSum }: { closed: ClosedFill[]; realizedSum: number }) {
  return (
    <Card
      title="이익실현 (청산 내역)"
      action={
        closed.length > 0 ? (
          <span className={cn("text-xs font-semibold", pnlClass(realizedSum))}>
            이 계좌 누적 실현 {wonKRSigned(realizedSum)}
          </span>
        ) : undefined
      }
    >
      {closed.length === 0 ? (
        <EmptyNote>아직 실현된 수익이 없어요 — 목표가/손절선 도달 시 자동 청산되고 여기 기록됩니다.</EmptyNote>
      ) : (
        <div className="flex flex-col gap-2">
          {closed.map((c, i) => {
            const cost = c.value_krw - c.realized_pnl_krw;
            const pct = cost > 0 ? (c.realized_pnl_krw / cost) * 100 : null;
            const win = c.realized_pnl_krw >= 0;
            return (
              <div key={`c${i}`} className="flex items-center gap-3 rounded-xl bg-surface px-3 py-2">
                <Badge tone={win ? "profit" : "loss"}>{fillReasonKR("sell", c.reason, c.leg)}</Badge>
                <span className="text-sm text-body">
                  {c.filled_date.slice(5)} · {c.ticker} — {manWon(c.fill_price)} × {c.shares.toFixed(0)}주 → 실현{" "}
                  <span className={cn("font-semibold", pnlClass(c.realized_pnl_krw))}>
                    {wonKRSigned(c.realized_pnl_krw)}
                    {pct !== null ? ` (${fmtPct(pct)})` : ""}
                  </span>
                </span>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

// ── 메인 ─────────────────────────────────────────────────────────────────────
export function AccountDetail({
  accounts,
  acct,
  curve,
  holdings,
  kpi,
}: {
  accounts: AccountItem[];
  acct: AccountItem;
  curve: WealthCurve | undefined;
  holdings: HoldingsResp | undefined;
  kpi: KpiSummary | undefined;
}) {
  const unrealized = holdings?.summary.unrealized_pnl_krw ?? 0;
  const realizedSum = kpi?.realized_pnl_sum_krw ?? holdings?.summary.realized_pnl_krw ?? 0;
  const points = curve?.points ?? [];
  const equity = points.length ? points[points.length - 1].equity_krw : acct.seed_krw + realizedSum + unrealized;
  const accMdd = maxDrawdownPct(points.map((p) => p.equity_krw));

  return (
    <div className="flex flex-col gap-5">
      <Link href="/desk" className="text-sm font-semibold text-faint transition hover:text-foreground">
        ← 가상매매로 돌아가기
      </Link>
      <AccountTabs accounts={accounts} current={acct.account_id} />
      <SummaryStrip acct={acct} equity={equity} realized={realizedSum} unrealized={unrealized} />
      <WealthCurveCard curve={curve} title="자산 곡선 (이 계좌)" />
      <MetricStrip kpi={kpi} mddPct={accMdd} />
      <HoldingsCard holdings={holdings?.holdings ?? []} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <PendingCard pending={holdings?.pending ?? { ladder_waiting: [], watching: [] }} />
        <ClosedCard closed={holdings?.closed ?? []} realizedSum={realizedSum} />
      </div>
    </div>
  );
}
