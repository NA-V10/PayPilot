"""Request / response models for the REST API."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.core.money import Money
from app.schemas.domain import PolicySpec, TransactionProposal, UntrustedContent


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


UTCDateTime = Annotated[datetime, AfterValidator(_utc)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PolicyOut(ORM):
    id: str
    agent_id: str
    name: str
    currency: str
    max_transaction_amount: Money
    daily_spending_limit: Money
    monthly_spending_limit: Money
    allowed_categories: list[str]
    blocked_categories: list[str]
    minimum_merchant_trust: int
    require_approval_above: Money
    allow_new_merchants: bool
    allow_international: bool
    auto_refund_enabled: bool
    source_text: str | None
    version: int
    created_at: UTCDateTime
    updated_at: UTCDateTime


class AgentStats(BaseModel):
    spent_today: Money
    spent_month: Money
    total_spent: Money
    transactions: int
    blocked: int
    pending_approvals: int


class AgentOut(ORM):
    id: str
    name: str
    type: str
    status: str
    description: str
    policy_id: str | None
    created_at: UTCDateTime
    policy: PolicyOut | None = None
    stats: AgentStats | None = None


class MerchantOut(ORM):
    id: str
    name: str
    domain: str
    country: str
    trust_score: int
    risk_score: int
    verification_status: str
    categories: list[str]
    refund_rate: float
    chargeback_rate: float
    onboarded_at: UTCDateTime
    created_at: UTCDateTime


class MerchantRef(ORM):
    id: str
    name: str
    domain: str
    trust_score: int
    verification_status: str
    country: str


class AgentRef(ORM):
    id: str
    name: str
    type: str


class TransactionOut(ORM):
    id: str
    trace_id: str
    agent: AgentRef
    merchant: MerchantRef | None
    amount: Money
    currency: str
    category: str
    description: str
    status: str
    decision: str | None
    risk_score: int | None
    risk_level: str | None
    policy_decision: str | None = None
    approval_status: str
    autonomous: bool
    payment_provider: str | None
    paypal_order_id: str | None
    paypal_status: str | None
    scenario: str | None
    created_at: UTCDateTime
    completed_at: UTCDateTime | None


class AuditEventOut(ORM):
    id: str
    transaction_id: str | None
    trace_id: str | None
    event_type: str
    stage: str | None
    outcome: str | None
    actor: str
    message: str
    metadata: dict[str, Any] = Field(validation_alias="event_metadata")
    duration_ms: float | None
    timestamp: UTCDateTime


class TransactionDetail(TransactionOut):
    user_request: str | None
    decision_reasons: list[str]
    risk_assessment: dict[str, Any] | None
    shield_result: dict[str, Any] | None
    policy_result: dict[str, Any] | None
    intent: dict[str, Any] | None
    approval_reason: str | None
    approved_by: str | None
    decided_at: UTCDateTime | None
    paypal_capture_id: str | None
    paypal_approve_url: str | None
    settlement_amount: Money | None
    settlement_currency: str | None
    failure_reason: str | None
    events: list[AuditEventOut] = []


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int


class ThreatOut(ORM):
    id: str
    transaction_id: str | None
    threat_type: str
    severity: str
    title: str
    detail: str
    attempted_amount: Money | None
    limit_amount: Money | None
    currency: str | None
    action: str
    created_at: UTCDateTime
    agent: AgentRef | None
    merchant: MerchantRef | None


# ---------- requests


class AgentRunRequest(BaseModel):
    request: str = Field(min_length=3, max_length=500)


class ProposalRequest(TransactionProposal):
    """Direct proposal from an external agent framework (bypasses the built-in search, not governance)."""

    user_request: str | None = Field(default=None, max_length=500)


class PolicyUpdate(PolicySpec):
    source_text: str | None = Field(default=None, max_length=2000)


class CompileRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=2000)
    policy_id: str | None = None


class EvaluateRequest(BaseModel):
    """Policy simulator input. Either reference an agent's policy or supply one inline."""

    policy_id: str | None = None
    policy: PolicySpec | None = None
    amount: Money = Field(gt=0, le=Decimal("100000000"))
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    category: str = Field(min_length=1, max_length=40)
    merchant_trust: int = Field(ge=0, le=100)
    merchant_status: Literal["VERIFIED", "PENDING", "UNVERIFIED", "FLAGGED"] = "VERIFIED"
    merchant_country: str = Field(default="IN", pattern=r"^[A-Z]{2}$")
    merchant_age_days: int = Field(default=365, ge=0)
    daily_spent: Money = Decimal("0")
    intent_budget: Money | None = None


class ScanRequest(BaseModel):
    content: list[UntrustedContent] = Field(min_length=1, max_length=20)
    intent_budget: Money | None = None


class RiskAssessRequest(BaseModel):
    agent_id: str
    merchant_id: str
    amount: Money = Field(gt=0)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    category: str
    external_content: list[UntrustedContent] = Field(default_factory=list, max_length=20)
    intent_budget: Money | None = None


class ApprovalAction(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class CreateOrderRequest(BaseModel):
    transaction_id: str = Field(max_length=20)


class CaptureOrderRequest(BaseModel):
    transaction_id: str = Field(max_length=20)
    order_id: str = Field(max_length=64)


class DemoRunRequest(BaseModel):
    scenario: Literal["safe_purchase", "prompt_injection", "human_approval", "policy_violation", "fail_closed"]
