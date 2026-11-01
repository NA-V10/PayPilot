"""Intent Engine: turns a natural-language request into a structured, validated intent."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.core.money import Money
from app.services.llm import LLMUnavailable, get_llm
from app.services.parsing import CURRENCY_TOKEN, detect_category, parse_amount

AGENT_FOR_CATEGORY = {"travel": "travel", "electronics": "shopping", "saas": "business", "office_supplies": "business"}


class Intent(BaseModel):
    agent_type: Literal["travel", "shopping", "business"] | None = None
    query: str = Field(max_length=200)
    category: str | None = Field(default=None, max_length=40)
    max_budget: Money | None = Field(default=None, gt=0)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    location: str | None = Field(default=None, max_length=80)
    avoid_suspicious_merchants: bool = False
    constraints: list[str] = Field(default_factory=list, max_length=10)
    source: Literal["llm", "rules"] = "rules"


BUDGET_RE = re.compile(
    rf"\b(under|below|less than|max(?:imum)?|up to|within|budget(?: of)?|not more than|pay|for)\s+(?:{CURRENCY_TOKEN}\s*)?\d",
    re.IGNORECASE,
)
LOCATION_RE = re.compile(r"\b(?:in|at|near|to)\s+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)")
SUSPICIOUS_RE = re.compile(r"suspicious|sketchy|untrusted|unverified|scam|shady|trusted|verified", re.IGNORECASE)


def parse_intent_rules(text: str, default_currency: str = "INR") -> Intent:
    budget: Decimal | None = None
    currency = default_currency
    m = BUDGET_RE.search(text)
    parsed = parse_amount(text[m.start() :]) if m else None
    if parsed is None:
        # "Pay this SaaS vendor ₹25,000": any explicit currency amount is the cap.
        candidate = parse_amount(text)
        parsed = candidate if candidate and candidate[1] else None
    if parsed:
        budget, cur = parsed
        currency = cur or default_currency
    category = detect_category(text)
    loc = LOCATION_RE.search(text)
    constraints: list[str] = []
    avoid = bool(SUSPICIOUS_RE.search(text))
    if avoid:
        constraints.append("Only use trusted merchants")
    if budget:
        constraints.append(f"Budget cap {currency} {budget:,.0f}")
    return Intent(
        agent_type=AGENT_FOR_CATEGORY.get(category or ""),  # type: ignore[arg-type]
        query=text.strip()[:200],
        category=category,
        max_budget=budget,
        currency=currency,
        location=loc.group(1) if loc else None,
        avoid_suspicious_merchants=avoid,
        constraints=constraints,
        source="rules",
    )


SYSTEM_PROMPT = """You extract purchase intent for a payments governance system.
Return ONLY a JSON object with keys:
agent_type ("travel"|"shopping"|"business"|null), query (short string), category
("travel"|"electronics"|"saas"|"office_supplies"|"gift_cards"|"crypto"|"gambling"|null),
max_budget (number or null; the user's spending cap), currency (ISO code, default INR),
location (string or null), avoid_suspicious_merchants (boolean), constraints (array of short strings).
Never invent a budget the user did not state."""


def extract_intent(text: str, default_currency: str = "INR") -> Intent:
    """Use the LLM when configured; otherwise the deterministic parser.

    If an LLM is configured but fails or returns invalid output, this raises LLMUnavailable
    and the caller fails closed. A misread budget is not something we guess about.
    """
    llm = get_llm()
    if llm is None:
        return parse_intent_rules(text, default_currency)
    data = llm.complete_json(SYSTEM_PROMPT, text)
    try:
        data["source"] = "llm"
        data.setdefault("query", text[:200])
        data["currency"] = data.get("currency") or default_currency
        return Intent.model_validate(data)
    except ValidationError as exc:
        raise LLMUnavailable(f"LLM returned an invalid intent: {exc.error_count()} validation error(s)") from exc
