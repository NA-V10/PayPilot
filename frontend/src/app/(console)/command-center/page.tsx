"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Ban, Bot, CheckCircle2, Hand, Loader2, Play, ServerCrash, ShieldAlert, Sparkles, Zap } from "lucide-react";
import { useRef, useState } from "react";
import { Badge } from "@/components/badges";
import { ErrorState, PageHeader } from "@/components/states";
import { LiveRun } from "@/components/trace/live-run";
import { Button } from "@/components/ui/button";
import { Card, Select, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import { useInvalidateAll } from "@/lib/hooks";
import type { Scenario, TransactionDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

const PRIMARY: { id: Scenario["id"]; label: string; cta: string; icon: typeof Zap; tone: string; expect: string }[] = [
  { id: "safe_purchase", label: "Safe purchase", cta: "Run", icon: CheckCircle2, tone: "text-good", expect: "Approved → PayPal" },
  { id: "prompt_injection", label: "Malicious merchant", cta: "Attack", icon: ShieldAlert, tone: "text-bad", expect: "AgentShield blocks" },
  { id: "human_approval", label: "High-value purchase", cta: "Request approval", icon: Hand, tone: "text-warn", expect: "Human approval" },
];
const SECONDARY: { id: Scenario["id"]; label: string; icon: typeof Zap; expect: string }[] = [
  { id: "policy_violation", label: "Policy violation", icon: Ban, expect: "Denied by policy" },
  { id: "fail_closed", label: "Risk engine outage", icon: ServerCrash, expect: "Fails closed" },
];

const AGENT_EXAMPLES: Record<string, string> = {
  agt_travel: "Book me a hotel in Bangalore under ₹10,000. Don't use suspicious merchants.",
  agt_shopping: "Find me a laptop for development under ₹80,000.",
  agt_business: "Pay this SaaS vendor ₹25,000.",
};

export default function CommandCenterPage() {
  const scenarios = useQuery({ queryKey: ["scenarios"], queryFn: api.scenarios, staleTime: Infinity });
  const invalidate = useInvalidateAll();
  const [tx, setTx] = useState<TransactionDetail | null>(null);
  const [runKey, setRunKey] = useState<string>();
  const [agentId, setAgentId] = useState("agt_travel");
  const [text, setText] = useState(AGENT_EXAMPLES.agt_travel);
  const resultRef = useRef<HTMLDivElement>(null);

  const onResult = (t: TransactionDetail) => {
    setTx(t);
    setRunKey(`${t.id}-${Date.now()}`);
    invalidate();
    requestAnimationFrame(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
  };
  const runScenario = useMutation({ mutationFn: api.runScenario, onSuccess: onResult });
  const runAgent = useMutation({ mutationFn: () => api.runAgent(agentId, text), onSuccess: onResult });
  const byId = Object.fromEntries((scenarios.data ?? []).map((s) => [s.id, s]));
  const busy = runScenario.isPending || runAgent.isPending;
  const error = runScenario.error ?? runAgent.error;

  return (
    <div>
      <PageHeader
        eyebrow="PayPilot Command Center"
        title="Watch autonomous commerce happen safely."
        description="Each scenario sends a real request through the governance pipeline: AgentShield, Risk, Policy and Approval, then PayPal. Outcomes are deterministic."
        actions={<Badge tone="accent">Demo scenarios</Badge>}
      />

      <div className="grid gap-3 md:grid-cols-3">
        {PRIMARY.map((p) => {
          const s = byId[p.id];
          const running = runScenario.isPending && runScenario.variables === p.id;
          return (
            <Card key={p.id} className="flex flex-col p-5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-fg-3">{p.label}</span>
                <p.icon className={cn("size-4", p.tone)} />
              </div>
              <p className="mt-3 text-3xl font-semibold tracking-tight tabular">{s ? money(s.amount, s.currency) : "—"}</p>
              <p className="mt-1 line-clamp-2 min-h-10 text-[13px] text-fg-2">{s?.request ?? " "}</p>
              <div className="mt-4 flex items-center justify-between gap-2">
                <span className="text-[12px] text-fg-3">Expect: {p.expect}</span>
                <Button size="sm" variant={p.id === "prompt_injection" ? "danger" : "primary"} disabled={busy} onClick={() => runScenario.mutate(p.id)}>
                  {running ? <Loader2 className="animate-spin" /> : <Play />}
                  {p.cta}
                </Button>
              </div>
              {s?.mode === "scripted" && <p className="mt-3 border-t border-border pt-2.5 text-[11px] text-fg-3">{s.note}</p>}
            </Card>
          );
        })}
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_1fr_2fr]">
        {SECONDARY.map((p) => {
          const s = byId[p.id];
          return (
            <Card key={p.id} className="flex items-center gap-3 p-4">
              <p.icon className="size-4 shrink-0 text-fg-3" />
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-medium">{p.label}</p>
                <p className="truncate text-[12px] text-fg-3">
                  {s ? money(s.amount, s.currency) : ""} · {p.expect}
                </p>
              </div>
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => runScenario.mutate(p.id)}>
                {runScenario.isPending && runScenario.variables === p.id ? <Loader2 className="animate-spin" /> : <Play />} Run
              </Button>
            </Card>
          );
        })}
        <Card className="p-4">
          <form
            className="flex flex-col gap-2.5"
            onSubmit={(e) => {
              e.preventDefault();
              if (text.trim().length >= 3) runAgent.mutate();
            }}
          >
            <div className="flex items-center gap-2">
              <Bot className="size-4 text-fg-3" />
              <span className="text-[13px] font-medium">Give an agent a task</span>
              <Select
                aria-label="Agent"
                className="ml-auto h-8 w-40 text-[13px]"
                value={agentId}
                onChange={(e) => {
                  setAgentId(e.target.value);
                  setText(AGENT_EXAMPLES[e.target.value]);
                }}
              >
                <option value="agt_travel">Travel Agent</option>
                <option value="agt_shopping">Shopping Agent</option>
                <option value="agt_business">Business Agent</option>
              </Select>
            </div>
            <div className="flex gap-2">
              <Textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} maxLength={500} aria-label="Request" className="min-h-9 py-2" />
              <Button type="submit" variant="accent" disabled={busy || text.trim().length < 3}>
                {runAgent.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />} Run
              </Button>
            </div>
          </form>
        </Card>
      </div>

      <div ref={resultRef} className="scroll-mt-20 pt-8">
        {error && <ErrorState error={error} title="Request could not be evaluated" className="mb-4" />}
        {tx && runKey ? (
          <LiveRun tx={tx} runKey={runKey} onUpdate={(t) => { setTx(t); invalidate(); }} />
        ) : (
          !error && (
            <Card className="dot-grid flex flex-col items-center justify-center px-6 py-16 text-center">
              <Zap className="size-5 text-fg-3" />
              <p className="mt-3 font-medium">Run a scenario to see the governance pipeline</p>
              <p className="mt-1 max-w-md text-sm text-fg-2">Intent → Agent → AgentShield → Risk → Policy → Approval → PayPal. Every stage is recorded with a trace ID.</p>
            </Card>
          )
        )}
      </div>
    </div>
  );
}
