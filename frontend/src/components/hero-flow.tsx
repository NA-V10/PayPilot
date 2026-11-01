"use client";

import { motion } from "framer-motion";
import { Bot, Check, CreditCard, Store } from "lucide-react";
import { LogoMark } from "@/components/logo";

const CHECKS = ["Policy", "Risk", "Security"];

function Node({ icon, title, sub, delay, accent }: { icon: React.ReactNode; title: string; sub: string; delay: number; accent?: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className={`flex items-center gap-3 rounded-xl border px-4 py-3 ${accent ? "border-border-strong bg-surface shadow-card" : "border-border bg-surface/70"}`}
    >
      <span className="grid size-9 place-items-center rounded-lg bg-surface-2">{icon}</span>
      <div>
        <p className="text-[13px] font-semibold">{title}</p>
        <p className="text-[12px] text-fg-3">{sub}</p>
      </div>
    </motion.div>
  );
}

function Connector({ delay }: { delay: number }) {
  return (
    <div className="flex justify-center py-1" aria-hidden>
      <motion.span initial={{ scaleY: 0 }} animate={{ scaleY: 1 }} transition={{ delay, duration: 0.3 }} className="h-6 w-px origin-top bg-border-strong" />
    </div>
  );
}

/** Static architecture illustration for the hero: agent → PayPilot checks → PayPal → merchant. */
export function HeroFlow() {
  return (
    <div className="dot-grid relative rounded-2xl border border-border bg-surface-2/40 p-6 sm:p-8" role="img" aria-label="AI agent request passes PayPilot's policy, risk and security checks before PayPal executes payment">
      <div className="mx-auto max-w-xs">
        <Node icon={<Bot className="size-4 text-fg-2" />} title="AI agent" sub="Proposes ₹7,900 · Lumen Suites" delay={0.1} />
        <Connector delay={0.35} />
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45, duration: 0.4 }}
          className="rounded-xl border border-border-strong bg-surface p-4 shadow-card"
        >
          <div className="flex items-center gap-2">
            <LogoMark className="size-6" />
            <span className="text-[13px] font-semibold">PayPilot</span>
            <span className="ml-auto text-[11px] font-medium text-fg-3">deterministic</span>
          </div>
          <ul className="mt-3 space-y-1.5">
            {CHECKS.map((c, i) => (
              <motion.li
                key={c}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.7 + i * 0.2 }}
                className="flex items-center justify-between rounded-md bg-surface-2 px-2.5 py-1.5 text-[13px]"
              >
                {c}
                <span className="flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wide text-good">
                  <Check className="size-3.5" strokeWidth={3} /> Pass
                </span>
              </motion.li>
            ))}
          </ul>
        </motion.div>
        <Connector delay={1.4} />
        <Node icon={<CreditCard className="size-4 text-fg-2" />} title="PayPal" sub="Order created & captured" delay={1.5} />
        <Connector delay={1.75} />
        <Node icon={<Store className="size-4 text-fg-2" />} title="Merchant" sub="Paid · within your rules" delay={1.85} />
      </div>
    </div>
  );
}
