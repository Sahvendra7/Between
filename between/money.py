"""Money is integer US cents. Typed amounts come from people, never from the model unconfirmed."""
from __future__ import annotations

import re

MAX_MINOR = 100_000_000  # $1,000,000.00
_SHAPE = re.compile(r"^(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$")


class MoneyError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def parse_usd(text: str) -> int:
    s = (text or "").strip().replace("$", "").strip()
    if not s:
        raise MoneyError("empty")
    if s.startswith("-"):
        raise MoneyError("not_positive")
    if not _SHAPE.match(s):
        raise MoneyError("format")
    whole, _, frac = s.replace(",", "").partition(".")
    if len(frac) > 2:
        raise MoneyError("too_many_decimals")
    cents = int(whole) * 100 + int((frac + "00")[:2])
    if cents <= 0:
        raise MoneyError("not_positive")
    if cents > MAX_MINOR:
        raise MoneyError("too_large")
    return cents


def fmt_usd(cents: int) -> str:
    return f"${cents // 100:,}.{cents % 100:02d}"


def split_amount(amount: int, shares: dict[str, int]) -> dict[str, int]:
    """Whole cents that always add up; leftover cents go to the largest remainders, then A before B."""
    exact = {p: amount * pct for p, pct in shares.items()}
    out = {p: v // 100 for p, v in exact.items()}
    left = amount - sum(out.values())
    for p in sorted(shares, key=lambda p: (-(exact[p] % 100), p))[:left]:
        out[p] += 1
    return out


def fee_estimate(cents: int) -> int:
    """PayPal's commercial fee as the sandbox charged it (3.49% + $0.49). Always shown as an estimate."""
    return (cents * 349 + 5000) // 10000 + 49
