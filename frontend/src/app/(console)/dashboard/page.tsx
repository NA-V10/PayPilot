"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, TerminalSquare } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/badges";
import { AgentSpendChart, DecisionsChart, Legend, RiskDistribution, SpendChart } from "@/components/charts";
import { ErrorState, PageHeader } from "@/components/states";
import { TransactionDrawer } from "@/components/trace/transaction-drawer";
import { TransactionTable } from "@/components/transaction-table";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { money } from "@/lib/format";

function Stat({ label, value, hint, tone }: { label: string; value: React.ReactNode; hint?: string; tone?: "good" | "warn" | "bad" }) {
  const color = tone === "good" ? "text-good" : tone === "warn" ? "text-warn" : tone === "bad" ? "text-bad" : "text-fg";
  return (
    <Card className="p-4">
      <p className="text-[12px] font-medium text-fg-3">{label}</p>
      <p className={`mt-1.5 text-2xl font-semibold tracking-tight ${color}`}>{value}</p>
      {hint && <p className="mt-0.5 text-[12px] text-fg-3">{hint}</p>}
    </Card>
  );
}

export default function DashboardPage() {
  const q = useQuery({ queryKey: ["overview"], queryFn: api.overview, refetchInterval: 20_000 });
  const [selected, setSelected] = useState<string | null>(null);
  const d = q.data;
  const c = d?.currency ?? "INR";

  return (
    <div>
      <PageHeader
        eyebrow="Overview"
        title="Agent spending, governed"
        description="Every payment your agents attempt, and what PayPilot decided."
        actions={
          <Button asChild variant="secondary">
            <Link href="/command-center">
              <TerminalSquare /> Command Center
            </Link>
          </Button>
        }
      />

      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            {!d ? (
              Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[92px] rounded-xl" />)
            ) : (
              <>
                <Stat label="Total spend" value={money(d.metrics.total_spend, c)} hint="Completed payments" />
                <Stat label="Autonomous spend" value={money(d.metrics.autonomous_spend, c)} hint="No human needed" />
                <Stat label="Awaiting approval" value={d.metrics.awaiting_approval} tone={d.metrics.awaiting_approval ? "warn" : undefined} hint="In your inbox" />
                <Stat label="Blocked transactions" value={d.metrics.blocked_transactions} tone="bad" hint="Blocked or denied" />
                <Stat label="Risk prevented" value={money(d.metrics.risk_prevented, c)} tone="good" hint="Never left your account" />
                <Stat label="Active agents" value={d.metrics.active_agents} hint={`${d.metrics.total_transactions} transactions`} />
              </>
            )}
          </div>

          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            <Card>
              <CardHeader title="Spending over time" description="Completed payments, last 14 days" />
              <div className="px-3 pb-3">{d ? <SpendChart data={d.timeseries} currency={c} /> : <Skeleton className="m-2 h-[220px]" />}</div>
            </Card>
            <Card>
              <CardHeader
                title="Allowed vs blocked"
                description="Decisions per day"
                action={
                  <Legend
                    items={[
                      { label: "Allowed", color: "var(--status-good)" },
                      { label: "Approval", color: "var(--status-warning)" },
                      { label: "Blocked", color: "var(--status-critical)" },
                    ]}
                  />
                }
              />
              <div className="px-3 pb-3">{d ? <DecisionsChart data={d.timeseries} /> : <Skeleton className="m-2 h-[220px]" />}</div>
            </Card>
          </div>

          <div className="mt-3 grid gap-3 lg:grid-cols-3">
            <Card>
              <CardHeader title="Risk distribution" description="All evaluated transactions" />
              <div className="px-5 pb-5">{d ? <RiskDistribution data={d.risk_distribution} /> : <Skeleton className="h-20" />}</div>
            </Card>
            <Card>
              <CardHeader title="Agent spending" description="Completed, all time" />
              <div className="px-3 pb-3">{d ? <AgentSpendChart data={d.agent_spending} currency={c} /> : <Skeleton className="h-32" />}</div>
            </Card>
            <Card>
              <CardHeader title="Merchant risk" action={<Link href="/merchants" className="text-[12px] font-medium text-accent hover:underline">All</Link>} />
              <ul className="px-5 pb-4">
                {d?.merchant_risk.slice(0, 6).map((m) => (
                  <li key={m.merchant_id} className="flex items-center gap-3 py-1.5 text-[13px]">
                    <span className="min-w-0 flex-1 truncate">{m.merchant}</span>
                    <div className="h-1.5 w-20 overflow-hidden rounded-full bg-surface-2" aria-hidden>
                      <div className={m.trust_score >= 80 ? "h-full bg-good" : m.trust_score >= 60 ? "h-full bg-warn" : "h-full bg-bad"} style={{ width: `${m.trust_score}%` }} />
                    </div>
                    <span className="w-16 text-right font-mono text-[12px] text-fg-2 tabular">trust {m.trust_score}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          <Card className="mt-3">
            <CardHeader
              title="Recent transactions"
              action={
                <Link href="/transactions" className="inline-flex items-center gap-1 text-[12px] font-medium text-accent hover:underline">
                  View all <ArrowRight className="size-3" />
                </Link>
              }
            />
            <TransactionTable rows={d?.recent ?? []} loading={!d} onSelect={setSelected} compact />
          </Card>
          <p className="mt-3 text-[12px] text-fg-3">
            <Badge>Seed data</Badge> Historical transactions were generated by running the real governance engines; their payments are labelled as seed data.
          </p>
        </>
      )}
      <TransactionDrawer id={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
