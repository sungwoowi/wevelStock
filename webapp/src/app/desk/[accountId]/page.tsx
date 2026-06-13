"use client";

import { AccountDetail } from "@/components/desk/AccountDetail";
import { CardSkeleton } from "@/components/desk/primitives";
import {
  API_BASE,
  fetcher,
  type AccountItem,
  type HoldingsResp,
  type KpiSummary,
  type WealthCurve,
} from "@/lib/api";
import Link from "next/link";
import { useParams } from "next/navigation";
import useSWR from "swr";

const OPTS = { refreshInterval: 120_000, revalidateOnFocus: false } as const;

export default function AccountDetailPage() {
  const params = useParams<{ accountId: string }>();
  const accountId = params.accountId;

  const { data: accounts, isLoading, error } = useSWR<{ items: AccountItem[] }>("/api/accounts", fetcher, OPTS);
  const { data: curve } = useSWR<WealthCurve>(
    `/api/wealth/curve?account_id=${encodeURIComponent(accountId)}`,
    fetcher,
    OPTS,
  );
  const { data: holdings } = useSWR<HoldingsResp>(
    `/api/accounts/${encodeURIComponent(accountId)}/holdings`,
    fetcher,
    OPTS,
  );
  const { data: kpi } = useSWR<KpiSummary>(
    `/api/guidance/kpi?account_id=${encodeURIComponent(accountId)}`,
    fetcher,
    OPTS,
  );

  if (isLoading) {
    return (
      <div className="flex flex-col gap-5">
        <div className="h-6 w-40 animate-pulse rounded bg-surface" />
        <CardSkeleton h="h-12" />
        <CardSkeleton h="h-24" />
        <CardSkeleton h="h-72" />
      </div>
    );
  }
  if (error || !accounts) {
    return (
      <div className="rounded-2xl border border-border bg-card p-6">
        <p className="text-sm font-semibold text-foreground">계좌 데이터를 불러오지 못했습니다.</p>
        <p className="mt-1 text-xs text-faint">
          백엔드({API_BASE}) 연결을 확인하세요. {error ? String(error) : ""}
        </p>
      </div>
    );
  }

  const acct = accounts.items.find((a) => a.account_id === accountId);
  if (!acct) {
    return (
      <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 text-center">
        <p className="text-lg font-bold text-foreground">계좌를 찾을 수 없습니다</p>
        <p className="text-sm text-faint">존재하지 않는 계좌 ID: {accountId}</p>
        <Link href="/desk" className="text-sm text-primary underline">
          가상매매로 돌아가기
        </Link>
      </div>
    );
  }

  return <AccountDetail accounts={accounts.items} acct={acct} curve={curve} holdings={holdings} kpi={kpi} />;
}
