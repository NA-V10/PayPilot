from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import EventType, VerificationStatus
from app.core.security import Principal, get_principal
from app.db.models import AuditEvent, FinancialPolicy
from app.db.session import get_db
from app.engines.policy import evaluate_policy
from app.schemas.api import CompileRequest, EvaluateRequest, PolicyOut, PolicyUpdate
from app.schemas.domain import MerchantProfile, PolicyResult, PolicySpec, SpendingContext, TransactionProposal
from app.services.orchestrator import policy_spec
from app.services.policy_compiler import CompileResult, compile_policy

router = APIRouter(prefix="/policies", tags=["policies"])

DEFAULT_POLICY = PolicySpec(
    max_transaction_amount=50000,
    daily_spending_limit=100000,
    monthly_spending_limit=500000,
    require_approval_above=25000,
    minimum_merchant_trust=70,
)


def _get(db: Session, policy_id: str) -> FinancialPolicy:
    p = db.get(FinancialPolicy, policy_id)
    if p is None:
        raise HTTPException(404, f"Policy {policy_id} not found")
    return p


@router.get("", response_model=list[PolicyOut])
def list_policies(db: Session = Depends(get_db)) -> list[FinancialPolicy]:
    return list(db.scalars(select(FinancialPolicy).order_by(FinancialPolicy.created_at)).all())


@router.get("/{policy_id}", response_model=PolicyOut)
def get_policy(policy_id: str, db: Session = Depends(get_db)) -> FinancialPolicy:
    return _get(db, policy_id)


@router.put("/{policy_id}", response_model=PolicyOut)
def update_policy(policy_id: str, body: PolicyUpdate, db: Session = Depends(get_db), who: Principal = Depends(get_principal)) -> FinancialPolicy:
    """Replace a policy. The body is fully validated by PolicySpec before anything is stored."""
    p = _get(db, policy_id)
    before = policy_spec(p).model_dump(mode="json")
    data = body.model_dump(exclude={"source_text", "home_country"})
    for k, v in data.items():
        setattr(p, k, v)
    p.source_text = body.source_text
    p.version += 1
    p.updated_at = datetime.now(UTC)
    db.add(
        AuditEvent(
            event_type=EventType.POLICY_UPDATED.value,
            stage="policy",
            outcome="info",
            actor=who.name,
            message=f"{p.name} updated to v{p.version}",
            event_metadata={"policy_id": p.id, "before": before, "after": body.model_dump(mode="json")},
        )
    )
    db.commit()
    return p


@router.post("/compile", response_model=CompileResult)
def compile_(body: CompileRequest, db: Session = Depends(get_db)) -> CompileResult:
    """Natural language → validated structured policy. Nothing is saved until the user confirms."""
    base = policy_spec(_get(db, body.policy_id)) if body.policy_id else DEFAULT_POLICY
    return compile_policy(body.instruction, base)


@router.post("/evaluate", response_model=PolicyResult)
def evaluate(body: EvaluateRequest, db: Session = Depends(get_db)) -> PolicyResult:
    """Policy simulator: evaluate a hypothetical transaction without creating it."""
    if body.policy is not None:
        spec = body.policy
    elif body.policy_id:
        spec = policy_spec(_get(db, body.policy_id))
    else:
        raise HTTPException(422, "Provide policy_id or an inline policy")
    merchant = MerchantProfile(
        id="sim",
        name="Test merchant",
        domain="simulator.local",
        country=body.merchant_country,
        trust_score=body.merchant_trust,
        verification_status=VerificationStatus(body.merchant_status),
        age_days=body.merchant_age_days,
    )
    proposal = TransactionProposal(
        agent_id="simulator",
        merchant_id="sim",
        amount=body.amount,
        currency=body.currency,
        category=body.category,
        description="Policy simulator",
        intent_budget=body.intent_budget,
    )
    return evaluate_policy(spec, proposal, merchant, SpendingContext(daily_total=body.daily_spent, monthly_total=body.daily_spent))
