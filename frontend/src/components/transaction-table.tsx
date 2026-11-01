"use client";

import { PolicyBadge, ProviderBadge, RiskBadge, StatusBadge } from "@/components/badges";
import { Skeleton } from "@/components/ui/primitives";
import { money, timeAgo } from "@/lib/format";
import type { Transaction } from "@/lib/types";
import { cn } from "@/lib/utils";

export function TransactionTable({ rows, onSelect, loading, compact = false }: { rows: Transaction[]; onSelect: (id: string) => void; loading?: boolean; compact?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-[13px]">
        <thead>
          <tr className="border-b border-border text-[11px] font-medium uppercase tracking-wide text-fg-3">
            <th className="py-2.5 pl-5 pr-3 font-medium">Transaction</th>
            <th className="px-3 font-medium">Agent</th>
            <th className="px-3 font-medium">Merchant</th>
            <th className="px-3 text-right font-medium">Amount</th>
            <th className="px-3 font-medium">Risk</th>
            <th className="px-3 font-medium">Policy</th>
            <th className="px-3 font-medium">Status</th>
            <th className="pl-3 pr-5 text-right font-medium">Time</th>
          </tr>
        </thead>
        <tbody>
          {loading &&
            Array.from({ length: compact ? 5 : 8 }).map((_, i) => (
              <tr key={i} className="border-b border-border last:border-0">
                <td colSpan={8} className="px-5 py-3">
                  <Skeleton className="h-5" />
                </td>
              </tr>
            ))}
          {rows.map((t) => (
            <tr
              key={t.id}
              tabIndex={0}
              role="button"
              aria-label={`Open transaction ${t.id}`}
              onClick={() => onSelect(t.id)}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onSelect(t.id))}
              className="cursor-pointer border-b border-border transition-colors last:border-0 hover:bg-surface-2/60 focus-visible:bg-surface-2 focus-visible:outline-none"
            >
              <td className="py-3 pl-5 pr-3">
                <div className="font-mono text-[12px] font-medium">{t.id}</div>
                {!compact && <div className="max-w-56 truncate text-[12px] text-fg-3">{t.description}</div>}
              </td>
              <td className="px-3 text-fg-2">{t.agent.name}</td>
              <td className="px-3">
                <div className={cn("text-fg-2", t.merchant && t.merchant.trust_score < 60 && "text-bad")}>{t.merchant?.name ?? "—"}</div>
              </td>
              <td className="px-3 text-right font-medium tabular">{t.amount ? money(t.amount, t.currency) : "—"}</td>
              <td className="px-3">
                <RiskBadge level={t.risk_level} />
              </td>
              <td className="px-3">
                <PolicyBadge decision={t.policy_decision} />
              </td>
              <td className="px-3">
                <div className="flex items-center gap-1.5">
                  <StatusBadge status={t.status} />
                  {!compact && t.status === "COMPLETED" && <ProviderBadge provider={t.payment_provider} />}
                </div>
              </td>
              <td className="whitespace-nowrap pl-3 pr-5 text-right text-fg-3 tabular">{timeAgo(t.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
