from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import tx_detail
from app.core.enums import COMMITTED_STATUSES, TransactionStatus
from app.core.money import convert
from app.core.security import Principal, agent_rate_limit, get_principal
from app.db.models import Agent, FinancialPolicy, Merchant, Transaction
from app.db.session import get_db
from app.schemas.api import AgentOut, AgentRunRequest, AgentStats, PolicyOut, ProposalRequest, TransactionDetail
from app.services.orchestrator import as_utc, govern, run_agent

router = APIRouter(prefix="/agents", tags=["agents"])


def _agent_out(db: Session, agent: Agent) -> AgentOut:
    out = AgentOut.model_validate(agent)
    policy = db.get(FinancialPolicy, agent.policy_id) if agent.policy_id else None
    out.policy = PolicyOut.model_validate(policy) if policy else None
    ccy = policy.currency if policy else "INR"
    now = datetime.now(UTC)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month = day.replace(day=1)
    rows = db.scalars(select(Transaction).where(Transaction.agent_id == agent.id)).all()
    today = month_total = total = Decimal("0")
    for t in rows:
        if t.status not in COMMITTED_STATUSES:
            continue
        amt = convert(t.amount, t.currency, ccy)
        created = as_utc(t.created_at)
        total += amt
        if created >= month:
            month_total += amt
        if created >= day:
            today += amt
    out.stats = AgentStats(
        spent_today=today,
        spent_month=month_total,
        total_spent=total,
        transactions=len(rows),
        blocked=sum(1 for t in rows if t.status in (TransactionStatus.BLOCKED, TransactionStatus.DENIED)),
        pending_approvals=sum(1 for t in rows if t.status == TransactionStatus.AWAITING_APPROVAL),
    )
    return out


def _get_agent(db: Session, agent_id: str) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return agent


@router.get("", response_model=list[AgentOut])
def list_agents(db: Session = Depends(get_db)) -> list[AgentOut]:
    return [_agent_out(db, a) for a in db.scalars(select(Agent).order_by(Agent.created_at)).all()]


@router.get("/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: str, db: Session = Depends(get_db)) -> AgentOut:
    return _agent_out(db, _get_agent(db, agent_id))


@router.post("/{agent_id}/run", response_model=TransactionDetail, dependencies=[Depends(agent_rate_limit)])
def run(agent_id: str, body: AgentRunRequest, db: Session = Depends(get_db), _: Principal = Depends(get_principal)) -> TransactionDetail:
    """Give the agent a natural-language task. The agent searches and proposes; PayPilot decides."""
    agent = _get_agent(db, agent_id)
    if agent.status != "ACTIVE":
        raise HTTPException(409, f"{agent.name} is {agent.status.lower()}")
    tx = run_agent(db, agent, body.request)
    db.commit()
    return tx_detail(db, tx)


@router.post("/{agent_id}/proposals", response_model=TransactionDetail, dependencies=[Depends(agent_rate_limit)])
def propose(agent_id: str, body: ProposalRequest, db: Session = Depends(get_db), _: Principal = Depends(get_principal)) -> TransactionDetail:
    """Submit a transaction proposal from any external agent. It goes through full governance."""
    agent = _get_agent(db, agent_id)
    if body.agent_id != agent_id:
        raise HTTPException(422, "agent_id in body does not match the URL")
    if db.get(Merchant, body.merchant_id) is None:
        raise HTTPException(404, f"Merchant {body.merchant_id} not found")
    if agent.status != "ACTIVE":
        raise HTTPException(409, f"{agent.name} is {agent.status.lower()}")
    proposal = body.model_copy()
    tx = govern(db, agent, proposal, user_request=body.user_request)
    db.commit()
    return tx_detail(db, tx)


@router.post("/{agent_id}/status", response_model=AgentOut)
def set_status(agent_id: str, status: str, db: Session = Depends(get_db), _: Principal = Depends(get_principal)) -> AgentOut:
    if status not in ("ACTIVE", "PAUSED"):
        raise HTTPException(422, "status must be ACTIVE or PAUSED")
    agent = _get_agent(db, agent_id)
    agent.status = status
    db.commit()
    return _agent_out(db, agent)
