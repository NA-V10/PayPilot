"""Shared deterministic text parsing helpers (amounts, currencies, categories)."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

CURRENCY_TOKEN = r"(?:₹|rs\.?|inr|\$|usd|€|eur|£|gbp)"
AMOUNT_RE = re.compile(
    rf"(?P<cur>{CURRENCY_TOKEN})?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<mult>k|thousand|lakhs?|lacs?|l|cr|crores?|m|million)?\b\s*(?P<cur2>{CURRENCY_TOKEN})?",
    re.IGNORECASE,
)

MULTIPLIERS = {
    "k": 1_000,
    "thousand": 1_000,
    "l": 100_000,
    "lakh": 100_000,
    "lakhs": 100_000,
    "lac": 100_000,
    "lacs": 100_000,
    "cr": 10_000_000,
    "crore": 10_000_000,
    "crores": 10_000_000,
    "m": 1_000_000,
    "million": 1_000_000,
}

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "travel": ("hotel", "stay", "room", "resort", "flight", "trip", "travel", "booking", "hostel", "airbnb", "train"),
    "electronics": ("laptop", "macbook", "phone", "monitor", "headphone", "keyboard", "tablet", "camera", "electronics", "thinkpad"),
    "saas": ("saas", "subscription", "software", "license", "licence", "vendor", "invoice", "seat", "cloud"),
    "gift_cards": ("gift card", "giftcard", "voucher"),
    "crypto": ("crypto", "bitcoin", "ethereum", "usdt", "token"),
    "gambling": ("casino", "betting", "gambling", "poker", "lottery"),
    "office_supplies": ("stationery", "office supplies", "printer", "paper"),
}


def currency_of(token: str | None) -> str | None:
    if not token:
        return None
    t = token.lower().rstrip(".")
    if t in ("₹", "rs", "inr"):
        return "INR"
    if t in ("$", "usd"):
        return "USD"
    if t in ("€", "eur"):
        return "EUR"
    if t in ("£", "gbp"):
        return "GBP"
    return None


def parse_amount(text: str) -> tuple[Decimal, str | None] | None:
    """Parse the first money amount in `text`. Returns (amount, currency or None)."""
    for m in AMOUNT_RE.finditer(text):
        try:
            value = Decimal(m.group("num").replace(",", ""))
        except InvalidOperation:
            continue
        mult = (m.group("mult") or "").lower()
        if mult:
            value *= MULTIPLIERS[mult]
        cur = currency_of(m.group("cur")) or currency_of(m.group("cur2"))
        # Ignore bare small numbers like "3 nights" unless a currency or multiplier is present.
        if cur is None and not mult and value < 100:
            continue
        return value, cur
    return None


def detect_category(text: str) -> str | None:
    lower = text.lower()
    for category, words in CATEGORY_KEYWORDS.items():
        if any(w in lower for w in words):
            return category
    return None


def categories_in(text: str) -> list[str]:
    lower = text.lower()
    return [c for c, words in CATEGORY_KEYWORDS.items() if any(w in lower for w in words) or c.replace("_", " ") in lower]
