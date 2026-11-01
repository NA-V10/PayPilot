import type {
  Agent,
  AuditEvent,
  CompileResult,
  Merchant,
  Overview,
  Policy,
  PolicyFields,
  PolicyResult,
  RiskOverview,
  Scenario,
  ShieldResult,
  SystemStatus,
  Transaction,
  TransactionDetail,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
    public fields?: { field: string; message: string }[],
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("The PayPilot API could not be reached. Is the backend running?", 0, "network");
  }
  if (!res.ok) {
    let body: { error?: { message?: string; code?: string; fields?: { field: string; message: string }[] } } = {};
    try {
      body = await res.json();
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(body.error?.message ?? `Request failed (${res.status})`, res.status, body.error?.code ?? "error", body.error?.fields);
  }
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });

export const api = {
  status: () => request<SystemStatus>("/system/status"),
  overview: () => request<Overview>("/dashboard/overview"),
  riskOverview: () => request<RiskOverview>("/risk/overview"),
  agents: () => request<Agent[]>("/agents"),
  agent: (id: string) => request<Agent>(`/agents/${id}`),
  runAgent: (id: string, text: string) => post<TransactionDetail>(`/agents/${id}/run`, { request: text }),
  setAgentStatus: (id: string, status: "ACTIVE" | "PAUSED") => post<Agent>(`/agents/${id}/status?status=${status}`),
  policies: () => request<Policy[]>("/policies"),
  updatePolicy: (id: string, body: PolicyFields & { source_text?: string | null }) =>
    request<Policy>(`/policies/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  compilePolicy: (instruction: string, policy_id?: string) => post<CompileResult>("/policies/compile", { instruction, policy_id }),
  evaluatePolicy: (body: Record<string, unknown>) => post<PolicyResult>("/policies/evaluate", body),
  transactions: (params: Record<string, string | string[] | number | undefined> = {}) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === "") continue;
      if (Array.isArray(v)) v.forEach((x) => q.append(k, x));
      else q.set(k, String(v));
    }
    return request<{ items: Transaction[]; total: number }>(`/transactions?${q}`);
  },
  transaction: (id: string) => request<TransactionDetail>(`/transactions/${id}`),
  approvals: (state: "pending" | "resolved" | "all" = "pending") => request<TransactionDetail[]>(`/approvals?state=${state}`),
  approve: (id: string, note?: string) => post<TransactionDetail>(`/approvals/${id}/approve`, { note }),
  deny: (id: string, note?: string) => post<TransactionDetail>(`/approvals/${id}/deny`, { note }),
  createOrder: (transaction_id: string) => post<TransactionDetail>("/paypal/create-order", { transaction_id }),
  captureOrder: (transaction_id: string, order_id: string) => post<TransactionDetail>("/paypal/capture-order", { transaction_id, order_id }),
  merchants: () => request<Merchant[]>("/merchants"),
  audit: (params: { limit?: number; offset?: number; event_type?: string } = {}) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]));
    return request<{ items: AuditEvent[]; total: number }>(`/audit?${q}`);
  },
  scan: (content: string, intent_budget?: number) =>
    post<ShieldResult>("/security/scan", { content: [{ source: "pasted content", content }], intent_budget }),
  scenarios: () => request<Scenario[]>("/demo/scenarios"),
  runScenario: (scenario: Scenario["id"]) => post<TransactionDetail>("/demo/run", { scenario }),
  resetDemo: () => post<{ status: string }>("/demo/reset"),
};
