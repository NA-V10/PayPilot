"use client";

import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { money, shortDate } from "@/lib/format";
import type { Overview } from "@/lib/types";

/* Colors follow the dataviz reference palette via CSS variables (light/dark selected separately).
   Status colors are reserved for allowed / blocked and always appear with a text label. */

const axis = { stroke: "var(--axis)", tick: { fill: "var(--fg-3)", fontSize: 11 }, tickLine: false } as const;

function TooltipBox({ title, rows }: { title: string; rows: { label: string; value: string; color: string }[] }) {
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2 text-[12px] shadow-lg">
      <p className="mb-1 font-medium text-fg">{title}</p>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center gap-2">
          <span className="size-2 rounded-sm" style={{ background: r.color }} />
          <span className="text-fg-2">{r.label}</span>
          <span className="ml-auto pl-4 font-medium text-fg tabular">{r.value}</span>
        </div>
      ))}
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-fg-2">
      {items.map((i) => (
        <span key={i.label} className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm" style={{ background: i.color }} />
          {i.label}
        </span>
      ))}
    </div>
  );
}

export function SpendChart({ data, currency }: { data: Overview["timeseries"]; currency: string }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="spendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--series-1)" stopOpacity={0.22} />
            <stop offset="100%" stopColor="var(--series-1)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke="var(--grid)" />
        <XAxis dataKey="date" {...axis} tickFormatter={shortDate} minTickGap={24} />
        <YAxis {...axis} axisLine={false} width={56} tickFormatter={(v) => money(v, currency, { compact: true })} />
        <Tooltip
          cursor={{ stroke: "var(--axis)" }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TooltipBox title={shortDate(String(label))} rows={[{ label: "Completed spend", value: money(Number(payload[0].value), currency), color: "var(--series-1)" }]} />
            ) : null
          }
        />
        <Area type="monotone" dataKey="spend" stroke="var(--series-1)" strokeWidth={2} fill="url(#spendFill)" activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--chart-surface)" }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function DecisionsChart({ data }: { data: Overview["timeseries"] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }} barGap={2}>
        <CartesianGrid vertical={false} stroke="var(--grid)" />
        <XAxis dataKey="date" {...axis} tickFormatter={shortDate} minTickGap={24} />
        <YAxis {...axis} axisLine={false} allowDecimals={false} />
        <Tooltip
          cursor={{ fill: "var(--surface-2)" }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TooltipBox
                title={shortDate(String(label))}
                rows={[
                  { label: "Allowed", value: String(payload.find((p) => p.dataKey === "allowed")?.value ?? 0), color: "var(--status-good)" },
                  { label: "Needs approval", value: String(payload.find((p) => p.dataKey === "approval")?.value ?? 0), color: "var(--status-warning)" },
                  { label: "Blocked / denied", value: String(payload.find((p) => p.dataKey === "blocked")?.value ?? 0), color: "var(--status-critical)" },
                ]}
              />
            ) : null
          }
        />
        <Bar dataKey="allowed" stackId="a" fill="var(--status-good)" stroke="var(--chart-surface)" strokeWidth={1} />
        <Bar dataKey="approval" stackId="a" fill="var(--status-warning)" stroke="var(--chart-surface)" strokeWidth={1} />
        <Bar dataKey="blocked" stackId="a" fill="var(--status-critical)" stroke="var(--chart-surface)" strokeWidth={1} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

const AGENT_COLOR: Record<string, string> = { travel: "var(--series-1)", shopping: "var(--series-2)", business: "var(--series-3)" };

export function AgentSpendChart({ data, currency }: { data: Overview["agent_spending"]; currency: string }) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(120, data.length * 44)}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 64, left: 0, bottom: 0 }}>
        <XAxis type="number" hide />
        <YAxis type="category" dataKey="agent" {...axis} axisLine={false} width={110} tick={{ fill: "var(--fg-2)", fontSize: 12 }} />
        <Tooltip
          cursor={{ fill: "var(--surface-2)" }}
          content={({ active, payload }) =>
            active && payload?.length ? (
              <TooltipBox
                title={String(payload[0].payload.agent)}
                rows={[{ label: "Completed spend", value: money(Number(payload[0].value), currency), color: AGENT_COLOR[payload[0].payload.type] }]}
              />
            ) : null
          }
        />
        <Bar dataKey="spend" radius={[0, 4, 4, 0]} barSize={18} label={{ position: "right", fill: "var(--fg-2)", fontSize: 12, formatter: (v: unknown) => money(Number(v), currency, { compact: true }) }}>
          {data.map((d) => (
            <Cell key={d.agent_id} fill={AGENT_COLOR[d.type] ?? "var(--series-1)"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

const RISK_COLOR: Record<string, string> = {
  LOW: "var(--status-good)",
  MEDIUM: "var(--status-warning)",
  HIGH: "var(--status-serious)",
  CRITICAL: "var(--status-critical)",
};

/** Risk distribution as a single segmented bar with labelled counts (a part-to-whole of 4). */
export function RiskDistribution({ data }: { data: Overview["risk_distribution"] }) {
  const total = data.reduce((s, d) => s + d.count, 0) || 1;
  return (
    <div>
      <div className="flex h-3 w-full gap-[2px] overflow-hidden rounded-full" role="img" aria-label={data.map((d) => `${d.level}: ${d.count}`).join(", ")}>
        {data.filter((d) => d.count).map((d) => (
          <div key={d.level} style={{ width: `${(d.count / total) * 100}%`, background: RISK_COLOR[d.level] }} title={`${d.level}: ${d.count}`} />
        ))}
      </div>
      <dl className="mt-4 grid grid-cols-4 gap-2">
        {data.map((d) => (
          <div key={d.level}>
            <dt className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-fg-3">
              <span className="size-2 rounded-sm" style={{ background: RISK_COLOR[d.level] }} />
              {d.level}
            </dt>
            <dd className="mt-0.5 text-lg font-semibold tabular">{d.count}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
