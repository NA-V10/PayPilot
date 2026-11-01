"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { BookCheck, Briefcase, Plane, ShoppingBag, TerminalSquare } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/badges";
import { ErrorState, PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, Skeleton, Switch } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import { useInvalidateAll } from "@/lib/hooks";
import type { Agent } from "@/lib/types";

const ICON = { travel: Plane, shopping: ShoppingBag, business: Briefcase };

function Meter({ label, used, limit, currency }: { label: string; used: number; limit: number; currency: string }) {
  const pct = Math.min(100, (used / Math.max(1, limit)) * 100);
  return (
    <div>
      <div className="flex justify-between text-[12px]">
        <span className="text-fg-3">{label}</span>
        <span className="tabular text-fg-2">
          {money(used, currency, { compact: true })} / {money(limit, currency, { compact: true })}
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-2" role="meter" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
        <div className={pct > 85 ? "h-full bg-bad" : pct > 60 ? "h-full bg-warn" : "h-full bg-accent"} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function AgentCard({ agent }: { agent: Agent }) {
  const invalidate = useInvalidateAll();
  const toggle = useMutation({ mutationFn: (active: boolean) => api.setAgentStatus(agent.id, active ? "ACTIVE" : "PAUSED"), onSuccess: invalidate });
  const Icon = ICON[agent.type] ?? Plane;
  const p = agent.policy;
  const s = agent.stats;
  const active = agent.status === "ACTIVE";
  return (
    <Card className="flex flex-col p-5">
      <div className="flex items-start gap-3">
        <span className="grid size-10 place-items-center rounded-lg bg-surface-2">
          <Icon className="size-5 text-fg-2" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{agent.name}</p>
          <p className="text-[13px] text-fg-3">{agent.description}</p>
        </div>
        <Switch checked={active} onCheckedChange={(v) => toggle.mutate(v)} label={`${agent.name} active`} />
      </div>
      <div className="mt-3">
        <Badge tone={active ? "good" : "neutral"}>{active ? "Active" : "Paused"}</Badge>
      </div>
      {p && s && (
        <>
          <div className="mt-5 space-y-3">
            <Meter label="Today" used={s.spent_today} limit={p.daily_spending_limit} currency={p.currency} />
            <Meter label="This month" used={s.spent_month} limit={p.monthly_spending_limit} currency={p.currency} />
          </div>
          <dl className="mt-5 grid grid-cols-2 gap-3 border-t border-border pt-4 text-[13px]">
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-fg-3">Autonomous up to</dt>
              <dd className="font-medium tabular">{money(p.require_approval_above, p.currency)}</dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-fg-3">Hard maximum</dt>
              <dd className="font-medium tabular">{money(p.max_transaction_amount, p.currency)}</dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-fg-3">Min. merchant trust</dt>
              <dd className="font-medium">{p.minimum_merchant_trust}%</dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-fg-3">Transactions</dt>
              <dd className="font-medium tabular">
                {s.transactions} <span className="text-fg-3">· {s.blocked} blocked</span>
              </dd>
            </div>
          </dl>
          <div className="mt-3 flex flex-wrap gap-1">
            {p.allowed_categories.map((c) => (
              <Badge key={c} tone="good">{c.replace(/_/g, " ")}</Badge>
            ))}
            {p.blocked_categories.map((c) => (
              <Badge key={c} tone="bad">no {c.replace(/_/g, " ")}</Badge>
            ))}
          </div>
        </>
      )}
      <div className="mt-auto flex gap-2 pt-5">
        <Button asChild size="sm" variant="secondary">
          <Link href="/command-center">
            <TerminalSquare /> Give a task
          </Link>
        </Button>
        <Button asChild size="sm" variant="ghost">
          <Link href="/policies">
            <BookCheck /> Policy
          </Link>
        </Button>
      </div>
    </Card>
  );
}

export default function AgentsPage() {
  const q = useQuery({ queryKey: ["agents"], queryFn: api.agents });
  return (
    <div>
      <PageHeader
        eyebrow="Agents"
        title="Your autonomous agents"
        description="Every agent shares one governance layer. Agents can reason and propose; only PayPilot can authorize spending."
      />
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {q.isPending && Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-[420px] rounded-xl" />)}
        {q.data?.map((a) => <AgentCard key={a.id} agent={a} />)}
      </div>
    </div>
  );
}
