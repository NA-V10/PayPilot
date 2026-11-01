"""Approval Engine: combines AgentShield, Risk and Policy into one final, deterministic decision.

Precedence (first match wins):
  1. Any engine failed to run           -> BLOCK (fail closed)
  2. AgentShield verdict BLOCK          -> BLOCK
  3. Overall risk CRITICAL (>= 80)      -> BLOCK
  4. Policy DENY                        -> DENY
  5. Policy approval threshold, risk HIGH, or shield SUSPICIOUS -> HUMAN_APPROVAL_REQUIRED
  6. Otherwise                          -> ALLOW
"""

from __future__ import annotations

from app.core.enums import Decision, FinalDecision, RiskLevel, TransactionStatus
from app.schemas.domain import DecisionResult, PolicyResult, RiskAssessment, ShieldResult


def fail_closed(stage: str, reason: str) -> DecisionResult:
    return DecisionResult(
        decision=FinalDecision.BLOCK,
        status=TransactionStatus.BLOCKED,
        blocking_stage=stage,
        reasons=[f"{reason}. PayPilot cannot safely evaluate this transaction, so it was blocked. No money was moved."],
        fail_closed=True,
    )


def decide(shield: ShieldResult | None, risk: RiskAssessment | None, policy: PolicyResult | None) -> DecisionResult:
    if shield is None:
        return fail_closed("shield", "AgentShield unavailable")
    if risk is None:
        return fail_closed("risk", "Risk engine unavailable")
    if policy is None:
        return fail_closed("policy", "Policy engine unavailable")

    reasons: list[str] = []
    blocking_stage: str | None = None

    if shield.verdict == "BLOCK":
        blocking_stage = "shield"
        reasons.append(f"AgentShield: {shield.summary}")
    if risk.level == RiskLevel.CRITICAL:
        blocking_stage = blocking_stage or "risk"
        reasons.append(f"Risk engine: overall risk {risk.overall_score}/100 ({risk.level})")
    if policy.decision == Decision.DENY:
        reasons.extend(f"Policy: {r}" for r in policy.reasons)

    if blocking_stage:
        return DecisionResult(decision=FinalDecision.BLOCK, status=TransactionStatus.BLOCKED, blocking_stage=blocking_stage, reasons=reasons)

    if policy.decision == Decision.DENY:
        return DecisionResult(decision=FinalDecision.DENY, status=TransactionStatus.DENIED, blocking_stage="policy", reasons=reasons)

    if policy.decision == Decision.HUMAN_APPROVAL_REQUIRED:
        reasons.extend(policy.reasons)
    if risk.level == RiskLevel.HIGH:
        reasons.append(f"Risk is elevated ({risk.overall_score}/100); a human must confirm")
    if shield.verdict == "SUSPICIOUS":
        reasons.append(f"AgentShield flagged suspicious content: {shield.summary}")

    if reasons:
        return DecisionResult(
            decision=FinalDecision.HUMAN_APPROVAL_REQUIRED,
            status=TransactionStatus.AWAITING_APPROVAL,
            blocking_stage="approval",
            reasons=reasons,
        )

    return DecisionResult(
        decision=FinalDecision.ALLOW,
        status=TransactionStatus.APPROVED,
        blocking_stage=None,
        reasons=["All checks passed. Within the agent's autonomous authority."],
    )
