"use client";

import {
  Activity,
  BookCheck,
  Bot,
  Gauge,
  Inbox,
  LayoutDashboard,
  Menu,
  Moon,
  Radar,
  ScrollText,
  Settings,
  Store,
  Sun,
  TerminalSquare,
  Workflow,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useState, type ReactNode } from "react";
import { Logo } from "@/components/logo";
import { Tip } from "@/components/ui/primitives";
import { usePendingApprovals, useSystemStatus } from "@/lib/hooks";
import { cn } from "@/lib/utils";

const NAV: { href: string; label: string; icon: typeof Gauge; group?: string }[] = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/command-center", label: "Command Center", icon: TerminalSquare },
  { href: "/agents", label: "Agents", icon: Bot, group: "Govern" },
  { href: "/policies", label: "Policies", icon: BookCheck, group: "Govern" },
  { href: "/approvals", label: "Approvals", icon: Inbox, group: "Govern" },
  { href: "/transactions", label: "Transactions", icon: Activity, group: "Observe" },
  { href: "/trace", label: "Agent Trace", icon: Workflow, group: "Observe" },
  { href: "/risk", label: "Risk Center", icon: Radar, group: "Observe" },
  { href: "/merchants", label: "Merchants", icon: Store, group: "Observe" },
  { href: "/audit", label: "Audit Log", icon: ScrollText, group: "Observe" },
  { href: "/settings", label: "Settings", icon: Settings, group: "System" },
];

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { data: pending } = usePendingApprovals();
  return (
    <nav className="flex flex-col gap-0.5 px-3" aria-label="Main">
      {NAV.map((item, i) => {
        const active = pathname === item.href || pathname.startsWith(item.href + "/");
        const header = i === 0 || NAV[i - 1].group !== item.group ? item.group : undefined;
        return (
          <div key={item.href}>
            {header && <div className="mt-5 mb-1.5 px-2 text-[11px] font-medium uppercase tracking-[0.1em] text-fg-3">{header}</div>}
            <Link
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "group flex h-8 items-center gap-2.5 rounded-md px-2 text-[13px] font-medium transition-colors",
                active ? "bg-surface-2 text-fg" : "text-fg-2 hover:bg-surface-2/60 hover:text-fg",
              )}
              aria-current={active ? "page" : undefined}
            >
              <item.icon className={cn("size-4", active ? "text-accent" : "text-fg-3 group-hover:text-fg-2")} />
              {item.label}
              {item.href === "/approvals" && pending && pending.length > 0 && (
                <span className="ml-auto rounded-full bg-warn-soft px-1.5 text-[11px] font-semibold text-warn tabular">{pending.length}</span>
              )}
            </Link>
          </div>
        );
      })}
    </nav>
  );
}

function StatusPills() {
  const { data, isError } = useSystemStatus();
  if (isError) {
    return <span className="inline-flex items-center gap-1.5 rounded-md border border-bad/30 bg-bad-soft px-2 py-1 text-[11px] font-semibold text-bad">● API OFFLINE</span>;
  }
  if (!data) return <span className="h-6 w-40 animate-pulse rounded-md bg-surface-2" />;
  const pp = data.payments;
  const ppTone = pp.mode === "paypal" ? (pp.connected ? "text-good" : "text-bad") : "text-warn";
  return (
    <div className="flex items-center gap-2">
      <Tip
        content={
          pp.mode === "paypal"
            ? `Real PayPal ${pp.environment} Orders API. Settles in ${pp.settlement_currency}.`
            : "No PayPal credentials configured. Payments are simulated and clearly labelled — no real PayPal transaction occurs."
        }
      >
        <span className="inline-flex cursor-default items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-1 text-[11px] font-semibold uppercase tracking-wide">
          <span className="text-fg-3">{pp.mode === "paypal" ? `PayPal ${pp.environment}` : "Payments"}</span>
          <span className={ppTone}>● {pp.mode === "paypal" ? (pp.connected ? "Connected" : "Unreachable") : "Simulated"}</span>
        </span>
      </Tip>
      <Tip content={data.llm.configured ? `Intent & policy compiling via ${data.llm.label}. Authorization never uses the LLM.` : "No LLM configured: intent and policy compiling use a deterministic rule parser. Authorization is always deterministic."}>
        <span className="hidden cursor-default items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-1 text-[11px] font-semibold uppercase tracking-wide sm:inline-flex">
          <span className="text-fg-3">AI</span>
          <span className={data.llm.configured ? "text-good" : "text-fg-2"}>{data.llm.configured ? data.llm.model : "Rule-based"}</span>
        </span>
      </Tip>
    </div>
  );
}

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  return (
    <button
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      className="rounded-md p-2 text-fg-3 hover:bg-surface-2 hover:text-fg cursor-pointer"
      aria-label="Toggle theme"
    >
      <Sun className="hidden size-4 dark:block" />
      <Moon className="size-4 dark:hidden" />
    </button>
  );
}

export function ConsoleShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-border bg-bg lg:flex">
        <div className="flex h-14 items-center px-5">
          <Link href="/" aria-label="PayPilot home">
            <Logo />
          </Link>
        </div>
        <div className="flex-1 overflow-y-auto py-2">
          <NavLinks />
        </div>
        <div className="m-3 rounded-lg border border-border bg-surface p-3">
          <p className="text-[12px] font-medium">Deterministic authorization</p>
          <p className="mt-0.5 text-[12px] leading-snug text-fg-3">AI proposes. Policy, risk and AgentShield decide. No model can approve a payment.</p>
        </div>
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col border-r border-border bg-bg py-3">
            <div className="mb-2 flex items-center justify-between px-5">
              <Logo />
              <button onClick={() => setOpen(false)} aria-label="Close menu" className="rounded-md p-1.5 hover:bg-surface-2 cursor-pointer">
                <X className="size-4" />
              </button>
            </div>
            <NavLinks onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-bg/80 px-4 backdrop-blur-md sm:px-6">
          <button onClick={() => setOpen(true)} className="rounded-md p-1.5 hover:bg-surface-2 lg:hidden cursor-pointer" aria-label="Open menu">
            <Menu className="size-5" />
          </button>
          <p className="hidden text-[13px] text-fg-3 md:block">AI can reason. PayPilot decides if it can spend.</p>
          <div className="ml-auto flex items-center gap-1.5">
            <StatusPills />
            <ThemeToggle />
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1320px] flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>
      </div>
    </div>
  );
}
