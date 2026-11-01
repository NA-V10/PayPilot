"""Read-mostly endpoints: dashboard, risk center, security tools, merchants, audit log."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.serializers import tx_out
from app.core.enums import ThreatType, TransactionStatus, VerificationStatus
from app.core.money import convert
from app.db.models import Agent, AuditEvent, FinancialPolicy, Merchant, ThreatEvent, Transaction
from app.db.session import get_db
from app.engines import risk as risk_engine
from app.engines import shield as agent_shield
from app.schemas.api import AuditEventOut, MerchantOut, RiskAssessRequest, ScanRequest, ThreatOut
from app.schemas.domain import RiskAssessment, ShieldResult, TransactionProposal
from app.services.orchestrator import as_utc, merchant_profile, policy_spec, spending_context

router = APIRouter(tags=["insights"])

BASE_CCY = "INR"
BLOCKED = (TransactionStatus.BLOCKED, TransactionStatus.DENIED)


def _f(d: Decimal) -> float:
    return float(round(d, 2))


@router.get("/dashboard/overview")
def overview(db: Session = Depends(get_db), days: int = Query(default=14, ge=1, le=90)) -> dict[str, object]:
    now = datetime.now(UTC)
    txs = db.scalars(select(Transaction)).all()
    agents = {a.id: a for a in db.scalars(select(Agent)).all()}

    total = autonomous = prevented = Decimal("0")
    awaiting = blocked = 0
    start = (now - timedelta(days=days - 1)).date()
    by_day: dict[str, dict[str, float]] = {
        (start + timedelta(days=i)).isoformat(): {"spend": 0.0, "prevented": 0.0, "allowed": 0, "blocked": 0, "approval": 0}
        for i in range(days)
    }
    risk_dist = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    agent_spend: dict[str, Decimal] = defaultdict(Decimal)

    for t in txs:
        amt = convert(t.amount, t.currency, BASE_CCY)
        day = as_utc(t.created_at).date().isoformat()
        bucket = by_day.get(day)
        if t.risk_level in risk_dist:
            risk_dist[t.risk_level] += 1
        if t.status == TransactionStatus.COMPLETED:
            total += amt
            agent_spend[t.agent_id] += amt
            if t.autonomous:
                autonomous += amt
            if bucket:
                bucket["spend"] += float(amt)
        if t.status in BLOCKED:
            blocked += 1
            prevented += amt
            if bucket:
                bucket["prevented"] += float(amt)
                bucket["blocked"] += 1
        elif t.status == TransactionStatus.AWAITING_APPROVAL:
            awaiting += 1
            if bucket:
                bucket["approval"] += 1
        elif t.status in (TransactionStatus.COMPLETED, TransactionStatus.APPROVED, TransactionStatus.PAYMENT_CREATED) and bucket:
            bucket["allowed"] += 1

    merchants = db.scalars(select(Merchant).order_by(Merchant.trust_score.desc())).all()
    tx_count_by_merchant: dict[str, int] = defaultdict(int)
    for t in txs:
        if t.merchant_id:
            tx_count_by_merchant[t.merchant_id] += 1

    recent = sorted(txs, key=lambda t: as_utc(t.created_at), reverse=True)[:6]
    return {
        "currency": BASE_CCY,
        "metrics": {
            "total_spend": _f(total),
            "autonomous_spend": _f(autonomous),
            "awaiting_approval": awaiting,
            "blocked_transactions": blocked,
            "risk_prevented": _f(prevented),
            "active_agents": sum(1 for a in agents.values() if a.status == "ACTIVE"),
            "total_transactions": len(txs),
        },
        "timeseries": [{"date": d, **v} for d, v in by_day.items()],
        "risk_distribution": [{"level": k, "count": v} for k, v in risk_dist.items()],
        "agent_spending": [
            {"agent_id": a.id, "agent": a.name, "type": a.type, "spend": _f(agent_spend.get(a.id, Decimal("0")))} for a in agents.values()
        ],
        "merchant_risk": [
            {"merchant_id": m.id, "merchant": m.name, "trust_score": m.trust_score, "risk_score": m.risk_score,
             "verification_status": m.verification_status, "transactions": tx_count_by_merchant.get(m.id, 0)}
            for m in merchants
        ],
        "recent": [tx_out(t).model_dump(mode="json") for t in recent],
    }


@router.get("/risk/overview")
def risk_overview(db: Session = Depends(get_db)) -> dict[str, object]:
    now = datetime.now(UTC)
    threats = db.scalars(select(ThreatEvent).order_by(ThreatEvent.created_at.desc())).all()
    merchants = db.scalars(select(Merchant)).all()
    recent_tx = db.scalars(
        select(Transaction).where(Transaction.risk_score.is_not(None)).order_by(Transaction.created_at.desc()).limit(20)
    ).all()
    avg = round(sum(t.risk_score or 0 for t in recent_tx) / len(recent_tx)) if recent_tx else 0
    last_24h = [t for t in threats if as_utc(t.created_at) >= now - timedelta(hours=24)]

    # Heatmap: average score of each risk factor, per agent, over the last 30 days.
    agents = db.scalars(select(Agent).order_by(Agent.created_at)).all()
    window = db.scalars(select(Transaction).where(Transaction.created_at >= now - timedelta(days=30), Transaction.risk_assessment.is_not(None))).all()
    factor_keys = ["merchant", "transaction", "behavior", "policy", "prompt_injection"]
    sums: dict[tuple[str, str], list[int]] = defaultdict(list)
    for t in window:
        for f in (t.risk_assessment or {}).get("factors", []):
            sums[(t.agent_id, f["key"])].append(int(f["score"]))
    heatmap = [
        {
            "agent": a.name,
            "agent_id": a.id,
            "cells": [
                {"factor": k, "avg": round(sum(v) / len(v)) if (v := sums.get((a.id, k))) else 0, "max": max(v) if v else 0, "n": len(v) if v else 0}
                for k in factor_keys
            ],
        }
        for a in agents
    ]

    by_day: dict[str, dict[str, int]] = {}
    for i in range(13, -1, -1):
        by_day[(now - timedelta(days=i)).date().isoformat()] = defaultdict(int)  # type: ignore[assignment]
    for t in threats:
        d = as_utc(t.created_at).date().isoformat()
        if d in by_day:
            by_day[d][t.threat_type] += 1

    return {
        "current_risk_level": risk_engine.level_for(avg).value,
        "average_risk_score": avg,
        "threats_24h": len(last_24h),
        "blocked_attacks": sum(1 for t in threats if t.action == "BLOCKED"),
        "prompt_injection_attempts": sum(1 for t in threats if t.threat_type == ThreatType.PROMPT_INJECTION),
        "suspicious_merchants": sum(
            1 for m in merchants if m.trust_score < 60 or m.verification_status in (VerificationStatus.FLAGGED, VerificationStatus.UNVERIFIED)
        ),
        "policy_violations": sum(1 for t in threats if t.threat_type in (ThreatType.SPENDING_VIOLATION, ThreatType.POLICY_VIOLATION)),
        "heatmap": heatmap,
        "threat_timeline": [{"date": d, **dict(v)} for d, v in by_day.items()],
        "recent_threats": [ThreatOut.model_validate(t).model_dump(mode="json") for t in threats[:25]],
    }


@router.get("/threats", response_model=list[ThreatOut])
def list_threats(db: Session = Depends(get_db), limit: int = Query(default=50, le=200)) -> list[ThreatEvent]:
    return list(db.scalars(select(ThreatEvent).order_by(ThreatEvent.created_at.desc()).limit(limit)).all())


@router.post("/security/scan", response_model=ShieldResult)
def security_scan(body: ScanRequest) -> ShieldResult:
    """Run AgentShield on arbitrary external content."""
    return agent_shield.scan(body.content, intent_budget=body.intent_budget)


@router.post("/risk/assess", response_model=RiskAssessment)
def risk_assess(body: RiskAssessRequest, db: Session = Depends(get_db)) -> RiskAssessment:
    agent = db.get(Agent, body.agent_id)
    merchant = db.get(Merchant, body.merchant_id)
    if agent is None or merchant is None:
        raise HTTPException(404, "Unknown agent or merchant")
    policy = db.get(FinancialPolicy, agent.policy_id) if agent.policy_id else None
    if policy is None:
        raise HTTPException(409, "Agent has no policy")
    spec = policy_spec(policy)
    now = datetime.now(UTC)
    proposal = TransactionProposal(
        agent_id=agent.id, merchant_id=merchant.id, amount=body.amount, currency=body.currency, category=body.category,
        description="Risk assessment", intent_budget=body.intent_budget, external_content=body.external_content,
    )
    shield = agent_shield.scan(body.external_content, intent_budget=body.intent_budget)
    return risk_engine.assess(proposal, merchant_profile(merchant, now), spending_context(db, agent.id, spec.currency, now), spec, shield)


@router.get("/merchants", response_model=list[MerchantOut])
def list_merchants(db: Session = Depends(get_db)) -> list[Merchant]:
    return list(db.scalars(select(Merchant).order_by(Merchant.trust_score.desc())).all())


@router.get("/audit")
def audit_log(
    db: Session = Depends(get_db),
    event_type: str | None = None,
    transaction_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    stmt = select(AuditEvent)
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    if transaction_id:
        stmt = stmt.where(AuditEvent.transaction_id == transaction_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(AuditEvent.timestamp.desc()).limit(limit).offset(offset)).all()
    return {"items": [AuditEventOut.model_validate(e).model_dump(mode="json") for e in rows], "total": total}
