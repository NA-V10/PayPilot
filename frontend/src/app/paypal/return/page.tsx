"use client";

import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Loader2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef } from "react";
import { Logo } from "@/components/logo";
import { ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { money } from "@/lib/format";

/** PayPal redirect flow: the buyer lands here after approving, and we capture server-side. */
function Capture() {
  const params = useSearchParams();
  const txId = params.get("tx");
  const orderId = params.get("token");
  const started = useRef(false);
  const capture = useMutation({ mutationFn: () => api.captureOrder(txId!, orderId!) });

  useEffect(() => {
    if (txId && orderId && !started.current) {
      started.current = true;
      capture.mutate();
    }
  }, [txId, orderId, capture]);

  if (!txId || !orderId) return <ErrorState error={new Error("Missing transaction or PayPal order reference.")} title="Invalid return link" />;
  if (capture.isError) return <ErrorState error={capture.error} title="Capture failed" onRetry={() => capture.mutate()} />;
  if (!capture.data)
    return (
      <p className="flex items-center gap-2 text-fg-2">
        <Loader2 className="size-4 animate-spin" /> Capturing PayPal payment…
      </p>
    );
  const tx = capture.data;
  return (
    <div className="text-center">
      {tx.status === "COMPLETED" ? <CheckCircle2 className="mx-auto size-8 text-good" /> : null}
      <p className="mt-3 text-xl font-semibold">{tx.status === "COMPLETED" ? "Payment completed" : "Payment not completed"}</p>
      <p className="mt-1 text-fg-2">
        {money(tx.amount, tx.currency)} · {tx.merchant?.name}
      </p>
      {tx.failure_reason && <p className="mt-2 text-[13px] text-warn">{tx.failure_reason}</p>}
      <Button asChild className="mt-6">
        <Link href={`/trace/${tx.id}`}>View trace</Link>
      </Button>
    </div>
  );
}

export default function PayPalReturnPage() {
  return (
    <div className="grid min-h-screen place-items-center px-4">
      <div className="w-full max-w-md">
        <Logo className="mb-10 flex justify-center" />
        <Suspense>
          <Capture />
        </Suspense>
      </div>
    </div>
  );
}
