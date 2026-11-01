"""SQLAlchemy ORM models. Portable across PostgreSQL and SQLite."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_tx_id() -> str:
    return f"PP-{secrets.token_hex(3).upper()}"


def new_trace_id() -> str:
    return f"tr_{secrets.token_hex(5)}"


def new_uuid() -> str:
    return uuid.uuid4().hex


MoneyCol = Numeric(14, 2)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    country: Mapped[str] = mapped_column(String(2), default="IN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FinancialPolicy(Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    # Not a FK: agents and policies reference each other, and SQLite cannot add constraints later.
    agent_id: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    max_transaction_amount: Mapped[Decimal] = mapped_column(MoneyCol)
    daily_spending_limit: Mapped[Decimal] = mapped_column(MoneyCol)
    monthly_spending_limit: Mapped[Decimal] = mapped_column(MoneyCol)
    allowed_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    blocked_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    minimum_merchant_trust: Mapped[int] = mapped_column(Integer, default=70)
    require_approval_above: Mapped[Decimal] = mapped_column(MoneyCol)
    allow_new_merchants: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_international: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_refund_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(40))  # travel | shopping | business
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    description: Mapped[str] = mapped_column(Text)
    policy_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    policy: Mapped[FinancialPolicy | None] = relationship(
        primaryjoin="Agent.policy_id == FinancialPolicy.id", foreign_keys="Agent.policy_id", viewonly=True
    )


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    domain: Mapped[str] = mapped_column(String(200))
    country: Mapped[str] = mapped_column(String(2), default="IN")
    trust_score: Mapped[int] = mapped_column(Integer)
    risk_score: Mapped[int] = mapped_column(Integer)
    verification_status: Mapped[str] = mapped_column(String(20))
    categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    refund_rate: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    chargeback_rate: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    onboarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=new_tx_id)
    trace_id: Mapped[str] = mapped_column(String(20), index=True, default=new_trace_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    merchant_id: Mapped[str | None] = mapped_column(ForeignKey("merchants.id"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(MoneyCol)
    currency: Mapped[str] = mapped_column(String(3))
    category: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    user_request: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenario: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decision_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(12), nullable=True)
    risk_assessment: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    shield_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    policy_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    intent: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(16))
    approval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    autonomous: Mapped[bool] = mapped_column(Boolean, default=True)
    payment_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)  # paypal | simulated
    paypal_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    paypal_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    paypal_capture_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    paypal_approve_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    settlement_amount: Mapped[Decimal | None] = mapped_column(MoneyCol, nullable=True)
    settlement_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agent: Mapped[Agent] = relationship()
    merchant: Mapped[Merchant | None] = relationship()


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    stage: Mapped[str | None] = mapped_column(String(24), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)  # pass | fail | warn | info
    actor: Mapped[str] = mapped_column(String(60))
    message: Mapped[str] = mapped_column(Text)
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    duration_ms: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class ThreatEvent(Base):
    __tablename__ = "threat_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    merchant_id: Mapped[str | None] = mapped_column(ForeignKey("merchants.id"), nullable=True)
    threat_type: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(12))
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(Text)
    attempted_amount: Mapped[Decimal | None] = mapped_column(MoneyCol, nullable=True)
    limit_amount: Mapped[Decimal | None] = mapped_column(MoneyCol, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    action: Mapped[str] = mapped_column(String(16))  # BLOCKED | DENIED | ESCALATED | FLAGGED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    agent: Mapped[Agent | None] = relationship()
    merchant: Mapped[Merchant | None] = relationship()
