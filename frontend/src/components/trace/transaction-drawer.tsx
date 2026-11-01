"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { StatusBadge } from "@/components/badges";
import { ErrorState } from "@/components/states";
import { Sheet, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { TransactionInvestigation } from "./investigation";

export function TransactionDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["tx", id], queryFn: () => api.transaction(id!), enabled: !!id });
  return (
    <Sheet
      open={!!id}
      onOpenChange={(o) => !o && onClose()}
      title={
        <span className="flex items-center gap-2">
          <span className="font-mono">{id}</span>
          {q.data && <StatusBadge status={q.data.status} />}
        </span>
      }
      description={
        q.data ? (
          <span className="flex items-center gap-3">
            {dateTime(q.data.created_at)}
            <Link href={`/trace/${id}`} className="inline-flex items-center gap-0.5 font-medium text-accent hover:underline">
              Open full trace <ArrowUpRight className="size-3" />
            </Link>
          </span>
        ) : undefined
      }
    >
      <div className="p-6">
        {q.isPending && (
          <div className="space-y-3">
            <Skeleton className="h-10 w-48" />
            <Skeleton className="h-16" />
            <Skeleton className="h-40" />
          </div>
        )}
        {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
        {q.data && <TransactionInvestigation tx={q.data} onUpdate={(t) => qc.setQueryData(["tx", id], t)} />}
      </div>
    </Sheet>
  );
}
