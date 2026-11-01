from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.enums import Decision
from app.engines.policy import evaluate_policy, fmt
from tests.factories import merchant, policy, proposal, spending


def failed(result) -> set[str]:  # type: ignore[no-untyped-def]
    return set(result.failed_rules)


def test_allows_transaction_within_all_limits() -> None:
    r = evaluate_policy(policy(), proposal(7900), merchant(), spending())
    assert r.decision == Decision.ALLOW
    assert not r.failed_rules
    assert r.approval_required is False


def test_amount_limit_denies() -> None:
    r = evaluate_policy(policy(), proposal(25000), merchant(), spending())
    assert r.decision == Decision.DENY
    assert "max_transaction_amount" in failed(r)


def test_amount_equal_to_max_is_allowed_but_needs_approval() -> None:
    r = evaluate_policy(policy(), proposal(20000), merchant(), spending())
    assert r.decision == Decision.HUMAN_APPROVAL_REQUIRED


def test_category_outside_allow_list_denies() -> None:
    r = evaluate_policy(policy(), proposal(5000, category="saas"), merchant(), spending())
    assert r.decision == Decision.DENY
    assert failed(r) == {"category_allowed"}


def test_blocked_category_always_denies_even_with_empty_allow_list() -> None:
    r = evaluate_policy(policy(allowed_categories=[]), proposal(500, category="gift_cards"), merchant(), spending())
    assert r.decision == Decision.DENY
    assert "blocked_category" in failed(r)


def test_merchant_trust_below_minimum_denies() -> None:
    r = evaluate_policy(policy(), proposal(5000), merchant(trust_score=62), spending())
    assert failed(r) == {"minimum_merchant_trust"}


def test_daily_limit_includes_already_committed_spend() -> None:
    r = evaluate_policy(policy(), proposal(9000), merchant(), spending(daily_total=Decimal("35000")))
    assert r.decision == Decision.DENY
    assert failed(r) == {"daily_spending_limit"}


def test_monthly_limit() -> None:
    r = evaluate_policy(policy(), proposal(9000), merchant(), spending(monthly_total=Decimal("145000")))
    assert failed(r) == {"monthly_spending_limit"}


def test_approval_threshold() -> None:
    r = evaluate_policy(policy(), proposal(15000), merchant(), spending())
    assert r.decision == Decision.HUMAN_APPROVAL_REQUIRED
    assert r.approval_required is True
    assert any("autonomous limit" in reason for reason in r.reasons)


def test_hard_failure_beats_approval() -> None:
    r = evaluate_policy(policy(), proposal(15000), merchant(trust_score=10), spending())
    assert r.decision == Decision.DENY
    assert r.approval_required is False


def test_international_merchant_denied_when_not_allowed() -> None:
    r = evaluate_policy(policy(), proposal(5000), merchant(country="SG"), spending())
    assert failed(r) == {"allow_international"}


def test_international_merchant_allowed_when_permitted() -> None:
    r = evaluate_policy(policy(allow_international=True), proposal(5000), merchant(country="SG"), spending())
    assert r.decision == Decision.ALLOW


def test_new_merchant_denied_when_not_allowed() -> None:
    r = evaluate_policy(policy(), proposal(5000), merchant(age_days=5), spending())
    assert failed(r) == {"allow_new_merchants"}


def test_intent_budget_is_enforced() -> None:
    r = evaluate_policy(policy(), proposal(9000, intent_budget=Decimal("8000")), merchant(), spending())
    assert failed(r) == {"intent_budget"}


def test_foreign_currency_is_converted_before_comparison() -> None:
    # $300 at 84 INR/USD = ₹25,200 > ₹20,000 maximum
    r = evaluate_policy(policy(), proposal(300, currency="USD"), merchant(), spending())
    assert "max_transaction_amount" in failed(r)
    assert r.evaluated_amount == Decimal("25200.00")


def test_policy_is_deterministic() -> None:
    args = (policy(), proposal(15000), merchant(), spending(daily_total=Decimal("1000")))
    assert evaluate_policy(*args) == evaluate_policy(*args)


@pytest.mark.parametrize(
    "kw",
    [
        {"require_approval_above": Decimal("30000")},  # above max
        {"daily_spending_limit": Decimal("200000")},  # daily > monthly
        {"allowed_categories": ["travel"], "blocked_categories": ["travel"]},
        {"minimum_merchant_trust": 120},
        {"max_transaction_amount": Decimal("-1")},
    ],
)
def test_invalid_policies_are_rejected(kw: dict) -> None:  # type: ignore[type-arg]
    with pytest.raises(ValidationError):
        policy(**kw)


def test_indian_currency_formatting() -> None:
    assert fmt(Decimal("120000"), "INR") == "₹1,20,000"
    assert fmt(Decimal("7900"), "INR") == "₹7,900"
    assert fmt(Decimal("94.05"), "USD") == "$94.05"
