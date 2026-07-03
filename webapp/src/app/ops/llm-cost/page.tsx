"use client";

// 운영자 화면 — LLM 비용 원장 (LLM-COST-LEDGER-001).
// 유저 비노출 예정 URL. 일단위 × 벤더 × 모델 × 질의영역 지출을 한 화면에.
import { API_BASE, fetcher, type LlmCostRow, type LlmCostSummary } from "@/lib/api";
import { useState } from "react";
import useSWR from "swr";

const OPTS = { refreshInterval: 60_000, revalidateOnFocus: false } as const;
const RANGES = [7, 14, 30] as const;

function usd(v: number | undefined): string {
  const n = v ?? 0;
  if (n === 0) return "$0";
  if (n < 0.01) return `$${n.toFixed(6)}`;
  return `$${n.toFixed(4)}`;
}

function num(v: number | undefined): string {
  return (v ?? 0).toLocaleString();
}

/** 비용 비율 막대 — 최댓값 대비 상대 폭. */
function Bar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.max(2, Math.round((value / max) * 100)) : 0;
  return (
    <div className="h-1.5 w-full rounded-full bg-surface">
      <div className="h-1.5 rounded-full bg-primary" style={{ width: `${pct}%` }} />
    </div>
  );
}

function Section({
  title,
  hint,
  rows,
  label,
}: {
  title: string;
  hint: string;
  rows: LlmCostRow[];
  label: (r: LlmCostRow) => string;
}) {
  const max = Math.max(0, ...rows.map((r) => r.cost_usd ?? 0));
  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="mb-1 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        <span className="text-xs text-faint">{hint}</span>
      </div>
      {rows.length === 0 ? (
        <p className="py-6 text-center text-xs text-faint">기록 없음</p>
      ) : (
        <div className="mt-3 flex flex-col gap-3">
          {rows.map((r, i) => (
            <div key={i} className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-3">
                <span className="truncate text-sm text-foreground">{label(r)}</span>
                <span className="shrink-0 font-mono text-sm font-semibold text-foreground">
                  {usd(r.cost_usd)}
                </span>
              </div>
              <Bar value={r.cost_usd ?? 0} max={max} />
              <div className="flex gap-3 text-[11px] text-faint">
                <span>{num(r.calls)} 콜</span>
                {r.cache_hits ? <span>캐시 {num(r.cache_hits)}</span> : null}
                {r.tokens_in ? <span>in {num(r.tokens_in)}</span> : null}
                {r.tokens_out ? <span>out {num(r.tokens_out)}</span> : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function LlmCostPage() {
  const [days, setDays] = useState<number>(7);
  const { data, isLoading, error } = useSWR<LlmCostSummary>(
    `/api/ops/llm-cost?days=${days}`,
    fetcher,
    OPTS,
  );

  return (
    <div className="mx-auto flex max-w-[1100px] flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-foreground">LLM 비용 원장</h1>
          <p className="text-xs text-faint">
            운영자 전용 · 벤더·모델·질의영역별 지출 추적 (llm_cost_ledger)
          </p>
        </div>
        <div className="flex gap-1 rounded-lg border border-border bg-card p-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setDays(r)}
              className={`rounded-md px-3 py-1 text-xs font-medium transition ${
                days === r
                  ? "bg-primary text-primary-foreground"
                  : "text-faint hover:text-foreground"
              }`}
            >
              {r}일
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-border bg-card p-6">
          <p className="text-sm font-semibold text-foreground">원장을 불러오지 못했습니다.</p>
          <p className="mt-1 text-xs text-faint">
            백엔드({API_BASE}) 연결을 확인하세요. {String(error)}
          </p>
        </div>
      ) : isLoading || !data ? (
        <div className="h-40 animate-pulse rounded-2xl bg-surface" />
      ) : (
        <>
          {/* 총계 */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="총 지출" value={usd(data.totals.cost_usd)} accent />
            <Stat label="총 호출" value={`${num(data.totals.calls)} 콜`} />
            <Stat label="캐시 히트" value={num(data.totals.cache_hits)} />
            <Stat
              label="토큰 (in/out)"
              value={`${num(data.totals.tokens_in)} / ${num(data.totals.tokens_out)}`}
            />
          </div>
          <p className="-mt-1 text-[11px] text-faint">
            기간: {data.range.since} ~ 오늘 ({data.range.days}일)
          </p>

          {/* 벤더 · 모델 · 질의영역 */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Section
              title="벤더별"
              hint="provider"
              rows={data.by_provider}
              label={(r) => r.provider ?? "?"}
            />
            <Section
              title="모델별"
              hint="provider / model"
              rows={data.by_model}
              label={(r) => `${r.provider ?? "?"} / ${r.model ?? "?"}`}
            />
            <Section
              title="질의영역별"
              hint="call_type"
              rows={data.by_call_type}
              label={(r) => r.call_type ?? "general"}
            />
          </div>

          {/* 일자별 */}
          <div className="rounded-2xl border border-border bg-card p-5">
            <h2 className="mb-3 text-sm font-semibold text-foreground">일자별</h2>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[360px] text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-faint">
                    <th className="pb-2 font-medium">날짜</th>
                    <th className="pb-2 text-right font-medium">지출</th>
                    <th className="pb-2 text-right font-medium">호출</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_day.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="py-6 text-center text-xs text-faint">
                        기록 없음
                      </td>
                    </tr>
                  ) : (
                    data.by_day.map((r) => (
                      <tr key={r.day} className="border-b border-border/50">
                        <td className="py-2 text-foreground">{r.day}</td>
                        <td className="py-2 text-right font-mono font-semibold text-foreground">
                          {usd(r.cost_usd)}
                        </td>
                        <td className="py-2 text-right text-faint">{num(r.calls)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <p className="text-xs text-faint">{label}</p>
      <p
        className={`mt-1 font-mono text-lg font-semibold ${
          accent ? "text-primary" : "text-foreground"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
