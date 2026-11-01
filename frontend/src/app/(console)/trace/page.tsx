"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { RiskBadge, StatusBadge } from "@/components/badges";
import { ErrorState, PageHeader } from "@/components/states";
import { Card, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { money, timeAgo } from "@/lib/format";

export default function TraceIndexPage() {
  const q = useQuery({ queryKey: ["transactions", "trace-index"], queryFn: () => api.transactions({ limit: 40 }) });
  return (
    <div className="max-w-4xl">
      <PageHeader
        eyebrow="Agent Trace"
        title="Follow any decision end to end"
        description="Each transaction carries a trace ID. Every stage from intent to settlement is recorded as an event you can inspect."
      />
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      <Card className="divide-y divide-border">
        {q.isPending && Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="m-4 h-8" />)}
        {q.data?.items.map((t) => (
          <Link key={t.id} href={`/trace/${t.id}`} className="group flex items-center gap-4 px-5 py-3 hover:bg-surface-2/60">
            <div className="w-28 shrink-0">
              <p className="font-mono text-[12px] font-medium">{t.id}</p>
              <p className="font-mono text-[11px] text-fg-3">{t.trace_id}</p>
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-medium">{t.description}</p>
              <p className="truncate text-[12px] text-fg-3">
                {t.agent.name} → {t.merchant?.name ?? "—"} · {timeAgo(t.created_at)}
              </p>
            </div>
            <span className="hidden text-[13px] font-medium tabular sm:block">{t.amount ? money(t.amount, t.currency) : "—"}</span>
            <span className="hidden md:block">
              <RiskBadge level={t.risk_level} />
            </span>
            <StatusBadge status={t.status} />
            <ChevronRight className="size-4 text-fg-3 group-hover:text-fg" />
          </Link>
        ))}
      </Card>
    </div>
  );
}
