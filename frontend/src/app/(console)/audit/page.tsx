"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/badges";
import { EmptyState, ErrorState, PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, Select, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { dateTime } from "@/lib/format";

const TYPES = [
  "INTENT_RECEIVED", "MERCHANT_FOUND", "MERCHANT_ANALYZED", "SECURITY_SCANNED", "PROMPT_INJECTION_DETECTED", "RISK_ASSESSED",
  "POLICY_EVALUATED", "APPROVAL_REQUESTED", "APPROVED", "DENIED", "PAYPAL_ORDER_CREATED", "PAYPAL_PAYMENT_CAPTURED",
  "PAYMENT_FAILED", "TRANSACTION_COMPLETED", "TRANSACTION_BLOCKED", "TRANSACTION_DENIED", "FAIL_CLOSED", "POLICY_UPDATED",
];
const PAGE = 50;
const OUTCOME_TONE = { pass: "good", fail: "bad", warn: "warn", info: "neutral", skip: "neutral" } as const;

export default function AuditPage() {
  const [type, setType] = useState("");
  const [page, setPage] = useState(0);
  const q = useQuery({
    queryKey: ["audit", type, page],
    queryFn: () => api.audit({ event_type: type, limit: PAGE, offset: page * PAGE }),
    placeholderData: keepPreviousData,
  });
  const total = q.data?.total ?? 0;

  return (
    <div>
      <PageHeader
        eyebrow="Audit Log"
        title="Immutable decision record"
        description="Every stage of every transaction, with actor, outcome and correlation ID."
        actions={
          <Select aria-label="Event type" className="w-64" value={type} onChange={(e) => (setType(e.target.value), setPage(0))}>
            <option value="">All events</option>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
        }
      />
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-border text-[11px] uppercase tracking-wide text-fg-3">
                <th className="py-2.5 pl-5 font-medium">Time</th>
                <th className="px-3 font-medium">Event</th>
                <th className="px-3 font-medium">Actor</th>
                <th className="px-3 font-medium">Message</th>
                <th className="pr-5 pl-3 font-medium">Trace</th>
              </tr>
            </thead>
            <tbody>
              {q.isPending && (
                <tr>
                  <td colSpan={5} className="p-5">
                    <Skeleton className="h-64" />
                  </td>
                </tr>
              )}
              {q.data?.items.map((e) => (
                <tr key={e.id} className="border-b border-border align-top last:border-0">
                  <td className="py-2.5 pl-5 whitespace-nowrap text-fg-3 tabular">{dateTime(e.timestamp)}</td>
                  <td className="px-3 py-2.5">
                    <Badge tone={OUTCOME_TONE[e.outcome ?? "info"]} className="font-mono normal-case tracking-normal">
                      {e.event_type}
                    </Badge>
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap text-fg-2">{e.actor}</td>
                  <td className="px-3 py-2.5">{e.message}</td>
                  <td className="py-2.5 pr-5 pl-3 whitespace-nowrap">
                    {e.transaction_id ? (
                      <Link href={`/trace/${e.transaction_id}`} className="font-mono text-[12px] text-accent hover:underline">
                        {e.trace_id}
                      </Link>
                    ) : (
                      <span className="text-fg-3">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {q.data?.items.length === 0 && <EmptyState title="No events" />}
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
    </div>
  );
}
