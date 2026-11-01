"""Deterministic Policy Engine.

Pure function of (policy, proposal, merchant, spending). No I/O, no LLM. The same input
always produces the same decision, which is what makes it auditable.
"""

from __future__ import annotations

from decimal import Decimal

from app.core.enums import Decision
from app.core.money import convert
from app.schemas.domain import (
    MerchantProfile,
    PolicyResult,
    PolicySpec,
    RuleCheck,
    SpendingContext,
    TransactionProposal,
)

NEW_MERCHANT_DAYS = 30


def fmt(amount: Decimal, currency: str) -> str:
    symbol = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}.get(currency, f"{currency} ")
    if currency == "INR":
        # Indian digit grouping: 1,20,000
        whole = int(amount)
        s = str(whole)
        if len(s) > 3:
            head, tail = s[:-3], s[-3:]
            groups = []
            while len(head) > 2:
                groups.insert(0, head[-2:])
                head = head[:-2]
            if head:
                groups.insert(0, head)
            s = ",".join(groups) + "," + tail
        cents = amount - whole
        return f"{symbol}{s}" + (f"{cents:.2f}"[1:] if cents else "")
    return f"{symbol}{amount:,.2f}".replace(".00", "")


def evaluate_policy(
    policy: PolicySpec,
    proposal: TransactionProposal,
    merchant: MerchantProfile,
    spending: SpendingContext,
) -> PolicyResult:
    ccy = policy.currency
    amount = convert(proposal.amount, proposal.currency, ccy)
    checks: list[RuleCheck] = []

    def add(rule: str, label: str, ok: bool, detail: str, actual: str | None = None, limit: str | None = None) -> None:
        checks.append(RuleCheck(rule=rule, label=label, status="pass" if ok else "fail", detail=detail, actual=actual, limit=limit))

    # 1. Blocked categories always deny.
    blocked = proposal.category in policy.blocked_categories
    add(
        "blocked_category",
        "Category not blocked",
        not blocked,
        f"'{proposal.category}' is on the blocked list" if blocked else f"'{proposal.category}' is not blocked",
        actual=proposal.category,
    )

    # 2. Allowed categories (empty list means any non-blocked category).
    if policy.allowed_categories:
        allowed = proposal.category in policy.allowed_categories
        add(
            "category_allowed",
            "Category allowed",
            allowed,
            f"'{proposal.category}' is permitted" if allowed else f"'{proposal.category}' is outside this agent's allowed categories",
            actual=proposal.category,
            limit=", ".join(policy.allowed_categories),
        )
    else:
        checks.append(RuleCheck(rule="category_allowed", label="Category allowed", status="skip", detail="No category allow-list configured"))

    # 3. Per-transaction maximum.
    ok = amount <= policy.max_transaction_amount
    add(
        "max_transaction_amount",
        "Amount within maximum",
        ok,
        "Within per-transaction maximum" if ok else "Exceeds per-transaction maximum",
        actual=fmt(amount, ccy),
        limit=fmt(policy.max_transaction_amount, ccy),
    )

    # 4. Daily and monthly limits include already-committed spend.
    daily_after = spending.daily_total + amount
    ok = daily_after <= policy.daily_spending_limit
    add(
        "daily_spending_limit",
        "Daily limit",
        ok,
        f"{fmt(daily_after, ccy)} of {fmt(policy.daily_spending_limit, ccy)} used after this payment"
        if ok
        else f"Would bring today's spend to {fmt(daily_after, ccy)}",
        actual=fmt(daily_after, ccy),
        limit=fmt(policy.daily_spending_limit, ccy),
    )
    monthly_after = spending.monthly_total + amount
    ok = monthly_after <= policy.monthly_spending_limit
    add(
        "monthly_spending_limit",
        "Monthly limit",
        ok,
        "Within monthly budget" if ok else f"Would bring this month's spend to {fmt(monthly_after, ccy)}",
        actual=fmt(monthly_after, ccy),
        limit=fmt(policy.monthly_spending_limit, ccy),
    )

    # 5. Merchant trust.
    ok = merchant.trust_score >= policy.minimum_merchant_trust
    add(
        "minimum_merchant_trust",
        "Merchant trusted",
        ok,
        f"{merchant.name} trust {merchant.trust_score} meets minimum" if ok else f"{merchant.name} trust {merchant.trust_score} is below minimum",
        actual=str(merchant.trust_score),
        limit=f">= {policy.minimum_merchant_trust}",
    )

    # 6. New merchants.
    is_new = merchant.age_days < NEW_MERCHANT_DAYS
    if is_new:
        add(
            "allow_new_merchants",
            "New merchant",
            policy.allow_new_merchants,
            f"Merchant onboarded {merchant.age_days} days ago; " + ("new merchants allowed" if policy.allow_new_merchants else "new merchants are not allowed"),
            actual=f"{merchant.age_days} days",
            limit=f">= {NEW_MERCHANT_DAYS} days",
        )
    else:
        checks.append(RuleCheck(rule="allow_new_merchants", label="New merchant", status="pass", detail=f"Established merchant ({merchant.age_days} days)"))

    # 7. International.
    international = merchant.country != policy.home_country
    if international:
        add(
            "allow_international",
            "International",
            policy.allow_international,
            f"Merchant is in {merchant.country}; " + ("international allowed" if policy.allow_international else "international payments are not allowed"),
            actual=merchant.country,
            limit=policy.home_country,
        )
    else:
        checks.append(RuleCheck(rule="allow_international", label="International", status="pass", detail="Domestic merchant"))

    # 8. The user's own stated budget for this request is a policy too.
    if proposal.intent_budget is not None:
        budget = convert(proposal.intent_budget, proposal.currency, ccy)
        ok = amount <= budget
        add(
            "intent_budget",
            "Matches user's budget",
            ok,
            "Within the budget the user stated" if ok else "Exceeds the budget the user stated in their request",
            actual=fmt(amount, ccy),
            limit=fmt(budget, ccy),
        )

    failed = [c for c in checks if c.status == "fail"]
    approval_required = amount > policy.require_approval_above

    if failed:
        decision = Decision.DENY
    elif approval_required:
        decision = Decision.HUMAN_APPROVAL_REQUIRED
        checks.append(
            RuleCheck(
                rule="require_approval_above",
                label="Approval required",
                status="warn",
                detail="Exceeds the agent's autonomous spending limit",
                actual=fmt(amount, ccy),
                limit=fmt(policy.require_approval_above, ccy),
            )
        )
    else:
        decision = Decision.ALLOW
        checks.append(
            RuleCheck(
                rule="require_approval_above",
                label="Autonomous limit",
                status="pass",
                detail="Within the agent's autonomous spending limit",
                actual=fmt(amount, ccy),
                limit=fmt(policy.require_approval_above, ccy),
            )
        )

    reasons = [f"{c.label}: {c.detail}" for c in failed]
    if decision == Decision.HUMAN_APPROVAL_REQUIRED:
        reasons.append(
            f"Amount {fmt(amount, ccy)} exceeds autonomous limit {fmt(policy.require_approval_above, ccy)}"
        )

    return PolicyResult(
        decision=decision,
        reasons=reasons,
        failed_rules=[c.rule for c in failed],
        approval_required=approval_required and not failed,
        checks=checks,
        evaluated_amount=amount,
        policy_currency=ccy,
    )
