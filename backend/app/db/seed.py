"""Migrate and seed the database with a realistic, deterministic dataset.

    python -m app.db.seed           # migrate + seed if empty
    python -m app.db.seed --reset   # wipe and re-seed

Historical transactions are produced by running the real governance engines with past
timestamps, so every seeded decision is one PayPilot would actually make. Historical
payments are marked `payment_provider="seed"`; they never claim to be PayPal payments.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.enums import ApprovalStatus, EventType, TransactionStatus
from app.db.models import Agent, AuditEvent, FinancialPolicy, Merchant, ThreatEvent, Transaction, User
from app.db.session import SessionLocal
from app.schemas.domain import TransactionProposal, UntrustedContent
from app.services import catalog
from app.services.orchestrator import Recorder, govern

USER_ID = "usr_demo"


def _merchants(now: datetime) -> list[Merchant]:
    def m(id: str, name: str, domain: str, trust: int, risk: int, status: str, cats: list[str], refund: str, cb: str, age: int, country: str = "IN") -> Merchant:
        return Merchant(id=id, name=name, domain=domain, trust_score=trust, risk_score=risk, verification_status=status, categories=cats,
                        refund_rate=Decimal(refund), chargeback_rate=Decimal(cb), onboarded_at=now - timedelta(days=age), country=country,
                        created_at=now - timedelta(days=age))

    return [
        m("mer_booking", "Booking.com", "booking.com", 96, 6, "VERIFIED", ["travel"], "0.031", "0.0040", 2400),
        m("mer_amazon", "Amazon", "amazon.in", 94, 8, "VERIFIED", ["electronics", "office_supplies", "gift_cards"], "0.042", "0.0050", 3100),
        m("mer_saas", "Verified SaaS Vendor", "verifiedsaas.io", 92, 9, "VERIFIED", ["saas", "software", "cloud"], "0.012", "0.0020", 900),
        m("mer_skyline", "Skyline Stays", "skylinestays.in", 88, 14, "VERIFIED", ["travel"], "0.048", "0.0060", 720),
        m("mer_northwind", "Northwind Electronics", "northwind.in", 81, 19, "VERIFIED", ["electronics"], "0.061", "0.0090", 410),
        m("mer_example_travel", "Example Travel", "example-travel.com", 38, 78, "UNVERIFIED", ["travel"], "0.180", "0.0350", 19),
        m("mer_unknown", "Unknown Vendor", "unknown-vendor.biz", 31, 86, "FLAGGED", ["saas", "electronics"], "0.220", "0.0410", 12, "SG"),
    ]


def _policies(now: datetime) -> list[FinancialPolicy]:
    created = now - timedelta(days=30)
    return [
        FinancialPolicy(
            id="pol_travel", agent_id="agt_travel", name="Travel policy", currency="INR",
            max_transaction_amount=Decimal("20000"), daily_spending_limit=Decimal("40000"), monthly_spending_limit=Decimal("150000"),
            allowed_categories=["travel"], blocked_categories=["gift_cards", "crypto", "gambling"], minimum_merchant_trust=75,
            require_approval_above=Decimal("15000"), allow_new_merchants=False, allow_international=False, auto_refund_enabled=True,
            source_text="Hotels and travel only, up to ₹20,000 per booking. Anything above ₹15,000 needs my approval. Never use suspicious merchants.",
            created_at=created, updated_at=created,
        ),
        FinancialPolicy(
            id="pol_shopping", agent_id="agt_shopping", name="Shopping policy", currency="INR",
            max_transaction_amount=Decimal("150000"), daily_spending_limit=Decimal("150000"), monthly_spending_limit=Decimal("400000"),
            allowed_categories=["electronics", "office_supplies"], blocked_categories=["gift_cards", "crypto", "gambling"], minimum_merchant_trust=70,
            require_approval_above=Decimal("50000"), allow_new_merchants=False, allow_international=False, auto_refund_enabled=True,
            source_text="Electronics and office supplies. Up to ₹1.5 lakh per purchase, anything above ₹50,000 needs my approval. Never buy gift cards.",
            created_at=created, updated_at=created,
        ),
        FinancialPolicy(
            id="pol_business", agent_id="agt_business", name="Business policy", currency="INR",
            max_transaction_amount=Decimal("100000"), daily_spending_limit=Decimal("100000"), monthly_spending_limit=Decimal("500000"),
            allowed_categories=["saas", "software", "cloud", "office_supplies"], blocked_categories=["gift_cards", "crypto", "gambling"],
            minimum_merchant_trust=75, require_approval_above=Decimal("50000"), allow_new_merchants=False, allow_international=True,
            auto_refund_enabled=False,
            source_text="Pay verified software vendors up to ₹1 lakh. Anything above ₹50,000 needs my approval.",
            created_at=created, updated_at=created,
        ),
    ]


def _agents(now: datetime) -> list[Agent]:
    created = now - timedelta(days=30)
    return [
        Agent(id="agt_travel", user_id=USER_ID, name="Travel Agent", type="travel", status="ACTIVE", policy_id="pol_travel", created_at=created,
              description="Finds and books hotels and travel within your budget."),
        Agent(id="agt_shopping", user_id=USER_ID, name="Shopping Agent", type="shopping", status="ACTIVE", policy_id="pol_shopping",
              created_at=created + timedelta(minutes=1), description="Researches and buys electronics and office equipment."),
        Agent(id="agt_business", user_id=USER_ID, name="Business Agent", type="business", status="ACTIVE", policy_id="pol_business",
              created_at=created + timedelta(minutes=2), description="Pays SaaS vendors and recurring business invoices."),
    ]


@dataclass
class SeedTx:
    days_ago: int
    hour: int
    agent: str
    merchant: str
    amount: int
    category: str
    description: str
    request: str | None = None
    budget: int | None = None
    content: str | None = None
    then: str | None = None  # "approve" | "deny" | "fail" for post-decision outcomes
    extra: dict[str, str] = field(default_factory=dict)


ORCHID_PAGE = catalog.OFFERS_BY_ID["off_orchid_bangalore"].page_content
UNKNOWN_PAGE = catalog.OFFERS_BY_ID["off_unknown_license"].page_content

HISTORY: list[SeedTx] = [
    SeedTx(13, 10, "agt_travel", "mer_booking", 7900, "travel", "Lumen Suites, Pune · 1 night", "Book a hotel in Pune under ₹10,000", 10000),
    SeedTx(13, 15, "agt_business", "mer_saas", 25000, "saas", "Analytics Team Plan · monthly renewal"),
    SeedTx(12, 11, "agt_shopping", "mer_amazon", 3499, "electronics", "Mechanical keyboard · TKL"),
    SeedTx(11, 9, "agt_travel", "mer_booking", 12450, "travel", "Seaview Resort, Goa · 1 night", "Find a resort in Goa under ₹15,000", 15000),
    SeedTx(10, 14, "agt_shopping", "mer_northwind", 24999, "electronics", "27\" 4K monitor"),
    SeedTx(10, 16, "agt_business", "mer_saas", 18000, "saas", "Error monitoring · annual seats"),
    SeedTx(9, 12, "agt_travel", "mer_skyline", 9400, "travel", "Skyline Stays, Koramangala · 1 night", "Book a stay in Bangalore under ₹10,000", 10000),
    SeedTx(9, 17, "agt_business", "mer_unknown", 19000, "saas", "Enterprise Analytics License", "Buy an analytics license", None, UNKNOWN_PAGE),
    SeedTx(8, 10, "agt_shopping", "mer_amazon", 92000, "electronics", "MacBook Pro 14\" · M4 Pro", "Get me a MacBook Pro", None, None, "deny"),
    SeedTx(7, 9, "agt_travel", "mer_booking", 4200, "travel", "Airport hotel, Delhi · 1 night"),
    SeedTx(7, 13, "agt_business", "mer_saas", 64000, "saas", "Data warehouse credits · annual", None, None, None, "approve"),
    SeedTx(6, 11, "agt_travel", "mer_example_travel", 35000, "travel", "Orchid Bay Residency · Premium package", "Book me a hotel in Bangalore under ₹10,000.", 10000, ORCHID_PAGE),
    SeedTx(6, 15, "agt_shopping", "mer_amazon", 10000, "gift_cards", "Amazon Pay Gift Card", "Buy a ₹10,000 gift card"),
    SeedTx(5, 10, "agt_travel", "mer_booking", 18500, "travel", "The Leela Palace, Chennai · 1 night", None, None, None, "approve"),
    SeedTx(5, 14, "agt_business", "mer_saas", 8500, "saas", "Design tool · 5 seats"),
    SeedTx(4, 12, "agt_shopping", "mer_unknown", 8000, "electronics", "Wireless earbuds (bulk)", "Buy cheap earbuds"),
    SeedTx(4, 16, "agt_shopping", "mer_amazon", 6799, "office_supplies", "Ergonomic office chair"),
    SeedTx(3, 9, "agt_travel", "mer_booking", 5600, "travel", "Business hotel, Hyderabad · 1 night"),
    SeedTx(3, 11, "agt_business", "mer_saas", 25000, "saas", "Analytics Team Plan · monthly renewal"),
    SeedTx(2, 10, "agt_travel", "mer_booking", 22000, "travel", "Taj West End, Bangalore · 1 night", "Book the Taj in Bangalore"),
    SeedTx(2, 13, "agt_shopping", "mer_amazon", 2150, "electronics", "USB-C hub · 8-in-1"),
    SeedTx(2, 17, "agt_business", "mer_unknown", 45000, "saas", "CRM migration services"),
    SeedTx(1, 11, "agt_shopping", "mer_northwind", 12450, "electronics", "Noise-cancelling headphones", None, None, None, "fail"),
    SeedTx(1, 15, "agt_shopping", "mer_amazon", 120000, "electronics", "MacBook Pro 16\" · M4 Max", "Buy a MacBook Pro 16 for video editing"),
    SeedTx(0, 1, "agt_travel", "mer_skyline", 16800, "travel", "Skyline Stays, Whitefield · 2 nights", "Book 2 nights in Whitefield"),
    SeedTx(0, 2, "agt_business", "mer_saas", 75000, "saas", "Platform plan · annual prepay", "Pay the annual platform invoice"),
]


def _complete(db: Session, tx: Transaction, rec: Recorder, *, approved_by: str | None = None) -> None:
    if approved_by:
        tx.approval_status = ApprovalStatus.APPROVED
        tx.approved_by = approved_by
        tx.decision = "ALLOW"
        rec.clock += timedelta(minutes=14)
        rec.emit(EventType.APPROVED, "approval", "pass", f"Approved by {approved_by}", actor=approved_by)
    tx.status = TransactionStatus.COMPLETED
    tx.payment_provider = "seed"
    tx.settlement_currency = tx.currency
    tx.settlement_amount = tx.amount
    rec.clock += timedelta(seconds=3)
    tx.completed_at = rec.clock
    rec.emit(EventType.TRANSACTION_COMPLETED, "complete", "pass", "Historical seed transaction · completed (no live payment provider involved)")


def seed(db: Session, reset: bool = False) -> None:
    if reset:
        for model in (AuditEvent, ThreatEvent, Transaction, Agent, FinancialPolicy, Merchant, User):
            db.execute(delete(model))
        db.commit()
    elif db.scalar(select(User).limit(1)) is not None:
        print("Database already seeded; use --reset to re-seed.")
        return

    now = datetime.now(UTC)
    db.add(User(id=USER_ID, name="Demo User", email="demo@paypilot.dev", currency="INR", country="IN", created_at=now - timedelta(days=30)))
    db.flush()
    db.add_all(_merchants(now))
    db.add_all(_policies(now))
    db.add_all(_agents(now))
    db.flush()

    agents = {a.id: a for a in db.scalars(select(Agent)).all()}
    today = now.replace(minute=0, second=0, microsecond=0)
    for s in HISTORY:
        when = (today - timedelta(days=s.days_ago)).replace(hour=s.hour)
        if when > now:
            when = now - timedelta(minutes=30 * (s.hour + 1))
        content = [UntrustedContent(source=f"https://{s.merchant.removeprefix('mer_')}.example/listing", content=s.content)] if s.content else []
        proposal = TransactionProposal(
            agent_id=s.agent, merchant_id=s.merchant, amount=Decimal(s.amount), currency="INR", category=s.category,
            description=s.description, intent_budget=Decimal(s.budget) if s.budget else None, external_content=content,
        )
        tx = govern(db, agents[s.agent], proposal, user_request=s.request, now=when, execute_payment=False)
        rec = Recorder(db, tx, when + timedelta(seconds=2))
        if tx.status == TransactionStatus.APPROVED:
            if s.then == "fail":
                tx.status = TransactionStatus.FAILED
                tx.payment_provider = "seed"
                tx.failure_reason = "Payment provider declined the instrument (seed data). No money was moved."
                rec.emit(EventType.PAYMENT_FAILED, "paypal", "fail", "Payment failed: instrument declined (seed data). No money was moved.")
            else:
                _complete(db, tx, rec)
        elif tx.status == TransactionStatus.AWAITING_APPROVAL and s.then == "approve":
            _complete(db, tx, rec, approved_by="Demo User")
        elif tx.status == TransactionStatus.AWAITING_APPROVAL and s.then == "deny":
            rec.clock += timedelta(minutes=9)
            tx.status = TransactionStatus.DENIED
            tx.approval_status = ApprovalStatus.DENIED
            tx.approved_by = "Demo User"
            tx.decision = "DENY"
            tx.decision_reasons = ["Denied by Demo User: not needed this quarter"]
            rec.emit(EventType.DENIED, "approval", "fail", "Denied by Demo User: not needed this quarter · no payment attempted", actor="Demo User")
        db.flush()
    db.commit()
    counts = {st: 0 for st in TransactionStatus}
    for t in db.scalars(select(Transaction)).all():
        counts[TransactionStatus(t.status)] += 1
    print("Seeded:", {k.value: v for k, v in counts.items() if v})


def migrate() -> None:
    from alembic import command
    from alembic.config import Config

    backend = Path(__file__).resolve().parents[2]
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "alembic"))
    command.upgrade(cfg, "head")


def main() -> None:
    migrate()
    with SessionLocal() as db:
        seed(db, reset="--reset" in sys.argv)


if __name__ == "__main__":
    main()
