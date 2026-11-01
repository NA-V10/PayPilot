export type TxStatus =
  | "PROPOSED"
  | "POLICY_REVIEW"
  | "RISK_REVIEW"
  | "AWAITING_APPROVAL"
  | "APPROVED"
  | "DENIED"
  | "BLOCKED"
  | "PAYMENT_CREATED"
  | "COMPLETED"
  | "FAILED";

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type Outcome = "pass" | "fail" | "warn" | "info" | "skip";
export type Stage = "intent" | "agent" | "shield" | "risk" | "policy" | "approval" | "paypal" | "complete";

export interface Policy {
  id: string;
  agent_id: string;
  name: string;
  currency: string;
  max_transaction_amount: number;
  daily_spending_limit: number;
  monthly_spending_limit: number;
  allowed_categories: string[];
  blocked_categories: string[];
  minimum_merchant_trust: number;
  require_approval_above: number;
  allow_new_merchants: boolean;
  allow_international: boolean;
  auto_refund_enabled: boolean;
  source_text: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export type PolicyFields = Omit<Policy, "id" | "agent_id" | "name" | "version" | "created_at" | "updated_at" | "source_text">;

export interface Agent {
  id: string;
  name: string;
  type: "travel" | "shopping" | "business";
  status: "ACTIVE" | "PAUSED";
  description: string;
  policy_id: string | null;
  created_at: string;
  policy: Policy | null;
  stats: {
    spent_today: number;
    spent_month: number;
    total_spent: number;
    transactions: number;
    blocked: number;
    pending_approvals: number;
  } | null;
}

export interface Merchant {
  id: string;
  name: string;
  domain: string;
  country: string;
  trust_score: number;
  risk_score: number;
  verification_status: "VERIFIED" | "PENDING" | "UNVERIFIED" | "FLAGGED";
  categories: string[];
  refund_rate: number;
  chargeback_rate: number;
  onboarded_at: string;
  created_at: string;
}

export interface Transaction {
  id: string;
  trace_id: string;
  agent: { id: string; name: string; type: string };
  merchant: { id: string; name: string; domain: string; trust_score: number; verification_status: string; country: string } | null;
  amount: number;
  currency: string;
  category: string;
  description: string;
  status: TxStatus;
  decision: string | null;
  risk_score: number | null;
  risk_level: RiskLevel | null;
  policy_decision: "ALLOW" | "DENY" | "HUMAN_APPROVAL_REQUIRED" | null;
  approval_status: "NOT_REQUIRED" | "PENDING" | "APPROVED" | "DENIED";
  autonomous: boolean;
  payment_provider: "paypal" | "simulated" | "seed" | null;
  paypal_order_id: string | null;
  paypal_status: string | null;
  scenario: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface AuditEvent {
  id: string;
  transaction_id: string | null;
  trace_id: string | null;
  event_type: string;
  stage: Stage | null;
  outcome: Outcome | null;
  actor: string;
  message: string;
  metadata: Record<string, unknown>;
  duration_ms: number | null;
  timestamp: string;
}

export interface RuleCheck {
  rule: string;
  label: string;
  status: "pass" | "fail" | "warn" | "skip";
  detail: string;
  actual: string | null;
  limit: string | null;
}

export interface PolicyResult {
  decision: "ALLOW" | "DENY" | "HUMAN_APPROVAL_REQUIRED";
  reasons: string[];
  failed_rules: string[];
  approval_required: boolean;
  checks: RuleCheck[];
  evaluated_amount: number;
  policy_currency: string;
}

export interface Threat {
  type: string;
  pattern_id: string;
  severity: RiskLevel;
  title: string;
  explanation: string;
  excerpt: string;
  source: string;
  detector: "deterministic" | "llm";
}

export interface ShieldResult {
  verdict: "CLEAN" | "SUSPICIOUS" | "BLOCK";
  severity: RiskLevel | null;
  risk_score: number;
  threats: Threat[];
  sources_scanned: number;
  sanitized: { source: string; content: string }[];
  summary: string;
}

export interface RiskFactor {
  name: string;
  key: string;
  score: number;
  weight: number;
  reasons: string[];
}

export interface RiskAssessment {
  overall_score: number;
  level: RiskLevel;
  factors: RiskFactor[];
  reasons: string[];
  method: string;
  transaction_risk: number;
  merchant_risk: number;
  behavior_risk: number;
  policy_risk: number;
  prompt_injection_risk: number;
}

export interface Intent {
  agent_type: string | null;
  query: string;
  category: string | null;
  max_budget: number | null;
  currency: string;
  location: string | null;
  avoid_suspicious_merchants: boolean;
  constraints: string[];
  source: "llm" | "rules";
}

export interface TransactionDetail extends Transaction {
  user_request: string | null;
  decision_reasons: string[];
  risk_assessment: RiskAssessment | null;
  shield_result: ShieldResult | null;
  policy_result: PolicyResult | null;
  intent: Intent | null;
  approval_reason: string | null;
  approved_by: string | null;
  decided_at: string | null;
  paypal_capture_id: string | null;
  paypal_approve_url: string | null;
  settlement_amount: number | null;
  settlement_currency: string | null;
  failure_reason: string | null;
  events: AuditEvent[];
}

export interface SystemStatus {
  demo_mode: boolean;
  authorization: string;
  payments: {
    mode: "paypal" | "simulated";
    environment: string;
    connected: boolean;
    client_id: string | null;
    settlement_currency: string;
    label: string;
  };
  llm: { configured: boolean; provider: string | null; model: string | null; label: string };
}

export interface ThreatEvent {
  id: string;
  transaction_id: string | null;
  threat_type: string;
  severity: RiskLevel;
  title: string;
  detail: string;
  attempted_amount: number | null;
  limit_amount: number | null;
  currency: string | null;
  action: "BLOCKED" | "DENIED" | "ESCALATED" | "FLAGGED";
  created_at: string;
  agent: { id: string; name: string; type: string } | null;
  merchant: { id: string; name: string; domain: string; trust_score: number } | null;
}

export interface Overview {
  currency: string;
  metrics: {
    total_spend: number;
    autonomous_spend: number;
    awaiting_approval: number;
    blocked_transactions: number;
    risk_prevented: number;
    active_agents: number;
    total_transactions: number;
  };
  timeseries: { date: string; spend: number; prevented: number; allowed: number; blocked: number; approval: number }[];
  risk_distribution: { level: RiskLevel; count: number }[];
  agent_spending: { agent_id: string; agent: string; type: string; spend: number }[];
  merchant_risk: { merchant_id: string; merchant: string; trust_score: number; risk_score: number; verification_status: string; transactions: number }[];
  recent: Transaction[];
}

export interface RiskOverview {
  current_risk_level: RiskLevel;
  average_risk_score: number;
  threats_24h: number;
  blocked_attacks: number;
  prompt_injection_attempts: number;
  suspicious_merchants: number;
  policy_violations: number;
  heatmap: { agent: string; agent_id: string; cells: { factor: string; avg: number; max: number; n: number }[] }[];
  threat_timeline: ({ date: string } & Record<string, number | string>)[];
  recent_threats: ThreatEvent[];
}

export interface CompileResult {
  instruction: string;
  source: "llm" | "rules";
  changes: { field: string; label: string; before: unknown; after: unknown; display: string }[];
  policy: (PolicyFields & { home_country: string }) | null;
  valid: boolean;
  errors: string[];
  notes: string[];
}

export interface Scenario {
  id: "safe_purchase" | "prompt_injection" | "human_approval" | "policy_violation" | "fail_closed";
  title: string;
  agent_id: string;
  request: string;
  amount: number;
  currency: string;
  expected: string;
  mode: "agent" | "scripted";
  note: string;
  faults: string[];
}
