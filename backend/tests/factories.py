from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.enums import VerificationStatus
from app.schemas.domain import MerchantProfile, PolicySpec, SpendingContext, TransactionProposal, UntrustedContent


def policy(**kw: Any) -> PolicySpec:
    base: dict[str, Any] = dict(
        currency="INR",
        max_transaction_amount=Decimal("20000"),
        daily_spending_limit=Decimal("40000"),
        monthly_spending_limit=Decimal("150000"),
        require_approval_above=Decimal("10000"),
        minimum_merchant_trust=80,
        allowed_categories=["travel", "electronics"],
        blocked_categories=["gift_cards", "crypto"],
        allow_new_merchants=False,
        allow_international=False,
    )
    base.update(kw)
    return PolicySpec(**base)


def merchant(**kw: Any) -> MerchantProfile:
    base: dict[str, Any] = dict(
        id="mer_test",
        name="Test Hotels",
        domain="test.example",
        country="IN",
        trust_score=95,
        verification_status=VerificationStatus.VERIFIED,
        refund_rate=0.02,
        chargeback_rate=0.003,
        age_days=900,
    )
    base.update(kw)
    return MerchantProfile(**base)


def proposal(amount: int | str = 7900, content: str | None = None, **kw: Any) -> TransactionProposal:
    base: dict[str, Any] = dict(
        agent_id="agt_test",
        merchant_id="mer_test",
        amount=Decimal(str(amount)),
        currency="INR",
        category="travel",
        description="Hotel",
        external_content=[UntrustedContent(source="https://merchant.example", content=content)] if content else [],
    )
    base.update(kw)
    return TransactionProposal(**base)


def spending(**kw: Any) -> SpendingContext:
    return SpendingContext(**kw)
