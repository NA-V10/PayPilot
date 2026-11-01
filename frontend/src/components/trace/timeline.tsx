"use client";

import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Check, ChevronRight, Circle, X } from "lucide-react";
import { useState } from "react";
import { clock } from "@/lib/format";
import type { AuditEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

const STAGE_LABEL: Record<string, string> = {
  intent: "Intent Engine",
  agent: "Agent",
  shield: "AgentShield",
  risk: "Risk Engine",
  policy: "Policy Engine",
  approval: "Approval Engine",
  paypal: "Payment",
  complete: "Settlement",
};

function OutcomeDot({ outcome }: { outcome: AuditEvent["outcome"] }) {
  const cls = {
    pass: "bg-good-soft text-good",
    fail: "bg-bad-soft text-bad",
    warn: "bg-warn-soft text-warn",
    info: "bg-surface-2 text-fg-3",
    skip: "bg-surface-2 text-fg-3",
  }[outcome ?? "info"];
  return (
    <span className={cn("grid size-6 place-items-center rounded-full", cls)}>
      {outcome === "pass" ? <Check className="size-3.5" strokeWidth={3} /> : outcome === "fail" ? <X className="size-3.5" strokeWidth={3} /> : outcome === "warn" ? <AlertTriangle className="size-3" /> : <Circle className="size-2 fill-current" />}
    </span>
  );
}

export function TraceTimeline({ events, showMs = true }: { events: AuditEvent[]; showMs?: boolean }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <ol className="relative" aria-label="Transaction trace">
      <AnimatePresence initial={false}>
        {events.map((e, i) => {
          const expanded = open === e.id;
          return (
            <motion.li
              key={e.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
              className="relative grid grid-cols-[76px_24px_1fr] gap-x-3 pb-1"
            >
              <time className="pt-[3px] text-right font-mono text-[11px] text-fg-3 tabular">{clock(e.timestamp, showMs)}</time>
              <div className="relative flex flex-col items-center">
                <OutcomeDot outcome={e.outcome} />
                {i < events.length - 1 && <span className="mt-1 w-px flex-1 bg-border-strong" />}
              </div>
              <div className="min-w-0 pb-3">
                <button
                  onClick={() => setOpen(expanded ? null : e.id)}
                  className="group flex w-full items-start gap-2 text-left cursor-pointer"
                  aria-expanded={expanded}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2 text-[11px] font-semibold uppercase tracking-wide text-fg-3">
                      <span>{STAGE_LABEL[e.stage ?? ""] ?? e.stage}</span>
                      <span className="font-mono font-normal normal-case tracking-normal opacity-70">{e.event_type}</span>
                      {e.duration_ms != null && Number(e.duration_ms) > 0 && <span className="font-mono font-normal normal-case tracking-normal opacity-70">{Number(e.duration_ms).toFixed(1)} ms</span>}
                    </div>
                    <p className={cn("mt-0.5 text-[13px] leading-snug", e.outcome === "fail" ? "text-bad font-medium" : e.outcome === "warn" ? "text-warn font-medium" : "text-fg")}>{e.message}</p>
                  </div>
                  {Object.keys(e.metadata ?? {}).length > 0 && (
                    <ChevronRight className={cn("mt-1 size-3.5 shrink-0 text-fg-3 transition group-hover:text-fg", expanded && "rotate-90")} />
                  )}
                </button>
                {expanded && (
                  <pre className="mt-2 max-h-72 overflow-auto rounded-lg border border-border bg-surface-2 p-3 font-mono text-[11px] leading-relaxed text-fg-2">
                    {JSON.stringify(e.metadata, null, 2)}
                  </pre>
                )}
              </div>
            </motion.li>
          );
        })}
      </AnimatePresence>
    </ol>
  );
}
