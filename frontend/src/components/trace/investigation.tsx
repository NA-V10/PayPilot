"use client";

import { Check, Loader2, X } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, Tabs, TabsContent, TabsList, TabsTrigger, Textarea } from "@/components/ui/primitives";
import { useApprovalActions } from "@/lib/hooks";
import type { TransactionDetail } from "@/lib/types";
import { PaymentPanel } from "./payment-panel";
import { Pipeline } from "./pipeline";
import { DecisionSummary, PolicyChecks, RiskBreakdown, ShieldReport, TxFacts } from "./sections";
import { TraceTimeline } from "./timeline";

export function ApprovalBar({ tx, onUpdate }: { tx: TransactionDetail; onUpdate?: (t: TransactionDetail) => void }) {
  const { approve, deny } = useApprovalActions();
  const [note, setNote] = useState("");
  const err = approve.error ?? deny.error;
  if (tx.status !== "AWAITING_APPROVAL") return null;
  const busy = approve.isPending || deny.isPending;
  return (
    <div className="rounded-xl border border-warn/40 bg-warn-soft/60 p-4">
      <p className="text-[13px] font-semibold">Your decision</p>
      <p className="mt-0.5 text-[12px] text-fg-2">{tx.approval_reason}</p>
      <Textarea rows={2} className="mt-3 bg-surface" placeholder="Optional note for the audit log" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} />
      <div className="mt-3 flex gap-2">
        <Button variant="secondary" disabled={busy} onClick={() => deny.mutate({ id: tx.id, note: note || undefined }, { onSuccess: onUpdate })}>
          {deny.isPending ? <Loader2 className="animate-spin" /> : <X />} Deny
        </Button>
        <Button variant="good" disabled={busy} onClick={() => approve.mutate({ id: tx.id, note: note || undefined }, { onSuccess: onUpdate })}>
          {approve.isPending ? <Loader2 className="animate-spin" /> : <Check />} Approve & pay
        </Button>
      </div>
      <p className="mt-2 text-[11px] text-fg-3">Approving re-checks hard policy limits before any payment is created.</p>
      {err && <p role="alert" className="mt-2 text-[12px] font-medium text-bad">{(err as Error).message}</p>}
    </div>
  );
}

export function GovernanceDetails({ tx }: { tx: TransactionDetail }) {
  return (
    <div className="grid gap-5">
      {tx.shield_result && <ShieldReport shield={tx.shield_result} />}
      {tx.risk_assessment && <RiskBreakdown risk={tx.risk_assessment} />}
      {tx.policy_result && <PolicyChecks result={tx.policy_result} />}
      {!tx.shield_result && !tx.risk_assessment && !tx.policy_result && (
        <p className="text-[13px] text-fg-3">No governance results were recorded. The pipeline stopped before evaluation (fail closed).</p>
      )}
    </div>
  );
}

export function TransactionInvestigation({ tx, onUpdate }: { tx: TransactionDetail; onUpdate?: (t: TransactionDetail) => void }) {
  return (
    <div className="space-y-5">
      <TxFacts tx={tx} />
      <Pipeline events={tx.events} status={tx.status} done compact />
      <DecisionSummary tx={tx} />
      <ApprovalBar tx={tx} onUpdate={onUpdate} />
      <Tabs defaultValue="decision">
        <TabsList>
          <TabsTrigger value="decision">Why</TabsTrigger>
          <TabsTrigger value="trace">Trace ({tx.events.length})</TabsTrigger>
          <TabsTrigger value="payment">Payment</TabsTrigger>
        </TabsList>
        <TabsContent value="decision" className="mt-4">
          <GovernanceDetails tx={tx} />
        </TabsContent>
        <TabsContent value="trace" className="mt-4">
          <Card className="p-4">
            <TraceTimeline events={tx.events} />
          </Card>
        </TabsContent>
        <TabsContent value="payment" className="mt-4">
          <PaymentPanel tx={tx} onUpdate={onUpdate} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
