"use client";

import { PayPalButtons, PayPalScriptProvider } from "@paypal/react-paypal-js";
import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, CreditCard, ExternalLink, Info, Loader2, RotateCw } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import { useInvalidateAll, useSystemStatus } from "@/lib/hooks";
import type { TransactionDetail } from "@/lib/types";

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5 text-[13px]">
      <span className="text-fg-3">{k}</span>
      <span className="truncate font-medium">{v}</span>
    </div>
  );
}

export function PaymentPanel({ tx, onUpdate }: { tx: TransactionDetail; onUpdate?: (tx: TransactionDetail) => void }) {
  const { data: status } = useSystemStatus();
  const invalidate = useInvalidateAll();
  const [error, setError] = useState<string | null>(null);

  const retry = useMutation({
    mutationFn: () => api.createOrder(tx.id),
    onSuccess: (t) => {
      onUpdate?.(t);
      invalidate();
    },
    onError: (e: Error) => setError(e.message),
  });

  const provider = tx.payment_provider;
  const settle = tx.settlement_amount != null && tx.settlement_currency && tx.settlement_currency !== tx.currency;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-[13px] font-semibold">Payment execution</h4>
        {provider === "paypal" && <Badge tone="info">PayPal {status?.payments.environment ?? "sandbox"}</Badge>}
        {provider === "simulated" && <Badge>Simulated</Badge>}
        {provider === "seed" && <Badge>Seed data</Badge>}
      </div>
      <div className="rounded-lg border border-border bg-surface px-3 py-1.5">
        <Row k="Amount" v={money(tx.amount, tx.currency)} />
        {settle && <Row k="Settlement" v={`${money(tx.settlement_amount!, tx.settlement_currency!)} · fixed demo FX rate`} />}
        <Row k={provider === "simulated" ? "Simulated order" : "PayPal order"} v={tx.paypal_order_id ? <span className="font-mono text-[12px]">{tx.paypal_order_id}</span> : "Not created"} />
        {tx.paypal_capture_id && <Row k="Capture" v={<span className="font-mono text-[12px]">{tx.paypal_capture_id}</span>} />}
        {tx.paypal_status && <Row k="Provider status" v={tx.paypal_status} />}
      </div>

      {provider === "simulated" && (
        <p className="mt-2 flex gap-2 text-[12px] text-fg-3">
          <Info className="mt-0.5 size-3.5 shrink-0" />
          Simulated payment: no PayPal credentials are configured, so no real PayPal transaction occurred. Add sandbox credentials to execute real orders.
        </p>
      )}
      {provider === "seed" && <p className="mt-2 text-[12px] text-fg-3">Historical seed transaction. No payment provider was contacted.</p>}

      {["BLOCKED", "DENIED"].includes(tx.status) && (
        <p className="mt-2 text-[12px] text-fg-3">PayPal was never contacted for this transaction. Governance stopped it first.</p>
      )}

      {tx.status === "APPROVED" && !tx.paypal_order_id && (
        <div className="mt-3 rounded-lg border border-bad/30 bg-bad-soft p-3">
          <p className="text-[13px] font-medium text-bad">Payment provider unavailable</p>
          <p className="mt-0.5 text-[12px] text-fg-2">{tx.failure_reason ?? "The payment provider could not be reached."}</p>
          <Button size="sm" variant="secondary" className="mt-2" onClick={() => retry.mutate()} disabled={retry.isPending}>
            {retry.isPending ? <Loader2 className="animate-spin" /> : <RotateCw />} Retry
          </Button>
        </div>
      )}

      {tx.status === "PAYMENT_CREATED" && provider === "paypal" && tx.paypal_order_id && (
        <div className="mt-3 rounded-lg border border-info/30 bg-info-soft/40 p-3">
          <p className="flex items-center gap-2 text-[13px] font-medium">
            <CreditCard className="size-4 text-info" /> PayPilot authorized this payment. Complete it with your PayPal sandbox buyer account.
          </p>
          {tx.failure_reason && <p className="mt-1 text-[12px] text-warn">{tx.failure_reason}</p>}
          {status?.payments.client_id ? (
            <div className="mt-3 max-w-sm">
              <PayPalScriptProvider options={{ clientId: status.payments.client_id, currency: tx.settlement_currency ?? "USD", intent: "capture" }}>
                <PayPalButtons
                  style={{ layout: "horizontal", height: 40, tagline: false }}
                  fundingSource="paypal"
                  createOrder={async () => tx.paypal_order_id!}
                  onApprove={async () => {
                    setError(null);
                    try {
                      const t = await api.captureOrder(tx.id, tx.paypal_order_id!);
                      onUpdate?.(t);
                      invalidate();
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                  onError={() => setError("PayPal checkout could not be completed. No money was moved.")}
                />
              </PayPalScriptProvider>
            </div>
          ) : null}
          {tx.paypal_approve_url && (
            <a href={tx.paypal_approve_url} className="mt-2 inline-flex items-center gap-1 text-[12px] font-medium text-info hover:underline">
              Or open PayPal checkout <ExternalLink className="size-3" />
            </a>
          )}
        </div>
      )}

      {tx.status === "COMPLETED" && provider !== "seed" && (
        <p className="mt-2 flex items-center gap-1.5 text-[12px] font-medium text-good">
          <CheckCircle2 className="size-3.5" /> {provider === "paypal" ? "Captured by PayPal" : "Simulated capture complete"}
        </p>
      )}
      {error && <p role="alert" className="mt-2 text-[12px] font-medium text-bad">{error}</p>}
    </div>
  );
}
