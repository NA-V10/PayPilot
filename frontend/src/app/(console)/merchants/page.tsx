"use client";

import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/badges";
import { ErrorState, PageHeader } from "@/components/states";
import { Card, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { Merchant } from "@/lib/types";

const VERIFY_TONE = { VERIFIED: "good", PENDING: "warn", UNVERIFIED: "warn", FLAGGED: "bad" } as const;

function days(iso: string) {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
}

function TrustBar({ m }: { m: Merchant }) {
  const color = m.trust_score >= 80 ? "bg-good" : m.trust_score >= 60 ? "bg-warn" : "bg-bad";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-2" aria-hidden>
        <div className={`h-full ${color}`} style={{ width: `${m.trust_score}%` }} />
      </div>
      <span className="font-mono text-[12px] tabular">{m.trust_score}</span>
    </div>
  );
}

export default function MerchantsPage() {
  const q = useQuery({ queryKey: ["merchants"], queryFn: api.merchants });
  return (
    <div>
      <PageHeader eyebrow="Merchants" title="Merchant intelligence" description="Trust signals PayPilot uses in the risk and policy engines." />
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-border text-[11px] uppercase tracking-wide text-fg-3">
                <th className="py-2.5 pl-5 font-medium">Merchant</th>
                <th className="px-3 font-medium">Trust</th>
                <th className="px-3 font-medium">Verification</th>
                <th className="px-3 font-medium">Categories</th>
                <th className="px-3 text-right font-medium">Refunds</th>
                <th className="px-3 text-right font-medium">Chargebacks</th>
                <th className="px-3 font-medium">Country</th>
                <th className="pr-5 pl-3 text-right font-medium">Age</th>
              </tr>
            </thead>
            <tbody>
              {q.isPending && (
                <tr>
                  <td colSpan={8} className="p-5">
                    <Skeleton className="h-40" />
                  </td>
                </tr>
              )}
              {q.data?.map((m) => {
                const age = days(m.onboarded_at);
                return (
                  <tr key={m.id} className="border-b border-border last:border-0">
                    <td className="py-3 pl-5">
                      <p className="font-medium">{m.name}</p>
                      <p className="font-mono text-[12px] text-fg-3">{m.domain}</p>
                    </td>
                    <td className="px-3">
                      <TrustBar m={m} />
                    </td>
                    <td className="px-3">
                      <Badge tone={VERIFY_TONE[m.verification_status]}>{m.verification_status.toLowerCase()}</Badge>
                    </td>
                    <td className="px-3 text-fg-2">{m.categories.map((c) => c.replace(/_/g, " ")).join(", ")}</td>
                    <td className={`px-3 text-right tabular ${m.refund_rate > 0.1 ? "text-bad" : "text-fg-2"}`}>{(m.refund_rate * 100).toFixed(1)}%</td>
                    <td className={`px-3 text-right tabular ${m.chargeback_rate > 0.02 ? "text-bad" : "text-fg-2"}`}>{(m.chargeback_rate * 100).toFixed(2)}%</td>
                    <td className="px-3 text-fg-2">{m.country}</td>
                    <td className="pr-5 pl-3 text-right tabular text-fg-2">
                      {age < 30 ? <Badge tone="warn">new · {age}d</Badge> : age > 365 ? `${(age / 365).toFixed(1)}y` : `${age}d`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
