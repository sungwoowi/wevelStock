"use client";
import useSWR from "swr";
import { fetcher, StandardOutput } from "@/lib/api";
import { VerdictBadge } from "./VerdictBadge";

export function BriefingCard() {
  const { data, error, isLoading } = useSWR<StandardOutput>(
    "/api/teams/daily_briefing/latest",
    fetcher,
    { refreshInterval: 5000 }
  );

  if (isLoading)
    return <Card title="데일리 브리핑">로딩 중…</Card>;
  if (error)
    return (
      <Card title="데일리 브리핑">
        ⚠ 데이터 없음 (데모를 실행해 주세요)
      </Card>
    );
  if (!data) return <Card title="데일리 브리핑">-</Card>;

  const narrative = (data.data as { narrative?: string })?.narrative ?? "";
  const mock = data.metadata && (data.metadata as any).model?.includes("mock");

  return (
    <Card
      title="데일리 브리핑"
      subtitle={`${data.timestamp.slice(0, 16).replace("T", " ")} · ${(data.metadata as any).model || ""}${mock ? " (mock)" : ""}`}
    >
      <div className="flex items-center gap-3 mb-3">
        <VerdictBadge verdict={data.verdict} />
        <span className="text-sm text-neutral-400">신뢰도 {data.confidence}</span>
      </div>
      <p className="text-sm leading-relaxed text-neutral-200 whitespace-pre-wrap">
        {narrative}
      </p>
      {data.reasons?.length > 0 && (
        <details className="mt-3 text-xs text-neutral-500">
          <summary className="cursor-pointer">판단 근거 ({data.reasons.length})</summary>
          <ul className="mt-2 space-y-1">
            {data.reasons.map((r, i) => (
              <li key={i}>• {r}</li>
            ))}
          </ul>
        </details>
      )}
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
        {subtitle && (
          <p className="text-xs text-neutral-500 font-mono">{subtitle}</p>
        )}
      </div>
      {children}
    </div>
  );
}
