"use client";
import useSWR from "swr";
import { fetcher, StandardOutput } from "@/lib/api";
import { VerdictBadge } from "./VerdictBadge";

export function PrincipleCard() {
  const { data, error, isLoading } = useSWR<StandardOutput>(
    "/api/teams/principles/latest",
    fetcher,
    { refreshInterval: 5000 }
  );

  if (isLoading) return <Card title="원칙 관리팀">로딩 중…</Card>;
  if (error) return <Card title="원칙 관리팀">⚠ 데이터 없음 (데모를 실행해 주세요)</Card>;
  if (!data) return <Card title="원칙 관리팀">-</Card>;

  const data_ = data.data as {
    total_weight_pct?: number;
    max_single_stock_pct?: number;
    trading_weight_pct?: number;
    violations?: { commandment: string; title: string; detail: string }[];
    warnings?: { commandment: string; title: string; detail: string }[];
    passes?: { commandment: string; title: string }[];
  };

  return (
    <Card title="원칙 관리팀" subtitle={`7계명 · ${data.timestamp.slice(0, 16).replace("T", " ")}`}>
      <div className="flex items-center gap-3 mb-3">
        <VerdictBadge verdict={data.verdict} />
        <span className="text-sm text-neutral-400">신뢰도 {data.confidence}</span>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-4 text-xs">
        <Metric label="총 비중" value={pct(data_.total_weight_pct)} />
        <Metric label="단일 최대" value={pct(data_.max_single_stock_pct)} />
        <Metric label="트레이딩" value={pct(data_.trading_weight_pct)} />
      </div>

      <ul className="space-y-1 text-sm">
        {(data_.violations ?? []).map((v) => (
          <li key={v.commandment} className="text-red-300">
            ✗ [{v.commandment}] {v.title}: {v.detail}
          </li>
        ))}
        {(data_.warnings ?? []).map((w) => (
          <li key={w.commandment} className="text-amber-300">
            ⚠ [{w.commandment}] {w.title}: {w.detail}
          </li>
        ))}
        {data_.violations?.length === 0 && data_.warnings?.length === 0 && (
          <li className="text-emerald-300">✓ 모든 원칙 준수</li>
        )}
      </ul>
    </Card>
  );
}

function Card({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-5">
      <div className="mb-3">
        <h2 className="text-lg font-semibold">{title}</h2>
        {subtitle && <p className="text-xs text-neutral-500 font-mono">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-neutral-800/40 px-2 py-1.5">
      <div className="text-neutral-500">{label}</div>
      <div className="font-mono text-neutral-100">{value}</div>
    </div>
  );
}

function pct(n: number | undefined) {
  if (n === undefined || n === null) return "-";
  return `${n}%`;
}
