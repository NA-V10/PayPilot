"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense } from "react";
import { StatusBadge } from "@/components/badges";
import { ErrorState } from "@/components/states";
import { ApprovalBar, GovernanceDetails } from "@/components/trace/investigation";
import { PaymentPanel } from "@/components/trace/payment-panel";
import { Pipeline } from "@/components/trace/pipeline";
import { DecisionSummary, TxFacts } from "@/components/trace/sections";
import { TraceTimeline } from "@/components/trace/timeline";
import { Card, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { dateTime } from "@/lib/format";

function TraceView() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["tx", id], queryFn: () => api.transaction(id), refetchInterval: (query) => (query.state.data?.status === "PAYMENT_CREATED" ? 5000 : false) });
  const tx = q.data;

  return (
    <div>
      <Link href="/trace" className="mb-4 inline-flex items-center gap-1 text-[13px] text-fg-3 hover:text-fg">
        <ArrowLeft className="size-3.5" /> All traces
      </Link>
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.isPending && <Skeleton className="h-96 rounded-xl" />}
      {tx && (
        <>
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <h1 className="font-mono text-2xl font-semibold tracking-tight">Transaction #{tx.id}</h1>
            <StatusBadge status={tx.status} />
            <span className="text-[13px] text-fg-3">
              {dateTime(tx.created_at)} · trace <span className="font-mono">{tx.trace_id}</span>
            </span>
          </div>
          <Card className="p-5">
            <TxFacts tx={tx} />
            <div className="mt-5">
              <Pipeline events={tx.events} status={tx.status} done />
            </div>
          </Card>
          <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <Card className="p-5">
              <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.1em] text-fg-3">Timeline</p>
              <TraceTimeline events={tx.events} />
            </Card>
            <div className="space-y-4">
              <DecisionSummary tx={tx} />
              <ApprovalBar tx={tx} onUpdate={(t) => qc.setQueryData(["tx", id], t)} />
              <Card className="p-5">
                <PaymentPanel tx={tx} onUpdate={(t) => qc.setQueryData(["tx", id], t)} />
              </Card>
              <Card className="p-5">
                <GovernanceDetails tx={tx} />
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function TracePage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
      <TraceView />
    </Suspense>
  );
}
