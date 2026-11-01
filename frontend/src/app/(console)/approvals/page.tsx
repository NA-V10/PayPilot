"use client";

import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, Check, Inbox, Loader2, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { Badge, RiskBadge, StatusBadge } from "@/components/badges";
import { EmptyState, ErrorState, PageHeader } from "@/components/states";
import { TransactionDrawer } from "@/components/trace/transaction-drawer";
import { Button } from "@/components/ui/button";
import { Card, Skeleton, Tabs, TabsList, TabsTrigger } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { money, timeAgo } from "@/lib/format";
import { useApprovalActions } from "@/lib/hooks";
import type { TransactionDetail } from "@/lib/types";

function ApprovalCard({ tx, onOpen }: { tx: TransactionDetail; onOpen: () => void }) {
  const { approve, deny } = useApprovalActions();
  const threshold = tx.policy_result?.checks.find((c) => c.rule === "require_approval_above");
  const busy = (approve.isPending && approve.variables?.id === tx.id) || (deny.isPending && deny.variables?.id === tx.id);
  const err = approve.variables?.id === tx.id ? approve.error : deny.variables?.id === tx.id ? deny.error : null;
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-border bg-warn-soft/50 px-5 py-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-warn">Requires your approval</span>
        <span className="text-[12px] text-fg-3">{timeAgo(tx.created_at)}</span>
      </div>
      <div className="grid gap-5 p-5 md:grid-cols-[1.3fr_1fr]">
        <div className="min-w-0">
          <p className="text-[13px] text-fg-3">{tx.agent.name}</p>
          <p className="mt-0.5 truncate text-[15px] font-medium">{tx.description}</p>
          <p className="mt-2 text-3xl font-semibold tracking-tight tabular">{money(tx.amount, tx.currency)}</p>
          {tx.user_request && <p className="mt-2 text-[13px] text-fg-2">“{tx.user_request}”</p>}
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-[13px]">
          <div className="col-span-2">
            <dt className="text-[11px] uppercase tracking-wide text-fg-3">Reason</dt>
            <dd className="mt-0.5">{tx.approval_reason}</dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wide text-fg-3">Risk</dt>
            <dd className="mt-1">
              <RiskBadge level={tx.risk_level} score={tx.risk_score} />
            </dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wide text-fg-3">Merchant</dt>
            <dd className="mt-1 flex items-center gap-1.5">
              {tx.merchant?.name}
              {tx.merchant?.verification_status === "VERIFIED" && <BadgeCheck className="size-3.5 text-good" aria-label="Verified" />}
            </dd>
          </div>
          <div className="col-span-2">
            <dt className="text-[11px] uppercase tracking-wide text-fg-3">Policy</dt>
            <dd className="mt-0.5">Approval required above {threshold?.limit ?? "the autonomous limit"} · all other rules pass</dd>
          </div>
        </dl>
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t border-border px-5 py-3">
        <Button variant="ghost" size="sm" onClick={onOpen}>
          Investigate
        </Button>
        {err && <span role="alert" className="text-[12px] text-bad">{(err as Error).message}</span>}
        <div className="ml-auto flex gap-2">
          <Button variant="secondary" disabled={busy} onClick={() => deny.mutate({ id: tx.id })}>
            {deny.isPending && deny.variables?.id === tx.id ? <Loader2 className="animate-spin" /> : <X />} Deny
          </Button>
          <Button variant="good" disabled={busy} onClick={() => approve.mutate({ id: tx.id })}>
            {approve.isPending && approve.variables?.id === tx.id ? <Loader2 className="animate-spin" /> : <Check />} Approve
          </Button>
        </div>
      </div>
    </Card>
  );
}

export default function ApprovalsPage() {
  const [tab, setTab] = useState<"pending" | "resolved">("pending");
  const [selected, setSelected] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["approvals", tab], queryFn: () => api.approvals(tab), refetchInterval: tab === "pending" ? 10_000 : false });

  return (
    <div className="max-w-4xl">
      <PageHeader
        eyebrow="Approvals"
        title="Human-in-the-loop"
        description="Payments above an agent's autonomous limit pause here. Approving re-checks policy, then executes through PayPal."
        actions={
          <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
            <TabsList>
              <TabsTrigger value="pending">Pending</TabsTrigger>
              <TabsTrigger value="resolved">Resolved</TabsTrigger>
            </TabsList>
          </Tabs>
        }
      />
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.isPending && (
        <div className="space-y-3">
          <Skeleton className="h-56 rounded-xl" />
          <Skeleton className="h-56 rounded-xl" />
        </div>
      )}
      {q.data && q.data.length === 0 && (
        <Card>
          <EmptyState
            icon={tab === "pending" ? <ShieldCheck className="size-5" /> : <Inbox className="size-5" />}
            title={tab === "pending" ? "Inbox zero" : "No resolved approvals yet"}
            description={tab === "pending" ? "Your agents are operating within their autonomous limits." : undefined}
          />
        </Card>
      )}
      <div className="space-y-3">
        {tab === "pending" && q.data?.map((tx) => <ApprovalCard key={tx.id} tx={tx} onOpen={() => setSelected(tx.id)} />)}
        {tab === "resolved" && q.data && q.data.length > 0 && (
          <Card className="divide-y divide-border">
            {q.data.map((tx) => (
              <button key={tx.id} onClick={() => setSelected(tx.id)} className="flex w-full items-center gap-4 px-5 py-3 text-left hover:bg-surface-2/60 cursor-pointer">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-medium">{tx.description}</p>
                  <p className="text-[12px] text-fg-3">
                    {tx.agent.name} · {tx.approval_status === "APPROVED" ? "Approved" : "Denied"} by {tx.approved_by ?? "—"}
                  </p>
                </div>
                <span className="text-[13px] font-medium tabular">{money(tx.amount, tx.currency)}</span>
                <StatusBadge status={tx.status} />
              </button>
            ))}
          </Card>
        )}
      </div>
      {tab === "pending" && q.data && q.data.length > 0 && (
        <p className="mt-4 text-[12px] text-fg-3">
          <Badge>Policy</Badge> Approving never bypasses hard limits. If a limit was consumed since the request, the approval is rejected.
        </p>
      )}
      <TransactionDrawer id={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
