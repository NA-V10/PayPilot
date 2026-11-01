"""PayPilot orchestrator: runs every agent action through the governance pipeline.

    INTENT -> AGENT (search + proposal) -> AGENTSHIELD -> RISK -> POLICY -> APPROVAL -> PAYPAL

Every stage emits an AuditEvent tagged with the transaction's trace id, which powers the
live trace UI. Any engine failure fails closed: the transaction is blocked and no payment
is attempted.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import (
    COMMITTED_STATUSES,
    ApprovalStatus,
    Decision,
    EventType,
    FinalDecision,
    Severity,
    ThreatType,
    TransactionStatus,
    VerificationStatus,
)
from app.core.logging import get_logger, trace_id_var
from app.core.money import convert
from app.db.models import Agent, AuditEvent, FinancialPolicy, Merchant, ThreatEvent, Transaction, new_trace_id, new_tx_id
from app.engines import decision as decision_engine
from app.engines import policy as policy_engine
from app.engines import risk as risk_engine
from app.engines import shield as agent_shield
from app.engines.policy import fmt
from app.schemas.domain import (
    DecisionResult,
    MerchantProfile,
    PolicyResult,
    PolicySpec,
    RiskAssessment,
    ShieldResult,
    SpendingContext,
    TransactionProposal,
    UntrustedContent,
)
from app.services import catalog
from app.services.intent import Intent, extract_intent
from app.services.llm import LLMUnavailable
from app.services.paypal import PaymentError, get_payment_provider

log = get_logger("orchestrator")

SUPPORTED_FAULTS = {"risk_engine", "ai_service", "paypal"}


class TransitionError(RuntimeError):
    """Raised when an action is not valid for the transaction's current state (HTTP 409)."""


def as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


# ---------------------------------------------------------------- conversions


def policy_spec(p: FinancialPolicy, home_country: str = "IN") -> PolicySpec:
    return PolicySpec(
        currency=p.currency,
        home_country=home_country,
        max_transaction_amount=p.max_transaction_amount,
        daily_spending_limit=p.daily_spending_limit,
        monthly_spending_limit=p.monthly_spending_limit,
        allowed_categories=list(p.allowed_categories or []),
        blocked_categories=list(p.blocked_categories or []),
        minimum_merchant_trust=p.minimum_merchant_trust,
        require_approval_above=p.require_approval_above,
        allow_new_merchants=p.allow_new_merchants,
        allow_international=p.allow_international,
        auto_refund_enabled=p.auto_refund_enabled,
    )


def merchant_profile(m: Merchant, now: datetime) -> MerchantProfile:
    return MerchantProfile(
        id=m.id,
        name=m.name,
        domain=m.domain,
        country=m.country,
        trust_score=m.trust_score,
        verification_status=VerificationStatus(m.verification_status),
        categories=list(m.categories or []),
        refund_rate=float(m.refund_rate),
        chargeback_rate=float(m.chargeback_rate),
        age_days=max(0, (now - as_utc(m.onboarded_at)).days),
    )


def spending_context(db: Session, agent_id: str, currency: str, now: datetime, exclude_tx: str | None = None) -> SpendingContext:
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = day_start.replace(day=1)
    q = select(Transaction).where(Transaction.agent_id == agent_id, Transaction.created_at >= now - timedelta(days=60))
    if exclude_tx:
        q = q.where(Transaction.id != exclude_tx)
    rows = db.scalars(q).all()

    daily = monthly = Decimal("0")
    committed: list[Decimal] = []
    categories: set[str] = set()
    last_hour = 0
    for t in rows:
        created = as_utc(t.created_at)
        if created > now:
            continue
        amt = convert(t.amount, t.currency, currency)
        if created >= now - timedelta(hours=1):
            last_hour += 1
        if t.status in COMMITTED_STATUSES:
            committed.append(amt)
            categories.add(t.category)
            if created >= day_start:
                daily += amt
            if created >= month_start:
                monthly += amt
    return SpendingContext(
        daily_total=daily,
        monthly_total=monthly,
        tx_last_hour=last_hour,
        average_amount=(sum(committed) / len(committed)) if committed else None,
        history_count=len(committed),
        known_categories=sorted(categories),
    )


# ---------------------------------------------------------------- events


class Recorder:
    """Collects audit events for one transaction, with real stage timings."""

    def __init__(self, db: Session, tx: Transaction, now: datetime) -> None:
        self.db = db
        self.tx = tx
        self.clock = now
        self._t0 = time.perf_counter()

    def emit(
        self,
        event_type: EventType,
        stage: str,
        outcome: str,
        message: str,
        actor: str = "paypilot",
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        elapsed = (time.perf_counter() - self._t0) * 1000
        self._t0 = time.perf_counter()
        ev = AuditEvent(
            transaction_id=self.tx.id,
            trace_id=self.tx.trace_id,
            event_type=event_type.value,
            stage=stage,
            outcome=outcome,
            actor=actor,
            message=message,
            event_metadata=metadata or {},
            duration_ms=round(elapsed, 2),
            timestamp=self.clock,
        )
        # Keep timestamps strictly ordered for the trace, even within the same millisecond.
        self.clock = self.clock + timedelta(milliseconds=1)
        self.db.add(ev)
        log.info(message, extra={"data": {"event": event_type.value, "tx": self.tx.id, "stage": stage, "outcome": outcome}})
        return ev


def _threat(
    db: Session,
    tx: Transaction,
    threat_type: ThreatType,
    severity: Severity,
    title: str,
    detail: str,
    action: str,
    now: datetime,
    attempted: Decimal | None = None,
    limit: Decimal | None = None,
) -> None:
    db.add(
        ThreatEvent(
            transaction_id=tx.id,
            agent_id=tx.agent_id,
            merchant_id=tx.merchant_id,
            threat_type=threat_type.value,
            severity=severity.value,
            title=title,
            detail=detail,
            attempted_amount=attempted,
            limit_amount=limit,
            currency=tx.currency,
            action=action,
            created_at=now,
        )
    )


# ---------------------------------------------------------------- governance


def govern(
    db: Session,
    agent: Agent,
    proposal: TransactionProposal,
    *,
    user_request: str | None = None,
    intent: Intent | None = None,
    scenario: str | None = None,
    faults: set[str] | None = None,
    now: datetime | None = None,
    tx: Transaction | None = None,
    recorder: Recorder | None = None,
    execute_payment: bool = True,
) -> Transaction:
    """Evaluate a proposal through AgentShield, Risk, Policy and Approval, then act on the decision."""
    faults = faults or set()
    now = now or datetime.now(UTC)

    merchant = db.get(Merchant, proposal.merchant_id)
    if merchant is None:
        raise ValueError(f"Unknown merchant {proposal.merchant_id}")
    policy_row = db.get(FinancialPolicy, agent.policy_id) if agent.policy_id else None

    if tx is None:
        tx = Transaction(id=new_tx_id(), trace_id=new_trace_id(), created_at=now)
        db.add(tx)
    tx.agent_id = agent.id
    tx.merchant_id = merchant.id
    tx.amount = proposal.amount
    tx.currency = proposal.currency
    tx.category = proposal.category
    tx.description = proposal.description
    tx.user_request = user_request
    tx.scenario = scenario
    tx.intent = intent.model_dump(mode="json") if intent else None
    tx.status = TransactionStatus.PROPOSED
    tx.approval_status = ApprovalStatus.NOT_REQUIRED
    tx.decision_reasons = []
    db.flush()

    token = trace_id_var.set(tx.trace_id)
    rec = recorder or Recorder(db, tx, now)
    try:
        if recorder is None:
            rec.emit(
                EventType.TRANSACTION_PROPOSED,
                "agent",
                "info",
                f"{agent.name} proposed {fmt(proposal.amount, proposal.currency)} at {merchant.name}",
                actor=agent.name,
                metadata={"description": proposal.description, "category": proposal.category},
            )

        mprof = merchant_profile(merchant, now)
        rec.emit(
            EventType.MERCHANT_ANALYZED,
            "agent",
            "pass" if mprof.trust_score >= 70 and mprof.verification_status == VerificationStatus.VERIFIED else "warn",
            f"Merchant trust evaluated: {merchant.name} · trust {mprof.trust_score} · {mprof.verification_status.value.lower()}",
            metadata=mprof.model_dump(mode="json"),
        )

        if policy_row is None:
            return _finish_blocked(db, tx, rec, decision_engine.fail_closed("policy", "Agent has no financial policy"), now)
        spec = policy_spec(policy_row)
        spending = spending_context(db, agent.id, spec.currency, now, exclude_tx=tx.id)

        # ---- AgentShield
        tx.status = TransactionStatus.RISK_REVIEW
        shield: ShieldResult | None
        try:
            shield = agent_shield.scan(proposal.external_content, intent_budget=proposal.intent_budget)
        except Exception as exc:  # noqa: BLE001 - any failure must fail closed
            log.exception("AgentShield failed")
            shield = None
            rec.emit(EventType.FAIL_CLOSED, "shield", "fail", f"AgentShield unavailable: {exc}")
        if shield is not None:
            tx.shield_result = shield.model_dump(mode="json")
            if shield.threats:
                top = shield.threats[0]
                rec.emit(
                    EventType.PROMPT_INJECTION_DETECTED,
                    "shield",
                    "fail" if shield.verdict == "BLOCK" else "warn",
                    f"AgentShield: {top.title.upper()} in {top.source} ({shield.severity})",
                    actor="agentshield",
                    metadata=shield.model_dump(mode="json"),
                )
            else:
                rec.emit(
                    EventType.SECURITY_SCANNED,
                    "shield",
                    "pass",
                    f"AgentShield scan clean · {shield.sources_scanned} external source(s) treated as data",
                    actor="agentshield",
                    metadata=shield.model_dump(mode="json"),
                )

        # ---- Risk
        risk: RiskAssessment | None = None
        if shield is not None:
            try:
                if "risk_engine" in faults:
                    raise risk_engine.RiskEngineUnavailable("Risk engine did not respond (simulated outage)")
                risk = risk_engine.assess(proposal, mprof, spending, spec, shield)
            except Exception as exc:  # noqa: BLE001
                log.warning("Risk engine unavailable", extra={"data": {"error": str(exc)}})
                rec.emit(EventType.FAIL_CLOSED, "risk", "fail", f"Risk engine unavailable: {exc}. Failing closed.", actor="risk-engine")
        if risk is not None:
            tx.risk_assessment = risk.model_dump(mode="json")
            tx.risk_score = risk.overall_score
            tx.risk_level = risk.level.value
            rec.emit(
                EventType.RISK_ASSESSED,
                "risk",
                {"LOW": "pass", "MEDIUM": "pass", "HIGH": "warn", "CRITICAL": "fail"}[risk.level.value],
                f"Risk assessment: {risk.level.value} ({risk.overall_score}/100)",
                actor="risk-engine",
                metadata=risk.model_dump(mode="json"),
            )

        # ---- Policy (always deterministic; evaluated even when earlier stages fail, for explainability)
        tx.status = TransactionStatus.POLICY_REVIEW
        policy_result: PolicyResult | None = None
        try:
            policy_result = policy_engine.evaluate_policy(spec, proposal, mprof, spending)
        except Exception as exc:  # noqa: BLE001
            log.exception("Policy engine failed")
            rec.emit(EventType.FAIL_CLOSED, "policy", "fail", f"Policy engine unavailable: {exc}")
        if policy_result is not None:
            tx.policy_result = policy_result.model_dump(mode="json")
            failed = [c.label for c in policy_result.checks if c.status == "fail"]
            rec.emit(
                EventType.POLICY_EVALUATED,
                "policy",
                {"ALLOW": "pass", "DENY": "fail", "HUMAN_APPROVAL_REQUIRED": "warn"}[policy_result.decision.value],
                "Policy evaluation: "
                + {"ALLOW": "PASS", "DENY": "FAIL", "HUMAN_APPROVAL_REQUIRED": "APPROVAL REQUIRED"}[policy_result.decision.value]
                + (f" · {', '.join(failed)}" if failed else ""),
                actor="policy-engine",
                metadata=policy_result.model_dump(mode="json"),
            )

        # ---- Decision
        if risk is None and shield is not None:
            result = decision_engine.fail_closed("risk", "Risk engine unavailable")
        else:
            result = decision_engine.decide(shield, risk, policy_result)
        _record_threats(db, tx, shield, risk, policy_result, result, spec, now)
        return _apply_decision(db, tx, rec, result, now, execute_payment=execute_payment, faults=faults)
    finally:
        trace_id_var.reset(token)


def _record_threats(
    db: Session,
    tx: Transaction,
    shield: ShieldResult | None,
    risk: RiskAssessment | None,
    policy_result: PolicyResult | None,
    result: DecisionResult,
    spec: PolicySpec,
    now: datetime,
) -> None:
    action = {"BLOCK": "BLOCKED", "DENY": "DENIED", "HUMAN_APPROVAL_REQUIRED": "ESCALATED", "ALLOW": "FLAGGED"}[result.decision.value]
    if result.fail_closed:
        _threat(db, tx, ThreatType.SYSTEM_FAILURE, Severity.HIGH, "Fail-closed block", result.reasons[0], "BLOCKED", now)
        return
    if shield and shield.threats:
        top = shield.threats[0]
        _threat(db, tx, ThreatType.PROMPT_INJECTION, shield.severity or Severity.MEDIUM, top.title, top.excerpt, action, now, attempted=tx.amount)
    if policy_result:
        failed = {c.rule: c for c in policy_result.checks if c.status == "fail"}
        spend_rules = {"max_transaction_amount", "daily_spending_limit", "monthly_spending_limit", "intent_budget"}
        if failed.keys() & spend_rules:
            limit = spec.max_transaction_amount if "max_transaction_amount" in failed else None
            _threat(
                db, tx, ThreatType.SPENDING_VIOLATION, Severity.HIGH, "Spending limit exceeded",
                "; ".join(failed[r].detail for r in failed if r in spend_rules), action, now, attempted=tx.amount, limit=limit,
            )
        if failed.keys() & {"minimum_merchant_trust", "allow_new_merchants"}:
            _threat(db, tx, ThreatType.SUSPICIOUS_MERCHANT, Severity.MEDIUM, "Untrusted merchant",
                    "; ".join(failed[r].detail for r in failed if r in {"minimum_merchant_trust", "allow_new_merchants"}), action, now)
        other = failed.keys() - spend_rules - {"minimum_merchant_trust", "allow_new_merchants"}
        if other:
            _threat(db, tx, ThreatType.POLICY_VIOLATION, Severity.MEDIUM, "Policy violation",
                    "; ".join(failed[r].detail for r in other), action, now, attempted=tx.amount)
    if risk and risk.behavior_risk >= 40:
        _threat(db, tx, ThreatType.UNUSUAL_TRANSACTION, Severity.MEDIUM, "Unusual transaction pattern",
                "; ".join(next(f for f in risk.factors if f.key == "behavior").reasons), action, now, attempted=tx.amount)


def _finish_blocked(db: Session, tx: Transaction, rec: Recorder, result: DecisionResult, now: datetime) -> Transaction:
    return _apply_decision(db, tx, rec, result, now, execute_payment=False, faults=set())


def _apply_decision(
    db: Session,
    tx: Transaction,
    rec: Recorder,
    result: DecisionResult,
    now: datetime,
    *,
    execute_payment: bool,
    faults: set[str],
) -> Transaction:
    tx.decision = result.decision.value
    tx.decision_reasons = result.reasons
    tx.decided_at = now
    tx.status = result.status.value

    if result.decision == FinalDecision.BLOCK:
        tx.approval_status = ApprovalStatus.NOT_REQUIRED
        tx.failure_reason = result.reasons[0] if result.fail_closed else None
        rec.emit(
            EventType.TRANSACTION_BLOCKED,
            "approval",
            "fail",
            "Final decision: BLOCKED" + (" (fail closed)" if result.fail_closed else "") + " · no payment attempted",
            metadata=result.model_dump(mode="json"),
        )
    elif result.decision == FinalDecision.DENY:
        tx.approval_status = ApprovalStatus.NOT_REQUIRED
        rec.emit(EventType.TRANSACTION_DENIED, "approval", "fail", "Final decision: DENIED by policy · no payment attempted", metadata=result.model_dump(mode="json"))
    elif result.decision == FinalDecision.HUMAN_APPROVAL_REQUIRED:
        tx.approval_status = ApprovalStatus.PENDING
        tx.autonomous = False
        tx.approval_reason = result.reasons[0] if result.reasons else "Requires human approval"
        rec.emit(EventType.APPROVAL_REQUESTED, "approval", "warn", "Human approval required · payment paused", metadata=result.model_dump(mode="json"))
    else:
        tx.approval_status = ApprovalStatus.NOT_REQUIRED
        tx.autonomous = True
        rec.emit(EventType.DECISION_MADE, "approval", "pass", "Final decision: ALLOW · within autonomous authority", metadata=result.model_dump(mode="json"))
        db.flush()
        if execute_payment:
            start_payment(db, tx, rec, now, faults=faults)
    db.flush()
    return tx


# ---------------------------------------------------------------- payments


def start_payment(db: Session, tx: Transaction, rec: Recorder | None = None, now: datetime | None = None, faults: set[str] | None = None) -> Transaction:
    """Create the PayPal order for an authorized transaction.

    Only transactions in APPROVED status can reach PayPal, so nothing upstream can skip governance.
    With simulated payments, the order is also captured immediately (no buyer step exists).
    """
    if tx.status != TransactionStatus.APPROVED:
        raise TransitionError(f"Transaction {tx.id} is {tx.status}; only APPROVED transactions can be paid")
    now = now or datetime.now(UTC)
    rec = rec or Recorder(db, tx, now)
    settings = get_settings()
    provider = get_payment_provider()
    settle_ccy = settings.paypal_settlement_currency
    settle_amount = convert(tx.amount, tx.currency, settle_ccy)
    tx.settlement_amount = settle_amount
    tx.settlement_currency = settle_ccy
    tx.payment_provider = provider.mode

    if tx.paypal_order_id:
        return tx  # idempotent

    try:
        if faults and "paypal" in faults:
            raise PaymentError("PayPal could not be reached (simulated outage).")
        order = provider.create_order(
            reference_id=tx.id, trace_id=tx.trace_id, description=tx.description, amount=settle_amount, currency=settle_ccy
        )
    except PaymentError as exc:
        tx.failure_reason = f"{exc} No money was moved."
        if not exc.retryable:
            tx.status = TransactionStatus.FAILED
        rec.emit(EventType.PAYMENT_FAILED, "paypal", "fail", f"Payment provider error: {exc} No money was moved.", actor=provider.mode)
        db.flush()
        return tx

    tx.paypal_order_id = order.order_id
    tx.paypal_status = order.status
    tx.paypal_approve_url = order.approve_url
    tx.status = TransactionStatus.PAYMENT_CREATED
    tx.failure_reason = None
    label = "Simulated order" if order.simulated else "PayPal order"
    fx = f" ({fmt(settle_amount, settle_ccy)} settlement)" if settle_ccy != tx.currency else ""
    rec.emit(
        EventType.PAYPAL_ORDER_CREATED,
        "paypal",
        "pass",
        f"{label} created · {order.order_id}{fx}",
        actor=provider.mode,
        metadata={"order_id": order.order_id, "status": order.status, "simulated": order.simulated, "approve_url": order.approve_url,
                  "settlement_amount": float(settle_amount), "settlement_currency": settle_ccy},
    )
    db.flush()
    if order.simulated:
        capture_payment(db, tx, order.order_id, rec=rec, now=rec.clock)
    return tx


def capture_payment(db: Session, tx: Transaction, order_id: str, rec: Recorder | None = None, now: datetime | None = None) -> Transaction:
    if tx.status == TransactionStatus.COMPLETED and tx.paypal_order_id == order_id:
        return tx  # duplicate capture is a no-op
    if tx.status != TransactionStatus.PAYMENT_CREATED:
        raise TransitionError(f"Transaction {tx.id} is {tx.status}; nothing to capture")
    if tx.paypal_order_id != order_id:
        raise TransitionError("Order id does not belong to this transaction")
    now = now or datetime.now(UTC)
    rec = rec or Recorder(db, tx, now)
    provider = get_payment_provider()
    token = trace_id_var.set(tx.trace_id)
    try:
        try:
            result = provider.capture_order(order_id, idempotency_key=f"{tx.id}-capture")
        except PaymentError as exc:
            not_approved = isinstance(exc.details, dict) and "ORDER_NOT_APPROVED" in str(exc.details)
            tx.failure_reason = "The buyer has not approved this PayPal order yet." if not_approved else f"{exc} No money was moved."
            if not exc.retryable and not not_approved:
                tx.status = TransactionStatus.FAILED
            rec.emit(EventType.PAYMENT_FAILED, "paypal", "fail", f"Capture failed: {tx.failure_reason}", actor=provider.mode)
            db.flush()
            return tx

        tx.paypal_status = result.status
        tx.paypal_capture_id = result.capture_id
        if result.status == "COMPLETED":
            tx.status = TransactionStatus.COMPLETED
            tx.completed_at = rec.clock
            tx.failure_reason = None
            label = "Simulated payment captured" if result.simulated else "PayPal payment captured"
            rec.emit(EventType.PAYPAL_PAYMENT_CAPTURED, "paypal", "pass", f"{label} · {result.capture_id}", actor=provider.mode,
                     metadata={"capture_id": result.capture_id, "status": result.status, "simulated": result.simulated})
            rec.emit(EventType.TRANSACTION_COMPLETED, "complete", "pass", f"Payment completed · {fmt(tx.amount, tx.currency)} to {tx.merchant.name if tx.merchant else 'merchant'}")
        else:
            tx.failure_reason = f"PayPal capture returned status {result.status}"
            rec.emit(EventType.PAYMENT_FAILED, "paypal", "warn", tx.failure_reason, actor=provider.mode)
        db.flush()
        return tx
    finally:
        trace_id_var.reset(token)


# ---------------------------------------------------------------- human approval


def approve(db: Session, tx: Transaction, actor: str, note: str | None = None) -> Transaction:
    if tx.approval_status != ApprovalStatus.PENDING or tx.status != TransactionStatus.AWAITING_APPROVAL:
        raise TransitionError(f"Transaction {tx.id} is not awaiting approval (status {tx.status})")
    now = datetime.now(UTC)
    rec = Recorder(db, tx, max(now, _last_event_time(db, tx) + timedelta(milliseconds=1)))
    token = trace_id_var.set(tx.trace_id)
    try:
        # Re-verify hard policy rules at execution time: limits may have been consumed or
        # the policy tightened while the request sat in the inbox.
        agent = db.get(Agent, tx.agent_id)
        merchant = db.get(Merchant, tx.merchant_id) if tx.merchant_id else None
        policy_row = db.get(FinancialPolicy, agent.policy_id) if agent and agent.policy_id else None
        if agent and merchant and policy_row:
            spec = policy_spec(policy_row)
            proposal = TransactionProposal(
                agent_id=agent.id, merchant_id=merchant.id, amount=tx.amount, currency=tx.currency,
                category=tx.category, description=tx.description,
                intent_budget=Decimal(str(tx.intent["max_budget"])) if tx.intent and tx.intent.get("max_budget") else None,
            )
            recheck = policy_engine.evaluate_policy(spec, proposal, merchant_profile(merchant, now), spending_context(db, agent.id, spec.currency, now, exclude_tx=tx.id))
            if recheck.decision == Decision.DENY:
                tx.status = TransactionStatus.DENIED
                tx.approval_status = ApprovalStatus.DENIED
                tx.decision = FinalDecision.DENY.value
                tx.decision_reasons = [f"Policy re-check at approval time: {r}" for r in recheck.reasons]
                rec.emit(EventType.TRANSACTION_DENIED, "approval", "fail", "Approval rejected: policy no longer permits this payment", actor="policy-engine",
                         metadata=recheck.model_dump(mode="json"))
                db.flush()
                return tx

        tx.approval_status = ApprovalStatus.APPROVED
        tx.approved_by = actor
        tx.status = TransactionStatus.APPROVED
        tx.decision = FinalDecision.ALLOW.value
        rec.emit(EventType.APPROVED, "approval", "pass", f"Approved by {actor}" + (f": {note}" if note else ""), actor=actor)
        db.flush()
        return start_payment(db, tx, rec, now=rec.clock)
    finally:
        trace_id_var.reset(token)


def deny(db: Session, tx: Transaction, actor: str, note: str | None = None) -> Transaction:
    if tx.approval_status != ApprovalStatus.PENDING or tx.status != TransactionStatus.AWAITING_APPROVAL:
        raise TransitionError(f"Transaction {tx.id} is not awaiting approval (status {tx.status})")
    now = datetime.now(UTC)
    rec = Recorder(db, tx, max(now, _last_event_time(db, tx) + timedelta(milliseconds=1)))
    tx.approval_status = ApprovalStatus.DENIED
    tx.approved_by = actor
    tx.status = TransactionStatus.DENIED
    tx.decision = FinalDecision.DENY.value
    tx.decision_reasons = [f"Denied by {actor}" + (f": {note}" if note else "")]
    rec.emit(EventType.DENIED, "approval", "fail", f"Denied by {actor}" + (f": {note}" if note else "") + " · no payment attempted", actor=actor)
    db.flush()
    return tx


def _last_event_time(db: Session, tx: Transaction) -> datetime:
    ts = db.scalar(select(func.max(AuditEvent.timestamp)).where(AuditEvent.transaction_id == tx.id))
    return as_utc(ts) if ts else as_utc(tx.created_at)


# ---------------------------------------------------------------- agents


def _rank(offer: catalog.Offer, merchant: Merchant, budget: Decimal | None) -> float:
    price_factor = float(offer.price / budget) if budget else 0.5
    return merchant.trust_score * 0.5 + offer.rating * 10 - price_factor * 10


def run_agent(
    db: Session,
    agent: Agent,
    request_text: str,
    *,
    faults: set[str] | None = None,
    scenario: str | None = None,
    now: datetime | None = None,
    default_currency: str = "INR",
) -> Transaction:
    """Full agent flow: understand the request, search, propose, then hand to governance."""
    faults = faults or set()
    now = now or datetime.now(UTC)
    tx = Transaction(id=new_tx_id(), trace_id=new_trace_id(), created_at=now, agent_id=agent.id, amount=Decimal("0"),
                     currency=default_currency, category="unknown", description="Evaluating request", user_request=request_text,
                     scenario=scenario, status=TransactionStatus.PROPOSED, approval_status=ApprovalStatus.NOT_REQUIRED)
    db.add(tx)
    db.flush()
    rec = Recorder(db, tx, now)
    token = trace_id_var.set(tx.trace_id)
    try:
        # ---- Intent
        try:
            if "ai_service" in faults:
                raise LLMUnavailable("AI service did not respond (simulated outage)")
            intent = extract_intent(request_text, default_currency)
        except LLMUnavailable as exc:
            rec.emit(EventType.FAIL_CLOSED, "intent", "fail", f"AI service unavailable: {exc}. Failing closed.", actor="intent-engine")
            tx.description = "Request could not be safely interpreted"
            result = decision_engine.fail_closed("intent", "AI service unavailable")
            _threat(db, tx, ThreatType.SYSTEM_FAILURE, Severity.HIGH, "Fail-closed block", result.reasons[0], "BLOCKED", now)
            return _finish_blocked(db, tx, rec, result, now)

        tx.intent = intent.model_dump(mode="json")
        budget_txt = f" · budget {fmt(intent.max_budget, intent.currency)}" if intent.max_budget else ""
        rec.emit(
            EventType.INTENT_RECEIVED,
            "intent",
            "pass",
            f"Intent understood: {intent.category or 'general'} purchase{budget_txt}"
            + (f" · {intent.location}" if intent.location else ""),
            actor="intent-engine",
            metadata={**intent.model_dump(mode="json"), "method": "LLM structured extraction" if intent.source == "llm" else "Deterministic rule parser"},
        )

        # ---- Agent search + proposal
        rec.emit(EventType.AGENT_STARTED, "agent", "info", f"{agent.name} started · searching demo catalog", actor=agent.name)
        offers = catalog.search(intent.category, intent.location, intent.max_budget)
        merchants = {m.id: m for m in db.scalars(select(Merchant).where(Merchant.id.in_({o.merchant_id for o in offers}))).all()}
        candidates = [o for o in offers if o.merchant_id in merchants]
        if intent.avoid_suspicious_merchants:
            candidates = [o for o in candidates if merchants[o.merchant_id].trust_score >= 80] or candidates
        if not candidates:
            tx.description = "No matching offers found"
            rec.emit(EventType.MERCHANT_FOUND, "agent", "fail", "No matching offers found; nothing to purchase", actor=agent.name)
            tx.status = TransactionStatus.FAILED
            tx.failure_reason = "The agent could not find an offer matching this request."
            db.flush()
            return tx
        chosen = max(candidates, key=lambda o: _rank(o, merchants[o.merchant_id], intent.max_budget))
        m = merchants[chosen.merchant_id]
        rec.emit(
            EventType.MERCHANT_FOUND,
            "agent",
            "pass",
            f"Merchant discovered: {chosen.title} via {m.name} · {fmt(chosen.price, chosen.currency)}",
            actor=agent.name,
            metadata={
                "considered": [
                    {"title": o.title, "merchant": merchants[o.merchant_id].name, "price": float(o.price), "trust": merchants[o.merchant_id].trust_score}
                    for o in candidates
                ],
                "selected": chosen.model_dump(mode="json"),
                "method": "Deterministic ranking (trust, rating, price vs budget)",
            },
        )
        proposal = TransactionProposal(
            agent_id=agent.id,
            merchant_id=chosen.merchant_id,
            amount=chosen.price,
            currency=chosen.currency,
            category=chosen.category,
            description=f"{chosen.title} · {chosen.subtitle}",
            intent_budget=intent.max_budget,
            external_content=[UntrustedContent(source=chosen.page_url, content=chosen.page_content)],
        )
        rec.emit(
            EventType.TRANSACTION_PROPOSED,
            "agent",
            "info",
            f"{agent.name} proposed {fmt(proposal.amount, proposal.currency)} at {m.name}",
            actor=agent.name,
            metadata={"description": proposal.description},
        )
        return govern(db, agent, proposal, user_request=request_text, intent=intent, scenario=scenario, faults=faults,
                      now=now, tx=tx, recorder=rec)
    finally:
        trace_id_var.reset(token)
