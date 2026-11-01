"use client";

import { AnimatePresence, motion } from "framer-motion";
import { FastForward, Timer } from "lucide-react";
import { useEffect } from "react";
import { StatusBadge } from "@/components/badges";
import { Card } from "@/components/ui/primitives";
import { money } from "@/lib/format";
import type { TransactionDetail } from "@/lib/types";
import { ApprovalBar, GovernanceDetails } from "./investigation";
import { PaymentPanel } from "./payment-panel";
import { Pipeline } from "./pipeline";
import { DecisionSummary } from "./sections";
import { TraceTimeline } from "./timeline";
import { useReplay } from "./use-replay";

/**
 * Shows a governed transaction as it moved through the pipeline. The events are the real
 * recorded trace; they are revealed at presentation pace (labelled) so humans can follow.
 */
export function LiveRun({
  tx,
  runKey,
  onUpdate,
  onDone,
  showDetails = true,
  paceMs,
}: {
  tx: TransactionDetail;
  runKey: string;
  onUpdate?: (t: TransactionDetail) => void;
  onDone?: () => void;
  showDetails?: boolean;
  paceMs?: number;
}) {
  const { shown, done, skip } = useReplay(tx.events.length, runKey, paceMs);
  const visible = tx.events.slice(0, shown);
  const engineMs = tx.events.reduce((s, e) => s + (Number(e.duration_ms) || 0), 0);

  useEffect(() => {
    if (done) onDone?.();
  }, [done, onDone]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="min-w-0">
          <p className="font-mono text-[12px] text-fg-3">
            {tx.id} · {tx.trace_id}
          </p>
          <p className="truncate text-[15px] font-semibold">
            {tx.agent.name} → {tx.merchant?.name ?? "—"} · <span className="tabular">{tx.amount ? money(tx.amount, tx.currency) : "—"}</span>
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {done ? (
            <StatusBadge status={tx.status} />
          ) : (
            <button onClick={skip} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[12px] font-medium text-fg-3 hover:bg-surface-2 hover:text-fg cursor-pointer">
              <FastForward className="size-3.5" /> Skip
            </button>
          )}
        </div>
      </div>

      <Pipeline events={visible} status={tx.status} done={done} />

      <p className="flex items-center gap-1.5 text-[11px] text-fg-3">
        <Timer className="size-3" />
        Governance engines ran in {engineMs.toFixed(1)} ms. Recorded events are replayed at presentation speed.
      </p>

      <div className={showDetails ? "grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]" : ""}>
        <Card className="p-4">
          <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-fg-3">Event stream</p>
          <TraceTimeline events={visible} />
        </Card>
        {showDetails && (
          <AnimatePresence>
            {done && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
                <DecisionSummary tx={tx} />
                <ApprovalBar tx={tx} onUpdate={onUpdate} />
                {tx.status !== "AWAITING_APPROVAL" && <PaymentPanel tx={tx} onUpdate={onUpdate} />}
                <Card className="p-4">
                  <GovernanceDetails tx={tx} />
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
