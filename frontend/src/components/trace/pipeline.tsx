"use client";

import { motion } from "framer-motion";
import { Ban, Bot, Check, CreditCard, Flag, Gauge, Hourglass, Minus, ScrollText, ShieldCheck, Sparkles, UserCheck, X } from "lucide-react";
import type { AuditEvent, Stage, TxStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

export const STAGES: { id: Stage; label: string; sub: string; icon: typeof Bot }[] = [
  { id: "intent", label: "Intent", sub: "Understand request", icon: Sparkles },
  { id: "agent", label: "Agent", sub: "Search & propose", icon: Bot },
  { id: "shield", label: "AgentShield", sub: "Injection defense", icon: ShieldCheck },
  { id: "risk", label: "Risk", sub: "Score 0–100", icon: Gauge },
  { id: "policy", label: "Policy", sub: "Deterministic rules", icon: ScrollText },
  { id: "approval", label: "Approval", sub: "Final decision", icon: UserCheck },
  { id: "paypal", label: "PayPal", sub: "Order & capture", icon: CreditCard },
  { id: "complete", label: "Complete", sub: "Settled", icon: Flag },
];

export type NodeState = "idle" | "active" | "pass" | "warn" | "fail" | "skipped" | "waiting";

export function stageStates(events: AuditEvent[], status: TxStatus | undefined, done: boolean): Record<Stage, NodeState> {
  const out = {} as Record<Stage, NodeState>;
  const terminalStop = status === "BLOCKED" || status === "DENIED" || status === "FAILED";
  let nextFound = false;
  for (const s of STAGES) {
    const ev = events.filter((e) => e.stage === s.id);
    if (ev.length) {
      out[s.id] = ev.some((e) => e.outcome === "fail") ? "fail" : ev.some((e) => e.outcome === "warn") ? "warn" : "pass";
      continue;
    }
    if (!done) {
      out[s.id] = nextFound ? "idle" : "active";
      nextFound = true;
    } else if (terminalStop) {
      out[s.id] = "skipped";
    } else if (status === "AWAITING_APPROVAL" || status === "PAYMENT_CREATED" || status === "APPROVED") {
      out[s.id] = "waiting";
    } else {
      out[s.id] = "skipped";
    }
  }
  // The approval stage on a paused transaction is a wait state, not a warning.
  if (done && status === "AWAITING_APPROVAL") out.approval = "waiting";
  return out;
}

const NODE_STYLE: Record<NodeState, string> = {
  idle: "border-border bg-surface text-fg-3",
  active: "border-accent bg-accent-soft text-accent",
  pass: "border-good/40 bg-good-soft text-good",
  warn: "border-warn/50 bg-warn-soft text-warn",
  fail: "border-bad/50 bg-bad-soft text-bad",
  skipped: "border-dashed border-border-strong bg-transparent text-fg-3/60",
  waiting: "border-warn/50 bg-warn-soft text-warn",
};

function StateIcon({ state, Icon }: { state: NodeState; Icon: typeof Bot }) {
  if (state === "pass") return <Check className="size-4" strokeWidth={2.5} />;
  if (state === "fail") return <X className="size-4" strokeWidth={2.5} />;
  if (state === "skipped") return <Minus className="size-4" />;
  if (state === "waiting") return <Hourglass className="size-4" />;
  return <Icon className="size-4" />;
}

const STATE_TEXT: Record<NodeState, string> = {
  idle: "Pending",
  active: "Evaluating",
  pass: "Passed",
  warn: "Flagged",
  fail: "Failed",
  skipped: "Not reached",
  waiting: "Waiting",
};

export function Pipeline({ events, status, done, compact = false }: { events: AuditEvent[]; status?: TxStatus; done: boolean; compact?: boolean }) {
  const states = stageStates(events, status, done);
  const finalBlocked = done && (status === "BLOCKED" || status === "DENIED");
  return (
    <ol className={cn("grid gap-2", compact ? "grid-cols-4 sm:grid-cols-8" : "grid-cols-2 sm:grid-cols-4 xl:grid-cols-8")} aria-label="Transaction pipeline">
      {STAGES.map((s, i) => {
        let state = states[s.id];
        let label = s.label;
        let Icon = s.icon;
        let sub = s.sub;
        if (s.id === "complete" && finalBlocked) {
          sub = "No payment";
          state = "fail";
          label = status === "DENIED" ? "Denied" : "Blocked";
          Icon = Ban;
        }
        return (
          <li key={s.id} className="relative">
            <motion.div
              layout
              initial={false}
              animate={{ scale: state === "active" ? 1.02 : 1 }}
              className={cn(
                "relative flex h-full flex-col gap-2 rounded-lg border px-3 py-2.5 transition-colors duration-300",
                NODE_STYLE[state],
                compact && "items-center px-2 py-2 text-center",
              )}
            >
              <div className={cn("flex items-center gap-2", compact && "flex-col gap-1")}>
                <span className={cn("grid size-6 shrink-0 place-items-center rounded-md", state === "idle" || state === "skipped" ? "bg-surface-2" : "bg-surface/60")}>
                  {state === "active" ? (
                    <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 1.2, repeat: Infinity }}>
                      <Icon className="size-4" />
                    </motion.span>
                  ) : (
                    <StateIcon state={state} Icon={Icon} />
                  )}
                </span>
                <span className={cn("text-[13px] font-semibold", state === "idle" || state === "skipped" ? "text-fg-3" : "text-fg")}>{label}</span>
              </div>
              {!compact && (
                <div className="flex items-center justify-between gap-1 text-[11px]">
                  <span className="truncate text-fg-3">{sub}</span>
                  <span className="shrink-0 font-semibold uppercase tracking-wide">{STATE_TEXT[state]}</span>
                </div>
              )}
              <span className="sr-only">
                {label}: {STATE_TEXT[state]}
              </span>
            </motion.div>
            {i < STAGES.length - 1 && <span aria-hidden className="absolute top-1/2 -right-2 hidden h-px w-2 bg-border-strong xl:block" />}
          </li>
        );
      })}
    </ol>
  );
}
