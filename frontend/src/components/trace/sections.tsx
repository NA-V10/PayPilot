"use client";

import { AlertTriangle, Ban, Check, CheckCircle2, Clock, Minus, ShieldAlert, ShieldCheck, X, XCircle } from "lucide-react";
import { Badge, riskTone } from "@/components/badges";
import { money } from "@/lib/format";
import type { PolicyResult, RiskAssessment, ShieldResult, TransactionDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

/* ---------------- Decision summary ---------------- */

const DECISION_VIEW = {
  COMPLETED: { tone: "good", title: "Payment completed", icon: CheckCircle2 },
  PAYMENT_CREATED: { tone: "info", title: "Authorized · awaiting payment", icon: Clock },
  APPROVED: { tone: "info", title: "Authorized", icon: CheckCircle2 },
  AWAITING_APPROVAL: { tone: "warn", title: "Human approval required", icon: Clock },
  BLOCKED: { tone: "bad", title: "Transaction blocked", icon: Ban },
  DENIED: { tone: "bad", title: "Transaction denied", icon: XCircle },
  FAILED: { tone: "bad", title: "Payment failed", icon: AlertTriangle },
} as const;

export function DecisionSummary({ tx }: { tx: TransactionDetail }) {
  const v = DECISION_VIEW[tx.status as keyof typeof DECISION_VIEW] ?? { tone: "info", title: tx.status, icon: Clock };
  const tone = {
    good: "border-good/30 bg-good-soft text-good",
    info: "border-info/30 bg-info-soft text-info",
    warn: "border-warn/40 bg-warn-soft text-warn",
    bad: "border-bad/30 bg-bad-soft text-bad",
  }[v.tone];
  const noMoney = ["BLOCKED", "DENIED", "FAILED", "AWAITING_APPROVAL"].includes(tx.status);
  return (
    <div className={cn("rounded-xl border p-4", tone)}>
      <div className="flex items-center gap-2.5">
        <v.icon className="size-5" />
        <p className="text-[15px] font-semibold tracking-tight">{v.title}</p>
        {noMoney && <span className="ml-auto text-[12px] font-medium opacity-80">No money moved</span>}
      </div>
      {tx.decision_reasons.length > 0 && (
        <ul className="mt-2.5 space-y-1 pl-7 text-[13px] leading-snug text-fg">
          {tx.decision_reasons.map((r, i) => (
            <li key={i} className="list-disc marker:text-fg-3">
              {r}
            </li>
          ))}
        </ul>
      )}
      {tx.failure_reason && tx.status !== "BLOCKED" && <p className="mt-2 pl-7 text-[13px] text-fg">{tx.failure_reason}</p>}
    </div>
  );
}

/* ---------------- Policy checks ---------------- */

const CHECK_ICON = {
  pass: <Check className="size-3.5 text-good" strokeWidth={3} />,
  fail: <X className="size-3.5 text-bad" strokeWidth={3} />,
  warn: <AlertTriangle className="size-3.5 text-warn" />,
  skip: <Minus className="size-3.5 text-fg-3" />,
};

export function PolicyChecks({ result }: { result: PolicyResult }) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-[13px] font-semibold">Policy Engine</h4>
        <Badge tone={result.decision === "ALLOW" ? "good" : result.decision === "DENY" ? "bad" : "warn"}>
          {result.decision === "HUMAN_APPROVAL_REQUIRED" ? "Approval required" : result.decision === "ALLOW" ? "Pass" : "Fail"}
        </Badge>
      </div>
      <ul className="divide-y divide-border rounded-lg border border-border bg-surface">
        {result.checks.map((c) => (
          <li key={c.rule} className="flex items-start gap-3 px-3 py-2">
            <span className="mt-0.5">{CHECK_ICON[c.status]}</span>
            <div className="min-w-0 flex-1">
              <p className={cn("text-[13px] font-medium", c.status === "fail" && "text-bad", c.status === "skip" && "text-fg-3")}>{c.label}</p>
              <p className="text-[12px] text-fg-3">{c.detail}</p>
            </div>
            {(c.actual || c.limit) && (
              <div className="shrink-0 text-right font-mono text-[11px] leading-tight text-fg-2 tabular">
                {c.actual && <div>{c.actual}</div>}
                {c.limit && <div className="text-fg-3">limit {c.limit}</div>}
              </div>
            )}
          </li>
        ))}
      </ul>
      <p className="mt-1.5 text-[11px] text-fg-3">Deterministic rules · same input, same decision · no LLM involved</p>
    </div>
  );
}

/* ---------------- Risk breakdown ---------------- */

function barColor(score: number) {
  return score >= 80 ? "bg-bad" : score >= 60 ? "bg-bad/70" : score >= 30 ? "bg-warn" : "bg-good";
}

export function RiskBreakdown({ risk }: { risk: RiskAssessment }) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-[13px] font-semibold">Risk Engine</h4>
        <Badge tone={riskTone(risk.level)}>
          {risk.level} <span className="font-mono opacity-70">{risk.overall_score}/100</span>
        </Badge>
      </div>
      <div className="space-y-2.5 rounded-lg border border-border bg-surface p-3">
        {risk.factors.map((f) => (
          <div key={f.key}>
            <div className="flex items-baseline justify-between text-[12px]">
              <span className="font-medium">
                {f.name} <span className="font-normal text-fg-3">· weight {Math.round(f.weight * 100)}%</span>
              </span>
              <span className="font-mono text-fg-2 tabular">{f.score}</span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-2">
              <div className={cn("h-full rounded-full transition-all duration-700", barColor(f.score))} style={{ width: `${Math.max(2, f.score)}%` }} />
            </div>
            <p className="mt-1 text-[11px] text-fg-3">{f.reasons.join(" · ")}</p>
          </div>
        ))}
      </div>
      <p className="mt-1.5 text-[11px] text-fg-3">Overall: {risk.method}</p>
    </div>
  );
}

/* ---------------- AgentShield ---------------- */

export function ShieldReport({ shield }: { shield: ShieldResult }) {
  const clean = shield.verdict === "CLEAN";
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-[13px] font-semibold">AgentShield</h4>
        <Badge tone={clean ? "good" : shield.verdict === "BLOCK" ? "bad" : "warn"} icon={clean ? <ShieldCheck /> : <ShieldAlert />}>
          {clean ? "Clean" : shield.verdict === "BLOCK" ? "Threat detected" : "Suspicious"}
        </Badge>
      </div>
      {clean ? (
        <div className="rounded-lg border border-border bg-surface px-3 py-2.5 text-[13px] text-fg-2">{shield.summary}</div>
      ) : (
        <div className="space-y-2">
          {shield.threats.map((t, i) => (
            <div key={i} className="rounded-lg border border-bad/25 bg-bad-soft/50 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[12px] font-semibold uppercase tracking-wide text-bad">{t.title}</span>
                <Badge tone={t.severity === "CRITICAL" || t.severity === "HIGH" ? "bad" : "warn"}>{t.severity}</Badge>
                <span className="ml-auto font-mono text-[10px] text-fg-3">{t.pattern_id}</span>
              </div>
              <p className="mt-1 text-[12px] text-fg-2">{t.explanation}</p>
              <blockquote className="mt-2 border-l-2 border-bad/50 pl-2.5 font-mono text-[11px] leading-relaxed text-fg">“{t.excerpt}”</blockquote>
              <p className="mt-1 truncate text-[11px] text-fg-3">Source: {t.source}</p>
            </div>
          ))}
          <div className="rounded-lg border border-border bg-surface p-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-fg-3">Sanitized content passed downstream (data only)</p>
            {shield.sanitized.map((s, i) => (
              <p key={i} className="mt-1 font-mono text-[11px] leading-relaxed text-fg-2">
                {s.content}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------------- Facts header ---------------- */

export function TxFacts({ tx }: { tx: TransactionDetail }) {
  const facts: [string, React.ReactNode][] = [
    ["Agent", tx.agent.name],
    ["Merchant", tx.merchant ? `${tx.merchant.name} · trust ${tx.merchant.trust_score}` : "—"],
    ["Category", tx.category.replace(/_/g, " ")],
    ["Trace ID", <span key="t" className="font-mono">{tx.trace_id}</span>],
  ];
  return (
    <div>
      {tx.user_request && (
        <p className="mb-3 rounded-lg border border-border bg-surface-2 px-3 py-2 text-[13px] text-fg-2">
          <span className="text-fg-3">User asked: </span>“{tx.user_request}”
        </p>
      )}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[13px] text-fg-2">{tx.description}</p>
          <p className="text-3xl font-semibold tracking-tight tabular">{money(tx.amount, tx.currency)}</p>
        </div>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4">
        {facts.map(([k, v]) => (
          <div key={k} className="min-w-0">
            <dt className="text-[11px] uppercase tracking-wide text-fg-3">{k}</dt>
            <dd className="truncate text-[13px] font-medium capitalize-first">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
