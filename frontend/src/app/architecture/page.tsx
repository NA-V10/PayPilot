"use client";

import { ArrowDown, ArrowRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/badges";
import { LogoMark } from "@/components/logo";
import { MarketingFooter, MarketingHeader } from "@/components/marketing";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Comp = { id: string; name: string; kind: "AI" | "Deterministic" | "Human" | "External" | "Infra"; purpose: string; inputs: string; outputs: string; failure: string; code: string };

const C: Record<string, Comp> = {
  user: { id: "user", name: "User", kind: "Human", purpose: "States what they want in plain language and sets spending policy. Approves anything above an agent's autonomous limit.", inputs: "Natural-language requests and policies", outputs: "Intent, policy, approvals", failure: "—", code: "frontend /command-center, /policies, /approvals" },
  intent: { id: "intent", name: "Intent Layer", kind: "AI", purpose: "Turns a request into structured intent (category, budget, location, constraints). Uses the configured LLM with schema validation, or a deterministic parser.", inputs: "User request", outputs: "Validated Intent object", failure: "If a configured LLM fails or returns invalid output, the transaction fails closed.", code: "backend/app/services/intent.py" },
  agents: { id: "agents", name: "Agent Layer", kind: "AI", purpose: "Travel, Shopping and Business agents search and propose a concrete purchase. Agents hold no payment authority. Their output is only a proposal.", inputs: "Intent", outputs: "TransactionProposal + the external content it read", failure: "No offer found → no transaction", code: "backend/app/services/orchestrator.py · run_agent" },
  shield: { id: "shield", name: "AgentShield", kind: "Deterministic", purpose: "Scans everything the agent read for text acting as instructions: overrides, limit tampering, payment redirection, exfiltration, hidden content, budget escalation. Produces a sanitized, data-only copy.", inputs: "Untrusted external content, user's budget", outputs: "CLEAN / SUSPICIOUS / BLOCK with threats and excerpts", failure: "Any exception → fail closed", code: "backend/app/engines/shield.py" },
  risk: { id: "risk", name: "Risk Engine", kind: "Deterministic", purpose: "Scores merchant, transaction, behavior, policy-proximity and prompt-injection risk 0–100 with reasons. The overall score is a weighted average, floored by the worst factor.", inputs: "Proposal, merchant profile, spending history, policy, shield result", outputs: "RiskAssessment with explained factors", failure: "Unavailable → BLOCK, no payment (fail closed)", code: "backend/app/engines/risk.py" },
  policy: { id: "policy", name: "Policy Engine", kind: "Deterministic", purpose: "Pure function: amount, daily/monthly limits, allowed/blocked categories, merchant trust, new and international merchants, user's stated budget, approval threshold.", inputs: "PolicySpec, proposal, merchant, spending", outputs: "ALLOW / DENY / HUMAN_APPROVAL_REQUIRED with every rule check", failure: "Exception → fail closed", code: "backend/app/engines/policy.py" },
  approval: { id: "approval", name: "Approval Engine", kind: "Deterministic", purpose: "Combines shield, risk and policy with fixed precedence: fail-closed → shield block → critical risk → policy deny → approval → allow. On human approval, hard policy limits are re-checked before payment.", inputs: "Shield, Risk, Policy results", outputs: "Final decision and status", failure: "Missing input → BLOCK", code: "backend/app/engines/decision.py" },
  audit: { id: "audit", name: "Audit Layer", kind: "Infra", purpose: "Every stage emits an event with a trace ID, actor, outcome, metadata and timing. Structured JSON logs carry the same correlation ID.", inputs: "Pipeline events", outputs: "Audit log, live trace, threat events", failure: "—", code: "backend/app/services/orchestrator.py · Recorder" },
  paypal: { id: "paypal", name: "PayPal", kind: "External", purpose: "Executes only APPROVED transactions: Orders v2 create (idempotent) → buyer approval → capture. Amount comes from the stored transaction, never the client. Without credentials, a clearly labelled simulator is used.", inputs: "Authorized transaction", outputs: "Order ID, capture ID, status", failure: "Unreachable → 'No money was moved', retryable", code: "backend/app/services/paypal.py" },
  merchant: { id: "merchant", name: "Merchant", kind: "External", purpose: "Receives payment. Merchant pages are untrusted content; trust, verification, age, refund and chargeback rates feed the risk engine.", inputs: "Payment", outputs: "Goods / services", failure: "—", code: "backend/app/db/models.py · Merchant" },
};

const KIND_TONE = { AI: "accent", Deterministic: "good", Human: "warn", External: "info", Infra: "neutral" } as const;

function Box({ id, active, onSelect, className }: { id: string; active: string; onSelect: (id: string) => void; className?: string }) {
  const c = C[id];
  return (
    <button
      onClick={() => onSelect(id)}
      aria-pressed={active === id}
      className={cn(
        "w-full rounded-lg border px-4 py-3 text-left transition cursor-pointer",
        active === id ? "border-accent bg-accent-soft ring-2 ring-ring/30" : "border-border bg-surface hover:border-border-strong",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[14px] font-semibold">{c.name}</span>
        <Badge tone={KIND_TONE[c.kind]}>{c.kind}</Badge>
      </div>
    </button>
  );
}

const Down = () => (
  <div className="flex justify-center py-1.5 text-fg-3" aria-hidden>
    <ArrowDown className="size-4" />
  </div>
);

export default function ArchitecturePage() {
  const [active, setActive] = useState("policy");
  const c = C[active];
  return (
    <div className="min-h-screen">
      <MarketingHeader />
      <main className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-fg-3">Architecture</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">AI proposes. Deterministic code authorizes.</h1>
        <p className="mt-3 max-w-2xl text-fg-2">Select any component to see what it does, what it consumes and how it fails. Note where the AI boundary ends.</p>

        <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_380px]">
          <div className="mx-auto w-full max-w-xl">
            <Box id="user" active={active} onSelect={setActive} />
            <Down />
            <Box id="intent" active={active} onSelect={setActive} />
            <Down />
            <Box id="agents" active={active} onSelect={setActive} />
            <Down />
            <div className="relative rounded-xl border-2 border-dashed border-good/40 p-3 pt-9">
              <div className="absolute top-2.5 left-3 flex items-center gap-2">
                <LogoMark className="size-5" />
                <span className="text-[12px] font-semibold uppercase tracking-[0.1em]">PayPilot governance</span>
                <span className="text-[11px] text-fg-3">· no LLM past this line</span>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                <Box id="shield" active={active} onSelect={setActive} />
                <Box id="risk" active={active} onSelect={setActive} />
                <Box id="policy" active={active} onSelect={setActive} />
                <Box id="approval" active={active} onSelect={setActive} />
                <Box id="audit" active={active} onSelect={setActive} className="sm:col-span-2" />
              </div>
            </div>
            <Down />
            <Box id="paypal" active={active} onSelect={setActive} />
            <Down />
            <Box id="merchant" active={active} onSelect={setActive} />
          </div>

          <aside className="lg:sticky lg:top-20 lg:self-start" aria-live="polite">
            <div className="rounded-xl border border-border bg-surface p-6 shadow-card">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">{c.name}</h2>
                <Badge tone={KIND_TONE[c.kind]}>{c.kind}</Badge>
              </div>
              <p className="mt-3 text-[14px] text-fg-2">{c.purpose}</p>
              <dl className="mt-5 space-y-3 text-[13px]">
                {(
                  [
                    ["Inputs", c.inputs],
                    ["Outputs", c.outputs],
                    ["On failure", c.failure],
                  ] as const
                ).map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-[11px] font-semibold uppercase tracking-wide text-fg-3">{k}</dt>
                    <dd className="mt-0.5">{v}</dd>
                  </div>
                ))}
                <div>
                  <dt className="text-[11px] font-semibold uppercase tracking-wide text-fg-3">Code</dt>
                  <dd className="mt-0.5 font-mono text-[12px] text-fg-2">{c.code}</dd>
                </div>
              </dl>
            </div>
            <Button asChild className="mt-4 w-full" variant="secondary">
              <Link href="/command-center">
                See it run <ArrowRight />
              </Link>
            </Button>
          </aside>
        </div>
      </main>
      <MarketingFooter />
    </div>
  );
}
