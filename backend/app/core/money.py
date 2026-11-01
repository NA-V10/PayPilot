"""Currency handling. Amounts are always Decimal; floats never enter decision logic."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import PlainSerializer

from app.core.config import get_settings

# Serialize Decimal as a JSON number so the frontend receives numbers, not strings.
Money = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]


class UnsupportedCurrency(ValueError):
    pass


def q2(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def convert(amount: Decimal, from_ccy: str, to_ccy: str) -> Decimal:
    if from_ccy == to_ccy:
        return amount
    rates = get_settings().fx_rates
    try:
        return q2(amount / rates[from_ccy] * rates[to_ccy])
    except KeyError as exc:
        raise UnsupportedCurrency(f"No FX rate configured for {exc.args[0]}") from exc
