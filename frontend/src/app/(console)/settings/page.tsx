"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2, RotateCcw } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/badges";
import { ErrorState, PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, Dialog, Skeleton } from "@/components/ui/primitives";
import { api, API_URL } from "@/lib/api";
import { useInvalidateAll, useSystemStatus } from "@/lib/hooks";

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-3 text-[13px] last:border-0">
      <span className="text-fg-2">{k}</span>
      <span className="text-right font-medium">{v}</span>
    </div>
  );
}

export default function SettingsPage() {
  const s = useSystemStatus();
  const invalidate = useInvalidateAll();
  const [confirm, setConfirm] = useState(false);
  const reset = useMutation({
    mutationFn: api.resetDemo,
    onSuccess: () => {
      setConfirm(false);
      invalidate();
    },
  });
  const d = s.data;

  return (
    <div className="max-w-3xl">
      <PageHeader eyebrow="Settings" title="System configuration" description="Configured on the server through environment variables. Secrets never reach the browser." />
      {s.isError && <ErrorState error={s.error} onRetry={() => s.refetch()} />}
      {s.isPending && <Skeleton className="h-64 rounded-xl" />}
      {d && (
        <div className="space-y-4">
          <Card>
            <CardHeader title="Payments" />
            <Row k="Provider" v={d.payments.mode === "paypal" ? <Badge tone="info">PayPal {d.payments.environment}</Badge> : <Badge>Simulated</Badge>} />
            <Row k="Connection" v={d.payments.mode === "paypal" ? (d.payments.connected ? <span className="text-good">Connected</span> : <span className="text-bad">Unreachable / bad credentials</span>) : "Not configured"} />
            <Row k="Settlement currency" v={d.payments.settlement_currency} />
            <Row k="Client ID (public)" v={<span className="font-mono text-[12px]">{d.payments.client_id ? `${d.payments.client_id.slice(0, 10)}…` : "—"}</span>} />
            {d.payments.mode === "simulated" && (
              <p className="px-5 pb-4 text-[12px] text-fg-3">
                Set <code className="font-mono">PAYPAL_CLIENT_ID</code> and <code className="font-mono">PAYPAL_CLIENT_SECRET</code> in the backend environment to execute real PayPal sandbox orders.
              </p>
            )}
          </Card>
          <Card>
            <CardHeader title="AI" />
            <Row k="Intent & policy compiling" v={d.llm.label} />
            <Row k="Transaction authorization" v={<Badge tone="good">Deterministic</Badge>} />
            <p className="px-5 pb-4 text-[12px] text-fg-3">
              The LLM only interprets language. It cannot approve, deny or execute payments, and its output is schema-validated. If a configured AI service fails during
              a request, the transaction fails closed.
            </p>
          </Card>
          <Card>
            <CardHeader title="Environment" />
            <Row k="API endpoint" v={<span className="font-mono text-[12px]">{API_URL}</span>} />
            <Row k="Demo mode" v={d.demo_mode ? <Badge tone="accent">On</Badge> : <Badge>Off</Badge>} />
          </Card>
          {d.demo_mode && (
            <Card className="p-5">
              <p className="text-[13px] font-medium">Reset demo data</p>
              <p className="mt-0.5 text-[12px] text-fg-3">Restores the seeded agents, policies, merchants and transaction history. All changes are discarded.</p>
              <Button variant="secondary" size="sm" className="mt-3" onClick={() => setConfirm(true)}>
                <RotateCcw /> Reset demo data
              </Button>
            </Card>
          )}
        </div>
      )}
      <Dialog open={confirm} onOpenChange={setConfirm} title="Reset demo data?" description="This deletes every transaction, policy change and audit event created since seeding.">
        {reset.error && <p className="mb-3 text-[12px] text-bad">{(reset.error as Error).message}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setConfirm(false)}>
            Cancel
          </Button>
          <Button variant="danger" onClick={() => reset.mutate()} disabled={reset.isPending}>
            {reset.isPending && <Loader2 className="animate-spin" />} Reset
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
