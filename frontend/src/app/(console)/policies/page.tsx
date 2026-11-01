"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowDown, Check, FlaskConical, Info, Loader2, Save, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/badges";
import { ErrorState, PageHeader } from "@/components/states";
import { PolicyChecks } from "@/components/trace/sections";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, Input, Label, Select, Skeleton, Switch, Tabs, TabsList, TabsTrigger, Textarea } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { money } from "@/lib/format";
import { useSystemStatus } from "@/lib/hooks";
import type { CompileResult, Policy, PolicyFields } from "@/lib/types";

const CATEGORIES = ["travel", "electronics", "saas", "software", "cloud", "office_supplies", "gift_cards", "crypto", "gambling"];

function fieldsOf(p: Policy | PolicyFields): PolicyFields {
  return {
    currency: p.currency,
    max_transaction_amount: p.max_transaction_amount,
    daily_spending_limit: p.daily_spending_limit,
    monthly_spending_limit: p.monthly_spending_limit,
    allowed_categories: p.allowed_categories,
    blocked_categories: p.blocked_categories,
    minimum_merchant_trust: p.minimum_merchant_trust,
    require_approval_above: p.require_approval_above,
    allow_new_merchants: p.allow_new_merchants,
    allow_international: p.allow_international,
    auto_refund_enabled: p.auto_refund_enabled,
  };
}

/* ---------------- Natural language compiler ---------------- */

function Compiler({ policy, onSaved }: { policy: Policy; onSaved: () => void }) {
  const { data: status } = useSystemStatus();
  const [text, setText] = useState("You can spend up to ₹20,000 per transaction. Anything above ₹10,000 needs my approval. Never use suspicious merchants.");
  const [result, setResult] = useState<CompileResult | null>(null);
  const compile = useMutation({ mutationFn: () => api.compilePolicy(text, policy.id), onSuccess: setResult });
  const save = useMutation({
    mutationFn: () => api.updatePolicy(policy.id, { ...fieldsOf(result!.policy!), source_text: text }),
    onSuccess: () => {
      setResult(null);
      onSaved();
    },
  });

  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <Sparkles className="size-4 text-accent" /> Natural language policy
          </span>
        }
        description={status?.llm.configured ? `Compiled by ${status.llm.label}, then validated deterministically.` : "Compiled by the deterministic rule parser (no LLM configured), then validated."}
      />
      <div className="space-y-4 px-5 pb-5">
        <div>
          <Label htmlFor="nl">Your instruction</Label>
          <Textarea id="nl" rows={3} className="mt-1.5" value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} />
        </div>
        <Button variant="accent" onClick={() => compile.mutate()} disabled={compile.isPending || text.trim().length < 3}>
          {compile.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />} Compile policy
        </Button>
        {compile.error && <p className="text-[13px] text-bad">{(compile.error as Error).message}</p>}

        {result && (
          <div className="rounded-xl border border-border bg-surface-2/50 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-fg-3">Your instruction</p>
            <p className="mt-1 text-[13px] italic text-fg-2">“{result.instruction}”</p>
            <div className="my-3 flex justify-center text-fg-3">
              <ArrowDown className="size-4" />
            </div>
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-fg-3">PayPilot policy · {policy.name}</p>
              <Badge tone={result.source === "llm" ? "accent" : "neutral"}>{result.source === "llm" ? "AI compiled" : "Rule parser"}</Badge>
            </div>
            {result.changes.length > 0 ? (
              <dl className="mt-2 divide-y divide-border rounded-lg border border-border bg-surface">
                {result.changes.map((c) => (
                  <div key={c.field} className="flex items-center justify-between gap-4 px-3 py-2.5">
                    <dt className="text-[13px] text-fg-2">{c.label}</dt>
                    <dd className="text-right text-[15px] font-semibold tabular">{c.display}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="mt-2 text-[13px] text-fg-3">No changes recognised.</p>
            )}
            {result.notes.map((n) => (
              <p key={n} className="mt-2 flex gap-1.5 text-[12px] text-fg-3">
                <Info className="mt-0.5 size-3.5 shrink-0" />
                {n}
              </p>
            ))}
            {result.errors.map((e) => (
              <p key={e} className="mt-2 flex gap-1.5 text-[12px] font-medium text-bad">
                <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
                {e}
              </p>
            ))}
            <div className="mt-4 flex gap-2">
              <Button onClick={() => save.mutate()} disabled={!result.valid || save.isPending}>
                {save.isPending ? <Loader2 className="animate-spin" /> : <Save />} Save policy
              </Button>
              <Button variant="ghost" onClick={() => setResult(null)}>
                Discard
              </Button>
            </div>
            {save.error && <p className="mt-2 text-[12px] text-bad">{(save.error as Error).message}</p>}
            <p className="mt-2 text-[11px] text-fg-3">Validated by the policy schema before saving. Nothing changes until you save.</p>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ---------------- Structured editor ---------------- */

function MoneyField({ id, label, value, onChange, currency }: { id: string; label: string; value: number; onChange: (v: number) => void; currency: string }) {
  return (
    <div>
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type="number" min={0} step={500} className="mt-1.5 tabular" value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <p className="mt-1 text-[11px] text-fg-3 tabular">{money(value, currency)}</p>
    </div>
  );
}

function CategoryPicker({ label, value, onChange, tone }: { label: string; value: string[]; onChange: (v: string[]) => void; tone: "good" | "bad" }) {
  return (
    <div>
      <Label>{label}</Label>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {CATEGORIES.map((c) => {
          const on = value.includes(c);
          return (
            <button
              key={c}
              type="button"
              aria-pressed={on}
              onClick={() => onChange(on ? value.filter((x) => x !== c) : [...value, c])}
              className={
                "rounded-md border px-2 py-1 text-[12px] font-medium transition cursor-pointer " +
                (on ? (tone === "good" ? "border-good/40 bg-good-soft text-good" : "border-bad/40 bg-bad-soft text-bad") : "border-border text-fg-3 hover:text-fg")
              }
            >
              {c.replace(/_/g, " ")}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Editor({ policy, onSaved }: { policy: Policy; onSaved: () => void }) {
  const [f, setF] = useState<PolicyFields>(() => fieldsOf(policy));
  const set = <K extends keyof PolicyFields>(k: K, v: PolicyFields[K]) => setF((p) => ({ ...p, [k]: v }));
  const save = useMutation({ mutationFn: () => api.updatePolicy(policy.id, { ...f, source_text: policy.source_text }), onSuccess: onSaved });
  const dirty = JSON.stringify(f) !== JSON.stringify(fieldsOf(policy));
  const err = save.error as ApiError | null;

  return (
    <Card>
      <CardHeader title="Structured policy" description={`Version ${policy.version} · ${policy.currency}`} />
      <form
        className="space-y-5 px-5 pb-5"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <MoneyField id="max" label="Maximum transaction" value={f.max_transaction_amount} onChange={(v) => set("max_transaction_amount", v)} currency={f.currency} />
          <MoneyField id="appr" label="Approval required above" value={f.require_approval_above} onChange={(v) => set("require_approval_above", v)} currency={f.currency} />
          <MoneyField id="daily" label="Daily limit" value={f.daily_spending_limit} onChange={(v) => set("daily_spending_limit", v)} currency={f.currency} />
          <MoneyField id="monthly" label="Monthly limit" value={f.monthly_spending_limit} onChange={(v) => set("monthly_spending_limit", v)} currency={f.currency} />
        </div>
        <div>
          <div className="flex items-center justify-between">
            <Label htmlFor="trust">Minimum merchant trust</Label>
            <span className="font-mono text-[13px] font-semibold tabular">{f.minimum_merchant_trust}%</span>
          </div>
          <input id="trust" type="range" min={0} max={100} value={f.minimum_merchant_trust} onChange={(e) => set("minimum_merchant_trust", Number(e.target.value))} className="mt-2 w-full accent-[var(--accent)]" />
        </div>
        <CategoryPicker label="Allowed categories (empty = any non-blocked)" value={f.allowed_categories} onChange={(v) => set("allowed_categories", v)} tone="good" />
        <CategoryPicker label="Blocked categories (always denied)" value={f.blocked_categories} onChange={(v) => set("blocked_categories", v)} tone="bad" />
        <div className="grid gap-3 sm:grid-cols-3">
          {(
            [
              ["allow_new_merchants", "New merchants"],
              ["allow_international", "International"],
              ["auto_refund_enabled", "Auto refunds"],
            ] as const
          ).map(([k, l]) => (
            <label key={k} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5 text-[13px]">
              {l}
              <Switch checked={f[k]} onCheckedChange={(v) => set(k, v)} label={l} />
            </label>
          ))}
        </div>
        {err && (
          <div role="alert" className="rounded-lg border border-bad/30 bg-bad-soft p-3 text-[12px] text-bad">
            <p className="font-medium">{err.message}</p>
            {err.fields?.map((x, i) => (
              <p key={i}>{x.message.replace("Value error, ", "")}</p>
            ))}
          </div>
        )}
        <div className="flex items-center gap-2">
          <Button type="submit" disabled={!dirty || save.isPending}>
            {save.isPending ? <Loader2 className="animate-spin" /> : <Save />} Save changes
          </Button>
          {dirty && (
            <Button type="button" variant="ghost" onClick={() => setF(fieldsOf(policy))}>
              Reset
            </Button>
          )}
          {save.isSuccess && !dirty && <span className="flex items-center gap-1 text-[12px] text-good"><Check className="size-3.5" /> Saved</span>}
        </div>
      </form>
    </Card>
  );
}

/* ---------------- Simulator ---------------- */

function Simulator({ policy }: { policy: Policy }) {
  const [s, setS] = useState({ amount: 15000, category: policy.allowed_categories[0] ?? "travel", merchant_trust: 91, merchant_status: "VERIFIED", merchant_country: "IN", daily_spent: 0 });
  const evaluate = useMutation({ mutationFn: () => api.evaluatePolicy({ policy_id: policy.id, currency: policy.currency, ...s }) });
  const r = evaluate.data;
  const verdict = r && { ALLOW: ["Allow", "text-good", Check], DENY: ["Deny", "text-bad", X], HUMAN_APPROVAL_REQUIRED: ["Human approval required", "text-warn", AlertTriangle] }[r.decision];

  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <FlaskConical className="size-4 text-fg-3" /> Policy simulator
          </span>
        }
        description="Test a hypothetical transaction against this policy. Nothing is created."
      />
      <form
        className="grid gap-3 px-5 sm:grid-cols-3"
        onSubmit={(e) => {
          e.preventDefault();
          evaluate.mutate();
        }}
      >
        <div>
          <Label htmlFor="s-amt">Amount ({policy.currency})</Label>
          <Input id="s-amt" type="number" min={1} className="mt-1.5" value={s.amount} onChange={(e) => setS({ ...s, amount: Number(e.target.value) })} />
        </div>
        <div>
          <Label htmlFor="s-cat">Category</Label>
          <Select id="s-cat" className="mt-1.5" value={s.category} onChange={(e) => setS({ ...s, category: e.target.value })}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c.replace(/_/g, " ")}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="s-trust">Merchant trust</Label>
          <Input id="s-trust" type="number" min={0} max={100} className="mt-1.5" value={s.merchant_trust} onChange={(e) => setS({ ...s, merchant_trust: Number(e.target.value) })} />
        </div>
        <div>
          <Label htmlFor="s-status">Merchant status</Label>
          <Select id="s-status" className="mt-1.5" value={s.merchant_status} onChange={(e) => setS({ ...s, merchant_status: e.target.value })}>
            <option value="VERIFIED">Verified</option>
            <option value="PENDING">Pending</option>
            <option value="UNVERIFIED">Unverified</option>
            <option value="FLAGGED">Flagged</option>
          </Select>
        </div>
        <div>
          <Label htmlFor="s-country">Merchant country</Label>
          <Select id="s-country" className="mt-1.5" value={s.merchant_country} onChange={(e) => setS({ ...s, merchant_country: e.target.value })}>
            <option value="IN">India (domestic)</option>
            <option value="US">United States</option>
            <option value="SG">Singapore</option>
            <option value="GB">United Kingdom</option>
          </Select>
        </div>
        <div>
          <Label htmlFor="s-daily">Already spent today</Label>
          <Input id="s-daily" type="number" min={0} className="mt-1.5" value={s.daily_spent} onChange={(e) => setS({ ...s, daily_spent: Number(e.target.value) })} />
        </div>
        <div className="sm:col-span-3">
          <Button type="submit" variant="secondary" disabled={evaluate.isPending}>
            {evaluate.isPending ? <Loader2 className="animate-spin" /> : <FlaskConical />} Evaluate
          </Button>
        </div>
      </form>
      <div className="px-5 pt-4 pb-5">
        {evaluate.error && <p className="text-[13px] text-bad">{(evaluate.error as Error).message}</p>}
        {r && verdict && (
          <div className="space-y-3">
            <PolicyChecks result={r} />
            <div className="flex items-center justify-between rounded-lg border border-border bg-surface-2 px-4 py-3">
              <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-fg-3">Final</span>
              <span className={`flex items-center gap-1.5 text-[15px] font-semibold uppercase ${verdict[1]}`}>
                {(() => {
                  const I = verdict[2] as typeof Check;
                  return <I className="size-4" />;
                })()}
                {verdict[0] as string}
              </span>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

export default function PoliciesPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["policies"], queryFn: api.policies });
  const agents = useQuery({ queryKey: ["agents"], queryFn: api.agents });
  const [active, setActive] = useState("pol_travel");
  const policy = q.data?.find((p) => p.id === active);
  const onSaved = () => {
    qc.invalidateQueries({ queryKey: ["policies"] });
    qc.invalidateQueries({ queryKey: ["agents"] });
  };

  return (
    <div>
      <PageHeader
        eyebrow="Policies"
        title="Spending policies"
        description="Write rules in plain language or edit them directly. Every policy is validated, versioned and enforced deterministically."
        actions={
          q.data && (
            <Tabs value={active} onValueChange={setActive}>
              <TabsList>
                {q.data.map((p) => (
                  <TabsTrigger key={p.id} value={p.id}>
                    {agents.data?.find((a) => a.id === p.agent_id)?.name ?? p.name}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          )
        }
      />
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.isPending && <Skeleton className="h-96 rounded-xl" />}
      {policy && (
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="space-y-4">
            <Compiler key={policy.id} policy={policy} onSaved={onSaved} />
            <Simulator key={`sim-${policy.id}-${policy.version}`} policy={policy} />
          </div>
          <Editor key={`${policy.id}-${policy.version}`} policy={policy} onSaved={onSaved} />
        </div>
      )}
    </div>
  );
}
