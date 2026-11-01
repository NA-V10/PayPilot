"""Engine-facing domain models. Pure data, no ORM, so the engines stay deterministic and testable."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import Decision, FinalDecision, RiskLevel, Severity, TransactionStatus, VerificationStatus
from app.core.money import Money

Category = str


def _norm_categories(values: list[str]) -> list[str]:
    out: list[str] = []
    for v in values:
        c = v.strip().lower().replace(" ", "_").replace("-", "_")
        if c and c not in out:
            out.append(c)
    return out


class PolicySpec(BaseModel):
    """A validated financial policy. Every limit is expressed in `currency`."""

    model_config = ConfigDict(extra="forbid")

    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    home_country: str = Field(default="IN", pattern=r"^[A-Z]{2}$")
    max_transaction_amount: Money = Field(ge=0, le=Decimal("100000000"))
    daily_spending_limit: Money = Field(ge=0, le=Decimal("100000000"))
    monthly_spending_limit: Money = Field(ge=0, le=Decimal("1000000000"))
    allowed_categories: list[Category] = Field(default_factory=list, max_length=50)
    blocked_categories: list[Category] = Field(default_factory=list, max_length=50)
    minimum_merchant_trust: int = Field(default=70, ge=0, le=100)
    require_approval_above: Money = Field(ge=0, le=Decimal("100000000"))
    allow_new_merchants: bool = False
    allow_international: bool = False
    auto_refund_enabled: bool = True

    @field_validator("allowed_categories", "blocked_categories")
    @classmethod
    def _normalize(cls, v: list[str]) -> list[str]:
        return _norm_categories(v)

    @model_validator(mode="after")
    def _coherent(self) -> PolicySpec:
        if self.require_approval_above > self.max_transaction_amount:
            raise ValueError("Approval threshold cannot exceed the maximum transaction amount")
        if self.daily_spending_limit > self.monthly_spending_limit:
            raise ValueError("Daily spending limit cannot exceed the monthly limit")
        overlap = set(self.allowed_categories) & set(self.blocked_categories)
        if overlap:
            raise ValueError(f"Categories cannot be both allowed and blocked: {', '.join(sorted(overlap))}")
        return self


class MerchantProfile(BaseModel):
    id: str
    name: str
    domain: str
    country: str = "IN"
    trust_score: int = Field(ge=0, le=100)
    verification_status: VerificationStatus
    categories: list[str] = Field(default_factory=list)
    refund_rate: float = Field(default=0, ge=0, le=1)
    chargeback_rate: float = Field(default=0, ge=0, le=1)
    age_days: int = Field(default=365, ge=0)


class UntrustedContent(BaseModel):
    """External content the agent read (merchant pages, reviews, emails). Always DATA, never instructions."""

    source: str = Field(max_length=300)
    content: str = Field(max_length=20000)


class TransactionProposal(BaseModel):
    agent_id: str
    merchant_id: str
    amount: Money = Field(gt=0, le=Decimal("100000000"))
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    category: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=500)
    intent_budget: Money | None = Field(default=None, gt=0)
    external_content: list[UntrustedContent] = Field(default_factory=list, max_length=20)

    @field_validator("category")
    @classmethod
    def _cat(cls, v: str) -> str:
        return _norm_categories([v])[0]


class SpendingContext(BaseModel):
    """Historical facts about the agent, all in the policy currency."""

    daily_total: Money = Decimal("0")
    monthly_total: Money = Decimal("0")
    tx_last_hour: int = 0
    average_amount: Money | None = None
    history_count: int = 0
    known_categories: list[str] = Field(default_factory=list)


# ---------- engine outputs ----------

RuleStatus = Literal["pass", "fail", "warn", "skip"]


class RuleCheck(BaseModel):
    rule: str
    label: str
    status: RuleStatus
    detail: str
    actual: str | None = None
    limit: str | None = None


class PolicyResult(BaseModel):
    decision: Decision
    reasons: list[str]
    failed_rules: list[str]
    approval_required: bool
    checks: list[RuleCheck]
    evaluated_amount: Money
    policy_currency: str


class Threat(BaseModel):
    type: str
    pattern_id: str
    severity: Severity
    title: str
    explanation: str
    excerpt: str
    source: str
    detector: Literal["deterministic", "llm"] = "deterministic"


class ShieldResult(BaseModel):
    verdict: Literal["CLEAN", "SUSPICIOUS", "BLOCK"]
    severity: Severity | None
    risk_score: int = Field(ge=0, le=100)
    threats: list[Threat]
    sources_scanned: int
    sanitized: list[UntrustedContent]
    summary: str


class RiskFactor(BaseModel):
    name: str
    key: str
    score: int = Field(ge=0, le=100)
    weight: float
    reasons: list[str]


class RiskAssessment(BaseModel):
    transaction_risk: int
    merchant_risk: int
    behavior_risk: int
    policy_risk: int
    prompt_injection_risk: int
    overall_score: int
    level: RiskLevel
    factors: list[RiskFactor]
    reasons: list[str]
    method: str


class DecisionResult(BaseModel):
    decision: FinalDecision
    status: TransactionStatus
    blocking_stage: str | None
    reasons: list[str]
    fail_closed: bool = False
