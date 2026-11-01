"""Natural Language Policy Compiler.

"You can spend up to ₹20,000 per transaction. Anything above ₹10,000 needs my approval."
  -> structured, *validated* PolicySpec changes, shown to the user before saving.

The LLM (when configured) only proposes field values. The merged result must pass
PolicySpec validation before it can be stored, and the user confirms it in the UI.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from app.engines.policy import fmt
from app.services.llm import LLMUnavailable, get_llm
from app.services.parsing import CATEGORY_KEYWORDS, categories_in, parse_amount
from app.schemas.domain import PolicySpec

FIELD_LABELS = {
    "max_transaction_amount": "Maximum transaction",
    "require_approval_above": "Approval required above",
    "daily_spending_limit": "Daily limit",
    "monthly_spending_limit": "Monthly limit",
    "minimum_merchant_trust": "Minimum merchant trust",
    "allowed_categories": "Allowed categories",
    "blocked_categories": "Blocked categories",
    "allow_new_merchants": "New merchants",
    "allow_international": "International payments",
    "auto_refund_enabled": "Automatic refunds",
}
MONEY_FIELDS = {"max_transaction_amount", "require_approval_above", "daily_spending_limit", "monthly_spending_limit"}


class FieldChange(BaseModel):
    field: str
    label: str
    before: Any
    after: Any
    display: str


class CompileResult(BaseModel):
    instruction: str
    source: Literal["llm", "rules"]
    changes: list[FieldChange]
    policy: PolicySpec | None
    valid: bool
    errors: list[str]
    notes: list[str]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.;!?\n])\s+|\band\b(?=\s+(?:anything|any|never|only|no|don't|do not))", text) if s and s.strip()]


def _money_after(sentence: str, anchor: re.Pattern[str]) -> Decimal | None:
    m = anchor.search(sentence)
    if not m:
        return None
    parsed = parse_amount(sentence[m.start() :]) or parse_amount(sentence)
    return parsed[0] if parsed else None


APPROVAL_RE = re.compile(r"approv|ask me|check with me|confirm with me|need my (ok|okay|sign)", re.I)
ABOVE_RE = re.compile(r"\b(above|over|more than|exceeding|greater than|beyond)\b", re.I)
MAX_RE = re.compile(r"\b(up to|max(imum)?|at most|no more than|not more than|cap|limit|spend)\b", re.I)
DAILY_RE = re.compile(r"\b(per day|a day|daily|each day|every day)\b", re.I)
MONTHLY_RE = re.compile(r"\b(per month|a month|monthly|each month|every month)\b", re.I)
TRUST_NUM_RE = re.compile(r"trust(?:\s*score)?[^\d]{0,20}(\d{1,3})", re.I)
SUSPICIOUS_RE = re.compile(r"suspicious|sketchy|untrusted|unverified|shady|scam|risky merchants|only trusted|trusted merchants", re.I)
NEGATIVE_RE = re.compile(r"\b(never|don't|do not|no|not|without|avoid|block)\b", re.I)


def compile_rules(text: str) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    for s in _sentences(text):
        lower = s.lower()
        negative = bool(NEGATIVE_RE.search(s))

        if APPROVAL_RE.search(s):
            amt = _money_after(s, ABOVE_RE)
            if amt is not None:
                changes["require_approval_above"] = amt
            continue

        if DAILY_RE.search(s):
            amt = parse_amount(s)
            if amt:
                changes["daily_spending_limit"] = amt[0]
            continue
        if MONTHLY_RE.search(s):
            amt = parse_amount(s)
            if amt:
                changes["monthly_spending_limit"] = amt[0]
            continue

        if MAX_RE.search(s) and ("transaction" in lower or "purchase" in lower or "payment" in lower or "spend" in lower):
            amt = parse_amount(s)
            if amt:
                changes["max_transaction_amount"] = amt[0]
                continue

        if "trust" in lower:
            m = TRUST_NUM_RE.search(s)
            if m and 0 <= int(m.group(1)) <= 100:
                changes["minimum_merchant_trust"] = int(m.group(1))
                continue
        if SUSPICIOUS_RE.search(s):
            changes["minimum_merchant_trust"] = max(80, int(changes.get("minimum_merchant_trust", 0)))
            if "new" in lower:
                changes["allow_new_merchants"] = False
            continue

        if "international" in lower or "foreign" in lower or "abroad" in lower or "domestic only" in lower:
            changes["allow_international"] = not negative and "domestic only" not in lower
            continue
        if "new merchant" in lower or "unknown merchant" in lower or "new vendor" in lower:
            changes["allow_new_merchants"] = not negative
            continue
        if "refund" in lower:
            changes["auto_refund_enabled"] = not negative
            continue

        cats = categories_in(s)
        if cats:
            if re.search(r"\bonly\b", lower) and not negative:
                changes["allowed_categories"] = cats
            elif negative:
                changes["blocked_categories"] = sorted(set(changes.get("blocked_categories", [])) | set(cats))
    return changes


SYSTEM_PROMPT = f"""You convert a user's spending instructions for an AI agent into policy fields.
Return ONLY a JSON object containing just the fields the user actually specified, from:
max_transaction_amount (number), require_approval_above (number), daily_spending_limit (number),
monthly_spending_limit (number), minimum_merchant_trust (0-100 integer; "avoid suspicious merchants" means 80),
allowed_categories (array), blocked_categories (array), allow_new_merchants (bool),
allow_international (bool), auto_refund_enabled (bool).
Valid categories: {", ".join(CATEGORY_KEYWORDS)}.
Amounts are plain numbers in the user's currency (e.g. "₹1.2 lakh" -> 120000). Do not invent values."""


def _display(field: str, value: Any, currency: str) -> str:
    if field in MONEY_FIELDS:
        return fmt(Decimal(str(value)), currency)
    if field == "minimum_merchant_trust":
        return f"{value}%"
    if isinstance(value, bool):
        return "Allowed" if value else "Not allowed"
    if isinstance(value, list):
        return ", ".join(v.replace("_", " ") for v in value) or "None"
    return str(value)


def compile_policy(text: str, base: PolicySpec) -> CompileResult:
    llm = get_llm()
    source: Literal["llm", "rules"] = "rules"
    notes: list[str] = []
    if llm is not None:
        try:
            raw = llm.complete_json(SYSTEM_PROMPT, text)
            source = "llm"
        except LLMUnavailable:
            # Compiling is not an authorization decision, and the output is still validated and
            # human-confirmed, so falling back to the deterministic parser is safe here.
            raw = compile_rules(text)
            notes.append("AI service unavailable; used the deterministic rule parser instead.")
    else:
        raw = compile_rules(text)

    allowed_fields = set(FIELD_LABELS)
    raw = {k: v for k, v in raw.items() if k in allowed_fields and v is not None}

    merged = base.model_dump()
    merged.update(raw)

    # Keep the policy coherent when the user only changed one side of a relationship.
    if "require_approval_above" not in raw and Decimal(str(merged["require_approval_above"])) > Decimal(str(merged["max_transaction_amount"])):
        merged["require_approval_above"] = merged["max_transaction_amount"]
        notes.append("Approval threshold lowered to match the new maximum transaction.")
    if "max_transaction_amount" not in raw and "require_approval_above" in raw and Decimal(str(raw["require_approval_above"])) > Decimal(str(merged["max_transaction_amount"])):
        merged["max_transaction_amount"] = raw["require_approval_above"]
        notes.append("Maximum transaction raised to match the approval threshold.")
    if "monthly_spending_limit" not in raw and Decimal(str(merged["daily_spending_limit"])) > Decimal(str(merged["monthly_spending_limit"])):
        merged["monthly_spending_limit"] = Decimal(str(merged["daily_spending_limit"])) * 30
        notes.append("Monthly limit raised to stay above the daily limit.")

    errors: list[str] = []
    policy: PolicySpec | None = None
    try:
        policy = PolicySpec.model_validate(merged)
    except ValidationError as exc:
        errors = [e["msg"].removeprefix("Value error, ") for e in exc.errors()]

    before = base.model_dump()
    after = policy.model_dump() if policy else merged
    changes = [
        FieldChange(
            field=f,
            label=FIELD_LABELS[f],
            before=float(before[f]) if f in MONEY_FIELDS else before[f],
            after=float(after[f]) if f in MONEY_FIELDS else after[f],
            display=_display(f, after[f], base.currency),
        )
        for f in FIELD_LABELS
        if f in raw or (policy and after[f] != before[f])
    ]
    if not raw:
        notes.append("No policy rules were recognised in this instruction.")

    return CompileResult(
        instruction=text,
        source=source,
        changes=changes,
        policy=policy,
        valid=policy is not None and bool(raw),
        errors=errors,
        notes=notes,
    )
