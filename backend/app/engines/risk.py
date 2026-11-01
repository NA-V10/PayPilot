"""Transparent, rule-based risk scoring (0 = safe, 100 = dangerous).

Each factor is scored independently with human-readable reasons. The overall score is a
weighted average, floored by the single worst factor so one critical signal cannot be
diluted by several benign ones.
"""

from __future__ import annotations

from app.core.enums import RiskLevel, VerificationStatus
from app.core.money import convert
from app.engines.policy import NEW_MERCHANT_DAYS, fmt
from app.schemas.domain import (
    MerchantProfile,
    PolicySpec,
    RiskAssessment,
    RiskFactor,
    ShieldResult,
    SpendingContext,
    TransactionProposal,
)

WEIGHTS = {
    "merchant": 0.25,
    "transaction": 0.20,
    "behavior": 0.15,
    "policy": 0.15,
    "prompt_injection": 0.25,
}

# Inherent category risk (fraud / irreversibility exposure).
CATEGORY_RISK = {
    "travel": 10,
    "hotel": 10,
    "flights": 12,
    "electronics": 15,
    "saas": 8,
    "software": 8,
    "cloud": 8,
    "office_supplies": 6,
    "groceries": 4,
    "gift_cards": 55,
    "crypto": 70,
    "gambling": 75,
    "wire_transfer": 65,
}
DEFAULT_CATEGORY_RISK = 20

DOMINANT_FLOOR_THRESHOLD = 70
DOMINANT_FLOOR_FACTOR = 0.9


class RiskEngineUnavailable(RuntimeError):
    """Raised when risk cannot be computed. Callers must fail closed."""


def level_for(score: int) -> RiskLevel:
    if score >= 80:
        return RiskLevel.CRITICAL
    if score >= 60:
        return RiskLevel.HIGH
    if score >= 30:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _clamp(v: float) -> int:
    return max(0, min(100, round(v)))


def merchant_risk(m: MerchantProfile) -> RiskFactor:
    score = 100 - m.trust_score
    reasons = [f"Trust score {m.trust_score}/100"]
    bump = {
        VerificationStatus.VERIFIED: 0,
        VerificationStatus.PENDING: 10,
        VerificationStatus.UNVERIFIED: 25,
        VerificationStatus.FLAGGED: 40,
    }[m.verification_status]
    score += bump
    reasons.append(f"Verification: {m.verification_status.value.lower()}" + (f" (+{bump})" if bump else ""))
    if m.age_days < NEW_MERCHANT_DAYS:
        score += 15
        reasons.append(f"Merchant is {m.age_days} days old (+15)")
    elif m.age_days < 180:
        score += 5
        reasons.append(f"Merchant is {m.age_days} days old (+5)")
    if m.refund_rate > 0.10:
        score += 10
        reasons.append(f"High refund rate {m.refund_rate:.1%} (+10)")
    elif m.refund_rate > 0.05:
        score += 5
        reasons.append(f"Elevated refund rate {m.refund_rate:.1%} (+5)")
    if m.chargeback_rate > 0.02:
        score += 15
        reasons.append(f"High chargeback rate {m.chargeback_rate:.1%} (+15)")
    elif m.chargeback_rate > 0.01:
        score += 7
        reasons.append(f"Elevated chargeback rate {m.chargeback_rate:.1%} (+7)")
    return RiskFactor(name="Merchant", key="merchant", score=_clamp(score), weight=WEIGHTS["merchant"], reasons=reasons)


def transaction_risk(p: TransactionProposal, m: MerchantProfile, policy: PolicySpec) -> RiskFactor:
    amount = convert(p.amount, p.currency, policy.currency)
    reasons: list[str] = []
    ratio = float(amount / policy.max_transaction_amount) if policy.max_transaction_amount else 2.0
    if ratio <= 1:
        amt_score = ratio * 30
        reasons.append(f"Amount is {ratio:.0%} of the per-transaction maximum")
    else:
        amt_score = 40 + min(20, (ratio - 1) * 20)
        reasons.append(f"Amount is {ratio:.1f}x the per-transaction maximum")
    cat = CATEGORY_RISK.get(p.category, DEFAULT_CATEGORY_RISK)
    score = amt_score + cat * 0.5
    reasons.append(f"Category '{p.category}' inherent risk {cat}")
    if p.currency != policy.currency:
        score += 10
        reasons.append(f"Foreign currency {p.currency} (+10)")
    if m.country != policy.home_country:
        score += 10
        reasons.append(f"International merchant ({m.country}) (+10)")
    if m.age_days < NEW_MERCHANT_DAYS:
        score += 15
        reasons.append("First-time / new merchant (+15)")
    return RiskFactor(name="Transaction", key="transaction", score=_clamp(score), weight=WEIGHTS["transaction"], reasons=reasons)


def behavior_risk(p: TransactionProposal, s: SpendingContext, policy: PolicySpec) -> RiskFactor:
    amount = convert(p.amount, p.currency, policy.currency)
    score = 0.0
    reasons: list[str] = []
    if s.tx_last_hour >= 5:
        score += 40
        reasons.append(f"High velocity: {s.tx_last_hour} transactions in the last hour (+40)")
    elif s.tx_last_hour >= 3:
        score += 20
        reasons.append(f"Elevated velocity: {s.tx_last_hour} transactions in the last hour (+20)")
    if s.average_amount and s.history_count >= 3:
        mult = float(amount / s.average_amount) if s.average_amount else 0
        if mult > 3:
            score += 30
            reasons.append(f"Spending spike: {mult:.1f}x this agent's average (+30)")
        elif mult > 2:
            score += 15
            reasons.append(f"Above-normal amount: {mult:.1f}x average (+15)")
    if s.known_categories and p.category not in s.known_categories:
        score += 20
        reasons.append(f"Unusual category for this agent: '{p.category}' (+20)")
    if not reasons:
        reasons.append("Consistent with this agent's history")
    return RiskFactor(name="Behavior", key="behavior", score=_clamp(score), weight=WEIGHTS["behavior"], reasons=reasons)


def policy_risk(p: TransactionProposal, s: SpendingContext, policy: PolicySpec) -> RiskFactor:
    """How close the transaction pushes the agent to its limits."""
    amount = convert(p.amount, p.currency, policy.currency)
    reasons: list[str] = []
    util_tx = float(amount / policy.max_transaction_amount) if policy.max_transaction_amount else 2.0
    util_day = float((s.daily_total + amount) / policy.daily_spending_limit) if policy.daily_spending_limit else 2.0
    util = max(util_tx, util_day)
    score = util * 60 if util <= 1 else 80 + min(20, (util - 1) * 20)
    reasons.append(f"Limit utilisation {util:.0%}")
    if p.intent_budget is not None:
        budget = convert(p.intent_budget, p.currency, policy.currency)
        if amount > budget:
            score = max(score, 90)
            reasons.append(f"Exceeds user's stated budget {fmt(budget, policy.currency)}")
    return RiskFactor(name="Policy proximity", key="policy", score=_clamp(score), weight=WEIGHTS["policy"], reasons=reasons)


def injection_risk(shield: ShieldResult) -> RiskFactor:
    if not shield.threats:
        reasons = [shield.summary]
    else:
        reasons = [f"{t.title} in {t.source}" for t in shield.threats[:4]]
    return RiskFactor(
        name="Prompt injection", key="prompt_injection", score=shield.risk_score, weight=WEIGHTS["prompt_injection"], reasons=reasons
    )


def assess(
    proposal: TransactionProposal,
    merchant: MerchantProfile,
    spending: SpendingContext,
    policy: PolicySpec,
    shield: ShieldResult,
) -> RiskAssessment:
    try:
        factors = [
            merchant_risk(merchant),
            transaction_risk(proposal, merchant, policy),
            behavior_risk(proposal, spending, policy),
            policy_risk(proposal, spending, policy),
            injection_risk(shield),
        ]
    except (ArithmeticError, ValueError, KeyError) as exc:
        raise RiskEngineUnavailable(str(exc)) from exc

    weighted = sum(f.score * f.weight for f in factors)
    worst = max(factors, key=lambda f: f.score)
    overall = weighted
    method = "weighted average"
    if worst.score >= DOMINANT_FLOOR_THRESHOLD and worst.score * DOMINANT_FLOOR_FACTOR > weighted:
        overall = worst.score * DOMINANT_FLOOR_FACTOR
        method = f"floored by dominant factor '{worst.name}'"
    overall_i = _clamp(overall)

    by_key = {f.key: f.score for f in factors}
    notable = sorted((f for f in factors if f.score >= 30), key=lambda f: -f.score)
    reasons = [f"{f.name} risk {f.score}: {f.reasons[0]}" for f in notable] or ["All risk factors are low"]

    return RiskAssessment(
        transaction_risk=by_key["transaction"],
        merchant_risk=by_key["merchant"],
        behavior_risk=by_key["behavior"],
        policy_risk=by_key["policy"],
        prompt_injection_risk=by_key["prompt_injection"],
        overall_score=overall_i,
        level=level_for(overall_i),
        factors=factors,
        reasons=reasons,
        method=method,
    )
