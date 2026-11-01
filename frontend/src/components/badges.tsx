import { AlertTriangle, Ban, CheckCircle2, CircleDashed, Clock, CreditCard, ShieldAlert, ShieldCheck, XCircle } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { RiskLevel, TxStatus } from "@/lib/types";

type Tone = "good" | "warn" | "bad" | "info" | "neutral" | "accent";

const TONES: Record<Tone, string> = {
  good: "bg-good-soft text-good",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  info: "bg-info-soft text-info",
  accent: "bg-accent-soft text-accent",
  neutral: "bg-surface-2 text-fg-2",
};

export function Badge({ tone = "neutral", icon, children, className }: { tone?: Tone; icon?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide [&_svg]:size-3",
        TONES[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  );
}

const STATUS: Record<TxStatus, { tone: Tone; label: string; icon: ReactNode }> = {
  PROPOSED: { tone: "neutral", label: "Proposed", icon: <CircleDashed /> },
  POLICY_REVIEW: { tone: "info", label: "Policy review", icon: <CircleDashed /> },
  RISK_REVIEW: { tone: "info", label: "Risk review", icon: <CircleDashed /> },
  AWAITING_APPROVAL: { tone: "warn", label: "Awaiting approval", icon: <Clock /> },
  APPROVED: { tone: "info", label: "Approved", icon: <CheckCircle2 /> },
  DENIED: { tone: "bad", label: "Denied", icon: <XCircle /> },
  BLOCKED: { tone: "bad", label: "Blocked", icon: <Ban /> },
  PAYMENT_CREATED: { tone: "accent", label: "Payment pending", icon: <CreditCard /> },
  COMPLETED: { tone: "good", label: "Completed", icon: <CheckCircle2 /> },
  FAILED: { tone: "bad", label: "Failed", icon: <AlertTriangle /> },
};

export function StatusBadge({ status }: { status: TxStatus }) {
  const s = STATUS[status] ?? STATUS.PROPOSED;
  return (
    <Badge tone={s.tone} icon={s.icon}>
      {s.label}
    </Badge>
  );
}

export function riskTone(level: RiskLevel | null | undefined): Tone {
  return level === "LOW" ? "good" : level === "MEDIUM" ? "warn" : level ? "bad" : "neutral";
}

export function RiskBadge({ level, score }: { level: RiskLevel | null; score?: number | null }) {
  if (!level) return <Badge>—</Badge>;
  return (
    <Badge tone={riskTone(level)} icon={level === "LOW" ? <ShieldCheck /> : <ShieldAlert />}>
      {level}
      {score != null && <span className="font-mono font-medium opacity-70">{score}</span>}
    </Badge>
  );
}

export function PolicyBadge({ decision }: { decision: string | null }) {
  if (!decision) return <Badge>—</Badge>;
  if (decision === "ALLOW") return <Badge tone="good" icon={<CheckCircle2 />}>Pass</Badge>;
  if (decision === "DENY") return <Badge tone="bad" icon={<XCircle />}>Fail</Badge>;
  return <Badge tone="warn" icon={<Clock />}>Approval</Badge>;
}

export function ProviderBadge({ provider }: { provider: string | null }) {
  if (provider === "paypal") return <Badge tone="info">PayPal</Badge>;
  if (provider === "simulated") return <Badge tone="neutral">Simulated</Badge>;
  if (provider === "seed") return <Badge tone="neutral">Seed data</Badge>;
  return null;
}
