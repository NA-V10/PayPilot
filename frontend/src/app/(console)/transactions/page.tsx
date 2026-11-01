"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { EmptyState, ErrorState, PageHeader } from "@/components/states";
import { TransactionDrawer } from "@/components/trace/transaction-drawer";
import { TransactionTable } from "@/components/transaction-table";
import { Button } from "@/components/ui/button";
import { Card, Input, Select } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const FILTERS: { label: string; status?: string[] }[] = [
  { label: "All" },
  { label: "Completed", status: ["COMPLETED"] },
  { label: "Awaiting approval", status: ["AWAITING_APPROVAL"] },
  { label: "Blocked", status: ["BLOCKED", "DENIED"] },
  { label: "In flight", status: ["APPROVED", "PAYMENT_CREATED"] },
  { label: "Failed", status: ["FAILED"] },
];
const PAGE = 20;

function TransactionsView() {
  const params = useSearchParams();
  const [filter, setFilter] = useState(0);
  const [agent, setAgent] = useState("");
  const [risk, setRisk] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<string | null>(params.get("tx"));

  const query = useQuery({
    queryKey: ["transactions", filter, agent, risk, q, page],
    queryFn: () => api.transactions({ status: FILTERS[filter].status, agent_id: agent, risk_level: risk, q, limit: PAGE, offset: page * PAGE }),
    placeholderData: keepPreviousData,
  });
  const total = query.data?.total ?? 0;
  const reset = () => setPage(0);

  return (
    <div>
      <PageHeader eyebrow="Transactions" title="Every attempted payment" description="Click any row to investigate why PayPilot allowed, escalated or blocked it." />
      <Card>
        <div className="flex flex-col gap-3 border-b border-border p-4 lg:flex-row lg:items-center">
          <div className="flex flex-wrap gap-1" role="tablist" aria-label="Status filter">
            {FILTERS.map((f, i) => (
              <button
                key={f.label}
                role="tab"
                aria-selected={filter === i}
                onClick={() => {
                  setFilter(i);
                  reset();
                }}
                className={cn(
                  "rounded-md px-2.5 py-1 text-[13px] font-medium transition cursor-pointer",
                  filter === i ? "bg-surface-2 text-fg" : "text-fg-3 hover:text-fg",
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
          <div className="flex flex-1 flex-wrap items-center gap-2 lg:justify-end">
            <div className="relative w-full sm:w-56">
              <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-fg-3" />
              <Input
                placeholder="Search ID, merchant…"
                className="pl-8"
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  reset();
                }}
                aria-label="Search transactions"
              />
            </div>
            <Select aria-label="Agent" className="w-auto" value={agent} onChange={(e) => (setAgent(e.target.value), reset())}>
              <option value="">All agents</option>
              <option value="agt_travel">Travel Agent</option>
              <option value="agt_shopping">Shopping Agent</option>
              <option value="agt_business">Business Agent</option>
            </Select>
            <Select aria-label="Risk level" className="w-auto" value={risk} onChange={(e) => (setRisk(e.target.value), reset())}>
              <option value="">Any risk</option>
              <option value="LOW">Low</option>
              <option value="MEDIUM">Medium</option>
              <option value="HIGH">High</option>
              <option value="CRITICAL">Critical</option>
            </Select>
          </div>
        </div>
        {query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} className="m-4" />
        ) : query.data && query.data.items.length === 0 ? (
          <EmptyState title="No transactions match" description="Try a different filter, or run a scenario in the Command Center." />
        ) : (
          <TransactionTable rows={query.data?.items ?? []} loading={query.isPending} onSelect={setSelected} />
        )}
        {total > PAGE && (
          <div className="flex items-center justify-between border-t border-border px-5 py-3 text-[13px] text-fg-3">
            <span className="tabular">
              {page * PAGE + 1}–{Math.min(total, (page + 1) * PAGE)} of {total}
            </span>
            <div className="flex gap-1">
              <Button size="icon" variant="ghost" disabled={page === 0} onClick={() => setPage(page - 1)} aria-label="Previous page">
                <ChevronLeft />
              </Button>
              <Button size="icon" variant="ghost" disabled={(page + 1) * PAGE >= total} onClick={() => setPage(page + 1)} aria-label="Next page">
                <ChevronRight />
              </Button>
            </div>
          </div>
        )}
      </Card>
      <TransactionDrawer id={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

export default function TransactionsPage() {
  return (
    <Suspense>
      <TransactionsView />
    </Suspense>
  );
}
